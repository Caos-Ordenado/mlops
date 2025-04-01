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
        example=["https://example.com", "https://example.org"]
    )
    max_pages: Optional[int] = Field(
        default=10000,
        gt=0,
        description="Maximum number of pages to crawl",
        example=100
    )
    max_depth: Optional[int] = Field(
        default=20,
        gt=0,
        description="Maximum depth to crawl",
        example=3
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None,
        description="List of allowed domains to crawl",
        example=["example.com", "example.org"]
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="List of URL patterns to exclude",
        example=["/login", "/admin"]
    )
    respect_robots: Optional[bool] = Field(
        default=False,
        description="Whether to respect robots.txt rules",
        example=True
    )
    timeout: Optional[int] = Field(
        default=180000,
        gt=0,
        description="Timeout in milliseconds for each request",
        example=180000
    )
    max_total_time: Optional[int] = Field(
        default=300,
        gt=0,
        description="Maximum total time in seconds for the crawl",
        example=300
    )
    max_concurrent_pages: Optional[int] = Field(
        default=10,
        gt=0,
        description="Maximum number of concurrent pages to crawl",
        example=5
    )
class CrawlResult(BaseModel):
    """Model for individual crawl results."""
    url: str
    title: Optional[str]
    text: str
    links: List[str]
    metadata: dict

class CrawlResponse(BaseModel):
    """Response model for crawl endpoint."""
    results: List[CrawlResult]
    total_urls: int
    crawled_urls: int
    elapsed_time: float

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