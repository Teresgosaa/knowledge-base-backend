from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import openai

from app.settings.settings import settings

logger = logging.getLogger(__name__)

HYBRID_ANSWER_PROMPT = """Ты — помощник, отвечающий на вопросы по договорным документам.

У тебя есть два источника данных:

[ДАННЫЕ ИЗ ГРАФА ЗНАНИЙ]
Структурированные факты, извлечённые из документов и сохранённые в Neo4j.
{graph_section}

[ФРАГМЕНТЫ ДОКУМЕНТОВ]
Релевантные куски текста из оригинальных документов, найденные по смыслу.
{vector_section}

Правила:
- Собери всю релевантную информацию из обоих источников
- Если источники содержат разные значения одного факта — проанализируй даты документов (дата подписания, дата вступления в силу, дата изменения) и определи, какое значение актуальнее на момент последнего изменения
- Значения с entity_type "предыдущая_стоимость", "предыдущая_цена" и т.п. — исторические, упоминай их только как справку
- Если один из источников пустой — используй другой
- Отвечай на русском языке
- Будь точным и лаконичным; всегда указывай из какого документа взято актуальное значение
- В текстах встречается формат '[X=N%] текст' — элемент расположен на N% от левого края слайда. Элементы с близким X% находятся в одной колонке или секции

ВАЖНО — при наличии нескольких значений одного атрибута (стоимость, цена, дата):
- Значения с entity_type, содержащим "предыдущ" (предыдущая_стоимость, предыдущая_цена и т.п.) — СТАРЫЕ/ИСТОРИЧЕСКИЕ. Упоминай только как справку, не как основной ответ.
- Значения с entity_type "стоимость", "цена", "тариф" и т.п. (без "предыдущ") — АКТУАЛЬНЫЕ. Они имеют приоритет.
- Если несколько документов содержат разные значения одного факта — предпочитай значение из документа с БОЛЕЕ ПОЗДНЕЙ датой вступления в силу (дата начала действия, дата подписания). Если даты недоступны — дополнения/изменения к договору (addendum, amendment) приоритетнее оригинала.
- Всегда указывай из какого документа взят основной ответ (doc_id или название документа).
"""


