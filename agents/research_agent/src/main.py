"""
Main application module for the research agent
"""

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from shared.logging import setup_logger
from api import research

# Setup logger
logger = setup_logger("research_agent")

# Load environment variables
load_dotenv()

# Create and configure the FastAPI application
app = FastAPI(
    title="Research Agent API",
    description="API for product research in the Uruguayan market",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this based on environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(research.router)

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Add startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Research Agent API starting up")
    logger.info(f"Ollama service configured at: {settings.OLLAMA_URL}")
    logger.info(f"Web crawler configured at: {settings.CRAWLER_URL}")
    logger.info(f"Log level set to: {settings.LOG_LEVEL}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Research Agent API shutting down")


def main():
    """Run the FastAPI application with uvicorn"""
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main() 