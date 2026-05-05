from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ErrorCode


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
