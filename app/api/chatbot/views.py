import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chatbot.schema import ChatRequest, ChatResponse
from app.db.chatbot import Message
from app.db.dependencies import get_db_session
from app.db.user import User
from app.service.base_service import BaseService
from app.service.chatbot_service import graph_qa_service
from app.utils.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/query", response_model=ChatResponse)
async def query_chatbot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    logger.info(
        "Chatbot query from user %s: %s",
        current_user.username,
        request.question[:80],
    )

    result = await graph_qa_service.ask(
        question=request.question,
        conversation_id=request.conversation_id,
    )

    message_service = BaseService(db, Message)
    await message_service.create_object(
        {
            "agent_id": "graph_qa",
            "conversation_id": result["conversation_id"],
            "message_id": uuid.uuid4().hex,
            "message": request.question,
            "response": result["answer"],
            "user_id": current_user.id,
        }
    )

    return ChatResponse(**result)


@router.post("/debug/schema")
async def debug_schema(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    graph_qa_service.clear_schema_cache()
    schema = graph_qa_service._get_schema_info()
    return {"schema": schema}


@router.post("/debug/cypher")
async def debug_cypher(
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: ChatRequest,
):
    import asyncio

    loop = asyncio.get_event_loop()
    client = graph_qa_service._get_openai_client()
    cypher = await loop.run_in_executor(
        None, graph_qa_service._generate_cypher, client, request.question
    )
    results = await loop.run_in_executor(None, graph_qa_service._execute_cypher, cypher)
    return {
        "question": request.question,
        "cypher": cypher,
        "result_count": len(results),
        "results": results[:10],
    }
