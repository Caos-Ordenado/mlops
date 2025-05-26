#!/bin/bash

# Langflow Deployment Script
set -e

echo "🚀 Deploying Langflow to MicroK8s cluster..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not available. Please install kubectl."
    exit 1
fi

# Check if we can connect to the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your cluster."
    exit 1
fi

echo "✅ Connected to Kubernetes cluster"

# Update Traefik configuration first
echo "🔧 Updating Traefik configuration for Langflow port..."
cd k8s/traefik && helm upgrade traefik traefik/traefik -f values.yaml -n kube-system
cd ../..

echo "⏳ Waiting for Traefik to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/traefik -n kube-system

# Deploy Langflow
echo "📦 Deploying Langflow components..."
kubectl apply -k k8s/langflow/

echo "⏳ Waiting for Langflow deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/langflow -n shared

echo "🔍 Checking pod status..."
kubectl get pods -n shared -l app=langflow

echo "🌐 Checking service status..."
kubectl get svc -n shared langflow

echo "🛡️ Checking ingress route..."
kubectl get ingressroutes.traefik.io langflow -n shared -o yaml

echo "✅ Langflow deployment completed!"
echo ""
echo "🌍 Access Langflow at: http://home.server:30081"
echo "👤 Default credentials: admin / admin123"
echo ""
echo "📊 To check logs: kubectl logs -n shared -l app=langflow -f"
echo "🔧 To debug: kubectl describe pod -n shared -l app=langflow" 