from typing import List, Dict, Any
import tiktoken
from ..config.model_config import ModelConfig, get_model_config, OLLAMA_MODELS

def num_tokens_from_messages(messages: List[Dict[str, str]], model: str) -> int:
    """Calculate the number of tokens used by a list of messages."""
    # Normalize model name to lowercase for case-insensitive comparison
    model_lower = model.lower()
    
    # Check if model is in OLLAMA_MODELS (case-insensitive)
    is_ollama_model = any(ollama_model.lower() == model_lower for ollama_model in OLLAMA_MODELS)
    
    # For Ollama models, use a rough estimation
    if is_ollama_model:
        # Rough estimation: 1 token ≈ 4 characters
        total_chars = sum(len(message.get("content", "")) for message in messages)
        return total_chars // 4
    
    # For OpenAI models, use tiktoken
    try:
        # Use a default encoding that works for most models
        encoding = tiktoken.get_encoding("cl100k_base")
        
        # Only try model-specific encoding for known OpenAI models
        if model_lower.startswith(("gpt-3", "gpt-4")):
            try:
                encoding = tiktoken.encoding_for_model(model_lower)
            except KeyError:
                # Continue with the default encoding
                pass
    except Exception as e:
        print(f"Warning: Error initializing tokenizer: {e}. Using character-based estimation.")
        # Fallback to character-based estimation
        total_chars = sum(len(message.get("content", "")) for message in messages)
        return total_chars // 4
    
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens

def get_token_limit(model: str) -> int:
    """Get the token limit for a specific model."""
    config = get_model_config(model)
    return config.token_limit

def is_token_limit_exceeded(messages: List[Dict[str, str]], model: str) -> bool:
    """Check if the token limit is exceeded for a given model and messages."""
    token_limit = get_token_limit(model)
    num_tokens = num_tokens_from_messages(messages, model)
    return num_tokens > token_limit

def truncate_messages_to_fit_token_limit(
    messages: List[Dict[str, str]], 
    model: str,
    max_tokens: int = 2000
) -> List[Dict[str, str]]:
    """Truncate messages to fit within the token limit while preserving the last message."""
    if not is_token_limit_exceeded(messages, model):
        return messages
    
    token_limit = get_token_limit(model)
    truncated_messages = []
    current_tokens = 0
    
    # Always keep the last message
    last_message = messages[-1]
    last_message_tokens = num_tokens_from_messages([last_message], model)
    
    # Calculate available tokens for previous messages
    available_tokens = token_limit - last_message_tokens - max_tokens
    
    # Add previous messages until we reach the limit
    for message in messages[:-1]:
        message_tokens = num_tokens_from_messages([message], model)
        if current_tokens + message_tokens <= available_tokens:
            truncated_messages.append(message)
            current_tokens += message_tokens
        else:
            break
    
    # Add the last message
    truncated_messages.append(last_message)
    return truncated_messages 