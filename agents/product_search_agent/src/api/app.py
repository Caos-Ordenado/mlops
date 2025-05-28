from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from src.api.models import ProductSearchResponse
from src.core.agent import ProductSearchAgent
from shared.logging import setup_logger

logger = setup_logger("product_search_api")

app = FastAPI(
    title="Product Search Agent API",
    description="Agent for searching product information.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search", response_model=ProductSearchResponse)
async def search(product: str = Query(..., description="Product to search for")):
    try:
        async with ProductSearchAgent() as agent:
            (
                api_results, # List[str] of validated queries
                validation_attempts,
                extracted_candidates,
                identified_page_candidates # New 4th value
            ) = await agent.search_product(product)
        
        return ProductSearchResponse(
            success=True, 
            results=api_results, 
            validation_attempts=validation_attempts,
            extracted_product_candidates=extracted_candidates, # Kept for now
            identified_page_candidates=identified_page_candidates # Pass to response model
        )
    except Exception as e:
        logger.error(f"Error in /search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"} 