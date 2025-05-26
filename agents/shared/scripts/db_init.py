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

async def create_databases(config: DatabaseConfig):
    """Create the required databases if they don't exist."""
    # Create a temporary config for connecting to the default postgres database
    temp_config = DatabaseConfig(
        postgres_host=config.postgres_host,
        postgres_port=config.postgres_port,
        postgres_db="postgres",  # Connect to default postgres database
        postgres_user=config.postgres_user,
        postgres_password=config.postgres_password,
        redis_host=config.redis_host,
        redis_port=config.redis_port,
        redis_db=config.redis_db,
        redis_password=config.redis_password,
        echo_sql=True
    )
    
    print("Creating databases if they don't exist...")
    async with DatabaseContext(config=temp_config) as db:
        async with db.db.engine.begin() as conn:
            # Create web_crawler database
            result = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'web_crawler'"))
            if not result.fetchone():
                await conn.execute(text("CREATE DATABASE web_crawler"))
                print("Created 'web_crawler' database")
            else:
                print("Database 'web_crawler' already exists")
            
            # Create langflow database
            result = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'langflow'"))
            if not result.fetchone():
                await conn.execute(text("CREATE DATABASE langflow"))
                print("Created 'langflow' database")
            else:
                print("Database 'langflow' already exists")

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
    
    # First, create the databases
    await create_databases(config)
    
    print("Initializing web_crawler database...")
    async with DatabaseContext(config=config) as db:
        # Install pgvector extension
        print("Installing pgvector extension...")
        async with db.db.engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("pgvector extension installed successfully!")
        
        # Create tables for web_crawler
        print("Creating web_crawler database tables...")
        await db.db.create_tables()
        print("Web_crawler database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_database()) 