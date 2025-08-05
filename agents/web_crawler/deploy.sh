#!/bin/bash

# Exit on any error
set -e

# Simple deployment script that builds for linux/amd64 and deploys to home server

# Configuration
REMOTE_USER="caos"
REMOTE_HOST="internal-vpn-address"
REMOTE_PASS="***REMOVED***"
IMAGE_NAME="web-crawler"
IMAGE_TAG="latest"
K8S_DIR="../../k8s/web_crawler"

# Function to clean up temporary files
cleanup() {
    rm -f /tmp/${IMAGE_NAME}.tar
    rm -f /tmp/web-crawler-config.env
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

# Set up cleanup on script exit
trap cleanup EXIT

echo "🚀 Starting deployment process..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found in current directory"
    exit 1
fi

# Update ConfigMap first
echo "📝 Updating ConfigMap..."
grep -v "PASSWORD\|USER" .env | grep -v "^\s*#" | grep "=" > /tmp/web-crawler-config.env
if [ -s /tmp/web-crawler-config.env ]; then
    kubectl create configmap web-crawler-config --from-env-file=/tmp/web-crawler-config.env -n default --dry-run=client -o yaml | kubectl apply -f -
    echo "✅ ConfigMap updated successfully"
else
    echo "⚠️  Warning: No configuration found in .env file"
fi

# Build Docker image
echo "📦 Building Docker image..."
# Create a temporary directory for the build context
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_DIR"

# Copy the shared module
echo "Copying shared module..."
cp -r ../shared "$TEMP_DIR/"

# Copy the web crawler files
echo "Copying web crawler files..."
mkdir -p "$TEMP_DIR/web_crawler"
cp -r ./* "$TEMP_DIR/web_crawler/"

# Build the image from the temporary directory with retry logic
echo "Building Docker image (this may take a few minutes)..."
cd "$TEMP_DIR"

# Always build for linux/amd64 (Ubuntu server architecture)
BUILD_PLATFORM="linux/amd64"
echo "🎯 Building for server platform: $BUILD_PLATFORM"

# Build for linux/amd64 platform with optimizations
echo "Building Docker image with build optimizations..."
if docker build \
    --platform $BUILD_PLATFORM \
    --cache-from ${IMAGE_NAME}:${IMAGE_TAG} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -f web_crawler/Dockerfile \
    -t ${IMAGE_NAME}:${IMAGE_TAG} .; then
    echo "✅ Docker image built successfully"
    
    # Show image size for monitoring
    IMAGE_SIZE=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format "table {{.Size}}" | tail -n 1)
    echo "📊 Image size: $IMAGE_SIZE"
else
    echo "❌ Docker build failed"
    cd - > /dev/null
    exit 1
fi

# Return to original directory
cd - > /dev/null

# Save and transfer image
echo "💾 Saving Docker image..."
docker save ${IMAGE_NAME}:${IMAGE_TAG} -o /tmp/${IMAGE_NAME}.tar

echo "📤 Copying image to home server..."
if sshpass -p "${REMOTE_PASS}" scp /tmp/${IMAGE_NAME}.tar ${REMOTE_USER}@${REMOTE_HOST}:/tmp/; then
    echo "✅ Image copied successfully"
else
    echo "❌ Failed to copy image to remote server"
    exit 1
fi

echo "📥 Importing image into microk8s..."
if sshpass -p "${REMOTE_PASS}" ssh ${REMOTE_USER}@${REMOTE_HOST} "echo '${REMOTE_PASS}' | sudo -S microk8s ctr image import /tmp/${IMAGE_NAME}.tar && rm /tmp/${IMAGE_NAME}.tar"; then
    echo "✅ Image imported successfully"
else
    echo "❌ Failed to import image on remote server"
    exit 1
fi

# Apply k8s configurations
echo "⚙️ Applying Kubernetes configurations..."
if kubectl apply -k ${K8S_DIR}; then
    echo "✅ Kubernetes configurations applied"
else
    echo "❌ Failed to apply Kubernetes configurations"
    exit 1
fi

# Restart and wait for deployment
echo "🔄 Forcing a rollout restart..."
kubectl rollout restart deployment/web-crawler -n default

echo "⏳ Waiting for deployment to roll out..."
if kubectl rollout status deployment/web-crawler -n default --timeout=300s; then
    echo "✅ Deployment completed successfully!"
    echo "🌐 The web crawler is accessible at: http://home.server:30080/crawler/"
    echo "📝 Check the logs with: kubectl logs -n default -l app=web-crawler --tail=100"
else
    echo "❌ Deployment rollout timed out or failed"
    echo "📝 Check the logs with: kubectl logs -n default -l app=web-crawler --tail=100"
    exit 1
fi 