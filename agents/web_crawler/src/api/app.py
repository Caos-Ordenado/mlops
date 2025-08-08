"""
FastAPI application for the web crawler.
"""

import asyncio
import time
import hashlib
from typing import Optional, Tuple
from .models import CrawlRequest, CrawlResponse, CrawlResult, SingleCrawlRequest, SingleCrawlResponse
from fastapi import FastAPI, HTTPException, Response, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from shared import setup_logger, DatabaseContext, DatabaseConfig
import os
from dotenv import load_dotenv

from ..core import WebCrawlerAgent, CrawlerSettings

# Initialize logger
logger = setup_logger("web_crawler.api")

# Load environment variables
load_dotenv()


class TimedCache:
    """Simple time-based cache for crawl results with TTL."""
    
    def __init__(self, ttl: int = 300):  # 5 minutes TTL
        self.cache = {}
        self.ttl = ttl
    
    def _generate_key(self, url: str, extract_links: bool = True) -> str:
        """Generate cache key from URL and options."""
        key_data = f"{url}:{extract_links}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, extract_links: bool = True) -> Optional[Tuple[dict, float]]:
        """Get cached result if within TTL."""
        key = self._generate_key(url, extract_links)
        if key in self.cache:
            result, timestamp, elapsed_time = self.cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit for {url}")
                return result, elapsed_time
            else:
                del self.cache[key]
                logger.debug(f"Cache expired for {url}")
        return None
    
    def set(self, url: str, result: dict, elapsed_time: float, extract_links: bool = True):
        """Store result in cache with timestamp."""
        key = self._generate_key(url, extract_links)
        self.cache[key] = (result, time.time(), elapsed_time)
        logger.debug(f"Cached result for {url}")
        
        # Simple cleanup: remove old entries if cache gets large
        if len(self.cache) > 1000:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
            logger.debug("Cache cleanup: removed oldest entry")

# Initialize cache
url_cache = TimedCache(ttl=int(os.getenv("CRAWLER_CACHE_TTL", "300")))

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
    - Single URL crawling for quick content extraction
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
    
    # Initialize database context with retry logic
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
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
            logger.info("Database context initialized successfully")
            break
            
        except Exception as e:
            logger.warning(f"Database initialization attempt {attempt + 1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to initialize database context after all retries")
                # Don't raise exception - let the app start anyway and handle gracefully
                db_context = None
    
    # Start cleanup task only if database is available
    if db_context:
        asyncio.create_task(cleanup_task())
    else:
        logger.warning("Cleanup task disabled due to database initialization failure")
        
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
        # If db_context is None, let the agent create its own (it will try to connect)
        try:
            async with WebCrawlerAgent(settings, db_context=db_context) as agent:
                results = await agent.crawl_urls(request.urls)
        except Exception as db_error:
            logger.warning(f"Database-enabled crawler failed: {db_error}")
            # Try without database context as fallback
            logger.info("Attempting crawl without database storage")
            async with WebCrawlerAgent(settings, db_context=None) as agent:
                # Temporarily disable database saves in the agent
                agent.db_context = None
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


