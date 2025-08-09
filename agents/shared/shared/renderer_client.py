import aiohttp
from typing import Any, Dict, Optional
from .logging import setup_logger
from .interfaces.renderer import (
    RendererScreenshotRequest,
    RendererScreenshotResponse,
    RendererRenderHtmlResponse,
)

logger = setup_logger("shared.renderer_client")


class RendererClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def screenshot(self, **kwargs) -> Dict[str, Any]:
        if not self.session:
            self.session = aiohttp.ClientSession()
        endpoint = f"{self.base_url}/screenshot"
        payload = RendererScreenshotRequest(**kwargs).model_dump(mode="json")
        logger.debug(f"RendererClient screenshot -> {endpoint}")
        async with self.session.post(endpoint, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Renderer screenshot failed: {resp.status} {text}")
                resp.raise_for_status()
            data = await resp.json()
            return RendererScreenshotResponse(**data).model_dump()

    async def render_html(self, **kwargs) -> Dict[str, Any]:
        if not self.session:
            self.session = aiohttp.ClientSession()
        endpoint = f"{self.base_url}/render-html"
        payload = RendererScreenshotRequest(**kwargs).model_dump(mode="json")
        logger.debug(f"RendererClient render_html -> {endpoint}")
        async with self.session.post(endpoint, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Renderer render_html failed: {resp.status} {text}")
                resp.raise_for_status()
            data = await resp.json()
            return RendererRenderHtmlResponse(**data).model_dump()



