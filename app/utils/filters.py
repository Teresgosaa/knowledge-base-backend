import re
from datetime import datetime
from math import ceil
from typing import Any, Dict

from sqlalchemy import JSON, and_, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Query as SQLAlchemyQuery

NON_FILTER_FIELDS = ["page", "page_size", "count", "sort"]
EMPTY_VALUES = [None, [], {}]


class FilterBuilder:
    def __init__(self, model, extra_fields: dict | None = None):
        self.model = model
        self.conditions = []
        self.extra_fields = extra_fields

    def _parse_type_string(self, type_str: str) -> tuple:
        """
        Parse type string like 'list[int]', 'str', 'datetime' into (base_type, inner_type).

        Returns:
            tuple: (base_type, inner_type or None)
        """
        type_str = type_str.strip().lower()

        # Handle list types: list[int], list[str], etc.
        list_match = re.match(r"list\[(\w+)\]", type_str)
        if list_match:
            inner_type = list_match.group(1)
            return ("list", inner_type)

        # Handle simple types
        return (type_str, None)

    def _convert_value(self, value: str, type_str: str) -> Any:
        """
        Convert string value to the specified type.

        Args:
            value: String value from query params
            type_str: Type string like 'int', 'list[str]', 'datetime', etc.

        Returns:
            Converted Python value
        """
        if not isinstance(value, str):
            return value

        base_type, inner_type = self._parse_type_string(type_str)

        # Handle List types
        if base_type == "list":
            if not value.strip():
                return []

            items = [item.strip() for item in value.split(",")]

            # Convert each item based on inner type
            converted_items = []
            for item in items:
                converted_items.append(self._convert_single_value(item, inner_type))

            return converted_items

        # Handle single value types
        return self._convert_single_value(value, base_type)

    def _convert_single_value(self, value: str, type_str: str) -> Any:
        """
        Convert a single string value to the specified type.
        """
        type_str = type_str.strip().lower()

        # Boolean
        if type_str in ("bool", "boolean"):
            return value.lower() in ("true", "1", "yes")

        # Integer
        if type_str == "int":
            try:
                return int(value)
            except ValueError:
                return value  # Return original if conversion fails

        # Float
        if type_str in ("float", "double"):
            try:
                return float(value)
            except ValueError:
                return value

        # Date
        if type_str == "date":
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return value

        # DateTime
        if type_str in ("datetime", "timestamp"):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value

        # String (default)
        return value

    def add_filter(self, field: str, value: Any):
        operator = "eq"

        if isinstance(value, list):
            operator = "in"

        if "__" in field:
            field, operator = field.split("__", 1)

        column = getattr(self.model, field, None)

        def add_condition(condition):
            self.conditions.append(condition)

        if column is None:
            if hasattr(self.model, "data"):
                data_column = getattr(self.model, "data")

                if hasattr(data_column, "type") and isinstance(
                    data_column.type, (JSON, JSONB)
                ):
                    try:
                        json_field = data_column[field]
                        json_text_field = json_field.as_string()

                        if operator == "eq":
                            add_condition(json_text_field == str(value))
                        elif operator == "contains":
                            add_condition(json_text_field.ilike(f"%{value}%"))
                        elif operator == "in":
                            add_condition(json_text_field.in_([str(v) for v in value]))
                        elif operator == "gt":
                            add_condition(json_text_field > str(value))
                        elif operator == "gte":
                            add_condition(json_text_field >= str(value))
                        elif operator == "lt":
                            add_condition(json_text_field < str(value))
                        elif operator == "lte":
                            add_condition(json_text_field <= str(value))
                        return self
                    except (AttributeError, TypeError, KeyError) as error:
                        print(f"JSON field {field} not found {str(error)}")

                return self
        else:
            if operator == "eq":
                add_condition(column == value)
            elif operator == "contains":
                add_condition(column.ilike(f"%{value}%"))
            elif operator == "in":
                add_condition(column.in_(value))
            elif operator == "gt":
                add_condition(column > value)
            elif operator == "gte":
                add_condition(column >= value)
            elif operator == "lt":
                add_condition(column < value)
            elif operator == "lte":
                add_condition(column <= value)

        return self

    def apply_filters(self, query, filters) -> SQLAlchemyQuery:
        if not filters:
            return query

        defined_fields = (
            filters.model_dump() if hasattr(filters, "model_dump") else filters.dict()
        )
        extra_fields = filters.model_extra if hasattr(filters, "model_extra") else {}

        for field, value in defined_fields.items():
            if value not in EMPTY_VALUES and value and hasattr(self.model, field):
                self.add_filter(field, value)

        for field, value in extra_fields.items():
            if value not in EMPTY_VALUES:
                if self.extra_fields is not None and field in self.extra_fields:
                    type_str = self.extra_fields[field]
                    converted_value = self._convert_value(value, type_str)
                    self.add_filter(field, converted_value)
                else:
                    self.add_filter(field, value)

        if self.conditions:
            query = query.where(and_(*self.conditions))
        return query

    def apply_sorting(self, query, filters) -> SQLAlchemyQuery:
        if not getattr(filters, "sort", None):
            return query

        sort_fields = filters.sort.split(",")
        for field in sort_fields:
            direction = "desc" if field.startswith("-") else "asc"
            field_name = field.lstrip("-")

            if hasattr(self.model, field_name):
                if direction == "desc":
                    query = query.order_by(getattr(self.model, field_name).desc())
                else:
                    query = query.order_by(getattr(self.model, field_name).asc())
            else:
                if hasattr(self.model, "data"):
                    data_column = getattr(self.model, "data")

                    if hasattr(data_column, "type") and isinstance(
                        data_column.type, (JSON, JSONB)
                    ):
                        try:
                            json_field = data_column[field_name]
                            json_text_field = json_field.as_string()
                            if direction == "desc":
                                query = query.order_by(json_text_field.desc())
                            else:
                                query = query.order_by(json_text_field.asc())
                        except (AttributeError, TypeError, KeyError) as error:
                            print(f"JSON field {field_name} not found {str(error)}")

        return query

    def apply_pagination(self, query, filters) -> SQLAlchemyQuery:
        page_size = getattr(filters, "page_size", None)
        if not page_size:
            return query

        if filters.page_size != 0:
            query = query.offset(filters.page).limit(filters.page_size)

        return query

    def apply(self, query, filters) -> SQLAlchemyQuery:
        query = self.apply_filters(query, filters)
        query = self.apply_sorting(query, filters)
        query = self.apply_pagination(query, filters)
        return query

    async def paginate(self, db, filters) -> Dict:
        query = select(func.count(self.model.id))
        query = self.apply_filters(query, filters)

        result = await db.execute(query)
        count = result.scalar() or 0
        pages = ceil(count / filters.page_size) if count > 0 else 0

        return dict(
            pages=pages, count=count, page=filters.page, page_size=filters.page_size
        )


# end
