"""
FastAPI application for the web crawler.
"""

import asyncio
from api.models import CrawlRequest, CrawlResponse, CrawlResult
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import os
from dotenv import load_dotenv

from core import WebCrawlerAgent, CrawlerSettings

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

# Global storage instances
redis_storage = None
postgres_storage = None

async def cleanup_task():
    """Background task to clean up old data."""
    cleanup_interval = int(os.getenv("CRAWLER_CLEANUP_INTERVAL_HOURS", "24"))
    retention_days = int(os.getenv("CRAWLER_DATA_RETENTION_DAYS", "30"))
    
    while True:
        try:
            logger.debug("Starting periodic data cleanup")
            
            if redis_storage:
                await redis_storage.cleanup_old_data(days=retention_days)
            if postgres_storage:
                await postgres_storage.cleanup_old_data(days=retention_days)
                
            logger.debug(f"Cleanup complete. Next cleanup in {cleanup_interval} hours")
            await asyncio.sleep(cleanup_interval * 3600)  # Convert hours to seconds
            
        except Exception as e:
            logger.error(f"Error during cleanup task: {e}")
            await asyncio.sleep(3600)  # Wait an hour before retrying on error

@app.on_event("startup")
async def startup_event():
    """Initialize storage and start background tasks on startup."""
    global redis_storage, postgres_storage
    
    logger.info("Initializing web crawler API...")
    
    # Initialize storage if enabled
    if os.getenv("CRAWLER_STORAGE_REDIS", "false").lower() == "true":
        from core.storage import RedisStorage
        
        # Debug log Redis configuration
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")
        
        logger.debug(f"Redis Configuration:")
        logger.debug(f"Host: {redis_host}")
        logger.debug(f"Port: {redis_port}")
        logger.debug(f"DB: {redis_db}")
        logger.debug(f"Password set: {bool(redis_password)}")
        
        redis_storage = RedisStorage(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password
        )
        logger.debug("Redis storage initialized")
    
    if os.getenv("CRAWLER_STORAGE_POSTGRES", "false").lower() == "true":
        from core.storage import PostgresStorage
        postgres_storage = PostgresStorage(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "web_crawler"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD")
        )
        logger.debug("PostgreSQL storage initialized")
    
    # Start cleanup task
    asyncio.create_task(cleanup_task())
    logger.info("Web crawler API initialization complete")

@app.post("/crawl", response_model=CrawlResponse)
async def crawl(request: CrawlRequest):
    """
    Crawl the specified URLs with the given settings.
    
    This endpoint accepts a list of URLs and crawling parameters, then returns the crawled data
    along with metadata about the crawling process.
    
    The crawler will:
    1. Initialize with the specified settings and environment variables
    2. Crawl each URL up to the specified depth
    3. Store results in the configured storage backends (if enabled in environment)
    4. Return the crawled data and statistics
    
    Returns:
        CrawlResponse: Contains the crawled data and statistics
    
    Raises:
        HTTPException: If there's an error during crawling
    """
    try:
        # Get storage settings from environment
        storage_redis = os.getenv("CRAWLER_STORAGE_REDIS", "false").lower() == "true"
        storage_postgres = os.getenv("CRAWLER_STORAGE_POSTGRES", "false").lower() == "true"
        memory_threshold = float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "80.0"))
        
        # Create crawler settings from request and environment
        settings = CrawlerSettings(
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            allowed_domains=request.allowed_domains,
            exclude_patterns=request.exclude_patterns,
            respect_robots=request.respect_robots,
            timeout=request.timeout,
            max_total_time=request.max_total_time,
            max_concurrent_pages=request.max_concurrent_pages,
            memory_threshold=memory_threshold,  # From environment
            storage_redis=storage_redis,        # From environment
            storage_postgres=storage_postgres,   # From environment
            debug=request.debug
        )
        
        # Initialize and run crawler
        start_time = asyncio.get_event_loop().time()
        
        # Create a task for crawling to ensure proper cleanup
        async with WebCrawlerAgent(settings) as crawler:
            # Create a task for crawling
            crawl_task = asyncio.create_task(crawler.crawl_urls(request.urls))
            
            try:
                # Wait for crawling to complete with timeout
                results = await asyncio.wait_for(
                    crawl_task,
                    timeout=settings.max_total_time
                )
            except asyncio.TimeoutError:
                # Cancel the task if it times out
                crawl_task.cancel()
                try:
                    await crawl_task
                except asyncio.CancelledError:
                    pass
                raise HTTPException(
                    status_code=408,
                    detail="Crawling timed out"
                )
            
        # Calculate statistics
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # Convert results to response model
        crawl_results = [
            CrawlResult(
                url=result["url"],
                title=result.get("title"),
                text=result["text"],
                links=result["links"],
                metadata=result["metadata"]
            )
            for result in results
        ]
        
        return CrawlResponse(
            results=crawl_results,
            total_urls=len(request.urls),
            crawled_urls=len(results),
            elapsed_time=elapsed_time
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
        "crawler.log",
        rotation="100 MB",
        retention="5 days",
        compression="zip",
        level=os.getenv("CRAWLER_LOG_LEVEL", "DEBUG"),
        enqueue=True  # Thread-safe logging
    )
    uvicorn.run(app, host="0.0.0.0", port=8000) 