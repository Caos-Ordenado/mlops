"""
Configuration management for the web crawler.
"""

import os
from typing import Dict, Any
from pydantic import BaseModel

class CrawlerConfig(BaseModel):
    """Configuration model for the web crawler."""
    # Crawler settings
    debug: bool = False
    max_pages: int = 10000
    max_depth: int = 20
    respect_robots: bool = False
    timeout: int = 180000
    max_total_time: int = 300
    max_concurrent_pages: int = 10
    memory_threshold: float = 80.0
    
    # Storage settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "web_crawler"
    postgres_user: str = "postgres"
    postgres_password: str = None
    
    # Browser settings
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = "Mozilla/5.0 (compatible; WebCrawlerAgent/1.0)"

def load_config() -> CrawlerConfig:
    """Load configuration from environment variables."""
    config_dict: Dict[str, Any] = {
        # Crawler settings
        "debug": os.getenv("CRAWLER_DEBUG", "false").lower() == "true",
        "max_pages": int(os.getenv("CRAWLER_MAX_PAGES", "10000")),
        "max_depth": int(os.getenv("CRAWLER_MAX_DEPTH", "20")),
        "respect_robots": os.getenv("CRAWLER_RESPECT_ROBOTS", "false").lower() == "true",
        "timeout": int(os.getenv("CRAWLER_TIMEOUT", "180000")),
        "max_total_time": int(os.getenv("CRAWLER_MAX_TOTAL_TIME", "300")),
        "max_concurrent_pages": int(os.getenv("CRAWLER_MAX_CONCURRENT_PAGES", "10")),
        "memory_threshold": float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0")),
        
        # Storage settings
        "redis_host": os.getenv("CRAWLER_REDIS_HOST", "localhost"),
        "redis_port": int(os.getenv("CRAWLER_REDIS_PORT", "6379")),
        "redis_db": int(os.getenv("CRAWLER_REDIS_DB", "0")),
        "postgres_host": os.getenv("CRAWLER_POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.getenv("CRAWLER_POSTGRES_PORT", "5432")),
        "postgres_db": os.getenv("CRAWLER_POSTGRES_DB", "web_crawler"),
        "postgres_user": os.getenv("CRAWLER_POSTGRES_USER", "postgres"),
        "postgres_password": os.getenv("CRAWLER_POSTGRES_PASSWORD"),
        
        # Browser settings
        "headless": os.getenv("CRAWLER_HEADLESS", "true").lower() == "true",
        "viewport_width": int(os.getenv("CRAWLER_VIEWPORT_WIDTH", "1920")),
        "viewport_height": int(os.getenv("CRAWLER_VIEWPORT_HEIGHT", "1080")),
        "user_agent": os.getenv(
            "CRAWLER_USER_AGENT",
            "Mozilla/5.0 (compatible; WebCrawlerAgent/1.0)"
        )
    }
    
    return CrawlerConfig(**config_dict) 