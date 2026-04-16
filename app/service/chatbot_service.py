from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
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

The database is a knowledge graph extracted from procurement/contract documents. Nodes represent entities (suppliers, materials, manufacturers, etc.) and are connected via relationships.

=== CRITICAL: LABEL SYSTEM ===
The database has nodes with TWO kinds of labels:
- LightRAG labels: Russian names like `поставщик`, `материал`, `производитель` (always present on entities)
- Layered labels: English names like `Supplier`, `Material`, `Manufacture` with additional `Layered` label (present only on promoted/layered nodes)
Prefer using the English Layered labels (e.g. `Manufacture`, `Material`) when they exist, but be aware some nodes may only have the Russian LightRAG labels.

=== CRITICAL: HOW TO FIND RELATED ENTITIES ===

There are TWO ways entities can be related. ALWAYS try direct relationships FIRST:

1. DIRECT graph relationships between entity nodes (PRIMARY):
   Entity nodes often have DIRECT relationships to each other. Use `(a)--(b)` (undirected) to traverse.
   Example graph: Manufacture -- Material -- Price, Material -- Quantity

2. MENTIONED_IN via Clause (SECONDARY, may not exist):
   (Entity)-[:MENTIONED_IN]->(Clause)
   Entities in the same Clause belong together.

ALWAYS use direct `(a)--(b)` traversal as the primary approach. Use MENTIONED_IN only if you see it in the SAMPLE RELATIONSHIPS section of the schema below.

CORRECT — Find materials with prices and quantities for a manufacturer:
  MATCH (mf)
  WHERE (mf:Manufacture OR mf.entity_type = 'производитель')
    AND (mf.entity_id CONTAINS 'FG Wilson' OR mf.name CONTAINS 'FG Wilson')
  MATCH (mf)--(m:Material)
  OPTIONAL MATCH (m)--(p) WHERE (p:Price OR p.entity_type = 'цена')
  OPTIONAL MATCH (m)--(q) WHERE (q:Quantity OR q.entity_type = 'количество')
  RETURN COALESCE(m.name, m.entity_id) AS material,
         COALESCE(p.value, p.entity_id) AS price,
         COALESCE(q.value, q.entity_id) AS quantity
  LIMIT 50

CORRECT — Find all entities directly connected to a known entity:
  MATCH (mf) WHERE mf.entity_id CONTAINS 'FG Wilson'
  MATCH (mf)--(n)
  RETURN labels(n) AS node_type, n.entity_type AS entity_type,
         COALESCE(n.name, n.entity_id) AS name,
         COALESCE(n.value, n.entity_id) AS value,
         n.description AS description
  LIMIT 50

WRONG — Cartesian product (DO NOT use):
  MATCH (m:Material), (p:Price), (q:Quantity)
  WHERE m.doc_id = did AND p.doc_id = did AND q.doc_id = did
  RETURN m.name, p.value, q.value

=== CRITICAL: PROPERTY CONVENTIONS ===
- `entity_id`: ALWAYS present. Primary identifying value. Also holds numeric values for Price, Quantity, Cost etc when `value` is absent.
- `name`: may or may NOT be present. Always fall back to entity_id.
- `value`: numeric value on Price, Quantity, Volume, Cost, etc. MAY BE ABSENT — always use COALESCE(n.value, n.entity_id).
- `code`: used on Manufacture, PartNumber, ENSCode.
- `doc_id`: links entity to source document.
- `label`: normalized label/type string.
- `description`: textual description (often contains rich context about the entity).

CRITICAL: For entity NAMES use COALESCE(n.name, n.entity_id). For numeric VALUES use COALESCE(n.value, n.entity_id). The `value` property may not exist on all nodes.

When filtering by entity name/value, check multiple properties:
  For manufacturer: mf.entity_id CONTAINS 'X' OR mf.code CONTAINS 'X' OR mf.name CONTAINS 'X'
  For material: m.entity_id CONTAINS 'X' OR m.name CONTAINS 'X'
  For supplier: s.entity_id CONTAINS 'X' OR s.name CONTAINS 'X'

Rules:
1. Generate ONLY the Cypher query, nothing else.
2. Do not include any explanation, markdown formatting, or backticks.
3. Always use MATCH/WHERE patterns to find relevant nodes.
4. For multi-entity queries: use direct relationship traversal `(a)--(b)` as the PRIMARY approach.
5. NEVER use bare comma-separated MATCH for multiple entity types sharing only doc_id.
6. ALWAYS use COALESCE(n.name, n.entity_id) for entity names and COALESCE(n.value, n.entity_id) for numeric values.
7. Use case-insensitive matching (CONTAINS, toLower) for user-provided string values.
8. When matching entity types, check BOTH label `(p:Price)` AND entity_type `(p.entity_type = 'цена')` to handle both promoted and non-promoted nodes.
9. Use LIMIT to cap results at 50.
10. If the question cannot be answered with the available data, return: RETURN "No data found" AS result
"""

CYPHER_FALLBACK_PROMPT = """You are a Neo4j Cypher query expert. The first attempt query returned empty or null results. Generate a SIMPLER fallback query using DIRECT relationship traversal.

