from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List
from pydantic import HttpUrl
import asyncio
import json
import re
import time
import random
from urllib.parse import urlparse
from PIL import Image
import io
import os
import base64

from shared.interfaces.renderer import RendererScreenshotRequest
from shared import setup_logger

logger = setup_logger("renderer.routes")

try:
    from playwright.async_api import async_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover
    PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import stealth_async as _stealth_async  # type: ignore

    STEALTH_AVAILABLE = True
except Exception:  # pragma: no cover
    STEALTH_AVAILABLE = False
    _stealth_async = None


router = APIRouter()

USER_AGENTS: list[str] = [
    # Chrome (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari (macOS) - note: renderer uses Chromium, but a Safari UA can still help on some simplistic blocks
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Chrome (Linux)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

DEFAULT_LOCALE = "es-UY"
DEFAULT_TIMEZONE_ID = "America/Montevideo"
DEFAULT_EXTRA_HTTP_HEADERS = {
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}


def _clamp_int(v: int, min_v: int, max_v: Optional[int] = None) -> int:
    try:
        vi = int(v)
    except Exception:
        vi = min_v
    vi = max(min_v, vi)
    if max_v is not None:
        vi = min(max_v, vi)
    return vi


def _compute_viewport(req: RendererScreenshotRequest) -> dict:
    width = _clamp_int(req.viewport_width, 320)
    height = _clamp_int(req.viewport_height, 480)
    randomized = False
    if getattr(req, "viewport_randomize", False):
        width = _clamp_int(width + random.randint(-20, 20), 320)
        height = _clamp_int(height + random.randint(-20, 20), 480)
        randomized = True
    return {"width": width, "height": height, "_randomized": randomized}


def _pick_user_agent() -> str:
    try:
        return random.choice(USER_AGENTS)
    except Exception:
        return USER_AGENTS[0]


async def _apply_stealth_if_available(page) -> bool:
    if not STEALTH_AVAILABLE or _stealth_async is None:
        return False
    try:
        await _stealth_async(page)
        return True
    except Exception as e:
        logger.debug(f"stealth: failed err={e}")
        return False


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)[:80]


def _now_iso() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


async def _race_waits(page, selector: str, timeout_ms: int) -> None:
    try:
        await page.wait_for_selector(selector, timeout=max(500, min(timeout_ms, 5000)))
    except Exception:
        return


async def _close_context_safely(context) -> None:
    t0 = time.perf_counter()
    try:
        await context.close()
        logger.debug(f"render-html:context closed ms={(time.perf_counter()-t0)*1000:.1f}")
    except Exception as e:
        logger.debug(f"render-html:context close error={e}")


@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "playwright": PLAYWRIGHT_AVAILABLE,
        "browser_ready": bool(getattr(request.app.state, "browser", None)),
    }


