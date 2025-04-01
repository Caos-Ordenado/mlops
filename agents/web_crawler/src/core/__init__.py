"""
Core module containing the main crawler functionality.
"""

from .models import CrawlerSettings
from .crawler import WebCrawlerAgent
from .storage import StorageBackend, RedisStorage, PostgresStorage
from .agent import BaseAgent

__all__ = [
    'WebCrawlerAgent',
    'CrawlerSettings',
    'StorageBackend',
    'RedisStorage',
    'PostgresStorage',
    'BaseAgent'
] 