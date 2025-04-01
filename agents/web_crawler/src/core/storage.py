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
from datetime import datetime, timedelta

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
        try:
            # Always try with password first if provided
            if password:
                self.redis = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True
                )
            else:
                self.redis = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=True
                )
            # Test the connection
            self.redis.ping()
            
            self.prefix = "crawler:"
            logger.debug(f"Initialized Redis storage at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
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
            logger.debug("Cleared all results from Redis")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from Redis: {e}")
            return False

    async def close(self):
        """Close Redis connection."""
        try:
            self.redis.close()
            logger.debug("Closed Redis connection")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")

    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up data older than specified days."""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            current_time = datetime.now()
            deleted_count = 0
            invalid_count = 0
            total_keys = len(keys)
            
            logger.debug(f"Redis cleanup: checking {total_keys} keys for data older than {days} days")
            
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if not data:  # Handle empty data
                        self.redis.delete(key)
                        invalid_count += 1
                        continue
                        
                    parsed_data = json.loads(data)
                    timestamp = parsed_data.get("metadata", {}).get("timestamp")
                    if timestamp:
                        stored_time = datetime.fromtimestamp(timestamp)
                        if current_time - stored_time > timedelta(days=days):
                            self.redis.delete(key)
                            deleted_count += 1
                    else:  # No timestamp found, treat as invalid
                        self.redis.delete(key)
                        invalid_count += 1
                except json.JSONDecodeError:
                    # Invalid JSON data, delete the key
                    self.redis.delete(key)
                    invalid_count += 1
                    logger.debug(f"Deleted invalid JSON data for key {key}")
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error processing data for key {key}: {e}")
                    continue
            
            logger.info(f"Redis cleanup complete: {deleted_count} old entries and {invalid_count} invalid entries removed out of {total_keys} total keys")
            return True
        except Exception as e:
            logger.error(f"Error during Redis cleanup: {e}")
            return False

class PostgresStorage(StorageBackend):
    """PostgreSQL storage backend."""
    
    def __init__(
        self,
        host: str = "localhost",  # Default to home server
        port: int = 5432,
        dbname: str = "web_crawler",
        user: str = "admin",  # Default to admin user
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
        logger.debug(f"Initialized PostgreSQL storage at {host}:{port}/{dbname}")
    
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
            logger.debug("Cleared all results from PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Error clearing results from PostgreSQL: {e}")
            return False

    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up data older than specified days."""
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    # First count total rows
                    cur.execute("SELECT COUNT(*) FROM crawl_results")
                    total_rows = cur.fetchone()[0]
                    
                    # Then count how many rows will be deleted
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM crawl_results
                        WHERE updated_at < NOW() - INTERVAL '%s days'
                    """, (days,))
                    to_delete = cur.fetchone()[0]
                    
                    logger.debug(f"PostgreSQL cleanup: checking {total_rows} rows for data older than {days} days")
                    
                    # Then perform the deletion
                    cur.execute("""
                        DELETE FROM crawl_results
                        WHERE updated_at < NOW() - INTERVAL '%s days'
                    """, (days,))
                    conn.commit()
            
            logger.info(f"PostgreSQL cleanup complete: {to_delete} old entries removed out of {total_rows} total rows")
            return True
        except Exception as e:
            logger.error(f"Error during PostgreSQL cleanup: {e}")
            return False

    async def close(self):
        """Close PostgreSQL connection."""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                logger.debug("Closed PostgreSQL connection")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connection: {e}") 