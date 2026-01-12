# Website Service

Nginx-based static website serving the main www.reyops.com homepage.

## Overview

- **Image**: nginx:1.27-alpine
- **Resources**: 50m-200m CPU, 64Mi-128Mi RAM
- **Port**: 80
- **Namespace**: default

## Access

- **Public**: https://www.reyops.com/ (via Cloudflare Tunnel)
- **VPN**: http://home.server:30080/

## Architecture

```
┌─────────────────┐
│ Cloudflare      │
│ Tunnel          │
└────────┬────────┘
         │
    ┌────▼─────┐
    │ Traefik  │ :30080/web
    │ Ingress  │
    └────┬─────┘
         │
    ┌────▼────┐
    │ Website │ :80
    │ Service │
    └────┬────┘
         │
    ┌────▼─────┐
    │  Nginx   │
    │   Pod    │
    └──────────┘
```

## Routing Priority

The IngressRoute is configured with proper priorities to avoid conflicts:

| Service | Host | Path | Priority |
|---------|------|------|----------|
| web-crawler | www.reyops.com | /crawler | 200 |
| website | www.reyops.com | / | 100 |
| web-crawler | (any) | /crawler | 100 |
| website | (any) | / | 50 |

This ensures `/crawler` requests are always routed to the web crawler service.

## Content

The website content is stored in a ConfigMap (`website-html`) and includes:
- Landing page with service links
- Beautiful gradient design
- Responsive layout
- Links to: /crawler, /renderer, /ollama, /logs

## Health Check

- **Endpoint**: `/health`
- **Response**: `healthy`
- **Used by**: Kubernetes liveness and readiness probes

## Cloudflare Tunnel Configuration

To expose the website publicly, update `~/.cloudflared/config.yml`:

```yaml
tunnel: 82b29fec-7318-4c64-af2f-e2868c49196e
credentials-file: /etc/cloudflared/82b29fec-7318-4c64-af2f-e2868c49196e.json

ingress:
  # Expose /crawler/* on www.reyops.com
  - hostname: www.reyops.com
    path: ^/crawler(/.*)?$
    service: http://localhost:30080
    originRequest:
      httpHostHeader: localhost
  
  # Expose root path on www.reyops.com
  - hostname: www.reyops.com
    service: http://localhost:30080
    originRequest:
      httpHostHeader: www.reyops.com
  
  # Catch-all - 404 for other paths
  - service: http_status:404
```

Then restart the tunnel:
```bash
sudo systemctl restart cloudflared
```

## Updating Content

To update the website content:

1. Edit `configmap.yaml` - modify the `index.html` section
2. Apply changes: `kubectl apply -f configmap.yaml`
3. Restart deployment: `kubectl rollout restart deployment/website -n default`

## Monitoring

```bash
# Check pod status
kubectl get pods -n default -l app=website

# View logs
kubectl logs -n default -l app=website

# Check resource usage
kubectl top pod -n default -l app=website

# Test health
kubectl exec -n default deployment/website -- curl -s http://localhost/health
```

## Configuration Files

- `configmap.yaml` - HTML content and nginx configuration
- `deployment.yaml` - Pod specification with health checks
- `service.yaml` - ClusterIP service on port 80
- `ingress.yaml` - Traefik IngressRoute with priorities
- `kustomization.yaml` - Resource manifest

## Future Enhancements

- [ ] Add SSL/TLS certificates
- [ ] Implement caching headers
- [ ] Add analytics tracking
- [ ] Create custom 404 page
- [ ] Add sitemap.xml
- [ ] Implement CSP headers

