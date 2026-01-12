"""
JSON utilities for parsing LLM responses.

These utilities handle common issues with LLM-generated JSON:
- Markdown code fences (```json ... ```)
- Comments (// and /* */)
- Truncated responses from token limits
- Malformed JSON requiring regex extraction
"""

import re
from typing import Dict, List, Optional


def strip_json_code_block(text: str) -> str:
    """
    Remove markdown code fences and extract JSON content.
    
    Handles:
    - ```json ... ``` blocks
    - ``` ... ``` blocks (without language tag)
    - Raw JSON objects/arrays
    
    Args:
        text: Raw text that may contain markdown-wrapped JSON
        
    Returns:
        Cleaned JSON string ready for parsing
        
    Example:
        >>> strip_json_code_block('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
    """
    text = text.strip()
    
    # Regex to find content within ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Python-native extraction of the first {...} or [...] block (handles nesting)
    def extract_first_json_block(s: str) -> str:
        start = None
        stack = []
        for i, c in enumerate(s):
            if c in '{[':
                if start is None:
                    start = i
                stack.append(c)
            elif c in '}]' and stack:
                stack.pop()
                if not stack:
                    # Found the matching closing bracket
                    return s[start:i+1]
        return s.strip()  # fallback: return original

    return extract_first_json_block(text)


def remove_json_comments(text: str) -> str:
    """
    Remove JavaScript-style comments from JSON-like text.
    
    LLMs sometimes add comments to JSON output which makes it invalid.
    This removes both // line comments and /* */ block comments.
    
    Args:
        text: JSON-like text that may contain comments
        
    Returns:
        JSON text with comments removed
        
    Example:
        >>> remove_json_comments('{"key": "value" // this is a comment\\n}')
        '{"key": "value" \\n}'
    """
    # Remove // ... comments
    text = re.sub(r'//.*', '', text)
    # Remove /* ... */ block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


def fix_truncated_json(text: str) -> str:
    """
    Attempt to fix truncated JSON by adding missing closing brackets.
    
    When LLM responses are cut off due to token limits, JSON may be incomplete.
    This function attempts to close any open brackets/braces.
    
    Handles cases like:
    - {"queries": ["q1", "q2", "q3"  -> {"queries": ["q1", "q2", "q3"]}
    - ["q1", "q2", "q3"              -> ["q1", "q2", "q3"]
    
    Args:
        text: Potentially truncated JSON string
        
    Returns:
        JSON string with missing closers added
        
    Example:
        >>> fix_truncated_json('{"items": ["a", "b"')
        '{"items": ["a", "b"]}'
    """
    text = text.strip()
    if not text:
        return text
    
    # Count open and close brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    # If already balanced, return as-is
    if open_braces == close_braces and open_brackets == close_brackets:
        return text
    
    # Try to fix by adding missing closers
    fixed = text
    
    # Add missing ] first, then }
    missing_brackets = open_brackets - close_brackets
    missing_braces = open_braces - close_braces
    
    if missing_brackets > 0 or missing_braces > 0:
        # Remove trailing comma if present before adding closers
        fixed = fixed.rstrip().rstrip(',')
        
        # Handle truncated strings - check if we're in the middle of a quoted string
        quote_count = fixed.count('"')
        if quote_count % 2 == 1:
            # Odd number of quotes means unclosed string
            # Find the last complete quoted string and truncate there
            last_quote = fixed.rfind('"')
            if last_quote > 0:
                second_to_last = fixed.rfind('"', 0, last_quote)
                if second_to_last >= 0:
                    # Remove from the last comma before the incomplete string
                    last_comma = fixed.rfind(',', 0, second_to_last)
                    if last_comma > 0:
                        fixed = fixed[:last_comma]
        
        # Add missing closers
        fixed += ']' * max(0, missing_brackets)
        fixed += '}' * max(0, missing_braces)
    
    return fixed


def extract_fields_from_partial_json(text: str, fields: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Extract specific fields from malformed JSON using regex.
    
    Last-resort extraction when JSON parsing fails. Useful for recovering
    key fields like "page_type" or "product_name" from truncated responses.
    
    Args:
        text: Malformed JSON-like text
        fields: Optional list of field names to extract. If None, extracts
                common fields: page_type, identified_product_name, category_name, reasoning
        
    Returns:
        Dict of extracted field names to values
        
    Example:
        >>> extract_fields_from_partial_json('{"page_type": "PRODUCT", "name": "Test')
        {'page_type': 'PRODUCT'}
    """
    if fields is None:
        fields = ['page_type', 'identified_product_name', 'category_name', 'reasoning']
    
    result = {}
    
    for field in fields:
        # Match "field_name": "value" pattern
        pattern = rf'"{field}"\s*:\s*"([^"]*)"?'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1)
            # Clean up truncated values
            if value and not value.endswith('"'):
                value = value.rstrip() + "... (truncated)"
            result[field] = value
    
    return result


def extract_queries_with_regex(text: str) -> List[str]:
    """
    Extract query strings from malformed JSON using regex.
    
    Last-resort extraction when JSON parsing fails for query generation.
    Filters out JSON keys and very short/long strings.
    
    Args:
        text: Malformed JSON-like text containing quoted strings
        
    Returns:
        List of extracted query strings
        
    Example:
        >>> extract_queries_with_regex('{"queries": ["comprar laptop Uruguay", "laptop Montevideo"]}')
        ['comprar laptop Uruguay', 'laptop Montevideo']
    """
    # Find all double-quoted strings
    pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"'
    matches = re.findall(pattern, text)
    
    # Filter to keep only strings that look like search queries
    queries = []
    skip_keys = {'queries', 'query', 'search', 'results', 'page_type', 'reasoning'}
    
    for match in matches:
        # Skip JSON keys and very short strings
        if match.lower() in skip_keys:
            continue
        if len(match) < 5:  # Too short to be a search query
            continue
        if len(match) > 200:  # Too long
            continue
        # Keep strings that look like search queries (contain spaces or Spanish chars)
        if ' ' in match or any(c in match for c in 'áéíóúñü'):
            queries.append(match)
    
    return queries

