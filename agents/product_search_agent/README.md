# Product Search Agent

## Overview
A FastAPI-based agent that exposes a `/search` endpoint for product search queries. Follows the shared agent architecture and repository/database/cache patterns as described in `agents.mdc` and `database.mdc`.

## Features
- `/search` endpoint (GET): Accepts a `product` query parameter and returns a placeholder response.
- Uses shared logging (`loguru` via `shared.logging`).
- Async context managers for future service clients.
- Repository pattern for database access (to be implemented).
- All configuration via environment variables.

## Usage
```bash
uvicorn src.api.app:app --reload
```

## Endpoints
### GET /search
- **Query param:** `product` (str, required)
- **Response:**
  ```json
  {
    "success": true,
    "results": [
      {"product": "...", "info": "..."}
    ]
  }
  ```

## Development
- Logging: see `shared/logging.py`
- Service clients: see `shared/web_crawler_client.py`, `shared/ollama_client.py`
- Database: repository pattern, see `database.mdc`

## TODO
- Implement actual product search logic
- Add database/repository integration
- Add error handling and connection management 