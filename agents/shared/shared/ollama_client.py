"""
Client for interacting with Ollama LLM service.
"""

import aiohttp
from typing import Dict, Any, Optional
import json
import requests
from .logging import setup_logger

# Set up logger
logger = setup_logger(__name__)

class OllamaClient:
    """Client for interacting with Ollama LLM service."""
    
    def __init__(self, base_url: str = "http://home.server/ollama"):
        """Initialize the Ollama client.
        
        Args:
            base_url: Base URL of the Ollama API
        """
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
            
    async def generate(
            self,
            prompt: str,
            model: Optional[str] = None,
            system: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 2048
        ) -> str:
        """Generate text using the Ollama API.
        
        Args:
            prompt: The prompt to generate text from
            model: The model to use. Defaults to the one specified in constructor.
            system: Optional system prompt
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 2048)
            
        Returns:
            str: The generated text
            
        Raises:
            Exception: If the request fails
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system:
            payload["system"] = system
        
        logger.debug(f"Sending generate request to: {url}")
        logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with self.session.post(url, json=payload) as response:
                logger.debug(f"Generate response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Generate request failed with status {response.status}: {error_text}")
                    raise Exception(f"Generate request failed: {error_text}")
                
                # Handle NDJSON response format
                content_type = response.headers.get('Content-Type', '')
                if 'application/x-ndjson' in content_type:
                    text = ''
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)
                                if 'response' in data:
                                    text += data['response']
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse NDJSON line: {line}")
                    return text.strip()
                else:
                    # Handle regular JSON response
                    data = await response.json()
                    logger.debug(f"Generate response data: {json.dumps(data, indent=2)}")
                    return data.get('response', '').strip()
                
        except Exception as e:
            logger.error(f"Generate request failed with error: {str(e)}")
            raise Exception(f"Error during Ollama request: {str(e)}")
            
    async def health_check(self) -> bool:
        """Check if the Ollama service is healthy.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            async with self.session.get(f"{self.base_url}/api/tags", timeout=20) as response:
                return response.status == 200
        except Exception as e:
            print(f"Ollama health check failed: {str(e)}")
            return False 