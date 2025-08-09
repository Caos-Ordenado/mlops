import json
import re
from typing import List, Optional, Dict, Any
from shared.logging import setup_logger
from shared.ollama_client import OllamaClient
from shared.web_crawler_client import WebCrawlerClient
from src.api.models import IdentifiedPageCandidate, ProductWithPrice, PriceExtractionResult

logger = setup_logger("price_extractor_agent")

class PriceExtractorAgent:
    def __init__(self, model_name: str = "qwen2.5:7b", temperature: float = 0.0):
        """
        Initialize PriceExtractorAgent with LLM-based price extraction.
        
        Args:
            model_name: Ollama model to use for price extraction
            temperature: Temperature for LLM generation (0.0 for deterministic)
        """
        self.model_name = model_name
        self.temperature = temperature
        logger.info(f"PriceExtractorAgent initialized with model: {model_name}, temp: {temperature}")

    async def __aenter__(self):
        logger.debug("Entering PriceExtractorAgent context")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("Exiting PriceExtractorAgent context")

    async def extract_prices(self, identified_pages: List[IdentifiedPageCandidate]) -> List[ProductWithPrice]:
        """
        Extract prices from identified product pages.
        
        Args:
            identified_pages: List of identified page candidates
            
        Returns:
            List[ProductWithPrice]: Products with extracted price information, sorted by price
        """
        logger.info(f"Starting price extraction for {len(identified_pages)} page candidates")
        
        # Strictly keep PRODUCT pages; ignore CATEGORY/OTHER and non-Uruguay exclusions
        product_pages = [
            page for page in identified_pages
            if getattr(page, 'page_type', None) == "PRODUCT"
        ]
        
        logger.info(f"Filtered to {len(product_pages)} PRODUCT and CATEGORY pages for price extraction")
        
        if not product_pages:
            logger.warning("No PRODUCT or CATEGORY pages found for price extraction")
            return []
        
        extracted_products = []
        
        for page in product_pages:
            try:
                logger.debug(f"Extracting price for: {page.url}")
                
                # Get fresh page content using crawl-single
                page_content = await self._get_page_content(page.url)
                if not page_content:
                    logger.warning(f"Could not retrieve content for {page.url} - skipping price extraction")
                    # Add failed extraction result for tracking but continue processing other pages
                    extracted_products.append(ProductWithPrice(
                        url=page.url,
                        product_name=page.identified_product_name or "Unknown Product",
                        original_title=page.original_title,
                        source_query=page.source_query,
                        price_extraction=PriceExtractionResult(
                            success=False,
                            error="Failed to crawl page content (404 or network error)"
                        )
                    ))
                    continue
                    
                # Skip pages with insufficient content (likely loading issues)  
                if len(page_content.strip()) < 50:
                    logger.warning(f"Insufficient content for {page.url} ({len(page_content)} chars) - skipping price extraction")
                    extracted_products.append(ProductWithPrice(
                        url=page.url,
                        product_name=page.identified_product_name or "Unknown Product",
                        original_title=page.original_title,
                        source_query=page.source_query,
                        price_extraction=PriceExtractionResult(
                            success=False,
                            error=f"Insufficient page content ({len(page_content)} chars)"
                        )
                    ))
                    continue
                
                # Extract price using LLM as single product (catalog handled upstream)
                products_from_page = await self._extract_products_with_llm(
                    page_content=page_content,
                    url=page.url,
                    product_name=page.identified_product_name or "unknown product",
                    page_type="PRODUCT"
                )

                # Vision fallback: if nothing found or low-confidence, try rendered screenshot extraction
                need_vision = False
                try:
                    if not products_from_page:
                        need_vision = True
                    else:
                        # if single product result with low confidence or missing price
                        if len(products_from_page) == 1:
                            pr = products_from_page[0].get('price_extraction')
                            if not pr or not getattr(pr, 'success', False) or getattr(pr, 'confidence', 0.0) < 0.6:
                                need_vision = True
                except Exception:
                    need_vision = True

                if need_vision and (
                    "rappi.com.uy" not in page.url and
                    "evisos.com.uy" not in page.url and
                    "wikipedia.org" not in page.url and
                    "acg.com.uy" not in page.url
                ):
                    logger.info(f"Attempting vision fallback for {page.url}")
                    vision_data = await self._extract_with_vision(page.url)
                    if vision_data:
                        products_from_page = [{
                            'product_name': page.identified_product_name or vision_data.get('name') or 'unknown product',
                            'price_extraction': PriceExtractionResult(
                                success=True,
                                price=self._coerce_price(vision_data.get('price')),
                                currency=self._normalize_currency(vision_data.get('currency')),
                                original_text=str(vision_data.get('price')),
                                confidence=0.75
                            )
                        }]
                
                # Add all extracted products from this page
                for product_result in products_from_page:
                    extracted_products.append(ProductWithPrice(
                        url=page.url,
                        product_name=product_result.get('product_name', page.identified_product_name),
                        original_title=page.original_title,
                        source_query=page.source_query,
                        price_extraction=product_result['price_extraction']
                    ))
                
                successful_from_page = len([p for p in products_from_page if p['price_extraction'].success])
                logger.info(f"Extracted {successful_from_page}/{len(products_from_page)} products from {page.url}")
                    
            except Exception as e:
                logger.error(f"Error extracting price for {page.url}: {e}", exc_info=True)
                # Add failed extraction result
                extracted_products.append(ProductWithPrice(
                    url=page.url,
                    product_name=page.identified_product_name,
                    original_title=page.original_title,
                    source_query=page.source_query,
                    price_extraction=PriceExtractionResult(
                        success=False,
                        error=f"Extraction failed: {str(e)}"
                    )
                ))
        
        # Filter to only successful extractions (exclude failed extractions from response)
        successful_products = [p for p in extracted_products if p.price_extraction.success]
        
        # Sort successful products by price (cheapest first)
        sorted_products = sorted(successful_products, key=lambda p: p.sort_price)
        
        successful_count = len(sorted_products)
        total_count = len(extracted_products)
        logger.info(f"Price extraction complete: {successful_count}/{total_count} successful")
        logger.info(f"Returning {successful_count} products with valid prices (filtered out {total_count - successful_count} failed extractions)")
        
        return sorted_products
    
    async def _get_page_content(self, url: str) -> Optional[str]:
        """
        Get page content using the web crawler's crawl-single endpoint.
        
        Args:
            url: URL to crawl
            
        Returns:
            Optional[str]: Page text content or None if failed
        """
        try:
            async with WebCrawlerClient() as client:
                response = await client.crawl_single(
                    url=url,
                    extract_links=False,  # We only need content, not links
                    timeout=30000  # 30 second timeout
                )
                
                if response.success and response.result:
                    logger.debug(f"Successfully retrieved content for {url} ({len(response.result.text)} chars)")
                    return response.result.text
                else:
                    error_msg = response.error or "Unknown crawl error"
                    logger.error(f"Failed to crawl {url}: {error_msg}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None
    
    async def _extract_products_with_llm(self, page_content: str, url: str, product_name: str, page_type: str) -> List[Dict]:
        """
        Extract product(s) and price(s) from page content with automatic catalog detection.
        
        Args:
            page_content: HTML content of the page
            url: URL of the page
            product_name: Product name being searched for
            page_type: Type of page (PRODUCT or CATEGORY)
            
        Returns:
            List[Dict]: List of products with their price extraction results
        """
        try:
            # Enhanced LLM extraction with automatic catalog detection
            llm_response = await self._extract_with_catalog_detection(page_content, url, product_name)
            
            # Check if LLM detected multiple products (catalog page)
            if isinstance(llm_response, dict) and "products" in llm_response:
                logger.info(f"Detected catalog page with {len(llm_response['products'])} products: {url}")
                products = []
                
                for product_data in llm_response["products"]:
                    # Create PriceExtractionResult for each product
                    price_result = PriceExtractionResult(
                        success=True,
                        price=float(product_data.get("price", 0)),
                        currency=product_data.get("currency", "UYU"),
                        original_text=product_data.get("original_text", ""),
                        confidence=product_data.get("confidence", 0.8)
                    )
                    
                    # Apply direct price parsing fix
                    if price_result.original_text:
                        direct_parsed_price = self._parse_price_directly(price_result.original_text)
                        if direct_parsed_price is not None and direct_parsed_price != price_result.price:
                            logger.warning(f"Catalog product LLM parsing error: '{price_result.original_text}' → LLM: {price_result.price}, Direct: {direct_parsed_price}")
                            price_result.price = direct_parsed_price
                            price_result.confidence = 1.0
                    
                    products.append({
                        'product_name': product_data.get("product_name", product_name),
                        'price_extraction': price_result
                    })
                
                return products
            
            else:
                # Single product response - use existing logic
                price_result = await self._extract_price_with_llm(page_content, url, product_name)
                
                # Apply direct price parsing fix
                if price_result.success and price_result.original_text and price_result.price:
                    direct_parsed_price = self._parse_price_directly(price_result.original_text)
                    if direct_parsed_price is not None and direct_parsed_price != price_result.price:
                        logger.warning(f"Single product LLM parsing error: '{price_result.original_text}' → LLM: {price_result.price}, Direct: {direct_parsed_price}")
                        price_result.price = direct_parsed_price
                        price_result.confidence = 1.0
                
                return [{
                    'product_name': product_name,
                    'price_extraction': price_result
                }]
            
        except Exception as e:
            logger.error(f"Error in _extract_products_with_llm for {url}: {e}")
            return [{
                'product_name': product_name,
                'price_extraction': PriceExtractionResult(
                    success=False,
                    error=f"Extraction failed: {str(e)}"
                )
            }]

    async def _extract_with_vision(self, url: str) -> Optional[Dict[str, Any]]:
        """Call vision endpoint to extract fields from a rendered screenshot."""
        try:
            async with WebCrawlerClient() as client:
                resp = await client.extract_vision(
                    url=url,
                    fields=["name", "price", "currency", "availability"],
                    timeout=60000,
                )
                if resp.success and resp.data:
                    return resp.data
                logger.warning(f"Vision extraction failed for {url}: {resp.error}")
                return None
        except Exception as e:
            logger.error(f"Vision extraction error for {url}: {e}")
            return None

    def _coerce_price(self, price_val: Any) -> Optional[float]:
        """Coerce price from string/number to float using existing direct parser where needed."""
        if price_val is None:
            return None
        try:
            return float(price_val)
        except Exception:
            parsed = self._parse_price_directly(str(price_val))
            return parsed

    def _normalize_currency(self, currency: Optional[str]) -> Optional[str]:
        if not currency:
            return None
        c = str(currency).upper().strip()
        if c in ("UYU", "USD", "EUR", "GBP"):
            return c
        # Heuristics
        if c in ("$", "UY$", "U$S", "US$", "U$U"):
            return "UYU" if c in ("$", "UY$", "U$U") else "USD"
        return c

    async def _extract_with_catalog_detection(self, page_content: str, url: str, product_name: str) -> dict:
        """
        Extract products with automatic catalog detection based on actual page content.
        
        Returns either single product format or multi-product catalog format.
        """
        try:
            # Create enhanced system prompt for catalog detection
            system_prompt = self._create_catalog_detection_system_prompt()
            user_prompt = self._create_catalog_detection_user_prompt(page_content, url, product_name)
            
            async with OllamaClient() as llm:
                response = await llm.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model=self.model_name,
                    temperature=self.temperature,
                    num_predict=800,  # Allow more tokens for multi-product responses
                    format="json"
                )
                
                logger.debug(f"Catalog detection LLM response for {url}: {response[:300]}...")
                
                # Parse the response
                cleaned_response = self._clean_json_response(response)
                return json.loads(cleaned_response)
                
        except Exception as e:
            logger.error(f"Catalog detection failed for {url}: {e}")
            # Fallback to single product format
            return {"found": False}
    
    def _create_catalog_detection_system_prompt(self) -> str:
        """Create enhanced system prompt that can handle both single products and catalogs."""
        return """You are an expert at extracting product prices from Uruguay e-commerce websites.

TASK: Analyze page content and extract ALL relevant products with prices.

CONTENT-BASED DETECTION:
- If page shows MULTIPLE products with prices → Extract ALL (catalog/category page)
- If page shows ONE main product with price → Extract that one (product page)

OUTPUT FORMATS:

SINGLE PRODUCT (if only one main product found):
{
  "found": true|false,
  "price": <numeric_value>,
  "currency": "UYU"|"USD",
  "original_text": "<exact_price_text_found>",
  "confidence": <0.0_to_1.0>
}

MULTIPLE PRODUCTS (if multiple products found - CATALOG PAGE):
{
  "products": [
    {
      "product_name": "<full_product_name>",
      "price": <numeric_value>,
      "currency": "UYU"|"USD",
      "original_text": "<exact_price_text_found>", 
      "confidence": <0.0_to_1.0>
    }
  ]
}

CRITICAL PRICE PARSING RULES:
1. "$189" → price: 189.0 (one hundred eighty-nine)
2. "$13.000,00" → price: 13000.0 (thirteen thousand)
3. "$45,50" → price: 45.5 (forty-five point five)
4. NEVER perform mathematical operations

JSON OUTPUT REQUIREMENTS:
- Return VALID JSON only (no comments, no explanations)
- Do NOT use // comments in JSON (invalid JSON)
- Do NOT add explanatory text after commas
- Example: "price": 189.0 (NOT "price": 189.0, // explanation)
5. Extract literal numerical values only

CURRENCY DETECTION:
- $ = UYU (default in Uruguay)
- US$ or USD = USD

For catalog pages, extract UP TO 10 most relevant products that match the search query.
Return ONLY the JSON object - no markdown, no explanations."""

    def _create_catalog_detection_user_prompt(self, content: str, url: str, product_name: str) -> str:
        """Create user prompt for catalog detection."""
        # Use more content for catalog detection
        max_content_length = 3000  # Increased for catalog pages
        truncated_content = content[:max_content_length]
        if len(content) > max_content_length:
            truncated_content += "... [content truncated]"
        
        return f"""URL: {url}
Search Query: {product_name}

ANALYZE this page content. If it's a catalog/category page with multiple products and prices, extract ALL relevant products. If it's a single product page, extract that one product.

Page content:
{truncated_content}

Extract as JSON:"""

    async def _extract_price_with_llm(self, page_content: str, url: str, product_name: str) -> PriceExtractionResult:
        """
        Extract price from page content using LLM.
        
        Args:
            page_content: Full page text content
            url: Page URL for context
            product_name: Product name for context
            
        Returns:
            PriceExtractionResult: Structured price extraction result
        """
        try:
            # Create optimized prompt for Uruguay price extraction
            system_prompt = self._create_system_prompt()
            user_prompt = self._create_user_prompt(page_content, url, product_name)
            
            # Use Ollama client for LLM inference
            async with OllamaClient() as llm:
                response = await llm.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model=self.model_name,
                    temperature=self.temperature,
                    num_predict=300,  # Limit response length
                    format="json"
                )
                
                logger.debug(f"LLM response for {url}: {response[:200]}...")
                
                # Parse LLM response
                return self._parse_llm_response(response)
                
        except Exception as e:
            logger.error(f"LLM price extraction failed for {url}: {e}")
            return PriceExtractionResult(
                success=False,
                error=f"LLM extraction failed: {str(e)}"
            )
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for price extraction."""
        return """You are an expert at extracting product prices from Uruguay e-commerce websites.

