"""
Main entry point for the research agent API.
"""

import uvicorn
from fastapi import FastAPI
from api import router
from config import settings

app = FastAPI(
    title="Research Agent API",
    description="API for product research and analysis using LLMs and web search",
    version="0.1.0"
)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 