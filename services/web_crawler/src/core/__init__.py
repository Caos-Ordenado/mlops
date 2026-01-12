"""
Core module containing the main crawler functionality.
"""

from .models import CrawlerSettings
from .crawler import WebCrawlerAgent

__all__ = [
    'WebCrawlerAgent',
    'CrawlerSettings'
] 