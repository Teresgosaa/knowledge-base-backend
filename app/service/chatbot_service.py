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


CYPHER_SYSTEM_PROMPT = """Ты — эксперт по языку запросов Cypher для базы данных Neo4j. По вопросу пользователя и схеме базы данных сгенерируй один корректный Cypher-запрос.

ВАЖНО: Отвечай ТОЛЬКО Cypher-запросом. Никаких объяснений, никакого текста до или после запроса — только сам запрос.

База данных — это граф знаний, извлечённый из договорных документов. Узлы представляют сущности (поставщики, материалы, производители и т.д.) и связаны отношениями.

=== CRITICAL: LABEL SYSTEM ===
The database has nodes with TWO kinds of labels:
- LightRAG labels: Russian names like `поставщик`, `материал`, `производитель` (always present on entities)
- Layered labels: English names like `Supplier`, `Material`, `Manufacture` with additional `Layered` label (present only on promoted/layered nodes)
Prefer using the English Layered labels (e.g. `Manufacture`, `Material`) when they exist, but be aware some nodes may only have the Russian LightRAG labels.

=== CRITICAL: STANDALONE ENTITY QUERIES ===
Many entity types (DeliveryTerms, PaymentTerms, Destination, Subject, etc.) do NOT have direct graph relationships to other entity nodes. They are linked to documents ONLY through the shared `doc_id` property.

When the user asks about a specific entity TYPE (e.g. "what are the delivery terms?", "условия доставки", "условия оплаты"):
1. FIRST try a simple label/entity_type match WITHOUT relationship traversal:
   MATCH (n) WHERE (n:DeliveryTerms OR n.entity_type = 'условиядоставки')
   RETURN n.entity_id AS name, n.description AS description, n.doc_id AS doc_id
   LIMIT 50

2. If you need to show which document an entity belongs to, match by doc_id property:
   MATCH (n:DeliveryTerms)
   OPTIONAL MATCH (d:Document) WHERE d.doc_id = n.doc_id
   RETURN n.entity_id AS name, n.description AS description, n.doc_id AS doc_id, d.title AS document
   LIMIT 50

3. Do NOT require `(n)--(other)` relationship traversal for these standalone entity queries.

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

CORRECT — Find standalone entities by type (delivery terms, payment terms, etc.):
  MATCH (n) WHERE (n:DeliveryTerms OR n.entity_type = 'условиядоставки')
  RETURN n.entity_id AS name, n.description AS description, n.doc_id AS doc_id
  LIMIT 50

CORRECT — Find tariff/cost (Cost has multiple aliases — use IN [...], always include document dates):
  MATCH (n) WHERE (n:Cost OR n.entity_type IN ['стоимость', 'тариф', 'тарифперевозки', 'тарифнаперевозку', 'стоимостьперевозки'])
  OPTIONAL MATCH (n)--(route) WHERE (route.entity_type IN ['маршрут', 'пунктназначения', 'пунктотправления'])
  OPTIONAL MATCH (d:Document) WHERE d.doc_id = n.doc_id
  OPTIONAL MATCH (dt) WHERE dt.doc_id = n.doc_id AND (dt:StartDate OR dt.entity_type IN ['началодействия', 'датаначала'])
  RETURN COALESCE(n.value, n.entity_id) AS tariff, n.entity_type AS value_type,
         route.entity_id AS route, n.doc_id AS doc_id,
         d.title AS document_title, COALESCE(dt.date_value, dt.entity_id) AS effective_date
  LIMIT 50

IMPORTANT — for ANY query about financial values (стоимость, цена, тариф, сумма) or dates:
  Always fetch the document's effective date alongside the value so the LLM can determine which value is most current.
  Use: OPTIONAL MATCH (dt) WHERE dt.doc_id = n.doc_id AND dt.entity_type IN ['началодействия', 'датаначала']

WRONG — Cartesian product (DO NOT use):
  MATCH (m:Material), (p:Price), (q:Quantity)
  WHERE m.doc_id = did AND p.doc_id = did AND q.doc_id = did
  RETURN m.name, p.value, q.value

WRONG — Requiring relationship traversal for standalone entities (DO NOT use):
  MATCH (dt:DeliveryTerms)--(d:Document)
  RETURN dt.entity_id, d.title

=== CRITICAL: PROPERTY CONVENTIONS ===
- `entity_id`: ALWAYS present. Primary identifying value. Also holds numeric values for Price, Quantity, Cost etc when `value` is absent.
- `name`: may or may NOT be present. Always fall back to entity_id.
- `value`: numeric value on Price, Quantity, Volume, Cost, etc. MAY BE ABSENT — always use COALESCE(n.value, n.entity_id).
- `code`: used on Manufacture, PartNumber, ENSCode.
- `doc_id`: links entity to source document.
- `label`: normalized label/type string.
- `description`: textual description (often contains rich context about the entity).

CRITICAL: For entity NAMES use COALESCE(n.name, n.entity_id). For numeric VALUES use COALESCE(n.value, n.entity_id). The `value` property may not exist on all nodes.

=== CRITICAL: entity_type VALUES ARE NORMALIZED (NO SPACES) ===
The `entity_type` property stores Russian names WITHOUT spaces: 'условиядоставки' (NOT 'условия доставки'), 'условияоплаты' (NOT 'условия оплаты'), 'суммадоговорасндс' (NOT 'сумма договора с ндс'), etc.
When filtering by entity_type, ALWAYS remove spaces from Russian names:
  WRONG: n.entity_type = 'условия доставки'
  RIGHT: n.entity_type = 'условиядоставки'
  WRONG: n.entity_type = 'условия оплаты'
  RIGHT: n.entity_type = 'условияоплаты'
Check the Russian aliases in the NODE TYPES section above — they show the exact normalized values stored in entity_type.

When filtering by entity name/value, check multiple properties:
  For manufacturer: mf.entity_id CONTAINS 'X' OR mf.code CONTAINS 'X' OR mf.name CONTAINS 'X'
  For material: m.entity_id CONTAINS 'X' OR m.name CONTAINS 'X'
  For supplier: s.entity_id CONTAINS 'X' OR s.name CONTAINS 'X'

Rules:
1. Generate ONLY the Cypher query, nothing else.
2. Do not include any explanation, markdown formatting, or backticks.
3. Always use MATCH/WHERE patterns to find relevant nodes.
4. For queries about a specific entity TYPE (without naming a related entity), use simple label/entity_type match WITHOUT relationship traversal.
5. For multi-entity queries: use direct relationship traversal `(a)--(b)` as the PRIMARY approach.
6. NEVER use bare comma-separated MATCH for multiple entity types sharing only doc_id.
7. ALWAYS use COALESCE(n.name, n.entity_id) for entity names and COALESCE(n.value, n.entity_id) for numeric values.
8. Use case-insensitive matching (CONTAINS, toLower) for user-provided string values.
9. When matching entity types, check BOTH the English label AND entity_type property. If a node type has MULTIPLE Russian aliases listed, use IN [...] to match ANY of them — because the actual entity_type in the database may be any one of those aliases:
   CORRECT for Cost/тариф: WHERE (n:Cost OR n.entity_type IN ['стоимость', 'тариф', 'тарифперевозки', 'тарифнаперевозку', 'стоимостьперевозки'])
   WRONG (picks only one alias): WHERE (n:Cost OR n.entity_type = 'стоимостьперевозки')
   Remember: entity_type values have NO spaces.
10. Use LIMIT to cap results at 50.
11. NEVER return a sentinel like "No data found". Always generate a MATCH query — even if unsure, try the most likely match.
12. AVOID UNION. Use OPTIONAL MATCH instead to combine results in one query.
    If you must use UNION, BOTH parts MUST return EXACTLY the same column aliases — otherwise it is a syntax error in Cypher.
    WRONG: MATCH (a) RETURN a.name AS name UNION MATCH (b) RETURN b.entity_id AS id
    RIGHT: MATCH (a) RETURN a.name AS name UNION MATCH (b) RETURN b.entity_id AS name
13. NEVER write SQL syntax (SELECT, FROM as top-level keywords). This is Cypher, not SQL.
"""

