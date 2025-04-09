"""
Configuration module for the research agent
"""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Web Crawler Configuration
    CRAWLER_URL: str = os.getenv("CRAWLER_URL", "http://home.server/crawler/crawl")
    
    # Ollama Configuration
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://home.server/ollama")
    
    # Database Configuration
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "home.server")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "web_crawler")
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "home.server")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")

    # SerpAPI Configuration
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY")

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields in the .env file

# Create a global settings instance
settings = Settings() 