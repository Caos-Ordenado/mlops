from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    """Environment configuration for the price comparison agent."""
    
    # Ollama Configuration
    OLLAMA_HOST: str = Field(default="home.server", description="Ollama host")
    OLLAMA_PORT: int = Field(default=80, description="Ollama port")
    OLLAMA_PATH: str = Field(default="/ollama", description="Ollama base path")
    OLLAMA_MODEL: str = Field(default="llama3", description="Ollama model name")
    OLLAMA_TIMEOUT: int = Field(default=600, description="Timeout for model operations in seconds")
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="home.server", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_PREFIX: str = Field(default="price_comparison:", description="Redis key prefix")
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str = Field(default="home.server", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="web_crawler", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="admin", description="PostgreSQL user")
    POSTGRES_PASSWORD: str = Field(default="admin", description="PostgreSQL password")
    
    # Web Crawler Configuration
    CRAWLER_MAX_PAGES: int = Field(default=100, description="Maximum number of pages to crawl")
    CRAWLER_MAX_DEPTH: int = Field(default=3, description="Maximum crawl depth")
    CRAWLER_TIMEOUT: int = Field(default=30, description="Request timeout in seconds")
    CRAWLER_MAX_CONCURRENT: int = Field(default=5, description="Maximum concurrent pages to crawl")
    CRAWLER_MEMORY_THRESHOLD: float = Field(default=80.0, description="Memory threshold percentage")
    
    @property
    def ollama_base_url(self) -> str:
        """Get the full Ollama base URL."""
        return f"http://{self.OLLAMA_HOST}:{self.OLLAMA_PORT}{self.OLLAMA_PATH}"
    
    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        case_sensitive = True

# Create a global settings instance
settings = Settings() 