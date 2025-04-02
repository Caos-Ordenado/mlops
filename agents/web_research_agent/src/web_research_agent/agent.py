"""
Web Research Agent - Combines web crawling with LLM processing.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from urllib.parse import urlparse
import json
import os
import redis
import psycopg2
from datetime import datetime, timedelta
import aioredis

from agent_utils import WebCrawlerClient, CrawlResult, OllamaClient
from agent_utils.logging import setup_logger

# Set up logger
logger = setup_logger("web_research_agent")

@dataclass
class ResearchRequest:
    """A request for web research."""
    urls: List[str]
    query: str
    max_pages: int = 5
    max_depth: int = 2
    model: str = "llama2"

@dataclass
class ResearchResponse:
    """Response from the web research agent."""
    summary: str
    sources: List[Dict[str, str]]
    raw_content: Optional[List[CrawlResult]] = None

class WebResearchAgent:
    """Agent that combines web crawling with LLM processing."""
    
    def __init__(self):
        """Initialize the web research agent."""
        logger.debug("Initializing WebResearchAgent")
        self.crawler = WebCrawlerClient()
        self.llm = OllamaClient()
        
        # Initialize Redis connection
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "home.server"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD", ""),
            decode_responses=True
        )
        
        # Initialize PostgreSQL connection
        self.pg_conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "web_crawler"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=os.getenv("POSTGRES_HOST", "home.server"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        
    async def __aenter__(self):
        """Initialize connections when entering context."""
        logger.debug("Entering WebResearchAgent context")
        
        # Initialize Redis connection
        self.redis = await aioredis.from_url(
            f"redis://{os.getenv('REDIS_HOST', 'home.server')}:{os.getenv('REDIS_PORT', '6379')}",
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize PostgreSQL connection
        self.pg_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "home.server"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            database=os.getenv("POSTGRES_DB", "web_crawler")
        )
        
        # Initialize crawler and LLM
        await self.crawler.__aenter__()
        await self.llm.__aenter__()
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        logger.debug("Exiting WebResearchAgent context")
        if self.crawler:
            await self.crawler.__aexit__(exc_type, exc_val, exc_tb)
        if self.llm:
            await self.llm.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis:
            self.redis.close()
        if self.pg_conn:
            self.pg_conn.close()
            
    async def _check_services(self) -> bool:
        """Check if required services are healthy."""
        logger.debug("Checking service health")
        crawler_healthy = await self.crawler.health_check()
        llm_healthy = await self.llm.health_check()
        
        # Check Redis health
        try:
            self.redis.ping()
            redis_healthy = True
        except:
            redis_healthy = False
            
        # Check PostgreSQL health
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            pg_healthy = True
        except:
            pg_healthy = False
        
        logger.debug(f"Service health status - Crawler: {crawler_healthy}, LLM: {llm_healthy}, Redis: {redis_healthy}, PostgreSQL: {pg_healthy}")
        
        if not crawler_healthy:
            logger.error("Web crawler service is not available")
            raise Exception("Web crawler service is not available")
        if not llm_healthy:
            logger.error("Ollama LLM service is not available")
            raise Exception("Ollama LLM service is not available")
            
        return True
        
    def _extract_domains(self, urls: List[str]) -> List[str]:
        """Extract domains from URLs."""
        logger.debug(f"Extracting domains from URLs: {urls}")
        domains = []
        for url in urls:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain:
                domains.append(domain)
        domains = list(set(domains))
        logger.debug(f"Extracted domains: {domains}")
        return domains
        
    async def _get_cached_content(self, urls: List[str], query: str) -> List[Dict[str, Any]]:
        """Get relevant cached content from Redis and PostgreSQL.
        
        Args:
            urls: List of URLs to check for cached content
            query: Query to use for relevance scoring
            
        Returns:
            List of relevant cached content items
        """
        cached_items = []
        
        # Get domains from URLs
        domains = [urlparse(url).netloc for url in urls]
        logger.debug(f"Searching for content from domains: {domains}")
        
        # Search PostgreSQL for relevant content
        try:
            cur = self.pg_conn.cursor()
            try:
                # Search by domain and relevance
                cur.execute("""
                    SELECT url, title, text_content, metadata,
                        ts_rank_cd(to_tsvector('english', text_content), plainto_tsquery('english', %s)) as rank
                    FROM pages 
                    WHERE substring(url from '.*://([^/]*)') = ANY(%s)
                    AND ts_rank_cd(to_tsvector('english', text_content), plainto_tsquery('english', %s)) > 0.1
                    ORDER BY rank DESC
                    LIMIT 5
                """, (query, domains, query))
                
                for row in cur.fetchall():
                    logger.debug(f"Found relevant content in PostgreSQL: {row[0]} (rank: {row[4]})")
                    cached_items.append({
                        'url': row[0],
                        'title': row[1],
                        'text': row[2],
                        'metadata': row[3],
                        'type': 'cached',
                        'source': 'postgres'
                    })
            finally:
                cur.close()
                    
        except Exception as e:
            logger.error(f"Error retrieving content from PostgreSQL: {str(e)}", exc_info=True)
            
        # Check Redis cache
        try:
            for url in urls:
                redis_key = f"crawler:{url}"
                data = await self.redis.get(redis_key)
                if data:
                    try:
                        content = json.loads(data)
                        # Only include if from same domain
                        content_domain = urlparse(content.get('url', '')).netloc
                        if content_domain in domains:
                            logger.debug(f"Found content in Redis for {url}")
                            content['type'] = 'cached'
                            content['source'] = 'redis'
                            cached_items.append(content)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in Redis cache for {url}")
                        
        except Exception as e:
            logger.error(f"Error retrieving content from Redis: {str(e)}", exc_info=True)
            
        return cached_items
        
    def _create_research_prompt(self, query: str, crawled_content: List[CrawlResult], cached_content: List[Dict[str, Any]]) -> str:
        """Create a prompt for the LLM to generate a summary.
        
        Args:
            query: The research query
            crawled_content: List of crawled content items
            cached_content: List of cached content items
            
        Returns:
            Prompt string for the LLM
        """
        # Combine crawled and cached content, with crawled content first
        all_content = []
        
        # Add crawled content first since it's most relevant
        for item in crawled_content:
            all_content.append({
                'url': item.url,
                'title': item.title,
                'content': item.text,
                'type': 'crawled'
            })
            
        # Only add cached content from same domains
        target_domains = {urlparse(c.url).netloc for c in crawled_content}
        for item in cached_content:
            domain = urlparse(item['url']).netloc
            if domain in target_domains:
                all_content.append(item)
        
        # Build the prompt with clear section separation
        prompt = f"""Based on the following web content, please answer this question: {query}

