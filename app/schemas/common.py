"""Common API response schemas conforming strictly to the specification envelope."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIErrorDetails(BaseModel):
    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error description")
    details: Any | None = Field(default=None, description="Optional granular error details")


class APIResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Indicates request success status")
    data: T | None = Field(default=None, description="Response payload")
    error: APIErrorDetails | None = Field(default=None, description="Error details when failed")

    @classmethod
    def ok(cls, data: T) -> "APIResponse[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str, details: Any | None = None) -> "APIResponse[None]":
        return cls(
            success=False,
            data=None,
            error=APIErrorDetails(code=code, message=message, details=details),
        )


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    total: int
    has_more: bool
