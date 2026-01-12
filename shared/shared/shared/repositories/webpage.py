"""
Repository for WebPage model.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, text, insert
from sqlalchemy.ext.asyncio import AsyncSession
import json
from ..logging import setup_logger

from ..models.webpage import WebPage
from .base import BaseRepository

logger = setup_logger(__name__)

class WebPageRepository(BaseRepository):
    """Repository for web pages with Redis caching."""
    
    def _get_prefix(self) -> str:
        """Get Redis key prefix for WebPage entities."""
        return "webpage"

    def _get_entity_key(self, webpage: WebPage) -> str:
        """Get unique key for webpage."""
        return webpage.url

    def _to_redis_data(self, webpage: WebPage) -> dict:
        """Convert webpage to Redis data."""
        return webpage.to_redis_data()

    def _from_redis_data(self, data: dict) -> WebPage:
        """Create webpage from Redis data."""
        return WebPage.from_redis_data(data)

    async def save(self, webpage: WebPage) -> None:
        """Save webpage to PostgreSQL and invalidate Redis cache."""
        try:
            # Save to PostgreSQL
            async with self.db.get_session() as session:
                # Use merge to handle both insert and update cases
                await session.merge(webpage)
                await session.commit()

            # Invalidate Redis cache if available
            if self.redis:
                try:
                    redis_key = f"{self._get_prefix()}:{webpage.url}"
                    await self.redis.delete(redis_key)
                except Exception as e:
                    logger.warning(f"Redis cache invalidation failed for URL {webpage.url}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to save WebPage: {str(e)}")
            raise
    
    async def get_by_url(self, session: AsyncSession, url: str) -> Optional[WebPage]:
        """Get a webpage by URL with Redis caching."""
        # Try Redis first if available
        if self.redis:
            try:
                redis_key = f"{self._get_prefix()}:{url}"
                cached_data = await self.redis.get(redis_key)
                if cached_data:
                    return self._from_redis_data(json.loads(cached_data))
            except Exception as e:
                logger.warning(f"Redis fetch failed for URL {url}: {str(e)}")
        
        # Get from PostgreSQL
        stmt = select(WebPage).where(WebPage.url == url)
        result = await session.execute(stmt)
        webpage = result.scalar_one_or_none()
        
        # Cache in Redis if found
        if webpage and self.redis:
            try:
                redis_key = f"{self._get_prefix()}:{url}"
                await self.redis.set(
                    redis_key,
                    json.dumps(self._to_redis_data(webpage)),
                    ex=3600  # 1 hour cache
                )
            except Exception as e:
                logger.warning(f"Redis cache update failed for URL {url}: {str(e)}")
        
        return webpage
    
    async def get_recent_pages(self, session: AsyncSession, limit: int = 10) -> List[WebPage]:
        """Get recently crawled pages (no caching for lists)."""
        stmt = select(WebPage).order_by(WebPage.crawled_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_pages_by_domain(self, session: AsyncSession, domain: str) -> List[WebPage]:
        """Get all pages from a specific domain (no caching for lists)."""
        stmt = select(WebPage).where(WebPage.url.like(f"%{domain}%"))
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def search_pages(self, session: AsyncSession, query: str, limit: int = 10) -> List[WebPage]:
        """Search pages using full-text search (no caching for search results)."""
        stmt = select(WebPage).where(
            WebPage.search_vector.match(query)
        ).order_by(
            func.ts_rank_cd(WebPage.search_vector, func.plainto_tsquery('english', query)).desc()
        ).limit(limit)
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def semantic_search(self, session: AsyncSession, query_embedding: List[float], limit: int = 10) -> List[WebPage]:
        """Search pages using vector similarity (no caching for search results)."""
        stmt = select(WebPage).order_by(
            func.cosine_similarity(WebPage.embedding, query_embedding).desc()
        ).limit(limit)
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_rag_context(self, session: AsyncSession, urls: List[str]) -> List[Dict[str, Any]]:
        """Get RAG context for multiple URLs (using cache for individual pages)."""
        pages = []
        for url in urls:
            page = await self.get_by_url(session, url)
            if page:
                pages.append(page)
        return [page.to_rag_context() for page in pages]
    
    async def cleanup_old_pages(self, session: AsyncSession, days: int = 30) -> int:
        """Delete pages older than specified days and their cache entries."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            stmt = select(WebPage).where(WebPage.crawled_at < cutoff_date)
            result = await session.execute(stmt)
            old_pages = result.scalars().all()
            
            for page in old_pages:
                await session.delete(page)
                # Clean Redis cache if available
                if self.redis:
                    try:
                        redis_key = f"{self._get_prefix()}:{page.url}"
                        await self.redis.delete(redis_key)
                    except Exception as e:
                        logger.warning(f"Redis cache cleanup failed for URL {page.url}: {str(e)}")
            
            await session.commit()
            return len(old_pages)
            
        except Exception as e:
            logger.error(f"Error during cleanup of old pages: {str(e)}")
            await session.rollback()
            return 0
    
    async def iterate_all_pages(self, session: AsyncSession, batch_size: int = 100):
        """Iterate through all pages in batches (no caching for batches)."""
        offset = 0
        while True:
            stmt = select(WebPage).order_by(WebPage.url).limit(batch_size).offset(offset)
            result = await session.execute(stmt)
            batch = list(result.scalars().all())
            if not batch:
                break
            yield batch
            offset += batch_size
    
    async def truncate(self, session: AsyncSession) -> None:
        """Truncate the webpage table and clear all Redis cache entries."""
        try:
            # Truncate PostgreSQL table
            await session.execute(text("TRUNCATE TABLE webpage"))
            await session.commit()
            
            # Clear Redis cache if available
            if self.redis:
                try:
                    # Delete all keys with our prefix
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis.scan(
                            cursor,
                            match=f"{self._get_prefix()}:*",
                            count=100
                        )
                        if keys:
                            await self.redis.delete(*keys)
                        if cursor == 0:
                            break
                except Exception as e:
                    logger.warning(f"Redis cache clear failed: {str(e)}")
            
            logger.debug("Truncated webpage table and cleared cache")
        except Exception as e:
            logger.error(f"Failed to truncate webpage table: {str(e)}")
            raise 