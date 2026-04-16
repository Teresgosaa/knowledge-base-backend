from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class PropertyDef:
    name: str
    type: str
    required: bool = False
    description: str = ""
    default: str | None = None


@dataclass(frozen=True)
class NodeDef:
    node_type: str
    layer: str
    label: str
    description: str
    properties: List[PropertyDef] = field(default_factory=list)
    subtypes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RelationshipDef:
    rel_type: str
    source_types: List[str]
    target_types: List[str]
    description: str
    properties: List[PropertyDef] = field(default_factory=list)
    uses_semantic_source: bool = False
    uses_semantic_target: bool = False
