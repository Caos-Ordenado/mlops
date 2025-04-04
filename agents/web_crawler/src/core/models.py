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
    user_agent: str = "Mozilla/5.0 (compatible; WebCrawlerAgent/1.0)"
    storage_redis: bool = Field(default=False)
    storage_postgres: bool = Field(default=False)
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