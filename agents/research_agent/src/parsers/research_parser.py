"""
Parser for handling LLM responses in the research agent
"""

import json
from typing import List, Dict, Any
from shared.logging import setup_logger

from models import ProductComparison, StoreInfo, ResearchResponse
from services.product_crawler import ProductCrawler

logger = setup_logger("research_parser")

async def parse_llm_response(response: str, stores: List[Dict[str, Any]]) -> ResearchResponse:
    """
    Parse the LLM's response into a structured ResearchResponse object
    
    Args:
        response: LLM's analysis of the stores
        stores: List of store information from DuckDuckGo
        
    Returns:
        Structured ResearchResponse object
    """
    try:
        # Handle empty stores list
        if not stores:
            return ResearchResponse(
                result=ProductComparison(
                    product_name="Unknown Product",
                    stores=[],
                    price_range={"min": "N/A", "max": "N/A"},
                    best_value=StoreInfo(
                        name="N/A",
                        url="N/A",
                        price="N/A"
                    ),
                    common_features=[],
                    premium_options=[],
                    special_considerations=["No stores found"]
                )
            )
        
        # Try to parse the response as JSON
        try:
            response_data = json.loads(response)
            
            # Extract product name from the first store's description
            product_name = response_data.get("product_name", stores[0]["name"].split("|")[0].strip() if "|" in stores[0]["name"] else stores[0]["name"])
            
            # Create store info objects
            store_info = []
            for store in stores:
                # Ensure URL is properly formatted
                url = store.get("url", "")
                if not url:
                    continue
                    
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                    
                # Fetch product details from the store URL
                details = await ProductCrawler.fetch_product_details(url)
                
                store_info.append(StoreInfo(
                    name=store["name"],
                    url=url,
                    price=details.get("price"),
                    availability=details.get("availability"),
                    delivery_options=details.get("delivery_options", []),
                    description=details.get("description", "")
                ))
            
            # Create the product comparison
            product_comparison = ProductComparison(
                product_name=product_name,
                stores=store_info,
                price_range=response_data.get("price_range", {"min": "N/A", "max": "N/A"}),
                best_value=StoreInfo(
                    name=response_data.get("best_value", {}).get("store", "N/A"),
                    url=response_data.get("best_value", {}).get("url", "N/A"),
                    price=response_data.get("best_value", {}).get("price", "N/A")
                ),
                common_features=response_data.get("common_features", []),
                premium_options=[],
                special_considerations=response_data.get("special_considerations", [])
            )
            
            # Create the response object
            return ResearchResponse(result=product_comparison)
            
        except json.JSONDecodeError:
            # Fall back to text parsing if JSON parsing fails
            logger.warning("Failed to parse LLM response as JSON, falling back to text parsing")
            
            # Extract product name from the first store's description
            product_name = stores[0]["name"].split("|")[0].strip() if "|" in stores[0]["name"] else stores[0]["name"]
            
            # Create store info objects
            store_info = []
            for store in stores:
                # Ensure URL is properly formatted
                url = store.get("url", "")
                if not url:
                    continue
                    
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                    
                # Fetch product details from the store URL
                details = await ProductCrawler.fetch_product_details(url)
                
                store_info.append(StoreInfo(
                    name=store["name"],
                    url=url,
                    price=details.get("price"),
                    availability=details.get("availability"),
                    delivery_options=details.get("delivery_options", []),
                    description=details.get("description", "")
                ))
            
            # Create the product comparison
            product_comparison = ProductComparison(
                product_name=product_name,
                stores=store_info,
                price_range={"min": "N/A", "max": "N/A"},
                best_value=StoreInfo(
                    name="N/A",
                    url="N/A",
                    price="N/A"
                ),
                common_features=[],
                premium_options=[],
                special_considerations=[]
            )
            
            # Parse the LLM's analysis to update the response
            if "Common features:" in response:
                features_section = response.split("Common features:")[1].split("\n\n")[0]
                product_comparison.common_features = [f.strip("- ") for f in features_section.split("\n") if f.strip()]
            
            if "Price range:" in response:
                price_section = response.split("Price range:")[1].split("\n\n")[0]
                prices = [p.strip() for p in price_section.split("\n") if "UYU" in p]
                if prices:
                    product_comparison.price_range = {
                        "min": min(prices, key=lambda x: float(x.split("UYU")[0].strip())),
                        "max": max(prices, key=lambda x: float(x.split("UYU")[0].strip()))
                    }
            
            return ResearchResponse(result=product_comparison)
            
    except Exception as e:
        logger.error(f"Error parsing LLM response: {str(e)}")
        raise 