"""
URL utilities for common URL operations.

These utilities provide generic URL handling:
- Domain comparison
- URL normalization for deduplication
- List deduplication preserving order
"""

from typing import List, Set
from urllib.parse import urlparse


def same_domain(base_url: str, link: str) -> bool:
    """
    Check if two URLs share the same domain.
    
    Args:
        base_url: The base/reference URL
        link: The URL to compare against
        
    Returns:
        True if both URLs have the same netloc (domain)
        
    Example:
        >>> same_domain("https://example.com/page1", "https://example.com/page2")
        True
        >>> same_domain("https://example.com", "https://other.com")
        False
    """
    try:
        base_parsed = urlparse(base_url)
        link_parsed = urlparse(link)
        return link_parsed.netloc and link_parsed.netloc == base_parsed.netloc
    except Exception:
        return False


def normalize_url(url: str, remove_tracking_params: bool = True) -> str:
    """
    Normalize URL for deduplication.
    
    Normalizations applied:
    - Lowercase scheme and netloc
    - Remove 'www.' prefix
    - Remove trailing slashes from path
    - Optionally remove common tracking parameters
    
    Args:
        url: URL to normalize
        remove_tracking_params: If True, remove UTM and other tracking params
        
    Returns:
        Normalized URL string
        
    Example:
        >>> normalize_url("HTTPS://WWW.Example.COM/Page/?utm_source=google")
        'https://example.com/page'
    """
    # Common tracking parameters to remove
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'ref', 'referer', 'source', 'campaign', 'fbclid', 'gclid', 'dclid',
        '_ga', '_gac', 'mc_cid', 'mc_eid', 'affiliate', 'partner', 'srsltid'
    }
    
    try:
        parsed = urlparse(url.lower().strip())
        
        # Remove www prefix
        netloc = parsed.netloc
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        # Remove trailing slashes and normalize path
        path = parsed.path.rstrip('/')
        
        # Handle query parameters
        query = ''
        if parsed.query and remove_tracking_params:
            # Parse and filter query params
            params = []
            for param in parsed.query.split('&'):
                if '=' in param:
                    key = param.split('=')[0]
                    if key not in tracking_params:
                        params.append(param)
                else:
                    params.append(param)
            query = '&'.join(params)
        elif parsed.query:
            query = parsed.query
        
        # Build normalized URL
        normalized = f"{parsed.scheme}://{netloc}{path}"
        if query:
            normalized += f"?{query}"
        
        return normalized
        
    except Exception:
        return url.lower().strip()


def dedupe_urls_preserve_order(urls: List[str]) -> List[str]:
    """
    Remove duplicate URLs while preserving their original order.
    
    Args:
        urls: List of URLs (may contain duplicates)
        
    Returns:
        List of unique URLs in original order
        
    Example:
        >>> dedupe_urls_preserve_order(["a", "b", "a", "c", "b"])
        ['a', 'b', 'c']
    """
    seen: Set[str] = set()
    result: List[str] = []
    
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    
    return result

