"""
Web crawler implementation.
"""

from typing import List, Dict, Any, Optional, Set
import asyncio
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from loguru import logger
from pydantic import BaseModel, Field
from crawl4ai import AsyncWebCrawler, CrawlResult, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai import CrawlerMonitor, DisplayMode
from dotenv import load_dotenv
import aiohttp
from asyncio import TimeoutError
from urllib.robotparser import RobotFileParser
from .storage import StorageBackend, PostgresStorage, RedisStorage
from datetime import datetime
import psutil
import sys
from bs4 import BeautifulSoup
from .agent import BaseAgent
from .models import CrawlerSettings
import time

# Load environment variables
load_dotenv()

def get_memory_usage():
    """Get current memory usage percentage."""
    process = psutil.Process(os.getpid())
    return process.memory_percent()

def log_memory_usage(context: str, debug: bool = False):
    """Log memory usage with context. Only logs if debug is True."""
    memory_percent = get_memory_usage()
    if debug:
        logger.debug(f"Memory Usage [{context}]: {memory_percent:.2f}%")
    return memory_percent

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
    robot_parser: Optional[RobotFileParser] = None
    processed_urls: Set[str] = set()
    processed_sitemaps: Set[str] = set()
    site_urls: List[str] = []
    debug: bool = os.getenv("CRAWLER_DEBUG", "false").lower() == "true"

    model_config = {
        "arbitrary_types_allowed": True
    }

    def __init__(self, **data):
        super().__init__(**data)
        if self.respect_robots:
            self.robot_parser = RobotFileParser()
        # Parse site URLs from environment variable
        self.site_urls = self._parse_site_urls()
        # Log initial memory usage
        log_memory_usage("Crawler Initialization", self.debug)

    def _parse_site_urls(self) -> List[str]:
        """Parse site URLs from environment variable."""
        urls_str = os.getenv("CRAWLER_SITE_URL", "https://ai.pydantic.dev")
        return [url.strip() for url in urls_str.split(",") if url.strip()]

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to avoid duplicates with different formats."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

    def check_memory_threshold(self) -> bool:
        """Check if memory usage exceeds threshold and log the status."""
        memory_percent = log_memory_usage("Memory Threshold Check", self.debug)
        is_exceeded = memory_percent > self.memory_threshold
        if is_exceeded:
            logger.warning(f"Memory threshold exceeded: {memory_percent:.2f}% > {self.memory_threshold}%")
        return is_exceeded

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not self.respect_robots:
            return True
            
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            self.robot_parser.set_url(robots_url)
            self.robot_parser.user_agent = self.user_agent
            self.robot_parser.read()
            
            return self.robot_parser.can_fetch(self.user_agent, url)
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {str(e)}")
            return False

    async def _get_sitemap_urls(self, base_url: str) -> List[str]:
        """Extract URLs from sitemap.xml."""
        urls = []
        try:
            if self.respect_robots:
                robots_url = urljoin(base_url, "/robots.txt")
                if await self._check_robots_txt(robots_url):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(robots_url, timeout=self.timeout) as response:
                            if response.status == 200:
                                robots_text = await response.text()
                                for line in robots_text.split('\n'):
                                    if line.lower().startswith('sitemap:'):
                                        sitemap_url = line.split(':', 1)[1].strip()
                                        if sitemap_url not in self.processed_sitemaps:
                                            self.processed_sitemaps.add(sitemap_url)
                                            urls.extend(await self._parse_sitemap(sitemap_url))
                                            break
            
            if not urls:
                common_sitemaps = [
                    urljoin(base_url, "/sitemap.xml"),
                    urljoin(base_url, "/sitemap_index.xml"),
                ]
                
                for sitemap_url in common_sitemaps:
                    if sitemap_url not in self.processed_sitemaps:
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(sitemap_url, timeout=self.timeout) as response:
                                    if response.status == 200:
                                        urls.extend(await self._parse_sitemap(sitemap_url))
                                        self.processed_sitemaps.add(sitemap_url)
                                        break
                        except Exception as e:
                            logger.warning(f"Failed to fetch sitemap from {sitemap_url}: {str(e)}")
                            continue
                        
        except Exception as e:
            logger.error(f"Error fetching sitemap: {str(e)}")
            
        return urls

    async def _parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse a sitemap XML file and extract URLs."""
        urls = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=self.timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        root = ET.fromstring(content)
                        
                        if 'sitemapindex' in root.tag:
                            for sitemap in root.findall('.//{*}loc'):
                                sitemap_url = sitemap.text
                                if sitemap_url not in self.processed_sitemaps:
                                    self.processed_sitemaps.add(sitemap_url)
                                    urls.extend(await self._parse_sitemap(sitemap_url))
                        else:
                            for url in root.findall('.//{*}url'):
                                loc = url.find('{*}loc')
                                if loc is not None and loc.text:
                                    urls.append(loc.text)
                                
        except Exception as e:
            logger.error(f"Error parsing sitemap {sitemap_url}: {str(e)}")
            
        return urls

    async def _filter_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs based on allowed domains and exclude patterns."""
        filtered_urls = []
        for url in urls:
            normalized_url = self._normalize_url(url)
            if normalized_url in self.processed_urls:
                continue
                
            if self.allowed_domains:
                if not any(domain in url for domain in self.allowed_domains):
                    continue
                    
            if self.exclude_patterns:
                if any(pattern in url for pattern in self.exclude_patterns):
                    continue
                    
            filtered_urls.append(url)
            self.processed_urls.add(normalized_url)
            
        return filtered_urls[:self.max_pages]

