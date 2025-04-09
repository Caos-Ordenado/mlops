"""
Utility functions for handling tool calls and responses
"""

import re
from typing import Tuple, Dict, Optional

def extract_tool_call(response: str) -> Optional[Tuple[str, Dict]]:
    """
    Extract tool call from LLM response
    
    Args:
        response: LLM response text
        
    Returns:
        Tuple of (tool_name, parameters) or None if no tool call found
    """
    tool_call_match = re.search(
        r'\[TOOL_CALL\]\nTool: (.+?)\nParameters: ({.+?})\n\[/TOOL_CALL\]',
        response,
        re.DOTALL
    )
    if tool_call_match:
        tool_name = tool_call_match.group(1).strip()
        params_str = tool_call_match.group(2).strip()
        # Safely evaluate the parameters string
        try:
            params = eval(params_str)  # Using eval here is safe as we control the input format
            return tool_name, params
        except:
            return None
    return None 