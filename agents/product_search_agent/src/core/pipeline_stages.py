"""
Pipeline Stage Processors: Individual stage handlers for the async pipeline.

This module contains the stage processor functions that handle each phase
of the product search pipeline in the concurrent processing system.
"""

import asyncio
from typing import List, Optional

from shared.logging import setup_logger
from .pipeline_processor import PipelineJob, PipelineStage
from .query_generator import QueryGeneratorAgent
from .search_agent import SearchAgent  
from .url_extractor_agent import UrlExtractorAgent
from .product_page_candidate_identifier import ProductPageCandidateIdentifierAgent
from .price_extractor import PriceExtractorAgent
from .category_expansion_agent import CategoryExpansionAgent
from src.api.models import BraveSearchResult, ExtractedUrlInfo, IdentifiedPageCandidate, ProductWithPrice

logger = setup_logger("pipeline_stages")

class PipelineStageProcessors:
    """
    Collection of stage processor functions for the pipeline.
    
    Each processor is designed to be called by pipeline workers and
    handles one specific stage of the product search process.
    """
    
    def __init__(self):
        """Initialize stage processors with agent instances."""
        self.query_generator = QueryGeneratorAgent()
        self.search_agent = SearchAgent()
        self.url_extractor = UrlExtractorAgent(llm_threshold=20)
        self.page_identifier = ProductPageCandidateIdentifierAgent()
        self.price_extractor = PriceExtractorAgent()
        self.category_expander = CategoryExpansionAgent()
        
        logger.info("Pipeline stage processors initialized")
    
    async def process_query_generation(self, job: PipelineJob) -> List[BraveSearchResult]:
        """
        Stage 1: Query Generation and Search
        
        Generates optimized search queries and performs web search.
        
        Args:
            job: Pipeline job with search request
            
        Returns:
            List of search results
        """
        request = job.request
        
        logger.debug(f"Stage 1 - Query Generation for job {job.job_id}: '{request.query}'")
        
        try:
            # Generate optimized queries (agents already initialized in __aenter__)
            generated_queries, _ = await self.query_generator.generate_queries(
                product=request.query
            )
            
            logger.debug(f"Generated {len(generated_queries)} queries for job {job.job_id}")
            
            # Perform web search with generated queries
            # Use all generated queries (typically 5 as per system prompt)
            query_strings = generated_queries
            
            # Use aggregate_search like the original agent
            search_results = await self.search_agent.aggregate_search(query_strings)
            
            # Return BraveSearchResult objects (what url_extractor expects)
            logger.info(f"Stage 1 complete for job {job.job_id}: {len(search_results)} search result objects")
            return search_results
            
        except Exception as e:
            logger.error(f"Stage 1 failed for job {job.job_id}: {e}")
            raise
    
    async def process_url_extraction(self, job: PipelineJob) -> List[ExtractedUrlInfo]:
        """
        Stage 2: URL Extraction and Pre-filtering
        
        Extracts and filters URLs from search results.
        
        Args:
            job: Pipeline job with search results
            
        Returns:
            List of extracted and filtered URLs
        """
        logger.debug(f"Stage 2 - URL Extraction for job {job.job_id}")
        
        if not job.search_results:
            logger.warning(f"No search results for job {job.job_id}")
            return []
        
        try:
            # Extract URLs with pre-filtering optimization
            extracted_urls = await self.url_extractor.extract_product_url_info(job.search_results)
            
            logger.info(f"Stage 2 complete for job {job.job_id}: {len(extracted_urls)} URLs extracted")
            return extracted_urls
            
        except Exception as e:
            logger.error(f"Stage 2 failed for job {job.job_id}: {e}")
            raise
    
    async def process_page_identification(self, job: PipelineJob) -> List[IdentifiedPageCandidate]:
        """
        Stage 3: Page Type Identification
        
        Identifies whether URLs are product pages, category pages, or neither.
        
        Args:
            job: Pipeline job with extracted URLs
            
        Returns:
            List of identified page candidates
        """
        logger.debug(f"Stage 3 - Page Identification for job {job.job_id}")
        
        if not job.extracted_urls:
            logger.warning(f"No extracted URLs for job {job.job_id}")
            return []
        
        try:
            # Identify page types (already optimized with batch processing)
            identified_pages = await self.page_identifier.identify_batch_page_types(job.extracted_urls, job.request.query)
            
            # Expand category pages to find more product URLs
            category_pages = [
                page for page in identified_pages 
                if page.page_type == "CATEGORY"
            ]
            
            if category_pages:
                logger.debug(f"Expanding {len(category_pages)} category pages for job {job.job_id}")
                
                category_urls = [page.url for page in category_pages]
                # Extract query terms for dynamic product URL filtering
                query_terms = job.request.query.split() if hasattr(job.request, 'query') and job.request.query else None
                expanded_urls = await self.category_expander.expand(category_urls, query_terms)
                
                if expanded_urls:
                    # Convert expanded URLs to ExtractedUrlInfo for processing
                    expanded_url_info = [
                        ExtractedUrlInfo(
                            url=url,
                            source_query=job.request.query,
                            original_title=f"Expanded from category",
                            original_snippet=""
                        )
                        for url in expanded_urls[:10]  # Limit for performance
                    ]
                    
                    # Identify the expanded URLs
                    expanded_identified = await self.page_identifier.identify_batch_page_types(expanded_url_info, job.request.query)
                    
                    # Add product pages from expansion
                    product_pages_from_expansion = [
                        page for page in expanded_identified 
                        if page.page_type == "PRODUCT"
                    ]
                    
                    identified_pages.extend(product_pages_from_expansion)
                    logger.debug(f"Added {len(product_pages_from_expansion)} product pages from category expansion")
            
            logger.info(f"Stage 3 complete for job {job.job_id}: {len(identified_pages)} pages identified")
            return identified_pages
            
        except Exception as e:
            logger.error(f"Stage 3 failed for job {job.job_id}: {e}")
            raise
    
    async def process_price_extraction(self, job: PipelineJob) -> List[ProductWithPrice]:
        """
        Stage 4: Price Extraction
        
        Extracts prices from identified product pages using batch content retrieval.
        
        Args:
            job: Pipeline job with identified pages
            
        Returns:
            List of products with extracted prices
        """
        logger.debug(f"Stage 4 - Price Extraction for job {job.job_id}")
        
        if not job.identified_pages:
            logger.warning(f"No identified pages for job {job.job_id}")
            return []
        
        try:
            # Extract prices using optimized batch retrieval
            products_with_prices = await self.price_extractor.extract_prices(job.identified_pages)
            
            logger.info(f"Stage 4 complete for job {job.job_id}: {len(products_with_prices)} products with prices")
            return products_with_prices
            
        except Exception as e:
            logger.error(f"Stage 4 failed for job {job.job_id}: {e}")
            raise
    
    async def __aenter__(self) -> 'PipelineStageProcessors':
        """Async context manager entry."""
        # Initialize all agents
        await self.query_generator.__aenter__()
        await self.search_agent.__aenter__()
        await self.url_extractor.__aenter__()
        await self.page_identifier.__aenter__()
        await self.price_extractor.__aenter__()
        
        logger.debug("Pipeline stage processors context entered")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        # Clean up all agents
        await self.query_generator.__aexit__(exc_type, exc_val, exc_tb)
        await self.search_agent.__aexit__(exc_type, exc_val, exc_tb)
        await self.url_extractor.__aexit__(exc_type, exc_val, exc_tb)
        await self.page_identifier.__aexit__(exc_type, exc_val, exc_tb)
        await self.price_extractor.__aexit__(exc_type, exc_val, exc_tb)
        
        logger.debug("Pipeline stage processors context exited")
