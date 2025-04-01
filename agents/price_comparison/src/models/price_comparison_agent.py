from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from .storage import PriceStorage
from .config import settings

class ProductComparison(BaseModel):
    """Model for product comparison results."""
    product_name: str
    normalized_name: str
    best_price: float
    best_price_store: str
    best_price_url: Optional[str] = None
    all_prices: Dict[str, float]
    price_difference: float = Field(description="Difference between highest and lowest price")
    price_difference_percentage: float = Field(description="Percentage difference between highest and lowest price")
    last_updated: str
    historical_low: Optional[float] = None
    historical_high: Optional[float] = None

class PriceComparisonAgent:
    """AI agent for comparing product prices across different supermarkets."""
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize the price comparison agent.
        
        Args:
            model_name: Optional name of the Ollama model to use, defaults to env config
        """
        # Configure Ollama to use Traefik endpoint
        self.model = Ollama(
            base_url=settings.ollama_base_url,
            model=model_name or settings.OLLAMA_MODEL,
            temperature=0.1  # Lower temperature for more consistent outputs
        )
        self.storage = PriceStorage()
        logger.info(f"Price comparison agent initialized with model: {model_name or settings.OLLAMA_MODEL}")

        # Create the normalization prompt template
        self.normalize_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a product name normalizer. Your task is to standardize product names by following these rules:
            1. Standardize units (e.g., 'kg' instead of 'kilos')
            2. Remove packaging information unless essential
            4. Use lowercase
            4. Remove extra spaces
            
            Respond ONLY with the normalized name, nothing else."""),
            ("human", "{product_name}")
        ])
        
        # Create the normalization chain
        self.normalize_chain = self.normalize_prompt | self.model
    
    async def initialize(self):
        """Initialize storage connections and ensure model is available."""
        await self.storage.initialize()
        
        # Check if model exists, pull if it doesn't
        try:
            # Try to use the model
            await self.normalize_product_name("test product")
        except Exception as e:
            logger.warning(f"Error accessing model, attempting to pull: {e}")
            # If model doesn't exist, pull it
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/pull",
                    json={"name": settings.OLLAMA_MODEL},
                    timeout=settings.OLLAMA_TIMEOUT
                )
                if response.status_code != 200:
                    raise Exception(f"Failed to pull model: {response.text}")
                logger.info(f"Successfully pulled {settings.OLLAMA_MODEL} model")
    
    async def normalize_product_name(self, product_name: str) -> str:
        """Use LLM to normalize product names for better comparison.
        
        Args:
            product_name: Raw product name from crawler
            
        Returns:
            Normalized product name
        """
        try:
            # Use the normalization chain
            response = await self.normalize_chain.ainvoke({"product_name": product_name})
            return response.strip()
        except Exception as e:
            logger.error(f"Error normalizing product name: {e}")
            # Fallback to basic normalization if LLM fails
            return product_name.lower().strip()
    
    async def store_product_price(
        self,
        raw_name: str,
        store: str,
        price: float,
        url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Store a product price after normalizing the name.
        
        Args:
            raw_name: Original product name
            store: Store name
            price: Product price
            url: Optional URL to the product
            metadata: Optional additional data
        """
        normalized_name = await self.normalize_product_name(raw_name)
        await self.storage.store_product_price(
            raw_name=raw_name,
            normalized_name=normalized_name,
            store=store,
            price=price,
            url=url,
            metadata=metadata
        )
    
    async def compare_products(self, raw_name: str) -> ProductComparison:
        """Compare prices of similar products across different stores.
        
        Args:
            raw_name: Raw product name to compare
            
        Returns:
            ProductComparison object with analysis results
        """
        normalized_name = await self.normalize_product_name(raw_name)
        current_prices = await self.storage.get_latest_prices(normalized_name)
        history = await self.storage.get_price_history(normalized_name)
        
        if not current_prices:
            raise ValueError(f"No prices found for product: {raw_name}")
        
        # Calculate current price statistics
        prices = {store: data["price"] for store, data in current_prices.items()}
        min_price = min(prices.values())
        max_price = max(prices.values())
        best_store = min(prices.items(), key=lambda x: x[1])[0]
        
        # Calculate historical statistics if available
        historical_prices = [item["price"] for item in history]
        historical_low = min(historical_prices) if historical_prices else None
        historical_high = max(historical_prices) if historical_prices else None
        
        return ProductComparison(
            product_name=raw_name,
            normalized_name=normalized_name,
            best_price=min_price,
            best_price_store=best_store,
            best_price_url=current_prices[best_store].get("url"),
            all_prices=prices,
            price_difference=max_price - min_price,
            price_difference_percentage=((max_price - min_price) / min_price) * 100,
            last_updated=max(data["updated_at"] for data in current_prices.values()),
            historical_low=historical_low,
            historical_high=historical_high
        )
    
    async def get_historical_trends(self, raw_name: str, store: Optional[str] = None) -> Dict:
        """Analyze historical price trends for a product.
        
        Args:
            raw_name: Product name to analyze
            store: Optional store name to filter by
            
        Returns:
            Dictionary with trend analysis
        """
        normalized_name = await self.normalize_product_name(raw_name)
        history = await self.storage.get_price_history(normalized_name, store)
        
        if not history:
            raise ValueError(f"No price history found for product: {raw_name}")
        
        # Calculate trend statistics
        prices = [item["price"] for item in history]
        current_price = prices[0]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        return {
            "product_name": raw_name,
            "normalized_name": normalized_name,
            "current_price": current_price,
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "price_volatility": max_price - min_price,
            "price_trend": [
                {
                    "date": item["date"],
                    "price": item["price"],
                    "store": item["store"]
                }
                for item in history
            ],
            "num_records": len(history)
        }
    
    async def close(self):
        """Close all connections and cleanup resources."""
        await self.storage.close()
        logger.info("Price comparison agent resources cleaned up") 