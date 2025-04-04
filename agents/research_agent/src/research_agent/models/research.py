from pydantic import BaseModel, Field
from typing import Optional


class ResearchRequest(BaseModel):
    """
    Research request model for LLM query
    """
    query: str = Field(..., description="The research question to be answered")
    model: str = Field(default="llama3.1", description="The LLM model to use")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum number of tokens in the response")
    additional_context: Optional[str] = Field(default=None, description="Optional additional context for the query")


class ResearchResponse(BaseModel):
    """
    Research response model with LLM result
    """
    result: str = Field(..., description="The research result from the LLM") 