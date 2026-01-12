"""
Web crawler implementation.
"""

from typing import List, Dict, Any, Optional
import asyncio
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import fnmatch
from dotenv import load_dotenv
import aiohttp
from asyncio import TimeoutError
from urllib.robotparser import RobotFileParser
import psutil

from .models import CrawlerSettings
from bs4 import BeautifulSoup

import time
import json
from shared import setup_logger
from shared.database.context import DatabaseContext
from shared.models.webpage import WebPage

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

class WebCrawlerAgent:
    """Agent for crawling web pages with database integration and robust features."""
    
    def __init__(
        self,
        settings: CrawlerSettings,
        db_context: Optional[DatabaseContext] = None,
        use_database: bool = True,
    ):
        """Initialize the web crawler agent."""
        self.settings = settings
        self.session = None
        self.start_time = None
        self.db_context = db_context
        self.use_database = use_database
        self._owns_db_context = False
        self._robots_cache: Dict[str, RobotFileParser] = {}
        self._robots_cache_ts: Dict[str, float] = {}
        self._robots_cache_ttl_seconds = int(os.getenv("CRAWLER_ROBOTS_CACHE_TTL_SECONDS", "3600"))
        logger.info(f"Initialized robust web crawler agent with settings: {settings.model_dump()}")
    
    async def __aenter__(self):
        """Enter async context."""
        # Create session with comprehensive browser-like headers
        self.session = aiohttp.ClientSession(headers=self.settings._get_browser_headers())
        if self.use_database and self.db_context is None:
            self.db_context = DatabaseContext()
            await self.db_context.__aenter__()
            self._owns_db_context = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
        # Only close the db_context if we created it
        if self._owns_db_context and self.db_context:
            await self.db_context.__aexit__(exc_type, exc_val, exc_tb)

    async def _maybe_backoff_for_memory(self, context: str) -> None:
        """Best-effort memory backoff to avoid exhaustion."""
        try:
            if self.settings.memory_threshold <= 0:
                return
            memory_percent = get_memory_usage()
            if memory_percent <= self.settings.memory_threshold:
                return
            # Simple adaptive backoff: sleep longer as we exceed threshold.
            over = max(0.0, memory_percent - self.settings.memory_threshold)
            sleep_s = min(5.0, 0.25 + over / 10.0)
            logger.warning(
                f"Memory threshold exceeded [{context}]: {memory_percent:.2f}% > {self.settings.memory_threshold:.2f}% "
                f"(backing off {sleep_s:.2f}s)"
            )
            await asyncio.sleep(sleep_s)
        except Exception as e:
            logger.debug(f"Memory backoff check failed [{context}]: {e}")

    def _matches_exclude_patterns(self, url: str) -> bool:
        """Return True if the URL matches any exclude pattern.

        Semantics:
        - If a pattern contains glob metacharacters (* ? []), use fnmatch against the full URL.
        - Otherwise, treat it as a simple substring match (backward compatible).
        """
        if not self.settings.exclude_patterns:
            return False
        for pattern in self.settings.exclude_patterns:
            if pattern is None:
                continue
            p = pattern.strip()
            if not p:
                continue
            if any(ch in p for ch in ["*", "?", "[", "]"]):
                if fnmatch.fnmatch(url, p):
                    return True
            else:
                if p in url:
                    return True
        return False

    async def _is_allowed_by_robots(self, url: str) -> bool:
        """Return True if robots.txt allows fetching this url (best-effort)."""
        if not self.settings.respect_robots:
            return True
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return True
            domain = parsed.netloc
            now = time.time()
            cached = self._robots_cache.get(domain)
            cached_ts = self._robots_cache_ts.get(domain, 0.0)
            if cached and (now - cached_ts) < self._robots_cache_ttl_seconds:
                return cached.can_fetch(self.settings.user_agent, url)

            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                # Keep robots fetching bounded; if it fails, allow (best-effort).
                async with self.session.get(robots_url, timeout=min(10, self.settings.timeout / 1000)) as resp:
                    if resp.status >= 400:
                        self._robots_cache[domain] = rp
                        self._robots_cache_ts[domain] = now
                        return True
                    content = await resp.text()
                rp.parse(content.splitlines())
            except Exception as e:
                logger.debug(f"robots.txt fetch/parse failed for {robots_url}: {e}")
                self._robots_cache[domain] = rp
                self._robots_cache_ts[domain] = now
                return True

            self._robots_cache[domain] = rp
            self._robots_cache_ts[domain] = now
            return rp.can_fetch(self.settings.user_agent, url)
        except Exception as e:
            logger.debug(f"robots allow check failed for {url}: {e}")
            return True
    
    async def crawl_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl a single URL and return the extracted data."""
        try:
            logger.debug(f"Starting crawl of {url}")
            
            # Check memory usage before crawling
            if self.settings.debug:
                memory_percent = psutil.Process().memory_percent()
                logger.debug(f"Memory usage before crawling {url}: {memory_percent:.2f}%")
            
            # Perform the crawl
            await self._maybe_backoff_for_memory("before_fetch")
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
                    html=html,  # Add raw HTML content for storage compatibility
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
                
                # Save webpage using shared components with timeout protection
                if self.use_database and self.db_context is not None:
                    try:
                        await asyncio.wait_for(
                            self.db_context.webpages.save(webpage),
                            timeout=30.0  # 30 second timeout for database operations
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Database save timed out for {url}")
                        # Continue without saving to database, but still return the result
                    except Exception as e:
                        logger.error(f"Database save failed for {url}: {str(e)}")
                        # Continue without saving to database, but still return the result
                
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
            logger.error(f"Exception type: {type(e).__name__}")
            if hasattr(e, 'errno'):
                logger.error(f"Error code: {e.errno}")
            # For debugging network issues, log more details
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
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
        successful_crawls = len(self.settings.processed_urls)
        if successful_crawls >= self.settings.max_pages:
            logger.info(f"Reached max pages {self.settings.max_pages}")
            return []

        try:
            logger.debug(f"Starting crawl of {len(urls)} URLs at depth {current_depth}")
            self.start_time = time.time() if current_depth == 0 else self.start_time
            
            # Check if we've exceeded the maximum total time
            if self.start_time and (time.time() - self.start_time) > self.settings.max_total_time:
                logger.warning(f"Maximum total time {self.settings.max_total_time}s exceeded, stopping crawl")
                return []
            
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
                    # Check time limit before each URL
                    if self.start_time and (time.time() - self.start_time) > self.settings.max_total_time:
                        logger.warning(f"Time limit exceeded, skipping {url}")
                        return None
                    # Enforce robots.txt (best-effort) if enabled
                    if not await self._is_allowed_by_robots(url):
                        logger.info(f"Skipping {url} due to robots.txt rules")
                        return None
                    await self._maybe_backoff_for_memory("before_crawl_url")
                    result = await self.crawl_url(url)
                    if result:
                        self.settings.processed_urls.add(url)
                    return result

            for url in filtered_urls:
                tasks.append(asyncio.create_task(crawl_with_semaphore(url)))

            # Wait for all tasks to complete with a timeout
            try:
                # Calculate remaining time for this batch
                remaining_time = self.settings.max_total_time
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    remaining_time = max(5, self.settings.max_total_time - elapsed)  # At least 5 seconds
                
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), 
                    timeout=remaining_time
                )
            except asyncio.TimeoutError:
                logger.warning(f"Batch crawling timed out after {remaining_time}s")
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Wait a bit for cancellation to complete
                await asyncio.sleep(0.1)
                results = [task.result() if task.done() and not task.cancelled() else None for task in tasks]
            
            valid_results = [r for r in results if isinstance(r, dict)]
            
            # Check if we should continue crawling (with time limit check)
            successful_crawls += len(valid_results)
            if (current_depth < self.settings.max_depth and 
                successful_crawls < self.settings.max_pages and
                (not self.start_time or (time.time() - self.start_time) < self.settings.max_total_time)):
                
                # Extract all links from results
                next_urls = []
                for result in valid_results:
                    next_urls.extend(result.get('links', []))
                
                if next_urls:
                    logger.debug(f"Found {len(next_urls)} new URLs at depth {current_depth}")
                    # Recursively crawl next level with timeout protection
                    try:
                        remaining_time = self.settings.max_total_time
                        if self.start_time:
                            elapsed = time.time() - self.start_time
                            remaining_time = max(5, self.settings.max_total_time - elapsed)
                        
                        next_results = await asyncio.wait_for(
                            self.crawl_urls(next_urls, current_depth + 1),
                            timeout=remaining_time
                        )
                        valid_results.extend(next_results)
                    except asyncio.TimeoutError:
                        logger.warning(f"Recursive crawling timed out at depth {current_depth + 1}")
            
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
        if self._matches_exclude_patterns(url):
            return False

        return True 