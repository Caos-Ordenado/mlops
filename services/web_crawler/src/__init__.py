"""
Web crawler package.
"""

from .core import WebCrawlerAgent, CrawlerSettings
from .api import app

__version__ = "1.0.0"
__all__ = ['WebCrawlerAgent', 'CrawlerSettings', 'app'] 