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
    "Если в контексте недостаточно информации, так и скажи."
)


class RAGChatbotService:
    def __init__(self) -> None:
        self._rag: Any = None
        self._initializing = False
        self._token_counter: dict = {"prompt": 0, "completion": 0}

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
                        messages.append({"role": "user", "content": prompt})
                        llm_folder = settings.yandex_cloud_folder
                        client = openai.OpenAI(
                            api_key="ignored",
                            base_url="https://ai.api.cloud.yandex.net/v1",
                            default_headers={
                                "Authorization": f"Api-Key {settings.yandex_cloud_api_key}",
                                "x-folder-id": llm_folder,
                            },
                        )
                        logger.info(
                            "Yandex LLM call: prompt_len=%d sys_len=%d",
                            len(prompt),
                            len(system_prompt) if system_prompt else 0,
                        )
                        response = client.chat.completions.create(
                            model=f"gpt://{llm_folder}/{settings.yandex_cloud_model}",
                            messages=messages,
                            temperature=0.3,
                            max_tokens=3000,
                        )
                        text = response.choices[0].message.content or ""
                        logger.info("Yandex LLM response text_len=%d", len(text))
                        if hasattr(response, "usage") and response.usage:
                            self._token_counter["prompt"] = self._token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
                            self._token_counter["completion"] = self._token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
                        return text

                    return await loop.run_in_executor(None, _call)
                except Exception as exc:
                    logger.error("Error calling Yandex Cloud LLM: %s", exc)
                    return ""

            config = RAGAnythingConfig(
                parser="docling",
                parse_method="auto",
                working_dir=RAG_WORKING_DIR,
                parser_output_dir=PARSER_OUTPUT_DIR,
                enable_image_processing=False,
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
            logger.info("RAGChatbotService: RAGAnything initialized for querying")
            return self._rag
        except Exception as exc:
            logger.error("Failed to initialize RAG for chatbot: %s", exc)
            raise
        finally:
            self._initializing = False

    async def retrieve(self, question: str) -> dict[str, Any]:
        """Retrieve relevant context from vector store without generating a final answer."""
        try:
            rag = await self._ensure_rag()
            init_result = await rag._ensure_lightrag_initialized()
            if not init_result.get("success"):
                raise RuntimeError(init_result.get("error", "Failed to initialize LightRAG"))

            self._token_counter = {"prompt": 0, "completion": 0}
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

    async def ask(
        self,
        question: str,
        conversation_id: Optional[str] = None,
        mode: str = "mix",
    ) -> dict[str, Any]:
        if not conversation_id:
            conversation_id = uuid.uuid4().hex[:12]

        try:
            rag = await self._ensure_rag()
            init_result = await rag._ensure_lightrag_initialized()
            if not init_result.get("success"):
                raise RuntimeError(init_result.get("error", "Failed to initialize LightRAG"))

            self._token_counter = {"prompt": 0, "completion": 0}
            answer = await rag.aquery(
                question,
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
