"""
Service for crawling product details from store URLs
"""

import re
from typing import Dict, Any
from shared.logging import setup_logger
from tools import WebCrawlerTool

logger = setup_logger("product_crawler")

class ProductCrawler:
    """Service for crawling product details from store URLs"""
    
    @staticmethod
    async def fetch_product_details(url: str) -> Dict[str, Any]:
        """
        Fetch product details from a store URL using the web crawler
        
        Args:
            url: The store URL to crawl
            
        Returns:
            Dictionary containing product details
        """
        try:
            web_tool = WebCrawlerTool()
            result = await web_tool.execute(url)
            
            if result.get("status") == "error":
                logger.warning(f"Failed to fetch details from {url}: {result.get('error')}")
                return {}
                
            # Extract product details from the page content
            content = result.get("content", "").lower()
            
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
                    break
                    
            return {
                "price": price,
                "availability": availability,
                "delivery_options": delivery_options,
                "description": description
            }
            
        except Exception as e:
            logger.error(f"Error fetching product details from {url}: {str(e)}")
            return {} 