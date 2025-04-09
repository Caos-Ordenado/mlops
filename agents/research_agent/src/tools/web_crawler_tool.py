from typing import Dict, Any, Optional, List
import aiohttp
from shared.web_crawler_client import WebCrawlerClient
from shared.logging import setup_logger
from config import settings

logger = setup_logger("web_crawler_tool")

class WebCrawlerTool:
    """
    Tool for web crawling and extracting content from web pages
    """
    def __init__(self):
        self.name = "web_crawler"
        self.description = "Crawl to a web page and extract its content. Useful for reading and analyzing web pages found through search."
        self._openapi_spec = None
        self._crawl_parameters = None
        self._update_parameters_from_openapi()
        self.base_url = settings.CRAWLER_URL  # Use the full URL from settings
        self.session = None

    def _update_parameters_from_openapi(self) -> None:
        """
        Update the tool's parameters based on the OpenAPI specification
        """
        base_parameters = {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the web page to navigate to"
                },
                "extract_links": {
                    "type": "boolean",
                    "description": "Whether to extract and return links found on the page",
                    "default": False
                }
            },
            "required": ["url"]
        }

        # If we have OpenAPI spec, add additional parameters
        if self._openapi_spec:
            try:
                # Extract crawl endpoint parameters from OpenAPI spec
                paths = self._openapi_spec.get("paths", {})
                crawl_path = next((path for path in paths if "crawl" in path), None)
                if crawl_path:
                    crawl_endpoint = paths[crawl_path]
                    post_method = crawl_endpoint.get("post", {})
                    parameters = post_method.get("parameters", [])
                    request_body = post_method.get("requestBody", {})
                    
                    # Add parameters from OpenAPI spec
                    for param in parameters:
                        if param.get("in") == "query":
                            param_name = param["name"]
                            base_parameters["properties"][param_name] = {
                                "type": param.get("schema", {}).get("type", "string"),
                                "description": param.get("description", ""),
                                "default": param.get("schema", {}).get("default")
                            }
                    
                    # Add request body parameters
                    if request_body:
                        content = request_body.get("content", {})
                        schema = content.get("application/json", {}).get("schema", {})
                        properties = schema.get("properties", {})
                        for prop_name, prop in properties.items():
                            base_parameters["properties"][prop_name] = {
                                "type": prop.get("type", "string"),
                                "description": prop.get("description", ""),
                                "default": prop.get("default")
                            }
                
                logger.info("Updated tool parameters from OpenAPI specification")
            except Exception as e:
                logger.error(f"Error updating parameters from OpenAPI spec: {str(e)}")
        
        self.parameters = base_parameters

    async def _fetch_openapi_spec(self) -> Dict[str, Any]:
        """
        Fetch the OpenAPI specification from the web crawler service
        """
        if self._openapi_spec is not None:
            return self._openapi_spec

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://home.server/crawler/openapi.json") as response:
                    if response.status == 200:
                        self._openapi_spec = await response.json()
                        self._update_parameters_from_openapi()
                        logger.info("Successfully fetched OpenAPI specification from web crawler")
                        return self._openapi_spec
                    else:
                        logger.warning(f"Failed to fetch OpenAPI spec. Status: {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Error fetching OpenAPI specification: {str(e)}")
            return {}

    async def __aenter__(self):
        """Create aiohttp session"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    async def execute(self, url: str, extract_links: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Navigate to a web page and extract its content
        
        Args:
            url: The URL of the web page to navigate to
            extract_links: Whether to extract and return links found on the page
            **kwargs: Additional parameters from the OpenAPI specification
            
        Returns:
            Dictionary containing the page content and optionally links
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            logger.info(f"Navigating to URL: {url}")
            
            # Fetch OpenAPI spec to ensure we're using the correct API
            openapi_spec = await self._fetch_openapi_spec()
            
            async with WebCrawlerClient() as client:
                # Get the page content with all provided parameters
                crawl_params = {"urls": [url], **kwargs}
                response = await client.crawl(**crawl_params)
                
                if not response or not response.results:
                    logger.warning(f"No results found for URL: {url}")
                    return {
                        "error": "Failed to retrieve page content",
                        "url": url,
                        "status": "error"
                    }
                
                # Get the first result (most relevant page)
                result = response.results[0]
                
                # Extract content from the result
                content = result.text
                title = result.title
                links = result.links
                metadata = result.metadata
                
                logger.debug(f"Retrieved content length: {len(content)} characters")
                logger.debug(f"Title: {title}")
                logger.debug(f"Found {len(links)} links")
                
                # Build the result dictionary
                result_dict = {
                    "url": url,
                    "title": title,
                    "content": content,
                    "status": "success"
                }
                
                # Add links if requested
                if extract_links:
                    result_dict["links"] = links
                
                logger.info(f"Successfully extracted content from URL: {url}")
                return result_dict
                
        except Exception as e:
            logger.error(f"Error navigating to URL {url}: {str(e)}")
            return {
                "error": str(e),
                "url": url,
                "status": "error"
            } 