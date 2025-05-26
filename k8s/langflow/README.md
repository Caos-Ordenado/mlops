# Langflow Deployment

This directory contains the Kubernetes manifests to deploy Langflow on your home server MicroK8s cluster.

## Overview

Langflow is deployed in the `shared` namespace alongside PostgreSQL and Redis services. It uses:

- **PostgreSQL**: For persistent data storage
- **Redis**: For caching and session management  
- **Traefik**: For ingress routing on dedicated port 30081

## Files Structure

```
k8s/langflow/
├── configmap.yaml      # Environment variables and configuration
├── deployment.yaml     # Langflow pod deployment
├── service.yaml        # ClusterIP service
├── ingress.yaml        # Traefik IngressRoute on dedicated port
├── kustomization.yaml  # Kustomize configuration
├── deploy.sh          # Deployment script
└── README.md          # This file
```

## Configuration

### Environment Variables (configmap.yaml)

Key configurations:
- `LANGFLOW_HOST`: 0.0.0.0 (listen on all interfaces)
- `LANGFLOW_PORT`: 7860 (default Langflow port)
- `LANGFLOW_DATABASE_URL`: PostgreSQL connection
- `LANGFLOW_REDIS_URL`: Redis connection for caching

### Resources

- **CPU**: 200m requests, 500m limits
- **Memory**: 512Mi requests, 1Gi limits
- **Storage**: Uses shared PostgreSQL for persistence

## Deployment

### Quick Deploy

```bash
# Deploy Langflow (includes Traefik update)
./k8s/langflow/deploy.sh
```

### Manual Deploy

```bash
# Update Traefik first
cd k8s/traefik && helm upgrade traefik traefik/traefik -f values.yaml -n kube-system
cd ../..

# Apply manifests
kubectl apply -k k8s/langflow/

# Check deployment status
kubectl get pods -n shared -l app=langflow
kubectl get svc -n shared langflow
kubectl get ingressroute -n shared langflow
```

## Access

Once deployed, Langflow will be available at:

- **URL**: http://home.server:30081
- **Default Login**: admin / admin123

## Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n shared -l app=langflow
kubectl describe pod -n shared -l app=langflow
```

### View Logs
```bash
# Follow logs
kubectl logs -n shared -l app=langflow -f

# View recent logs
kubectl logs -n shared -l app=langflow --tail=100
```

### Check Database Connection
```bash
# Test PostgreSQL connection from Langflow pod
kubectl exec -n shared -l app=langflow -- psql $LANGFLOW_DATABASE_URL -c "SELECT version();"

# Test Redis connection
kubectl exec -n shared -l app=langflow -- redis-cli -u $LANGFLOW_REDIS_URL ping
```

### Common Issues

1. **Pod not starting**: Check if PostgreSQL and Redis are running
2. **Database connection errors**: Verify secret keys and database availability
3. **Ingress not working**: Ensure Traefik is running and IngressRoute is applied

## Health Checks

The deployment includes:
- **Liveness Probe**: `/health` endpoint (60s initial delay)
- **Readiness Probe**: `/health` endpoint (30s initial delay)

## Security Notes

⚠️ **Important**: Change the default credentials in production!

Update these values in `configmap.yaml`:
- `LANGFLOW_SECRET_KEY`
- `LANGFLOW_JWT_SECRET`
- `LANGFLOW_SUPERUSER_PASSWORD`

## Integration with Custom Agents

Langflow can be integrated with your custom agents in the `agents/` directory:

1. **API Access**: Your agents can call Langflow's API endpoints
2. **Shared Database**: Both can use the same PostgreSQL instance
3. **Shared Redis**: Both can use the same Redis for caching

### Example Agent Integration

```python
import requests

# Call Langflow API from your custom agent
response = requests.post(
    "http://home.server:30081/api/v1/process",
    json={"input": "Your prompt here"}
)
```

## Monitoring

### Resource Usage
```bash
kubectl top pods -n shared -l app=langflow
```

### Service Endpoints
```bash
kubectl get endpoints -n shared langflow
```

## Scaling

To scale Langflow:

```bash
# Scale to 2 replicas
kubectl scale deployment langflow -n shared --replicas=2
```

Note: Consider database connection limits when scaling.

## Cleanup

To remove Langflow:

```bash
kubectl delete -k k8s/langflow/
``` 