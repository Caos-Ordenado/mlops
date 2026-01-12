"""
Client for interacting with Ollama LLM service.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
import json
import requests
from .logging import setup_logger

# Set up logger
logger = setup_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRYABLE_ERRORS = ["unexpected EOF", "llama runner process no longer running", "connection"]

# Global semaphore to limit concurrent Ollama requests across all client instances
_global_ollama_semaphore: Optional[asyncio.Semaphore] = None


def _get_global_semaphore(max_concurrent: int = 2) -> asyncio.Semaphore:
    """Get or create the global Ollama semaphore for the current event loop."""
    global _global_ollama_semaphore
    # Create semaphore lazily to avoid event loop issues
    if _global_ollama_semaphore is None:
        _global_ollama_semaphore = asyncio.Semaphore(max_concurrent)
    return _global_ollama_semaphore


def _is_retryable_error(error_text: str) -> bool:
    """Check if the error is retryable."""
    error_lower = error_text.lower()
    return any(err in error_lower for err in RETRYABLE_ERRORS)


class OllamaClient:
    """Client for interacting with Ollama LLM service (text and vision)."""
    
    def __init__(self, base_url: str = "http://home.server:30080/ollama", model: str = "llama3.2", max_concurrent: int = 2):
        """Initialize the Ollama client.
        
        Args:
            base_url: Base URL of the Ollama API
            model: Default model to use
            max_concurrent: Maximum concurrent Ollama requests (applies globally)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.session = None
        self.max_concurrent = max_concurrent
        
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
            temperature: float = 0.2,
            num_predict: int = 4096,
            format: Optional[str] = None,
        ) -> str:
        """Generate text using the Ollama API.
        
        Args:
            prompt: The prompt to generate text from
            model: The model to use. Defaults to the one specified in constructor.
            system: Optional system prompt
            temperature: Sampling temperature (default: 0.2)
            num_predict: Maximum tokens to generate (default: 4096)
            
        Returns:
            str: The generated text
            
        Raises:
            Exception: If the request fails after all retries
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict
            }
        }
        
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format
        
        last_error: Optional[Exception] = None
        semaphore = _get_global_semaphore(self.max_concurrent)
        
        for attempt in range(MAX_RETRIES):
            try:
                async with semaphore:
                    async with self.session.post(url, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            
                            # Check if error is retryable
                            if response.status == 500 and _is_retryable_error(error_text) and attempt < MAX_RETRIES - 1:
                                delay = RETRY_BASE_DELAY * (2 ** attempt)
                                logger.warning(f"Generate request failed (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s: {error_text[:100]}")
                                await asyncio.sleep(delay)
                                continue
                            
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
                            return data.get('response', '').strip()
                    
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Generate connection error (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s: {str(e)[:100]}")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Generate request failed with error: {str(e)}")
                raise Exception(f"Error during Ollama request: {str(e)}")
            except Exception as e:
                # For non-retryable exceptions, fail immediately
                if "Generate request failed" in str(e):
                    raise
                last_error = e
                logger.error(f"Generate request failed with error: {str(e)}")
                raise Exception(f"Error during Ollama request: {str(e)}")
        
        # Should not reach here, but just in case
        raise Exception(f"Generate request failed after {MAX_RETRIES} retries: {last_error}")

    async def chat(
            self,
            messages: list[dict],
            model: Optional[str] = None,
            format: Optional[str] = None,
            stream: bool = False,
            temperature: float = 0.2,
            num_predict: int = 4096,
        ) -> Dict[str, Any]:
        """Generic chat API supporting images for vision models.

        Args:
            messages: List of message dicts. Each message can include an 'images' list with base64 strings.
            model: Optional override model name.
            format: Optional output format hint (e.g., "json").
            stream: Whether to stream.
            temperature: Sampling temperature.
            num_predict: Max tokens to generate.

        Returns:
            Dict response from Ollama chat endpoint.
        """
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict
            }
        }
        if format:
            payload["format"] = format

        last_error: Optional[Exception] = None
        semaphore = _get_global_semaphore(self.max_concurrent)
        
        for attempt in range(MAX_RETRIES):
            try:
                async with semaphore:
                    async with self.session.post(url, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            
                            # Check if error is retryable
                            if response.status == 500 and _is_retryable_error(error_text) and attempt < MAX_RETRIES - 1:
                                delay = RETRY_BASE_DELAY * (2 ** attempt)
                                logger.warning(f"Chat request failed (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s: {error_text[:100]}")
                                await asyncio.sleep(delay)
                                continue
                            
                            logger.error(f"Chat request failed with status {response.status}: {error_text}")
                            raise Exception(f"Chat request failed: {error_text}")
                        return await response.json()
                    
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Chat connection error (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s: {str(e)[:100]}")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Chat request failed with error: {str(e)}")
                raise Exception(f"Error during Ollama chat: {str(e)}")
            except Exception as e:
                # For non-retryable exceptions, fail immediately
                if "Chat request failed" in str(e):
                    raise
                last_error = e
                logger.error(f"Chat request failed with error: {str(e)}")
                raise Exception(f"Error during Ollama chat: {str(e)}")
        
        # Should not reach here, but just in case
        raise Exception(f"Chat request failed after {MAX_RETRIES} retries: {last_error}")

    async def extract_from_image(
            self,
            image_base64: str,
            instruction: str,
            model: Optional[str] = None,
            format: str = "json",
            num_predict: int = 4096,
        ) -> str:
        """Convenience helper to perform vision extraction from a single image.

        Args:
            image_base64: Base64 encoded image
            instruction: Extraction instruction
            model: Vision model to use
            format: Output format (default: json)
            num_predict: Max tokens to generate. Use 2048 for moondream which has smaller context.

        Returns the assistant content (string). Use JSON-only instructions and format="json" to get structured output.
        """
        messages = [{
            "role": "user",
            "content": instruction,
            "images": [image_base64]
        }]
        data = await self.chat(messages=messages, model=model, format=format, stream=False, num_predict=num_predict)
        # Newer Ollama chat returns { message: { content } } or { choices } depending on version
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict):
                return (data["message"].get("content") or "").strip()
            if "response" in data:
                return str(data.get("response", "")).strip()
        return str(data)
            
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