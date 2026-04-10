from enum import Enum


class Status(str, Enum):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    UPLOADED = "UPLOADED"
    PENDING = "PENDING"
