from typing import List, Optional, Dict, Any
from shared.logging import setup_logger
# Import the shared client and its response model
from shared.web_crawler_client import WebCrawlerClient, CrawlResponse 

logger = setup_logger("product_search_agent.web_crawler_trigger_service")

class WebCrawlerTriggerService:
    def __init__(self):
        logger.info("WebCrawlerTriggerService initialized.")

    async def trigger_crawls(
        self,
        urls_to_crawl: List[str],
        max_pages: Optional[int] = 1, 
        max_depth: Optional[int] = 1, 
        allowed_domains: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        respect_robots: Optional[bool] = False, 
        max_total_time: Optional[int] = 60
    ) -> bool:
        """
        Triggers the web crawler for a list of URLs using the shared WebCrawlerClient.
        The primary goal is to get the data into backend storage (Redis/Postgres)
        via the web_crawler_service's own saving mechanism.

        Returns:
            bool: True if the crawl task was successfully triggered and the service
                  reported no errors, False otherwise.
        """
        if not urls_to_crawl:
            logger.warning("No URLs provided to trigger crawl.")
            return False

        logger.info(f"Triggering crawl for {len(urls_to_crawl)} URLs: {urls_to_crawl[:3]}... via shared WebCrawlerClient")

        try:
            async with WebCrawlerClient() as client:
                # Perform a health check first (optional, but good practice)
                if not await client.health_check():
                    logger.error("Web crawler service health check failed. Aborting crawl trigger.")
                    return False
                logger.debug("Web crawler service is healthy. Proceeding with crawl trigger.")

                response: CrawlResponse = await client.crawl(
                    urls=urls_to_crawl,
                    max_pages=max_pages,
                    max_depth=max_depth,
                    allowed_domains=allowed_domains,
                    exclude_patterns=exclude_patterns,
                    respect_robots=respect_robots,
                    max_total_time=max_total_time
                    # Other parameters like timeout, max_concurrent_pages will use defaults from shared client
                )

                if response.error:
                    logger.error(f"Crawl triggered but service reported an error: {response.error}")
                    # Depending on desired behavior, this might still be considered a 'successful trigger'
                    # if the main goal is just to make sure the request reached the crawler service.
                    # For now, we'll say if the service itself reports an error, the trigger wasn't fully successful.
                    return False # Or True, if partial success is acceptable for a 'trigger'
                else:
                    logger.info(f"Crawl successfully triggered for URLs. Total URLs processed by crawler: {response.total_urls}")
                    return True

        except Exception as e:
            logger.error(f"Failed to trigger crawl due to an exception: {e}", exc_info=True)
            return False 