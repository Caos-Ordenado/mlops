"""
Shared logging configuration for agents.
"""

import os
from loguru import logger

def setup_logger(name: str):
    """Configure logging for an agent.
    
    Args:
        name: Name of the agent for log identification
        
    Returns:
        Configured logger instance
    """
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
        enqueue=True,  # Thread-safe logging
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add stderr handler for console output
    logger.add(
        lambda msg: print(msg, flush=True),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    return logger.bind(name=name) 