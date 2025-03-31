from typing import List, Dict, Any, Optional, Set
import asyncio
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from loguru import logger
from pydantic import BaseModel, HttpUrl
from crawl4ai import AsyncWebCrawler, CrawlResult, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai import CrawlerMonitor, DisplayMode
from dotenv import load_dotenv
import aiohttp
from bs4 import BeautifulSoup
from asyncio import TimeoutError
from urllib.robotparser import RobotFileParser
import json
from datetime import datetime
from pathlib import Path
from .database import Database

# Load environment variables
load_dotenv()

class CrawlerSettings(BaseModel):
    """Settings for the web crawler agent."""
    max_pages: int = int(os.getenv("CRAWLER_MAX_PAGES", "100"))
    max_depth: int = int(os.getenv("CRAWLER_MAX_DEPTH", "3"))
    respect_robots: bool = os.getenv("CRAWLER_RESPECT_ROBOTS", "true").lower() == "true"
    user_agent: str = os.getenv("CRAWLER_USER_AGENT", "Crawl4AI Agent/1.0")
    timeout: int = int(os.getenv("CRAWLER_TIMEOUT", "30"))
    allowed_domains: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    use_sitemap: bool = True  # Whether to use sitemap.xml for crawling
    max_total_time: int = int(os.getenv("CRAWLER_MAX_TOTAL_TIME", "300"))  # Maximum total time in seconds
    robot_parser: Optional[RobotFileParser] = None
    processed_urls: Set[str] = set()
    processed_sitemaps: Set[str] = set()
    content_dir: str = os.getenv("CRAWLER_CONTENT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/crawled_content"))
    max_concurrent_pages: int = int(os.getenv("CRAWLER_MAX_CONCURRENT_PAGES", "5"))  # Maximum concurrent pages to crawl
    memory_threshold: float = float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0"))  # Memory threshold percentage

    model_config = {
        "arbitrary_types_allowed": True
    }

    def __init__(self, **data):
        super().__init__(**data)
        if self.respect_robots:
            self.robot_parser = RobotFileParser()
        # Create content directory if it doesn't exist
        self.content_dir = os.path.abspath(self.content_dir)
        logger.info(f"Content directory (absolute path): {self.content_dir}")
        try:
            Path(self.content_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Created/verified content directory at: {self.content_dir}")
        except Exception as e:
            logger.error(f"Failed to create content directory at {self.content_dir}: {str(e)}")
            raise

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to avoid duplicates with different formats."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not self.respect_robots:
            return True
            
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            # Set user agent for robots.txt check
            self.robot_parser.set_url(robots_url)
            self.robot_parser.user_agent = self.user_agent
            
            # Read and parse robots.txt
            self.robot_parser.read()
            
            # Check if crawling is allowed
            return self.robot_parser.can_fetch(self.user_agent, url)
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {str(e)}")
            # If we can't check robots.txt, be conservative and assume crawling is not allowed
            return False

    async def _get_sitemap_urls(self, base_url: str) -> List[str]:
        """Extract URLs from sitemap.xml."""
        urls = []
        try:
            # Try to find sitemap in robots.txt first if respect_robots is enabled
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
            
            # If no sitemap found in robots.txt or respect_robots is False, try common sitemap locations
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
                        
                        # Handle sitemap index files
                        if 'sitemapindex' in root.tag:
                            for sitemap in root.findall('.//{*}loc'):
                                sitemap_url = sitemap.text
                                if sitemap_url not in self.processed_sitemaps:
                                    self.processed_sitemaps.add(sitemap_url)
                                    urls.extend(await self._parse_sitemap(sitemap_url))
                        else:
                            # Handle regular sitemap files
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
                
            # Check if URL is from allowed domains
            if self.allowed_domains:
                if not any(domain in url for domain in self.allowed_domains):
                    continue
                    
            # Check if URL matches exclude patterns
            if self.exclude_patterns:
                if any(pattern in url for pattern in self.exclude_patterns):
                    continue
                    
            filtered_urls.append(url)
            self.processed_urls.add(normalized_url)
            
        return filtered_urls[:self.max_pages]
    
    async def _crawl_url_async(self, url: str) -> CrawlResult:
        """Internal async method to crawl a URL."""
        config = CrawlerRunConfig(
            check_robots_txt=self.respect_robots,
            verbose=True,
            wait_until="domcontentloaded",
            page_timeout=self.timeout * 1000  # Convert to milliseconds
        )
        result = await self.crawler.arun(url=url, config=config)
        return result[0]  # arun returns a container with one result
    
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
            result = await self._crawl_url_async(url)
            logger.info(f"Completed crawl of {url}")
            return self._process_result(result)
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            raise
    
    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs in parallel and return the extracted data for each.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of dictionaries containing crawled data and metadata
        """
        results = []
        start_time = asyncio.get_event_loop().time()
        
        try:
            # If sitemap is enabled, try to get more URLs from sitemap
            if self.use_sitemap:
                for base_url in urls:
                    if asyncio.get_event_loop().time() - start_time > self.max_total_time:
                        logger.warning("Maximum crawling time reached")
                        break
                        
                    try:
                        sitemap_urls = await self._get_sitemap_urls(base_url)
                        if sitemap_urls:
                            logger.info(f"Found {len(sitemap_urls)} URLs in sitemap")
                            filtered_urls = await self._filter_urls(sitemap_urls)
                            logger.info(f"Filtered to {len(filtered_urls)} URLs")
                            urls.extend(filtered_urls)
                    except Exception as e:
                        logger.error(f"Error processing sitemap for {base_url}: {str(e)}")
            
            # Remove duplicates while preserving order
            urls = list(dict.fromkeys(urls))
            
            # Configure the dispatcher for parallel crawling
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=self.memory_threshold,
                check_interval=1.0,
                max_session_permit=self.max_concurrent_pages,
                monitor=CrawlerMonitor(
                    max_visible_rows=15,
                    display_mode=DisplayMode.DETAILED
                )
            )
            
            # Configure crawler run settings
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                check_robots_txt=self.respect_robots,
                verbose=True,
                wait_until="domcontentloaded",
                page_timeout=self.timeout * 1000
            )
            
            # Crawl URLs in parallel using the dispatcher
            async for result in await self.crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            ):
                if result.success:
                    try:
                        processed_result = self._process_result(result)
                        results.append(processed_result)
                    except Exception as e:
                        logger.error(f"Failed to process result for {result.url}: {str(e)}")
                else:
                    logger.error(f"Failed to crawl {result.url}: {result.error_message}")
                    
                # Check if we've exceeded the maximum time
                if asyncio.get_event_loop().time() - start_time > self.max_total_time:
                    logger.warning("Maximum crawling time reached")
                    break
                    
        except TimeoutError:
            logger.error("Crawling timed out")
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            
        return results

    def _get_content_filename(self, url: str) -> str:
        """Generate a filename for storing content."""
        parsed_url = urlparse(url)
        # Create a safe filename from the URL
        safe_path = parsed_url.path.strip('/').replace('/', '_')
        if not safe_path:
            safe_path = 'index'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{parsed_url.netloc}_{safe_path}_{timestamp}"

    def _store_content(self, result: Dict[str, Any]) -> None:
        """Store crawled content in files."""
        try:
            # Ensure content directory exists
            Path(self.content_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Verified content directory exists: {self.content_dir}")
            
            # Create a safe filename
            filename = self._get_content_filename(result['url'])
            logger.info(f"Generated filename '{filename}' for URL: {result['url']}")
            
            # Store raw content
            raw_file = Path(self.content_dir) / f"{filename}_raw.json"
            logger.info(f"Writing raw content to: {raw_file} (absolute path: {raw_file.absolute()})")
            try:
                with open(raw_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"Successfully wrote raw content to {raw_file}")
            except Exception as e:
                logger.error(f"Failed to write raw content to {raw_file}: {str(e)}")
                raise
            
            # Store processed content (markdown)
            if result.get('text'):
                md_file = Path(self.content_dir) / f"{filename}.md"
                logger.info(f"Writing markdown content to: {md_file} (absolute path: {md_file.absolute()})")
                try:
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(f"# {result.get('title', 'Untitled')}\n\n")
                        f.write(f"Source: {result.get('url')}\n\n")
                        f.write("## Content\n\n")
                        f.write(result['text'])
                    logger.info(f"Successfully wrote markdown content to {md_file}")
                except Exception as e:
                    logger.error(f"Failed to write markdown content to {md_file}: {str(e)}")
                    raise
            else:
                logger.warning(f"No text content available for {result['url']}, skipping markdown file")
            
            logger.info(f"Successfully stored all content for {result['url']}")
            
        except Exception as e:
            logger.error(f"Error storing content for {result['url']}: {str(e)}")
            logger.error(f"Current working directory: {os.getcwd()}")
            logger.error(f"Content directory: {self.content_dir}")
            logger.error(f"Content directory exists: {os.path.exists(self.content_dir)}")
            logger.error(f"Content directory is writable: {os.access(self.content_dir, os.W_OK)}")
            raise

    def _process_result(self, result: CrawlResult) -> Dict[str, Any]:
        """Process the crawl result into a dictionary format."""
        logger.info(f"Processing result for URL: {result.url}")
        
        # Extract markdown content safely
        markdown_content = ''
        if result.markdown:
            markdown_content = result.markdown.raw_markdown
            logger.info(f"Extracted markdown content length: {len(markdown_content)}")
        else:
            logger.warning(f"No markdown content available for {result.url}")
        
        # Extract metadata safely
        metadata = {}
        if result.metadata:
            metadata = result.metadata
            logger.info(f"Extracted metadata keys: {', '.join(metadata.keys())}")
        else:
            logger.warning(f"No metadata available for {result.url}")
        
        # Create processed result with all required fields
        processed_result = {
            'url': result.url,
            'title': metadata.get('title', 'Untitled'),
            'text': markdown_content,
            'links': result.links if result.links else [],
            'metadata': metadata,
            'crawl_timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Created processed result with {len(processed_result['text'])} characters of text")
        
        # Store the content
        try:
            self._store_content(processed_result)
            logger.info(f"Successfully stored content for {result.url}")
        except Exception as e:
            logger.error(f"Failed to store content for {result.url}: {str(e)}")
            raise
        
        return processed_result

    async def _extract_text_async(self, html_content: str) -> str:
        """Internal async method to extract text."""
        async with AsyncWebCrawler(self.crawler.config) as crawler:
            return crawler.extract_text(html_content)

    async def extract_text(self, html_content: str) -> str:
        """
        Extract text content from HTML.
        
        Args:
            html_content: The HTML content to extract text from
            
        Returns:
            Extracted text content
        """
        return await self._extract_text_async(html_content)
    
    async def _extract_links_async(self, html_content: str) -> List[str]:
        """Internal async method to extract links."""
        async with AsyncWebCrawler(self.crawler.config) as crawler:
            return crawler.extract_links(html_content)

    async def extract_links(self, html_content: str) -> List[str]:
        """
        Extract links from HTML content.
        
        Args:
            html_content: The HTML content to extract links from
            
        Returns:
            List of extracted URLs
        """
        return await self._extract_links_async(html_content)
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        self.crawler = AsyncWebCrawler(self.crawler.config)
        self.db = Database()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
        if self.crawler:
            await self.crawler.close()
        if self.db:
            self.db.close()

class WebCrawlerAgent:
    """Agent for crawling web pages."""
    def __init__(self, settings: CrawlerSettings):
        self.settings = settings
        self.crawler = AsyncWebCrawler(settings)
        self.processed_urls: Set[str] = set()
        self.processed_sitemaps: Set[str] = set()
        logger.info("WebCrawler initialized with settings:")
        logger.info(f"  - Max pages: {settings.max_pages}")
        logger.info(f"  - Max depth: {settings.max_depth}")
        logger.info(f"  - Timeout: {settings.timeout}")
        logger.info(f"  - Max total time: {settings.max_total_time}")
        logger.info(f"  - Respect robots.txt: {settings.respect_robots}")
        logger.info(f"  - Max concurrent pages: {settings.max_concurrent_pages}")
        logger.info(f"  - Memory threshold: {settings.memory_threshold}%")

__all__ = ['CrawlerSettings', 'WebCrawlerAgent'] 