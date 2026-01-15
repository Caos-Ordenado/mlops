#!/bin/bash

set -e
set -o pipefail

cd "$(dirname "$0")"

REMOTE_USER="${REMOTE_USER:-caos}"
REMOTE_HOST="${REMOTE_HOST:-home.server}"
REMOTE_PASS="${REMOTE_PASS:?Error: REMOTE_PASS environment variable not set}"
IMAGE_NAME="web"
IMAGE_TAG="dev-$(date +%Y%m%d%H%M%S)"
K8S_DIR="../../k8s/web"
BUILD_PLATFORM="linux/amd64"
TAR_GZ_PATH="/tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"

cleanup() {
  rm -f "${TAR_GZ_PATH}" || true
  [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

ensure_buildx_builder() {
  local builder_name="${BUILDX_BUILDER_NAME:-mlops-builder}"

  if ! docker buildx version >/dev/null 2>&1; then
    local docker_arch
    docker_arch="$(docker info --format '{{.Architecture}}' 2>/dev/null || true)"
    if [[ "$docker_arch" == "x86_64" || "$docker_arch" == "amd64" ]]; then
      echo "docker buildx is not available, but Docker daemon architecture is '$docker_arch'."
      echo "Proceeding without buildx (native amd64 daemon)."
      return 1
    fi

    echo "Error: docker buildx is not available (required to build ${BUILD_PLATFORM} images)."
    echo "Install buildx or run Colima as amd64."
    exit 1
  fi

  if ! docker buildx inspect "$builder_name" >/dev/null 2>&1; then
    docker buildx create --name "$builder_name" --driver docker-container --use >/dev/null
  else
    docker buildx use "$builder_name" >/dev/null
  fi

  docker buildx inspect --bootstrap >/dev/null
}

echo "Building and deploying web..."

TEMP_DIR=$(mktemp -d)
echo "Using temp dir: $TEMP_DIR"

mkdir -p "$TEMP_DIR/web"
cp -r ./* "$TEMP_DIR/web/"

cd "$TEMP_DIR/web"

if [ -f ".dockerignore" ]; then
  :
else
  cat > ".dockerignore" <<'EOF'
.git
**/node_modules/**
**/.nuxt/**
**/.output/**
**/dist/**
**/.env
.DS_Store
k8s/**
EOF
fi

echo "Building image for ${BUILD_PLATFORM} with tag ${IMAGE_NAME}:${IMAGE_TAG}"
if ensure_buildx_builder; then
  docker buildx build \
    --platform "${BUILD_PLATFORM}" \
    --load \
    -f Dockerfile \
    -t ${IMAGE_NAME}:${IMAGE_TAG} .
else
  docker build \
    --platform "${BUILD_PLATFORM}" \
    -f Dockerfile \
    -t ${IMAGE_NAME}:${IMAGE_TAG} .
fi

cd - >/dev/null

echo "Saving and compressing image..."
if command -v pigz >/dev/null 2>&1; then
  docker save ${IMAGE_NAME}:${IMAGE_TAG} | pigz -c > "${TAR_GZ_PATH}"
else
  docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip -c > "${TAR_GZ_PATH}"
fi

echo "Copying image to remote..."
sshpass -p "${REMOTE_PASS}" scp -C "${TAR_GZ_PATH}" ${REMOTE_USER}@${REMOTE_HOST}:/tmp/

echo "Importing into microk8s..."
sshpass -p "${REMOTE_PASS}" ssh ${REMOTE_USER}@${REMOTE_HOST} "set -e; echo '${REMOTE_PASS}' | sudo -S sh -c 'gunzip -c /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz | microk8s ctr image import -'; rm -f /tmp/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"

echo "Applying Kubernetes manifests..."
kubectl apply -k ${K8S_DIR}

echo "Updating deployment image to ${IMAGE_NAME}:${IMAGE_TAG}..."
kubectl set image deployment/web web=${IMAGE_NAME}:${IMAGE_TAG} -n default

echo "Restarting deployment..."
kubectl rollout restart deployment/web -n default

echo "Waiting for rollout..."
kubectl rollout status deployment/web -n default --timeout=300s

echo "Web deployed."
echo "Test health: curl http://home.server:30080/api/health"
