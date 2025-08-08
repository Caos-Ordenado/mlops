"""
Pydantic models for the web crawler API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from urllib.parse import urlparse


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


class SingleCrawlRequest(BaseModel):
    """Request model for single URL crawl endpoint."""
    url: str = Field(
        ...,
        description="URL to crawl",
        example="https://example.com"
    )
    respect_robots: Optional[bool] = Field(
        default=False,
        description="Whether to respect robots.txt rules",
        example=True
    )
    timeout: Optional[int] = Field(
        default=180000,
        gt=0,
        description="Timeout in milliseconds for the request",
        example=180000
    )
    extract_links: Optional[bool] = Field(
        default=True,
        description="Whether to extract links from the page",
        example=True
    )
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="Whether to bypass cache and force fresh crawl",
        example=False
    )

    @validator('url')
    def validate_url(cls, v):
        """Validate URL format."""
        try:
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError('Invalid URL format: URL must include scheme and netloc')
            if result.scheme not in ['http', 'https']:
                raise ValueError('Invalid URL scheme: Only http and https are supported')
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            raise ValueError(f'Invalid URL format: {str(e)}')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "respect_robots": False,
                "timeout": 30000,
                "extract_links": True,
                "bypass_cache": False
            }
        }


class CrawlResult(BaseModel):
    """Model for individual crawl results."""
    url: str
    title: Optional[str]
    text: str
    links: List[str]
    metadata: dict


class CrawlResponse(BaseModel):
    """Response model for crawl endpoint."""
    success: bool
    results: List[CrawlResult]
    total_urls: int
    crawled_urls: int
    elapsed_time: float


class SingleCrawlResponse(BaseModel):
    """Response model for single URL crawl endpoint."""
    success: bool = Field(
        ...,
        description="Whether the crawl was successful",
        example=True
    )
    result: Optional[CrawlResult] = Field(
        default=None,
        description="Crawl result for the single URL"
    )
    elapsed_time: float = Field(
        ...,
        description="Time taken to complete the request in seconds",
        example=1.5
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the crawl failed",
        example="Timeout while crawling URL"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "result": {
                    "url": "https://example.com",
                    "title": "Example Domain",
                    "text": "This domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.",
                    "links": ["https://www.iana.org/domains/example"],
                    "metadata": {
                        "status_code": 200,
                        "content_type": "text/html; charset=UTF-8",
                        "meta_tags": [
                            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
                            {"name": "description", "content": "Example Domain"}
                        ],
                        "headers_hierarchy": {
                            "h1": ["Example Domain"], 
                            "h2": [], 
                            "h3": []
                        },
                        "images": [],
                        "structured_data": [],
                        "main_content": "This domain is for use in illustrative examples in documents."
                    }
                },
                "elapsed_time": 1.5,
                "error": None
            }
        }


class VisionExtractRequest(BaseModel):
    """Request model for vision-based extraction using Playwright + Ollama."""
    url: str = Field(..., description="URL to navigate and capture screenshot from")
    fields: Optional[List[str]] = Field(
        default_factory=lambda: ["name", "price", "currency", "availability"],
        description="Fields to extract as JSON keys"
    )
    timeout: Optional[int] = Field(
        default=60000,
        gt=0,
        description="Timeout in milliseconds for page navigation"
    )
    bypass_cache: Optional[bool] = Field(
        default=True,
        description="Bypass any internal caches (reserved for future use)"
    )

    @validator('url')
    def validate_url(cls, v):
        try:
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError('Invalid URL format: URL must include scheme and netloc')
            if result.scheme not in ['http', 'https']:
                raise ValueError('Invalid URL scheme: Only http and https are supported')
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            raise ValueError(f'Invalid URL format: {str(e)}')
        return v


class VisionExtractResponse(BaseModel):
    """Response model for vision-based extraction endpoint."""
    success: bool = Field(..., description="Whether extraction succeeded")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted JSON data")
    elapsed_time: float = Field(..., description="Time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")

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