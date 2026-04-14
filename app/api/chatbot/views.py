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
