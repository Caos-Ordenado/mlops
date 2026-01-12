"""
E-commerce URL utilities with Uruguay-specific handling.

This module provides domain-specific URL processing for:
- Sanitizing malformed e-commerce URLs
- Uruguay-specific TLD and pattern handling
- Product page detection from URL patterns
- Query relevance filtering
"""

import re
from typing import List, Optional, Set
from urllib.parse import urlparse

from shared.logging import setup_logger

logger = setup_logger("ecommerce_url_utils")


# Characters that indicate a malformed/concatenated URL (from breadcrumbs in search results)
INVALID_URL_CHARS: Set[str] = {'›', '‹', '»', '«', '\u203a', '\u2039'}

# Uruguay-specific TLDs
URUGUAY_TLDS: List[str] = ['.com.uy', '.gub.uy', '.org.uy', '.edu.uy', '.net.uy', '.uy']

def is_mercadolibre_listing_url(url: str) -> bool:
    """Return True for MercadoLibre listing/search/category pages (not single product)."""
    if not url:
        return False
    try:
        p = urlparse(url.lower())
        # Common UY listing host
        if p.netloc.startswith("listado.mercadolibre.com.uy"):
            return True
        # Some category listings live on main domain
        if p.netloc in ("www.mercadolibre.com.uy", "mercadolibre.com.uy"):
            path = p.path or ""
            # Category/listing structures (best-effort)
            if path.startswith("/listado") or "/listado/" in path:
                return True
            if "/c/" in path:
                return True
        return False
    except Exception:
        return False


def is_mercadolibre_product_url(url: str) -> bool:
    """Return True for MercadoLibre single product pages (UY)."""
    if not url:
        return False
    try:
        u = url.lower()
        p = urlparse(u)
        if p.netloc.endswith("mercadolibre.com.uy"):
            # VTEX-like ML product permalink path contains /p/MLU...
            if "/p/" in p.path and "mlu" in p.path:
                return True
        # Dedicated product host
        if p.netloc.startswith("articulo.mercadolibre.com.uy"):
            # Common pattern: /MLU-123456789-...
            if p.path.startswith("/mlu-"):
                return True
        return False
    except Exception:
        return False


