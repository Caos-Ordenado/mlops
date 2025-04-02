"""
FastAPI application for web research agent.
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import json
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from agent_utils import CrawlResult
from agent_utils.logging import setup_logger
from .agent import WebResearchAgent

# Configure logging
logger = setup_logger("web_research_agent")

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Initialize the agent
    app.state.agent = WebResearchAgent()
    await app.state.agent.__aenter__()
    
    yield
    
    # Cleanup
    await app.state.agent.__aexit__(None, None, None)

app = FastAPI(
    title="Web Research Agent API",
    description="API for web research and RAG using web crawler and Ollama LLM",
    version="1.0.0",
    lifespan=lifespan
)

# Request/Response models
class ResearchRequest(BaseModel):
    """Research request model."""
    urls: List[str]
    query: str
    max_pages: int = 5
    max_depth: int = 2
    model: str = "llama2"
    use_cache: bool = True

class Source(BaseModel):
    """Source model for research results."""
    url: str
    title: str
    text: str = Field(description="The content text from the source")
    source_type: str = Field(description="Either 'crawled' or 'cached'")

class ResearchResponse(BaseModel):
    """Research response model."""
    summary: str
    sources: List[Source]

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        await app.state.agent.redis.ping()
        
        # Check PostgreSQL connection
        with app.state.agent.pg_conn.cursor() as cur:
            cur.execute("SELECT 1")
            
        # Check web crawler
        await app.state.agent.crawler.health_check()
        
        # Check LLM
        await app.state.agent.llm.health_check()
        
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Service unhealthy: {str(e)}")

@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    """Research endpoint."""
    try:
        # Check cache first if enabled
        if request.use_cache:
            cache_key = f"research:{','.join(sorted(request.urls))}:{request.query}"
            cached = await app.state.agent.redis.get(cache_key)
            
            if cached:
                logger.info("Found cached result")
                cached_dict = json.loads(cached)
                return ResearchResponse(
                    summary=cached_dict["summary"],
                    sources=[Source(**s) for s in cached_dict["sources"]]
                )
        
        # Perform research
        summary, sources = await app.state.agent.research(
            urls=request.urls,
            query=request.query,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            model=request.model
        )
        
        # Convert sources to Source models
        source_models = []
        for s in sources:
            if isinstance(s, CrawlResult):
                # Handle crawled sources
                source_models.append(Source(
                    url=s.url,
                    title=s.title,
                    text=s.text,
                    source_type="crawled"
                ))
            else:
                # Handle cached sources
                source_models.append(Source(
                    url=s["url"],
                    title=s["title"],
                    text=s["text"],
                    source_type="cached"
                ))
        
        response = ResearchResponse(
            summary=summary,
            sources=source_models
        )
        
        # Cache the result if caching is enabled
        if request.use_cache:
            await app.state.agent.redis.set(
                cache_key,
                json.dumps(response.model_dump()),
                ex=3600  # 1 hour expiration
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Research failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def _get_cached_content(urls: List[str], query: str) -> List[Dict[str, Any]]:
    """Get relevant cached content from Redis and PostgreSQL.
    
    Args:
        urls: List of URLs to check for cached content
        query: Query to use for relevance scoring
        
    Returns:
        List of relevant cached content items
    """
    cached_items = []
    
    # Get domains from URLs
    domains = [urlparse(url).netloc for url in urls]
    logger.debug(f"Searching for content from domains: {domains}")
    
    # Search PostgreSQL for relevant content
    try:
        with app.state.agent.pg_conn.cursor() as cur:
            # Search by domain and relevance
            cur.execute("""
                SELECT url, title, text_content, metadata,
                    ts_rank_cd(to_tsvector('english', text_content), plainto_tsquery('english', %s)) as rank
                FROM pages 
                WHERE substring(url from '.*://([^/]*)') = ANY(%s)
                AND ts_rank_cd(to_tsvector('english', text_content), plainto_tsquery('english', %s)) > 0.1
                ORDER BY rank DESC
                LIMIT 5
            """, (query, domains, query))
            
            for row in cur.fetchall():
                logger.debug(f"Found relevant content in PostgreSQL: {row[0]} (rank: {row[4]})")
                cached_items.append({
                    'url': row[0],
                    'title': row[1],
                    'content': row[2],
                    'metadata': row[3],
                    'type': 'cached',
                    'source': 'postgres'
                })
                
    except Exception as e:
        logger.error(f"Error retrieving content from PostgreSQL: {str(e)}", exc_info=True)
        
    # Check Redis cache
    try:
        for url in urls:
            redis_key = f"crawler:{url}"
            data = await app.state.agent.redis.get(redis_key)
            if data:
                try:
                    content = json.loads(data)
                    # Only include if from same domain
                    content_domain = urlparse(content.get('url', '')).netloc
                    if content_domain in domains:
                        logger.debug(f"Found content in Redis for {url}")
                        content['type'] = 'cached'
                        content['source'] = 'redis'
                        cached_items.append(content)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in Redis cache for {url}")
                    
    except Exception as e:
        logger.error(f"Error retrieving content from Redis: {str(e)}", exc_info=True)
        
    return cached_items 