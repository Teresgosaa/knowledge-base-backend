from typing import Any, Optional

from neo4j import Driver, GraphDatabase
from neo4j.time import Date, DateTime, Duration, Time

from app.settings.settings import settings


def _neo4j_to_native(value: Any) -> Any:
    if isinstance(
        value,
        (DateTime, Date, Time, Duration),
    ):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_neo4j_to_native(v) for v in value]
    if isinstance(value, dict):
        return {k: _neo4j_to_native(v) for k, v in value.items()}
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, float):
        return value
    try:
        import neo4j.graph

        if isinstance(value, (neo4j.graph.Node, neo4j.graph.Relationship)):
            return _neo4j_to_native(dict(value))
    except Exception:
        pass
    return value


def _convert_node_props(node_data: dict[str, Any]) -> dict[str, Any]:
    return {k: _neo4j_to_native(v) for k, v in node_data.items()}


class Neo4jService:
    def __init__(self):
        self._driver: Optional[Driver] = None

    def _get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def get_entity_types(self) -> list[str]:
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
            entity_types: set[str] = set()
            for record in result:
                for label in record["labels"]:
                    entity_types.add(label)
            return sorted(entity_types)

    def get_doc_ids(self, entity_type: Optional[str] = None) -> list[str]:
        driver = self._get_driver()
        query = "MATCH (n) WHERE n.doc_id IS NOT NULL"
        params: dict[str, Any] = {}
        if entity_type:
            query += " AND $entity_type IN labels(n)"
            params["entity_type"] = entity_type
        query += " RETURN DISTINCT n.doc_id AS doc_id ORDER BY n.doc_id"
        with driver.session() as session:
            result = session.run(query, params)
            return [record["doc_id"] for record in result]

    def get_nodes(
        self,
        entity_type: Optional[str] = None,
        doc_id: Optional[str] = None,
        entity_value: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        driver = self._get_driver()
        query = "MATCH (n)"
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if entity_type:
            conditions.append("$entity_type IN labels(n)")
            params["entity_type"] = entity_type
        if doc_id:
            conditions.append("n.doc_id = $doc_id")
            params["doc_id"] = doc_id
        if entity_value:
            conditions.append("n.name CONTAINS $entity_value")
            params["entity_value"] = entity_value

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " RETURN n, labels(n) AS node_labels, elementId(n) AS elem_id"
        query += " SKIP $skip LIMIT $limit"
        params["skip"] = offset
        params["limit"] = limit

        with driver.session() as session:
            result = session.run(query, params)  # type: ignore
            nodes = []
            for record in result:
                node = _convert_node_props(dict(record["n"]))
                node["id"] = record["elem_id"]
                node["entity_types"] = record["node_labels"]
                nodes.append(node)
            return nodes

    def get_nodes_with_relationships(
        self,
        entity_type: Optional[str] = None,
        doc_id: Optional[str] = None,
        entity_value: Optional[str] = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        driver = self._get_driver()
        node_query = "MATCH (n)"
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if entity_type:
            conditions.append("$entity_type IN labels(n)")
            params["entity_type"] = entity_type
        if doc_id:
            conditions.append("n.doc_id = $doc_id")
            params["doc_id"] = doc_id
        if entity_value:
            conditions.append("n.name CONTAINS $entity_value")
            params["entity_value"] = entity_value

        conditions.append("NOT 'other' IN labels(n)")

        if conditions:
            node_query += " WHERE " + " AND ".join(conditions)

        node_query += " RETURN n, labels(n) AS node_labels, elementId(n) AS elem_id"
        node_query += " LIMIT $limit"
        params["limit"] = limit

        nodes_map: dict[str, dict[str, Any]] = {}

        with driver.session() as session:
            result = session.run(node_query, params)  # type: ignore
            for record in result:
                elem_id = record["elem_id"]
                node_data = _convert_node_props(dict(record["n"]))
                nodes_map[elem_id] = {
                    "id": elem_id,
                    "labels": record["node_labels"],
                    "properties": node_data,
                }

            if not nodes_map:
                return {"nodes": [], "edges": []}

            node_ids = list(nodes_map.keys())
            edge_query = (
                "MATCH (a)-[r]->(b) "
                "WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids "
                "RETURN elementId(a) AS source_id, elementId(b) AS target_id, "
                "type(r) AS rel_type, properties(r) AS rel_props"
            )
            edge_result = session.run(edge_query, {"node_ids": node_ids})
            edges = []
            for record in edge_result:
                edges.append(
                    {
                        "source": record["source_id"],
                        "target": record["target_id"],
                        "type": record["rel_type"],
                        "properties": _convert_node_props(dict(record["rel_props"]))
                        if record["rel_props"]
                        else {},
                    }
                )

        return {
            "nodes": list(nodes_map.values()),
            "edges": edges,
        }


neo4j_service = Neo4jService()
