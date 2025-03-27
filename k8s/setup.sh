#!/bin/bash

# Exit on error
set -e

# Create namespace if it doesn't exist
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Apply ArgoCD manifests
kubectl apply -k argocd

# Wait for ArgoCD to be ready
echo "Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Get the initial admin password
echo "Initial admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo

# Add local domain to /etc/hosts if not already present
if ! grep -q "argocd.local" /etc/hosts; then
    echo "Adding argocd.local to /etc/hosts..."
    echo "127.0.0.1 argocd.local" | sudo tee -a /etc/hosts
fi

echo "Setup complete! You can now access ArgoCD at https://argocd.local"
echo "Default credentials:"
echo "Username: admin"
echo "Password: (shown above)" 