TASK: Extract product prices from the given page content.

FOR SINGLE PRODUCT PAGES: Extract the main product price.
FOR CATALOG/CATEGORY PAGES: Extract ALL products with their prices (up to 10 products).

OUTPUT FORMAT: JSON only, no markdown, no explanations

SINGLE PRODUCT:
{
  "found": true|false,
  "price": <numeric_value>,
  "currency": "UYU"|"USD",
  "original_text": "<exact_price_text_found>",
  "confidence": <0.0_to_1.0>
}

MULTIPLE PRODUCTS (for catalog pages):
{
  "products": [
    {
      "product_name": "<product_name>",
      "price": <numeric_value>,
      "currency": "UYU"|"USD", 
      "original_text": "<exact_price_text_found>",
      "confidence": <0.0_to_1.0>
    }
  ]
}

CRITICAL PRICE PARSING RULES:

1. CRITICAL PRICE CONVERSION - FOLLOW EXACTLY:
   - "$189" → price: 189.0 (one hundred eighty-nine)
   - "$220" → price: 220.0 (two hundred twenty)  
   - "$13.000,00" → price: 13000.0 (thirteen thousand - remove dots/commas from thousands)
   - "$1.250" → price: 1250.0 (one thousand two hundred fifty)  
   - "$45,50" → price: 45.5 (forty-five point five - comma is decimal)
   
   RULE: If you see "$189", the price is EXACTLY 189, NOT 45.5, NOT any other number.
   NEVER perform mathematical operations. Extract the literal numerical value.

