"""
Shared utilities for agents.
"""

from .logging import setup_logger, log_database_config
from .redis_client import RedisClient
from .web_crawler_client import WebCrawlerClient, CrawlRequest, CrawlResult, CrawlResponse
from .ollama_client import OllamaClient
from .renderer_client import RendererClient
from .models import Base, WebPage
from .database import DatabaseContext, DatabaseManager
from .repositories.webpage import WebPageRepository
from .config import DatabaseConfig

__version__ = "0.1.0"

__all__ = [
    'setup_logger',
    'log_database_config',
    'RedisClient',
    'WebCrawlerClient',
    'CrawlRequest',
    'CrawlResult',
    'CrawlResponse',
    'OllamaClient',
    'RendererClient',
    'Base',
    'WebPage',
    'DatabaseContext',
    'DatabaseManager',
    'WebPageRepository',
    'DatabaseConfig',
    '__version__',
] 