def sanitize_ecommerce_url(url: str) -> Optional[str]:
    """
    Sanitize and validate e-commerce URLs with Uruguay-specific handling.
    
    Handles:
    1. URLs with breadcrumb characters (›, », etc.) from search result snippets
    2. URLs with duplicate http:// or https:// segments (concatenated URLs)
    3. URLs with trailing garbage text
    4. Malformed TLD patterns (e.g., tata.com.uy.Visit -> tata.com.uy)
    5. Non-ASCII path components
    
    Args:
        url: URL to sanitize
        
    Returns:
        Cleaned URL or None if invalid
        
    Example:
        >>> sanitize_ecommerce_url("https://store.com.uy/product › category")
        'https://store.com.uy/product'
    """
    if not url:
        return None
        
    original_url = url
    
    # Check for breadcrumb characters that indicate malformed URL
    if any(char in url for char in INVALID_URL_CHARS):
        logger.debug(f"URL contains breadcrumb chars, sanitizing: {url[:100]}...")
        # Take only the part before any breadcrumb character
        for char in INVALID_URL_CHARS:
            if char in url:
                url = url.split(char)[0]
    
    # Handle duplicate http:// or https:// in URL (concatenated URLs)
    http_count = url.lower().count('http://')
    https_count = url.lower().count('https://')
    
    if http_count + https_count > 1:
        logger.debug(f"URL contains multiple protocols, extracting first: {url[:100]}...")
        # Find the first valid URL segment
        match = re.match(r'(https?://[^\s]+?)(?=https?://|$)', url)
        if match:
            url = match.group(1)
        else:
            # Fallback: take content up to second http
            parts = re.split(r'(?=https?://)', url)
            if parts and parts[0]:
                url = parts[0]
            elif len(parts) > 1:
                url = parts[1]
    
    # Remove trailing garbage (non-URL characters at the end)
    # Valid URL characters: alphanumeric, -, _, ., ~, :, /, ?, #, [, ], @, !, $, &, ', (, ), *, +, ,, ;, =, %
    url = re.sub(r'[^\w\-._~:/?#\[\]@!$&\'()*+,;=%]+$', '', url)
    
    # Remove any remaining trailing slashes followed by garbage
    url = re.sub(r'/[^/]*[^\w\-._~:/?#\[\]@!$&\'()*+,;=%/][^/]*$', '', url)
    
    # Remove trailing dots (e.g., "tata.com.uy..." -> "tata.com.uy")
    url = re.sub(r'\.+$', '', url)
    
    # Fix malformed domain extensions where garbage is appended after valid TLD
    # This catches patterns like "tata.com.uy.Visit" -> "tata.com.uy"
    # Look for valid Uruguay TLDs followed by garbage (e.g., .uy.SomeText)
    malformed_tld_pattern = r'(\.(?:com\.uy|gub\.uy|org\.uy|edu\.uy|net\.uy|uy|com|org|net))(\.[A-Z][a-zA-Z]+)(?:/|$)'
    match = re.search(malformed_tld_pattern, url)
    if match:
        # Remove the garbage extension
        url = url.replace(match.group(2), '', 1)
        logger.debug(f"Removed malformed TLD extension: {match.group(2)}")
    
    # Validate the cleaned URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.debug(f"Invalid URL after sanitization: {url}")
            return None
            
        # Ensure scheme is http or https
        if parsed.scheme not in ('http', 'https'):
            logger.debug(f"Invalid scheme in URL: {url}")
            return None
            
        # Enhanced domain validation - check for valid TLD structure
        netloc = parsed.netloc.lower()
        if '.' not in netloc:
            logger.debug(f"Invalid domain in URL (no dots): {url}")
            return None
        
        # Check for obviously invalid domain patterns
        # Domain should not end with multiple dots or have very long extensions
        if netloc.endswith('.') or '..' in netloc:
            logger.debug(f"Invalid domain in URL (trailing/double dots): {url}")
            return None
        
        # Get the last part of domain (TLD) and validate it's reasonable
        domain_parts = netloc.split('.')
        last_part = domain_parts[-1]
        if len(last_part) > 10 or not last_part.isalpha():
            # TLDs are usually short (2-6 chars) and alphabetic
            # Exception for country codes with second-level domains like .com.uy
            if len(domain_parts) < 2 or len(domain_parts[-2]) > 10:
                logger.debug(f"Invalid domain TLD in URL: {url} (TLD: {last_part})")
                return None
            
    except Exception as e:
        logger.debug(f"URL parsing failed: {e}")
        return None
    
    if url != original_url:
        logger.debug(f"Sanitized URL: {original_url[:80]}... -> {url}")
        
    return url


