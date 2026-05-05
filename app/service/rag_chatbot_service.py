from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

import openai
import requests

from app.settings.settings import settings

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = (
    "Ты — полезный ассистент, отвечающий на вопросы по документам из базы знаний. "
    "База знаний содержит презентации, документы, отчёты. "
    "Отвечай на русском языке. Будь точным и по существу. "
    "Если информация взята из презентации — укажи номер слайда. "
    "Если в контексте недостаточно информации, так и скажи. "
    "ВАЖНО: В текстах встречается формат '[X=N%] текст' — это означает что элемент "
    "расположен на N% от левого края слайда. Элементы с близким значением X% "
    "находятся в одной колонке или секции слайда. "
    "Используй это для определения к какой колонке относится каждый элемент."
)


class RAGChatbotService:
    def __init__(self) -> None:
        self._rag: Any = None
        self._initializing = False
        self._token_counter: dict = {"prompt": 0, "completion": 0}
        self._embedding_func: Any = None

    async def _ensure_rag(self) -> Any:
        if self._rag is not None:
            return self._rag

        if self._initializing:
            raise RuntimeError("RAG is currently initializing, please retry later")

        self._initializing = True
        try:
            import os

            import numpy as np
            import requests
            from lightrag.utils import wrap_embedding_func_with_attrs
            from raganything import RAGAnything, RAGAnythingConfig

            from app.service.node_config import get_entity_type_keys
            from app.service.rag_anything import (
                MAX_CONCURRENT_FILES,
                PARSER_OUTPUT_DIR,
                RAG_WORKING_DIR,
                patch_lightrag_prompts,
            )

            if settings.neo4j_uri:
                os.environ.setdefault("NEO4J_URI", settings.neo4j_uri)
            if settings.neo4j_user:
                os.environ.setdefault("NEO4J_USERNAME", settings.neo4j_user)
            if settings.neo4j_password:
                os.environ.setdefault("NEO4J_PASSWORD", settings.neo4j_password)

            patch_lightrag_prompts()

            YANDEX_EMBEDDING_DIM = 256
            _EMBED_URL = "https://ai.api.cloud.yandex.net:443/foundationModels/v1/textEmbedding"

            iam_resp = requests.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={"yandexPassportOauthToken": settings.yandex_cloud_oauth_token},
                timeout=30,
                verify=False,
            )
            iam_resp.raise_for_status()
            iam_token = iam_resp.json()["iamToken"]

            @wrap_embedding_func_with_attrs(
                embedding_dim=YANDEX_EMBEDDING_DIM,
                max_token_size=8192,
                model_name="yandex-text-search-doc",
            )
            async def embedding_func(texts: list[str]) -> np.ndarray:
                doc_uri = f"emb://{settings.yandex_cloud_folder}/text-search-doc/latest"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {iam_token}",
                    "x-folder-id": settings.yandex_cloud_folder or "",
                }
                loop = asyncio.get_event_loop()

                def _embed_one(text: str) -> list[float]:
                    delay = 2.0
                    for attempt in range(5):
                        resp = requests.post(
                            _EMBED_URL,
                            json={"modelUri": doc_uri, "text": text},
                            headers=headers,
                            timeout=30,
                            verify=False,
                        )
                        if resp.status_code == 429:
                            import time

                            time.sleep(delay * (2**attempt))
                            continue
                        resp.raise_for_status()
                        return resp.json()["embedding"]
                    raise RuntimeError("Embedding API returned 429 after 5 retries")

                embeddings: list[list[float]] = []
                for text in texts:
                    embedding = await loop.run_in_executor(None, _embed_one, text)
                    embeddings.append(embedding)
                    await asyncio.sleep(0.2)
                return np.array(embeddings, dtype=np.float32)

            async def llm_model_func(
                prompt: str,
                system_prompt: Optional[str] = None,
                history_messages: Optional[list] = None,
                **kwargs,
            ) -> str:
                try:
                    loop = asyncio.get_event_loop()

                    def _call() -> str:
                        messages = []
                        if system_prompt:
                            messages.append({"role": "system", "content": system_prompt})
                        _prompt = f"/no_think {prompt}" if "qwen" in settings.routerai_model.lower() else prompt
                        messages.append({"role": "user", "content": _prompt})
                        client = openai.OpenAI(
                            api_key=settings.routerai_api_key,
                            base_url=settings.routerai_base_url,
                        )
                        logger.info(
                            "RouterAI LLM call: prompt_len=%d sys_len=%d",
                            len(prompt),
                            len(system_prompt) if system_prompt else 0,
                        )
                        _create_kwargs: dict = {
                            "model": settings.routerai_model,
                            "messages": messages,
                            "temperature": 0.3,
                            "max_tokens": 3000,
                        }
                        if "qwen" in settings.routerai_model.lower():
                            _create_kwargs["extra_body"] = {"reasoning_effort": "low"}
                        response = client.chat.completions.create(**_create_kwargs)
                        text = response.choices[0].message.content or ""
                        if not text:
                            text = getattr(response.choices[0].message, "reasoning_content", None) or ""
                        logger.info("RouterAI LLM response text_len=%d", len(text))
                        if hasattr(response, "usage") and response.usage:
                            self._token_counter["prompt"] = self._token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
                            self._token_counter["completion"] = self._token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
                        return text

                    return await loop.run_in_executor(None, _call)
                except Exception as exc:
                    logger.error("Error calling RouterAI LLM: %s", exc)
                    return ""

            config = RAGAnythingConfig(
                parser="docling",
                parse_method="auto",
                working_dir=RAG_WORKING_DIR,
                parser_output_dir=PARSER_OUTPUT_DIR,
                enable_image_processing=True,
                enable_table_processing=True,
                enable_equation_processing=False,
                use_full_path=False,
                supported_file_extensions=[
                    ".pdf",
                    ".doc",
                    ".docx",
                    ".ppt",
                    ".pptx",
                    ".xls",
                    ".xlsx",
                    ".md",
                    ".txt",
                ],
                max_concurrent_files=MAX_CONCURRENT_FILES,
            )

            if settings.neo4j_uri:
                os.environ.setdefault("QDRANT_URL", settings.qdrant_uri)

            from lightrag import LightRAG
            from lightrag.kg.shared_storage import initialize_pipeline_status

            lightrag_instance = LightRAG(
                working_dir=RAG_WORKING_DIR,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                graph_storage="Neo4JStorage",
                kv_storage="JsonKVStorage",
                vector_storage="QdrantVectorDBStorage",
                doc_status_storage="JsonDocStatusStorage",
                chunk_token_size=1024,
                chunk_overlap_token_size=20,
                addon_params={
                    "language": "Russian",
                    "entity_types": get_entity_type_keys(),
                },
            )
            await lightrag_instance.initialize_storages()
            await initialize_pipeline_status()

            rag = RAGAnything(
                lightrag=lightrag_instance,
                config=config,
            )

            self._rag = rag
            self._embedding_func = embedding_func
            logger.info("RAGChatbotService: RAGAnything initialized for querying")
            return self._rag
        except Exception as exc:
            logger.error("Failed to initialize RAG for chatbot: %s", exc)
            raise
        finally:
            self._initializing = False

    async def retrieve(self, question: str, doc_filter: list[str] | None = None) -> dict[str, Any]:
        """Retrieve relevant context from vector store without generating a final answer."""
        try:
            rag = await self._ensure_rag()
            init_result = await rag._ensure_lightrag_initialized()
            if not init_result.get("success"):
                raise RuntimeError(init_result.get("error", "Failed to initialize LightRAG"))

            self._token_counter = {"prompt": 0, "completion": 0}

            if doc_filter and self._embedding_func:
                # Прямой поиск в Qdrant с фильтром по full_doc_id
                context = await self._retrieve_filtered(question, doc_filter)
            else:
                context = await rag.aquery(question, mode="mix")

            return {
                "success": True,
                "context": context,
                "tokens": {
                    "prompt": self._token_counter["prompt"],
                    "completion": self._token_counter["completion"],
                },
            }
        except Exception as exc:
            logger.error("RAG retrieve error: %s", exc)
            return {"success": False, "error": str(exc), "context": "", "tokens": {"prompt": 0, "completion": 0}}

    async def _retrieve_filtered(self, question: str, doc_filter: list[str]) -> str:
        """Поиск в Qdrant с фильтром по full_doc_id."""
        try:
            import numpy as np
            from qdrant_client import QdrantClient
            from qdrant_client.models import FieldCondition, Filter, MatchAny

            loop = asyncio.get_event_loop()
            embeddings = await self._embedding_func([question])
            query_vector = embeddings[0].tolist()

            client = QdrantClient(url=settings.qdrant_uri)
            collection = "lightrag_vdb_chunks_yandex_text_search_doc_256d"

            qdrant_filter = Filter(
                must=[FieldCondition(key="full_doc_id", match=MatchAny(any=doc_filter))]
            )

            results = await loop.run_in_executor(
                None,
                lambda: client.query_points(
                    collection_name=collection,
                    query=query_vector,
                    query_filter=qdrant_filter,
                    limit=20,
                    with_payload=True,
                )
            )

            chunks = [p.payload.get("content", "") for p in results.points if p.payload.get("content")]
            context = "\n\n".join(chunks)
            logger.info("Filtered Qdrant search: %d chunks from doc_filter=%s", len(chunks), doc_filter)
            return context
        except Exception as exc:
            logger.error("Filtered Qdrant search failed: %s, falling back to unfiltered", exc)
            rag = self._rag
            return await rag.aquery(question, mode="mix")

    async def ask(
        self,
        question: str,
        conversation_id: Optional[str] = None,
        mode: str = "mix",
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        if not conversation_id:
            conversation_id = uuid.uuid4().hex[:12]

        try:
            rag = await self._ensure_rag()
            init_result = await rag._ensure_lightrag_initialized()
            if not init_result.get("success"):
                raise RuntimeError(init_result.get("error", "Failed to initialize LightRAG"))

            # Добавляем историю к вопросу если она есть
            question_with_history = question
            if history:
                lines = ["Контекст предыдущего диалога:"]
                for msg in history[-6:]:
                    role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                    lines.append(f"{role}: {msg['content'][:300]}")
                lines.append(f"\nТекущий вопрос: {question}")
                question_with_history = "\n".join(lines)

            self._token_counter = {"prompt": 0, "completion": 0}
            answer = await rag.aquery(
                question_with_history,
                mode=mode,
                system_prompt=RAG_SYSTEM_PROMPT,
            )

            total = self._token_counter["prompt"] + self._token_counter["completion"]
            logger.info(
                "RAG tokens for question '%s': prompt=%d, completion=%d, total=%d",
                question[:80],
                self._token_counter["prompt"],
                self._token_counter["completion"],
                total,
            )

            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "mode": mode,
                "success": True,
                "tokens": {
                    "prompt": self._token_counter["prompt"],
                    "completion": self._token_counter["completion"],
                    "total": total,
                },
            }
        except Exception as exc:
            logger.error("RAGChatbot error: %s", exc, exc_info=True)
            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": f"Произошла ошибка при обработке запроса: {exc}",
                "mode": mode,
                "success": False,
                "tokens": None,
            }


rag_chatbot_service = RAGChatbotService()
