"""
Web crawler implementation.
"""

from typing import List, Dict, Any, Optional, Set
import asyncio
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import aiohttp
from asyncio import TimeoutError
from urllib.robotparser import RobotFileParser
import psutil
from bs4 import BeautifulSoup
from .agent import BaseAgent
import time
import json
from logging import setup_logger
from database.context import DatabaseContext
from models.webpage import WebPage

# Initialize logger
logger = setup_logger("web_crawler.core")

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

def get_domain(url: str) -> str:
    """Extract the domain from a URL."""
    parsed = urlparse(url)
    return parsed.netloc

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
    debug: bool = os.getenv("CRAWLER_LOG_LEVEL", "false").lower() == "true"

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
        self.start_time = None
        self.db_context = None
    
    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        self.db_context = DatabaseContext()
        await self.db_context.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
        if self.db_context:
            await self.db_context.__aexit__(exc_type, exc_val, exc_tb)
    
    async def crawl_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl a single URL and return the extracted data."""
        try:
            logger.debug(f"Starting crawl of {url}")
            
            # Check memory usage before crawling
            if self.settings.debug:
                memory_percent = psutil.Process().memory_percent()
                logger.debug(f"Memory usage before crawling {url}: {memory_percent:.2f}%")
            
            # Perform the crawl
            async with self.session.get(url, timeout=self.settings.timeout/1000) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract meta tags
                meta_tags = {}
                for meta in soup.find_all('meta'):
                    name = meta.get('name', meta.get('property', ''))
                    if name:
                        meta_tags[name] = meta.get('content', '')

                # Extract headers hierarchy
                headers = {
                    'h1': [h.get_text(strip=True) for h in soup.find_all('h1')],
                    'h2': [h.get_text(strip=True) for h in soup.find_all('h2')],
                    'h3': [h.get_text(strip=True) for h in soup.find_all('h3')]
                }

                # Extract images
                images = [{
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                } for img in soup.find_all('img')]

                # Extract structured data (JSON-LD)
                structured_data = []
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        structured_data.append(json.loads(script.string))
                    except (json.JSONDecodeError, AttributeError):
                        pass

                # Extract main content (article or main tag)
                main_content = ''
                main_tag = soup.find('main') or soup.find('article')
                if main_tag:
                    main_content = main_tag.get_text(strip=True)
                
                # Create webpage instance
                webpage = WebPage.from_crawl_result(
                    url=url,
                    title=soup.title.string.strip() if soup.title else None,
                    text=soup.get_text(strip=True),
                    links=[
                        urljoin(url, link['href'])
                        for link in soup.find_all('a', href=True)
                    ],
                    metadata={
                        'status_code': response.status,
                        'content_type': response.headers.get('content-type'),
                        'last_modified': response.headers.get('last-modified'),
                        'content_language': response.headers.get('content-language'),
                        'meta_tags': meta_tags,
                        'headers_hierarchy': headers,
                        'images': images,
                        'structured_data': structured_data,
                        'main_content': main_content
                    }
                )
                
                # Save webpage using shared components
                await self.db_context.webpages.save(webpage)
                
                # Check memory usage after crawling
                if self.settings.debug:
                    memory_percent = psutil.Process().memory_percent()
                    logger.debug(f"Memory usage after crawling {url}: {memory_percent:.2f}%")
                
                logger.info(f"Completed crawl of {url}")
                return webpage.to_redis_data()
                
        except TimeoutError:
            logger.warning(f"Timeout while crawling {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            return None
    
    async def crawl_urls(self, urls: List[str], current_depth: int = 0) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs in parallel, following links up to max_depth.
        
        Args:
            urls: List of URLs to crawl
            current_depth: Current crawl depth (internal use)
            
        Returns:
            List of dictionaries containing the crawled data
        """
        if current_depth > self.settings.max_depth:
            logger.info(f"Reached max depth {self.settings.max_depth}")
            return []

        # Track successfully crawled URLs separately from processed ones
        successful_crawls = len([url for url in self.settings.processed_urls if url in self.settings.processed_urls])
        if successful_crawls >= self.settings.max_pages:
            logger.info(f"Reached max pages {self.settings.max_pages}")
            return []

        try:
            logger.debug(f"Starting crawl of {len(urls)} URLs at depth {current_depth}")
            self.start_time = time.time() if current_depth == 0 else self.start_time
            
            # Filter URLs based on settings and remaining capacity
            remaining_slots = self.settings.max_pages - successful_crawls
            filtered_urls = []
            for url in urls:
                if len(filtered_urls) >= remaining_slots:
                    break
                if self._should_crawl_url(url):
                    filtered_urls.append(url)

            if not filtered_urls:
                return []

            # Create tasks for filtered URLs
            tasks = []
            semaphore = asyncio.Semaphore(self.settings.max_concurrent_pages)
            
            async def crawl_with_semaphore(url: str) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    result = await self.crawl_url(url)
                    if result:
                        self.settings.processed_urls.add(url)
                    return result

            for url in filtered_urls:
                tasks.append(asyncio.create_task(crawl_with_semaphore(url)))

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid_results = [r for r in results if isinstance(r, dict)]
            
            # Check if we should continue crawling
            successful_crawls += len(valid_results)
            if current_depth < self.settings.max_depth and successful_crawls < self.settings.max_pages:
                # Extract all links from results
                next_urls = []
                for result in valid_results:
                    next_urls.extend(result.get('links', []))
                
                if next_urls:
                    logger.debug(f"Found {len(next_urls)} new URLs at depth {current_depth}")
                    # Recursively crawl next level
                    next_results = await self.crawl_urls(next_urls, current_depth + 1)
                    valid_results.extend(next_results)
            
            logger.info(f"Completed crawl of {len(valid_results)} URLs at depth {current_depth} (total successfully crawled: {successful_crawls})")
            return valid_results
            
        except Exception as e:
            logger.error(f"Error during crawl at depth {current_depth}: {str(e)}")
            raise
    
    def _should_crawl_url(self, url: str) -> bool:
        """Check if a URL should be crawled based on settings."""
        # Skip if already processed
        if url in self.settings.processed_urls:
            return False

        # Check allowed domains
        if self.settings.allowed_domains:
            url_domain = get_domain(url)
            if not any(url_domain == domain for domain in self.settings.allowed_domains):
                return False

        # Check exclude patterns
        if self.settings.exclude_patterns:
            if any(pattern in url for pattern in self.settings.exclude_patterns):
                return False

        return True 