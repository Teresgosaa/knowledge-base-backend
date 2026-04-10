import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.chatbot.schema import ChatRequest, ChatResponse
from app.db.user import User
from app.service.chatbot_service import graph_qa_service
from app.utils.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/query", response_model=ChatResponse)
async def query_chatbot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: ChatRequest,
):
    logger.info(
        "Chatbot query from user %s: %s",
        current_user.username,
        request.question[:80],
    )

    result = await graph_qa_service.ask(question=request.question)

    return ChatResponse(**result)
