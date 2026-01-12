"""
Shared utility functions for agents.

This module provides common utilities for:
- JSON parsing and LLM response cleaning
- URL manipulation and deduplication
"""

from .json_utils import (
    strip_json_code_block,
    remove_json_comments,
    fix_truncated_json,
    extract_fields_from_partial_json,
)
from .url_utils import (
    same_domain,
    normalize_url,
    dedupe_urls_preserve_order,
)

__all__ = [
    # JSON utilities
    'strip_json_code_block',
    'remove_json_comments',
    'fix_truncated_json',
    'extract_fields_from_partial_json',
    # URL utilities
    'same_domain',
    'normalize_url',
    'dedupe_urls_preserve_order',
]

