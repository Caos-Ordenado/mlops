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

echo "Applying Traefik dashboard service and IngressRoute..."
kubectl apply -f "${SCRIPT_DIR}/traefik-dashboard-service.yaml"
kubectl apply -f "${SCRIPT_DIR}/dashboard-ingressroute.yaml"

echo "Restarting Traefik deployment to ensure new config is loaded..."
kubectl rollout restart deployment traefik -n kube-system

echo "Traefik installation completed!"
echo "Dashboard available at: http://home.server:30080/dashboard/"
echo "Web services available at: http://home.server:30080/"