# Web Research Agent

A powerful agent that combines web crawling with LLM processing to perform research tasks.

## Features

- Asynchronous web crawling with configurable depth and page limits
- LLM-powered content analysis and summarization
- Redis caching for improved performance
- PostgreSQL storage for persistent data
- FastAPI-based REST API
- Comprehensive logging system

## Installation

1. Create a virtual environment:
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

## Configuration

### Environment Variables

#### Database Configuration
- `REDIS_HOST`: Redis server hostname (default: home.server)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password

- `POSTGRES_HOST`: PostgreSQL server hostname (default: home.server)
- `POSTGRES_PORT`: PostgreSQL server port (default: 5432)
- `POSTGRES_DB`: PostgreSQL database name (default: web_crawler)
- `POSTGRES_USER`: PostgreSQL username (default: admin)
- `POSTGRES_PASSWORD`: PostgreSQL password

#### Logging Configuration
- `LOG_LEVEL`: Set the logging level (default: DEBUG)
  - Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Affects both file and console output
  - Logs are written to `server.log` with the following settings:
    - Rotation: 100 MB
    - Retention: 5 days
    - Compression: ZIP
    - Thread-safe logging enabled

#### Web Crawler 

## Usage

Start the server:
```bash
python -m web_research_agent.server
```

The server will be available at http://localhost:8000 with the following endpoints:

- `/health`: Health check endpoint
- `/research`: Main research endpoint
  - POST request with JSON body:
    ```json
    {
      "urls": ["https://example.com"],
      "query": "What is this about?",
      "max_pages": 5,
      "max_depth": 2,
      "model": "llama2"
    }
    ```

## Monitoring

### Logs
All logs are written to `server.log` in the current directory. You can monitor them with:
```bash
tail -f server.log
```

### Health Check
Check the service health with:
```bash
curl http://localhost:8000/health
```

## Development

### Code Structure
- `api.py`: FastAPI application and endpoints
- `agent.py`: Core research agent implementation
- `models.py`: Pydantic models for request/response handling

### Running Tests
```bash
pytest
```

## License
MIT 