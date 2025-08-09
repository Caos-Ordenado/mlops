# Renderer Service

A Playwright-based microservice for rendering web pages and producing artifacts for downstream agents.

## Features

- FastAPI API with async Playwright (Chromium)
- Endpoints:
  - `POST /screenshot` – capture screenshots (viewport or full page)
  - `POST /render-html` – return page HTML and extracted text
  - `GET /health` – readiness check
- Full-page strategies:
  - `native` – Playwright `full_page=true`
  - `scroll` – iterative scrolling with per-tile capture and vertical stitching
- Reliability improvements:
  - Blocks webfonts to avoid font-load stalls
  - Optional selector hiding to remove sticky modals/headers/footers
  - Auto-detect and crop fixed header/footer per tile
  - Layout-stability early stop (`stable_ticks`) to avoid duplicates
- Outputs
  - Returns base64 JPEG (quality 70)
  - Stores reduced-size snapshot under `/tmp/renderer-snapshots` with metadata JSON
  - Hourly cleanup daemon removes files older than TTL

## Request DTO (shared)
See `agents/shared/shared/interfaces/renderer.py`.

```python
class RendererScreenshotRequest(BaseModel):
    url: HttpUrl
    wait_for_selector: str = "body"
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 800
    wait_until: Literal["load","domcontentloaded","networkidle"] = "domcontentloaded"
    full_page: bool = False
    full_page_strategy: Literal["native","scroll"] = "scroll"
    scroll_pause_ms: int = 400
    max_scroll_steps: int = 30
    wait_network_idle_ms: int = 1500
    hide_selectors: List[str] = []
    detect_fixed: bool = True
    header_crop_px: int = 0
    footer_crop_px: int = 0
    stable_ticks: int = 3
```

Responses:
- Screenshot: `RendererScreenshotResponse { url, screenshot_b64, content_type, saved_path }`
- HTML: `RendererRenderHtmlResponse { url, html, text }`

## Example

Viewport-only (fast):
```bash
curl -sS -X POST $RENDERER_URL/screenshot -H 'Content-Type: application/json' \
  --data '{"url":"https://example.com","full_page":false,"timeout_ms":20000}' | jq -r '.saved_path'
```

Full-page scroll with sticky removal:
```json
{
  "url": "https://en.wikipedia.org/wiki/Instagram",
  "full_page": true,
  "full_page_strategy": "scroll",
  "timeout_ms": 60000,
  "hide_selectors": ["header", ".mw-sticky-header", ".mwe-popups"],
  "detect_fixed": true,
  "stable_ticks": 3
}
```

## Environment

- RENDERER_HEADLESS=true
- RENDERER_VIEWPORT_WIDTH=1280
- RENDERER_VIEWPORT_HEIGHT=800
- RENDERER_SNAPSHOT_DIR=/tmp/renderer-snapshots
- RENDERER_SNAPSHOT_TTL_SECONDS=86400
- RENDERER_CLEANUP_INTERVAL_SECONDS=3600

## Kubernetes

Manifests under `k8s/renderer/` (Deployment, Service, IngressRoute, ConfigMap). Exposed via Traefik (`/renderer`).

## Clients

Use the shared `RendererClient`:
```python
from shared.renderer_client import RendererClient
from shared.interfaces.renderer import RendererScreenshotRequest

async with RendererClient(base_url=os.getenv("RENDERER_BASE_URL")) as rc:
    req = RendererScreenshotRequest(url="https://example.com", full_page=True, full_page_strategy="scroll")
    data = await rc.screenshot(**req.model_dump())
```


