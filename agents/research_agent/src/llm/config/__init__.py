"""
Configuration package for LLM settings and model configurations.
"""

from .model_config import (
    LLMProvider,
    ModelConfig,
    MODEL_CONFIGS,
    OLLAMA_MODELS,
    OPENAI_MODELS,
    get_model_config,
    get_provider_from_model
)

__all__ = [
    'LLMProvider',
    'ModelConfig',
    'MODEL_CONFIGS',
    'OLLAMA_MODELS',
    'OPENAI_MODELS',
    'get_model_config',
    'get_provider_from_model'
] 