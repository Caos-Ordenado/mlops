"""
BatchContentRetriever: Intelligent caching service for bulk content retrieval.

This service implements a 3-layer caching strategy:
1. Memory cache (fastest, 5-minute TTL)
2. Redis cache (fast, 1-hour TTL) 
3. Database + Web crawling (slowest, persistent)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Union
from datetime import datetime, timedelta

from shared.logging import setup_logger
from shared.web_crawler_client import WebCrawlerClient
from shared.repositories.webpage import WebPageRepository
from shared.database.manager import DatabaseManager
from shared.redis_client import RedisClient

logger = setup_logger("batch_content_retriever")


@dataclass
class PageContent:
    """Content with optional structured data for price extraction."""
    text: str
    meta_tags: Optional[Dict[str, Any]] = None
    structured_data: Optional[List[Dict[str, Any]]] = None


class ContentCacheEntry:
    """Represents a cached content entry with TTL."""
    
    def __init__(self, content: PageContent, timestamp: float, ttl_seconds: int = 300):
        self.content = content
        self.timestamp = timestamp
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > self.ttl_seconds

class BatchContentRetriever:
    """
    High-performance content retrieval service with intelligent 3-layer caching.
    
    Optimizations:
    - Memory cache: 5-minute TTL for ultra-fast repeated access
    - Redis cache: 1-hour TTL for session persistence 
    - Database cache: Permanent storage with automatic updates
    - Bulk crawling: Single request for multiple missing URLs
    """
    
    def __init__(self, 
                 memory_ttl_seconds: int = 300,  # 5 minutes
                 redis_ttl_seconds: int = 3600,  # 1 hour
                 max_memory_entries: int = 500):
        self.memory_ttl_seconds = memory_ttl_seconds
        self.redis_ttl_seconds = redis_ttl_seconds
        self.max_memory_entries = max_memory_entries
        
        # Memory cache with LRU eviction
        self.memory_cache: Dict[str, ContentCacheEntry] = {}
        self.access_order: List[str] = []  # For LRU tracking
        
        # Statistics for monitoring
        self.stats = {
            "memory_hits": 0,
            "redis_hits": 0, 
            "database_hits": 0,
            "crawl_requests": 0,
            "total_requests": 0
        }
        
        logger.info(f"BatchContentRetriever initialized with memory_ttl={memory_ttl_seconds}s, redis_ttl={redis_ttl_seconds}s")
    
    async def get_contents_batch(self, urls: List[str]) -> Dict[str, PageContent]:
        """
        Retrieve content for multiple URLs using intelligent 3-layer caching.
        
        Args:
            urls: List of URLs to retrieve content for
            
        Returns:
            Dict mapping URL to PageContent (text + metadata for structured data extraction)
        """
        if not urls:
            return {}
        
        self.stats["total_requests"] += len(urls)
        logger.info(f"Retrieving content for {len(urls)} URLs using batch retrieval")
        
        cached_content: Dict[str, PageContent] = {}
        missing_urls = []
        
        # Layer 1: Check memory cache
        memory_hits = await self._check_memory_cache(urls, cached_content, missing_urls)
        if memory_hits:
            self.stats["memory_hits"] += memory_hits
            logger.debug(f"Memory cache hits: {memory_hits}/{len(urls)}")
        
        # Layer 2: Check Redis cache for remaining URLs
        if missing_urls:
            redis_hits = await self._check_redis_cache(missing_urls, cached_content)
            if redis_hits:
                self.stats["redis_hits"] += redis_hits
                logger.debug(f"Redis cache hits: {redis_hits}/{len(missing_urls)}")
                # Update missing_urls list
                missing_urls = [url for url in missing_urls if url not in cached_content or cached_content[url] is None]
        
        # Layer 3: Check database for remaining URLs
        if missing_urls:
            db_hits = await self._check_database_cache(missing_urls, cached_content)
            if db_hits:
                self.stats["database_hits"] += db_hits
                logger.debug(f"Database cache hits: {db_hits}/{len(missing_urls)}")
                # Update missing_urls list
                missing_urls = [url for url in missing_urls if url not in cached_content or cached_content[url] is None]
        
        # Layer 4: Bulk crawl remaining URLs
        if missing_urls:
            crawled_content = await self._bulk_crawl_missing_urls(missing_urls)
            cached_content.update(crawled_content)
            
            # Update all cache layers with new content
            await self._update_all_caches(crawled_content)
        
        # Log performance stats
        total_found = len([c for c in cached_content.values() if c is not None])
        cache_hit_rate = ((len(urls) - len(missing_urls)) / len(urls) * 100) if urls else 0
        
        logger.info(f"Batch retrieval complete: {total_found}/{len(urls)} URLs found, "
                   f"cache hit rate: {cache_hit_rate:.1f}%, "
                   f"crawl requests: {len(missing_urls) if missing_urls else 0}")
        
        # Return only URLs with content (filter out None values)
        return {url: content for url, content in cached_content.items() if content is not None}
    
    async def _check_memory_cache(self, urls: List[str], cached_content: Dict[str, PageContent], missing_urls: List[str]) -> int:
        """Check memory cache and update LRU access order."""
        hits = 0
        current_time = time.time()
        
        for url in urls:
            if url in self.memory_cache:
                entry = self.memory_cache[url]
                if not entry.is_expired():
                    cached_content[url] = entry.content
                    # Update LRU order
                    if url in self.access_order:
                        self.access_order.remove(url)
                    self.access_order.append(url)
                    hits += 1
                else:
                    # Expired entry - remove it
                    del self.memory_cache[url]
                    if url in self.access_order:
                        self.access_order.remove(url)
                    missing_urls.append(url)
            else:
                missing_urls.append(url)
        
        return hits
    
    async def _check_redis_cache(self, urls: List[str], cached_content: Dict[str, PageContent]) -> int:
        """Check Redis cache for missing URLs, including metadata for structured data extraction."""
        hits = 0
        try:
            async with RedisClient() as redis_client:
                if not await redis_client.health_check():
                    logger.warning("Redis not healthy, skipping Redis cache check")
                    return 0
                
                # Batch get from Redis
                for url in urls:
                    redis_key = f"webpage:{url}"
                    redis_value = await redis_client.get(redis_key)
                    
                    if redis_value:
                        try:
                            webpage_data = json.loads(redis_value)
                            content = webpage_data.get("text") or webpage_data.get("full_text") or webpage_data.get("main_content", "")
                            if content:
                                # Extract metadata for structured data extraction
                                meta_tags = webpage_data.get("meta_tags")
                                structured_data = webpage_data.get("structured_data")
                                # Also check nested metadata field
                                if not meta_tags and "metadata" in webpage_data:
                                    meta_tags = webpage_data["metadata"].get("meta_tags")
                                if not structured_data and "metadata" in webpage_data:
                                    structured_data = webpage_data["metadata"].get("structured_data")
                                
                                page_content = PageContent(
                                    text=content,
                                    meta_tags=meta_tags,
                                    structured_data=structured_data if isinstance(structured_data, list) else [structured_data] if structured_data else None
                                )
                                cached_content[url] = page_content
                                # Update memory cache
                                self._add_to_memory_cache(url, page_content)
                                hits += 1
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Failed to parse Redis data for {url}: {e}")
                            
        except Exception as e:
            logger.warning(f"Redis cache check failed: {e}")
        
        return hits
    
    async def _check_database_cache(self, urls: List[str], cached_content: Dict[str, PageContent]) -> int:
        """Check database for cached webpage content, including metadata for structured data extraction."""
        hits = 0
        try:
            db_manager = DatabaseManager()
            await db_manager.init()  # Initialize database connection
            webpage_repo = WebPageRepository(db_manager)  # Let repo handle its own Redis
            
            async with db_manager.get_session() as session:
                for url in urls:
                    webpage = await webpage_repo.get_by_url(session, url)
                    if webpage and webpage.full_text:
                        # Extract metadata for structured data extraction
                        structured_data = webpage.structured_data
                        page_content = PageContent(
                            text=webpage.full_text,
                            meta_tags=webpage.meta_tags,
                            structured_data=structured_data if isinstance(structured_data, list) else [structured_data] if structured_data else None
                        )
                        cached_content[url] = page_content
                        # Update memory cache
                        self._add_to_memory_cache(url, page_content)
                        hits += 1
                        
        except Exception as e:
            logger.warning(f"Database cache check failed: {e}")
        
        return hits
    
    async def _bulk_crawl_missing_urls(self, urls: List[str]) -> Dict[str, PageContent]:
        """Crawl missing URLs in a single bulk request, including metadata for structured data extraction."""
        if not urls:
            return {}
        
        self.stats["crawl_requests"] += len(urls)
        logger.info(f"Bulk crawling {len(urls)} missing URLs")
        
        crawled_content: Dict[str, PageContent] = {}
        
        try:
            async with WebCrawlerClient() as client:
                # Use bulk crawl with minimal settings for speed
                response = await client.crawl(
                    urls=urls,
                    max_pages=1,  # Only crawl the specific URLs
                    max_depth=1,  # No link following
                    timeout=30000,  # 30 second timeout per page
                    max_total_time=120,  # 2 minute total timeout
                    max_concurrent_pages=5  # Reasonable concurrency
                )
                
                if response.success and response.results:
                    for result in response.results:
                        if result.url and result.text:
                            # Extract metadata from crawl result
                            meta_tags = None
                            structured_data = None
                            if hasattr(result, 'metadata') and result.metadata:
                                meta_tags = result.metadata.get("meta_tags")
                                sd = result.metadata.get("structured_data")
                                structured_data = sd if isinstance(sd, list) else [sd] if sd else None
                            
                            page_content = PageContent(
                                text=result.text,
                                meta_tags=meta_tags,
                                structured_data=structured_data
                            )
                            crawled_content[result.url] = page_content
                            logger.debug(f"Successfully crawled {result.url} ({len(result.text)} chars, has_metadata={meta_tags is not None or structured_data is not None})")
                        else:
                            logger.warning(f"No content found for {result.url}")
                else:
                    logger.error(f"Bulk crawl failed: {response.error if hasattr(response, 'error') else 'Unknown error'}")
                    
        except Exception as e:
            logger.error(f"Bulk crawl request failed: {e}")
            
        return crawled_content
    
    async def _update_all_caches(self, content_batch: Dict[str, PageContent]) -> None:
        """Update all cache layers with newly crawled content."""
        if not content_batch:
            return
        
        # Update memory cache
        for url, content in content_batch.items():
            self._add_to_memory_cache(url, content)
        
        # Note: Database and Redis updates are handled by the web crawler service
        # when it saves the crawled results. This avoids duplicate storage logic.
        logger.debug(f"Updated memory cache with {len(content_batch)} new entries")
    
    def _add_to_memory_cache(self, url: str, content: PageContent) -> None:
        """Add content to memory cache with LRU eviction."""
        current_time = time.time()
        
        # Add/update entry
        self.memory_cache[url] = ContentCacheEntry(content, current_time, self.memory_ttl_seconds)
        
        # Update LRU order
        if url in self.access_order:
            self.access_order.remove(url)
        self.access_order.append(url)
        
        # Evict old entries if cache is full
        while len(self.memory_cache) > self.max_memory_entries:
            oldest_url = self.access_order.pop(0)
            if oldest_url in self.memory_cache:
                del self.memory_cache[oldest_url]
                logger.debug(f"Evicted {oldest_url} from memory cache (LRU)")
    
    def get_stats(self) -> Dict[str, any]:
        """Get cache performance statistics."""
        if self.stats["total_requests"] > 0:
            hit_rate = ((self.stats["memory_hits"] + self.stats["redis_hits"] + self.stats["database_hits"]) 
                       / self.stats["total_requests"] * 100)
        else:
            hit_rate = 0
        
        return {
            **self.stats,
            "cache_hit_rate_percent": round(hit_rate, 2),
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_max": self.max_memory_entries
        }
    
    def clear_memory_cache(self) -> None:
        """Clear the memory cache (for testing or cleanup)."""
        self.memory_cache.clear()
        self.access_order.clear()
        logger.info("Memory cache cleared")
