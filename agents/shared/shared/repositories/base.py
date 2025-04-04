"""
Base repository class for all repositories.
"""

from typing import Generic, TypeVar, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.manager import DatabaseManager
from ..models.base import Base

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """Base repository class with dual storage support (PostgreSQL + Redis)."""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository with database manager."""
        self.db = db
        self.redis = db.redis_client if db.redis_client else None
    
    async def save(self, session: AsyncSession, instance: T) -> T:
        """Save instance to both PostgreSQL and Redis."""
        try:
            # Save to PostgreSQL
            session.add(instance)
            await session.flush()
            
            # If model supports Redis and we have Redis connection
            if self.redis and hasattr(instance, 'to_redis_data'):
                redis_key = f"{instance.__tablename__}:{self._get_primary_key(instance)}"
                redis_data = instance.to_redis_data()
                await self.redis.set(redis_key, redis_data, ex=3600)  # 1 hour cache
            
            return instance
            
        except Exception as e:
            await session.rollback()
            raise

    async def get(self, session: AsyncSession, id: Any) -> Optional[T]:
        """Get instance from Redis first, fallback to PostgreSQL."""
        if self.redis:
            redis_key = f"{self.model.__tablename__}:{id}"
            cached_data = await self.redis.get(redis_key)
            if cached_data:
                return self.model.from_redis_data(cached_data)
        
        # Fallback to PostgreSQL
        result = await session.get(self.model, id)
        return result

    def _get_primary_key(self, instance: T) -> Any:
        """Extract primary key value from instance."""
        for column in instance.__table__.primary_key:
            return getattr(instance, column.name)
