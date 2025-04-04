import uvicorn
from dotenv import load_dotenv

from research_agent.config import settings


def main():
    """Run the FastAPI application with uvicorn"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Run the application
    # Note: HOST and PORT are hardcoded in config.py
    uvicorn.run(
        "research_agent.main:app",
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main() 