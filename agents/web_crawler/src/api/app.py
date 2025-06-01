"""
FastAPI application for the web crawler.
"""

import asyncio
from api.models import CrawlRequest, CrawlResponse, CrawlResult
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared import setup_logger, DatabaseContext, DatabaseConfig
import os
from dotenv import load_dotenv

from core import WebCrawlerAgent, CrawlerSettings

# Initialize logger
logger = setup_logger("web_crawler.api")

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Web Crawler API",
    description="""
    A high-performance web crawler with memory-adaptive features.
    
    Features:
    - Memory-adaptive crawling with configurable threshold
    - Support for both Redis and PostgreSQL storage backends
    - Asynchronous web crawling with configurable concurrency
    - Built-in memory monitoring and logging
    - Robots.txt support
    """,
    version="1.0.0",
    contact={
        "name": "Web Crawler Team",
        "email": "team@webcrawler.com",
        "url": "https://github.com/yourusername/web-crawler"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database context
db_context = None

async def cleanup_task():
    """Background task to clean up old data."""
    cleanup_interval = int(os.getenv("CRAWLER_CLEANUP_INTERVAL_HOURS", "24"))
    retention_days = int(os.getenv("CRAWLER_DATA_RETENTION_DAYS", "30"))
    
    while True:
        try:
            logger.debug("Starting periodic data cleanup")
            
            if db_context:
                async with db_context.db.get_session() as session:
                    count = await db_context.webpages.cleanup_old_pages(session, days=retention_days)
                    logger.info(f"Cleaned up {count} old pages")
                
            logger.debug(f"Cleanup complete. Next cleanup in {cleanup_interval} hours")
            await asyncio.sleep(cleanup_interval * 3600)  # Convert hours to seconds
            
        except Exception as e:
            logger.error(f"Error during cleanup task: {e}")
            await asyncio.sleep(3600)  # Wait an hour before retrying on error

@app.on_event("startup")
async def startup_event():
    """Initialize database connection and start background tasks on startup."""
    global db_context
    
    logger.info("Initializing web crawler API...")
    
    # Initialize database context
    db_context = DatabaseContext(
        config=DatabaseConfig(
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "web_crawler"),
            postgres_user=os.getenv("POSTGRES_USER", "admin"),
            postgres_password=os.getenv("POSTGRES_PASSWORD"),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD")
        )
    )
    await db_context.__aenter__()
    logger.debug("Database context initialized")
    
    # Start cleanup task
    asyncio.create_task(cleanup_task())
    logger.info("Web crawler API initialization complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    global db_context
    if db_context:
        await db_context.__aexit__(None, None, None)
        db_context = None
        logger.info("Database connections closed")

@app.post("/crawl", response_model=CrawlResponse)
async def crawl(request: CrawlRequest) -> CrawlResponse:
    """Crawl a list of URLs and return the results."""
    try:
        # Initialize crawler settings
        settings = CrawlerSettings(
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            respect_robots=request.respect_robots,
            timeout=request.timeout,
            max_total_time=request.max_total_time,
            max_concurrent_pages=request.max_concurrent_pages,
            memory_threshold=float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0")),
            allowed_domains=request.allowed_domains,
            exclude_patterns=request.exclude_patterns
        )
        
        # Create crawler agent with existing database context
        async with WebCrawlerAgent(settings, db_context=db_context) as agent:
            results = await agent.crawl_urls(request.urls)
            
        return CrawlResponse(
            success=True,
            results=[CrawlResult(**result) for result in results],
            total_urls=len(request.urls),
            crawled_urls=len(results),
            elapsed_time=0.0  # TODO: Track elapsed time
        )
        
    except Exception as e:
        logger.error(f"Error during crawling: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Ensure environment variables are loaded
    load_dotenv(override=True)
    # Configure logging
    logger.add(
        "server.log",
        rotation="100 MB",
        retention="5 days",
        compression="zip",
        level=os.getenv("CRAWLER_LOG_LEVEL", "DEBUG"),
        enqueue=True  # Thread-safe logging
    )
    uvicorn.run(app, host="0.0.0.0", port=8000) 