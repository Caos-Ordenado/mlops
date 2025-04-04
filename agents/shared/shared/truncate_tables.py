#!/usr/bin/env python3
import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def truncate_tables():
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            dbname=os.getenv('POSTGRES_DB')
        )
        
        with conn.cursor() as cur:
            # Get all tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            # Truncate each table
            for table in tables:
                print(f"Truncating table: {table}")
                cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(
                    sql.Identifier(table)
                ))
            
            conn.commit()
            print("All tables truncated successfully")
            
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    truncate_tables() 