2. CURRENCY DETECTION:
   - $ = UYU (default in Uruguay)
   - US$ or USD = USD
   - UYU or $ UYU = UYU

3. PRICE SELECTION:
   - Choose current selling price (not crossed-out/old prices)
   - If discount shown, use final discounted price
   - Ignore shipping costs, taxes shown separately

4. DECIMAL HANDLING:
   - In Uruguay: "1.250" = 1250 (dot as thousands separator)
   - In Uruguay: "45,50" = 45.5 (comma as decimal separator)
   - Always return price as a number: 1250, not "1.250"

5. VALIDATION:
   - Price should be reasonable (10-100000 UYU typical range)
   - If price seems wrong, return {"found": false}

If no valid price found, return {"found": false}

Return ONLY the JSON object."""

    def _create_user_prompt(self, content: str, url: str, product_name: str) -> str:
        """Create user prompt with page content."""
        # Truncate content to avoid token limits
        max_content_length = 2000
        truncated_content = content[:max_content_length]
        if len(content) > max_content_length:
            truncated_content += "... [content truncated]"
        
        return f"""URL: {url}
Product Query: {product_name}

Analyze the page content below. If this is a single product page, extract ONE price. If this is a catalog/category page with multiple products, extract ALL relevant products and their prices (up to 10).

