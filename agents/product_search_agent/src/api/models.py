from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class ProductSearchRequest(BaseModel):
    product: str = Field(..., description="Product to search for", example="laptop")

class BraveApiHit(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    # Add other fields if Brave returns more that might be useful, e.g., is_source_amp, profile, etc.

class BraveSearchResult(BaseModel):
    query: str # The validated query string used for Brave search
    results: Optional[Dict[str, Any]] = None # The raw JSON object from Brave for this query. It often contains keys like 'web', 'faq', 'videos'. We're mainly interested in 'web'.'results'

class ExtractedUrlInfo(BaseModel):
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    source_query: str # The original search query that led to this URL

class IdentifiedPageCandidate(BaseModel):
    url: str
    original_title: Optional[str] = None
    original_snippet: Optional[str] = None
    source_query: str # The original search query that led to this URL

    # Fields from LLM
    page_type: str # e.g., "PRODUCT", "CATEGORY", "BLOG", "OTHER"
    reasoning: Optional[str] = None # Simplified and made optional
    identified_product_name: Optional[str] = None # For PRODUCT type
    category_name: Optional[str] = None # For CATEGORY type
    # Removed confidence, analysis_details

# QueryValidationDetail is no longer directly exposed in the final API response
# but is used internally by ProductSearchAgent.
# class QueryValidationDetail(BaseModel):
#     query: str
#     valid: bool
#     reason: Optional[str] = None

class PriceExtractionResult(BaseModel):
    """Result from price extraction for a single product."""
    success: bool
    price: Optional[float] = None
    currency: Optional[str] = None  # "UYU", "USD", etc.
    original_text: Optional[str] = None  # Original price text found
    confidence: Optional[float] = None  # 0.0 to 1.0
    error: Optional[str] = None

class ProductWithPrice(BaseModel):
    """Product information with extracted price data."""
    url: str
    product_name: Optional[str] = None
    original_title: Optional[str] = None
    source_query: str
    
    # Price information
    price_extraction: PriceExtractionResult
    
    # Sort helper property
    @property
    def sort_price(self) -> float:
        """Return price for sorting, or infinity if no price."""
        if self.price_extraction.success and self.price_extraction.price is not None:
            return self.price_extraction.price
        return float('inf')

class ProductSearchResponse(BaseModel):
    success: bool
    results: List[str] # Validated query strings
    extracted_product_candidates: Optional[List[ExtractedUrlInfo]] = None
    identified_page_candidates: Optional[List[IdentifiedPageCandidate]] = None
    extracted_prices: Optional[List[ProductWithPrice]] = None  # 🆕 NEW: Price extraction results
    validation_attempts: int = 0 