class HybridChatbotService:
    def __init__(self) -> None:
        pass

    def _get_openai_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
        )

    def _format_graph_section(self, graph_data: dict[str, Any]) -> str:
        if not graph_data.get("success") or not graph_data.get("results"):
            error = graph_data.get("error", "")
            return f"Данные из графа недоступны. {error}".strip()

        results = graph_data["results"]
        cypher = graph_data.get("cypher", "")
        lines = []
        if cypher:
            lines.append(f"Запрос: {cypher}")
        lines.append(f"Найдено записей: {len(results)}")
        shown = results[:20]
        lines.append(json.dumps(shown, ensure_ascii=False, indent=2, default=str))
        return "\n".join(lines)

    def _format_vector_section(self, vector_data: dict[str, Any]) -> str:
        if not vector_data.get("success") or not vector_data.get("context"):
            error = vector_data.get("error", "")
            return f"Данные из векторной базы недоступны. {error}".strip()
        return str(vector_data["context"])

    def _generate_hybrid_answer(
        self,
        client: openai.OpenAI,
        question: str,
        graph_section: str,
        vector_section: str,
        token_counter: dict,
    ) -> str:
        import time
        # Ограничиваем размер контекста чтобы не превышать лимиты
        graph_section = graph_section[:8000]
        vector_section = vector_section[:15000]
        system_prompt = HYBRID_ANSWER_PROMPT.format(
            graph_section=graph_section,
            vector_section=vector_section,
        )
        for attempt in range(6):
            try:
                _create_kwargs: dict = {
                    "model": settings.routerai_model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"/no_think {question}" if "qwen" in settings.routerai_model.lower() else question},
                    ],
                    "max_tokens": 2000,
                }
                if "qwen" in settings.routerai_model.lower():
                    _create_kwargs["extra_body"] = {"enable_thinking": False}
                response = client.chat.completions.create(**_create_kwargs)
                if hasattr(response, "usage") and response.usage:
                    token_counter["prompt"] = token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
                    token_counter["completion"] = token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
                text = response.choices[0].message.content or ""
                if not text:
                    text = getattr(response.choices[0].message, "reasoning_content", None) or ""
                return text.strip()
            except openai.RateLimitError:
                wait = 5 * (2 ** attempt)
                logger.warning("OpenRouter 429 (hybrid answer) — waiting %ds", wait)
                time.sleep(wait)
        return ""

    async def ask(
        self,
        question: str,
        conversation_id: str | None = None,
        history: list[dict] | None = None,
        doc_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.service.chatbot_service import graph_qa_service
        from app.service.rag_chatbot_service import rag_chatbot_service

        if not conversation_id:
            conversation_id = uuid.uuid4().hex[:12]

        try:
            logger.info("Hybrid.ask() started: %s", question[:80])

            graph_task = asyncio.create_task(graph_qa_service.retrieve(question))
            vector_task = asyncio.create_task(rag_chatbot_service.retrieve(question))

            graph_data, vector_data = await asyncio.gather(
                graph_task, vector_task, return_exceptions=True
            )

            if isinstance(graph_data, Exception):
                logger.error("Graph retrieve failed: %s", graph_data)
                graph_data = {"success": False, "error": str(graph_data), "results": [], "cypher": None, "tokens": {"prompt": 0, "completion": 0}}

            if isinstance(vector_data, Exception):
                logger.error("Vector retrieve failed: %s", vector_data)
                vector_data = {"success": False, "error": str(vector_data), "context": "", "tokens": {"prompt": 0, "completion": 0}}

            graph_section = self._format_graph_section(graph_data)
            vector_section = self._format_vector_section(vector_data)

            filter_text = ""
            if doc_filter:
                filter_text = f"[ФИЛЬТР] Отвечай ТОЛЬКО на основе документов с идентификаторами: {', '.join(doc_filter)}. Игнорируй информацию из других документов.\n\n"

            history_text = ""
            if history:
                lines = ["[ИСТОРИЯ ДИАЛОГА]"]
                for msg in history[-6:]:  # последние 3 обмена
                    role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                    lines.append(f"{role}: {msg['content'][:500]}")
                history_text = "\n".join(lines) + "\n\n"

            token_counter: dict = {"prompt": 0, "completion": 0}
            client = self._get_openai_client()
            loop = asyncio.get_event_loop()

            answer = await loop.run_in_executor(
                None,
                self._generate_hybrid_answer,
                client,
                question,
                filter_text + history_text + graph_section,
                vector_section,
                token_counter,
            )

            graph_tokens = graph_data.get("tokens", {})
            vector_tokens = vector_data.get("tokens", {})
            total_prompt = (
                token_counter.get("prompt", 0)
                + graph_tokens.get("prompt", 0)
                + vector_tokens.get("prompt", 0)
            )
            total_completion = (
                token_counter.get("completion", 0)
                + graph_tokens.get("completion", 0)
                + vector_tokens.get("completion", 0)
            )

            logger.info(
                "Hybrid tokens: graph=%d, vector=%d, answer=%d, total=%d",
                graph_tokens.get("prompt", 0) + graph_tokens.get("completion", 0),
                vector_tokens.get("prompt", 0) + vector_tokens.get("completion", 0),
                token_counter.get("prompt", 0) + token_counter.get("completion", 0),
                total_prompt + total_completion,
            )

            graph_results = graph_data.get("results", [])
            vector_context = vector_data.get("context", "")

            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "cypher": graph_data.get("cypher"),
                "result_count": len(graph_results),
                "success": True,
                "tokens": {
                    "prompt": total_prompt,
                    "completion": total_completion,
                    "total": total_prompt + total_completion,
                },
                "sources": {
                    "graph_used": graph_data.get("success", False) and len(graph_results) > 0,
                    "vector_used": vector_data.get("success", False) and bool(vector_context),
                    "graph_result_count": len(graph_results),
                    "vector_context": vector_context[:1000] if vector_context else "",
                },
            }

        except Exception as exc:
            logger.error("Hybrid error: %s", exc, exc_info=True)
            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": f"Произошла ошибка при обработке запроса: {exc}",
                "cypher": None,
                "result_count": 0,
                "success": False,
                "tokens": None,
            }


hybrid_chatbot_service = HybridChatbotService()