Page content:
{truncated_content}

Extract price(s) as JSON:"""

    def _parse_llm_response(self, response: str) -> PriceExtractionResult:
        """
        Parse LLM response into PriceExtractionResult.
        
        Args:
            response: Raw LLM response
            
        Returns:
            PriceExtractionResult: Parsed result
        """
        try:
            # Clean up response (remove markdown formatting if present)
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON
            data = json.loads(cleaned_response)
            
            if not data.get("found", False):
                return PriceExtractionResult(
                    success=False,
                    error="No price found in content"
                )
            
            # Extract and validate price
            price = data.get("price")
            if price is None:
                return PriceExtractionResult(
                    success=False,
                    error="Price value missing from response"
                )
            
            # Convert price to float
            price_float = float(price)
            
            # Validate price range (sanity check)
            if price_float <= 0 or price_float > 1000000:  # Reasonable price range
                return PriceExtractionResult(
                    success=False,
                    error=f"Price {price_float} outside reasonable range"
                )
            
            return PriceExtractionResult(
                success=True,
                price=price_float,
                currency=data.get("currency", "UYU"),
                original_text=data.get("original_text"),
                confidence=data.get("confidence", 0.8)
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}. Response: {response}")
            return PriceExtractionResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}"
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid price value: {e}")
            return PriceExtractionResult(
                success=False,
                error=f"Invalid price value: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return PriceExtractionResult(
                success=False,
                error=f"Parse error: {str(e)}"
            )
    
    def _clean_json_response(self, response: str) -> str:
        """Clean LLM response to extract valid JSON by removing comments and markdown."""
        response = response.strip()
        
        # Remove markdown code blocks
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*$', '', response)
        
        # Find JSON object
        start = response.find('{')
        end = response.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            json_content = response[start:end + 1]
            
            # Remove JSON comments (// text until end of line)
            # This handles cases like: "price": 189.0, // Assuming the currency is USD...
            json_content = re.sub(r'//.*?(?=\n|$)', '', json_content, flags=re.MULTILINE)
            
            # Remove any trailing commas that might be left after comment removal
            json_content = re.sub(r',\s*}', '}', json_content)
            json_content = re.sub(r',\s*]', ']', json_content)
            
            return json_content
        
        return response
    
    def _parse_price_directly(self, price_text: str) -> Optional[float]:
        """Parse price directly from text using regex (bypass LLM errors)."""
        if not price_text:
            return None
        
        import re
        
        # Clean the price text
        price_text = price_text.strip()
        
        # Extract numeric part - handle Uruguay formats
        # Patterns: $189, $13.000,00, $1.250, $45,50, UYU 220, etc.
        
        # Remove currency symbols and spaces
        numeric_part = re.sub(r'[UYU$\s]', '', price_text)
        
        # Handle different decimal/thousand separator patterns
        if ',' in numeric_part and '.' in numeric_part:
            # Format like 13.000,50 (thousands with dots, decimals with comma)
            numeric_part = numeric_part.replace('.', '').replace(',', '.')
        elif ',' in numeric_part and numeric_part.count(',') == 1:
            # Check if comma is decimal separator (like 45,50) or thousands (like 1,250)
            parts = numeric_part.split(',')
            if len(parts[1]) <= 2:  # Decimal separator
                numeric_part = numeric_part.replace(',', '.')
            else:  # Thousands separator
                numeric_part = numeric_part.replace(',', '')
        elif '.' in numeric_part and numeric_part.count('.') == 1:
            # Check if dot is decimal or thousands separator
            parts = numeric_part.split('.')
            if len(parts[1]) <= 2:  # Likely decimal
                pass  # Keep as is
            else:  # Likely thousands separator
                numeric_part = numeric_part.replace('.', '')
        
        try:
            parsed_price = float(numeric_part)
            logger.debug(f"Direct price parsing: '{price_text}' → {parsed_price}")
            return parsed_price
        except (ValueError, TypeError):
            logger.warning(f"Could not parse price directly from: '{price_text}'")
            return None 