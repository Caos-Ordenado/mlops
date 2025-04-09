"""
Tool for searching using SerpAPI
"""

import aiohttp
from typing import Dict, Any, List
from shared.logging import setup_logger
from config import settings

logger = setup_logger("serpapi_tool")

class SerpAPITool:
    """Tool for searching using SerpAPI"""
    
    def __init__(self):
        """Initialize the SerpAPI tool"""
        self.name = "serpapi_search"
        self.description = "Search for online stores in Montevideo using SerpAPI"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10
                }
            },
            "required": ["query"]
        }
        self._session = None
        self.api_key = settings.SERPAPI_API_KEY
        
    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the tool to a dictionary for serialization
        
        Returns:
            Dictionary representation of the tool
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
        
    async def __aenter__(self):
        """Create aiohttp session"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session"""
        await self.close()
            
    async def execute(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """
        Execute the SerpAPI search
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results
        """
        try:
            # Add Montevideo and shopping terms if not present
            if "montevideo" not in query.lower():
                query = f"{query} montevideo"
            if "comprar" not in query.lower() and "tienda" not in query.lower():
                query = f"{query} comprar"
                
            logger.debug(f"Searching with query: {query}")
            
            # Make request to SerpAPI
            async with self.session.get(
                "https://serpapi.com/search.json",
                params={
                    "q": query,
                    "api_key": self.api_key,
                    "engine": "google",  # Use Google search engine
                    "gl": "uy",         # Uruguay
                    "hl": "es",         # Spanish language
                    "num": max_results, # Number of results
                    "safe": "active"    # Safe search
                }
            ) as response:
                # Log response status
                logger.debug(f"Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Log the response structure
                    logger.debug(f"Response keys: {list(data.keys())}")
                    
                    results = []
                    
                    # Process organic results
                    for result in data.get("organic_results", [])[:max_results]:
                        try:
                            title = result.get("title", "")
                            url = result.get("link", "")
                            snippet = result.get("snippet", "")
                            
                            # Log each result for debugging
                            logger.debug(f"Processing result: {title} - {url}")
                            
                            # Include all results
                            results.append({
                                "name": title,
                                "url": url,
                                "description": snippet
                            })
                        except Exception as e:
                            logger.error(f"Error processing result: {str(e)}")
                            continue
                    
                    # Process shopping results if available
                    for result in data.get("shopping_results", [])[:max_results]:
                        try:
                            title = result.get("title", "")
                            url = result.get("link", "")
                            snippet = result.get("snippet", "")
                            
                            # Log each result for debugging
                            logger.debug(f"Processing shopping result: {title} - {url}")
                            
                            results.append({
                                "name": title,
                                "url": url,
                                "description": snippet
                            })
                        except Exception as e:
                            logger.error(f"Error processing shopping result: {str(e)}")
                            continue
                    
                    # Remove duplicates based on URL
                    unique_results = []
                    seen_urls = set()
                    for result in results:
                        if result["url"] not in seen_urls:
                            seen_urls.add(result["url"])
                            unique_results.append(result)
                    
                    logger.debug(f"Found {len(unique_results)} relevant stores")
                    return unique_results[:max_results]
                else:
                    logger.error(f"Error from SerpAPI: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error executing SerpAPI tool: {str(e)}")
            return [] 