import uuid
from typing import Any, Dict, List, Optional, Type, Union

from sqlalchemy import delete, select, update

from app.db.base import Base, ModelType
from app.utils.filters import FilterBuilder


class BaseService:
    def __init__(self, db, model: Type[ModelType]):
        self._db = db
        self._model = model

    async def get_objects(
        self,
        filter_query: Any = None,
    ) -> Dict:
        query = select(self._model)

        filter_builder = FilterBuilder(model=self._model)
        query = filter_builder.apply(query=query, filters=filter_query)

        result = await self._db.execute(query)
        instances = list(result.scalars().all())

        return dict(results=instances)

    async def get_object(
        self,
        instance_id: Union[uuid.UUID, int],
    ) -> Optional[Base]:
        query = select(self._model).where(self._model.id == instance_id)  # type: ignore
        result = await self._db.execute(query)
        return result.scalar_one_or_none()

    async def create_object(self, data: Dict[str, Any]) -> Base:
        instance = self._model(**data)
        self._db.add(instance)
        await self._db.commit()
        await self._db.refresh(instance)
        return instance

    async def update_object(
        self, instance_id: Union[uuid.UUID, int], data: Dict[str, Any]
    ) -> Optional[Base]:
        instance = await self.get_object(instance_id=instance_id)
        if not instance:
            return None

        if data:
            query = (
                update(self._model)
                .where(self._model.id == instance_id)  # type: ignore
                .values(**data)
                .execution_options(synchronize_session="fetch")
            )

            await self._db.execute(query)
            await self._db.commit()
            await self._db.refresh(instance)

        return instance

    async def delete_object(self, instance_id: Union[uuid.UUID, int]) -> bool:
        instance = await self.get_object(instance_id=instance_id)
        if not instance:
            return False

        await self._db.delete(instance)
        await self._db.commit()
        return True

    async def get_model_values(
        self,
        field: str,
        filter_query: Any = None,
    ) -> List[Any]:
        try:
            query = select(getattr(self._model, field))

            filter_builder = FilterBuilder(model=self._model)
            query = filter_builder.apply_filters(query=query, filters=filter_query)
            result = await self._db.execute(query)
            values = result.scalars().all()
        except Exception:
            values = []

        return sorted(list(set(values))) if values else []

    async def bulk_create_or_update(self, data: List[Dict[str, Any]]) -> List[Base]:
        results = []

        object_ids = [item["id"] for item in data if "id" in item]

        query = select(self._model).where(self._model.id.in_(object_ids))  # type: ignore
        result = await self._db.execute(query)
        existing_instances = {instance.id: instance for instance in list(result.scalars().all())}

        for item in data:
            if "id" in item and item["id"] in existing_instances:
                instance = await self.update_object(instance_id=item["id"], data=item)
            else:
                instance = await self.create_object(data=item)
            results.append(instance)

        return results

    async def bulk_delete(self, data: Dict[str, List[Any]]):
        if data:
            query = delete(self._model)
            for field, values in data.items():
                query = query.where(getattr(self._model, field).in_(values))

            await self._db.execute(query)
            await self._db.commit()


# end
