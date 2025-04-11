from enum import Enum
from typing import Dict, Set, Optional
from dataclasses import dataclass

class LLMProvider(Enum):
    """Enum for different LLM providers"""
    OLLAMA = "ollama"
    OPENAI = "openai"

@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    provider: LLMProvider
    token_limit: int
    temperature: float
    max_tokens: int
    description: Optional[str] = None

# Model configurations
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    # OpenAI Models
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        provider=LLMProvider.OPENAI,
        token_limit=128000,
        temperature=0.1,
        max_tokens=2000,
        description="OpenAI's most capable model with large context window"
    ),
    "gpt-3.5-turbo": ModelConfig(
        name="gpt-3.5-turbo",
        provider=LLMProvider.OPENAI,
        token_limit=16385,
        temperature=0.1,
        max_tokens=2000,
        description="OpenAI's efficient model with smaller context window"
    ),
    
    # Ollama Models
    "mixtral": ModelConfig(
        name="mixtral",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Mixtral model with good balance of capacity and performance"
    ),
    "mistral": ModelConfig(
        name="mistral",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Mistral model with good performance"
    ),
    "llama3.1": ModelConfig(
        name="llama3.1",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Llama 3.1 model"
    ),
    "llama2:13b": ModelConfig(
        name="llama2:13b",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Llama 2 13B model"
    ),
    "neural-chat": ModelConfig(
        name="neural-chat",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Neural Chat model optimized for HTML content analysis"
    ),
    "deepseek-coder:33b": ModelConfig(
        name="deepseek-coder:33b",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="DeepSeek Coder 33B model"
    ),
    "gemma3:12b": ModelConfig(
        name="gemma3:12b",
        provider=LLMProvider.OLLAMA,
        token_limit=32768,
        temperature=0.1,
        max_tokens=4000,
        description="Gemma 3 12B model"
    )
}

# Provider-specific model sets
OLLAMA_MODELS: Set[str] = {
    model for model, config in MODEL_CONFIGS.items()
    if config.provider == LLMProvider.OLLAMA
}

OPENAI_MODELS: Set[str] = {
    model for model, config in MODEL_CONFIGS.items()
    if config.provider == LLMProvider.OPENAI
}

def get_model_config(model: str) -> ModelConfig:
    """Get configuration for a specific model"""
    # Convert model name to lowercase for case-insensitive matching
    model_lower = model.lower()
    
    # Try exact match first
    if model in MODEL_CONFIGS:
        return MODEL_CONFIGS[model]
    
    # Try case-insensitive match
    for config_model, config in MODEL_CONFIGS.items():
        if config_model.lower() == model_lower:
            return config
    
    # Default to Mixtral for unknown models
    return MODEL_CONFIGS["mixtral"]

def get_provider_from_model(model: str) -> LLMProvider:
    """Get the provider for a specific model"""
    return get_model_config(model).provider 