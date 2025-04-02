# Agent Utilities

Shared utilities for AI agents running on the home server infrastructure.

## Installation

From your agent's directory or virtual environment:

```bash
pip install -e /path/to/agents/shared
```

## Available Utilities

### Logging System (`logging.py`)

Provides a unified logging configuration for all agents:

```python
from agent_utils.logging import setup_logger

logger = setup_logger("my_agent")
```

#### Configuration
- Environment variable: `LOG_LEVEL` (default: DEBUG)
  - Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Affects both file and console output

#### Log File Settings
- File name: `server.log`
- Rotation: 100 MB
- Retention: 5 days
- Compression: ZIP
- Thread-safe logging enabled

### Redis Client (`redis_client.py`)

Asynchronous Redis client with connection pooling and error handling.

#### Configuration
- `REDIS_HOST`: Redis server hostname (default: home.server)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password

#### Usage
```python
from agent_utils import RedisClient

async with RedisClient() as redis:
    await redis.set("key", "value")
    value = await redis.get("key")
```

### PostgreSQL Client (`postgres_client.py`)

PostgreSQL client with connection pooling and async support.

#### Configuration
- `POSTGRES_HOST`: PostgreSQL server hostname (default: home.server)
- `POSTGRES_PORT`: PostgreSQL server port (default: 5432)
- `POSTGRES_DB`: PostgreSQL database name (default: web_crawler)
- `POSTGRES_USER`: PostgreSQL username (default: admin)
- `POSTGRES_PASSWORD`: PostgreSQL password

#### Usage
```python
from agent_utils import PostgresClient

async with PostgresClient() as db:
    async with db.cursor() as cur:
        await cur.execute("SELECT * FROM my_table")
        rows = await cur.fetchall()
```

### Web Crawler Client (`web_crawler.py`)

Client for interacting with the web crawler service running on the home server.

#### Usage
```python
from agent_utils import WebCrawlerClient

async def crawl_example():
    async with WebCrawlerClient() as client:
        # Check service health
        if await client.health_check():
            # Perform crawl
            response = await client.crawl(
                urls=["https://example.com"],
                max_pages=5,
                max_depth=2,
                allowed_domains=["example.com"]
            )
            
            # Process results
            for result in response.results:
                print(f"Title: {result.title}")
                print(f"Content: {result.text[:200]}...")
```

The crawler client provides:
- Async/await interface
- Automatic session management
- Health checking
- Full parameter control
- Type hints and dataclasses
- Error handling
- Clean data structures

### Ollama Client (`ollama.py`)

Client for interacting with the Ollama LLM service.

#### Usage
```python
from agent_utils import OllamaClient

async with OllamaClient() as llm:
    response = await llm.generate("Your prompt here", model="llama2")
```

## Development

### Project Structure
- `__init__.py`: Package exports
- `logging.py`: Shared logging configuration
- `redis_client.py`: Redis client implementation
- `web_crawler.py`: Web crawler service client
- `ollama.py`: Ollama LLM client

### Best Practices
1. Always use async context managers for clients
2. Handle connection errors gracefully
3. Use the shared logging configuration
4. Follow the established error handling patterns
5. Document new features and changes

## License
MIT 