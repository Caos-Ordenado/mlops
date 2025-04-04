"""
Storage backends for the web crawler.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
from logging import setup_logger
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from redis_client import RedisClient

# Initialize logger
logger = setup_logger("web_crawler.storage")

class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def store_result(self, url: str, data: Dict[str, Any]) -> bool:
        """Store crawl result for a URL."""
        pass
    
    @abstractmethod
    async def get_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve crawl result for a URL."""
        pass
    
    @abstractmethod
    async def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieve all crawl results."""
        pass
    
    @abstractmethod
    async def clear_results(self) -> bool:
        """Clear all stored results."""
        pass

    @abstractmethod
    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up data older than specified days."""
        pass

    @abstractmethod
    async def close(self):
        """Close the storage connection."""
        pass

class RedisStorage(StorageBackend):
    """Redis storage backend."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: str = None):
        """Initialize Redis connection."""
        self.redis = None
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = "crawler:"
        logger.debug(f"Initialized Redis storage at {host}:{port}")
    
    async def _ensure_redis(self):
        """Ensure Redis client is initialized."""
        if not self.redis:
            try:
                self.redis = RedisClient(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password
                )
                await self.redis.__aenter__()
            except Exception as e:
                logger.error(f"Failed to initialize Redis connection: {e}")
                raise
    
    async def store_result(self, url: str, data: Dict[str, Any]) -> bool:
        """Store crawl result in Redis."""
        try:
            await self._ensure_redis()
            key = f"{self.prefix}{url}"
            await self.redis.set(key, json.dumps(data), ex=3600)  # 1 hour expiration
            logger.debug(f"Stored result for {url} in Redis")
            return True
        except Exception as e:
            logger.error(f"Error storing result in Redis: {e}")
            return False
    
    async def get_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve crawl result from Redis."""
        try:
            await self._ensure_redis()
            key = f"{self.prefix}{url}"
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving result from Redis: {e}")
            return None
    
    async def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieve all crawl results from Redis."""
        try:
            await self._ensure_redis()
            keys = await self.redis.keys(f"{self.prefix}*")
            results = []
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    results.append(json.loads(data))
            return results
        except Exception as e:
            logger.error(f"Error retrieving all results from Redis: {e}")
            return []
    
    async def clear_results(self) -> bool:
        """Clear all stored results from Redis."""
        try:
            await self._ensure_redis()
            keys = await self.redis.keys(f"{self.prefix}*")
            if keys:
                await self.redis.delete(*keys)
            logger.debug("Cleared all results from Redis")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from Redis: {e}")
            return False

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                await self.redis.__aexit__(None, None, None)
                self.redis = None
                logger.debug("Closed Redis connection")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up data older than specified days."""
        # Redis data has expiration time, no need for manual cleanup
        return True

class PostgresStorage(StorageBackend):
    """PostgreSQL storage backend using the shared ORM."""
    
    def __init__(
        self,
        host: str = "home.server",
        port: int = 5432,
        dbname: str = "web_crawler",
        user: str = "admin",
        password: str = None
    ):
        """Initialize PostgreSQL connection."""
        self.config = DatabaseConfig(
            postgres_host=host,
            postgres_port=port,
            postgres_db=dbname,
            postgres_user=user,
            postgres_password=password
        )
        self.db = None
        self.webpage_repo = WebPageRepository(WebPage)
        logger.debug(f"Initialized PostgreSQL storage at {host}:{port}/{dbname}")
    
    async def _get_db(self) -> DatabaseContext:
        """Get database context."""
        if not self.db:
            self.db = DatabaseContext(config=self.config)
            await self.db.__aenter__()
        return self.db
    
    async def store_result(self, url: str, data: Dict[str, Any]) -> bool:
        """Store crawl result in PostgreSQL."""
        try:
            db = await self._get_db()
            webpage = WebPage.from_crawl_result(
                url=url,
                title=data.get("title"),
                text=data.get("text", ""),
                links=data.get("links", []),
                metadata=data.get("metadata", {})
            )
            async with db.db.get_session() as session:
                await self.webpage_repo.save(session, webpage)
                await session.commit()
            logger.debug(f"Stored/updated result for {url} in PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Error storing result in PostgreSQL: {e}")
            return False
    
    async def get_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve crawl result from PostgreSQL."""
        try:
            db = await self._get_db()
            async with db.db.get_session() as session:
                webpage = await self.webpage_repo.get_by_url(session, url)
                if webpage:
                    return webpage.to_redis_data()
            return None
        except Exception as e:
            logger.error(f"Error retrieving result from PostgreSQL: {e}")
            return None
    
    async def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieve all crawl results from PostgreSQL."""
        try:
            db = await self._get_db()
            results = []
            async with db.db.get_session() as session:
                async for batch in self.webpage_repo.iterate_all_pages(session, batch_size=100):
                    for webpage in batch:
                        results.append(webpage.to_redis_data())
            return results
        except Exception as e:
            logger.error(f"Error retrieving all results from PostgreSQL: {e}")
            return []
    
    async def clear_results(self) -> bool:
        """Clear all stored results from PostgreSQL."""
        try:
            db = await self._get_db()
            async with db.db.get_session() as session:
                await self.webpage_repo.truncate(session)
            logger.debug("Cleared all results from PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from PostgreSQL: {e}")
            return False
    
    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up data older than specified days."""
        try:
            db = await self._get_db()
            async with db.db.get_session() as session:
                count = await self.webpage_repo.cleanup_old_pages(session, days)
                logger.info(f"Cleaned up {count} old pages from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Error cleaning up old data from PostgreSQL: {e}")
            return False
    
    async def close(self):
        """Close PostgreSQL connection."""
        if self.db:
            await self.db.__aexit__(None, None, None)
            self.db = None
            self.webpage_repo = None
            logger.debug("Closed PostgreSQL connection") 