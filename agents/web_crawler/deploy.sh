#!/bin/bash

# Exit on any error
set -e

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
}

# Set up cleanup on script exit
trap cleanup EXIT

echo "🚀 Starting deployment process..."

# Update ConfigMap and build image in parallel
echo "📝 Updating ConfigMap and building image..."
(
    grep -v "PASSWORD\|USER" .env | grep -v "^\s*#" | grep "=" > /tmp/web-crawler-config.env
    kubectl create configmap web-crawler-config --from-env-file=/tmp/web-crawler-config.env -n shared --dry-run=client -o yaml | kubectl apply -f -
) &

(
    echo "📦 Building Docker image..."
    # Create a temporary directory for the build context
    TEMP_DIR=$(mktemp -d)
    
    # Copy the shared module
    cp -r ../shared "$TEMP_DIR/"
    
    # Copy the web crawler files
    mkdir -p "$TEMP_DIR/web_crawler"
    cp -r ./* "$TEMP_DIR/web_crawler/"
    
    # Build the image from the temporary directory
    cd "$TEMP_DIR"
    docker build \
        --platform linux/amd64 \
        --memory-swap -1 \
        --memory 4g \
        -f web_crawler/Dockerfile \
        -t ${IMAGE_NAME}:${IMAGE_TAG} .
    
    # Clean up
    cd - > /dev/null
    rm -rf "$TEMP_DIR"
) &

# Wait for both processes to complete
wait

# Save and transfer image in parallel with k8s operations
echo "💾 Saving and transferring Docker image..."
(
    docker save ${IMAGE_NAME}:${IMAGE_TAG} -o /tmp/${IMAGE_NAME}.tar
    echo "📤 Copying image to home server..."
    sshpass -p "${REMOTE_PASS}" scp /tmp/${IMAGE_NAME}.tar ${REMOTE_USER}@${REMOTE_HOST}:/tmp/
    echo "📥 Importing image into microk8s..."
    sshpass -p "${REMOTE_PASS}" ssh ${REMOTE_USER}@${REMOTE_HOST} "echo '${REMOTE_PASS}' | sudo -S microk8s ctr image import /tmp/${IMAGE_NAME}.tar && rm /tmp/${IMAGE_NAME}.tar"
) &

# Apply k8s configurations in parallel
(
    echo "⚙️ Applying Kubernetes configurations..."
    kubectl apply -k ${K8S_DIR}
) &

# Wait for both processes to complete
wait

# Restart and wait for deployment
echo "🔄 Forcing a rollout restart..."
kubectl rollout restart deployment/web-crawler -n shared

echo "⏳ Waiting for deployment to roll out..."
kubectl rollout status deployment/web-crawler -n shared

echo "✅ Deployment completed successfully!"
echo "🌐 The web crawler is accessible at: http://home.server/crawler/"
echo "📝 Check the logs with: kubectl logs -n shared -l app=web-crawler --tail=100" 