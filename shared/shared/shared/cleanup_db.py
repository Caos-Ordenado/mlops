#!/usr/bin/env python3
import os
import sys
from .logging import setup_logger
from typing import List
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Configure logger
logger.basicConfig(
    level=logger.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logger.getLogger(__name__)

def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            dbname=os.getenv('POSTGRES_DB')
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)

def get_tables(conn) -> List[str]:
    """Get all tables in the database."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        return [row[0] for row in cur.fetchall()]

def cleanse_database():
    """Main function to cleanse the database."""
    conn = None
    try:
        conn = get_db_connection()
        tables = get_tables(conn)
        
        logger.info(f"Found {len(tables)} tables to clean")
        
        with conn.cursor() as cur:
            # Disable foreign key checks temporarily
            cur.execute("SET session_replication_role = 'replica';")
            
            for table in tables:
                logger.info(f"Cleaning table: {table}")
                cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(
                    sql.Identifier(table)
                ))
            
            # Re-enable foreign key checks
            cur.execute("SET session_replication_role = 'origin';")
            
            conn.commit()
            logger.info("Database cleanup completed successfully")
            
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting database cleanup...")
    cleanse_database() 