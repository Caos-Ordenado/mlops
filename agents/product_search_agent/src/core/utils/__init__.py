"""
Local utilities for the product search agent.

This module provides domain-specific utilities for:
- E-commerce URL sanitization (Uruguay-specific)
- Product page detection patterns
- Query relevance filtering
- HTML link extraction
"""

from .ecommerce_url_utils import (
    INVALID_URL_CHARS,
    URUGUAY_TLDS,
    sanitize_ecommerce_url,
    is_likely_product_url,
    url_matches_query,
    remove_duplicated_path_segments,
    extract_links_from_html,
    is_mercadolibre_listing_url,
    is_mercadolibre_product_url,
)

__all__ = [
    'INVALID_URL_CHARS',
    'URUGUAY_TLDS',
    'sanitize_ecommerce_url',
    'is_likely_product_url',
    'url_matches_query',
    'remove_duplicated_path_segments',
    'extract_links_from_html',
    'is_mercadolibre_listing_url',
    'is_mercadolibre_product_url',
]