def is_likely_product_url(url: str, query_terms: Optional[List[str]] = None) -> bool:
    """
    Determine if a URL is likely a product page based on structural patterns.
    
    Uses platform-agnostic patterns rather than hardcoded product-specific terms.
    
    Args:
        url: URL to analyze
        query_terms: Optional list of search terms for relevance filtering
        
    Returns:
        True if URL is likely a product page
        
    Example:
        >>> is_likely_product_url("https://store.com.uy/producto/123")
        True
        >>> is_likely_product_url("https://store.com.uy/category/shoes")
        False
    """
    u = url.lower()
    
    # Exclude obvious non-product/content/link-hubs
    exclude_patterns = (
        "wikipedia.org",
        "evisos.com.uy", 
        "foodbevg.com",
        "acg.com.uy",
        "/search",
        "/busca", 
        "/resultados",
        "/results",
        "/category/",
        "/categories/",
        "/collections/",
        "/collection/",
        "/list/",
        "/filtros",
        "/filters",
        "/ordenar",
        "/sort",
        "javascript:",
        "mailto:",
        "#",
        "/account",
        "/login",
        "/register", 
        "/contact",
        "/about",
        "/politica",
        "/terminos",
        "/help",
        "/ayuda",
        "/cart",
        "/checkout",
        "/wishlist"
    )
    
    if any(bad in u for bad in exclude_patterns):
        return False
        
    # Exclude pagination and search parameters
    if any(token in u for token in ("?page=", "&page=", "?q=", "?search=", "&q=", "?sort=", "&sort=")):
        return False
    
    # Strong product URL indicators (platform-agnostic)
    strong_product_tokens = (
        "/p/", "/product/", "/producto/", "/item/", "/sku/", "/prod/",
        ".producto", "/products/", "/articulo/", "/art/",
        "/dp/", "/gp/product/", "/i/"
    )
    if any(token in u for token in strong_product_tokens):
        return True
    
    # VTEX-style product URLs ending with '/p'
    if u.rstrip('/').endswith('/p'):
        return True
    
    # Numeric product IDs (common e-commerce pattern)
    if re.search(r'/\d{6,}', u):  # 6+ digit numbers often indicate product IDs
        return True
    
    # Dynamic query-based filtering (if search terms provided)
    if query_terms:
        # Check if URL contains any search terms (indicates relevance)
        query_lower = [term.lower() for term in query_terms if len(term) > 2]
        if any(term in u for term in query_lower):
            # URL contains search terms AND has deep structure = likely product
            if len(u.split('/')) >= 4:
                return True
    
    # Deep URL structure often indicates specific items (products)
    if len(u.split('/')) >= 5:  # Deep paths often lead to specific items
        # Additional validation: should contain meaningful path segments
        path_segments = u.split('/')[3:]  # Skip protocol and domain
        meaningful_segments = [s for s in path_segments if len(s) > 2 and not s.isdigit()]
        if len(meaningful_segments) >= 2:  # At least 2 meaningful path parts
            return True
    
    return False


def url_matches_query(url: str, query_terms: Optional[List[str]]) -> bool:
    """
    Check if a URL is relevant to the search query.
    
    Filters out category pages that don't match the product being searched.
    E.g., when searching for "plancha vapor", filter out "aspiradoras" and "mopas".
    
    Args:
        url: The URL to check
        query_terms: List of search terms to match against
        
    Returns:
        True if URL is relevant to query, False otherwise
        
    Example:
        >>> url_matches_query("https://store.com/planchas/vapor", ["plancha", "vapor"])
        True
        >>> url_matches_query("https://store.com/aspiradoras", ["plancha", "vapor"])
        False
    """
    if not query_terms:
        return True  # No query terms means accept all
    
    url_lower = url.lower()
    
    # Normalize query terms (remove short words, lowercase)
    normalized_terms = [term.lower() for term in query_terms if len(term) > 2]
    
    if not normalized_terms:
        return True
    
    # Check if URL contains any of the main search terms
    for term in normalized_terms:
        if term in url_lower:
            return True
    
    # Also check for common variations/stems
    # E.g., "plancha" matches "planchas", "vapor" matches "vaporizador"
    for term in normalized_terms:
        # Check if any URL path segment starts with the term or vice versa
        # Filter out empty segments to avoid false positives (any string starts with '')
        path_segments = [s for s in url_lower.split('/') if s and len(s) > 2]
        for segment in path_segments:
            # Check if segment starts with term (e.g., "planchas" starts with "plancha")
            if segment.startswith(term):
                return True
            # Check if term starts with segment (e.g., "plancha" starts with "planch")
            # Only if segment is at least 4 chars to avoid false matches
            if len(segment) >= 4 and term.startswith(segment):
                return True
    
    logger.debug(f"Filtered out URL not matching query terms {normalized_terms}: {url}")
    return False