@router.post("/screenshot")
async def screenshot(req: RendererScreenshotRequest, request: Request):
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Playwright not available in this container")
    if not getattr(request.app.state, "browser", None):
        raise HTTPException(status_code=503, detail="Browser not initialized")

    started = time.time()
    context = None
    try:
        browser = request.app.state.browser
        user_agent = _pick_user_agent()
        viewport = _compute_viewport(req)
        viewport_payload = {"width": viewport["width"], "height": viewport["height"]}
        logger.debug(
            f"screenshot:start url={req.url} ua='{user_agent}' locale={DEFAULT_LOCALE} tz={DEFAULT_TIMEZONE_ID} "
            f"vw={viewport_payload['width']} vh={viewport_payload['height']} viewport_randomize={bool(viewport.get('_randomized'))}"
        )
        context = await browser.new_context(
            user_agent=user_agent,
            locale=DEFAULT_LOCALE,
            timezone_id=DEFAULT_TIMEZONE_ID,
            extra_http_headers=DEFAULT_EXTRA_HTTP_HEADERS,
            viewport=viewport_payload,
        )
        page = await context.new_page()
        stealth_ok = await _apply_stealth_if_available(page)
        logger.debug(f"screenshot:stealth applied={stealth_ok}")

        async def _route_handler(route, _request):
            url = _request.url.lower()
            if _request.resource_type == "font" or any(url.endswith(ext) for ext in (".woff", ".woff2", ".ttf", ".otf")):
                return await route.abort()
            return await route.continue_()

        try:
            await context.route("**/*", _route_handler)
        except Exception:
            pass

        try:
            page.set_default_navigation_timeout(req.timeout_ms)
            page.set_default_timeout(req.timeout_ms)
        except Exception:
            pass

        if req.hide_selectors:
            try:
                await page.add_init_script(
                    "(sels) => { try { sels.forEach(s => { document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll(s).forEach(el=>el.style.display='none');}); }); } catch(e){} }",
                    req.hide_selectors,
                )
            except Exception:
                pass

        try:
            await page.goto(str(req.url), wait_until=req.wait_until, timeout=max(1000, min(req.timeout_ms, 5000)))
        except Exception:
            pass
        await _race_waits(page, req.wait_for_selector, req.timeout_ms)

        stitched_img: Optional[bytes] = None
        if req.full_page and req.full_page_strategy == "scroll":
            try:
                await page.evaluate("window.scrollTo(0, 0)")
                tiles: list[Image.Image] = []
                stable_count = 0
                last_scroll_height = await page.evaluate("() => document.body.scrollHeight")
                for _ in range(req.max_scroll_steps):
                    tile_bytes = await page.screenshot(full_page=False, type="png", timeout=max(2000, req.wait_network_idle_ms))
                    try:
                        tiles.append(Image.open(io.BytesIO(tile_bytes)).convert("RGB"))
                    except Exception:
                        break
                    at_bottom = await page.evaluate("() => (window.innerHeight + window.scrollY) >= document.body.scrollHeight")
                    if at_bottom:
                        break
                    await page.evaluate("() => window.scrollBy(0, window.innerHeight)")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=req.wait_network_idle_ms)
                    except Exception:
                        pass
                    await asyncio.sleep(req.scroll_pause_ms / 1000)
                    try:
                        current_h = await page.evaluate("() => document.body.scrollHeight")
                        if current_h == last_scroll_height:
                            stable_count += 1
                        else:
                            stable_count = 0
                            last_scroll_height = current_h
                        if stable_count >= req.stable_ticks:
                            break
                    except Exception:
                        pass
                if tiles:
                    width = max(t.width for t in tiles)
                    header_crop = req.header_crop_px
                    footer_crop = req.footer_crop_px
                    if req.detect_fixed:
                        try:
                            fixed_top = await page.evaluate("() => Array.from(document.querySelectorAll('*')).filter(e=>getComputedStyle(e).position==='fixed'&& e.getBoundingClientRect().top<=0).reduce((m,e)=>Math.max(m,e.getBoundingClientRect().height),0)")
                            fixed_bottom = await page.evaluate("() => Array.from(document.querySelectorAll('*')).filter(e=>getComputedStyle(e).position==='fixed'&& (window.innerHeight - e.getBoundingClientRect().bottom)<=0).reduce((m,e)=>Math.max(m,e.getBoundingClientRect().height),0)")
                            header_crop = max(header_crop, int(fixed_top) if fixed_top else 0)
                            footer_crop = max(footer_crop, int(fixed_bottom) if fixed_bottom else 0)
                        except Exception:
                            pass
                    cropped_tiles: List[Image.Image] = []
                    for t in tiles:
                        top = max(0, header_crop)
                        bottom = max(0, footer_crop)
                        h = t.height
                        box = (0, top, width, max(top, h - bottom))
                        try:
                            cropped_tiles.append(t.crop(box))
                        except Exception:
                            cropped_tiles.append(t)
                    total_height = sum(t.height for t in cropped_tiles)
                    canvas = Image.new("RGB", (width, total_height))
                    y = 0
                    for t in cropped_tiles:
                        canvas.paste(t, (0, y))
                        y += t.height
                    buf2 = io.BytesIO()
                    canvas.save(buf2, format="JPEG", quality=70, optimize=True)
                    stitched_img = buf2.getvalue()
            except Exception:
                stitched_img = None

        try:
            _ = await page.screenshot(full_page=False, type="jpeg", quality=40, timeout=2000)
        except Exception:
            pass

        if stitched_img is not None:
            img_bytes = stitched_img
        else:
            try:
                img_bytes = await page.screenshot(
                    full_page=req.full_page,
                    type="png",
                    timeout=req.timeout_ms,
                    animations="disabled",
                )
            except TypeError:
                img_bytes = await page.screenshot(full_page=req.full_page, type="png", timeout=req.timeout_ms)

        try:
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=70, optimize=True)
            img = buf.getvalue()
        except Exception:
            img = img_bytes
        await context.close()

        base_dir = os.getenv("RENDERER_SNAPSHOT_DIR", "/tmp/renderer-snapshots")
        os.makedirs(base_dir, exist_ok=True)
        host = _slugify(urlparse(str(req.url)).netloc or "page")
        ts = _now_iso()
        fname = f"{host}_{ts}.jpg"
        fpath = os.path.join(base_dir, fname)
        with open(fpath, "wb") as f:
            f.write(img)
        meta = {
            "url": str(req.url),
            "created_at": ts,
            "wait_until": req.wait_until,
            "viewport": viewport_payload,
            "viewport_randomize": bool(viewport.get("_randomized")),
            "locale": DEFAULT_LOCALE,
            "timezone_id": DEFAULT_TIMEZONE_ID,
            "user_agent": user_agent,
            "stealth_applied": stealth_ok,
            "full_page": req.full_page,
        }
        with open(fpath + ".json", "w") as mf:
            json.dump(meta, mf)

        return {
            "url": str(req.url),
            "screenshot_b64": base64.b64encode(img).decode("ascii"),
            "content_type": "image/jpeg",
            "saved_path": fpath,
        }
    except Exception as e:
        try:
            if context:
                await context.close()
        except Exception:
            pass
        elapsed_ms = int((time.time() - started) * 1000)
        msg = str(e)
        status = 504 if "Timeout" in msg else 500
        logger.error(f"screenshot error: {e}")
        raise HTTPException(
            status_code=status,
            detail={
                "success": False,
                "error_stage": "screenshot",
                "error_message": msg,
                "url": str(req.url),
                "elapsed_ms": elapsed_ms,
            },
        )


