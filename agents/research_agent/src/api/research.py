from fastapi import APIRouter, HTTPException, Body
import re
import json
from typing import List, Dict, Any
from shared.logging import setup_logger
from pydantic import BaseModel
from shared.ollama_client import OllamaClient
from tools.web_search_tool import web_search
from prompts.research_prompt import RESEARCH_SYSTEM_PROMPT
from utils.tool_utils import extract_tool_call
from parsers.research_parser import parse_llm_response
from config import settings
from tools.web_crawler_tool import WebCrawlerTool

logger = setup_logger("research_agent.api.research")

router = APIRouter(prefix="/research", tags=["research"])

class ResearchRequest(BaseModel):
    """Request model for product research"""
    query: str
    model: str = "llama3.1"
    max_tokens: int = 1000

class ResearchResponse(BaseModel):
    """Response model for product research"""
    product_name: str
    stores: List[Dict[str, str]]
    price_range: Dict[str, str]
    best_value: Dict[str, str]
    common_features: List[str]
    premium_options: List[str]
    special_considerations: List[str]
    result: Dict[str, Any] = None  # Make result field optional with None as default

async def fetch_product_details(url: str) -> Dict[str, Any]:
    """
    Fetch product details from a store URL using the web crawler
    
    Args:
        url: The store URL to crawl
        
    Returns:
        Dictionary containing product details
    """
    try:
        logger.info(f"Fetching product details from URL: {url}")
        web_tool = WebCrawlerTool()
        results = await web_tool.execute(url)
        
        if not results or not isinstance(results, list) or len(results) == 0:
            logger.warning(f"No results found for URL: {url}")
            return {}
            
        # Get the first result (most relevant page)
        result = results[0]
        
        if result.get("status") == "error":
            logger.warning(f"Failed to fetch details from {url}: {result.get('error')}")
            return {}
            
        # Extract product details from the page content
        content = result.get("content", "").lower()
        logger.debug(f"Retrieved content length: {len(content)} characters")
        
        # Look for price patterns (e.g., "UYU 100", "$100", "100 pesos")
        price_patterns = [
            r"u\s*y\s*u\s*(\d+(?:\.\d+)?)",  # UYU 100
            r"\$(\d+(?:\.\d+)?)",  # $100
            r"(\d+(?:\.\d+)?)\s*pesos",  # 100 pesos
        ]
        
        price = None
        for pattern in price_patterns:
            match = re.search(pattern, content)
            if match:
                price = match.group(1)
                logger.debug(f"Found price using pattern {pattern}: {price}")
                break
                
        # Look for availability indicators
        availability_indicators = {
            "en stock": "In Stock",
            "disponible": "Available",
            "agotado": "Out of Stock",
            "sin stock": "Out of Stock"
        }
        
        availability = None
        for indicator, status in availability_indicators.items():
            if indicator in content:
                availability = status
                logger.debug(f"Found availability status: {status}")
                break
                
        # Look for delivery options
        delivery_options = []
        delivery_indicators = [
            "envío",
            "delivery",
            "entrega",
            "retiro"
        ]
        
        for indicator in delivery_indicators:
            if indicator in content:
                delivery_options.append(indicator.capitalize())
                logger.debug(f"Found delivery option: {indicator}")
                
        # Extract product description
        description = None
        # Common description patterns in e-commerce sites
        description_patterns = [
            r"descripción[:\s]+(.+?)(?=\n|$)",  # "Descripción: ..."
            r"detalles[:\s]+(.+?)(?=\n|$)",  # "Detalles: ..."
            r"características[:\s]+(.+?)(?=\n|$)",  # "Características: ..."
            r"información[:\s]+(.+?)(?=\n|$)",  # "Información: ..."
            r"producto[:\s]+(.+?)(?=\n|$)",  # "Producto: ..."
        ]
        
        for pattern in description_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                description = match.group(1).strip()
                # Clean up the description
                description = re.sub(r'\s+', ' ', description)  # Remove extra whitespace
                description = description.capitalize()  # Capitalize first letter
                logger.debug(f"Found description using pattern {pattern}")
                break
                
        result = {
            "price": price,
            "availability": availability,
            "delivery_options": delivery_options,
            "description": description
        }
        logger.info(f"Successfully extracted product details: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching product details from {url}: {str(e)}")
        return {}