These entity nodes have DIRECT graph relationships between them (check the SAMPLE RELATIONSHIPS section). They do NOT have MENTIONED_IN relationships.

PATTERN:
  1. Find the anchor entity by entity_id or name
  2. Traverse direct relationships using (anchor)--(related_node) — undirected
  3. Use COALESCE(n.name, n.entity_id) for entity names
  4. Use COALESCE(n.value, n.entity_id) for numeric values — `value` property may be absent
  5. Match entity types by BOTH label AND entity_type property: (n:Price OR n.entity_type = 'цена')

FALLBACK for "materials with prices and quantities for manufacturer X":
  MATCH (mf) WHERE mf.entity_id CONTAINS 'X'
  MATCH (mf)--(m) WHERE (m:Material OR m.entity_type IN ['наименованиематериала', 'материал'])
  OPTIONAL MATCH (m)--(p) WHERE (p:Price OR p.entity_type = 'цена')
  OPTIONAL MATCH (m)--(q) WHERE (q:Quantity OR q.entity_type = 'количество')
  RETURN COALESCE(m.name, m.entity_id) AS material,
         COALESCE(p.value, p.entity_id) AS price,
         COALESCE(q.value, q.entity_id) AS quantity
  LIMIT 50

If direct Material→Price/Quantity edges do not exist, return ALL nodes connected to the anchor:
  MATCH (mf) WHERE mf.entity_id CONTAINS 'X'
  MATCH (mf)--(n)
  RETURN labels(n) AS node_type, n.entity_type AS entity_type,
         COALESCE(n.name, n.entity_id) AS name,
         COALESCE(n.value, n.entity_id) AS value,
         n.description AS description
  LIMIT 50

