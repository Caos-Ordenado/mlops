from typing import List, Optional, Dict, Any
from shared.logging import setup_logger
from src.api.models import BraveSearchResult, ExtractedUrlInfo, BraveApiHit

logger = setup_logger("url_extractor_agent")

class UrlExtractorAgent:
    def __init__(self):
        logger.info("UrlExtractorAgent initialized - CONSTRUCTOR CALLED V3")

    async def __aenter__(self):
        logger.debug("Entering UrlExtractorAgent context")
        # No external resources to manage for now
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("Exiting UrlExtractorAgent context")
        # No external resources to clean up

    def extract_product_url_info(self, all_brave_results: Optional[List[BraveSearchResult]]) -> List[ExtractedUrlInfo]:
        if not all_brave_results:
            return []

        extracted_candidates: List[ExtractedUrlInfo] = []
        for brave_result_item in all_brave_results:
            if not brave_result_item.results: # This is the raw dict from Brave API for a single query
                continue

            # Brave Search API typically nests web results under a 'web' key, which then has a 'results' list.
            # Other types like 'videos', 'images', 'news' might also exist at the same level as 'web'.
            # We are primarily interested in the 'web' -> 'results' array.
            web_search_results = brave_result_item.results.get('web', {}).get('results', [])
            
            if not isinstance(web_search_results, list):
                logger.warning(f"Expected a list for web_search_results for query '{brave_result_item.query}', but got {type(web_search_results)}. Skipping.")
                continue

            for hit_data in web_search_results:
                if not isinstance(hit_data, dict):
                    logger.warning(f"Skipping non-dictionary item in Brave web search results: {hit_data} for query '{brave_result_item.query}'")
                    continue
                
                # Use Pydantic model for safer access and type checking
                try:
                    brave_hit = BraveApiHit(**hit_data)
                    if brave_hit.url:
                        extracted_candidates.append(
                            ExtractedUrlInfo(
                                url=brave_hit.url,
                                title=brave_hit.title,
                                snippet=brave_hit.description, # Brave uses 'description' for snippet
                                source_query=brave_result_item.query
                            )
                        )
                    else:
                        logger.debug(f"Skipping Brave hit with no URL: {brave_hit.title or 'No Title'} for query '{brave_result_item.query}'")
                except Exception as e: # Catch Pydantic validation errors or other issues
                    logger.warning(f"Could not parse Brave hit data: {hit_data} for query '{brave_result_item.query}'. Error: {e}")
        
        logger.info(f"Extracted {len(extracted_candidates)} candidate URLs from Brave results.")
        return extracted_candidates 