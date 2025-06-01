#!/usr/bin/env python3
"""
Database initialization and migration script.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

from shared import DatabaseContext, DatabaseConfig

async def create_databases(config: DatabaseConfig):
    """Create the required databases if they don't exist."""
    print("Creating databases if they don't exist...")
    conn = psycopg2.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        dbname="postgres",
        user=config.postgres_user,
        password=config.postgres_password,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Create web_crawler database
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'web_crawler'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE web_crawler")
        print("Created 'web_crawler' database")
    else:
        print("Database 'web_crawler' already exists")

    # Create langflow database
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'langflow'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE langflow")
        print("Created 'langflow' database")
    else:
        print("Database 'langflow' already exists")

    cur.close()
    conn.close()

async def init_database():
    """Initialize the database (ensure databases exist)."""
    # Create database config
    config = DatabaseConfig(
        postgres_host=os.getenv("POSTGRES_HOST", "postgres.shared.svc.cluster.local"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "web_crawler"),
        postgres_user=os.getenv("POSTGRES_USER", "admin"),
        postgres_password=os.getenv("POSTGRES_PASSWORD"),
        redis_host=os.getenv("REDIS_HOST", "redis.shared.svc.cluster.local"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        redis_password=os.getenv("REDIS_PASSWORD"),
        echo_sql=True
    )
    
    # First, create the databases if they don't exist
    await create_databases(config)
    
    print("Database existence check complete. Further schema setup should be handled by Alembic migrations.")
    # Commenting out or removing parts now handled by Alembic:
    # print("Initializing web_crawler database...")
    # async with DatabaseContext(config=config) as db:
    #     # Install pgvector extension
    #     print("Installing pgvector extension...") # This is now in Alembic initial migration
    #     async with db.db.engine.begin() as conn:
    #         await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    #     print("pgvector extension installed successfully!")
        
    #     # Create tables for web_crawler
    #     print("Creating web_crawler database tables...") # This should be done by Alembic
    #     await db.db.create_tables()
    #     print("Web_crawler database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_database()) 