CYPHER_FALLBACK_PROMPT = """You are a Neo4j Cypher query expert. The first attempt query returned empty or null results. Generate a SIMPLER fallback query.

IMPORTANT: Many entity types (DeliveryTerms, PaymentTerms, Destination, Subject, PaymentForm, etc.) are STANDALONE — they have NO direct graph relationships. For these, use a simple label/entity_type match:

  MATCH (n) WHERE (n:DeliveryTerms OR n.entity_type = 'условиядоставки')
  RETURN n.entity_id AS name, n.description AS description, n.doc_id AS doc_id
  LIMIT 50

To connect standalone entities to documents, match by doc_id property:
  MATCH (n:DeliveryTerms)
  OPTIONAL MATCH (d:Document) WHERE d.doc_id = n.doc_id
  RETURN n.entity_id AS name, n.description AS description, n.doc_id AS doc_id, d.title AS document
  LIMIT 50

For entity types that DO have direct relationships (check SAMPLE RELATIONSHIPS section), use direct traversal:
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

If direct edges do not exist, return ALL nodes connected to the anchor:
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
3. For entity types NOT appearing in SAMPLE RELATIONSHIPS, use simple label/entity_type match WITHOUT relationship traversal.
4. Match entity types by BOTH label AND entity_type property. If a type has multiple aliases (shown as `entity_type IN [...]` in NODE TYPES), use IN [...] to match ANY of them:
   CORRECT: WHERE (n:Cost OR n.entity_type IN ['стоимость', 'тариф', 'тарифперевозки', 'тарифнаперевозку', 'стоимостьперевозки'])
5. NEVER use bare Cartesian product: MATCH (a), (b) WHERE a.doc_id = b.doc_id.
6. entity_type values are NORMALIZED: no spaces. Use 'условиядоставки' NOT 'условия доставки'. Check NODE TYPES for exact values.
7. NEVER return a sentinel like "No data found". Always generate a MATCH query.
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

IMPORTANT — when multiple values exist for the same attribute (e.g. cost, price, date):
- Values with entity_type containing "предыдущ" (предыдущая_стоимость, предыдущая_цена, etc.) are OLD/HISTORICAL values — mention them only as context, not as the primary answer.
- Values with entity_type "стоимость", "цена", "тариф" etc. (without "предыдущ") are CURRENT values — these take priority.
- If only a previous value is found and no current one, state clearly that only a historical value is available.
- When multiple documents contain conflicting values for the same fact, analyze the dates in the data (signing date, effective date, amendment date) and determine which value is most recent. Present the most recent value as the primary answer.
- Always indicate which document the primary answer comes from (doc_id or document title if available).
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
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
        )

    def _build_schema_description(self) -> str:
        node_types = self._load_json_config("node_types.json")
        rel_types = self._load_json_config("relationship_types.json")
        parts: list[str] = []

        parts.append("=== NODE TYPES ===")
        parts.append(
            "Each type has: English label (graph_db_name), Russian name, Russian aliases (=entity_type values), and key properties."
        )
        parts.append("Nodes may carry BOTH English and Russian labels simultaneously.")
        parts.append(
            "IMPORTANT: When a node type has MULTIPLE Russian aliases, the entity_type in the database can be ANY of them. Use IN [...] when filtering."
        )
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
            with driver.session(database=settings.neo4j_database) as session:
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

    def _generate_cypher(self, client: openai.OpenAI, question: str, token_counter: dict) -> str:
        schema = self._get_schema_info()

        response = client.chat.completions.create(
            model=settings.routerai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": CYPHER_SYSTEM_PROMPT + "\n\n" + schema},
                {"role": "user", "content": question},
            ],
            max_tokens=1000,
        )
        if hasattr(response, "usage") and response.usage:
            token_counter["prompt"] = token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
            token_counter["completion"] = token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
        result = (response.choices[0].message.content or "").strip()

        result = result.strip()
        if result.startswith("```cypher"):
            result = result[len("```cypher") :]
        elif result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()

        # Validate that the result looks like a Cypher query
        cypher_keywords = ("MATCH", "RETURN", "WITH", "CALL", "CREATE", "MERGE", "OPTIONAL")
        if not any(result.upper().startswith(kw) for kw in cypher_keywords):
            logger.warning("LLM did not return a Cypher query, got: %s", result[:200])
            # Return empty result so fallback strategies (_generate_fallback_cypher, _try_direct_entity_query) can run
            result = "MATCH (n) WHERE 1=0 RETURN n.entity_id LIMIT 0"

        return result

    def _execute_cypher(self, cypher: str) -> list[dict[str, Any]]:
        driver = neo4j_service._get_driver()
        with driver.session(database=settings.neo4j_database) as session:
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
        token_counter: dict,
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

        response = client.chat.completions.create(
            model=settings.routerai_model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            max_tokens=2000,
        )
        if hasattr(response, "usage") and response.usage:
            token_counter["prompt"] = token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
            token_counter["completion"] = token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
        return (response.choices[0].message.content or "").strip()

    def _generate_fallback_cypher(
        self, client: openai.OpenAI, question: str, original_cypher: str, token_counter: dict
    ) -> str:
        schema = self._get_schema_info()

        prompt = (
            CYPHER_FALLBACK_PROMPT
            + "\n\n"
            + schema
            + f"\n\nOriginal query that returned 0 results:\n{original_cypher}"
        )

        response = client.chat.completions.create(
            model=settings.routerai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=1000,
        )
        if hasattr(response, "usage") and response.usage:
            token_counter["prompt"] = token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
            token_counter["completion"] = token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)
        result = (response.choices[0].message.content or "").strip()

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
        sentinel_values = {"no data found", "нет данных"}
        for row in results:
            non_null = [v for v in row.values() if v is not None]
            if not non_null:
                continue
            all_sentinels = all(
                isinstance(v, str) and v.strip().lower() in sentinel_values
                for v in row.values()
                if v is not None
            )
            if not all_sentinels:
                return True
        return False

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return "".join(c for c in text.lower() if c not in " -/.,!?")

    def _try_direct_entity_query(
        self, question: str
    ) -> tuple[list[dict[str, Any]], str]:
        normalized_q = self._normalize_for_match(question)
        node_types = self._load_json_config("node_types.json")

        for nt in node_types:
            if not nt.get("is_active", True):
                continue
            if nt.get("layer_type") != "semantic":
                continue

            gdb = nt["graph_db_name"]
            ru_name = nt["name"]
            aliases = nt.get("node_names", [])

            all_terms = [ru_name] + aliases
            matched_alias = None
            for term in all_terms:
                norm_term = self._normalize_for_match(term)
                if norm_term and norm_term in normalized_q:
                    matched_alias = aliases[0] if aliases else norm_term
                    break

            if matched_alias is None:
                continue

            logger.info(
                "Direct entity fallback matched node type %s (alias=%s) for question '%s'",
                gdb,
                matched_alias,
                question[:80],
            )

            queries = [
                (
                    f"MATCH (n) WHERE (n:{gdb} OR n.entity_type = '{matched_alias}') "
                    f"RETURN n.entity_id AS name, n.description AS description, "
                    f"n.doc_id AS doc_id LIMIT 50"
                ),
                (
                    f"MATCH (n) WHERE n.entity_type = '{matched_alias}' "
                    f"RETURN n.entity_id AS name, n.description AS description, "
                    f"n.doc_id AS doc_id LIMIT 50"
                ),
            ]

            for cypher in queries:
                try:
                    records = self._execute_cypher(cypher)
                    if self._has_meaningful_results(records):
                        logger.info(
                            "Direct entity query returned %d records: %s",
                            len(records),
                            cypher,
                        )
                        return records, cypher
                except Exception as exc:
                    logger.debug("Direct entity query failed: %s", exc)
                    continue

        return [], ""

    async def retrieve(self, question: str) -> dict[str, Any]:
        """Retrieve structured data from Neo4j without generating a final answer."""
        try:
            client = self._get_openai_client()
            loop = asyncio.get_event_loop()
            token_counter: dict = {"prompt": 0, "completion": 0}

            cypher = await loop.run_in_executor(None, self._generate_cypher, client, question, token_counter)
            results = await loop.run_in_executor(None, self._execute_cypher, cypher)

            if not self._has_meaningful_results(results):
                fallback_cypher = await loop.run_in_executor(
                    None, self._generate_fallback_cypher, client, question, cypher, token_counter
                )
                fallback_results = await loop.run_in_executor(None, self._execute_cypher, fallback_cypher)
                if self._has_meaningful_results(fallback_results):
                    results = fallback_results
                    cypher = fallback_cypher

            if not self._has_meaningful_results(results):
                direct_results, direct_cypher = await loop.run_in_executor(
                    None, self._try_direct_entity_query, question
                )
                if self._has_meaningful_results(direct_results):
                    results = direct_results
                    cypher = direct_cypher

            return {
                "success": True,
                "cypher": cypher,
                "results": results,
                "tokens": token_counter,
            }
        except Exception as exc:
            logger.error("GraphQA retrieve error: %s", exc)
            return {"success": False, "error": str(exc), "results": [], "cypher": None, "tokens": {"prompt": 0, "completion": 0}}

    async def ask(
        self, question: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        if not conversation_id:
            conversation_id = uuid.uuid4().hex[:12]

        try:
            logger.info("GraphQA.ask() started for question: %s", question[:80])
            client = self._get_openai_client()
            loop = asyncio.get_event_loop()
            token_counter: dict = {"prompt": 0, "completion": 0}

            cypher = await loop.run_in_executor(
                None, self._generate_cypher, client, question, token_counter
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
                    token_counter,
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

            if not self._has_meaningful_results(results):
                logger.info(
                    "LLM queries returned no results, trying direct entity fallback"
                )
                direct_results, direct_cypher = await loop.run_in_executor(
                    None, self._try_direct_entity_query, question
                )
                if self._has_meaningful_results(direct_results):
                    results = direct_results
                    cypher = direct_cypher
                    logger.info(
                        "Direct entity fallback succeeded with %d records",
                        len(results),
                    )

            answer = await loop.run_in_executor(
                None,
                self._generate_answer,
                client,
                question,
                cypher,
                results,
                token_counter,
            )

            total_tokens = token_counter["prompt"] + token_counter["completion"]
            logger.info(
                "GraphQA tokens for question '%s': prompt=%d, completion=%d, total=%d",
                question[:80],
                token_counter["prompt"],
                token_counter["completion"],
                total_tokens,
            )

            return {
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "cypher": cypher,
                "result_count": len(results),
                "success": True,
                "tokens": {
                    "prompt": token_counter["prompt"],
                    "completion": token_counter["completion"],
                    "total": total_tokens,
                },
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
                "tokens": None,
            }


graph_qa_service = GraphQAService()
