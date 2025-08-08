import json
from shared.logging import setup_logger
from shared.ollama_client import OllamaClient
import re

logger = setup_logger("query_generator")

# System prompt to guide the LLM for generating search queries
SYSTEM_PROMPT = """
You are a Web Search Query Generator AI. Your task is to generate 8 optimized search queries for finding a specific product online, focusing on purchase intent in Uruguay, specifically Montevideo. The queries should be suitable for e-commerce sites and general web search engines.

Requirements:
1. Generate exactly 8 distinct queries.
2. **Purchase Intent**: include intent keywords such as "comprar", "precio", "oferta", "tienda", "online"
3. **Product Clarity**:Iinsert the provided product name verbatim.
4. **Location**: include "Montevideo" and/or "Uruguay" in at least 6 of the 8 queries.
5. **Natural phrasing**: emulate how local shoppers search; vary structure (e.g. brand + product, product + feature, generic product type + location).
6. Avoid overly technical terms unless part of the product name.
7. **Format**:
    - Output ONLY a JSON array of 8 strings.
    - No surrounding text, line breaks, or comments.

IMPORTANT: 
- Your goal is to generate search queries that will return individual product pages, not category, collection, or listing pages. 
- Each query should be as specific as possible, including product model, brand, or unique features if available.
- If the product has a unique identifier (SKU, model number, price), include it in the query.
- Avoid generic queries that would return a list of products or a category page.


Example of a good query: "comprar impermeable invierno Uruguay"
Example of a good query: "tienda bicicleta GT 2025 Montevideo"
Example of a bad query: "impermeables invierno" (too broad, likely to return category pages, not related to Uruguay)


Return a JSON array of 8 strings, with each string being a search query.
Ensure the output is ONLY the JSON array, with no other text or explanations.
Ensure that each query string within the JSON array is a single line and does not contain any newline characters (e.g., \n).
"""

def strip_json_code_block(text: str) -> str:
    text = text.strip()
    
    # Regex to find content within ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match:
        # If found, return the stripped content of the first capturing group
        return match.group(1).strip()
    
    # Fallback: If no markdown code block is found,
    # try to extract content between the first '{' or '['
    # and the last '}' or ']'. This is a bit more fragile but
    # can work if the LLM omits the markdown fences.
    
    start_char_map = {'{': '}', '[': ']'}
    first_bracket_idx = text.find('[')
    first_curly_idx = text.find('{')
    
    start_idx = -1
    
    if first_bracket_idx != -1 and first_curly_idx != -1:
        start_idx = min(first_bracket_idx, first_curly_idx)
    elif first_bracket_idx != -1:
        start_idx = first_bracket_idx
    elif first_curly_idx != -1:
        start_idx = first_curly_idx
        
    if start_idx != -1:
        expected_end_char = start_char_map[text[start_idx]]
        # Find the last occurrence of the corresponding closing character
        end_idx = text.rfind(expected_end_char)
        
        if end_idx > start_idx:
            # Slice the string and strip whitespace
            return text[start_idx : end_idx+1].strip()
            
    # If no JSON structure is found by either method, return the original (stripped) text
    return text

class QueryGeneratorAgent:
    def __init__(self, model_name="phi3", temperature=0.1):
        self.model_name = model_name
        self.temperature = temperature
        self.llm_client = OllamaClient()
        logger.info(f"QueryGeneratorAgent initialized with model: {model_name}, temp: {temperature}")

    async def __aenter__(self):
        logger.debug("QueryGeneratorAgent context entered")
        await self.llm_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("QueryGeneratorAgent context exited")
        await self.llm_client.__aexit__(exc_type, exc_val, exc_tb)

    async def generate_queries(self, product: str):
        logger.info(f"Generating queries for product: {product}")
        
        # Use system prompt for instructions, user prompt for product
        user_prompt = f"Product: {product}"

        raw_llm_response = ""
        try:
            raw_llm_response = await self.llm_client.generate(
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                model=self.model_name,
                temperature=self.temperature
            )
            logger.debug(f"Ollama response: {raw_llm_response}")
            
            clean_response = strip_json_code_block(raw_llm_response)
            queries = json.loads(clean_response)
            
            if not isinstance(queries, list):
                if isinstance(queries, str):
                    try:
                        potential_list = json.loads(queries)
                        if isinstance(potential_list, list):
                            queries = potential_list
                        else:
                            raise ValueError("Ollama did not return a JSON array after reparsing string.")
                    except json.JSONDecodeError:
                        raise ValueError(f"Ollama did not return a valid JSON array. Raw after strip: {clean_response if 'clean_response' in locals() else 'N/A'}")
                else:
                    raise ValueError("Ollama did not return a JSON array")
            
            if not all(isinstance(q, str) for q in queries):
                logger.warning(f"Ollama response contained non-string elements: {queries}. Filtering.")
                queries = [q for q in queries if isinstance(q, str)]
                if not queries:
                    raise ValueError("Ollama response had no valid string queries after filtering.")

            return queries, raw_llm_response
        except json.JSONDecodeError as jde:
            logger.error(f"JSONDecodeError in generate_queries for product {product}: {jde}. Raw response: {raw_llm_response}. Cleaned attempt: {clean_response if 'clean_response' in locals() else 'N/A'}")
            return [], raw_llm_response 
        except Exception as e:
            logger.error(f"Error generating queries for product {product}: {e}. Raw response: {raw_llm_response}", exc_info=True)
            return [], raw_llm_response 