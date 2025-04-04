from typing import Optional
from shared.ollama_client import OllamaClient
from shared.logging import setup_logger

from research_agent.config import settings

logger = setup_logger("ollama_service")


class OllamaService:
    """
    Service for interacting with the Ollama LLM
    """
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL):
        self.base_url = base_url
        logger.debug(f"Initialized OllamaService with base_url: {base_url}")

    async def generate_response(
        self,
        prompt: str,
        model: str = settings.DEFAULT_MODEL,
        max_tokens: Optional[int] = 1000
    ) -> str:
        """
        Generate a response from the Ollama LLM
        
        Args:
            prompt: The prompt to send to the LLM
            model: The model to use for generation
            max_tokens: Maximum tokens in the response
        
        Returns:
            The generated text response
        """
        logger.debug(f"Generating response with model: {model}")
        
        try:
            async with OllamaClient(base_url=self.base_url) as llm:
                response = await llm.generate(
                    prompt,
                    model=model,
                    max_tokens=max_tokens
                )
                return response
        except Exception as e:
            logger.error(f"Error generating response from Ollama: {str(e)}")
            raise 