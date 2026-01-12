# Open WebUI Tools Proxy

Small FastAPI service that exposes **stable HTTP endpoints** for Open WebUI “tools”, and forwards calls to:

- Web Crawler (`web-crawler` service)
- Renderer (`renderer` service)

This service is designed to run **inside the cluster** (ClusterIP only).

## Endpoints

- `GET /health` → `{ "status": "ok" }`
- `POST /crawl` → forwards to crawler `POST /crawl`
- `POST /render-html` → forwards to renderer `POST /render-html`
- `POST /screenshot` → forwards to renderer `POST /screenshot`
- `POST /extract-vision` → forwards to crawler `POST /extract-vision`

All tool endpoints return a normalized shape:

```json
{ "success": true, "data": { ... }, "error": null }
```

On failure:

```json
{ "success": false, "data": null, "error": "..." }
```

## Configuration

Environment variables:

- `CRAWLER_BASE_URL` (default: `http://web-crawler.default.svc.cluster.local:8000`)
- `RENDERER_BASE_URL` (default: `http://renderer.default.svc.cluster.local:8000`)
- `LOG_LEVEL` (default: `INFO`)
- `OPENWEBUI_TOOLS_HTTP_TIMEOUT_SECONDS` (default: `180`) — proxy timeout for upstream calls (increase for `/extract-vision`)

## Local run

```bash
cd services/openwebui_tools
./start.sh
```


