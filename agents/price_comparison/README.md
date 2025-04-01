# Price Comparison AI Agent

## Overview
AI-powered agent that analyzes and compares product prices across multiple supermarket websites. The agent integrates with the existing web crawler system and utilizes collected data stored in Redis and PostgreSQL.

## Features
- Data retrieval from Redis and PostgreSQL
- Product name standardization and price normalization
- Cross-supermarket product matching
- Best price identification and analysis
- Historical price trend tracking
- RESTful API for data access

## Technical Stack
- **AI Model**: Llama 3 (8B) via Ollama
- **Storage**: 
  - Redis (shared instance for caching/realtime storage)
  - PostgreSQL (persistent storage)
- **API Framework**: FastAPI (planned)

## Setup Instructions

### Prerequisites
- Ollama installed and running
- Access to shared Redis instance
- Access to PostgreSQL database
- Python 3.8+
- Virtual environment (recommended)

### Installation
1. Ensure Ollama is running and Llama 3 model is pulled:
```bash
ollama pull llama3
```

2. Install Python dependencies (to be added):
```bash
pip install -r requirements.txt
```

## Project Structure
```
price_comparison/
├── src/
│   ├── models/      # AI model integration and inference
│   ├── analysis/    # Price analysis and comparison logic
│   └── api/         # FastAPI endpoints
├── tests/           # Unit and integration tests
└── data/           # Sample data and model artifacts
```

## Usage
(To be added as development progresses)

## Development Status
- [ ] Initial setup
- [ ] Data retrieval integration
- [ ] AI model integration
- [ ] Price analysis implementation
- [ ] API development
- [ ] Testing and validation
- [ ] Documentation 