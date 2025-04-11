"""
Tool for extracting product URLs from search engine HTML results using LLM providers.
"""

import json
import re
from typing import Dict, List, Any
from shared.logging import setup_logger
from prompts.product_extractor_prompt import PRODUCT_EXTRACTOR_SYSTEM_PROMPT, PRODUCT_EXTRACTOR_HUMAN_PROMPT
from .llm_provider import LLMProvider, get_llm_client
from llm.utils.token_utils import truncate_messages_to_fit_token_limit, num_tokens_from_messages, get_token_limit
from llm.config.model_config import get_model_config, get_provider_from_model, MODEL_CONFIGS

logger = setup_logger("product_extractor_tool")

def truncate_html(html: str, max_tokens: int) -> str:
    """
    Truncate HTML content to fit within token limits
    
    Args:
        html: The HTML content to truncate
        max_tokens: Maximum number of tokens allowed
        
    Returns:
        Truncated HTML content
    """
    # Rough estimation: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    
    if len(html) <= max_chars:
        return html
        
    # Find a good truncation point (end of a tag)
    truncated = html[:max_chars]
    last_tag_end = truncated.rfind('>')
    
    if last_tag_end != -1:
        truncated = truncated[:last_tag_end + 1]
        
    return truncated

class ProductExtractorTool:
    """Tool for extracting product URLs from search engine HTML results"""
    
    def __init__(self, provider: LLMProvider = LLMProvider.OLLAMA, model: str = "mixtral"):
        """
        Initialize the product extractor tool
        
        Args:
            provider: The LLM provider to use (Ollama or OpenAI)
            model: The model to use for extraction
        """
        self.name = "product_extractor"
        self.description = "Extract product URLs from search engine HTML results"
        self.provider = provider
        self.model = model
        self.parameters = {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "The HTML content to analyze"
                },
                "query": {
                    "type": "string",
                    "description": "The search query used"
                },
                "provider": {
                    "type": "string",
                    "description": "The LLM provider to use",
                    "enum": [p.value for p in LLMProvider],
                    "default": provider.value
                },
                "model": {
                    "type": "string",
                    "description": "The model to use for extraction",
                    "default": model
                }
            },
            "required": ["html", "query"]
        }
        
    async def execute(self, html: str, query: str, model: str = None) -> List[Dict[str, Any]]:
        """
        Extract product URLs from search engine HTML results
        
        Args:
            html: The HTML content to analyze
            query: The search query used
            model: The model to use for extraction (defaults to tool's default model)
            
        Returns:
            List of dictionaries containing URL, title, relevance, and match type
        """
        try:          
            # Create the prompt
            try:
                # Get the model and provider
                current_model = model or self.model
                
                # Get model configuration
                model_config = get_model_config(current_model)
                if not model_config:
                    logger.error(f"Model configuration not found for {current_model}")
                    return []
                
                # Create messages for token calculation
                messages = [
                    {"role": "system", "content": PRODUCT_EXTRACTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": PRODUCT_EXTRACTOR_HUMAN_PROMPT.replace("{query}", query).replace("{html}", html)}
                ]
                
                # Truncate messages if needed
                truncated_messages = truncate_messages_to_fit_token_limit(messages, current_model)
                if truncated_messages != messages:
                    logger.warning(f"Messages truncated to fit within token limit")
                    html = truncated_messages[1]["content"].split("{html}")[1].split("}")[0]
                
                human_prompt = PRODUCT_EXTRACTOR_HUMAN_PROMPT.replace("{query}", query).replace("{html}", html)
            except Exception as e:
                logger.error(f"Error creating human extractor prompt: {str(e)}")
                return []
            
            # Get the appropriate LLM client and generate response
            try:
                # Get the provider based on the model
                provider = get_provider_from_model(current_model)
                if not provider:
                    logger.error(f"Could not determine provider for model {current_model}")
                    return []
                
                # Ensure provider is a valid LLMProvider enum value
                if isinstance(provider, str):
                    try:
                        provider = LLMProvider(provider)
                    except ValueError:
                        logger.error(f"Invalid provider value: {provider}")
                        return []
                
                # Get the client for the provider
                client = get_llm_client(provider)
                if not client:
                    logger.error(f"Could not get client for provider {provider}")
                    return []
                
                # Use model configuration for parameters
                provider_kwargs = {
                    "max_tokens": model_config.max_tokens,
                    "temperature": model_config.temperature,
                }
                
                response = await client.generate(
                    prompt=human_prompt,
                    system=PRODUCT_EXTRACTOR_SYSTEM_PROMPT,
                    model=current_model,
                    **provider_kwargs
                )
            except Exception as e:
                error_msg = str(e)
                if "rate limit" in error_msg.lower() or "tpm" in error_msg.lower():
                    logger.error("OpenAI rate limit exceeded. Please try again later or upgrade your plan.")
                elif "maximum context length" in error_msg.lower():
                    logger.error(f"Token limit exceeded for model {current_model}. Please try with a different model or reduce the HTML content.")
                else:
                    logger.error(f"Error generating response: {error_msg}")
                return []
                
            # Log the raw response
            logger.debug(f"Raw response: {response}")
            
            # Clean the response to extract JSON
            try:
                # Remove any text before the first { and after the last }
                response = response.strip()
                
                # Try to find JSON object
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start == -1 or json_end == 0:
                    logger.error(f"No JSON object found in response. Response content: {response}")
                    return []
                
                json_str = response[json_start:json_end]
                logger.debug(f"Extracted JSON string: {json_str}")
                
                # Remove any comments or non-JSON text
                json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                
                # Try to fix common JSON formatting issues
                json_str = json_str.replace('\n', ' ').replace('\r', '')
                json_str = re.sub(r'\s+', ' ', json_str)
                
                # Ensure the JSON string starts and ends with braces
                if not json_str.startswith('{'):
                    json_str = '{' + json_str
                if not json_str.endswith('}'):
                    json_str = json_str + '}'
                
                logger.debug(f"Cleaned JSON string: {json_str}")
                
                # Try to parse the JSON
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {str(e)}")
                    logger.error(f"JSON string that failed to parse: {json_str}")
                    return []
                
                logger.debug(f"Parsed JSON result: {json.dumps(result, indent=2)}")
                
                # Validate the result structure
                if not isinstance(result, dict):
                    logger.error(f"Result is not a dictionary: {result}")
                    return []
                
                if "urls" not in result:
                    logger.error(f"Missing 'urls' field in result: {result}")
                    return []
                
                if not isinstance(result["urls"], list):
                    logger.error(f"'urls' field is not a list: {result['urls']}")
                    return []
                
                # Clean and validate URLs
                cleaned_urls = []
                for url_data in result["urls"]:
                    if not isinstance(url_data, dict):
                        logger.debug(f"Skipping invalid URL data: {url_data}")
                        continue
                        
                    # Ensure required fields
                    if "url" not in url_data:
                        logger.debug(f"Skipping URL data missing 'url' field: {url_data}")
                        continue
                        
                    # Clean the URL
                    url = url_data["url"].strip()
                    if not url.startswith(("http://", "https://")):
                        logger.debug(f"Skipping invalid URL format: {url}")
                        continue
                        
                    # Get title and relevance with defaults
                    title = url_data.get("title", "").strip()
                    relevance = float(url_data.get("relevance", 0.9))  # Default to 0.9 if not specified
                    
                    # Add to cleaned results
                    cleaned_urls.append({
                        "url": url,
                        "title": title,
                        "relevance": relevance,
                        "match_type": "similar"  # Default to similar since OpenAI doesn't provide this
                    })
                
                logger.info(f"Successfully extracted {len(cleaned_urls)} URLs")
                logger.debug(f"Final cleaned URLs: {json.dumps(cleaned_urls, indent=2)}")
                return cleaned_urls
                
            except Exception as e:
                logger.error(f"Error processing response: {str(e)}")
                logger.error(f"Response content: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting URLs: {str(e)}")
            return []
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

# Create a singleton instance with default provider and model
product_extractor = ProductExtractorTool() 
