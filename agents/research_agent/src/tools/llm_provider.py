from enum import Enum
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import os
import openai
from shared.ollama_client import OllamaClient
from llm.config.model_config import OLLAMA_MODELS, OPENAI_MODELS, get_provider_from_model, LLMProvider
from config.settings import settings

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def generate(self, prompt: str, system: str, model: str, **kwargs) -> str:
        """Generate a response from the LLM"""
        pass

class OllamaLLMClient(BaseLLMClient):
    """Ollama implementation of the LLM client"""
    
    async def generate(self, prompt: str, system: str, model: str, **kwargs) -> str:
        """Generate a response using Ollama"""
        try:
            client = OllamaClient()
            async with client:
                response = await client.generate(
                    prompt=prompt,
                    system=system,
                    model=model,
                    **kwargs
                )
                return response
        except Exception as e:
            raise Exception(f"Error generating response with Ollama: {str(e)}")

class OpenAILLMClient(BaseLLMClient):
    """OpenAI implementation of the LLM client"""
    
    async def generate(self, prompt: str, system: str, model: str, **kwargs) -> str:
        """Generate a response using OpenAI"""
        try:
            # Initialize OpenAI client with API key from settings
            openai.api_key = settings.OPENAI_API_KEY
            if not openai.api_key:
                raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
            
            # Create completion
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error generating response with OpenAI: {str(e)}")

def get_llm_client(provider: LLMProvider) -> BaseLLMClient:
    """Factory function to get the appropriate LLM client"""
    try:
        # Ensure provider is a valid LLMProvider enum value
        if not isinstance(provider, LLMProvider):
            raise ValueError(f"Invalid provider type: {type(provider)}")
        
        clients = {
            LLMProvider.OLLAMA: OllamaLLMClient(),
            LLMProvider.OPENAI: OpenAILLMClient()
        }
        
        if provider not in clients:
            raise ValueError(f"Unsupported provider: {provider}")
            
        return clients[provider]
    except Exception as e:
        raise Exception(f"Error getting LLM client: {str(e)}") 