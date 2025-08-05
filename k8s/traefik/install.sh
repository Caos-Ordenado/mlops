#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Adding Traefik Helm repository..."
helm repo add traefik https://traefik.github.io/charts
helm repo update

echo "Installing Traefik..."
helm upgrade --install traefik traefik/traefik \
  --namespace kube-system \
  --create-namespace \
  --values "${SCRIPT_DIR}/values.yaml" \
  --timeout 5m \
  --debug \
  --wait

echo "Applying TCP IngressRoutes for PostgreSQL and Redis..."
kubectl apply -f "${SCRIPT_DIR}/tcp-ingressroutes.yaml"

echo "Applying custom NodePort service for additional entrypoints..."
kubectl apply -f "${SCRIPT_DIR}/custom-nodeports-service.yaml"

echo "Traefik installation completed!"
echo "Dashboard available at: http://home.server:31080/dashboard"
echo "Web services available at: http://home.server:30080/"

echo "PostgreSQL available at: home.server:32080"
echo "Redis available at: home.server:32081"