import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_agent.api import api_router
from research_agent.config import settings
from shared.logging import setup_logger

# Load environment variables
load_dotenv()

# Configure logging
logger = setup_logger("research_agent")

# Create application
app = FastAPI(
    title="Research Agent API",
    description="AI agent for research using web crawler and LLM",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    logger.info("Research Agent API starting up")
    logger.info(f"Ollama service configured at: {settings.OLLAMA_BASE_URL}")
    logger.info(f"Using default model: {settings.DEFAULT_MODEL}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Research Agent API shutting down") 