"""
LLM package for handling language model interactions and configurations.
"""

from .config.model_config import (
    LLMProvider,
    ModelConfig,
    MODEL_CONFIGS,
    OLLAMA_MODELS,
    OPENAI_MODELS,
    get_model_config,
    get_provider_from_model
)

from .utils.token_utils import (
    num_tokens_from_messages,
    get_token_limit,
    is_token_limit_exceeded,
    truncate_messages_to_fit_token_limit
)

__all__ = [
    'LLMProvider',
    'ModelConfig',
    'MODEL_CONFIGS',
    'OLLAMA_MODELS',
    'OPENAI_MODELS',
    'get_model_config',
    'get_provider_from_model',
    'num_tokens_from_messages',
    'get_token_limit',
    'is_token_limit_exceeded',
    'truncate_messages_to_fit_token_limit'
] 