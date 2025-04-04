"""
# Web Crawler Agent

A high-performance web crawler with memory-adaptive features and a RESTful API.

## Features

- Asynchronous web crawling with aiohttp
- Memory-adaptive crawling
  - Monitors system memory usage during crawling
  - Automatically adjusts crawling speed and concurrency based on memory usage
  - Prevents memory exhaustion by pausing when threshold is reached
  - Configurable memory threshold (default: 80%)
  - Memory usage logging can be enabled/disabled independently of general logging
    - Controlled via `CRAWLER_DEBUG` environment variable
    - When enabled, logs memory usage at key points:
      - Crawler initialization
      - Before/after URL crawling
      - Before/after storage operations
      - At the start/completion of each depth level
      - During memory threshold checks
    - Memory logging is optimized to minimize overhead when disabled
    - Can be used alongside different logging levels for other components
- Storage backends
  - Redis for fast, in-memory storage
  - PostgreSQL for persistent storage
- RESTful API with FastAPI
  - OpenAPI/Swagger documentation
  - Request/response validation
  - Async request handling
  - Health check endpoint
  - CORS support

## To run locally

1. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
```
Then edit `.env` with your specific settings.

### Automated Deployment
Use the deployment script for automated updates:
```bash
cd agents/web_crawler
./deploy.sh
```

## Project Structure

```
web_crawler/
├── src/
│   ├── core/
│   │   ├── __init__.py      # Core package exports
│   │   ├── agent.py         # Base agent class
│   │   ├── crawler.py       # Web crawler implementation
│   │   ├── models.py        # Shared data models
│   │   └── storage.py       # Storage backend implementations
│   ├── api/
│   │   ├── __init__.py      # API package exports
│   │   └── app.py          # FastAPI application
│   ├── main.py             # Entry point (FastAPI server or example)
│   └── config.py           # Configuration management
├── requirements.txt        # Project dependencies
└── setup.py               # Package configuration
```

## Environment Variables

### Core Settings
```env
CRAWLER_MAX_PAGES=10000
CRAWLER_MAX_DEPTH=20
CRAWLER_TIMEOUT=180000
CRAWLER_MAX_TOTAL_TIME=300
CRAWLER_MAX_CONCURRENT_PAGES=10
CRAWLER_MEMORY_THRESHOLD=80.0
CRAWLER_USER_AGENT=custom_agent
CRAWLER_RESPECT_ROBOTS=false
CRAWLER_DEBUG=false
CRAWLER_LOG_LEVEL=INFO
CRAWLER_CLEANUP_INTERVAL_HOURS=24
CRAWLER_DATA_RETENTION_DAYS=30
CRAWLER_ALLOWED_DOMAINS=example.com,ai.pydantic.dev
CRAWLER_EXCLUDE_PATTERNS=*.pdf,*.jpg,*.png,*.gif,*.zip,*.doc,*.docx,*.xls,*.xlsx,*.ppt,*.pptx
CRAWLER_HEADLESS=true
CRAWLER_VIEWPORT_HEIGHT=1080
CRAWLER_VIEWPORT_WIDTH=1920
```

### Storage Settings
```env
POSTGRES_HOST=postgres.shared.svc.cluster.local
POSTGRES_PORT=5432
POSTGRES_USER=admin
POSTGRES_DB=web_crawler
REDIS_HOST=redis.shared.svc.cluster.local
REDIS_PORT=6379
REDIS_DB=0
```

### Running the FastAPI Server

The project includes a `start.sh` script that handles environment setup and server startup:

```bash
# Start the server using the script
./start.sh
```

The script will:
1. Clean the server.log file
2. Verify Python version and virtual environment
3. Install/update requirements
4. Load environment variables
5. Start the FastAPI server

The FastAPI server will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc UI: http://localhost:8000/redoc

### API Endpoints
 - Check openapi.json

## Output and Logging

The crawler provides detailed output with configurable logging levels:

1. Console Output:
   - Shows real-time progress of the crawl
   - Displays basic information about crawled pages
   - Shows any errors or issues during crawling

2. Log File (`server.log`):
   - Contains detailed logging information based on LOG_LEVEL
   - Includes timestamps for each operation
   - Shows full crawl results and memory usage when debug is enabled
   - Log file is cleaned on each server start
   - Available log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Automated Deployment
The project includes a `deploy.sh` script that automates the entire process:

```bash
# From the web_crawler directory
./deploy.sh
```

The script will:
1. Create ConfigMap from your .env file (excluding sensitive data)
2. Build the Docker image for AMD64 architecture
3. Transfer the image to your home server
4. Import it into microk8s
5. Apply Kubernetes configurations
6. Force a rollout restart
7. Wait for deployment completion

After deployment, the web crawler will be accessible at:
- API Endpoint: `http://home.server/crawler/`
- Swagger UI: `http://home.server/crawler/docs`
- ReDoc UI: `http://home.server/crawler/redoc`

### Storage Configuration

The web crawler uses two storage backends:

#### PostgreSQL
Available in the shared namespace:
- Inside cluster: `postgres.shared.svc.cluster.local:5432`
- Database: `web_crawler`
- User: `admin`

When using PostgreSQL storage:
- Use the correct service DNS name
- Check database connectivity before crawling large sites

#### Redis
Available in the shared namespace:
- Inside cluster: `redis.shared.svc.cluster.local:6379`

When using Redis storage:
- Use the correct service DNS name
- Monitor Redis memory usage for large crawls
""" 