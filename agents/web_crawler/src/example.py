import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
from core.crawler import WebCrawlerAgent
from core.models import CrawlerSettings

# Load environment variables
load_dotenv()

async def main():
    # Configure logging
    logger.add(
        "server.log",
        rotation="500 MB",
        retention="10 days",
        level=os.getenv("CRAWLER_LOG_LEVEL", "DEBUG"),
        enqueue=True  # Thread-safe logging
    )
    
    # Log environment variables
    logger.info("Environment variables:")
    # Redis variables
    logger.info(f"REDIS_HOST: {os.getenv('REDIS_HOST', 'not set')}")
    logger.info(f"REDIS_PORT: {os.getenv('REDIS_PORT', 'not set')}")
    logger.info(f"REDIS_PASSWORD: {'set' if os.getenv('REDIS_PASSWORD') else 'not set'}")
    logger.info(f"REDIS_DB: {os.getenv('REDIS_DB', 'not set')}")
    
    # PostgreSQL variables
    logger.info(f"POSTGRES_HOST: {os.getenv('POSTGRES_HOST', 'not set')}")
    logger.info(f"POSTGRES_PORT: {os.getenv('POSTGRES_PORT', 'not set')}")
    logger.info(f"POSTGRES_DB: {os.getenv('POSTGRES_DB', 'not set')}")
    logger.info(f"POSTGRES_USER: {os.getenv('POSTGRES_USER', 'not set')}")
    logger.info(f"POSTGRES_PASSWORD: {'set' if os.getenv('POSTGRES_PASSWORD') else 'not set'}")
    
    # Crawler settings
    logger.info(f"CRAWLER_STORAGE_REDIS: {os.getenv('CRAWLER_STORAGE_REDIS', 'not set')}")
    logger.info(f"CRAWLER_STORAGE_POSTGRES: {os.getenv('CRAWLER_STORAGE_POSTGRES', 'not set')}")
    logger.info(f"CRAWLER_MAX_PAGES: {os.getenv('CRAWLER_MAX_PAGES', 'not set')}")
    logger.info(f"CRAWLER_MAX_DEPTH: {os.getenv('CRAWLER_MAX_DEPTH', 'not set')}")
    logger.info(f"CRAWLER_TIMEOUT: {os.getenv('CRAWLER_TIMEOUT', 'not set')}")
    logger.info(f"CRAWLER_MAX_TOTAL_TIME: {os.getenv('CRAWLER_MAX_TOTAL_TIME', 'not set')}")
    logger.info(f"CRAWLER_MAX_CONCURRENT_PAGES: {os.getenv('CRAWLER_MAX_CONCURRENT_PAGES', 'not set')}")
    logger.info(f"CRAWLER_MEMORY_THRESHOLD: {os.getenv('CRAWLER_MEMORY_THRESHOLD', 'not set')}")
    
    # Initialize crawler settings
    settings = CrawlerSettings(
        max_pages=int(os.getenv("CRAWLER_MAX_PAGES", "10000")),
        max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "20")),
        respect_robots=os.getenv("CRAWLER_RESPECT_ROBOTS", "false").lower() == "true",
        timeout=int(os.getenv("CRAWLER_TIMEOUT", "180000")),
        max_total_time=int(os.getenv("CRAWLER_MAX_TOTAL_TIME", "300")),
        max_concurrent_pages=int(os.getenv("CRAWLER_MAX_CONCURRENT_PAGES", "10")),
        memory_threshold=float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0")),
        storage_redis=os.getenv("CRAWLER_STORAGE_REDIS", "True")
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
            
            # Print some stats about the results
            for result in results:
                logger.info(f"Crawled: {result['url']}")
                logger.info(f"  Title: {result['title']}")
                logger.info(f"  Found {len(result['links'])} links")
                logger.info("  Metadata:")
                for key, value in result['metadata'].items():
                    if key != 'headers':  # Skip headers to keep output clean
                        logger.info(f"    {key}: {value}")
                logger.info("-" * 80)
            
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(main()) 