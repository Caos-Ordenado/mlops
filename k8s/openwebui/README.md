# Open WebUI (Kubernetes)

This directory deploys **Open WebUI** into the `default` namespace and exposes it via Traefik.

## Access (recommended: host-based)

Open WebUI uses several **root-level** paths (e.g. `/api`, `/ws`, `/_app`, `/assets`) and is not reliably subpath-friendly.
The recommended approach is **host-based routing**:

- Private (Tailscale/VPN): `http://webui.home.server:30080/`
  - Add `100.80.25.51 webui.home.server` to your `/etc/hosts` (or your local DNS)
- Public (Cloudflare tunnel): `https://chat.reyops.com/`

## Backwards compatibility (temporary)

- `https://www.reyops.com/webui` is still routed to Open WebUI, but host-based routing is preferred.

## 1) PostgreSQL provisioning (one-time)

Open WebUI must use PostgreSQL (no SQLite persistence).

Connect as Postgres admin and run:

```sql
CREATE USER openwebui_user WITH PASSWORD '<generated-password>';
CREATE DATABASE openwebui OWNER openwebui_user;
GRANT ALL PRIVILEGES ON DATABASE openwebui TO openwebui_user;
```

### Suggested `DATABASE_URL`

Use the in-cluster Postgres service DNS:

`postgresql://openwebui_user:<password>@postgres.shared.svc.cluster.local:5432/openwebui`

## 2) Secrets (required)

Generate and apply `openwebui-secrets` using the repo secret generator:

1. Run `k8s/secrets/scripts/generate-secrets.sh`
2. Select the `openwebui.template.yaml` template
3. Provide values for:
   - `__OPENWEBUI_DATABASE_URL__` (see above)
   - `__OLLAMA_BASE_URL__` (recommended: `http://ollama.default.svc.cluster.local:11434`)
   - `WEBUI_SECRET_KEY` is generated automatically via `__SERVER_SECRET_KEY__`

## 3) Deploy

Apply manifests:

```bash
kubectl apply -k k8s/openwebui
```

## 4) Verify

- Check the UI (private): `http://webui.home.server:30080/`
- Confirm it persists to Postgres (restart the pod and ensure state remains).

## 5) `/webui` subpath verification (optional / legacy)

Because Open WebUI is served behind a Traefik `PathPrefix(/webui)` + `stripPrefix`, validate:

- Static assets load correctly under `/webui` (no broken `/_next/...` or similar paths)
- Redirects keep the `/webui` prefix
- Any streaming endpoints (SSE / websocket) work if used by your WebUI version

This deployment also sets `X-Forwarded-Prefix: /webui` via Traefik middleware to improve subpath compatibility.

### Contingency (only if subpath support is incomplete)

If Open WebUI can’t reliably run under `/webui` even with forwarded prefix headers:

- Configure an explicit base-path/root-path env var **if Open WebUI supports it**, or
- Move to a dedicated host (e.g. `chat.reyops.com`) while keeping the local `/webui` route as an alternative.


