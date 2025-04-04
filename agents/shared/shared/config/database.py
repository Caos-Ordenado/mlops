"""
Database configuration settings.
"""

from typing import Optional
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    postgres_host: str = Field(
        default="home.server",
        description="PostgreSQL host"
    )
    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port"
    )
    postgres_db: str = Field(
        default="web_crawler",
        description="PostgreSQL database name"
    )
    postgres_user: str = Field(
        default="admin",
        description="PostgreSQL user"
    )
    postgres_password: Optional[str] = Field(
        default=None,
        description="PostgreSQL password"
    )
    redis_host: str = Field(
        default="home.server",
        description="Redis host"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port"
    )
    redis_db: int = Field(
        default=0,
        description="Redis database number"
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password"
    )
    echo_sql: bool = Field(
        default=False,
        description="Whether to echo SQL statements"
    ) 