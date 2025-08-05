# Product Search Agent - Product Requirements Document (PRD)

## 1. Executive Summary

The **Product Search Agent** is an intelligent web service that automates the discovery and classification of e-commerce product pages based on natural language product queries. It leverages AI-powered query generation, web search, intelligent crawling, and machine learning classification to provide highly relevant product results for any specified geographic market.

### Key Value Propositions
- **AI-Enhanced Query Generation**: Converts simple product names into optimized search queries with purchase intent
- **Intelligent Product Page Discovery**: Automatically identifies and classifies potential product pages
- **Proactive Web Crawling**: Triggers comprehensive content extraction for deeper product analysis
- **Geographic Targeting**: Configurable for any country or city-specific e-commerce landscape with intelligent URL validation

## 2. Product Overview

### 2.1 Core Functionality
The agent serves as a unified API endpoint that orchestrates multiple AI-powered sub-agents to transform basic product queries into comprehensive product discovery results.

### 2.2 Target Users
- E-commerce aggregators
- Price comparison platforms
- Market research analysts
- Automated shopping assistants
- Product availability monitoring systems

### 2.3 Success Metrics
- Query generation accuracy and relevance
- Product page classification precision
- API response time and reliability
- Web crawling efficiency and coverage

## 3. Technical Architecture

### 3.1 System Architecture
```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  ProductSearchAgent  │    │  External APIs  │
│   Web Server    │───▶│      (Core)          │───▶│  (Brave Search) │
│   Port: 8000    │    │                      │    │                 │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   ▼               ▼               ▼
          ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
          │ Query Gen   │ │ Search      │ │ URL Extract  │
          │ Agent       │ │ Agent       │ │ Agent        │
          └─────────────┘ └─────────────┘ └──────────────┘
                   │               │               │
                   ▼               ▼               ▼
          ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
          │ Ollama LLM  │ │ Brave       │ │ Web Crawler  │
          │ Service     │ │ Search      │ │ Service      │
          └─────────────┘ └─────────────┘ └──────────────┘
                                   │
                            ┌──────┴──────┐
                            ▼             ▼
                   ┌─────────────┐ ┌─────────────┐
                   │ Geographic  │ │ Product Page│
                   │ URL         │ │ Classifier  │
                   │ Validator   │ │ (Phase 5)   │
                   │ (Phase 2.5) │ │             │
                   └─────────────┘ └─────────────┘
                            │             │
                            ▼             ▼
                   ┌─────────────┐ ┌─────────────┐
                   │ deepseek-r1 │ │ llama3.2    │
                   │ 1.5b Model  │ │ Model       │
                   └─────────────┘ └─────────────┘
```

### 3.2 Infrastructure Dependencies

#### Core Infrastructure (Home Server - MicroK8s Cluster)
- **Host**: home.server (internal-vpn-address)
- **Access**: Tailscale VPN for remote connectivity
- **Ingress**: Traefik reverse proxy

#### Required Services
- **Ollama LLM Service**: 
  - URL: `http://home.server:30080/ollama`
  - Model: llama3.2 (default)
  - Purpose: AI query generation and product page classification

- **Web Crawler Service**:
  - URL: `http://home.server:30081/crawler/`
  - Purpose: Deep content extraction and page analysis
  - Namespace: default

- **PostgreSQL Database**:
  - Service: `postgres.shared.svc.cluster.local:5432`
  - Database: `web_crawler`
  - Purpose: Persistent storage for crawled content

- **Redis Cache**:
  - Service: `redis.shared.svc.cluster.local:6379`
  - Purpose: Performance caching layer

### 3.3 Shared Libraries
The agent utilizes the `shared` package for common functionality:

- **Logging System**: Thread-safe logging with loguru
- **Database Access**: Repository pattern with PostgreSQL + Redis caching
- **Service Clients**: Async HTTP clients for Ollama and Web Crawler
- **Configuration Management**: Environment-based configuration

## 4. Functional Requirements

### 4.1 Primary Workflow

#### Phase 1: Query Generation
**Input**: Natural language product name (e.g., "crema para el cabello")
**Process**: 
- Uses Ollama LLM (llama3.2 model) to generate 5 optimized search queries
- Queries designed with purchase intent and geographic context
- JSON-formatted output with specific search terms

**Output**: List of targeted search queries (example for Uruguay market)
```json
[
  "comprar crema para el cabello en Montevideo",
  "crema capilar precio Uruguay",
  "productos para el cabello tienda online Uruguay",
  "crema hidratante cabello venta Montevideo",
  "tratamiento capilar comprar online"
]
```

**Note**: Query generation adapts to the specified country and city parameters, automatically incorporating relevant geographic terms, local language variations, and market-specific e-commerce platforms.

