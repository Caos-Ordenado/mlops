"""
Pydantic models for the web crawler API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CrawlRequest(BaseModel):
    """Request model for crawling URLs."""
    urls: List[str] = Field(
        ...,
        description="List of URLs to crawl",
        example=["https://ai.pydantic.dev/api/", "https://ai.pydantic.dev/examples/"]
    )
    max_pages: Optional[int] = Field(
        default=10000,
        description="Maximum number of pages to crawl (from CRAWLER_MAX_PAGES)",
        gt=0,
        example=10
    )
    max_depth: Optional[int] = Field(
        default=20,
        description="Maximum crawl depth (from CRAWLER_MAX_DEPTH)",
        gt=0,
        example=2
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None,
        description="List of allowed domains to crawl. If None, any domain is allowed",
        example=["ai.pydantic.dev"]
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="List of URL patterns to exclude from crawling",
        example=["*.pdf", "/static/*"]
    )
    respect_robots: Optional[bool] = Field(
        default=False,
        description="Whether to respect robots.txt (from CRAWLER_RESPECT_ROBOTS)",
        example=True
    )
    timeout: Optional[int] = Field(
        default=180000,
        description="Request timeout in milliseconds (from CRAWLER_TIMEOUT)",
        gt=0,
        example=30000
    )
    max_total_time: Optional[int] = Field(
        default=300,
        description="Maximum total crawling time in seconds (from CRAWLER_MAX_TOTAL_TIME)",
        gt=0,
        example=60
    )
    max_concurrent_pages: Optional[int] = Field(
        default=10,
        description="Maximum number of pages to crawl concurrently (from CRAWLER_MAX_CONCURRENT_PAGES)",
        gt=0,
        example=5
    )
    memory_threshold: Optional[float] = Field(
        default=80.0,
        description="Memory usage threshold percentage to pause crawling (from CRAWLER_MEMORY_THRESHOLD)",
        gt=0.0,
        lt=100.0,
        example=80.0
    )
    user_agent: Optional[str] = Field(
        default="Mozilla/5.0 (compatible; WebCrawlerAgent/1.0)",
        description="Custom User-Agent string for requests",
        example="Mozilla/5.0 (compatible; WebCrawlerAgent/1.0)"
    )
    headless: Optional[bool] = Field(
        default=True,
        description="Whether to run browser in headless mode (from CRAWLER_HEADLESS)",
        example=True
    )
    viewport_width: Optional[int] = Field(
        default=1920,
        description="Browser viewport width (from CRAWLER_VIEWPORT_WIDTH)",
        gt=0,
        example=1920
    )
    viewport_height: Optional[int] = Field(
        default=1080,
        description="Browser viewport height (from CRAWLER_VIEWPORT_HEIGHT)",
        gt=0,
        example=1080
    )

    class Config:
        json_schema_extra = {
            "example": {
                "urls": ["https://ai.pydantic.dev/api/"],
                "max_pages": 10,
                "max_depth": 2,
                "respect_robots": True,
                "timeout": 30000,
                "max_concurrent_pages": 5,
                "memory_threshold": 80.0
            }
        }

class CrawlResult(BaseModel):
    """Model for individual crawl results."""
    url: str = Field(..., description="The URL that was crawled")
    success: bool = Field(..., description="Whether the crawl was successful")
    data: Dict[str, Any] = Field(
        ..., 
        description="""The crawled data including:
        - html: Raw HTML content
        - text: Extracted text content
        - links: List of discovered URLs
        - title: Page title
        - metadata: Additional metadata"""
    )

class CrawlResponse(BaseModel):
    """Response model for the crawl endpoint."""
    status: str = Field(
        ..., 
        description="Status of the crawl operation",
        example="success"
    )
    results: List[CrawlResult] = Field(
        ..., 
        description="List of crawl results for each URL"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "results": [{
                    "url": "https://ai.pydantic.dev/api/",
                    "success": True,
                    "data": {
                        "html": "<!DOCTYPE html>...",
                        "text": "Welcome to Pydantic AI...",
                        "links": ["https://ai.pydantic.dev/examples/"],
                        "title": "Pydantic AI Documentation",
                        "metadata": {
                            "description": "AI-powered data validation",
                            "author": "Pydantic team"
                        }
                    }
                }]
            }
        } 