import os
import sys
from typing import Dict, Any, List, Optional
from loguru import logger
from pathlib import Path

# Add web crawler to Python path
web_crawler_path = str(Path(__file__).parent.parent.parent.parent / "web_crawler" / "src")
if web_crawler_path not in sys.path:
    sys.path.append(web_crawler_path)

from crawler import WebCrawlerAgent, CrawlerSettings
from .config import settings

class PriceCrawlerIntegration:
    """Integration with the web crawler for price comparison."""
    
    def __init__(self):
        self.crawler_settings = CrawlerSettings(
            max_pages=int(settings.CRAWLER_MAX_PAGES),
            max_depth=int(settings.CRAWLER_MAX_DEPTH),
            timeout=settings.CRAWLER_TIMEOUT,
            max_concurrent_pages=int(settings.CRAWLER_MAX_CONCURRENT),
            memory_threshold=float(settings.CRAWLER_MEMORY_THRESHOLD),
            respect_robots=True,
            user_agent="Price Comparison Agent/1.0"
        )
        self.crawler = None
    
    async def initialize(self):
        """Initialize the web crawler."""
        self.crawler = WebCrawlerAgent(self.crawler_settings)
        logger.info("Web crawler initialized")
    
    async def crawl_product_prices(
        self,
        product_name: str,
        store_urls: List[str],
        allowed_domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Crawl product prices from specified store URLs.
        
        Args:
            product_name: Name of the product to search for
            store_urls: List of store URLs to crawl
            allowed_domains: Optional list of allowed domains
            
        Returns:
            List of dictionaries containing price information
        """
        if allowed_domains:
            self.crawler_settings.allowed_domains = allowed_domains
        
        results = []
        for url in store_urls:
            try:
                # Crawl the store URL
                result = await self.crawler.crawl_url(url)
                
                # Extract price information using the product name
                price_info = self._extract_price_info(result, product_name)
                if price_info:
                    results.append(price_info)
                    
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                continue
        
        return results
    
    def _extract_price_info(self, crawl_result: Dict[str, Any], product_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract price information from crawl result for a specific product.
        
        Args:
            crawl_result: Result from web crawler
            product_name: Name of the product to find
            
        Returns:
            Dictionary containing price information if found
        """
        try:
            # Extract text content
            text = crawl_result.get('text', '')
            
            # TODO: Implement price extraction logic using LLM
            # This will use the LLM to:
            # 1. Find product mentions in the text
            # 2. Extract price information
            # 3. Validate the extracted information
            
            # For now, return a placeholder
            return {
                'url': crawl_result.get('url', ''),
                'store': self._extract_store_name(crawl_result.get('url', '')),
                'raw_text': text,
                'metadata': crawl_result.get('metadata', {})
            }
            
        except Exception as e:
            logger.error(f"Error extracting price info: {e}")
            return None
    
    def _extract_store_name(self, url: str) -> str:
        """Extract store name from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.split('.')[1]
        except:
            return url
    
    async def close(self):
        """Close the web crawler."""
        if self.crawler:
            await self.crawler.close()
        logger.info("Web crawler closed") 