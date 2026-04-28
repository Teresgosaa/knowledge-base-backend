from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

from neo4j import GraphDatabase

from app.service.node_config import get_all_node_types, get_russian_to_graph_db_map
from app.settings.settings import settings

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPTS_PATH = "./data/prompts/layered_graph_prompts.md"

_PARTY_ROLE_TYPES = {"Supplier", "Contractor", "CustomerClient", "Buyer"}


def _normalize_node_name(name: str) -> str:
    return "".join(c for c in name.lower() if c not in " -/")


def _get_node_type_by_node_name(node_name: str) -> Optional[str]:
    normalized = _normalize_node_name(node_name)
    mapping = get_russian_to_graph_db_map()
    return mapping.get(normalized)


def _generate_uid(*parts: str) -> str:
    content = "|".join(str(p) for p in parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_prompt(name: str) -> Optional[str]:
    prompts_path = Path(_EXTRACTION_PROMPTS_PATH)
    if not prompts_path.exists():
        return None
    text = prompts_path.read_text(encoding="utf-8")
    in_block = False
    block_name = ""
    lines: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            if in_block and block_name == name and lines:
                return "\n".join(lines).strip()
            block_name = stripped[3:].strip()
            lines = []
            in_block = False
            continue
        if block_name == name and not in_block:
            if stripped.startswith("~~~"):
                in_block = True
                continue
        if in_block and block_name == name:
            if stripped == "~~~":
                return "\n".join(lines).strip()
            lines.append(raw_line)
    return None


def _is_presentation(filename: str, text: str) -> bool:
    if Path(filename).suffix.lower() in (".ppt", ".pptx"):
        return True
    return bool(text) and "## Слайд" in text[:2000]


def _detect_doc_subtype(filename: str, text: str) -> str:
    if _is_presentation(filename, text):
        return "Presentation"
    _DOC_TYPE_PATTERNS = {
        "договор": "Contract",
        "контракт": "Contract",
        "допсоглашение": "Amendment",
        "дополнительное соглашение": "Amendment",
        "приложение": "Annex",
        "спецификация": "Specification",
        "заказ": "PurchaseOrder",
        "акт": "Act",
        "протокол": "Protocol",
        "счет": "Invoice",
    }
    lower_name = filename.lower()
    lower_text = text[:2000].lower() if text else ""
    for pattern, subtype in _DOC_TYPE_PATTERNS.items():
        if pattern in lower_name or pattern in lower_text:
            return subtype
    return "Contract"


class LayeredGraphBuilder:
    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    async def build_graph_for_document(
        self,
        doc_id: str,
        filename: str,
        text: str,
        llm_func: Callable[..., Coroutine[Any, Any, str]],
        s3_key: str = "",
        file_hash: str = "",
    ) -> Dict[str, Any]:
        logger.info("Building layered graph for doc_id=%s file=%s", doc_id, filename)

        is_pres = _is_presentation(filename, text)
        doc_subtype = "Presentation" if is_pres else _detect_doc_subtype(filename, text)
        stats: Dict[str, int] = {
            "document": 0,
            "document_version": 0,
            "clause": 0,
            "text_unit": 0,
            "semantic_entity": 0,
            "relationships": 0,
        }

        driver = self._get_driver()

        doc_uid = _generate_uid("Document", doc_id, filename)
        with driver.session() as session:
            session.run(
                """
                MERGE (d:Document:Layered {uid: $uid})
                SET d.doc_id = $doc_id,
                    d.title = $title,
                    d.doc_subtype = $doc_subtype,
                    d.original_filename = $filename,
                    d.s3_key = $s3_key,
                    d.language = 'ru',
                    d.file_hash = $file_hash
                """,
                uid=doc_uid,
                doc_id=doc_id,
                title=filename,
                doc_subtype=doc_subtype,
                filename=filename,
                s3_key=s3_key,
                file_hash=file_hash,
            )
            stats["document"] += 1

            version_uid = _generate_uid("DocumentVersion", doc_id, "v1")
            session.run(
                """
                MERGE (dv:DocumentVersion:Layered {uid: $uid})
                SET dv.version = 1,
                    dv.status = 'active',
                    dv.created_at = datetime()
                WITH dv
                MATCH (d:Document:Layered {uid: $doc_uid})
                MERGE (d)-[:HAS_VERSION]->(dv)
                """,
                uid=version_uid,
                doc_uid=doc_uid,
            )
            stats["document_version"] += 1

        if is_pres:
            logger.info("Presentation detected for doc_id=%s, using slide-based graph", doc_id)
            stats = self._build_slide_clauses(
                driver, doc_id, doc_uid, version_uid, text, stats
            )
        else:
            extraction = await self._extract_structured_data(text, llm_func)

            if extraction:
                stats = self._write_extraction_to_graph(
                    driver, doc_id, doc_uid, version_uid, extraction, stats
                )
                if stats["clause"] == 0:
                    logger.warning(
                        "LLM extraction returned no clauses for doc_id=%s, building from raw text",
                        doc_id,
                    )
                    stats = self._build_basic_clauses(
                        driver, doc_id, doc_uid, version_uid, text, stats
                    )
            else:
                logger.warning(
                    "LLM extraction returned no data for doc_id=%s, building from raw text",
                    doc_id,
                )
                stats = self._build_basic_clauses(
                    driver, doc_id, doc_uid, version_uid, text, stats
                )

        with driver.session() as session:
            session.run(
                """
                MATCH (n:Layered)
                WHERE n.doc_id = $doc_id OR n.uid STARTS WITH $doc_prefix
                SET n.layered_graph = true
                """,
                doc_id=doc_id,
                doc_prefix=_generate_uid("", doc_id),
            )

        promoted = self._promote_lightrag_nodes(driver, doc_id, doc_uid)
        stats["promoted_lightrag_nodes"] = promoted

        logger.info("Layered graph build complete for doc_id=%s: %s", doc_id, stats)
        return stats

    def _promote_lightrag_nodes(
        self,
        driver,
        doc_id: str,
        doc_uid: str,
    ) -> int:
        promoted = 0
        with driver.session() as session:
            raw_nodes = session.run(
                """
                MATCH (n)
                WHERE n.doc_id = $doc_id
                  AND NOT 'Layered' IN labels(n)
                  AND n.entity_type IS NOT NULL
                RETURN n, labels(n) AS node_labels, elementId(n) AS elem_id
                """,
                doc_id=doc_id,
            )
            records = list(raw_nodes)

            for record in records:
                node_data = dict(record["n"])
                raw_entity_type = node_data.get("entity_type", "")

                node_type = _get_node_type_by_node_name(raw_entity_type)

                if node_type is None:
                    continue

                new_labels = ["Layered", node_type]

                entity_name = node_data.get("entity_id", node_data.get("name", ""))
                uid = node_data.get(
                    "uid", _generate_uid("promoted", doc_id, str(record["elem_id"]))
                )

                normalized_label = _normalize_node_name(raw_entity_type)

                set_clauses = [
                    "n.uid = $uid",
                    "n.label = $label",
                    "n.doc_id = $doc_id",
                    "n.layered_graph = true",
                ]
                params: Dict[str, Any] = {
                    "uid": uid,
                    "label": normalized_label,
                    "doc_id": doc_id,
                    "elem_id": record["elem_id"],
                    "doc_uid": doc_uid,
                }

                value_property = self._get_value_property_for_node_type(node_type)
                if value_property:
                    raw_value = node_data.get("value")
                    if raw_value is None:
                        raw_value = node_data.get("entity_id")
                    if raw_value is not None:
                        if isinstance(raw_value, str):
                            try:
                                raw_value = float(
                                    raw_value.replace(" ", "").replace(",", ".")
                                )
                            except (ValueError, TypeError):
                                pass
                        set_clauses.append(f"n.{value_property} = $value")
                        params["value"] = raw_value

                label_str = ":".join(new_labels)
                session.run(
                    f"MATCH (n) WHERE elementId(n) = $elem_id "
                    f"SET n:{label_str}, {', '.join(set_clauses)}",
                    **params,
                )

                session.run(
                    """
                    MATCH (n) WHERE elementId(n) = $elem_id
                    MATCH (d:Document:Layered {uid: $doc_uid})
                    MERGE (n)-[:BELONGS_TO]->(d)
                    """,
                    elem_id=record["elem_id"],
                    doc_uid=doc_uid,
                )

                if node_type in _PARTY_ROLE_TYPES:
                    session.run(
                        """
                        MATCH (org) WHERE elementId(org) = $elem_id
                        MATCH (d:Document:Layered {uid: $doc_uid})
                        MERGE (org)-[:PLAYS_ROLE_IN]->(d)
                        """,
                        elem_id=record["elem_id"],
                        doc_uid=doc_uid,
                    )

                promoted += 1

            if promoted > 0:
                logger.info(
                    "Promoted %d LightRAG nodes for doc_id=%s",
                    promoted,
                    doc_id,
                )
        return promoted

    def backfill_belongs_to_relationships(self) -> int:
        driver = self._get_driver()
        created = 0
        with driver.session() as session:
            result = session.run(
                """
                MATCH (n:Layered)
                WHERE n.doc_id IS NOT NULL
                  AND NOT 'Document' IN labels(n)
                  AND NOT 'DocumentVersion' IN labels(n)
                  AND NOT 'Clause' IN labels(n)
                  AND NOT 'TextUnit' IN labels(n)
                  AND NOT (n)-[:BELONGS_TO]->(:Document)
                MATCH (d:Document:Layered)
                WHERE d.doc_id = n.doc_id
                MERGE (n)-[:BELONGS_TO]->(d)
                RETURN count(n) AS cnt
                """
            )
            for record in result:
                created += record["cnt"]
        if created > 0:
            logger.info("Backfilled %d BELONGS_TO relationships", created)
        return created

    def _get_value_property_for_node_type(self, graph_db_name: str) -> str:
        for item in get_all_node_types():
            if item["graph_db_name"] == graph_db_name:
                props = item.get("node_definition", {}).get("properties", [])
                for prop in props:
                    if prop["name"] not in ("uid", "label", "doc_id"):
                        return prop["name"]
                break
        return "value"

    async def _extract_structured_data(
        self,
        text: str,
        llm_func: Callable[..., Coroutine[Any, Any, str]],
    ) -> Optional[Dict[str, Any]]:
        system_prompt = _load_prompt("layered_extraction_system_prompt")
        user_prompt_template = _load_prompt("layered_extraction_user_prompt")

        if not system_prompt or not user_prompt_template:
            logger.warning(
                "Layered extraction prompts not found, skipping LLM extraction"
            )
            return None

        user_prompt = user_prompt_template.replace("{input_text}", text[:12000])

        try:
            response = await llm_func(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Failed to extract structured data via LLM: %s", exc)
            return None

    def _write_extraction_to_graph(
        self,
        driver,
        doc_id: str,
        doc_uid: str,
        version_uid: str,
        extraction: Dict[str, Any],
        stats: Dict[str, int],
    ) -> Dict[str, int]:
        with driver.session() as session:
            doc_data = extraction.get("document", {})
            parties = doc_data.get("parties", [])

            for party in parties:
                party_name = party.get("name", "")
                if not party_name:
                    continue
                role = party.get("role", "")

                node_type = "Supplier" if role in ("supplier", "поставщик") else "Buyer"
                uid = _generate_uid(node_type, doc_id, party_name)

                session.run(
                    f"""
                    MERGE (o:{node_type}:Layered {{uid: $uid}})
                    SET o.name = $name,
                        o.label = $label,
                        o.inn = $inn,
                        o.role = $role,
                        o.doc_id = $doc_id
                    WITH o
                    MATCH (d:Document:Layered {{uid: $doc_uid}})
                    MERGE (o)-[:PLAYS_ROLE_IN {{role: $role}}]->(d)
                    """,
                    uid=uid,
                    name=party_name,
                    label=_normalize_node_name(party.get("entity_type", "Поставщик")),
                    inn=party.get("inn"),
                    role=role,
                    doc_id=doc_id,
                    doc_uid=doc_uid,
                )
                stats["semantic_entity"] += 1

            clauses = extraction.get("clauses", [])
            clause_uid_map: Dict[str, str] = {}

            for clause in clauses:
                clause_id = clause.get("clause_id", "")
                if not clause_id:
                    continue
                clause_uid = _generate_uid("Clause", doc_id, clause_id)
                clause_uid_map[clause_id] = clause_uid
                full_text = clause.get("full_text", "")

                session.run(
                    """
                    MERGE (c:Clause:Layered {uid: $uid})
                    SET c.clause_id = $clause_id,
                        c.clause_type = $clause_type,
                        c.title = $title,
                        c.full_text = $full_text,
                        c.order_index = $order_index,
                        c.page_number = $page_number,
                        c.doc_id = $doc_id
                    """,
                    uid=clause_uid,
                    clause_id=clause_id,
                    clause_type=clause.get("clause_type", "clause"),
                    title=clause.get("title"),
                    full_text=full_text,
                    order_index=clause.get("order_index", 0),
                    page_number=clause.get("page_number"),
                    doc_id=doc_id,
                )
                stats["clause"] += 1

                session.run(
                    """
                    MATCH (dv:DocumentVersion:Layered {uid: $version_uid})
                    MATCH (c:Clause:Layered {uid: $clause_uid})
                    MERGE (dv)-[:HAS_CLAUSE]->(c)
                    """,
                    version_uid=version_uid,
                    clause_uid=clause_uid,
                )
                stats["relationships"] += 1

                text_units = clause.get("text_units", [])
                for i, tu in enumerate(text_units):
                    tu_text = tu.get("text", "")
                    if not tu_text:
                        continue
                    tu_uid = _generate_uid("TextUnit", doc_id, clause_id, str(i))
                    session.run(
                        """
                        MERGE (tu:TextUnit:Layered {uid: $uid})
                        SET tu.text = $text,
                            tu.text_type = $text_type,
                            tu.page_number = $page_number,
                            tu.offset_start = $offset_start,
                            tu.offset_end = $offset_end,
                            tu.doc_id = $doc_id
                        WITH tu
                        MATCH (c:Clause:Layered {uid: $clause_uid})
                        MERGE (c)-[:HAS_TEXT_UNIT]->(tu)
                        """,
                        uid=tu_uid,
                        text=tu_text,
                        text_type=tu.get("text_type", "excerpt"),
                        page_number=tu.get("page_number"),
                        offset_start=tu.get("offset_start"),
                        offset_end=tu.get("offset_end"),
                        doc_id=doc_id,
                        clause_uid=clause_uid,
                    )
                    stats["text_unit"] += 1
                    stats["relationships"] += 1

            for clause in clauses:
                clause_id = clause.get("clause_id", "")
                clause_uid = clause_uid_map.get(clause_id, "")
                if not clause_uid:
                    continue

                for child_id in clause.get("children_clause_ids", []):
                    child_uid = clause_uid_map.get(child_id, "")
                    if child_uid:
                        session.run(
                            """
                            MATCH (parent:Clause:Layered {uid: $parent_uid})
                            MATCH (child:Clause:Layered {uid: $child_uid})
                            MERGE (parent)-[:HAS_CHILD]->(child)
                            """,
                            parent_uid=clause_uid,
                            child_uid=child_uid,
                        )
                        stats["relationships"] += 1

                for ref_id in clause.get("refers_to_clause_ids", []):
                    ref_uid = clause_uid_map.get(ref_id, "")
                    if ref_uid:
                        session.run(
                            """
                            MATCH (source:Clause:Layered {uid: $source_uid})
                            MATCH (target:Clause:Layered {uid: $target_uid})
                            MERGE (source)-[:REFERS_TO]->(target)
                            """,
                            source_uid=clause_uid,
                            target_uid=ref_uid,
                        )
                        stats["relationships"] += 1

            prev_uid: Optional[str] = None
            for clause in sorted(clauses, key=lambda c: c.get("order_index", 0)):
                clause_id = clause.get("clause_id", "")
                clause_uid = clause_uid_map.get(clause_id, "")
                if clause_uid and prev_uid:
                    session.run(
                        """
                        MATCH (a:Clause:Layered {uid: $a_uid})
                        MATCH (b:Clause:Layered {uid: $b_uid})
                        MERGE (a)-[:PRECEDES]->(b)
                        """,
                        a_uid=prev_uid,
                        b_uid=clause_uid,
                    )
                    stats["relationships"] += 1
                if clause_uid:
                    prev_uid = clause_uid

            entities = extraction.get("entities", [])
            for i, entity in enumerate(entities):
                entity_name = entity.get("name", "")
                entity_type_raw = entity.get("entity_type", "")
                if not entity_name:
                    continue

                node_type = _get_node_type_by_node_name(entity_type_raw)
                if node_type is None:
                    logger.warning("Unknown entity type: %s", entity_type_raw)
                    continue

                entity_uid = _generate_uid(node_type, doc_id, entity_name, str(i))
                clause_id_ref = entity.get("clause_id", "")
                clause_uid_ref = clause_uid_map.get(clause_id_ref, "")
                normalized_label = _normalize_node_name(entity_type_raw)

                value_property = self._get_value_property_for_node_type(node_type)
                value = entity.get("value", entity.get("normalized_value", ""))

                session.run(
                    f"""
                    MERGE (e:`{node_type}`:Layered {{uid: $uid}})
                    SET e.label = $label,
                        e.doc_id = $doc_id,
                        e.{value_property} = $value
                    {'''WITH e MATCH (c:Clause:Layered {uid: $clause_uid}) MERGE (e)-[:MENTIONED_IN]->(c)''' if clause_uid_ref else ""}
                    """,
                    uid=entity_uid,
                    label=normalized_label,
                    doc_id=doc_id,
                    value=value,
                    clause_uid=clause_uid_ref,
                )
                stats["semantic_entity"] += 1
                if clause_uid_ref:
                    stats["relationships"] += 1

            terms = extraction.get("terms", [])
            for i, term in enumerate(terms):
                term_name = term.get("name", "")
                term_type = term.get("term_type", "")
                if not term_name:
                    continue

                node_type = _get_node_type_by_node_name(term_type)
                if node_type is None:
                    node_type = "PaymentTerms"

                term_uid = _generate_uid(node_type, doc_id, term_name, str(i))
                clause_id_ref = term.get("clause_id", "")
                clause_uid_ref = clause_uid_map.get(clause_id_ref, "")
                normalized_label = _normalize_node_name(term_type)

                session.run(
                    f"""
                    MERGE (t:`{node_type}`:Layered {{uid: $uid}})
                    SET t.label = $label,
                        t.description = $description,
                        t.doc_id = $doc_id
                    WITH t
                    MATCH (c:Clause:Layered {{uid: $clause_uid}})
                    MERGE (c)-[:DEFINES_TERM]->(t)
                    """,
                    uid=term_uid,
                    label=normalized_label,
                    description=term.get("description", term_name),
                    doc_id=doc_id,
                    clause_uid=clause_uid_ref,
                )
                stats["semantic_entity"] += 1
                stats["relationships"] += 1

        return stats

    def _build_slide_clauses(
        self,
        driver,
        doc_id: str,
        doc_uid: str,
        version_uid: str,
        text: str,
        stats: Dict[str, int],
    ) -> Dict[str, int]:
        """Build Clause nodes from '## Слайд N: title' markers in pre-processed PPTX markdown."""
        slide_pattern = re.compile(r"^## Слайд (\d+)(?::\s*(.+))?$", re.MULTILINE)
        positions = [
            (m.start(), m.group(1), (m.group(2) or "").strip())
            for m in slide_pattern.finditer(text)
        ]

        if not positions:
            logger.warning(
                "No slide markers found for doc_id=%s, falling back to basic clauses", doc_id
            )
            return self._build_basic_clauses(driver, doc_id, doc_uid, version_uid, text, stats)

        prev_uid: Optional[str] = None
        with driver.session() as session:
            for i, (pos, slide_num, title) in enumerate(positions):
                end_pos = positions[i + 1][0] if i + 1 < len(positions) else len(text)
                slide_text = text[pos:end_pos].strip()

                clause_id = f"slide_{slide_num}"
                clause_uid = _generate_uid("Clause", doc_id, clause_id)

                session.run(
                    """
                    MERGE (c:Clause:Layered {uid: $uid})
                    SET c.clause_id   = $clause_id,
                        c.clause_type = 'slide',
                        c.title       = $title,
                        c.full_text   = $full_text,
                        c.order_index = $order_index,
                        c.page_number = $slide_num,
                        c.doc_id      = $doc_id
                    """,
                    uid=clause_uid,
                    clause_id=clause_id,
                    title=title,
                    full_text=slide_text,
                    order_index=int(slide_num),
                    slide_num=int(slide_num),
                    doc_id=doc_id,
                )
                session.run(
                    """
                    MATCH (dv:DocumentVersion:Layered {uid: $version_uid})
                    MATCH (c:Clause:Layered {uid: $clause_uid})
                    MERGE (dv)-[:HAS_CLAUSE]->(c)
                    """,
                    version_uid=version_uid,
                    clause_uid=clause_uid,
                )

                tu_uid = _generate_uid("TextUnit", doc_id, clause_id, "0")
                session.run(
                    """
                    MERGE (tu:TextUnit:Layered {uid: $tu_uid})
                    SET tu.text       = $text,
                        tu.text_type  = 'slide_content',
                        tu.page_number = $slide_num,
                        tu.doc_id     = $doc_id
                    WITH tu
                    MATCH (c:Clause:Layered {uid: $clause_uid})
                    MERGE (c)-[:HAS_TEXT_UNIT]->(tu)
                    """,
                    tu_uid=tu_uid,
                    text=slide_text,
                    slide_num=int(slide_num),
                    doc_id=doc_id,
                    clause_uid=clause_uid,
                )

                if prev_uid:
                    session.run(
                        """
                        MATCH (a:Clause:Layered {uid: $a_uid})
                        MATCH (b:Clause:Layered {uid: $b_uid})
                        MERGE (a)-[:PRECEDES]->(b)
                        """,
                        a_uid=prev_uid,
                        b_uid=clause_uid,
                    )
                    stats["relationships"] += 1

                prev_uid = clause_uid
                stats["clause"] += 1
                stats["text_unit"] += 1
                stats["relationships"] += 2

        logger.info(
            "Built %d slide clauses for doc_id=%s", stats["clause"], doc_id
        )
        return stats

    def _build_basic_clauses(
        self,
        driver,
        doc_id: str,
        doc_uid: str,
        version_uid: str,
        text: str,
        stats: Dict[str, int],
    ) -> Dict[str, int]:
        clause_pattern = re.compile(
            r"^(\d+(?:\.\d+)*)[.\s]+(.+?)(?=\n\d+(?:\.\d+)*[.\s]|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        matches = list(clause_pattern.finditer(text))

        if not matches:
            chunk_size = 2000
            chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
            for idx, chunk in enumerate(chunks):
                clause_uid = _generate_uid("Clause", doc_id, f"chunk_{idx}")
                tu_uid = _generate_uid("TextUnit", doc_id, f"chunk_{idx}", "0")
                with driver.session() as session:
                    session.run(
                        """
                        MERGE (c:Clause:Layered {uid: $uid})
                        SET c.clause_id = $clause_id,
                            c.clause_type = 'clause',
                            c.full_text = $text,
                            c.order_index = $order_index,
                            c.doc_id = $doc_id
                        """,
                        uid=clause_uid,
                        clause_id=f"chunk_{idx}",
                        text=chunk,
                        order_index=idx,
                        doc_id=doc_id,
                    )
                    session.run(
                        """
                        MATCH (dv:DocumentVersion:Layered {uid: $version_uid})
                        MATCH (c:Clause:Layered {uid: $clause_uid})
                        MERGE (dv)-[:HAS_CLAUSE]->(c)
                        """,
                        version_uid=version_uid,
                        clause_uid=clause_uid,
                    )
                    session.run(
                        """
                        MERGE (tu:TextUnit:Layered {uid: $tu_uid})
                        SET tu.text = $text,
                            tu.text_type = 'excerpt',
                            tu.doc_id = $doc_id
                        WITH tu
                        MATCH (c:Clause:Layered {uid: $clause_uid})
                        MERGE (c)-[:HAS_TEXT_UNIT]->(tu)
                        """,
                        tu_uid=tu_uid,
                        text=chunk,
                        doc_id=doc_id,
                        clause_uid=clause_uid,
                    )
                stats["clause"] += 1
                stats["text_unit"] += 1
                stats["relationships"] += 2
            return stats

        clause_uid_map: Dict[str, str] = {}
        with driver.session() as session:
            for idx, match in enumerate(matches):
                clause_id = match.group(1)
                clause_text = match.group(2).strip()
                clause_uid = _generate_uid("Clause", doc_id, clause_id)
                clause_uid_map[clause_id] = clause_uid

                is_section = "." not in clause_id
                clause_type = "section" if is_section else "clause"

                session.run(
                    """
                    MERGE (c:Clause:Layered {uid: $uid})
                    SET c.clause_id = $clause_id,
                        c.clause_type = $clause_type,
                        c.full_text = $text,
                        c.order_index = $order_index,
                        c.doc_id = $doc_id
                    """,
                    uid=clause_uid,
                    clause_id=clause_id,
                    clause_type=clause_type,
                    text=f"{clause_id}. {clause_text}",
                    order_index=idx,
                    doc_id=doc_id,
                )

                tu_uid = _generate_uid("TextUnit", doc_id, clause_id, "0")
                session.run(
                    """
                    MERGE (tu:TextUnit:Layered {uid: $tu_uid})
                    SET tu.text = $text,
                        tu.text_type = 'excerpt',
                        tu.doc_id = $doc_id
                    WITH tu
                    MATCH (c:Clause:Layered {uid: $clause_uid})
                    MERGE (c)-[:HAS_TEXT_UNIT]->(tu)
                    """,
                    tu_uid=tu_uid,
                    text=clause_text,
                    doc_id=doc_id,
                    clause_uid=clause_uid,
                )

                session.run(
                    """
                    MATCH (dv:DocumentVersion:Layered {uid: $version_uid})
                    MATCH (c:Clause:Layered {uid: $clause_uid})
                    MERGE (dv)-[:HAS_CLAUSE]->(c)
                    """,
                    version_uid=version_uid,
                    clause_uid=clause_uid,
                )

                stats["clause"] += 1
                stats["text_unit"] += 1
                stats["relationships"] += 2

                parent_parts = clause_id.split(".")
                if len(parent_parts) > 1:
                    parent_id = ".".join(parent_parts[:-1])
                    parent_uid = clause_uid_map.get(parent_id)
                    if parent_uid:
                        session.run(
                            """
                            MATCH (parent:Clause:Layered {uid: $parent_uid})
                            MATCH (child:Clause:Layered {uid: $child_uid})
                            MERGE (parent)-[:HAS_CHILD]->(child)
                            """,
                            parent_uid=parent_uid,
                            child_uid=clause_uid,
                        )
                        stats["relationships"] += 1

            prev_uid: Optional[str] = None
            for clause_id in sorted(
                clause_uid_map.keys(),
                key=lambda x: [int(p) for p in x.split(".") if p.isdigit()],
            ):
                uid = clause_uid_map[clause_id]
                if prev_uid:
                    session.run(
                        """
                        MATCH (a:Clause:Layered {uid: $a_uid})
                        MATCH (b:Clause:Layered {uid: $b_uid})
                        MERGE (a)-[:PRECEDES]->(b)
                        """,
                        a_uid=prev_uid,
                        b_uid=uid,
                    )
                    stats["relationships"] += 1
                prev_uid = uid

        return stats

    def get_document_text(
        self,
        doc_id: str,
        parser_output_dir: str,
        file_path: Optional[str] = None,
    ) -> Optional[str]:
        output_dir = Path(parser_output_dir)
        if not output_dir.exists():
            return None

        search_terms = [doc_id]
        if file_path:
            file_stem = Path(file_path).stem
            if file_stem and file_stem != doc_id:
                search_terms.append(file_stem)

        for search_term in search_terms:
            text = self._read_parsed_json(output_dir, search_term)
            if text:
                return text

        for search_term in search_terms:
            text = self._read_parsed_md(output_dir, search_term)
            if text:
                return text

        return None

    def _read_parsed_json(self, output_dir: Path, search_term: str) -> Optional[str]:
        for json_file in output_dir.rglob(f"*{search_term}*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                texts = []
                if isinstance(data, list):
                    for chunk in data:
                        if isinstance(chunk, dict):
                            texts.append(chunk.get("text", chunk.get("content", "")))
                elif isinstance(data, dict):
                    chunks = data.get(
                        "chunks", data.get("documents", data.get("texts", []))
                    )
                    for chunk in chunks:
                        if isinstance(chunk, dict):
                            texts.append(chunk.get("text", chunk.get("content", "")))
                    if not chunks:
                        docling_texts = self._extract_docling_text(data)
                        texts.extend(docling_texts)
                if texts:
                    return "\n\n".join(t for t in texts if t)
            except Exception as exc:
                logger.warning("Failed to read parsed output %s: %s", json_file, exc)
        return None

    def _extract_docling_text(self, data: Dict[str, Any]) -> List[str]:
        texts: List[str] = []
        body = data.get("body")
        if isinstance(body, dict):
            content = body.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content.strip())
        for item in data.get("main-text", []):
            if isinstance(item, dict):
                text = item.get("text", "")
                if text and text.strip():
                    texts.append(text.strip())
        return texts

    def _read_parsed_md(self, output_dir: Path, search_term: str) -> Optional[str]:
        for md_file in output_dir.rglob(f"*{search_term}*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if content.strip():
                    return content
            except Exception:
                pass
        return None
