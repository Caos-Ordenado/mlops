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
        "crawler.log",
        rotation="500 MB",
        retention="10 days",
        level=os.getenv("CRAWLER_LOG_LEVEL", "DEBUG"),
        enqueue=True  # Thread-safe logging
    )
    
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
            
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(main()) 