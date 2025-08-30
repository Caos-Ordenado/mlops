"""
Pipeline-Enabled Product Search Agent: High-performance concurrent processing.

This module implements the pipeline-enabled version of the ProductSearchAgent
using Solution 2: Pipeline Processing with Async Queues for maximum throughput.
"""

import asyncio
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from shared.logging import setup_logger
from .pipeline_processor import PipelineProcessor, PipelineStage
from .pipeline_stages import PipelineStageProcessors
from src.api.models import ProductSearchRequest, ProductWithPrice

logger = setup_logger("pipeline_agent")

class PipelineProductSearchAgent:
    """
    High-performance Product Search Agent with concurrent pipeline processing.
    
    Features:
    - Concurrent processing of multiple search requests
    - Queue-based pipeline stages for maximum throughput
    - Load balancing across pipeline workers
    - Real-time performance monitoring
    - Graceful fallback to sequential processing if needed
    """
    
    def __init__(self,
                 max_concurrent_searches: int = 5,
                 enable_pipeline: bool = True,
                 pipeline_timeout: int = 120):
        """
        Initialize pipeline-enabled search agent.
        
        Args:
            max_concurrent_searches: Maximum concurrent search requests
            enable_pipeline: Whether to use pipeline processing (fallback to sequential if False)
            pipeline_timeout: Timeout for pipeline processing in seconds
        """
        self.max_concurrent_searches = max_concurrent_searches
        self.enable_pipeline = enable_pipeline
        self.pipeline_timeout = pipeline_timeout
        
        # Pipeline components
        self.pipeline_processor: Optional[PipelineProcessor] = None
        self.stage_processors: Optional[PipelineStageProcessors] = None
        
        # Fallback to sequential agent if needed
        self.sequential_agent = None
        
        # Performance tracking
        self.search_stats = {
            "total_searches": 0,
            "pipeline_searches": 0,
            "sequential_searches": 0,
            "avg_response_time": 0.0,
            "concurrent_searches_active": 0
        }
        
        logger.info(f"PipelineProductSearchAgent initialized: "
                   f"max_concurrent={max_concurrent_searches}, "
                   f"pipeline_enabled={enable_pipeline}")
    
    async def search_product(self, request: ProductSearchRequest) -> List[ProductWithPrice]:
        """
        Search for products using high-performance pipeline processing.
        
        Args:
            request: Product search request
            
        Returns:
            List of products with prices
        """
        self.search_stats["total_searches"] += 1
        
        if self.enable_pipeline and self.pipeline_processor:
            return await self._search_with_pipeline(request)
        else:
            return await self._search_sequential_fallback(request)
    
    async def search_multiple(self, requests: List[ProductSearchRequest]) -> List[List[ProductWithPrice]]:
        """
        Process multiple search requests concurrently.
        
        Args:
            requests: List of search requests
            
        Returns:
            List of search results (one per request)
        """
        if not requests:
            return []
        
        logger.info(f"🚀 PIPELINE: Processing {len(requests)} concurrent search requests")
        
        if self.enable_pipeline and self.pipeline_processor:
            return await self._search_multiple_with_pipeline(requests)
        else:
            return await self._search_multiple_sequential(requests)
    
    async def _search_with_pipeline(self, request: ProductSearchRequest) -> List[ProductWithPrice]:
        """Search using pipeline processing."""
        try:
            self.search_stats["pipeline_searches"] += 1
            self.search_stats["concurrent_searches_active"] += 1
            
            logger.info(f"🚀 PIPELINE: Starting search for '{request.query}' (country: {request.country})")
            
            # Submit job to pipeline
            job_id = await self.pipeline_processor.submit_search(request)
            
            # Wait for results
            job = await self.pipeline_processor.get_result(job_id, timeout=self.pipeline_timeout)
            
            if job and job.final_products:
                logger.info(f"✅ PIPELINE: Search completed for '{request.query}' - {len(job.final_products)} products found")
                return job.final_products
            elif job and job.error:
                logger.error(f"❌ PIPELINE: Search failed for '{request.query}': {job.error}")
                # Fallback to sequential processing
                return await self._search_sequential_fallback(request)
            else:
                logger.warning(f"⏰ PIPELINE: Search timed out for '{request.query}' - falling back to sequential")
                return await self._search_sequential_fallback(request)
                
        except Exception as e:
            logger.error(f"❌ PIPELINE: Error processing '{request.query}': {e}")
            return await self._search_sequential_fallback(request)
        finally:
            self.search_stats["concurrent_searches_active"] -= 1
    
    async def _search_multiple_with_pipeline(self, requests: List[ProductSearchRequest]) -> List[List[ProductWithPrice]]:
        """Process multiple requests using pipeline."""
        try:
            # Submit all jobs to pipeline
            job_ids = []
            for request in requests:
                job_id = await self.pipeline_processor.submit_search(request)
                job_ids.append(job_id)
            
            logger.info(f"🚀 PIPELINE: Submitted {len(job_ids)} jobs to pipeline")
            
            # Collect results
            results = []
            for i, job_id in enumerate(job_ids):
                job = await self.pipeline_processor.get_result(job_id, timeout=self.pipeline_timeout)
                
                if job and job.final_products:
                    results.append(job.final_products)
                    logger.debug(f"✅ Job {i+1}/{len(job_ids)} completed: {len(job.final_products)} products")
                else:
                    logger.warning(f"⚠️ Job {i+1}/{len(job_ids)} failed or timed out")
                    results.append([])
            
            successful_jobs = sum(1 for r in results if r)
            logger.info(f"🎯 PIPELINE: Completed {successful_jobs}/{len(requests)} searches successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ PIPELINE: Error processing multiple requests: {e}")
            # Fallback to sequential processing
            return await self._search_multiple_sequential(requests)
    
    async def _search_sequential_fallback(self, request: ProductSearchRequest) -> List[ProductWithPrice]:
        """Fallback to sequential processing."""
        if not self.sequential_agent:
            # Import here to avoid circular imports
            from .agent import ProductSearchAgent
            self.sequential_agent = ProductSearchAgent(country=request.country, city=request.city)
        
        self.search_stats["sequential_searches"] += 1
        logger.debug(f"📎 FALLBACK: Using sequential processing for '{request.query}'")
        
        async with self.sequential_agent as agent:
            # Original agent returns tuple: (valid_queries, validation_attempts, extracted_candidates, identified_pages, extracted_prices)
            # We only need the extracted_prices (index 4)
            result = await agent.search_product(request.query)
            if isinstance(result, tuple) and len(result) >= 5:
                extracted_prices = result[4]  # Get the products with prices
                return extracted_prices if extracted_prices else []
            else:
                logger.warning(f"Unexpected result format from sequential agent: {type(result)}")
                return []
    
    async def _search_multiple_sequential(self, requests: List[ProductSearchRequest]) -> List[List[ProductWithPrice]]:
        """Process multiple requests sequentially."""
        logger.info(f"📎 FALLBACK: Processing {len(requests)} requests sequentially")
        
        results = []
        for i, request in enumerate(requests):
            result = await self._search_sequential_fallback(request)
            results.append(result)
            logger.debug(f"Sequential processing: {i+1}/{len(requests)} completed")
        
        return results
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline performance metrics."""
        base_metrics = {
            "search_stats": self.search_stats.copy(),
            "pipeline_enabled": self.enable_pipeline,
            "max_concurrent_searches": self.max_concurrent_searches
        }
        
        if self.pipeline_processor:
            pipeline_metrics = self.pipeline_processor.get_metrics()
            base_metrics.update(pipeline_metrics)
        
        return base_metrics
    
    async def __aenter__(self) -> 'PipelineProductSearchAgent':
        """Async context manager entry."""
        if self.enable_pipeline:
            try:
                # Initialize pipeline components
                self.stage_processors = PipelineStageProcessors()
                await self.stage_processors.__aenter__()
                
                # Initialize pipeline processor
                self.pipeline_processor = PipelineProcessor(
                    max_concurrent_jobs=self.max_concurrent_searches,
                    queue_size=50,
                    max_retries=2,
                    stage_timeout=60
                )
                
                # Register stage processors
                self.pipeline_processor.register_stage_processor(
                    PipelineStage.QUERY_GENERATION,
                    self.stage_processors.process_query_generation
                )
                self.pipeline_processor.register_stage_processor(
                    PipelineStage.URL_EXTRACTION,
                    self.stage_processors.process_url_extraction
                )
                self.pipeline_processor.register_stage_processor(
                    PipelineStage.PAGE_IDENTIFICATION,
                    self.stage_processors.process_page_identification
                )
                self.pipeline_processor.register_stage_processor(
                    PipelineStage.PRICE_EXTRACTION,
                    self.stage_processors.process_price_extraction
                )
                
                # Start pipeline
                await self.pipeline_processor.start_pipeline()
                
                logger.info("🚀 Pipeline Product Search Agent ready - concurrent processing enabled")
                
            except Exception as e:
                logger.error(f"Failed to initialize pipeline: {e}. Falling back to sequential processing.")
                self.enable_pipeline = False
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self.pipeline_processor:
            await self.pipeline_processor.stop_pipeline()
        
        if self.stage_processors:
            await self.stage_processors.__aexit__(exc_type, exc_val, exc_tb)
        
        if self.sequential_agent:
            await self.sequential_agent.__aexit__(exc_type, exc_val, exc_tb)
        
        logger.info("Pipeline Product Search Agent stopped")
