import os
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import Json
from loguru import logger
from typing import List, Dict, Any

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        self.reset_schema()  # Reset schema on initialization

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                dbname="web_crawler",
                user="admin",
                password=os.getenv("POSTGRES_PASSWORD", "admin"),
                host=os.getenv("POSTGRES_HOST", "home.server"),
                port=os.getenv("POSTGRES_PORT", "5432")
            )
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def reset_schema(self):
        """Drop and recreate the database schema."""
        try:
            with self.conn.cursor() as cur:
                # Drop existing table and indexes
                cur.execute("""
                    DROP TABLE IF EXISTS pages CASCADE
                """)
                self.conn.commit()
                logger.info("Existing schema dropped")
                
                # Create pages table
                cur.execute("""
                    CREATE TABLE pages (
                        id SERIAL PRIMARY KEY,
                        url TEXT UNIQUE NOT NULL,
                        title TEXT,
                        text_content TEXT,
                        links JSONB,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for faster URL lookups
                cur.execute("""
                    CREATE INDEX idx_pages_url ON pages(url)
                """)
                
                # Create index for text search
                cur.execute("""
                    CREATE INDEX idx_pages_text_content ON pages USING gin(to_tsvector('english', text_content))
                """)
                
                self.conn.commit()
                logger.info("Database schema recreated successfully")
        except Exception as e:
            logger.error(f"Error resetting schema: {str(e)}")
            self.conn.rollback()
            raise

    def setup_schema(self):
        """Set up the database schema if it doesn't exist."""
        try:
            with self.conn.cursor() as cur:
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'pages'
                    )
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    self.reset_schema()
                else:
                    logger.info("Database schema already exists")
        except Exception as e:
            logger.error(f"Error checking schema: {str(e)}")
            raise

    def store_page(self, url: str, title: str, text: str, links: List[str], metadata: Dict[str, Any]) -> None:
        """Store a crawled page in the database."""
        try:
            # Convert links list to JSON string
            links_json = json.dumps(links)
            metadata_json = json.dumps(metadata)

            # Insert the page data
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pages (url, title, text_content, links, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE
                    SET title = EXCLUDED.title,
                        text_content = EXCLUDED.text_content,
                        links = EXCLUDED.links,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (url, title, text, links_json, metadata_json)
                )
            self.conn.commit()
            logger.info(f"Stored page: {url}")
        except Exception as e:
            logger.error(f"Error storing page {url}: {str(e)}")
            self.conn.rollback()
            raise

    def get_page(self, url: str) -> dict:
        """Retrieve a page by URL"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT url, title, text_content, links, metadata, updated_at
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
                    "updated_at": row[5]
                }
            return None

    def search_pages(self, query: str, limit: int = 10) -> list:
        """Search pages by text content"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT url, title, text_content, links, metadata, updated_at
                FROM pages
                WHERE to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
                ORDER BY updated_at DESC
                LIMIT %s
            """, (query, limit))
            return [{
                "url": row[0],
                "title": row[1],
                "text_content": row[2],
                "links": row[3],
                "metadata": row[4],
                "updated_at": row[5]
            } for row in cur.fetchall()]

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed") 