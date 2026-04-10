from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Optional

import openai
from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.db.chatbot import Message
from app.service.base_service import BaseService
from app.service.neo4j_service import neo4j_service
from app.settings.settings import settings

logger = logging.getLogger(__name__)


class AIStudioOpenAIClient:
    """Client for interacting with Yandex AI Studio agents via OpenAI SDK."""

    def __init__(self, api_key: str, folder_id: str) -> None:
        self._api_key = api_key
        self._folder_id = folder_id
        self._base_url = settings.yandex_cloud_ai_base_url
        # Use x-folder-id header instead of `project` arg for compatibility
        self._client = openai.OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            default_headers={"x-folder-id": self._folder_id},
        )

    async def send_message(
        self,
        agent_id: str,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Send message to an AI Studio agent and return structured result."""

        if history is None:
            history = []

        try:
            logger.info("Sending message to AI Studio agent %s", agent_id)

            logger.debug(
                "Calling AI Studio agent via OpenAI client: agent_id=%s, message_length=%d",
                agent_id,
                len(message),
            )

            try:
                response = self._client.responses.create(
                    prompt={"id": agent_id},
                    input=message,
                )
            except Exception as error:  # noqa: BLE001
                logger.error(
                    "Error calling AI Studio agent %s: %s",
                    agent_id,
                    str(error),
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": str(error),
                    "response": "",
                }

            logger.info("Received response from AI Studio agent")
            try:
                logger.debug("Raw agent response object: %r", response)
            except Exception:
                logger.debug("Raw agent response object could not be stringified")

            documents = {}
            output = getattr(response, "output", []) or []
            for output_item in output:
                if hasattr(output_item, "results"):
                    for result in output_item.results:
                        if result.filename not in documents:
                            documents[result.filename] = ""
                        documents[result.filename] += self.clean_text(result.text)

            output_text = getattr(response, "output_text", "") or ""

            return {
                "success": True,
                "text": output_text,
                "documents": documents,
                "usage": getattr(response, "usage", {}) or {},
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error calling AI Studio agent %s: %s",
                agent_id,
                str(exc),
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(exc),
                "response": "",
            }

    def clean_text(self, text):
        text = text.replace("•\n", "\n").replace("<PAGE/>", "")

        while "  " in text:
            text = text.replace("  ", " ")

        return text

    def collect_filenames(self, response) -> set:
        """
        Returns a set of filenames.
        """
        filenames = set()

        outputs = getattr(response, "output", [])

        for output in outputs:
            contents = getattr(output, "results", [])
            for annotation in contents:
                try:
                    filename = getattr(annotation, "filename", None)
                    if filename:
                        filenames.add(filename)
                except Exception:
                    continue  # skip malformed annotation

        return filenames


class MessageService(BaseService):
    async def get_objects(
        self,
        conversation_id: str | None = None,
    ) -> list:
        query = select(self._model).where(
            self._model.conversation_id == conversation_id
        )  # type: ignore

        result = await self._db.execute(query)
        instances = list(result.scalars().all())

        return instances

    async def like_message(self, message_id: int, like: bool) -> Message:
        stmt = (
            update(Message)
            .where(Message.id == message_id)
            .values(like=like)
            .execution_options(synchronize_session="fetch")
        )
        await self._db.execute(stmt)
        await self._db.commit()

        result = await self._db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return message

    async def get_frequent_questions(self, agent_id: str | None = None):
        if agent_id is None:
            return []

        message_query = (
            select(Message.message, func.count(Message.message).label("frequency"))
            .where(
                Message.created_at >= datetime.now() - timedelta(days=10),
                Message.agent_id == agent_id,
            )
            .group_by(Message.message)
            .order_by(func.count(Message.message).desc())
            .limit(3)
        )

        message_result = await self._db.execute(message_query)
        message_objects = list(message_result.scalars().all())

        return message_objects


def _resolve_ai_studio_client() -> AIStudioOpenAIClient:
    """Create and configure AI Studio OpenAI client from settings."""

    api_key = settings.yandex_cloud_api_key
    if not api_key:
        raise RuntimeError("YC_API_KEY is not configured.")

    folder_id = settings.yandex_cloud_ai_folder
    if not folder_id:
        raise RuntimeError("YC_FOLDER_ID is not configured.")

    return AIStudioOpenAIClient(api_key=api_key, folder_id=folder_id)


@lru_cache(maxsize=1)
def get_ai_studio_client() -> AIStudioOpenAIClient:
    """Return a cached AI Studio client instance."""

    return _resolve_ai_studio_client()


CYPHER_SYSTEM_PROMPT = """You are a Neo4j Cypher query expert. Given the user's question and the database schema below, generate a single valid Cypher query to answer the question.

Database schema information:
- Nodes have labels and properties. Common labels include entity types from a knowledge graph.
- Relationships connect nodes. Common relationship types include various semantic connections.
- Common node properties: name, doc_id, description, and other domain-specific fields.

Rules:
1. Generate ONLY the Cypher query, nothing else.
2. Do not include any explanation, markdown formatting, or backticks.
3. Always use MATCH/WHERE patterns to find relevant nodes.
4. Return relevant node properties and relationship information.
5. Use LIMIT to cap results at 50.
6. If the question cannot be answered with the available data, return: RETURN "No data found" AS result
"""

ANSWER_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about data stored in a knowledge graph (Neo4j database).

You will receive:
1. The user's original question
2. The Cypher query that was executed
3. The raw query results from the Neo4j database

Your task:
- Analyze the query results and provide a clear, natural language answer to the user's question.
- If the results are empty, say that no relevant data was found.
- Present structured data in a readable format (lists, tables when appropriate).
- Answer in the same language the user used for their question.
- Be concise but thorough.
"""


class GraphQAService:
    def __init__(self) -> None:
        self._schema_cache: Optional[str] = None

    def _get_openai_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            api_key=settings.yandex_cloud_api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            default_headers={"x-folder-id": settings.yandex_cloud_folder or ""},
        )

    def _get_schema_info(self) -> str:
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            entity_types = neo4j_service.get_entity_types()
            sample_nodes: list[dict[str, Any]] = []
            seen_types: set[str] = set()
            for et in entity_types[:5]:
                if et in seen_types:
                    continue
                seen_types.add(et)
                nodes = neo4j_service.get_nodes(entity_type=et, limit=2)
                for n in nodes:
                    props = {
                        k: type(v).__name__
                        for k, v in n.items()
                        if k not in ("id", "entity_types") and v is not None
                    }
                    sample_nodes.append({"label": et, "properties": props})

            schema_parts = ["Node labels: " + ", ".join(entity_types[:20])]
            for sn in sample_nodes:
                schema_parts.append(f"  ({sn['label']}): {sn['properties']}")

            self._schema_cache = "\n".join(schema_parts)
        except Exception as exc:
            logger.warning("Failed to fetch schema info: %s", exc)
            self._schema_cache = "Schema unavailable"

        return self._schema_cache

    def _generate_cypher(self, client: openai.OpenAI, question: str) -> str:
        schema = self._get_schema_info()

        response = client.responses.create(
            model=f"gpt://{settings.yandex_cloud_folder}/{settings.yandex_cloud_model}",
            temperature=0.1,
            instructions=CYPHER_SYSTEM_PROMPT + "\n\n" + schema,
            input=question,
            max_output_tokens=1000,
        )
        result = response.output_text.strip()

        result = result.strip()
        if result.startswith("```cypher"):
            result = result[len("```cypher") :]
        elif result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()

        return result

    def _execute_cypher(self, cypher: str) -> list[dict[str, Any]]:
        driver = neo4j_service._get_driver()
        with driver.session() as session:
            result = session.run(cypher)
            records = []
            for record in result:
                row: dict[str, Any] = {}
                for key in record.keys():
                    val = record[key]
                    if hasattr(val, "items"):
                        row[key] = dict(val)
                    elif isinstance(val, list):
                        row[key] = list(val)
                    else:
                        row[key] = val
                records.append(row)
            return records

    def _generate_answer(
        self,
        client: openai.OpenAI,
        question: str,
        cypher: str,
        results: list[dict[str, Any]],
    ) -> str:
        import json

        context = (
            f"User question: {question}\n\n"
            f"Executed Cypher query:\n{cypher}\n\n"
            f"Query results ({len(results)} records):\n{json.dumps(results[:50], ensure_ascii=False, indent=2, default=str)}"
        )

        response = client.responses.create(
            model=f"gpt://{settings.yandex_cloud_folder}/{settings.yandex_cloud_model}",
            temperature=0.3,
            instructions=ANSWER_SYSTEM_PROMPT,
            input=context,
            max_output_tokens=2000,
        )
        return response.output_text.strip()

    async def ask(self, question: str) -> dict[str, Any]:
        conversation_id = uuid.uuid4().hex[:12]

        try:
            client = self._get_openai_client()
            loop = asyncio.get_event_loop()

            cypher = await loop.run_in_executor(
                None, self._generate_cypher, client, question
            )
            logger.info("Generated Cypher for question '%s': %s", question[:80], cypher)

            results = await loop.run_in_executor(None, self._execute_cypher, cypher)
            logger.info("Cypher returned %d records", len(results))

            answer = await loop.run_in_executor(
                None,
                self._generate_answer,
                client,
                question,
                cypher,
                results,
            )

            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "cypher": cypher,
                "result_count": len(results),
                "success": True,
            }
        except Exception as exc:
            logger.error("GraphQA error: %s", exc, exc_info=True)
            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": f"An error occurred while processing your question: {exc}",
                "cypher": None,
                "result_count": 0,
                "success": False,
            }


graph_qa_service = GraphQAService()
