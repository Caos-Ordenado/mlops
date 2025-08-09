"""
A simple client to interact with the web crawler API from your Mac.
"""

import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from .logging import setup_logger
from .interfaces.web_crawler import (
    CrawlRequest,
    CrawlResult,
    CrawlResponse,
    SingleCrawlRequest,
    SingleCrawlResponse,
    VisionExtractRequest,
    VisionExtractResponse,
)

# Set up logger
logger = setup_logger(__name__)

from pydantic import BaseModel

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
        payload = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
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
                results: list[CrawlResult] = []
                for result in data.get("results", []):
                    results.append(CrawlResult(
                        url=result["url"],
                        title=result.get("title"),
                        text=result["text"],
                        links=result["links"],
                        metadata=result.get("metadata", {})
                    ))

                return CrawlResponse(
                    success=bool(data.get("success", True)),
                    results=results,
                    total_urls=int(data.get("total_urls", len(results))),
                    crawled_urls=int(data.get("crawled_urls", len(results))),
                    elapsed_time=float(data.get("elapsed_time", 0.0)),
                )
                
        except Exception as e:
            logger.error(f"Crawl request failed with error: {str(e)}")
            raise Exception(f"Error during crawl request: {str(e)}")
    
    async def crawl_single(
        self,
        url: str,
        respect_robots: Optional[bool] = None,
        timeout: Optional[int] = None,
        extract_links: Optional[bool] = None,
        bypass_cache: Optional[bool] = None
    ) -> SingleCrawlResponse:
        """Crawl a single URL for detailed content extraction.
        
        Args:
            url: URL to crawl
            respect_robots: Whether to respect robots.txt rules
            timeout: Timeout in milliseconds for the request
            extract_links: Whether to extract links from the page
            bypass_cache: Whether to bypass cache and force fresh crawl
            
        Returns:
            SingleCrawlResponse: The crawl result for the single URL
            
        Raises:
            Exception: If the crawl request fails
        """
        request = SingleCrawlRequest(
            url=url,
            respect_robots=respect_robots if respect_robots is not None else False,
            timeout=timeout if timeout is not None else 180000,
            extract_links=extract_links if extract_links is not None else True,
            bypass_cache=bypass_cache if bypass_cache is not None else False
        )
        
        crawl_url = f"{self.base_url}/crawl-single"
        payload = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
        logger.debug(f"Sending single crawl request to: {crawl_url}")
        logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with self.session.post(
                crawl_url,
                json=payload,
                timeout=20
            ) as response:
                logger.debug(f"Single crawl response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Single crawl request failed with status {response.status}: {error_text}")
                    raise Exception(f"Single crawl request failed: {error_text}")
                    
                data = await response.json()
                logger.debug(f"Single crawl response data: {json.dumps(data, indent=2)}")
                
                # Convert result to CrawlResult object if successful
                result = None
                if data.get("success") and data.get("result"):
                    result_data = data["result"]
                    result = CrawlResult(
                        url=result_data["url"],
                        title=result_data.get("title"),
                        text=result_data["text"],
                        links=result_data["links"],
                        metadata=result_data.get("metadata", {})
                    )
                    
                return SingleCrawlResponse(
                    success=data["success"],
                    result=result,
                    elapsed_time=data["elapsed_time"],
                    error=data.get("error")
                )
                
        except Exception as e:
            logger.error(f"Single crawl request failed with error: {str(e)}")
            raise Exception(f"Error during single crawl request: {str(e)}")

    async def extract_vision(
        self,
        url: str,
        fields: Optional[List[str]] = None,
        timeout: int = 60000
    ) -> VisionExtractResponse:
        """Call the vision extraction endpoint to extract structured fields from a rendered screenshot.

        Args:
            url: The page URL to render and analyze
            fields: Optional list of keys to extract (e.g., ["name","price","currency","availability"])
            timeout: Navigation timeout in ms
        """
        request = VisionExtractRequest(url=url, fields=fields, timeout=timeout)
        vision_url = f"{self.base_url}/extract-vision"
        payload = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
        logger.debug(f"Sending vision extract request to: {vision_url} | Payload: {json.dumps(payload)[:200]}...")

        try:
            async with self.session.post(
                vision_url,
                json=payload,
                timeout=60
            ) as response:
                logger.debug(f"Vision extract response status: {response.status}")
                data = await response.json()
                return VisionExtractResponse(
                    success=bool(data.get("success")),
                    data=data.get("data"),
                    elapsed_time=float(data.get("elapsed_time", 0.0)),
                    error=data.get("error")
                )
        except Exception as e:
            logger.error(f"Vision extract request failed with error: {str(e)}")
            raise Exception(f"Error during vision extract request: {str(e)}")

if __name__ == "__main__":
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