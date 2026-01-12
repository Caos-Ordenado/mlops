import time
from fastapi import APIRouter, HTTPException, Query, Body
from src.api.models import (
    ProductSearchResponse, ProductSearchRequest,
    PipelineSearchRequest, PipelineSearchResponse,
    MultiplePipelineSearchRequest, MultiplePipelineSearchResponse
)
from src.core.agent import ProductSearchAgent
from src.core.pipeline_agent import PipelineProductSearchAgent
from shared.logging import setup_logger

router = APIRouter()
logger = setup_logger("product_search_api.routes")

# Global pipeline agent instance for reuse
_pipeline_agent: PipelineProductSearchAgent = None


@router.get("/search", response_model=ProductSearchResponse)
async def search(
    product: str = Query(..., description="Product to search for"),
    country: str = Query(
        "UY",
        description="Country code for geographic URL validation (e.g., UY, AR, BR, CL, CO, PE, EC, MX, US, ES)",
    ),
    city: str | None = Query(None, description="Optional city name for more specific geographic validation"),
):
    try:
        async with ProductSearchAgent(country=country, city=city) as agent:
            (
                api_results,
                validation_attempts,
                extracted_candidates,
                identified_page_candidates,
                extracted_prices,
            ) = await agent.search_product(product)

        return ProductSearchResponse(
            success=True,
            results=api_results,
            validation_attempts=validation_attempts,
            extracted_product_candidates=extracted_candidates,
            identified_page_candidates=identified_page_candidates,
            extracted_prices=extracted_prices,
        )
    except Exception as e:
        logger.error(f"Error in /search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "ok"}


async def _get_pipeline_agent() -> PipelineProductSearchAgent:
    """Get or create the global pipeline agent instance."""
    global _pipeline_agent
    if _pipeline_agent is None:
        _pipeline_agent = PipelineProductSearchAgent(
            max_concurrent_searches=5,
            enable_pipeline=True,
            pipeline_timeout=120
        )
        await _pipeline_agent.__aenter__()
    return _pipeline_agent


@router.post("/pipeline/search", response_model=PipelineSearchResponse)
async def pipeline_search(request: PipelineSearchRequest = Body(...)):
    """
    🚀 HIGH-PERFORMANCE: Search for products using concurrent pipeline processing.
    
    This endpoint uses Solution 2: Pipeline Processing with Async Queues for maximum
    throughput and performance. Ideal for production workloads.
    """
    start_time = time.time()
    
    try:
        logger.info(f"🚀 PIPELINE: Starting search for '{request.query}' (country: {request.country})")
        
        # Get pipeline agent
        pipeline_agent = await _get_pipeline_agent()
        
        # Convert to internal request format
        internal_request = ProductSearchRequest(
            query=request.query,
            country=request.country,
            city=request.city,
            max_queries=request.max_queries
        )
        
        # Execute search
        products = await pipeline_agent.search_product(internal_request)
        
        processing_time = time.time() - start_time
        
        logger.info(f"✅ PIPELINE: Search completed for '{request.query}' in {processing_time:.2f}s - {len(products)} products found")
        
        return PipelineSearchResponse(
            success=True,
            query=request.query,
            products=products,
            processing_time=processing_time,
            pipeline_used=True
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ PIPELINE: Error in /pipeline/search for '{request.query}': {e}", exc_info=True)
        
        # Return error response
        return PipelineSearchResponse(
            success=False,
            query=request.query,
            products=[],
            processing_time=processing_time,
            pipeline_used=True
        )


@router.post("/pipeline/search-multiple", response_model=MultiplePipelineSearchResponse)
async def pipeline_search_multiple(request: MultiplePipelineSearchRequest = Body(...)):
    """
    🚀 ULTRA-HIGH-PERFORMANCE: Process multiple product searches concurrently.
    
    This endpoint processes multiple search requests simultaneously using the
    concurrent pipeline for maximum throughput. Perfect for batch operations.
    """
    start_time = time.time()
    
    try:
        logger.info(f"🚀 PIPELINE: Starting {len(request.searches)} concurrent searches")
        
        # Get pipeline agent
        pipeline_agent = await _get_pipeline_agent()
        
        # Convert to internal request format
        internal_requests = [
            ProductSearchRequest(
                query=search.query,
                country=search.country,
                city=search.city,
                max_queries=search.max_queries
            )
            for search in request.searches
        ]
        
        # Execute concurrent searches
        results_lists = await pipeline_agent.search_multiple(internal_requests)
        
        # Build response
        search_responses = []
        for i, (search_req, products) in enumerate(zip(request.searches, results_lists)):
            search_responses.append(PipelineSearchResponse(
                success=len(products) > 0,
                query=search_req.query,
                products=products,
                processing_time=0.0,  # Individual timing not tracked in batch
                pipeline_used=True
            ))
        
        total_processing_time = time.time() - start_time
        successful_searches = sum(1 for r in search_responses if r.success)
        
        logger.info(f"✅ PIPELINE: Completed {successful_searches}/{len(request.searches)} searches in {total_processing_time:.2f}s")
        
        # Get pipeline metrics
        metrics = pipeline_agent.get_pipeline_metrics()
        
        return MultiplePipelineSearchResponse(
            success=True,
            results=search_responses,
            total_processing_time=total_processing_time,
            pipeline_metrics=metrics
        )
        
    except Exception as e:
        total_processing_time = time.time() - start_time
        logger.error(f"❌ PIPELINE: Error in /pipeline/search-multiple: {e}", exc_info=True)
        
        # Return error response
        return MultiplePipelineSearchResponse(
            success=False,
            results=[],
            total_processing_time=total_processing_time,
            pipeline_metrics=None
        )


@router.get("/pipeline/metrics")
async def pipeline_metrics():
    """Get real-time pipeline performance metrics."""
    try:
        if _pipeline_agent:
            metrics = _pipeline_agent.get_pipeline_metrics()
            return {"success": True, "metrics": metrics}
        else:
            return {"success": False, "error": "Pipeline not initialized"}
    except Exception as e:
        logger.error(f"Error getting pipeline metrics: {e}")
        return {"success": False, "error": str(e)}


