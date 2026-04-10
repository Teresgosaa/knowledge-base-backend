from typing import Any, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str
    cypher: Optional[str] = None
    result_count: int = 0
    success: bool = True