def extract_tool_call(response: str) -> tuple[str, dict] | None:
    """
    Extract tool call from LLM response
    
    Args:
        response: LLM response text
        
    Returns:
        Tuple of (tool_name, parameters) or None if no tool call found
    """
    tool_call_match = re.search(
        r'\[TOOL_CALL\]\nTool: (.+?)\nParameters: ({.+?})\n\[/TOOL_CALL\]',
        response,
        re.DOTALL
    )
    if tool_call_match:
        tool_name = tool_call_match.group(1).strip()
        params_str = tool_call_match.group(2).strip()
        # Safely evaluate the parameters string
        try:
            params = eval(params_str)  # Using eval here is safe as we control the input format
            return tool_name, params
        except:
            return None
    return None

@router.post("/", response_model=ResearchResponse)
async def perform_research(request: ResearchRequest) -> ResearchResponse:
    """
    Perform product research using web search and Ollama
    
    Args:
        request: Research request containing query and model parameters
        
    Returns:
        Research response with product information
    """
    logger.info(f"Processing product research request: {request.query}")
    
    try:
        # Initialize services
        ollama_client = OllamaClient()
        
        async with ollama_client:
            # Search for stores
            logger.info("Starting store search with web search")
            urls = await web_search.execute(
                query=request.query,
                engine="random",
                max_results=10,
                model=request.model  # Pass the model parameter from the request
            )
            logger.info(f"Found {len(urls)} URLs")
            
            if not urls:
                logger.warning("No search results found")
                return ResearchResponse(
                    product_name=request.query,
                    stores=[],
                    price_range={"min": "N/A", "max": "N/A"},
                    best_value={"name": "N/A", "url": "N/A", "price": "N/A", "description": "No stores found"},
                    common_features=[],
                    premium_options=[],
                    special_considerations=["No search results found for this product"],
                    result={"error": "No search results found"}
                )
            
            # Convert URLs to store format with more context
            stores = []
            for url in urls:
                # Extract domain name for store name
                domain = url.split('/')[2] if len(url.split('/')) > 2 else url
                stores.append({
                    "url": url,
                    "name": domain,
                    "description": f"Online store found at {domain}",
                    "search_rank": len(stores) + 1  # Add rank for context
                })
            
            # Fetch detailed information for each store
            logger.info("Starting detailed information gathering for stores")
            detailed_stores = []
            for store in stores:
                logger.info(f"Fetching details for store: {store.get('name')}")
                try:
                    details = await fetch_product_details(store.get('url'))
                    detailed_store = {**store, **details}
                    detailed_stores.append(detailed_store)
                    logger.debug(f"Store details: {detailed_store}")
                except Exception as e:
                    logger.error(f"Error fetching details for {store.get('url')}: {str(e)}")
                    # Still include the store with basic info
                    detailed_stores.append(store)
            
            # Generate response from Ollama using the system prompt
            logger.info("Generating analysis with Ollama")
            prompt = f"Analyze the following stores selling {request.query} in Montevideo:\n{json.dumps(detailed_stores, indent=2)}"
            
            logger.debug(f"Sending prompt to Ollama: {prompt}")
            response = await ollama_client.generate(
                prompt=prompt,
                system=RESEARCH_SYSTEM_PROMPT,  # Use system parameter for RAG context
                model=request.model,
                max_tokens=request.max_tokens
            )
            logger.debug(f"Received Ollama response: {response}")
            
            # Parse the response
            logger.info("Parsing Ollama response")
            research_response = await parse_llm_response(response, detailed_stores)
            logger.info(f"Final research response: {research_response}")
            
            return research_response
            
    except Exception as e:
        logger.error(f"Error performing research: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 