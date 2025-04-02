"""
A simple client to interact with the web crawler API from your Mac.
"""

import os
import json
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from urllib.parse import urljoin

# Set up logger
logger = logging.getLogger(__name__)

@dataclass
class CrawlRequest:
    """Request for crawling web pages."""
    urls: List[str]
    max_pages: int = 10000
    max_depth: int = 20
    allowed_domains: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    respect_robots: bool = False
    timeout: int = 180000
    max_total_time: int = 300
    max_concurrent_pages: int = 10

@dataclass
class CrawlResult:
    """Result from crawling a web page."""
    url: str
    title: Optional[str]
    text: str
    links: List[str]
    metadata: Dict[str, Any]

@dataclass
class CrawlResponse:
    """Response from the web crawler service."""
    results: List[CrawlResult]
    total_urls: int
    crawled_urls: int
    elapsed_time: float
    error: Optional[str] = None

class WebCrawlerClient:
    """Client for interacting with the web crawler API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the web crawler client.
        
        Args:
            base_url: Base URL of the web crawler API. Defaults to environment variable.
        """
        self.base_url = (base_url or os.getenv("CRAWLER_URL", "http://home.server/crawler")).rstrip('/')
        logger.debug(f"Initialized WebCrawlerClient with base_url: {self.base_url}")
        self.session = None
    
    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        logger.debug("Created aiohttp session")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
            logger.debug("Closed aiohttp session")
    
    async def health_check(self) -> bool:
        """Check if the web crawler service is healthy.
        
        Returns:
            bool: True if healthy, False otherwise.
        """
        url = f"{self.base_url}/health"
        logger.debug(f"Sending health check request to: {url}")
        
        try:
            async with self.session.get(url, timeout=20) as response:
                logger.debug(f"Health check response status: {response.status}")
                if response.status != 200:
                    logger.error(f"Health check failed with status {response.status}")
                    return False
                    
                data = await response.json()
                logger.debug(f"Health check response data: {data}")
                return data.get("status") == "ok"
                
        except Exception as e:
            logger.error(f"Health check failed with error: {str(e)}")
            return False
    
    async def crawl(
        self,
        urls: List[str],
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
        allowed_domains: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        respect_robots: Optional[bool] = None,
        timeout: Optional[int] = None,
        max_total_time: Optional[int] = None,
        max_concurrent_pages: Optional[int] = None
    ) -> CrawlResponse:
        """Crawl web pages starting from the given URLs.
        
        Args:
            urls: List of URLs to start crawling from
            max_pages: Maximum number of pages to crawl
            max_depth: Maximum depth to crawl
            allowed_domains: List of allowed domains to crawl
            exclude_patterns: List of URL patterns to exclude
            respect_robots: Whether to respect robots.txt rules
            timeout: Timeout in milliseconds for each request
            max_total_time: Maximum total time in seconds for the crawl
            max_concurrent_pages: Maximum number of concurrent pages to crawl
            
        Returns:
            CrawlResponse: The crawl results
            
        Raises:
            Exception: If the crawl request fails
        """
        request = CrawlRequest(
            urls=urls,
            max_pages=max_pages if max_pages is not None else 10000,
            max_depth=max_depth if max_depth is not None else 20,
            allowed_domains=allowed_domains,
            exclude_patterns=exclude_patterns,
            respect_robots=respect_robots if respect_robots is not None else False,
            timeout=timeout if timeout is not None else 180000,
            max_total_time=max_total_time if max_total_time is not None else 300,
            max_concurrent_pages=max_concurrent_pages if max_concurrent_pages is not None else 10
        )
        
        url = f"{self.base_url}/crawl"
        payload = asdict(request)
        logger.debug(f"Sending crawl request to: {url}")
        logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with self.session.post(
                url,
                json=payload,
                timeout=20
            ) as response:
                logger.debug(f"Crawl response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Crawl request failed with status {response.status}: {error_text}")
                    raise Exception(f"Crawl request failed: {error_text}")
                    
                data = await response.json()
                logger.debug(f"Crawl response data: {json.dumps(data, indent=2)}")
                
                # Convert results to CrawlResult objects
                results = []
                for result in data.get("results", []):
                    results.append(CrawlResult(
                        url=result["url"],
                        title=result.get("title"),
                        text=result["text"],
                        links=result["links"],
                        metadata=result.get("metadata", {})
                    ))
                    
                return CrawlResponse(
                    results=results,
                    total_urls=data["total_urls"],
                    crawled_urls=data["crawled_urls"],
                    elapsed_time=data["elapsed_time"],
                    error=data.get("error")
                )
                
        except Exception as e:
            logger.error(f"Crawl request failed with error: {str(e)}")
            raise Exception(f"Error during crawl request: {str(e)}")

if __name__ == "__main__":
    # Set up logging for the example
    logging.basicConfig(level=logging.DEBUG)
    
    async def example():
        """Example usage of the web crawler client."""
        async with WebCrawlerClient() as client:
            # Check if the crawler is healthy
            is_healthy = await client.health_check()
            print(f"Crawler health check: {'OK' if is_healthy else 'Failed'}")
            
            if is_healthy:
                # Example crawl
                try:
                    response = await client.crawl(
                        urls=["https://example.com"],
                        max_pages=5,
                        max_depth=2,
                        allowed_domains=["example.com"],
                        exclude_patterns=["*.pdf", "*.jpg"],
                        max_concurrent_pages=3
                    )
                    
                    print(f"\nCrawl Results:")
                    print(f"Total URLs: {response.total_urls}")
                    print(f"Crawled URLs: {response.crawled_urls}")
                    print(f"Elapsed Time: {response.elapsed_time:.2f} seconds")
                    
                    for result in response.results:
                        print(f"\nURL: {result.url}")
                        print(f"Title: {result.title}")
                        print(f"Links found: {len(result.links)}")
                        print(f"Content length: {len(result.text)}")
                    
                except Exception as e:
                    print(f"Crawl failed: {str(e)}")
    
    asyncio.run(example()) 