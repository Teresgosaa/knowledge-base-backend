import datetime as dt
from typing import Any

NONE_VALUES: list = ["None", None, "null", "NULL", "Null"]


def standardize_date(value: str, value_type: str = "date") -> Any:
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y.%m.%d",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y%m%d",
        "%m-%d-%Y",
        "%A, %B %d, %Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%Y%m%d %H%M%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%b %d, %Y %I:%M %p",
        "%H:%M:%S",
        "%H:%M",
        "%H%M%S",
    ]

    for fmt in formats:
        try:
            date = dt.datetime.strptime(value, fmt)
            if any(c in fmt for c in ["H", "M", "S", "I", "p"]):
                if value_type is not None and value_type == "datetime":
                    return date.strftime("%Y-%m-%d %H:%M:%S")
                elif value_type is not None and value_type == "date":
                    return date.strftime("%Y-%m-%d")
                elif value_type is not None and value_type == "time":
                    return date.strftime("%H:%M:%S")
                else:
                    return date.strftime("%Y-%m-%d %H:%M:%S")
            return date.strftime("%Y-%m-%d")
        except ValueError:
            continue
        except TypeError:
            continue

    return value


def map_types(value, value_type) -> Any:
    if value in NONE_VALUES:
        return None
    if not value:
        return value

    match value_type:
        case "int":
            try:
                return int(value)
            except ValueError:
                return value
        case "float":
            try:
                return float(value)
            except ValueError:
                return value
        case "str":
            try:
                return str(value)
            except ValueError:
                return value
        case "bool":
            try:
                return bool(value)
            except ValueError:
                return value
        case "date" | "datetime" | "time":
            try:
                return standardize_date(value=value, value_type=value_type)
            except ValueError:
                return value

    return value
