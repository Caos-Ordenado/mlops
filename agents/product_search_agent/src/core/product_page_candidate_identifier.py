import asyncio
import json
from typing import List, Dict, Any
import re
import httpx # For potential errors from OllamaClient

from shared.logging import setup_logger
from shared.ollama_client import OllamaClient
from src.api.models import ExtractedUrlInfo, IdentifiedPageCandidate

logger = setup_logger("product_page_candidate_identifier")

def strip_json_code_block(text: str) -> str:
    text = text.strip()
    
    # Regex to find content within ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match:
        # If found, return the stripped content of the first capturing group
        text = match.group(1).strip()

    # Python-native extraction of the first {...} or [...] block (handles nesting)
    def extract_first_json_block(s):
        start = None
        stack = []
        for i, c in enumerate(s):
            if c in '{[':
                if start is None:
                    start = i
                stack.append(c)
            elif c in '}]' and stack:
                open_c = stack.pop()
                if not stack:
                    # Found the matching closing bracket
                    return s[start:i+1]
        return s.strip()  # fallback: return original

    return extract_first_json_block(text)

def remove_json_comments(s):
    # Remove // ... comments
    s = re.sub(r'//.*', '', s)
    # Remove /* ... */ block comments
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
    return s

class ProductPageCandidateIdentifierAgent:
    def __init__(self, model_name="phi3", temperature=0.1):
        self.model_name = model_name
        self.temperature = temperature
        logger.info(f"ProductPageCandidateIdentifierAgent initialized with model: {model_name}, temp: {temperature}")

    async def __aenter__(self):
        logger.debug("ProductPageCandidateIdentifierAgent context entered")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("ProductPageCandidateIdentifierAgent context exited")

    async def _classify_url_with_llm(self, url_info: ExtractedUrlInfo, product_name: str) -> IdentifiedPageCandidate:
        system_prompt = f"""
You are an AI assistant that analyzes web page content (title, URL, and a snippet of text) to determine if it's a product page, a category page, a blog post, or 'other'.
You are also given the original product name the user is searching for: "{product_name}"

IMPORTANT GEOGRAPHIC FILTERING REQUIREMENTS:
- Only consider results for Uruguay.
- Exclude any URL where the domain ends with a country code that is not .uy (e.g., .ar, .es, .pt, .cl, .mx, .br, etc.)
- If the domain is .com, .net, .org, etc. (no country code), only accept if the URL path or domain contains 'uruguay', '/uy/', or another clear Uruguay indicator like Montevideo.
- If the URL does not have any Uruguay indicator, EXCLUDE it.
- Only classify as PRODUCT, CATEGORY, BLOG, or OTHER if the URL passes these Uruguay checks; otherwise, return page_type: 'EXCLUDE_NON_URUGUAY'.
- Never include or classify non-Uruguay results, even if the product matches.

Examples:
VALID:
- https://www.climasyviajes.com/clima/uruguay  (contains 'uruguay' in the path)
- https://www.compracompras.com/uy/lista/202381/pegamentos/  (contains '/uy/' in the path)
- https://paraguas.com.uy/producto/paraguas-vicenzo-windproof/ (domain ends with .uy)
INVALID:
- https://www.montagne.com.ar/categoria/12-camperas-de-hombre (.ar domain)
- https://www.decathlon.es/es/colecciones/calzado-impermeable (.es domain and /es/ path)
- https://shopix.com.ar/comprar-campera-nike-impermeable_pg_2 (.ar domain)
- https://www.campingcenter.com.ar/ropa-y-calzado/mujer/impermeable1/ (.ar domain)
- https://www.columbiasportswear.pt/es_CL/c/footwear-winter (.pt domain and /es_CL/ path)
- https://listado.mercadolibre.com.ar/camperas-de-invierno-impermeables-mujer (.ar domain)
- https://www.menshealth.com/es/moda-cuidados-hombre/a62734210/decathlon-botas-invierno-impermeables-comodas-hombre/ (/es/ path)

Respond with a JSON object containing ONLY the following fields:
- "page_type": (string) One of "PRODUCT", "CATEGORY", "BLOG", "OTHER", or "EXCLUDE_NON_URUGUAY" (if the URL is not for Uruguay).
- "identified_product_name": (string, OPTIONAL) If page_type is "PRODUCT", the product name identified on the page. Otherwise omit.
- "category_name": (string, OPTIONAL) If page_type is "CATEGORY", the name of the category. Otherwise omit.
- "reasoning": (string, OPTIONAL) A brief explanation for your classification.

Example for a PRODUCT page:
{{
  "page_type": "PRODUCT",
  "identified_product_name": "Specific Product Model X",
  "reasoning": "Page title and snippet suggest a specific product."
}}

Example for a CATEGORY page:
{{
  "page_type": "CATEGORY",
  "category_name": "Winter Jackets",
  "reasoning": "Lists multiple winter jackets."
}}

Example for EXCLUDE_NON_URUGUAY:
{{
  "page_type": "EXCLUDE_NON_URUGUAY",
  "reasoning": "The domain ends with .es, which is not Uruguay, or there is no Uruguay indicator in the URL."
}}

IMPORTANT: Only classify a page as "PRODUCT" if it is an individual product page, not a category, collection, or listing page.
- If the page lists multiple products, or is a category/collection/search result, classify as "CATEGORY" or "EXCLUDE_NON_PRODUCT".
- Only classify as "PRODUCT" if the page is dedicated to a single product, with specific details, price, and purchase options for that product.
- Example PRODUCT: A page for "Columbia Impermeable Invierno Modelo XYZ" with price and buy button.
- Example CATEGORY: A page listing many "impermeables invierno" with filters or multiple products.
- This is important so the price extractor agent can reliably extract a price for a single product.

Focus on the provided snippet, title, and URL.
URL: {url_info.url}
Title: {url_info.title}
Snippet: {url_info.snippet}
User's product query: "{product_name}"

Remember: Do NOT include any comments, explanations, or text outside or inside the JSON object. Do NOT use // or /* */ or any other comment syntax. Only output valid JSON.
"""
        user_prompt = f"Analyze the following web page information based on the user's query for '{product_name}':\nURL: {url_info.url}\nTitle: {url_info.title}\nSnippet: {url_info.snippet}\nReturn ONLY the JSON object as specified in the system instructions."

        response_text = ""
        cleaned_response_text = ""
        response_data = None

        try:
            async with OllamaClient() as llm:
                response_text = await llm.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model=self.model_name,
                    temperature=self.temperature
                )
            logger.debug(f"LLM raw response for {url_info.url}: {response_text}")
            cleaned_response_text = strip_json_code_block(response_text)
            cleaned_response_text = remove_json_comments(cleaned_response_text)
            
            try: # Attempt 1: json.loads on the whole cleaned text
                response_data = json.loads(cleaned_response_text)
            except json.JSONDecodeError as main_jde: # If json.loads fails
                logger.warning(f"Initial JSONDecodeError for {url_info.url} ('{main_jde}'). Trying to parse first object with raw_decode.")
                try:
                    # Attempt 2: Try to parse only the first JSON object from the string
                    first_json_obj, end_index = json.JSONDecoder().raw_decode(cleaned_response_text)
                    
                    # Log if there was actually any significant trailing data
                    trailing_data = cleaned_response_text[end_index:].strip()
                    if trailing_data:
                        logger.warning(f"raw_decode for {url_info.url} successful, but found trailing data (first 200 chars): '{trailing_data[:200]}...'" )
                    else:
                        logger.info(f"raw_decode for {url_info.url} successful. No significant trailing data.")
                    response_data = first_json_obj # Use the successfully parsed first object
                except json.JSONDecodeError as raw_decode_jde:
                    # If raw_decode also fails, the original main_jde is more indicative of the problem
                    # with the initial part of the string. Log this failure and re-raise main_jde.
                    logger.error(f"raw_decode also failed for {url_info.url} after initial error. Raw_decode error: '{raw_decode_jde}'. Original cleaned text: {cleaned_response_text}")
                    raise main_jde from raw_decode_jde # Re-raise the original error to be caught by the outer handler
            
        except json.JSONDecodeError as jde: # Catches main_jde if raw_decode also failed or if json.loads failed for other reasons initially
            logger.error(f"Final JSONDecodeError for {url_info.url}: {jde}. Cleaned text was: {cleaned_response_text}")
            return IdentifiedPageCandidate(
                original_url_info=url_info,
                analysis_details={"error": "JSONDecodeError", "message": str(jde), "raw_response": response_text, "cleaned_attempt": cleaned_response_text},
                page_type="ERROR_PARSING_JSON",
                reasoning=f"Failed to parse LLM JSON response: {str(jde)}"
            )
        except httpx.HTTPStatusError as hse:
            logger.error(f"HTTPStatusError calling LLM for {url_info.url}: {hse.response.status_code} - {hse.response.text}", exc_info=True)
            return IdentifiedPageCandidate(
                original_url_info=url_info,
                analysis_details={"error": f"HTTPStatusError: {hse.response.status_code}", "response_text": hse.response.text, "raw_llm_response_attempt": response_text},
                page_type="ERROR_LLM_HTTP",
                reasoning=f"HTTPStatusError while calling LLM: {hse.response.status_code}"
            )
        except Exception as e_llm_comm: # Catch other errors during LLM communication/parsing
            logger.error(f"Unexpected error during LLM communication or JSON parsing for {url_info.url}: {e_llm_comm}", exc_info=True)
            return IdentifiedPageCandidate(
                original_url_info=url_info,
                analysis_details={"error": "LLM communication/parsing error", "exception_type": type(e_llm_comm).__name__, "exception_message": str(e_llm_comm), "raw_llm_response_attempt": response_text, "cleaned_attempt": cleaned_response_text},
                page_type="ERROR_LLM_UNEXPECTED_COMM",
                reasoning=f"Unexpected error during LLM call or parsing: {str(e_llm_comm)}"
            )

        # If we've reached here, LLM call and JSON parsing were successful and response_data is populated.
        # Now, extract data and attempt to create IdentifiedPageCandidate.
        # Errors in this section (KeyError from .get, Pydantic ValidationError during construction) should propagate.

        page_type_from_llm = response_data.get("page_type")
        if page_type_from_llm is None:
            logger.warning(f"LLM response for {url_info.url} had null page_type. Defaulting to 'ERROR_LLM_NULL_PAGE_TYPE'. Raw response_data: {response_data}")
            final_page_type = "ERROR_LLM_NULL_PAGE_TYPE"
        else:
            final_page_type = str(page_type_from_llm)

        # Extract optional fields from LLM response
        llm_reasoning = response_data.get("reasoning")
        llm_identified_product_name = response_data.get("identified_product_name")
        llm_category_name = response_data.get("category_name")
            
        try:
            candidate = IdentifiedPageCandidate(
                # Fields from ExtractedUrlInfo
                url=url_info.url,
                original_title=url_info.title,
                original_snippet=url_info.snippet,
                source_query=url_info.source_query,

                # Fields from LLM
                page_type=final_page_type,
                reasoning=llm_reasoning,
                identified_product_name=llm_identified_product_name,
                category_name=llm_category_name
            )
            return candidate
        except Exception as e_candidate_creation: # Catch Pydantic ValidationErrors or other issues
            logger.error(f"Critical error during IdentifiedPageCandidate creation for {url_info.url}: {e_candidate_creation}", exc_info=True)
            logger.error(f"Data for failing IdentifiedPageCandidate: url_info: {url_info.model_dump_json()}, llm_response_data: {response_data}")
            raise 

    async def identify_batch_page_types(
        self, 
        extracted_urls: List[ExtractedUrlInfo], 
        product_name: str,
        batch_size: int = 2,
        delay_between_batches: float = 0.01 # seconds
    ) -> List[IdentifiedPageCandidate]:
        identified_candidates: List[IdentifiedPageCandidate] = []
        if not extracted_urls:
            return identified_candidates
            
        for i in range(0, len(extracted_urls), batch_size):
            batch_of_url_info = extracted_urls[i:i+batch_size] # Renamed for clarity
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(extracted_urls) + batch_size - 1)//batch_size} for page type identification.")
            
            tasks = [self._classify_url_with_llm(url_info, product_name) for url_info in batch_of_url_info]
            
            # Use return_exceptions=True to get exceptions as results instead of raising immediately
            results_or_exceptions = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, res_or_exc in enumerate(results_or_exceptions):
                current_url_info = batch_of_url_info[idx] # Get corresponding url_info for context
                if isinstance(res_or_exc, Exception):
                    # This is an exception that was raised from _classify_url_with_llm 
                    # (e.g., Pydantic ValidationError or KeyError during IdentifiedPageCandidate creation)
                    logger.error(f"Exception for URL {current_url_info.url} in batch {i//batch_size + 1}: {res_or_exc}", exc_info=res_or_exc) # Log with traceback
                    identified_candidates.append(IdentifiedPageCandidate(
                        original_url_info=current_url_info,
                        analysis_details={ 
                            "error_summary": "Candidate creation/validation failed in _classify_url_with_llm", 
                            "exception_type": type(res_or_exc).__name__,
                            "exception_message": str(res_or_exc) 
                        },
                        page_type="ERROR_CANDIDATE_INSTANTIATION",
                        reasoning=f"Failed during candidate object creation: {type(res_or_exc).__name__}"
                    ))
                elif isinstance(res_or_exc, IdentifiedPageCandidate): # This is a successfully created candidate or an error object returned by _classify_url_with_llm
                    identified_candidates.append(res_or_exc)
                else:
                    # Should not happen if _classify_url_with_llm always returns IdentifiedPageCandidate or raises Exception
                    logger.error(f"Unexpected result type for URL {current_url_info.url} in batch {i//batch_size + 1}: {type(res_or_exc)}", exc_info=True)
                    identified_candidates.append(IdentifiedPageCandidate(
                        original_url_info=current_url_info,
                        analysis_details={ 
                            "error_summary": "Unexpected result type from _classify_url_with_llm", 
                            "result_type": str(type(res_or_exc))
                        },
                        page_type="ERROR_UNEXPECTED_RESULT_TYPE",
                        reasoning="Internal error: Unexpected result type from classification task."
                    ))
            
            if i + batch_size < len(extracted_urls):
                logger.debug(f"Waiting for {delay_between_batches}s before next batch.")
                await asyncio.sleep(delay_between_batches)
                
        logger.info(f"Identified page types for {len(identified_candidates)} URLs (may include error objects).")

        # Filter out error candidates (e.g., those with page_type starting with 'ERROR_')
        successful_candidates = []
        for candidate in identified_candidates:
            if hasattr(candidate, 'page_type') and isinstance(candidate.page_type, str) and candidate.page_type.startswith("ERROR_"):
                url = getattr(candidate, 'url', None)
                orig_url_info = getattr(candidate, 'original_url_info', None)
                url_to_log = url or (orig_url_info.url if orig_url_info and hasattr(orig_url_info, 'url') else None)
                logger.warning(f"Skipping candidate for URL {url_to_log} due to error page_type: {candidate.page_type}")
            else:
                successful_candidates.append(candidate)

        logger.info(f"Returning {len(successful_candidates)} successfully identified page candidates (excluded {len(identified_candidates) - len(successful_candidates)} errors).")
        return successful_candidates 