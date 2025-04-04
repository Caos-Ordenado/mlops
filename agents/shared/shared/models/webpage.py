"""
WebPage model for storing crawled web pages.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import Column, String, JSON, DateTime, Text, Integer, Index, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import expression

from .base import Base

class WebPage(Base):
    """Model for storing crawled web pages with Redis support."""
    __tablename__ = "webpage"
    
    # Primary identification
    url = Column(String, primary_key=True)
    status_code = Column(Integer)
    content_type = Column(String)
    
    # Core content
    title = Column(String)
    description = Column(Text)
    main_content = Column(Text)
    full_text = Column(Text)
    
    # Semantic structure
    headers = Column(JSON)  # Headers hierarchy for better context
    meta_tags = Column(JSON)  # Meta tags for better understanding
    structured_data = Column(JSON)  # JSON-LD data for semantic understanding
    
    # Navigation and media
    links = Column(JSON)  # List of URLs found on the page
    images = Column(JSON)  # Image information including alt text
    
    # Technical metadata
    content_language = Column(String)
    last_modified = Column(DateTime(timezone=True))
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Search optimization
    search_vector = Column(TSVECTOR)
    embedding = Column(JSON)  # Vector embedding for semantic search

    # Indexes
    __table_args__ = (
        Index('idx_webpage_crawled_at', crawled_at),
        Index('idx_webpage_search_vector', search_vector, postgresql_using='gin'),
        Index('idx_webpage_content_language', content_language),
    )

    def to_redis_data(self) -> Dict[str, Any]:
        """Convert webpage to Redis-storable format."""
        return {
            # Primary identification
            "url": self.url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            
            # Core content
            "title": self.title,
            "description": self.description,
            "main_content": self.main_content,
            "full_text": self.full_text,
            
            # Semantic structure
            "headers": self.headers,
            "meta_tags": self.meta_tags,
            "structured_data": self.structured_data,
            
            # Navigation and media
            "links": self.links,
            "images": self.images,
            
            # Technical metadata
            "content_language": self.content_language,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            
            # Search optimization
            "embedding": self.embedding,
            
            # Required fields for CrawlResult
            "text": self.full_text or self.main_content or "",
            "metadata": {
                "status_code": self.status_code,
                "content_type": self.content_type,
                "last_modified": self.last_modified.isoformat() if self.last_modified else None,
                "content_language": self.content_language,
                "meta_tags": self.meta_tags,
                "headers_hierarchy": self.headers,
                "images": self.images,
                "structured_data": self.structured_data,
                "main_content": self.main_content
            }
        }

    @classmethod
    def from_redis_data(cls, data: Dict[str, Any]) -> 'WebPage':
        """Create WebPage instance from Redis data."""
        return cls(
            # Primary identification
            url=data["url"],
            status_code=data.get("status_code"),
            content_type=data.get("content_type"),
            
            # Core content
            title=data.get("title"),
            description=data.get("description"),
            main_content=data.get("main_content"),
            full_text=data.get("full_text"),
            
            # Semantic structure
            headers=data.get("headers"),
            meta_tags=data.get("meta_tags"),
            structured_data=data.get("structured_data"),
            
            # Navigation and media
            links=data.get("links"),
            images=data.get("images"),
            
            # Technical metadata
            content_language=data.get("content_language"),
            last_modified=datetime.fromisoformat(data["last_modified"]) if data.get("last_modified") else None,
            crawled_at=datetime.fromisoformat(data["crawled_at"]) if data.get("crawled_at") else None,
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            
            # Search optimization
            embedding=data.get("embedding")
        )

    def to_rag_context(self) -> Dict[str, Any]:
        """Convert to RAG-friendly format for context injection."""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "main_content": self.main_content,
            "headers": self.headers,
            "structured_data": self.structured_data,
            "content_language": self.content_language,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None
        }

    @classmethod
    def from_crawl_result(cls, url: str, title: str, text: str, links: List[str], 
                         metadata: Dict[str, Any]) -> 'WebPage':
        """Create a WebPage instance from crawl results."""
        last_modified = None
        if metadata.get('last_modified'):
            try:
                last_modified = datetime.fromisoformat(metadata['last_modified'])
            except (ValueError, TypeError):
                pass

        return cls(
            # Primary identification
            url=url,
            status_code=metadata.get('status_code'),
            content_type=metadata.get('content_type'),
            
            # Core content
            title=title,
            description=metadata.get('meta_tags', {}).get('description'),
            main_content=metadata.get('main_content'),
            full_text=text,
            
            # Semantic structure
            headers=metadata.get('headers_hierarchy'),
            meta_tags=metadata.get('meta_tags'),
            structured_data=metadata.get('structured_data'),
            
            # Navigation and media
            links=links,
            images=metadata.get('images'),
            
            # Technical metadata
            content_language=metadata.get('content_language'),
            last_modified=last_modified,
            
            # Initialize empty embedding
            embedding=None
        )

    def update_search_vector(self) -> None:
        """Update the search vector for full-text search."""
        # Combine relevant text fields for search
        text_parts = [
            self.title or '',
            self.description or '',
            self.main_content or '',
            self.full_text or ''
        ]
        
        # Convert headers to text if present
        if self.headers:
            for level, headers in self.headers.items():
                text_parts.extend(headers)

        # Join all text parts
        combined_text = ' '.join(text_parts)
        
        # Update search vector using PostgreSQL's to_tsvector
        self.search_vector = func.to_tsvector('english', combined_text)

    def __repr__(self) -> str:
        """String representation of the WebPage."""
        return f"<WebPage(url='{self.url}', title='{self.title}')>" 
