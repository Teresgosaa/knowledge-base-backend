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
from app.service.hybrid_chatbot_service import hybrid_chatbot_service
from app.service.rag_chatbot_service import rag_chatbot_service
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
        "Chatbot query from user %s (%s): %s",
        current_user.username,
        request.retrieval_mode,
        request.question[:80],
    )

    if request.retrieval_mode == "rag_anything":
        result = await rag_chatbot_service.ask(
            question=request.question,
            conversation_id=request.conversation_id,
        )
        result["retrieval_mode"] = "rag_anything"
    elif request.retrieval_mode == "hybrid":
        result = await hybrid_chatbot_service.ask(
            question=request.question,
            conversation_id=request.conversation_id,
        )
        result["retrieval_mode"] = "hybrid"
    else:
        result = await graph_qa_service.ask(
            question=request.question,
            conversation_id=request.conversation_id,
        )
        result["retrieval_mode"] = "graph_qa"

    try:
        message_service = BaseService(db, Message)
        await message_service.create_object(
            {
                "agent_id": request.retrieval_mode,
                "conversation_id": result["conversation_id"],
                "message_id": uuid.uuid4().hex,
                "message": request.question,
                "response": result["answer"],
                "user_id": current_user.id,
            }
        )
    except Exception as exc:
        logger.error("Failed to save chat message to DB: %s", exc, exc_info=True)

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

    # Capture raw LLM response before validation
    schema = graph_qa_service._get_schema_info()
    from app.service.chatbot_service import CYPHER_SYSTEM_PROMPT
    from app.settings.settings import settings as _settings
    import openai as _openai
    raw_response = client.chat.completions.create(
        model=f"gpt://{_settings.yandex_cloud_folder}/{_settings.yandex_cloud_model}",
        temperature=0.1,
        messages=[
            {"role": "system", "content": CYPHER_SYSTEM_PROMPT + "\n\n" + schema},
            {"role": "user", "content": request.question},
        ],
        max_tokens=1000,
    )
    raw_llm_text = (raw_response.choices[0].message.content or "").strip()

    token_counter: dict = {"prompt": 0, "completion": 0}
    cypher = await loop.run_in_executor(
        None, graph_qa_service._generate_cypher, client, request.question, token_counter
    )
    results = await loop.run_in_executor(None, graph_qa_service._execute_cypher, cypher)
    return {
        "question": request.question,
        "raw_llm_response": raw_llm_text[:500],
        "cypher": cypher,
        "result_count": len(results),
        "results": results[:10],
    }
