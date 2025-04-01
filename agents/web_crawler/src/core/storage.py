"""
Storage backends for the web crawler.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
import redis
import psycopg2
from psycopg2.extras import Json
from loguru import logger

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

class RedisStorage(StorageBackend):
    """Redis storage backend."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """Initialize Redis connection."""
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.prefix = "crawler:"
        logger.info(f"Initialized Redis storage at {host}:{port}")
    
    async def store_result(self, url: str, data: Dict[str, Any]) -> bool:
        """Store crawl result in Redis."""
        try:
            key = f"{self.prefix}{url}"
            self.redis.set(key, json.dumps(data))
            logger.debug(f"Stored result for {url} in Redis")
            return True
        except Exception as e:
            logger.error(f"Error storing result in Redis: {e}")
            return False
    
    async def get_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve crawl result from Redis."""
        try:
            key = f"{self.prefix}{url}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving result from Redis: {e}")
            return None
    
    async def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieve all crawl results from Redis."""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            results = []
            for key in keys:
                data = self.redis.get(key)
                if data:
                    results.append(json.loads(data))
            return results
        except Exception as e:
            logger.error(f"Error retrieving all results from Redis: {e}")
            return []
    
    async def clear_results(self) -> bool:
        """Clear all stored results from Redis."""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            if keys:
                self.redis.delete(*keys)
            logger.info("Cleared all results from Redis")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from Redis: {e}")
            return False

class PostgresStorage(StorageBackend):
    """PostgreSQL storage backend."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "web_crawler",
        user: str = "postgres",
        password: str = None
    ):
        """Initialize PostgreSQL connection."""
        self.conn_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password
        }
        self._init_db()
        logger.info(f"Initialized PostgreSQL storage at {host}:{port}/{dbname}")
    
    def _init_db(self):
        """Initialize database schema."""
        with psycopg2.connect(**self.conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS crawl_results (
                        url TEXT PRIMARY KEY,
                        data JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
    
    async def store_result(self, url: str, data: Dict[str, Any]) -> bool:
        """Store crawl result in PostgreSQL."""
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO crawl_results (url, data)
                        VALUES (%s, %s)
                        ON CONFLICT (url) DO UPDATE
                        SET data = %s, updated_at = CURRENT_TIMESTAMP
                    """, (url, Json(data), Json(data)))
                    conn.commit()
            logger.debug(f"Stored result for {url} in PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Error storing result in PostgreSQL: {e}")
            return False
    
    async def get_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve crawl result from PostgreSQL."""
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM crawl_results WHERE url = %s", (url,))
                    result = cur.fetchone()
                    if result:
                        return result[0]
            return None
        except Exception as e:
            logger.error(f"Error retrieving result from PostgreSQL: {e}")
            return None
    
    async def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieve all crawl results from PostgreSQL."""
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM crawl_results")
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving all results from PostgreSQL: {e}")
            return []
    
    async def clear_results(self) -> bool:
        """Clear all stored results from PostgreSQL."""
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE crawl_results")
                    conn.commit()
            logger.info("Cleared all results from PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from PostgreSQL: {e}")
            return False 