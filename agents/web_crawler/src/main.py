"""
Main entry point for the web crawler application.
Can run either the example crawler or the FastAPI server.
"""

import os
import sys
from shared.logging import log_database_config, setup_logger

# Initialize logger first
logger = setup_logger("web_crawler")

# Now import other modules
from dotenv import load_dotenv

from .api import app

# Load environment variables
load_dotenv(override=True)

# Log database configuration
log_database_config(logger)

# Import asyncio after logger setup
import asyncio

async def run_example():
    """Run the example crawler."""
    from core import WebCrawlerAgent, CrawlerSettings
    
    # Initialize crawler settings
    settings = CrawlerSettings(
        max_pages=int(os.getenv("CRAWLER_MAX_PAGES", "10")),
        max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "2")),
        respect_robots=os.getenv("CRAWLER_RESPECT_ROBOTS", "true").lower() == "true",
        timeout=int(os.getenv("CRAWLER_TIMEOUT", "180000")),
        max_total_time=int(os.getenv("CRAWLER_MAX_TOTAL_TIME", "60")),
        max_concurrent_pages=int(os.getenv("CRAWLER_MAX_CONCURRENT_PAGES", "5")),
        memory_threshold=float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0"))
    )
    
    # URLs to crawl
    urls = [
        "https://ai.pydantic.dev/api/",
        "https://ai.pydantic.dev/mcp/",
        "https://ai.pydantic.dev/examples/"
    ]
    
    # Initialize and run crawler
    async with WebCrawlerAgent(settings) as crawler:
        logger.info("Starting web crawler...")
        logger.info(f"Settings: {settings.model_dump()}")
        
        try:
            results = await crawler.crawl_urls(urls)
            logger.info(f"Successfully crawled {len(results)} pages")
            
            # Print results summary
            for url, result in zip(urls, results):
                logger.info(f"\nResults for {url}:")
                logger.info(f"Title: {result.get('title', 'N/A')}")
                logger.info(f"Links found: {len(result.get('links', []))}")
                logger.info(f"Content length: {len(result.get('text', ''))}")
            
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            raise

def run_server():
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # Check run mode
    if len(sys.argv) > 1 and sys.argv[1] == "example":
        logger.info("Running example crawler...")
        asyncio.run(run_example())
    else:
        logger.info("Starting FastAPI server...")
        run_server() 