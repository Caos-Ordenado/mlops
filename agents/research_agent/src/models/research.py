from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class StoreInfo(BaseModel):
    """Information about a store selling the product"""
    name: str = Field(..., description="Name of the store")
    url: str = Field(..., description="URL of the store")
    price: Optional[str] = Field(None, description="Price in Uruguayan Pesos (UYU)")
    availability: Optional[str] = Field(None, description="Product availability status")
    delivery_options: Optional[List[str]] = Field(default_factory=list, description="Available delivery options")
    rating: Optional[float] = Field(None, description="Store rating if available")
    special_offers: Optional[List[str]] = Field(default_factory=list, description="Any special offers or discounts")


class ProductComparison(BaseModel):
    """Comparison of product information across stores"""
    product_name: str = Field(..., description="Name of the product being researched")
    common_features: List[str] = Field(default_factory=list, description="Features common across all stores")
    stores: List[StoreInfo] = Field(..., description="List of stores selling the product")
    price_range: Dict[str, str] = Field(..., description="Price range (min and max)")
    best_value: StoreInfo = Field(..., description="Store offering the best value")
    premium_options: List[StoreInfo] = Field(default_factory=list, description="Stores offering premium options")
    special_considerations: List[str] = Field(default_factory=list, description="Any special considerations for buyers")


class ResearchRequest(BaseModel):
    """
    Research request model for product search
    """
    query: str = Field(..., description="The product to research")
    model: str = Field(default="llama3.3", description="The LLM model to use")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum number of tokens in the response")
    additional_context: Optional[str] = Field(default=None, description="Optional additional context for the query")


class ResearchResponse(BaseModel):
    """
    Research response model with structured product comparison
    """
    result: ProductComparison = Field(..., description="The structured product comparison result") 