def remove_duplicated_path_segments(url: str) -> str:
    """
    Detect and remove duplicated path segments in a URL.
    
    Examples:
    - Input:  https://loi.com.uy/electrodomesticos/orden-y-limpieza/electrodomesticos/orden-y-limpieza/planchas
    - Output: https://loi.com.uy/electrodomesticos/orden-y-limpieza/planchas
    
    - Input:  https://loi.com.uy/electrodomesticos/orden-y-limpieza/electrodomesticos
    - Output: https://loi.com.uy/electrodomesticos/orden-y-limpieza
    
    Args:
        url: URL that may contain duplicated path segments
        
    Returns:
        URL with duplicated segments removed
    """
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        if not path or path == '/':
            return url
        
        # Split path into segments, filtering empty ones
        segments = [s for s in path.split('/') if s]
        
        if len(segments) < 2:
            return url
        
        original_segments = segments.copy()
        found_duplicate = False
        
        # Pass 1: Look for repeating multi-segment patterns (2, 3, 4 segments)
        for pattern_len in range(2, min(len(segments) // 2 + 1, 5)):
            i = 0
            new_segments = []
            
            while i < len(segments):
                # Check if current position starts a duplicate of previous pattern
                if i >= pattern_len:
                    # Compare current slice with previous pattern_len segments in new_segments
                    if len(new_segments) >= pattern_len:
                        prev_pattern = new_segments[-pattern_len:]
                        current_slice = segments[i:i + pattern_len]
                        
                        if prev_pattern == current_slice:
                            # Skip this duplicate pattern
                            i += pattern_len
                            found_duplicate = True
                            continue
                
                new_segments.append(segments[i])
                i += 1
            
            if found_duplicate:
                segments = new_segments
                break
        
        # Pass 2: Remove single segment duplicates (e.g., /a/b/a -> /a/b)
        # This catches cases like /electrodomesticos/orden-y-limpieza/electrodomesticos
        seen_segments: Set[str] = set()
        final_segments: List[str] = []
        
        for seg in segments:
            if seg in seen_segments:
                # This segment already appeared earlier - skip it
                found_duplicate = True
                logger.debug(f"Removing duplicate single segment: {seg}")
                continue
            seen_segments.add(seg)
            final_segments.append(seg)
        
        if found_duplicate or final_segments != original_segments:
            # Reconstruct URL with deduplicated path
            new_path = '/' + '/'.join(final_segments)
            if parsed.path.endswith('/'):
                new_path += '/'
            
            new_url = parsed._replace(path=new_path).geturl()
            logger.debug(f"Removed duplicated path segments: {url} -> {new_url}")
            return new_url
        
        return url
        
    except Exception as e:
        logger.debug(f"Error removing duplicated path segments from {url}: {e}")
        return url


def extract_links_from_html(html_content: str, base_url: str) -> List[str]:
    """
    Extract links from HTML content that might have been missed by web crawlers.
    
    Handles various link patterns including:
    - Standard href attributes
    - data-href and data-url attributes (JS-heavy sites)
    - onclick handlers with URLs
    
    Args:
        html_content: Raw HTML content
        base_url: Base URL for resolving relative links
        
    Returns:
        List of extracted URLs (absolute)
    """
    from urllib.parse import urljoin
    
    if not html_content:
        return []
    
    links: List[str] = []
    try:
        # Extract href attributes from anchor tags
        href_pattern = r'href=["\']([^"\']+)["\']'
        href_matches = re.findall(href_pattern, html_content, re.IGNORECASE)
        
        # Extract data-href and data-url attributes (common in JS-heavy sites)
        data_href_pattern = r'data-href=["\']([^"\']+)["\']'
        data_url_pattern = r'data-url=["\']([^"\']+)["\']'
        
        data_href_matches = re.findall(data_href_pattern, html_content, re.IGNORECASE)
        data_url_matches = re.findall(data_url_pattern, html_content, re.IGNORECASE)
        
        # Extract URLs from onclick handlers and other JS patterns
        js_url_pattern = r'(?:window\.location|location\.href)\s*=\s*["\']([^"\']+)["\']'
        js_url_matches = re.findall(js_url_pattern, html_content, re.IGNORECASE)
        
        # Combine all extracted URLs
        all_matches = href_matches + data_href_matches + data_url_matches + js_url_matches
        
        # Convert relative URLs to absolute
        for match in all_matches:
            if match.startswith('http'):
                links.append(match)
            elif match.startswith('/'):
                links.append(urljoin(base_url, match))
            elif not match.startswith('#') and not match.startswith('javascript:'):
                links.append(urljoin(base_url, match))
        
        logger.debug(f"Extracted {len(links)} links from HTML content")
        
    except Exception as e:
        logger.debug(f"Error extracting links from HTML: {e}")
    
    return links

