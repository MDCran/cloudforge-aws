import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(StrEnum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TRANSITIONS = {
    Status.CREATED: {Status.UPLOADING, Status.CANCELLED},
    Status.UPLOADING: {Status.QUEUED, Status.CANCELLED},
    Status.QUEUED: {Status.PROCESSING, Status.CANCELLED},
    Status.PROCESSING: {Status.COMPLETED, Status.FAILED, Status.QUEUED},
    Status.COMPLETED: set(),
    Status.FAILED: set(),
    Status.CANCELLED: set(),
}


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=5, max_length=120)
    size: int = Field(gt=0, le=10 * 1024 * 1024)
    required_columns: list[str] = Field(default_factory=list, max_length=64)
    numeric_columns: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def safe_names(self) -> Self:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_. -]*\.csv", self.filename):
            raise ValueError("Use a plain CSV filename without path separators")
        for columns in (self.required_columns, self.numeric_columns):
            if len(set(columns)) != len(columns) or any(not c or len(c) > 100 for c in columns):
                raise ValueError("Column names must be unique and nonempty")
        return self


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)