#### Phase 2: Web Search Execution
**Input**: Generated search queries
**Process**:
- Executes parallel searches using Brave Search API
- Aggregates results from all queries
- Collects URLs, titles, descriptions, and snippets

**Output**: Comprehensive search results dataset

#### Phase 2.5: Geographic URL Validation
**Input**: Raw search results from Phase 2
**Process**: 
- Country-specific domain pattern matching (e.g., .uy, .com.uy for Uruguay; .ar, .com.ar for Argentina)
- LLM-based contextual analysis using deepseek-r1:1.5b model with geographic prompts
- Geographic indicator detection in URLs and metadata for the specified country/city
- Business name pattern recognition for local retailers and e-commerce platforms
- Multi-country support: UY, AR, BR, CL, CO, PE, EC, MX, US, ES
- Retry logic: Up to 3 iterations with query refinement when < 20 valid URLs found

**Output**: Filtered list of geographically-relevant URLs (target: 20+ URLs)
**Input Parameters**: `country` (required, default: "UY"), `city` (optional)
**Performance**: < 2 seconds per batch processing

#### Phase 3: URL Extraction and Filtering
**Input**: Raw search results
**Process**:
- Extracts unique URLs from search results
- Removes duplicates and invalid URLs
- Filters for relevant domains and content types

**Output**: Curated list of candidate URLs

#### Phase 4: Proactive Web Crawling
**Input**: Extracted URLs
**Process**:
- Triggers asynchronous crawling via Web Crawler Service
- Configurable parameters:
  - max_pages: 10 per URL
  - max_depth: 2 levels
  - timeout: 180 seconds
  - concurrent_pages: 5

**Output**: Crawl job initiation confirmation

#### Phase 5: Product Page Classification
**Input**: Candidate URLs
**Process**:
- Uses Ollama LLM to classify URLs as product pages
- Analyzes URL patterns, domain context, and available metadata
- Binary classification with confidence scoring

**Output**: Classified product page candidates
```json
{
  "product_pages": [
    {
      "url": "https://example.com/product/hair-cream",
      "classification": "product_page",
      "confidence": 0.95,
      "reasoning": "URL contains product identifier and domain is e-commerce"
    }
  ]
}
```

### 4.2 API Specification

#### Endpoint: GET /search
**Description**: Primary search endpoint for product discovery

**Parameters**:
- `product` (string, required): Product name or description to search for
- `country` (string, optional): Country code for geographic filtering (default: "UY")
  - Supported: UY, AR, BR, CL, CO, PE, EC, MX, US, ES
- `city` (string, optional): City name for more specific geographic validation

**Response Format**:
```json
{
  "success": true,
  "query": "crema para el cabello",
  "generated_queries": [
    "comprar crema para el cabello en Montevideo",
    "crema capilar precio Uruguay"
  ],
  "search_results_count": 45,
  "unique_urls_found": 23,
  "geographic_validated_urls": 21,
  "validation_retry_count": 0,
  "crawl_triggered": true,
  "product_page_candidates": [
    {
      "url": "https://farmacity.com/producto/crema-capilar",
      "title": "Crema Capilar Hidratante",
      "classification": "product_page",
      "confidence": 0.92,
      "validation_method": "domain_pattern"
    }
  ],
  "processing_time_ms": 2340,
  "validation_time_ms": 890
}
```

**Error Responses**:
- `400 Bad Request`: Missing or invalid product parameter
- `500 Internal Server Error`: Service failures or LLM errors
- `503 Service Unavailable`: Dependent services unreachable

## 5. Technical Implementation

### 5.1 Agent Architecture

#### ProductSearchAgent (Core Orchestrator)
- **File**: `src/core/agent.py`
- **Purpose**: Coordinates all sub-agents and manages the complete workflow
- **Key Methods**:
  - `search_product()`: Main entry point for product search

#### Sub-Agents

1. **QueryGeneratorAgent**
   - **File**: `src/core/query_generator.py`
   - **Purpose**: AI-powered search query generation
   - **LLM Integration**: Ollama with structured prompting

2. **SearchAgent**
   - **File**: `src/core/search_agent.py`
   - **Purpose**: External search API integration (Brave Search)
   - **Features**: Result aggregation and deduplication

3. **UrlExtractorAgent**
   - **File**: `src/core/url_extractor_agent.py`
   - **Purpose**: URL extraction and web crawling orchestration
   - **Integration**: Web Crawler Service trigger

4. **GeoUrlValidatorAgent**
   - **File**: `src/core/geo_url_validator_agent.py`
   - **Purpose**: Parametrized geographic validation of URLs for any country/city
   - **LLM Integration**: Ollama with deepseek-r1:1.5b model
   - **Features**: Multi-country domain patterns, contextual analysis, retry logic
   - **Countries Supported**: UY, AR, BR, CL, CO, PE, EC, MX, US, ES

