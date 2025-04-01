"""
Shared models for the web crawler.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

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
    storage_redis: bool = False
    storage_postgres: bool = False
    debug: bool = False 