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

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

from shared import DatabaseContext, DatabaseConfig

async def init_database():
    """Initialize the database and create tables."""
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
    
    print("Initializing database...")
    async with DatabaseContext(config=config) as db:
        # Install pgvector extension
        print("Installing pgvector extension...")
        async with db.db.engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("pgvector extension installed successfully!")
        
        # Create tables
        print("Creating database tables...")
        await db.db.create_tables()
        print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_database()) 