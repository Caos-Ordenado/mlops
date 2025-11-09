#!/bin/bash
set -e

# Ensure relative paths resolve from this script dir
cd "$(dirname "$0")"

# Config (reuse home server settings)
REMOTE_USER="${REMOTE_USER:-caos}"
REMOTE_HOST="${REMOTE_HOST:-home.server}"
REMOTE_PASS="${REMOTE_PASS:?Error: REMOTE_PASS environment variable not set}"
IMAGE_NAME="renderer"
# Unique tag to force rollout to pick new image
IMAGE_TAG="dev-$(date +%Y%m%d%H%M%S)"
K8S_DIR="../../k8s/renderer"

cleanup() {
  rm -f /tmp/${IMAGE_NAME}.tar.gz || true
  [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo "🚀 Building and deploying renderer..."

# Prepare temp build context
TEMP_DIR=$(mktemp -d)
echo "Using temp dir: $TEMP_DIR"

echo "Copying shared module..."
cp -r ../shared "$TEMP_DIR/shared"

echo "Copying renderer files..."
mkdir -p "$TEMP_DIR/renderer"
cp -r ./* "$TEMP_DIR/renderer/"

cd "$TEMP_DIR"

echo "🎯 Building image for linux/amd64 with tag ${IMAGE_NAME}:${IMAGE_TAG}"
if docker build \
  --platform linux/amd64 \
  --cache-from ${IMAGE_NAME}:${IMAGE_TAG} \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -f renderer/Dockerfile \
  -t ${IMAGE_NAME}:${IMAGE_TAG} .; then
  echo "✅ Image built"
else
  echo "❌ Build failed"; exit 1
fi

cd - >/dev/null

echo "💾 Saving and compressing image..."
docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip -c > /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz

echo "📤 Copying image to remote..."
sshpass -p "${REMOTE_PASS}" scp -C /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz ${REMOTE_USER}@${REMOTE_HOST}:/tmp/

echo "📥 Importing into microk8s..."
sshpass -p "${REMOTE_PASS}" ssh ${REMOTE_USER}@${REMOTE_HOST} "set -e; echo '${REMOTE_PASS}' | sudo -S sh -c 'gunzip -c /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz | microk8s ctr image import -'; rm -f /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"

echo "⚙️ Applying Kubernetes manifests..."
kubectl apply -k ${K8S_DIR}

# Point deployment to the freshly imported tag
echo "🔧 Updating deployment image to ${IMAGE_NAME}:${IMAGE_TAG}..."
kubectl set image deployment/renderer renderer=${IMAGE_NAME}:${IMAGE_TAG} -n default

echo "🔄 Restarting deployment..."
kubectl rollout restart deployment/renderer -n default

echo "⏳ Waiting for rollout..."
kubectl rollout status deployment/renderer -n default --timeout=300s

echo "✅ Renderer deployed."
echo "🌐 Test health: curl http://home.server:30080/renderer/health"

