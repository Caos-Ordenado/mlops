import os
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import Json
from loguru import logger

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        self.setup_schema()

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                dbname="web_crawler",
                user="admin",
                password=os.getenv("POSTGRES_PASSWORD", "admin"),
                host=os.getenv("POSTGRES_HOST", "postgres.shared.svc.cluster.local"),
                port=os.getenv("POSTGRES_PORT", "5432")
            )
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def setup_schema(self):
        """Create necessary tables if they don't exist"""
        with self.conn.cursor() as cur:
            # Create pages table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    text_content TEXT,
                    links JSONB,
                    metadata JSONB,
                    crawled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster URL lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url)
            """)
            
            # Create index for text search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pages_text_content ON pages USING gin(to_tsvector('english', text_content))
            """)
            
            self.conn.commit()
            logger.info("Database schema setup completed")

    def store_page(self, url: str, title: str, text: str, links: list, metadata: dict):
        """Store a crawled page in the database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pages (url, title, text_content, links, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        text_content = EXCLUDED.text_content,
                        links = EXCLUDED.links,
                        metadata = EXCLUDED.metadata,
                        crawled_at = CURRENT_TIMESTAMP
                """, (url, title, text, Json(links), Json(metadata)))
                self.conn.commit()
                logger.info(f"Successfully stored page: {url}")
        except Exception as e:
            logger.error(f"Failed to store page {url}: {e}")
            self.conn.rollback()
            raise

    def get_page(self, url: str) -> dict:
        """Retrieve a page by URL"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT url, title, text_content, links, metadata, crawled_at
                FROM pages
                WHERE url = %s
            """, (url,))
            row = cur.fetchone()
            if row:
                return {
                    "url": row[0],
                    "title": row[1],
                    "text_content": row[2],
                    "links": row[3],
                    "metadata": row[4],
                    "crawled_at": row[5]
                }
            return None

    def search_pages(self, query: str, limit: int = 10) -> list:
        """Search pages by text content"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT url, title, text_content, links, metadata, crawled_at
                FROM pages
                WHERE to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
                ORDER BY crawled_at DESC
                LIMIT %s
            """, (query, limit))
            return [{
                "url": row[0],
                "title": row[1],
                "text_content": row[2],
                "links": row[3],
                "metadata": row[4],
                "crawled_at": row[5]
            } for row in cur.fetchall()]

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed") 