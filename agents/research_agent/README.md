# Research Agent

AI research agent powered by FastAPI, web crawler, and Ollama LLM.

## Features

- FastAPI backend with async request handling
- Integration with Ollama LLM service
- Research API endpoint
- Logging with loguru (via shared utilities)

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -e .
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env file as needed
```

## Running the Application

### Development Mode

```bash
# Enable hot reloading
export RELOAD=true
# Run the application
research-agent
```

### Production Mode

```bash
# Run with production settings
export LOG_LEVEL=INFO
export RELOAD=false
research-agent
```

### Manual Run

```bash
uvicorn research_agent.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Health Check

```
GET /health
```

### Research

```
POST /api/research/
```

Request body:
```json
{
  "query": "Your research question",
  "model": "llama3.1",
  "max_tokens": 1000,
  "additional_context": "Optional additional context for the query"
}
```
