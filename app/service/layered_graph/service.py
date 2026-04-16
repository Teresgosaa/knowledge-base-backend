from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.time import DateTime as Neo4jDateTime

from app.service.layered_graph.config import (
    get_active_layers,
    get_active_relationship_types,
)
from app.service.node_config import get_all_node_types, get_semantic_graph_db_names
from app.settings.settings import settings

logger = logging.getLogger(__name__)


def _sanitize_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    return {k: str(v) if isinstance(v, Neo4jDateTime) else v for k, v in props.items()}


def _build_layer_match(layer: str) -> Optional[str]:
    layer_node_types = _resolve_layer_node_types(layer)
    if not layer_node_types:
        return None

    label_checks = " OR ".join(f"'{nt}' IN labels(n)" for nt in layer_node_types)
    etype_checks = " OR ".join(f"n.entity_type = '{nt}'" for nt in layer_node_types)
    return f"MATCH (n:Layered) WHERE ({label_checks} OR ({etype_checks}))"


def _resolve_layer_node_types(layer: str) -> List[str]:
    if layer == "semantic":
        return get_semantic_graph_db_names()
    for ld in get_active_layers():
        if ld["layer_type"] == layer:
            node_types = []
            for item in get_all_node_types():
                if not item.get("is_active", True):
                    continue
                if item["layer_type"] == layer:
                    node_types.append(item["graph_db_name"])
            return node_types
    return []


