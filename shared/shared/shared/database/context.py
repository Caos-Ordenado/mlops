"""
Context manager for database operations.
"""

from typing import Optional
from .manager import DatabaseManager
from ..repositories.webpage import WebPageRepository
from ..config.database import DatabaseConfig
from ..logging import setup_logger

logger = setup_logger(__name__)

class DatabaseContext:
    """Context manager for database operations."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.db = DatabaseManager()
        self.config = config
        self.webpages: Optional[WebPageRepository] = None

    async def __aenter__(self) -> 'DatabaseContext':
        """Enter the async context manager."""
        await self.db.init(config=self.config)
        self.webpages = WebPageRepository(self.db)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        if self.db.engine:
            await self.db.engine.dispose()
            logger.debug("Disposed database engine") 