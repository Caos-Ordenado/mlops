from fastapi import APIRouter, HTTPException, Query
from src.api.models import ProductSearchResponse
from src.core.agent import ProductSearchAgent
from shared.logging import setup_logger

router = APIRouter()
logger = setup_logger("product_search_api.routes")


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


