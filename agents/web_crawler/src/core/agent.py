"""
Base agent class for web crawling.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Set
import asyncio
import os
from logging import setup_logger
from crawl4ai import AsyncWebCrawler, CrawlResult, CrawlerRunConfig, BrowserConfig
import aiohttp
from .models import CrawlerSettings

# Initialize logger
logger = setup_logger("web_crawler.agent")

class BaseAgent(ABC):
    """Base class for web crawling agents."""
    
    def __init__(self, settings: CrawlerSettings):
        """Initialize the agent with settings."""
        self.settings = settings
        self.browser_config = BrowserConfig(
            headless=os.getenv("CRAWLER_HEADLESS", "true").lower() == "true",
            viewport_width=int(os.getenv("CRAWLER_VIEWPORT_WIDTH", "1920")),
            viewport_height=int(os.getenv("CRAWLER_VIEWPORT_HEIGHT", "1080"))
        )
        self.crawler = None
        logger.info(f"Initialized agent with settings: {settings.model_dump()}")

    @abstractmethod
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """
        Crawl a single URL and return the extracted data.
        
        Args:
            url: The URL to crawl
            
        Returns:
            Dict containing the crawled data and metadata
        """
        pass
    
    @abstractmethod
    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs in parallel.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of dictionaries containing the crawled data
        """
        pass
    
    async def __aenter__(self):
        """Enter the async context."""
        self.session = aiohttp.ClientSession()
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context."""
        if self.session:
            await self.session.close()
        if self.crawler:
            await self.crawler.close()

    async def _crawl_url_async(self, url: str) -> CrawlResult:
        """Internal async method to crawl a URL."""
        config = CrawlerRunConfig(
            check_robots_txt=self.settings.respect_robots,
            verbose=True,
            wait_until="domcontentloaded",
            page_timeout=self.settings.timeout * 1000  # Convert to milliseconds
        )
        result = await self.crawler.arun(url=url, config=config)
        return result[0]  # arun returns a container with one result

    def _process_result(self, result: CrawlResult) -> Dict[str, Any]:
        """Process the crawl result into a dictionary format."""
        return {
            'url': result.url,
            'title': result.metadata.get('title', ''),
            'text': result.markdown.raw_markdown if result.markdown else '',
            'links': result.links,
            'metadata': result.metadata
        }

    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs and return the extracted data for each.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of dictionaries containing crawled data and metadata
        """
        results = []
        start_time = asyncio.get_event_loop().time()
        
        try:
            # If sitemap is enabled, try to get more URLs from sitemap
            if self.settings.use_sitemap:
                for base_url in urls:
                    # Check if we've exceeded the maximum time
                    if asyncio.get_event_loop().time() - start_time > self.settings.max_total_time:
                        logger.warning("Maximum crawling time reached")
                        break
                        
                    try:
                        sitemap_urls = await self.settings._get_sitemap_urls(base_url)
                        if sitemap_urls:
                            logger.info(f"Found {len(sitemap_urls)} URLs in sitemap")
                            filtered_urls = await self.settings._filter_urls(sitemap_urls)
                            logger.info(f"Filtered to {len(filtered_urls)} URLs")
                            urls.extend(filtered_urls)
                    except Exception as e:
                        logger.error(f"Error processing sitemap for {base_url}: {str(e)}")
            
            # Remove duplicates while preserving order
            urls = list(dict.fromkeys(urls))
            
            for url in urls:
                # Check if we've exceeded the maximum time
                if asyncio.get_event_loop().time() - start_time > self.settings.max_total_time:
                    logger.warning("Maximum crawling time reached")
                    break
                    
                # Check robots.txt if enabled
                if self.settings.respect_robots and not await self.settings._check_robots_txt(url):
                    logger.info(f"Skipping {url} due to robots.txt rules")
                    continue
                    
                try:
                    result = await self.crawl_url(url)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to crawl {url}: {str(e)}")
                    continue
                    
        except asyncio.TimeoutError:
            logger.error("Crawling timed out")
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            
        return results 