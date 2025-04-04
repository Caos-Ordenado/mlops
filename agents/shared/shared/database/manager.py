"""
Database manager for handling database connections and sessions.
"""

from typing import Optional, Type, TypeVar, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from ..models.base import Base
from ..config.database import DatabaseConfig
from ..redis_client import RedisClient
from ..logging import setup_logger, log_database_config

logger = setup_logger(__name__)
T = TypeVar('T', bound=Base)

class DatabaseManager:
    """Manages database connections and provides session management."""
    
    def __init__(self):
        self.engine = None
        self.async_session = None
        self.redis_client = None
        self.config = None

    async def init(
        self,
        config: Optional[DatabaseConfig] = None,
        redis_client: Optional[RedisClient] = None,
    ) -> None:
        """Initialize database connections.
        
        Args:
            config: Database configuration
            redis_client: Optional Redis client instance
        """
        self.config = config or DatabaseConfig()
        
        try:
            # Log database configuration before connecting
            log_database_config(logger)
            
            # Create connection string
            connection_string = (
                f"postgresql+asyncpg://{self.config.postgres_user}:{self.config.postgres_password}"
                f"@{self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db}"
            )
            
            # Create engine with connection string
            self.engine = create_async_engine(
                connection_string,
                echo=self.config.echo_sql,
                pool_pre_ping=True,  # Enable connection health checks
                pool_size=5,  # Set a reasonable pool size
                max_overflow=10  # Allow some overflow connections
            )
            
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Initialize Redis client and establish connection
            self.redis_client = redis_client or RedisClient()
            await self.redis_client.__aenter__()  # Establish Redis connection
            
            # Test the PostgreSQL connection
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda _: None)
                
            # Test Redis connection
            if not await self.redis_client.health_check():
                logger.warning("Redis connection test failed")
            else:
                logger.info("Redis connection test successful")
                
            logger.info("Successfully initialized database connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {str(e)}")
            raise

    async def create_tables(self) -> None:
        """Create all database tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Successfully created database tables")
        except SQLAlchemyError as e:
            logger.error(f"Failed to create database tables: {str(e)}")
            raise

    def get_session(self) -> AsyncSession:
        """Get a new database session."""
        if not self.async_session:
            raise RuntimeError("DatabaseManager not initialized. Call init() first.")
        return self.async_session()

    async def get_by_id(self, model: Type[T], id_value: Any) -> Optional[T]:
        """Get a model instance by its primary key."""
        async with self.get_session() as session:
            result = await session.execute(
                select(model).filter_by(id=id_value)
            )
            return result.scalar_one_or_none()

    async def save(self, instance: Base) -> None:
        """Save a model instance to both PostgreSQL and Redis if applicable."""
        async with self.get_session() as session:
            try:
                session.add(instance)
                await session.commit()
                
                # If the model has Redis support, save to Redis too
                if hasattr(instance, 'to_redis_data') and hasattr(instance, 'redis_key'):
                    await self.redis_client.set(
                        instance.redis_key,
                        instance.to_redis_data(),
                        ex=3600  # 1 hour cache
                    )
                logger.debug(f"Successfully saved {instance.__class__.__name__}")
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to save {instance.__class__.__name__}: {str(e)}")
                raise

    async def cleanup(self) -> None:
        """Cleanup database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            
        if self.redis_client:
            await self.redis_client.__aexit__(None, None, None)
            self.redis_client = None
            
        logger.debug("Database connections cleaned up") 