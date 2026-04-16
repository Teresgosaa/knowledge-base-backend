import json
from dataclasses import dataclass
from typing import Any, Dict, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.layer import Layer
from app.db.node_type import NodeType
from app.db.relationship_type import RelationshipTypeModel

T = TypeVar("T")


@dataclass(frozen=True)
class Entry:
    cls: Type[T]  # type: ignore
    path: str
    name: str
    nested_cls: Type[T] | None  # type: ignore
    nested_field: str | None = None
    nested_relation: str | None = None


ENTRIES = (
    Entry(Layer, "data/setup_db/layers.json", "Слои", None, None, None),
    Entry(NodeType, "data/setup_db/node_types.json", "Типы нод", None, None, None),
    Entry(RelationshipTypeModel, "data/setup_db/relationship_types.json", "Типы связей", None, None, None),
)


async def setup_db(db: AsyncSession) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for entry in ENTRIES:
        result[entry.name] = {}

        print(f"Loading from {entry.path}")
        try:
            with open(entry.path, encoding="utf-8") as fp:
                data = json.load(fp)
                print(f"- Found {len(data)} objects")
        except json.JSONDecodeError as error:
            message = f"Error parsing {entry.path}: {str(error)}"
            result[entry.name] = {"error": message}
            continue
        except Exception as error:
            message = f"Error reading {entry.path}: {str(error)}"
            result[entry.name] = {"error": message}
            continue

        created = 0
        updated = 0

        for item in data:
            alias = item["alias"]
            query_result = await db.execute(
                select(entry.cls).where(entry.cls.alias == alias)  # type: ignore
            )

            model_object = query_result.scalar_one_or_none()

            nested_items: list = []
            if entry.nested_field is not None:
                nested_items = item.pop(entry.nested_field)

            if model_object:
                updated += 1
                for field, value in item.items():
                    setattr(model_object, field, value)
            else:
                created += 1
                model_object = entry.cls(**item)
                db.add(model_object)

            # Flush to get the ID if it's a new object
            await db.flush()

            # Handle nested items
            if nested_items and entry.nested_cls is not None and model_object.id:  # type: ignore
                for nested_item in nested_items:
                    alias = nested_item["alias"]
                    query_result = await db.execute(
                        select(entry.nested_cls).where(entry.nested_cls.alias == alias)  # type: ignore
                    )
                    nested_model_object = query_result.scalar_one_or_none()

                    if nested_model_object:
                        for field, value in nested_item.items():
                            setattr(nested_model_object, field, value)

                    else:
                        nested_model_object = entry.nested_cls(**nested_item)
                        setattr(
                            nested_model_object,
                            entry.nested_relation,  # type: ignore
                            model_object.id,  # type: ignore
                        )
                        db.add(nested_model_object)

        # Commit all changes at once for better performance
        await db.commit()

        result[entry.name] = {"created": created, "updated": updated}

    return result


# end