5. **ProductPageCandidateIdentifierAgent**
   - **File**: `src/core/product_page_candidate_identifier.py`
   - **Purpose**: AI-powered product page classification
   - **LLM Integration**: Ollama with classification prompting

### 5.2 Geographic URL Validator Agent

#### Overview
The GeoUrlValidatorAgent is responsible for filtering search results to ensure they are relevant to the specified geographic location (country and optionally city). This component sits between Phase 2 (Web Search) and Phase 2.5 (URL Validation) in the workflow, providing configurable geographic localization for better product discovery across multiple markets.

#### Model Selection
- **Primary model**: deepseek-r1:1.5b
- **Selection rationale**: Balance of accuracy and performance for classification tasks
- **Optimized for**: Geographic context analysis and URL classification
- **Performance**: Low latency (< 500ms per inference)
- **Fallback**: Pattern-based validation when LLM unavailable

#### Validation Criteria

**1. Domain-based validation** (country-specific):
- Country TLDs (e.g., .uy, .com.uy for Uruguay; .ar, .com.ar for Argentina)
- Known country-specific e-commerce platforms (mercadolibre variants, local retailers)
- Geographic subdomains (country.site.com, countrycode.site.com)

**2. Content-based validation** (parametrized):
- URL path analysis (/country/, /country-code/, /major-cities/)
- Query parameter detection (country=code, region=country-name)
- Business name pattern recognition for local retailers per country
- City-specific validation when city parameter provided
- Contextual relevance analysis using LLM with geographic prompts

**3. Multi-country support**:
- **Supported countries**: UY, AR, BR, CL, CO, PE, EC, MX, US, ES
- **Language support**: Spanish, Portuguese, English (automatic detection)
- **Regional platforms**: Amazon, MercadoLibre variants, local e-commerce sites

#### Integration Points
- **Input**: Receives raw search results from Web Search Agent (Phase 2)
- **Output**: Provides filtered URLs to URL Extraction Agent (Phase 3)
- **Configuration**: Configurable threshold for minimum valid URLs (default: 20)
- **Performance**: Processes batches within 2 seconds

#### Retry Logic
- **Trigger condition**: When fewer than target number (20) of valid URLs found
- **Maximum iterations**: 3 retry cycles to prevent infinite loops
- **Query refinement**: Progressive enhancement with stronger geographic context for specified country
- **Fallback strategy**: Heuristic-only validation if LLM services unavailable
- **Query enhancement**: Uses LLM to add country and city-specific terms with local language support
- **Adaptive**: Automatically adjusts enhancement strategy based on country/language (e.g., Spanish terms for LATAM countries)

#### Error Handling and Resilience
- Structured logging for validation decisions and performance metrics
- Graceful degradation with fallback to pattern-based validation
- Automatic retry with exponential backoff for transient errors
- Comprehensive error logging for debugging and monitoring
- Metrics tracking for validation success rates

### 5.3 Service Integration

#### Web Crawler Integration
- **Client**: `WebCrawlerClient` from shared library
- **Trigger Service**: `WebCrawlerTriggerService`
- **Data Retrieval**: `WebCrawlerDataRetrievalService`
- **Purpose**: Deep content extraction and persistent storage

#### LLM Integration
- **Client**: `OllamaClient` from shared library
- **Primary Model**: llama3.2 (query generation, product page classification)
- **Validation Model**: deepseek-r1:1.5b (Geographic URL validation)
- **Parameters**: 
  - `temperature`: 0.3 (for consistent results in classification)
  - `temperature`: 0.5 (for query enhancement creativity)
  - `num_predict`: 500 (general tasks), 200 (URL validation), 150 (query enhancement)
- **Usage**: Query generation, URL geographic validation, and product page classification

### 5.3 Data Models

#### API Models
```python
class SearchRequest(BaseModel):
    product: str
    country: str = "UY"
    city: Optional[str] = None

class ProductPageCandidate(BaseModel):
    url: str
    title: Optional[str] = None
    classification: str
    confidence: float
    reasoning: Optional[str] = None

class SearchResponse(BaseModel):
    success: bool
    query: str
    generated_queries: List[str]
    search_results_count: int
    unique_urls_found: int
    crawl_triggered: bool
    product_page_candidates: List[ProductPageCandidate]
    processing_time_ms: int
```

## 6. Deployment and Operations

### 6.1 Local Development Setup

#### Prerequisites
- Python 3.8+
- Access to home server infrastructure
- Tailscale VPN connection