Rules:
1. Generate ONLY the Cypher query.
2. ALWAYS use COALESCE(n.name, n.entity_id) for names and COALESCE(n.value, n.entity_id) for values.
3. Use (a)--(b) undirected traversal for relationships.
4. Match entity types by BOTH label AND entity_type property.
5. NEVER use MENTIONED_IN — it does not exist for these nodes.
6. NEVER use bare Cartesian product: MATCH (a), (b) WHERE a.doc_id = b.doc_id.
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
- Return answer in Russian
"""


class GraphQAService:
    def __init__(self) -> None:
        self._schema_cache: Optional[str] = None

    @staticmethod
    def _load_json_config(filename: str) -> list[dict[str, Any]]:
        path = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "setup_db"
            / filename
        )
        try:
            with open(path, encoding="utf-8") as fp:
                return json.load(fp)
        except Exception as exc:
            logger.warning("Failed to load config %s: %s", path, exc)
            return []

    def _get_openai_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            api_key=settings.yandex_cloud_api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            default_headers={"x-folder-id": settings.yandex_cloud_folder or ""},
        )

    def _build_schema_description(self) -> str:
        node_types = self._load_json_config("node_types.json")
        rel_types = self._load_json_config("relationship_types.json")
        parts: list[str] = []

        parts.append("=== NODE TYPES ===")
        parts.append(
            "Each type has: English label (graph_db_name), Russian name, Russian aliases, and key properties."
        )
        parts.append("Nodes may carry BOTH English and Russian labels simultaneously.")
        for nt in node_types:
            if not nt.get("is_active", True):
                continue
            gdb = nt["graph_db_name"]
            ru_name = nt["name"]
            aliases = nt.get("node_names", [])
            props = nt.get("node_definition", {}).get("properties", [])
            prop_details = []
            for p in props:
                if p["name"] == "uid":
                    continue
                desc = p.get("description", "")
                prop_details.append(
                    f"{p['name']}({p['type']}){'=' + desc if desc else ''}"
                )
            key_props = ", ".join(prop_details)
            alias_str = f" [Russian aliases: {', '.join(aliases)}]" if aliases else ""
            parts.append(f"  {gdb} ({ru_name}){alias_str}: {key_props}")

        parts.append("")
        parts.append("=== RELATIONSHIP TYPES ===")
        for rt in rel_types:
            if not rt.get("is_active", True):
                continue
            src = ", ".join(rt.get("source_types", [])) or "*"
            tgt = ", ".join(rt.get("target_types", [])) or "*"
            parts.append(f"  ({src})-[:{rt['rel_type']}]->({tgt}): {rt['name']}")

        try:
            entity_types = neo4j_service.get_entity_types()
            parts.append("")
            parts.append("=== LABELS ACTUALLY IN DATABASE ===")
            parts.append(", ".join(entity_types))

            parts.append("")
            parts.append("=== SAMPLE NODE PROPERTIES (from actual data) ===")
            for et in entity_types:
                try:
                    nodes = neo4j_service.get_nodes(entity_type=et, limit=1)
                    for n in nodes:
                        props = {
                            k: repr(v)[:80]
                            for k, v in n.items()
                            if k not in ("id", "entity_types") and v is not None
                        }
                        parts.append(f"  ({et}): {props}")
                        break
                except Exception:
                    continue

            parts.append("")
            parts.append("=== SAMPLE RELATIONSHIPS BETWEEN ENTITY NODES ===")
            driver = neo4j_service._get_driver()
            with driver.session() as session:
                try:
                    rel_result = session.run(
                        "MATCH (a)-[r]->(b) "
                        "WHERE a.doc_id IS NOT NULL AND b.doc_id IS NOT NULL "
                        "AND a.doc_id = b.doc_id "
                        "AND NOT 'Clause' IN labels(a) AND NOT 'Clause' IN labels(b) "
                        "AND NOT 'Document' IN labels(a) AND NOT 'Document' IN labels(b) "
                        "AND NOT 'DocumentVersion' IN labels(a) AND NOT 'DocumentVersion' IN labels(b) "
                        "AND NOT 'TextUnit' IN labels(a) AND NOT 'TextUnit' IN labels(b) "
                        "RETURN labels(a) AS src_labels, type(r) AS rel_type, labels(b) AS tgt_labels, "
                        "a.doc_id AS doc_id "
                        "LIMIT 30"
                    )
                    seen_rels: set[str] = set()
                    for rec in rel_result:
                        src = rec["src_labels"]
                        rt = rec["rel_type"]
                        tgt = rec["tgt_labels"]
                        key = f"{src}-{rt}->{tgt}"
                        if key not in seen_rels:
                            seen_rels.add(key)
                            parts.append(f"  {src} -[:{rt}]-> {tgt}")
                    if not seen_rels:
                        parts.append(
                            "  (no direct entity-to-entity relationships found)"
                        )
                except Exception as exc:
                    parts.append(f"  (failed to sample relationships: {exc})")
        except Exception as exc:
            logger.warning("Failed to query Neo4j for schema: %s", exc)

        return "\n".join(parts)

    def _get_schema_info(self) -> str:
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            self._schema_cache = self._build_schema_description()
            logger.info(
                "Schema info built (%d chars):\n%s",
                len(self._schema_cache),
                self._schema_cache[:2000],
            )
        except Exception as exc:
            logger.warning("Failed to fetch schema info: %s", exc)
            self._schema_cache = "Schema unavailable"

        return self._schema_cache

    def clear_schema_cache(self) -> None:
        self._schema_cache = None

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

    MAX_LLM_CONTEXT_CHARS = 30000

    def _generate_answer(
        self,
        client: openai.OpenAI,
        question: str,
        cypher: str,
        results: list[dict[str, Any]],
    ) -> str:
        total = len(results)
        shown = results[:20]
        results_json = json.dumps(shown, ensure_ascii=False, indent=2, default=str)

        context = (
            f"User question: {question}\n\n"
            f"Executed Cypher query:\n{cypher}\n\n"
            f"Query results ({total} records, showing first {len(shown)}):\n{results_json}"
        )

        if len(context) > self.MAX_LLM_CONTEXT_CHARS:
            context = context[: self.MAX_LLM_CONTEXT_CHARS]

        response = client.responses.create(
            model=f"gpt://{settings.yandex_cloud_folder}/{settings.yandex_cloud_model}",
            temperature=0.3,
            instructions=ANSWER_SYSTEM_PROMPT,
            input=context,
            max_output_tokens=2000,
        )
        return response.output_text.strip()

    def _generate_fallback_cypher(
        self, client: openai.OpenAI, question: str, original_cypher: str
    ) -> str:
        schema = self._get_schema_info()

        prompt = (
            CYPHER_FALLBACK_PROMPT
            + "\n\n"
            + schema
            + f"\n\nOriginal query that returned 0 results:\n{original_cypher}"
        )

        response = client.responses.create(
            model=f"gpt://{settings.yandex_cloud_folder}/{settings.yandex_cloud_model}",
            temperature=0.1,
            instructions=prompt,
            input=question,
            max_output_tokens=1000,
        )
        result = response.output_text.strip()

        if result.startswith("```cypher"):
            result = result[len("```cypher") :]
        elif result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        return result.strip()

    @staticmethod
    def _has_meaningful_results(results: list[dict[str, Any]]) -> bool:
        if not results:
            return False
        for row in results:
            non_null = [v for v in row.values() if v is not None]
            if non_null:
                return True
        return False

    async def ask(
        self, question: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        if not conversation_id:
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

            if not self._has_meaningful_results(results):
                logger.info(
                    "Query returned no meaningful results, trying fallback query"
                )
                fallback_cypher = await loop.run_in_executor(
                    None,
                    self._generate_fallback_cypher,
                    client,
                    question,
                    cypher,
                )
                logger.info(
                    "Fallback Cypher for question '%s': %s",
                    question[:80],
                    fallback_cypher,
                )
                fallback_results = await loop.run_in_executor(
                    None, self._execute_cypher, fallback_cypher
                )
                logger.info(
                    "Fallback Cypher returned %d records", len(fallback_results)
                )
                if self._has_meaningful_results(fallback_results):
                    results = fallback_results
                    cypher = fallback_cypher

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