@app.post(
    "/crawl-single",
    response_model=SingleCrawlResponse,
    status_code=200,
    summary="Crawl a single URL without following links",
    description="""
    Extracts content from a single webpage without traversing links. 
    
    This endpoint is optimized for single-page requests and includes:
    - Response caching (5-minute TTL by default)
    - Configurable timeout (capped at 30 seconds)
    - Memory optimization for single URL requests
    - Option to bypass cache for fresh content
    
    Returns the same rich data as the main crawl endpoint but with better performance.
    """,
    responses={
        200: {
            "description": "Successful crawl",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "result": {
                            "url": "https://example.com",
                            "title": "Example Domain",
                            "text": "This domain is for use in illustrative examples in documents.",
                            "links": ["https://www.iana.org/domains/example"],
                            "metadata": {
                                "status_code": 200,
                                "content_type": "text/html; charset=UTF-8",
                                "meta_tags": [{"name": "description", "content": "Example website"}],
                                "headers_hierarchy": {"h1": ["Example Domain"], "h2": [], "h3": []},
                                "images": [],
                                "structured_data": []
                            }
                        },
                        "elapsed_time": 0.543
                    }
                }
            }
        },
        400: {"description": "Invalid URL format or malformed request"},
        403: {"description": "Forbidden by robots.txt rules"},
        408: {"description": "Request timeout exceeded"},
        500: {"description": "Server error during crawling"},
        503: {"description": "Network error or service unavailable"}
    },
    tags=["Single URL Crawling"]
)
async def crawl_single(request: SingleCrawlRequest) -> SingleCrawlResponse:
    """Crawl a single URL and return the result with performance optimizations."""
    start_time = time.time()
    logger.info(f"Starting single URL crawl for: {request.url}")
    
    # Check cache first (unless bypassed)
    if not request.bypass_cache:
        cached_result = url_cache.get(request.url, request.extract_links)
        if cached_result:
            result, cached_elapsed_time = cached_result
            logger.info(f"Returning cached result for {request.url} (original time: {cached_elapsed_time:.2f}s)")
            return SingleCrawlResponse(
                success=True,
                result=CrawlResult(**result),
                elapsed_time=cached_elapsed_time
            )
    
    try:
        # Create optimized crawler settings for single URL
        settings = CrawlerSettings(
            max_pages=1,  # Only crawl one page
            max_depth=1,  # Crawl only the initial URL, no depth traversal
            respect_robots=request.respect_robots,
            timeout=min(request.timeout, 30000),  # Cap at 30 seconds for single URL
            max_total_time=min(300, request.timeout // 1000 + 60),  # Conservative total time
            max_concurrent_pages=1,  # Single URL, no concurrency needed
            memory_threshold=float(os.getenv("CRAWLER_MEMORY_THRESHOLD", "85.0"))  # Slightly higher for single URL
        )
        
        # Create crawler agent with optimized database context
        try:
            async with WebCrawlerAgent(settings, db_context=db_context) as agent:
                # Add timeout wrapper for the entire crawl operation
                try:
                    result = await asyncio.wait_for(
                        agent.crawl_url(request.url), 
                        timeout=request.timeout / 1000.0  # Convert ms to seconds
                    )
                except asyncio.TimeoutError:
                    raise HTTPException(
                        status_code=408, 
                        detail=f"Request timed out after {request.timeout/1000:.1f} seconds"
                    )
        except Exception as db_error:
            logger.warning(f"Database-enabled crawler failed: {db_error}")
            # Try without database context as fallback
            logger.info("Attempting single crawl without database storage")
            async with WebCrawlerAgent(settings, db_context=None) as agent:
                # Temporarily disable database saves in the agent
                agent.db_context = None
                try:
                    result = await asyncio.wait_for(
                        agent.crawl_url(request.url), 
                        timeout=request.timeout / 1000.0  # Convert ms to seconds
                    )
                except asyncio.TimeoutError:
                    raise HTTPException(
                        status_code=408, 
                        detail=f"Request timed out after {request.timeout/1000:.1f} seconds"
                    )
            
            # Clear agent's internal cache to free memory
            if hasattr(agent, '_session_cache'):
                agent._session_cache.clear()
            if hasattr(agent, 'visited_urls'):
                agent.visited_urls.clear()
            
        elapsed_time = time.time() - start_time
        
        if result:
            # Cache the successful result
            if not request.bypass_cache:
                url_cache.set(request.url, result, elapsed_time, request.extract_links)
            
            logger.info(f"Successfully crawled {request.url} in {elapsed_time:.2f}s")
            return SingleCrawlResponse(
                success=True,
                result=CrawlResult(**result),
                elapsed_time=elapsed_time
            )
        else:
            elapsed_time = time.time() - start_time
            logger.warning(f"No result returned for {request.url} after {elapsed_time:.2f}s")
            return SingleCrawlResponse(
                success=False,
                result=None,
                elapsed_time=elapsed_time,
                error="No content could be extracted from the URL"
            )
        
    except asyncio.TimeoutError:
        elapsed_time = time.time() - start_time
        error_msg = f"Request timed out after {elapsed_time:.2f} seconds"
        logger.error(f"Timeout for {request.url}: {error_msg}")
        raise HTTPException(status_code=408, detail=error_msg)
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Error crawling single URL {request.url} after {elapsed_time:.2f}s: {error_msg}")
        
        # Handle specific error types with appropriate HTTP status codes
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise HTTPException(status_code=408, detail=f"Request timeout: {error_msg}")
        elif "robots.txt" in error_msg.lower() or "robot" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Forbidden by robots.txt: {error_msg}")
        elif "invalid url" in error_msg.lower() or "url" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"Invalid URL: {error_msg}")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            raise HTTPException(status_code=503, detail=f"Network error: {error_msg}")
        else:
            raise HTTPException(status_code=500, detail=f"Server error: {error_msg}")


@app.get("/health")
async def health_check():
    """Health check endpoint with database status."""
    try:
        status = {
            "status": "ok",
            "database": "unknown"
        }
        
        if db_context:
            # Test database connection briefly
            try:
                async with db_context.db.get_session() as session:
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
                status["database"] = "connected"
            except Exception:
                status["database"] = "disconnected"
                status["status"] = "degraded"
        else:
            status["database"] = "not_initialized"
            status["status"] = "degraded"
            
        return status
    except Exception:
        # Always return 200 for basic health check to prevent restart loops
        return {"status": "ok", "database": "error"}

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