@router.post("/render-html")
async def render_html(req: RendererScreenshotRequest, request: Request):
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Playwright not available in this container")
    if not getattr(request.app.state, "browser", None):
        raise HTTPException(status_code=503, detail="Browser not initialized")
    started = time.perf_counter()
    context = None
    try:
        user_agent = _pick_user_agent()
        viewport = _compute_viewport(req)
        viewport_payload = {"width": viewport["width"], "height": viewport["height"]}
        logger.debug(
            f"render-html:start url={req.url} ua='{user_agent}' locale={DEFAULT_LOCALE} tz={DEFAULT_TIMEZONE_ID} "
            f"vw={viewport_payload['width']} vh={viewport_payload['height']} viewport_randomize={bool(viewport.get('_randomized'))} "
            f"timeout_ms={req.timeout_ms} wait_until={req.wait_until}"
        )
        browser = request.app.state.browser
        t0 = time.perf_counter()
        context = await browser.new_context(
            user_agent=user_agent,
            locale=DEFAULT_LOCALE,
            timezone_id=DEFAULT_TIMEZONE_ID,
            extra_http_headers=DEFAULT_EXTRA_HTTP_HEADERS,
            viewport=viewport_payload,
        )
        logger.debug(f"render-html:ctx new_context ms={(time.perf_counter()-t0)*1000:.1f}")
        page = await context.new_page()
        stealth_ok = await _apply_stealth_if_available(page)
        logger.debug(f"render-html:stealth applied={stealth_ok}")
        try:
            page.set_default_navigation_timeout(req.timeout_ms)
            page.set_default_timeout(req.timeout_ms)
        except Exception:
            pass

        # Prefer realism: abort only fonts (font loads can stall); keep images/scripts/styles.
        abort_counts = {"font": 0}
        async def _route_handler(route, _request):
            url = _request.url.lower()
            if _request.resource_type == "font" or any(url.endswith(ext) for ext in (".woff", ".woff2", ".ttf", ".otf")):
                abort_counts["font"] += 1
                return await route.abort()
            return await route.continue_()
        try:
            await context.route("**/*", _route_handler)
        except Exception:
            pass

        # Fast navigation strategy: go to DOMContentLoaded quickly; avoid long networkidle waits
        # Hard deadline: never exceed timeout_ms overall
        deadline = started + (req.timeout_ms / 1000.0)
        def remaining_ms(min_ms: int = 200, cap_ms: Optional[int] = None) -> int:
            rem = int((deadline - time.perf_counter()) * 1000)
            if cap_ms is not None:
                rem = min(rem, cap_ms)
            return max(min_ms, rem)

        t_nav = time.perf_counter()
        try:
            await page.goto(str(req.url), wait_until="domcontentloaded", timeout=remaining_ms(cap_ms=2000))
            logger.debug(f"render-html:goto domcontentloaded ms={(time.perf_counter()-t_nav)*1000:.1f}")
        except Exception as e:
            logger.debug(f"render-html:goto domcontentloaded error={e}")
            # Fall back to a quick 'load' state navigation to avoid long stalls
            try:
                t_nav2 = time.perf_counter()
                await page.goto(str(req.url), wait_until="load", timeout=remaining_ms(cap_ms=1500))
                logger.debug(f"render-html:goto load fallback ms={(time.perf_counter()-t_nav2)*1000:.1f}")
            except Exception as e2:
                logger.debug(f"render-html:goto load fallback error={e2}")

        # Attempt to stabilize page state before reading content
        t_wait = time.perf_counter()
        await _race_waits(page, req.wait_for_selector, remaining_ms(cap_ms=2000))
        logger.debug(f"render-html:wait_for_selector '{req.wait_for_selector}' ms={(time.perf_counter()-t_wait)*1000:.1f}")
        # Brief DOM settle only; skip networkidle to avoid slow pages
        try:
            t_dom = time.perf_counter()
            await page.wait_for_load_state("domcontentloaded", timeout=remaining_ms(cap_ms=1500))
            logger.debug(f"render-html:load_state domcontentloaded ms={(time.perf_counter()-t_dom)*1000:.1f}")
        except Exception as e:
            logger.debug(f"render-html:load_state domcontentloaded error={e}")

        # Retry reading content if the page is still navigating
        html = None
        text = None
        last_err = None
        for i in range(2):
            t_read = time.perf_counter()
            try:
                # outerHTML can be marginally faster than page.content on some pages
                html = await page.evaluate("document.documentElement ? document.documentElement.outerHTML : ''")
                text = await page.evaluate("document.body ? document.body.innerText : ''")
                logger.debug(f"render-html:read_content attempt={i+1} ms={(time.perf_counter()-t_read)*1000:.1f}")
                break
            except Exception as e:
                last_err = e
                # Sleep but respect overall deadline
                sleep_ms = min(150, remaining_ms())
                await asyncio.sleep(sleep_ms / 1000.0)

        if html is None:
            raise last_err or Exception("Failed to retrieve page content")

        total_ms = (time.perf_counter()-started)*1000
        logger.debug(
            f"render-html: ok url={req.url} total_ms={total_ms:.1f} aborted_fonts={abort_counts['font']} "
            f"stealth_applied={stealth_ok}"
        )
        await _close_context_safely(context)
        return {"url": str(req.url), "html": html, "text": text}
    except Exception as e:
        try:
            if context:
                await _close_context_safely(context)
        except Exception:
            pass
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        msg = str(e)
        status = 504 if "Timeout" in msg else 500
        logger.error(f"render-html error: {e}")
        raise HTTPException(
            status_code=status,
            detail={
                "success": False,
                "error_stage": "render-html",
                "error_message": msg,
                "url": str(req.url),
                "elapsed_ms": elapsed_ms,
            },
        )


