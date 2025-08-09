from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl
import os


class RendererScreenshotRequest(BaseModel):
    url: HttpUrl
    wait_for_selector: str = Field(default="body")
    timeout_ms: int = Field(default=30000, gt=0)
    viewport_width: int = Field(default=int(os.getenv("RENDERER_VIEWPORT_WIDTH", "1280")))
    viewport_height: int = Field(default=int(os.getenv("RENDERER_VIEWPORT_HEIGHT", "800")))
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = Field(
        default="domcontentloaded",
        description="waitUntil strategy for page.goto",
    )
    full_page: bool = Field(default=False, description="Capture full page screenshot")
    full_page_strategy: Literal["native", "scroll"] = Field(
        default="scroll",
        description="How to capture full page: native full_page or scroll to bottom then capture",
    )
    scroll_pause_ms: int = Field(default=400, ge=0, description="Pause between scroll steps")
    max_scroll_steps: int = Field(default=30, ge=1, description="Max number of scroll steps when using scroll strategy")
    wait_network_idle_ms: int = Field(default=1500, ge=0, description="Optional short network idle wait during scroll")
    hide_selectors: List[str] = Field(default_factory=list, description="CSS selectors to hide (display:none) before capture")
    detect_fixed: bool = Field(default=True, description="Auto-detect sticky/fixed header/footer heights for cropping")
    header_crop_px: int = Field(default=0, ge=0, description="Additional pixels to crop from top of each tile")
    footer_crop_px: int = Field(default=0, ge=0, description="Additional pixels to crop from bottom of each tile")
    stable_ticks: int = Field(default=3, ge=1, description="Stop scrolling when scrollHeight is stable for N ticks")


class RendererScreenshotResponse(BaseModel):
    url: str
    screenshot_b64: str
    content_type: str = "image/jpeg"
    saved_path: Optional[str] = None


class RendererRenderHtmlResponse(BaseModel):
    url: str
    html: str
    text: str


