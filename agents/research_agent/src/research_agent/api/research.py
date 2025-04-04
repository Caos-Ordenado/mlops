from fastapi import APIRouter, HTTPException
from shared.logging import setup_logger

from research_agent.models import ResearchRequest, ResearchResponse
from research_agent.services import OllamaService

logger = setup_logger("research_api")

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/", response_model=ResearchResponse)
async def perform_research(request: ResearchRequest):
    """
    Perform research by querying the Ollama LLM service
    """
    logger.info(f"Processing research request: {request.query}")
    
    try:
        # Initialize the Ollama service
        ollama_service = OllamaService()
        
        # Prepare the prompt
        prompt = request.query
        if request.additional_context:
            prompt = f"{prompt}\n\nAdditional context:\n{request.additional_context}"
        
        # Get response from LLM
        response = await ollama_service.generate_response(
            prompt=prompt,
            model=request.model,
            max_tokens=request.max_tokens
        )
        
        logger.info(f"Successfully processed research request")
        return ResearchResponse(result=response)
    
    except Exception as e:
        logger.error(f"Error processing research request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process research request: {str(e)}") 