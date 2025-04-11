"""
Search tool implementation for the research agent
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
import random
import aiohttp
from bs4 import BeautifulSoup
from tools.llm_provider import LLMProvider, get_provider_from_model
from shared.logging import setup_logger
from config import HEADERS, SEARCH_ENGINES, BRAVE_HEADERS, SEARCH_ENGINE_HEADERS
from tools.product_extractor_tool import product_extractor
import time
import socket
import urllib.parse

logger = setup_logger("search_tool")

class WebSearchTool:
    """Tool for searching the web using multiple search engines"""
    
    def __init__(self, model: str = "mixtral"):
        """
        Initialize the web search tool
        
        Args:
            model: The model to use for HTML extraction
        """
        self.name = "web_search"
        self.description = "Search the web for product URLs using multiple search engines"
        self.model = model
        self.provider = get_provider_from_model(model)
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "engine": {
                    "type": "string",
                    "description": "The search engine to use (default: random)",
                    "enum": list(SEARCH_ENGINES.keys()) + ["random"]
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "minimum": 1,
                    "maximum": 10
                },
                "model": {
                    "type": "string",
                    "description": "The model to use for HTML extraction",
                    "default": model
                }
            },
            "required": ["query"]
        }
        self._last_engine = None
        self._failed_engines = set()
        
    def _get_next_engine(self) -> str:
        """Get the next search engine to use, ensuring we don't use the same one twice in a row"""
        available_engines = list(SEARCH_ENGINES.keys())
        if len(available_engines) == 1:
            return available_engines[0]
            
        # Remove failed engines from available options
        available_engines = [e for e in available_engines if e not in self._failed_engines]
        
        if not available_engines:
            logger.warning("All search engines have failed, resetting failed engines set")
            self._failed_engines.clear()
            available_engines = list(SEARCH_ENGINES.keys())
            
        if self._last_engine in available_engines:
            available_engines.remove(self._last_engine)
            
        next_engine = random.choice(available_engines)
        self._last_engine = next_engine
        return next_engine
        
    async def _make_request(self, session: aiohttp.ClientSession, url: str, headers: Dict[str, str], max_retries: int = 3) -> Optional[str]:
        """Make an HTTP request with retry logic"""
        for attempt in range(max_retries):
            try:
                # Create a new session with increased size limits
                connector = aiohttp.TCPConnector(family=socket.AF_INET, limit_per_host=10)
                timeout = aiohttp.ClientTimeout(total=30)
                
                # Update headers to prefer gzip over brotli
                headers = headers.copy()
                headers['Accept-Encoding'] = 'gzip, deflate'
                
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    max_line_size=8190 * 2,
                    max_field_size=8190 * 2,
                ) as custom_session:
                    async with custom_session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.text()
                        elif response.status == 429:  # Too Many Requests
                            # Get retry-after from headers or use exponential backoff
                            retry_after = int(response.headers.get('Retry-After', 10 * (attempt + 1)))
                            logger.warning(f"Rate limited, waiting {retry_after} seconds")
                            await asyncio.sleep(retry_after)
                            
                            # Rotate headers on rate limit
                            if 'brave' in url:
                                headers = random.choice(BRAVE_HEADERS)
                                logger.debug("Rotating Brave headers after rate limit")
                            continue
                        elif response.status == 403:  # Forbidden
                            logger.warning(f"Access forbidden, trying different headers")
                            if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) + random.random()
                                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                                await asyncio.sleep(wait_time)
                                continue
                        else:
                            logger.error(f"Request failed with status {response.status}")
                            if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) + random.random()
                                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                                await asyncio.sleep(wait_time)
                            else:
                                return None
            except aiohttp.ClientError as e:
                logger.error(f"Request error: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.random()
                    logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    return None
        return None
        
    async def _search(self, query: str, engine: str = "random", max_results: int = 5, model: str = None) -> List[str]:
        """Search for product URLs using the specified search engine"""
        try:
            # Get the search engine URL
            if engine == "random":
                engine = self._get_next_engine()
                
            if engine not in SEARCH_ENGINES:
                logger.warning(f"Unsupported search engine: {engine}, falling back to random")
                engine = self._get_next_engine()
                
            # Add location and keywords to the search query
            location = "montevideo uruguay"
            keywords = "comprar"
            full_query = f"{query} {keywords} {location}"
            
            # URL encode the query
            encoded_query = urllib.parse.quote_plus(full_query)
            search_url = SEARCH_ENGINES[engine].format(query=encoded_query)
            logger.info(f"Searching with {engine} engine: {search_url}")
            
            # Select appropriate headers based on the search engine
            if engine in SEARCH_ENGINE_HEADERS:
                headers = random.choice(SEARCH_ENGINE_HEADERS[engine])
                logger.debug(f"Using {engine}-specific headers: {headers}")
            else:
                headers = random.choice(HEADERS)
                logger.debug(f"Using default headers: {headers}")
            
            # Make the request with retry logic
            async with aiohttp.ClientSession() as session:
                html = await self._make_request(session, search_url, headers)
                
                if html is None:
                    logger.error(f"Failed to get results from {engine}")
                    self._failed_engines.add(engine)
                    # Try another engine
                    if engine != "random":
                        logger.info("Falling back to random engine")
                        return await self._search(query, "random", max_results, model)
                    return []
                    
            # Extract only the body content
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove all script tags
            for script in soup.find_all('script'):
                script.decompose()
                
            # Remove all CSS links and style tags
            for link in soup.find_all('link', rel='stylesheet'):
                link.decompose()
            for style in soup.find_all('style'):
                style.decompose()
                
            # Remove header and footer sections
            header_footer_selectors = [
                'header', 'footer',
                '[class*="header"]', '[class*="Header"]',
                '[class*="footer"]', '[class*="Footer"]',
                '[id*="header"]', '[id*="Header"]',
                '[id*="footer"]', '[id*="Footer"]',
                'nav', 'navbar', 'navigation',
                '[class*="nav"]', '[class*="Nav"]',
                '[id*="nav"]', '[id*="Nav"]'
            ]
            
            for selector in header_footer_selectors:
                for element in soup.select(selector):
                    element.decompose()
                
            body_content = str(soup.body) if soup.body else html
            
            # Extract URLs using the HTML extractor (without location and keywords)
            logger.info(f"Extracting URLs with query: '{query}'")
            results = await product_extractor.execute(
                html=body_content,
                query=query,  # Pass original query without location and keywords
                model=model or self.model
            )
            
            # Convert to list of URLs and limit results
            urls = [result["url"] for result in results[:max_results]]
            
            logger.info(f"Found {len(urls)} results")
            if urls:
                logger.debug(f"First result: {urls[0]}")
                
            return urls
            
        except Exception as e:
            logger.error(f"Error searching for product: {str(e)}")
            self._failed_engines.add(engine)
            # Try another engine if this one failed
            if engine != "random":
                logger.info("Falling back to random engine")
                return await self._search(query, "random", max_results, model)
            return []
            
    async def execute(self, query: str, engine: str = "random", max_results: int = 5, model: str = None) -> List[str]:
        """
        Search for product URLs
        
        Args:
            query: The search query
            engine: The search engine to use (default: random)
            max_results: Maximum number of results to return (default: 5)
            model: The model to use for HTML extraction (defaults to tool's default model)
            
        Returns:
            List of product URLs
        """
        return await self._search(query, engine, max_results, model)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

# Create a singleton instance with default model
web_search = WebSearchTool()
