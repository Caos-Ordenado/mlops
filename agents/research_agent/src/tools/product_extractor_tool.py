"""
Tool for extracting product URLs from search engine HTML results using Ollama.
"""

import json
import re
from typing import Dict, List, Any
from shared.logging import setup_logger
from shared.ollama_client import OllamaClient
from prompts.product_extractor_prompt import PRODUCT_EXTRACTOR_SYSTEM_PROMPT, PRODUCT_EXTRACTOR_HUMAN_PROMPT

logger = setup_logger("product_extractor_tool")

class ProductExtractorTool:
    """Tool for extracting product URLs from search engine HTML results"""
    
    def __init__(self, model: str = "llama3.1"):
        """
        Initialize the product extractor tool
        
        Args:
            model: The Ollama model to use for extraction
        """
        self.name = "product_extractor"
        self.description = "Extract product URLs from search engine HTML results"
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
                "model": {
                    "type": "string",
                    "description": "The Ollama model to use for extraction",
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
            model: The Ollama model to use for extraction (defaults to tool's default model)
            
        Returns:
            List of dictionaries containing URL, title, relevance, and match type
        """
        try:          
            # Create the prompt
            try:
                human_prompt = PRODUCT_EXTRACTOR_HUMAN_PROMPT.replace("{query}", query).replace("{html}", html)
            except Exception as e:
                logger.error(f"Error creating human extractor prompt: {str(e)}")
                return []
            
            try:
                ollama_client = OllamaClient()
            except Exception as e:
                logger.error(f"Error initializing Ollama client: {str(e)}")
                return []

            async with ollama_client:
                try:
                    response = await ollama_client.generate(
                        prompt=human_prompt,
                        system=PRODUCT_EXTRACTOR_SYSTEM_PROMPT,  # Use system parameter for RAG context
                        model=model or self.model,
                        max_tokens=200000  # Increased for longer HTML content
                    )
                except Exception as e:
                    logger.error(f"Error getting response from Ollama: {str(e)}")
                    return []
                
                # Log the raw response
                logger.debug(f"Raw response: {response}")
                
                # Clean the response to extract JSON
                try:
                    # Remove any text before the first { and after the last }
                    response = response.strip()
                    # Strip markdown code fences
                    response = re.sub(r"^```(json)?", "", response.strip(), flags=re.IGNORECASE).strip("` \n")
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
                            
                        # Ensure other fields
                        title = url_data.get("title", "").strip()
                        relevance = float(url_data.get("relevance", 0.0))
                        match_type = url_data.get("match_type", "similar").lower()

                        if match_type not in {"exact", "similar", "category"}:
                            logger.debug(f"Invalid match_type '{match_type}', defaulting to 'similar'")
                            match_type = "similar"
                            
                        # Add to cleaned results
                        cleaned_urls.append({
                            "url": url,
                            "title": title,
                            "relevance": relevance,
                            "match_type": match_type
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

# Create a singleton instance with default model
product_extractor = ProductExtractorTool() 