class LayeredGraphService:
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

    def get_layers(self) -> List[Dict[str, Any]]:
        semantic_names = get_semantic_graph_db_names()
        layers = []
        for ld in get_active_layers():
            layer_type = ld["layer_type"]
            if layer_type == "semantic":
                layers.append(
                    {
                        "name": ld["name"],
                        "layer_type": layer_type,
                        "description": ld["description"],
                        "node_types": semantic_names,
                    }
                )
            else:
                node_types = [
                    item["graph_db_name"]
                    for item in get_all_node_types()
                    if item.get("is_active", True) and item["layer_type"] == layer_type
                ]
                layers.append(
                    {
                        "name": ld["name"],
                        "layer_type": layer_type,
                        "description": ld["description"],
                        "node_types": node_types,
                    }
                )
        return layers

    def get_node_types(self) -> List[Dict[str, Any]]:
        result = []
        for item in get_all_node_types():
            if not item.get("is_active", True):
                continue
            node_def = item.get("node_definition", {})
            result.append(
                {
                    "node_type": item["graph_db_name"],
                    "label": node_def.get("label", item["graph_db_name"]),
                    "layer": item["layer_type"],
                    "description": node_def.get("description", item["name"]),
                    "properties": node_def.get("properties", []),
                    "subtypes": node_def.get("subtypes", []),
                }
            )
        return result

    def get_relationship_types(self) -> List[Dict[str, Any]]:
        semantic_names = get_semantic_graph_db_names()
        semantic_set = set(semantic_names)

        result = []
        for rd in get_active_relationship_types():
            if rd["uses_semantic_source"] and not rd["source_types"]:
                source_types = semantic_names
            else:
                source_types = rd["source_types"]

            if rd["uses_semantic_target"] and not rd["target_types"]:
                target_types = semantic_names
            else:
                target_types = rd["target_types"]

            result.append(
                {
                    "rel_type": rd["rel_type"],
                    "source_types": source_types,
                    "target_types": target_types,
                    "description": rd["description"],
                    "properties": [
                        {"name": p["name"], "type": p["type"], "description": p.get("description", "")}
                        for p in rd["properties"]
                    ],
                }
            )
        return result

    def get_layer_nodes(
        self,
        layer: str,
        doc_id: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        driver = self._get_driver()
        base_query = _build_layer_match(layer)
        if not base_query:
            return []

        conditions = ["($doc_id IS NULL OR n.doc_id = $doc_id)"]
        params: Dict[str, Any] = {"doc_id": doc_id, "skip": offset, "limit": limit}

        if node_type:
            conditions.append(f"('{node_type}' IN labels(n) OR n.entity_type = '{node_type}')")

        where_clause = " AND " + " AND ".join(conditions)

        query = (
            base_query
            + where_clause
            + " RETURN DISTINCT n, labels(n) AS node_labels, elementId(n) AS elem_id"
            + " SKIP $skip LIMIT $limit"
        )

        with driver.session() as session:
            result = session.run(query, params)
            nodes = []
            seen = set()
            for record in result:
                elem_id = record["elem_id"]
                if elem_id in seen:
                    continue
                seen.add(elem_id)
                node_data = _sanitize_properties(dict(record["n"]))
                node_labels = [lbl for lbl in record["node_labels"] if lbl not in ("Layered", "base")]
                if not node_labels:
                    et = node_data.get("entity_type", "")
                    if et:
                        node_labels = [et]
                nodes.append(
                    {
                        "id": elem_id,
                        "uid": node_data.get("uid", ""),
                        "labels": node_labels,
                        "properties": node_data,
                    }
                )
            return nodes

    def get_layer_edges(
        self,
        layer: str,
        doc_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        driver = self._get_driver()

        layer_node_types = self._get_layer_node_types(layer)
        if not layer_node_types:
            return []

        label_checks = " OR ".join(f"'{nt}' IN labels(n)" for nt in layer_node_types)
        etype_checks = " OR ".join(f"n.entity_type = '{nt}'" for nt in layer_node_types)

        query = f"""
        MATCH (n)
        WHERE ('Layered' IN labels(n))
          AND ({label_checks} OR ({etype_checks}))
          AND ($doc_id IS NULL OR n.doc_id = $doc_id)
        WITH collect(elementId(n)) AS node_ids
        MATCH (a)-[r]->(b)
        WHERE elementId(a) IN node_ids AND elementId(b) IN node_ids
        RETURN elementId(a) AS source_id, elementId(b) AS target_id,
               type(r) AS rel_type, properties(r) AS rel_props
        LIMIT $limit
        """
        params = {"doc_id": doc_id, "limit": limit}

        with driver.session() as session:
            result = session.run(query, params)
            edges = []
            for record in result:
                edges.append(
                    {
                        "source": record["source_id"],
                        "target": record["target_id"],
                        "type": record["rel_type"],
                        "properties": _sanitize_properties(dict(record["rel_props"]))
                        if record["rel_props"]
                        else {},
                    }
                )
            return edges

    def get_layer_graph(
        self,
        layer: str,
        doc_id: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        nodes = self.get_layer_nodes(layer, doc_id, node_type, limit)
        if not nodes:
            return {"nodes": [], "edges": []}

        node_ids = [n["id"] for n in nodes]

        driver = self._get_driver()

        edge_query = """
        MATCH (a)-[r]->(b)
        WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids
        RETURN elementId(a) AS source_id, elementId(b) AS target_id,
               type(r) AS rel_type, properties(r) AS rel_props
        """
        params = {"node_ids": node_ids}

        with driver.session() as session:
            result = session.run(edge_query, params)
            edges = []
            for record in result:
                edges.append(
                    {
                        "source": record["source_id"],
                        "target": record["target_id"],
                        "type": record["rel_type"],
                        "properties": _sanitize_properties(dict(record["rel_props"]))
                        if record["rel_props"]
                        else {},
                    }
                )

        return {"nodes": nodes, "edges": edges}

    def get_document_overview(self, doc_id: str) -> Dict[str, Any]:
        driver = self._get_driver()

        with driver.session() as session:
            doc_result = session.run(
                "MATCH (d:Document:Layered) WHERE d.doc_id = $doc_id "
                "RETURN d, labels(d) AS labels, elementId(d) AS elem_id",
                doc_id=doc_id,
            )
            doc_records = list(doc_result)
            if not doc_records:
                return {}

            doc_data = _sanitize_properties(dict(doc_records[0]["d"]))
            doc_elem_id = doc_records[0]["elem_id"]

            clause_count_result = session.run(
                "MATCH (:DocumentVersion:Layered)-[:HAS_CLAUSE]->(c:Clause:Layered) "
                "WHERE c.doc_id = $doc_id RETURN count(c) AS cnt",
                doc_id=doc_id,
            )
            clause_count = clause_count_result.single()["cnt"] if clause_count_result.peek() else 0

            entity_count_result = session.run(
                "MATCH (e) WHERE 'Layered' IN labels(e) AND e.entity_type IS NOT NULL "
                "AND NOT 'Document' IN labels(e) AND NOT 'DocumentVersion' IN labels(e) "
                "AND NOT 'Clause' IN labels(e) AND NOT 'TextUnit' IN labels(e) "
                "AND e.doc_id = $doc_id RETURN count(e) AS cnt",
                doc_id=doc_id,
            )
            entity_count = entity_count_result.single()["cnt"] if entity_count_result.peek() else 0

            term_count_result = session.run(
                "MATCH (t:Term:Layered) WHERE t.doc_id = $doc_id RETURN count(t) AS cnt",
                doc_id=doc_id,
            )
            term_count = term_count_result.single()["cnt"] if term_count_result.peek() else 0

            obl_count_result = session.run(
                "MATCH (o:Obligation:Layered) WHERE o.doc_id = $doc_id RETURN count(o) AS cnt",
                doc_id=doc_id,
            )
            obl_count = obl_count_result.single()["cnt"] if obl_count_result.peek() else 0

            finding_count_result = session.run(
                "MATCH (f:Finding:Layered) WHERE f.doc_id = $doc_id RETURN count(f) AS cnt",
                doc_id=doc_id,
            )
            finding_count = finding_count_result.single()["cnt"] if finding_count_result.peek() else 0

            parties_result = session.run(
                "MATCH (o) WHERE 'Layered' IN labels(o) AND ('Organization' IN labels(o) "
                "OR o.entity_type = 'Organization') "
                "WITH o MATCH (o)-[:PLAYS_ROLE_IN]->(d:Document:Layered) "
                "WHERE d.doc_id = $doc_id "
                "RETURN o.name AS name, o.role AS role",
                doc_id=doc_id,
            )
            parties = [{"name": r["name"], "role": r["role"]} for r in parties_result]

            return {
                "id": doc_elem_id,
                "uid": doc_data.get("uid", ""),
                "doc_id": doc_id,
                "title": doc_data.get("title", ""),
                "doc_subtype": doc_data.get("doc_subtype", ""),
                "original_filename": doc_data.get("original_filename", ""),
                "language": doc_data.get("language", "ru"),
                "parties": parties,
                "stats": {
                    "clauses": clause_count,
                    "entities": entity_count,
                    "terms": term_count,
                    "obligations": obl_count,
                    "findings": finding_count,
                },
            }

    def search_nodes(
        self,
        query: str,
        doc_id: Optional[str] = None,
        node_type: Optional[str] = None,
        layer: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        driver = self._get_driver()

        cypher = "MATCH (n) WHERE 'Layered' IN labels(n)"
        params: Dict[str, Any] = {"query": query, "limit": limit}

        if doc_id:
            cypher += " AND n.doc_id = $doc_id"
            params["doc_id"] = doc_id

        if node_type:
            cypher += " AND ($node_type IN labels(n) OR n.entity_type = $node_type)"
            params["node_type"] = node_type

        if layer:
            layer_types = self._get_layer_node_types(layer)
            if layer_types:
                label_checks = " OR ".join(f"'{nt}' IN labels(n)" for nt in layer_types)
                etype_checks = " OR ".join(f"n.entity_type = '{nt}'" for nt in layer_types)
                cypher += f" AND ({label_checks} OR ({etype_checks}))"

        cypher += (
            " AND (n.name CONTAINS $query OR n.full_text CONTAINS $query "
            "OR n.text CONTAINS $query OR n.description CONTAINS $query "
            "OR n.entity_id CONTAINS $query)"
        )

        cypher += (
            " RETURN DISTINCT n, labels(n) AS node_labels, elementId(n) AS elem_id SKIP 0 LIMIT $limit"
        )

        with driver.session() as session:
            result = session.run(cypher, params)
            nodes = []
            seen = set()
            for record in result:
                elem_id = record["elem_id"]
                if elem_id in seen:
                    continue
                seen.add(elem_id)
                node_data = _sanitize_properties(dict(record["n"]))
                node_labels = [lbl for lbl in record["node_labels"] if lbl not in ("Layered", "base")]
                if not node_labels:
                    et = node_data.get("entity_type", "")
                    if et:
                        node_labels = [et]
                nodes.append(
                    {
                        "id": elem_id,
                        "uid": node_data.get("uid", ""),
                        "labels": node_labels,
                        "properties": node_data,
                    }
                )
            return nodes

    def get_document_doc_ids(self) -> List[str]:
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run(
                "MATCH (d:Document:Layered) RETURN DISTINCT d.doc_id AS doc_id ORDER BY d.doc_id"
            )
            return [r["doc_id"] for r in result]

    def _get_layer_node_types(self, layer: str) -> List[str]:
        return _resolve_layer_node_types(layer)
