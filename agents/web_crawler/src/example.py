import os
import asyncio
from loguru import logger
from crawler import WebCrawler, CrawlerSettings

async def main():
    # Configure logging
    logger.add(
        "crawler.log",
        rotation="500 MB",
        retention="10 days",
        level="INFO"
    )
    
    # Create crawler settings
    settings = CrawlerSettings(
        max_pages=int(os.getenv("CRAWLER_MAX_PAGES", "100")),
        max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "2")),
        timeout=int(os.getenv("CRAWLER_TIMEOUT", "30")),
        max_total_time=int(os.getenv("CRAWLER_MAX_TOTAL_TIME", "3600")),
        respect_robots=os.getenv("CRAWLER_RESPECT_ROBOTS", "true").lower() == "true",
        max_concurrent_pages=int(os.getenv("CRAWLER_MAX_CONCURRENT_PAGES", "5")),
        memory_threshold=float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0"))
    )
    
    # Log settings
    logger.info("Starting web crawler with settings:")
    logger.info(f"  - Max pages: {settings.max_pages}")
    logger.info(f"  - Max depth: {settings.max_depth}")
    logger.info(f"  - Timeout: {settings.timeout}")
    logger.info(f"  - Max total time: {settings.max_total_time}")
    logger.info(f"  - Respect robots.txt: {settings.respect_robots}")
    logger.info(f"  - Max concurrent pages: {settings.max_concurrent_pages}")
    logger.info(f"  - Memory threshold: {settings.memory_threshold}%")
    
    if not settings.respect_robots:
        logger.warning("WARNING: Robots.txt rules are being ignored. This may violate website terms of service.")
    
    # Initialize crawler
    crawler = WebCrawler(settings)
    
    # URLs to crawl
    urls = [
        "https://ai.pydantic.dev/api/",
        "https://ai.pydantic.dev/examples/",
        "https://ai.pydantic.dev/mcp/"
    ]
    
    try:
        # Start crawling
        await crawler.crawl_urls(urls)
        logger.info("Crawling completed successfully")
        logger.info("Content has been stored in the database")
        logger.info("You can query the content using the database methods:")
        logger.info("  - get_page(url) to retrieve a specific page")
        logger.info("  - search_pages(query) to search through the content")
        
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 