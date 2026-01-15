# Web (Nuxt SSR)

Nuxt 3 SSR portfolio site replacing the legacy nginx `website` service.

## Overview
- **Runtime**: Node.js (Nuxt 3 SSR)
- **Port**: 3000
- **Namespace**: default
- **Primary health**: `/api/health`

## Local development
```bash
./start.sh
```

## Build & deploy
```bash
./deploy.sh
```

## Endpoints
- `/` - portfolio homepage
- `/api/health` - health check (primary)
- `/health` - compatibility alias

## Cloudflare tunnel update (home.server)
Add `reyops.com` host rules to `~/.cloudflared/config.yml` (mirrors the existing
`www.reyops.com` setup):
```yaml
ingress:
  - hostname: reyops.com
    path: ^/crawler(/.*)?$
    service: http://localhost:30080
    originRequest:
      httpHostHeader: localhost

  - hostname: reyops.com
    service: http://localhost:30080
    originRequest:
      httpHostHeader: reyops.com
```

Then restart the tunnel:
```bash
sudo systemctl restart cloudflared
```

## Verification
```bash
curl http://home.server:30080/api/health
curl -H "Host: www.reyops.com" http://home.server:30080/api/health
curl -H "Host: reyops.com" http://home.server:30080/api/health
```
