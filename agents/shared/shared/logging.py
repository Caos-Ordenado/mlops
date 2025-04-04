"""
Shared logger configuration for agents.
"""

import os

def log_database_config(logger_instance=None):
    """Log database configuration details at debug level.
    
    Args:
        logger_instance: Optional logger instance to use. If not provided, uses the default logger.
    """
    from loguru import logger
    log = logger_instance or logger
    
    # PostgreSQL Configuration
    log.debug("PostgreSQL Configuration:")
    log.debug(f"  Host: {os.getenv('POSTGRES_HOST', 'home.server')}")
    log.debug(f"  Port: {os.getenv('POSTGRES_PORT', '5432')}")
    log.debug(f"  Database: {os.getenv('POSTGRES_DB', 'web_crawler')}")
    log.debug(f"  User: {os.getenv('POSTGRES_USER', 'admin')}")
    log.debug(f"  Password: {os.getenv('POSTGRES_PASSWORD')}")
    
    # Redis Configuration
    log.debug("Redis Configuration:")
    log.debug(f"  Host: {os.getenv('REDIS_HOST', 'home.server')}")
    log.debug(f"  Port: {os.getenv('REDIS_PORT', '6379')}")
    log.debug(f"  Password: {os.getenv('REDIS_PASSWORD')}")
    log.debug(f"  DB: {os.getenv('REDIS_DB', '0')}")

def setup_logger(name: str):
    """Configure logger for an agent.
    
    Args:
        name: Name of the agent for log identification
        
    Returns:
        Configured logger instance
    """
    from loguru import logger
    
    # Remove default logger
    logger.remove()
    
    # Get log level from environment or use DEBUG as default
    log_level = os.getenv("LOG_LEVEL", "DEBUG")
    
    # Add file handler with rotation and retention
    logger.add(
        "server.log",
        rotation="100 MB",
        retention="5 days",
        compression="zip",
        level=log_level,
        enqueue=True,  # Thread-safe logger
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add stderr handler for console output
    logger.add(
        lambda msg: print(msg, flush=True),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    logger_instance = logger.bind(name=name)
    
    return logger_instance 