class WebCrawlerAgent(BaseAgent):
    """Agent for crawling web pages."""
    
    def __init__(self, settings: CrawlerSettings):
        """Initialize the web crawler agent."""
        super().__init__(settings)
        self.session = None
        self.processed_urls: Set[str] = set()
        self.start_time = None
        
        # Initialize storage backends
        self.redis_storage = None
        self.postgres_storage = None
        if settings.storage_redis:
            self.redis_storage = RedisStorage()
        if settings.storage_postgres:
            self.postgres_storage = PostgresStorage()
    
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """
        Crawl a single URL and return the extracted data.
        
        Args:
            url: The URL to crawl
            
        Returns:
            Dict containing the crawled data and metadata
        """
        try:
            logger.info(f"Starting crawl of {url}")
            
            # Check memory usage before crawling
            if self.settings.debug:
                memory_percent = psutil.Process().memory_percent()
                logger.debug(f"Memory usage before crawling {url}: {memory_percent:.2f}%")
            
            # Perform the crawl
            async with self.session.get(url, timeout=self.settings.timeout/1000) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract data
                data = {
                    'url': url,
                    'html': html,
                    'text': soup.get_text(),
                    'title': soup.title.string if soup.title else None,
                    'links': [
                        urljoin(url, link['href'])
                        for link in soup.find_all('a', href=True)
                    ],
                    'metadata': {
                        'status_code': response.status,
                        'headers': dict(response.headers),
                        'content_type': response.headers.get('content-type'),
                        'timestamp': time.time()
                    }
                }
                
                # Store results if storage is configured
                if self.redis_storage:
                    await self.redis_storage.store_result(url, data)
                if self.postgres_storage:
                    await self.postgres_storage.store_result(url, data)
                
                # Check memory usage after crawling
                if self.settings.debug:
                    memory_percent = psutil.Process().memory_percent()
                    logger.debug(f"Memory usage after crawling {url}: {memory_percent:.2f}%")
                
                logger.info(f"Completed crawl of {url}")
                return data
                
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            raise
    
    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs in parallel.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of dictionaries containing the crawled data
        """
        try:
            logger.info(f"Starting crawl of {len(urls)} URLs")
            self.start_time = time.time()
            
            # Create tasks for each URL
            tasks = []
            for url in urls:
                if url not in self.processed_urls:
                    tasks.append(asyncio.create_task(self.crawl_url(url)))
                    self.processed_urls.add(url)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)
            
            logger.info(f"Completed crawl of {len(results)} URLs")
            return results
            
        except Exception as e:
            logger.error(f"Error during crawl: {str(e)}")
            raise
    
    async def __aenter__(self):
        """Enter the async context."""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': self.settings.user_agent}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context."""
        if self.session:
            await self.session.close()
        if self.redis_storage:
            await self.redis_storage.close()
        if self.postgres_storage:
            await self.postgres_storage.close() 