# Agent Utilities

Shared utilities for AI agents running on the home server infrastructure. This package provides standardized components for database access, logging, caching, and interaction with core services.

## Quick Start

```bash
# Install in your agent's environment
pip install -e /path/to/agents/shared
```

```python
# Basic usage example
from agent_utils import (
    setup_logger,
    DatabaseContext,
    RedisClient,
    WebCrawlerClient,
    OllamaClient
)

# Set up logging
logger = setup_logger("my_agent")

# Use the database
async with DatabaseContext() as db:
    # Database operations here
    pass

# Use Redis caching
async with RedisClient() as redis:
    # Redis operations here
    pass

# Use the web crawler
async with WebCrawlerClient() as crawler:
    # Crawling operations here
    pass

# Use Ollama LLM
async with OllamaClient() as llm:
    # LLM operations here
    pass
```

## Core Components

### 1. Database System
Provides a unified database interface with PostgreSQL storage and Redis caching.

```python
from agent_utils import DatabaseContext, WebPage

async with DatabaseContext() as db:
    # Create and save a webpage
    webpage = WebPage(
        url="https://example.com",
        title="Example Domain",
        text="Example content",
        links=["https://www.example.com/page1"],
        metadata={
            "language": "en",
            "content_type": "text/html"
        }
    )
    await db.webpages.save(webpage)
    
    # Query webpages
    recent_pages = await db.webpages.get_recent_pages(limit=5)
```

#### WebPage Model
The `WebPage` model is optimized for RAG (Retrieval-Augmented Generation) applications:

```python
from agent_utils import WebPage

webpage = WebPage(
    url="https://example.com",
    title="Title",
    description="Meta description",
    main_content="Main article content",
    full_text="Complete page text",
    headers={
        "h1": ["Main Header"],
        "h2": ["Subheader 1", "Subheader 2"]
    },
    meta_tags={
        "description": "Page description",
        "keywords": "key, words"
    },
    structured_data=[],  # JSON-LD data
    links=["https://example.com/page1"],
    images=[{
        "src": "image.jpg",
        "alt": "Description"
    }],
    content_language="en"
)
```

### 2. Web Crawler Client
Interface to the web crawler service for content retrieval:

```python
from agent_utils import WebCrawlerClient, CrawlRequest

async with WebCrawlerClient() as crawler:
    # Check service health
    is_healthy = await crawler.health_check()
    
    # Configure crawl request
    request = CrawlRequest(
        urls=["https://example.com"],
        max_pages=10,
        max_depth=2,
        allowed_domains=["example.com"],
        exclude_patterns=["/admin/", "/login/"],
        respect_robots=True
    )
    
    # Execute crawl
    response = await crawler.crawl(request)
    
    # Process results
    for result in response.results:
        print(f"URL: {result.url}")
        print(f"Title: {result.title}")
```

### 3. Ollama LLM Client
Interface to the local Ollama LLM service:

```python
from agent_utils import OllamaClient

async with OllamaClient() as llm:
    # Simple generation
    response = await llm.generate(
        "Summarize this text: ...",
        model="llama2"
    )
    
    # Advanced options
    response = await llm.generate(
        prompt="Your prompt here",
        model="llama2",
        temperature=0.7,
        max_tokens=500,
        stop_sequences=["END"]
    )
```

### 4. Redis Client
Thread-safe Redis client with connection pooling:

```python
from agent_utils import RedisClient

async with RedisClient() as redis:
    # Basic operations
    await redis.set("key", "value", ex=3600)  # 1 hour expiration
    value = await redis.get("key")
    
    # List operations
    await redis.lpush("list_key", "item1", "item2")
    items = await redis.lrange("list_key", 0, -1)
    
    # Hash operations
    await redis.hset("hash_key", mapping={"field1": "value1"})
    value = await redis.hget("hash_key", "field1")
```

### 5. Logging System
Standardized logging configuration:

```python
from agent_utils import setup_logger

# Create logger
logger = setup_logger("my_agent")

# Usage
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

## Configuration

### Environment Variables

```bash
# Database Configuration
POSTGRES_HOST=home.server
POSTGRES_PORT=5432
POSTGRES_DB=web_crawler
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_password

# Redis Configuration
REDIS_HOST=home.server
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password

# Logging Configuration
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Best Practices

1. **Resource Management**
   ```python
   # ALWAYS use async context managers
   async with DatabaseContext() as db:
       async with RedisClient() as redis:
           # Your code here
           pass
   ```

2. **Error Handling**
   ```python
   try:
       async with WebCrawlerClient() as crawler:
           response = await crawler.crawl(urls=["https://example.com"])
   except ConnectionError:
       logger.error("Failed to connect to crawler service")
   except Exception as e:
       logger.exception("Unexpected error during crawl")
   ```

3. **Logging**
   ```python
   # Use appropriate log levels
   logger.debug("Detailed information for debugging")
   logger.info("General information about program execution")
   logger.warning("Warning messages for potentially harmful situations")
   logger.error("Error messages for serious problems")
   ```

4. **Database Operations**
   ```python
   # Use repositories for data access
   async with DatabaseContext() as db:
       # Fetch data
       pages = await db.webpages.get_by_domain("example.com")
       
       # Batch operations
       await db.webpages.save_many(pages)
   ```

## Development Notes

- All clients are async/await compatible
- Thread-safe logging and connection pooling
- Automatic resource cleanup with context managers
- Type hints and validation throughout
- Error handling patterns established

## Support

For issues or questions:
1. Check the docstrings in the code
2. Review the examples in this README
3. Check the logs in `server.log`