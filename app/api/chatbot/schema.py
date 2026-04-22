from typing import Literal, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    retrieval_mode: Literal["graph_qa", "rag_anything", "hybrid"] = "hybrid"


class TokenUsage(BaseModel):
    prompt: int
    completion: int
    total: int


class HybridSources(BaseModel):
    graph_used: bool
    vector_used: bool
    graph_result_count: int
    vector_context: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str
    cypher: Optional[str] = None
    result_count: int = 0
    success: bool = True
    retrieval_mode: str = "graph_qa"
    tokens: Optional[TokenUsage] = None
    sources: Optional[HybridSources] = None
