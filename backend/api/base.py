"""
API Base Classes and Standard Response Models.

Provides unified response formats for all API endpoints.

Usage:
    from backend.api.base import APIResponse, PaginatedResponse, ErrorResponse

    @router.get("/items", response_model=APIResponse[List[Item]])
    async def get_items():
        items = await fetch_items()
        return APIResponse.success(data=items, message="Items fetched")

    @router.get("/items/{id}", response_model=APIResponse[Item])
    async def get_item(id: int):
        item = await fetch_item(id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return APIResponse.success(data=item)
"""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# Generic type for response data
T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    All API endpoints should return responses in this format for consistency.

    Attributes:
        success: Whether the request was successful
        data: The response payload (type varies by endpoint)
        message: Human-readable message about the result
        error: Error details if success is False
        timestamp: When the response was generated
        request_id: Optional request tracking ID
    """

    success: bool = Field(default=True, description="Whether the request succeeded")
    data: Optional[T] = Field(default=None, description="Response payload")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    error: Optional[str] = Field(default=None, description="Error details if failed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response timestamp",
    )
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")

    @classmethod
    def ok(
        cls,
        data: Optional[T] = None,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "APIResponse[T]":
        """Create a successful response."""
        return cls(
            success=True,
            data=data,
            message=message,
            request_id=request_id,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        message: Optional[str] = None,
        data: Optional[T] = None,
        request_id: Optional[str] = None,
    ) -> "APIResponse[T]":
        """Create an error response."""
        return cls(
            success=False,
            error=error,
            message=message or error,
            data=data,
            request_id=request_id,
        )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "data": {"id": 1, "name": "Example"},
                    "message": "Operation completed successfully",
                    "timestamp": "2026-01-26T12:00:00Z",
                }
            ]
        }


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=1000, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")

    @classmethod
    def from_query(cls, page: int, per_page: int, total_items: int) -> "PaginationMeta":
        """Create pagination meta from query parameters."""
        total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated API response.

    Use this for list endpoints that support pagination.
    """

    success: bool = True
    data: List[T] = Field(default_factory=list, description="List of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        items: List[T],
        page: int,
        per_page: int,
        total_items: int,
        message: Optional[str] = None,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        return cls(
            data=items,
            pagination=PaginationMeta.from_query(page, per_page, total_items),
            message=message,
        )


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(description="Error code for programmatic handling")
    message: str = Field(description="Human-readable error message")
    field: Optional[str] = Field(
        default=None, description="Field that caused the error"
    )
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )


class ErrorResponse(BaseModel):
    """
    Standardized error response.

    Use this for consistent error handling across the API.
    """

    success: bool = False
    error: str = Field(description="Main error message")
    code: str = Field(description="Error code")
    errors: Optional[List[ErrorDetail]] = Field(
        default=None, description="Detailed errors (for validation)"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None

    @classmethod
    def validation_error(
        cls,
        errors: List[ErrorDetail],
        request_id: Optional[str] = None,
    ) -> "ErrorResponse":
        """Create a validation error response."""
        return cls(
            error="Validation failed",
            code="VALIDATION_ERROR",
            errors=errors,
            request_id=request_id,
        )

    @classmethod
    def not_found(
        cls,
        resource: str,
        identifier: Any = None,
        request_id: Optional[str] = None,
    ) -> "ErrorResponse":
        """Create a not found error response."""
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} with id '{identifier}' not found"
        return cls(
            error=msg,
            code="NOT_FOUND",
            request_id=request_id,
        )

    @classmethod
    def internal_error(
        cls,
        message: str = "Internal server error",
        request_id: Optional[str] = None,
    ) -> "ErrorResponse":
        """Create an internal error response."""
        return cls(
            error=message,
            code="INTERNAL_ERROR",
            request_id=request_id,
        )


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(description="Overall status: healthy, degraded, unhealthy")
    version: str = Field(description="Application version")
    uptime_seconds: float = Field(description="Time since startup")
    checks: dict[str, Any] = Field(
        default_factory=dict, description="Individual component checks"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Export commonly used types
__all__ = [
    "APIResponse",
    "PaginatedResponse",
    "PaginationMeta",
    "ErrorResponse",
    "ErrorDetail",
    "HealthStatus",
]
