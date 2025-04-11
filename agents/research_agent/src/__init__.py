"""
Research Agent package for product research and analysis.
"""

from .api import router, ResearchRequest, ResearchResponse, research
from .tools import (
    LLMProvider,
    get_llm_client,
    ProductExtractorTool,
    product_extractor,
    WebSearchTool,
    web_search,
    WebCrawlerTool
)
from .llm import (
    get_model_config,
    truncate_messages_to_fit_token_limit,
    num_tokens_from_messages,
    get_token_limit,
    is_token_limit_exceeded
)

__all__ = [
    'router',
    'ResearchRequest',
    'ResearchResponse',
    'research',
    'LLMProvider',
    'get_llm_client',
    'ProductExtractorTool',
    'product_extractor',
    'WebSearchTool',
    'web_search',
    'WebCrawlerTool',
    'get_model_config',
    'truncate_messages_to_fit_token_limit',
    'num_tokens_from_messages',
    'get_token_limit',
    'is_token_limit_exceeded'
]

__version__ = "0.1.0" 