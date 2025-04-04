import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # Server settings
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"
    
    # LLM settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://home.server:9080/ollama")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3.1")
    
    # Redis configuration (optional)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "home.server")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # PostgreSQL configuration (optional)
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "home.server")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "web_crawler")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields


# Create global settings instance
settings = Settings() 