FRESHLY CRAWLED CONTENT:
"""
        
        # Add crawled content first
        for item in all_content:
            if item['type'] == 'crawled':
                prompt += f"\nSource: {item['url']}\n"
                prompt += f"Title: {item['title']}\n"
                prompt += f"Content:\n{item['content']}\n"
                
        # Add cached content if any
        cached = [item for item in all_content if item['type'] == 'cached']
        if cached:
            prompt += "\nRELEVANT HISTORICAL CONTENT:\n"
            for item in cached:
                prompt += f"\nSource: {item['url']} (from {item.get('source', 'cache')})\n"
                prompt += f"Title: {item['title']}\n"
                prompt += f"Content:\n{item['content']}\n"
            
        prompt += "\nPlease provide a comprehensive answer to the query, focusing primarily on the freshly crawled content but incorporating relevant historical information where appropriate. Cite specific sources for key information."
        
        return prompt
        
    async def research(
        self,
        urls: List[str],
        query: str,
        max_pages: int = 5,
        max_depth: int = 2,
        model: str = "llama2"
    ) -> Tuple[str, List[Union[CrawlResult, Dict[str, Any]]]]:
        """Research web pages and generate a summary.
        
        Args:
            urls: List of URLs to research
            query: Research query
            max_pages: Maximum number of pages to crawl per URL
            max_depth: Maximum depth to crawl
            model: LLM model to use for summarization
            
        Returns:
            Tuple of summary and list of sources
        """
        # Get cached content first
        cached_content = await self._get_cached_content(urls, query)
        
        # Crawl fresh content
        crawl_results = []
        try:
            # Crawl all URLs in a single request
            results = await self.crawler.crawl(urls, max_pages=max_pages, max_depth=max_depth)
            crawl_results.extend(results)
        except Exception as e:
            logger.error(f"Failed to crawl URLs: {str(e)}")
                
        # Create research prompt
        prompt = self._create_research_prompt(query, crawl_results, cached_content)
        
        # Generate summary using LLM
        summary = await self.llm.generate(prompt, model=model)
        
        # Return summary and sources
        return summary, crawl_results + cached_content

async def main():
    """Example usage of the web research agent."""
    logger.info("Starting web research example")
    request = ResearchRequest(
        urls=["https://example.com"],
        query="What is this website about?",
        max_pages=2,
        max_depth=1
    )
    
    try:
        async with WebResearchAgent() as agent:
            response = await agent.research(request.urls, request.query, request.max_pages, request.max_depth, request.model)
            
            print("\nResearch Results:")
            print("-" * 50)
            print("\nSummary:")
            print(response[0])
            print("\nSources:")
            for source in response[1]:
                print(f"- [{'crawled' if isinstance(source, CrawlResult) else 'cached'}] {source['title']}: {source['url']}")
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())