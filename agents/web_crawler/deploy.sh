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

echo "🚀 Starting deployment process..."

# Build the Docker image for AMD64 (home server architecture)
echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .

# Save the image to a tar file
echo "💾 Saving Docker image..."
docker save ${IMAGE_NAME}:${IMAGE_TAG} -o /tmp/${IMAGE_NAME}.tar

# Copy the tar to the home server
echo "📤 Copying image to home server..."
sshpass -p "${REMOTE_PASS}" scp /tmp/${IMAGE_NAME}.tar ${REMOTE_USER}@${REMOTE_HOST}:/tmp/

# Import the image into microk8s
echo "📥 Importing image into microk8s..."
sshpass -p "${REMOTE_PASS}" ssh ${REMOTE_USER}@${REMOTE_HOST} "echo '${REMOTE_PASS}' | sudo -S microk8s ctr image import /tmp/${IMAGE_NAME}.tar && rm /tmp/${IMAGE_NAME}.tar"

# Apply Kubernetes configurations
echo "⚙️ Applying Kubernetes configurations..."
kubectl apply -k ${K8S_DIR}

# Wait for the deployment to roll out
echo "⏳ Waiting for deployment to roll out..."
kubectl rollout status deployment/web-crawler -n shared

# Clean up local tar file
rm /tmp/${IMAGE_NAME}.tar

echo "✅ Deployment completed successfully!"
echo "🌐 The web crawler is accessible at: http://home.server/crawler/"
echo "📝 Check the logs with: kubectl logs -n shared -l app=web-crawler --tail=100" 