#### Installation Steps
```bash
# Navigate to project directory
cd agents/product_search_agent

# Run setup script
./start.sh
```

#### Environment Configuration
Create `.env` file with:
```bash
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
OLLAMA_BASE_URL=http://home.server:30080/ollama
WEB_CRAWLER_BASE_URL=http://home.server:30081/crawler
BRAVE_SEARCH_API_KEY=your_api_key_here
```

### 6.2 Dependencies

#### Core Dependencies
- **FastAPI**: Web framework for API development
- **Uvicorn**: ASGI server for production deployment
- **Langchain**: AI/LLM integration framework
- **Pydantic**: Data validation and serialization
- **Shared Library**: Internal utilities and service clients

#### Shared Library Components
- **Logging**: `shared.logging` - Thread-safe logging with loguru
- **Database**: `shared.repositories` - Repository pattern with caching
- **Service Clients**: 
  - `shared.ollama_client` - LLM service integration
  - `shared.web_crawler_client` - Web crawling service integration

### 6.3 Monitoring and Logging

#### Log Management
- **File**: `server.log` (automatically created)
- **Rotation**: 100MB file size limit
- **Retention**: 5 days
- **Format**: Structured JSON with timestamps
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

#### Health Monitoring
- **Endpoint**: `/health` (if implemented)
- **Dependencies Check**: Ollama and Web Crawler service availability
- **Metrics**: Response times, error rates, throughput

### 6.4 Performance Considerations

#### URL Validation Performance
- **Batch Processing**: Validates URLs in efficient batches to minimize latency
- **Caching Mechanism**: Previously validated URLs cached for 24 hours
- **Parallel Processing**: Domain validation performed in parallel threads
- **Adaptive Batching**: LLM analysis uses optimal batch sizes (5-10 URLs per request)
- **Graceful Degradation**: Falls back to pattern-only validation if LLM unavailable
- **Performance Target**: Complete validation within 2 seconds per batch

#### Retry Logic Optimization
- **Smart Thresholds**: Only triggers retry when < 20 validated URLs found
- **Progressive Enhancement**: Each retry iteration adds stronger geographic context for the specified country
- **Maximum Bounds**: Limits to 3 retry iterations to prevent delays
- **Query Refinement**: Uses LLM to generate enhanced queries with local terms
- **Fallback Strategy**: Pattern-based enhancement when LLM services fail

### 6.5 Scaling Considerations

#### Performance Optimization
- **Async Processing**: All I/O operations are asynchronous
- **Connection Pooling**: Reuse HTTP connections to external services
- **Caching**: Redis integration for frequently accessed data
- **Parallel Execution**: Concurrent search query processing

#### Resource Requirements
- **Memory**: ~512MB base + LLM processing overhead
- **CPU**: Multi-core recommended for concurrent processing
- **Network**: Stable connection to home server infrastructure
- **Storage**: Minimal local storage (logs only)

## 7. Future Enhancements

### 7.1 Planned Features
- **Price Extraction**: Integration with price extraction agent
- **Product Database**: Persistent storage for discovered products
- **Real-time Updates**: WebSocket support for live search results
- **Analytics Dashboard**: Search patterns and performance metrics

### 7.2 Integration Opportunities
- **E-commerce APIs**: Direct integration with major retailers per supported country
- **Notification System**: Alerts for new product discoveries
- **Machine Learning**: Enhanced classification with custom models
- **Multi-language Support**: Portuguese and English market expansion

## 8. Risk Assessment

### 8.1 Technical Risks
- **LLM Service Availability**: Dependency on Ollama service uptime
- **Rate Limiting**: External search API quotas and throttling
- **Infrastructure Dependency**: Single point of failure with home server

### 8.2 Mitigation Strategies
- **Service Health Checks**: Automated monitoring and alerting
- **Graceful Degradation**: Fallback mechanisms for service failures
- **Error Handling**: Comprehensive exception management
- **Retry Logic**: Exponential backoff for transient failures

## 9. Success Criteria

### 9.1 Performance Metrics
- **Response Time**: < 5 seconds for typical product searches
- **URL Validation**: < 2 seconds for validation phase completion
- **Accuracy**: > 95% precision in geographic URL identification across supported countries
- **Product Classification**: > 85% precision in product page classification
- **Validation Success**: Achieve 20+ validated URLs in > 90% of searches
- **Availability**: > 99% uptime for API endpoint
- **Throughput**: Support for concurrent search requests

### 9.2 Quality Metrics
- **Relevance**: Search results match user intent
- **Coverage**: Comprehensive discovery across e-commerce platforms in supported countries
- **Freshness**: Recent product listings prioritized
- **Diversity**: Results span multiple retailers and categories

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Product Search Agent Development Team 