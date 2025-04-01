import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import redis
import psycopg2
from psycopg2.extras import Json
from loguru import logger
from .config import settings

class PriceStorage:
    """Storage manager for price comparison data."""
    
    def __init__(self):
        self.redis = None
        self.pg_conn = None
        self.prefix = settings.REDIS_PREFIX
    
    async def initialize(self):
        """Initialize connections to Redis and PostgreSQL."""
        try:
            # Initialize Redis connection
            redis_config = {
                'host': settings.REDIS_HOST,
                'port': settings.REDIS_PORT,
                'db': settings.REDIS_DB,
                'decode_responses': True
            }
            # Only add password if it's not empty
            if settings.REDIS_PASSWORD:
                redis_config['password'] = settings.REDIS_PASSWORD
            
            self.redis = redis.Redis(**redis_config)
            logger.info("Successfully connected to Redis")
            
            # Initialize PostgreSQL connection
            logger.info(f"Connecting to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            self.pg_conn = psycopg2.connect(
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT
            )
            await self.setup_schema()
            logger.info("Successfully connected to PostgreSQL")
            
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            raise
    
    async def setup_schema(self):
        """Set up the necessary database schema for price tracking."""
        try:
            with self.pg_conn.cursor() as cur:
                # Create products table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        raw_name TEXT NOT NULL,
                        normalized_name TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(normalized_name)
                    )
                """)
                
                # Create prices table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prices (
                        id SERIAL PRIMARY KEY,
                        product_id INTEGER REFERENCES products(id),
                        store TEXT NOT NULL,
                        price DECIMAL(10,2) NOT NULL,
                        url TEXT,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id, store, created_at)
                    )
                """)
                
                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_products_normalized_name 
                    ON products(normalized_name)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_prices_product_id 
                    ON prices(product_id)
                """)
                
                self.pg_conn.commit()
                logger.info("Database schema setup complete")
        except Exception as e:
            logger.error(f"Error setting up schema: {e}")
            self.pg_conn.rollback()
            raise
    
    async def store_product_price(
        self, 
        raw_name: str, 
        normalized_name: str,
        store: str,
        price: float,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a product price in both Redis and PostgreSQL."""
        try:
            # Store in PostgreSQL
            with self.pg_conn.cursor() as cur:
                # Insert or get product
                cur.execute("""
                    INSERT INTO products (raw_name, normalized_name)
                    VALUES (%s, %s)
                    ON CONFLICT (normalized_name)
                    DO UPDATE SET raw_name = EXCLUDED.raw_name
                    RETURNING id
                """, (raw_name, normalized_name))
                product_id = cur.fetchone()[0]
                
                # Insert price
                cur.execute("""
                    INSERT INTO prices (product_id, store, price, url, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product_id, store, price, url, Json(metadata) if metadata else None))
                
                self.pg_conn.commit()
            
            # Store latest price in Redis for quick access
            redis_key = f"{self.prefix}latest:{normalized_name}:{store}"
            price_data = {
                "price": price,
                "url": url,
                "metadata": metadata,
                "updated_at": datetime.now().isoformat()
            }
            self.redis.set(redis_key, json.dumps(price_data), ex=3600 * 24)  # 24h expiry
            
            logger.info(f"Stored price for {normalized_name} at {store}: {price}")
            
        except Exception as e:
            logger.error(f"Error storing price: {e}")
            self.pg_conn.rollback()
            raise
    
    async def get_latest_prices(self, normalized_name: str) -> Dict[str, Dict[str, Any]]:
        """Get latest prices for a product across all stores."""
        prices = {}
        
        # Try Redis first for latest prices
        for key in self.redis.keys(f"{self.prefix}latest:{normalized_name}:*"):
            store = key.split(":")[-1]
            data = self.redis.get(key)
            if data:
                prices[store] = json.loads(data)
        
        # If not all stores found in Redis, query PostgreSQL
        if not prices:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (store)
                        store, price, url, metadata, created_at
                    FROM prices p
                    JOIN products prod ON p.product_id = prod.id
                    WHERE prod.normalized_name = %s
                    ORDER BY store, created_at DESC
                """, (normalized_name,))
                
                for row in cur.fetchall():
                    store, price, url, metadata, created_at = row
                    prices[store] = {
                        "price": float(price),
                        "url": url,
                        "metadata": metadata,
                        "updated_at": created_at.isoformat()
                    }
        
        return prices
    
    async def get_price_history(
        self, 
        normalized_name: str,
        store: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a product."""
        with self.pg_conn.cursor() as cur:
            query = """
                SELECT 
                    p.store,
                    p.price,
                    p.url,
                    p.metadata,
                    p.created_at
                FROM prices p
                JOIN products prod ON p.product_id = prod.id
                WHERE prod.normalized_name = %s
            """
            params = [normalized_name]
            
            if store:
                query += " AND p.store = %s"
                params.append(store)
            
            query += " ORDER BY p.created_at DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            
            return [{
                "store": row[0],
                "price": float(row[1]),
                "url": row[2],
                "metadata": row[3],
                "date": row[4].isoformat()
            } for row in cur.fetchall()]
    
    async def close(self):
        """Close all connections."""
        if self.redis:
            self.redis.close()
        if self.pg_conn:
            self.pg_conn.close()
        logger.info("Storage connections closed") 