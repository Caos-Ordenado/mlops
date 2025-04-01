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

## Installation

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

### Crawler Settings
- `CRAWLER_MAX_PAGES`: Maximum number of pages to crawl (default: 10000)
- `CRAWLER_MAX_DEPTH`: Maximum crawl depth (default: 20)
- `CRAWLER_TIMEOUT`: Timeout in milliseconds (default: 180000)
- `CRAWLER_MAX_TOTAL_TIME`: Maximum total crawling time in seconds (default: 300)
- `CRAWLER_MAX_CONCURRENT_PAGES`: Maximum number of pages to crawl concurrently (default: 10)
- `CRAWLER_MEMORY_THRESHOLD`: Memory threshold percentage for adaptive crawling (default: 80.0)
- `CRAWLER_USER_AGENT`: Custom user agent string
- `CRAWLER_RESPECT_ROBOTS`: Whether to respect robots.txt (default: false)
- `CRAWLER_DEBUG`: Enable debug logging (default: false)

### Storage Settings
- `CRAWLER_STORAGE_POSTGRES`: Enable PostgreSQL storage (default: false)
- `CRAWLER_STORAGE_REDIS`: Enable Redis storage (default: false)

### Database Configuration
#### PostgreSQL
- `POSTGRES_HOST`: PostgreSQL host address
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_DB`: Database name

#### Redis
- `REDIS_HOST`: Redis host address (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)

## Usage

### Running the FastAPI Server

```bash
# Start the server
python src/main.py

# Or run the example crawler
python src/main.py example
```

The FastAPI server will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc UI: http://localhost:8000/redoc

### API Endpoints

#### POST /crawl
Crawl specified URLs with configurable settings.

Request body:
```json
{
  "urls": ["https://example.com"],
  "max_pages": 100,
  "max_depth": 3,
  "allowed_domains": ["example.com"],
  "exclude_patterns": ["/login", "/admin"],
  "respect_robots": true,
  "timeout": 30000,
  "max_total_time": 60,
  "max_concurrent_pages": 5,
  "memory_threshold": 80.0,
  "storage_redis": false,
  "storage_postgres": false,
  "debug": false
}
```

Response:
```json
{
  "results": [
    {
      "url": "https://example.com",
      "title": "Example Domain",
      "text": "...",
      "links": ["https://example.com/page1", "..."],
      "metadata": {
        "status_code": 200,
        "headers": {},
        "content_type": "text/html",
        "timestamp": 1743511218.223563
      }
    }
  ],
  "total_urls": 1,
  "crawled_urls": 1,
  "elapsed_time": 0.211
}
```

#### GET /health
Health check endpoint.

Response:
```json
{
  "status": "ok"
}
```

### Using the Core Library

```python
from core import WebCrawlerAgent, CrawlerSettings

# Configure crawler settings
settings = CrawlerSettings(
    max_pages=10,
    max_depth=2,
    timeout=30000,
    memory_threshold=80.0,
    storage_redis=True
)

# Initialize and run crawler
async with WebCrawlerAgent(settings) as crawler:
    results = await crawler.crawl_urls([
        "https://example.com",
        "https://example.org"
    ])
```

## Output and Logging

The crawler provides detailed output in two ways:

1. Console Output:
   - Shows real-time progress of the crawl
   - Displays basic information about crawled pages
   - Shows any errors or issues during crawling

2. Log File (`crawler.log`):
   - Contains detailed logging information
   - Includes timestamps for each operation
   - Shows full crawl results
   - Log file rotates at 500MB to prevent disk space issues

## Development

To contribute to the project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License

## Deployment

### Prerequisites
- Docker installed on your local machine
- `kubectl` configured to access your Kubernetes cluster
- `sshpass` installed (`brew install sshpass` on macOS)

### Automated Deployment
The project includes a deployment script that automates the entire process of building and deploying the web crawler to your Kubernetes cluster.

To deploy:
```bash
# From the web_crawler directory
./deploy.sh
```

The script will:
1. Build the Docker image for the correct architecture
2. Transfer the image to your home server
3. Import it into microk8s
4. Apply the Kubernetes configurations
5. Wait for the deployment to complete

After deployment, the web crawler will be accessible at:
- API Endpoint: `http://home.server/crawler/`
- Swagger UI: `http://home.server/crawler/docs`
- ReDoc UI: `http://home.server/crawler/redoc`

### Manual Deployment
If you need to deploy manually or customize the deployment process:

1. Build the Docker image:
```bash
docker build --platform linux/amd64 -t web-crawler:latest .
```

2. Save and transfer the image:
```bash
docker save web-crawler:latest -o /tmp/web-crawler.tar
scp /tmp/web-crawler.tar caos@internal-vpn-address:/tmp/
```

3. Import into microk8s:
```bash
ssh caos@internal-vpn-address "echo '***REMOVED***' | sudo -S microk8s ctr image import /tmp/web-crawler.tar"
```

4. Apply Kubernetes configurations:
```bash
kubectl apply -k ../../k8s/web_crawler
```

### Monitoring
To monitor the deployment:
```bash
# Check pod status
kubectl get pods -n shared -l app=web-crawler

# Check logs
kubectl logs -n shared -l app=web-crawler --tail=100

# Check the deployment status
kubectl describe deployment -n shared web-crawler
```
""" 