"""
Shared models for the web crawler.
"""

from typing import List, Optional, Set
from pydantic import BaseModel, Field
import os

class CrawlerSettings(BaseModel):
    """Settings for the web crawler."""
    max_pages: int = Field(default=10000, gt=0)
    max_depth: int = Field(default=20, gt=0)
    allowed_domains: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    respect_robots: bool = False
    timeout: int = Field(default=180000, gt=0)  # milliseconds
    max_total_time: int = Field(default=300, gt=0)  # seconds
    max_concurrent_pages: int = Field(default=10, gt=0)
    memory_threshold: float = Field(default=80.0, gt=0.0, lt=100.0)
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    debug: bool = Field(default=False)
    processed_urls: Set[str] = Field(default_factory=set)
    processed_sitemaps: Set[str] = Field(default_factory=set)

    model_config = {
        "arbitrary_types_allowed": True
    }

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize empty sets if not provided
        if 'processed_urls' not in data:
            self.processed_urls = set()
        if 'processed_sitemaps' not in data:
            self.processed_sitemaps = set()
        # Set debug from environment if not provided
        if 'debug' not in data:
            self.debug = os.getenv("CRAWLER_DEBUG", "false").lower() == "true"
    
    def _get_browser_headers(self) -> dict:
        """Get comprehensive browser-like headers to avoid bot detection."""
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        } 