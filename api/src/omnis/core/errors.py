"""Typed, sanitized API errors and server-owned request correlation."""

from contextvars import ContextVar
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

request_correlation: ContextVar[UUID | None] = ContextVar("omnis_request_correlation", default=None)


class ErrorCode(StrEnum):
    INVALID_HOST = "INVALID_HOST"
    INVALID_ORIGIN = "INVALID_ORIGIN"
    QUERY_NOT_ALLOWED = "QUERY_NOT_ALLOWED"
    BODY_TOO_LARGE = "BODY_TOO_LARGE"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    CONTROL_UNAVAILABLE = "CONTROL_UNAVAILABLE"
    INVALID_CSRF = "INVALID_CSRF"
    CONTROL_TIMEOUT = "CONTROL_TIMEOUT"
    PAIRING_DENIED = "PAIRING_DENIED"
    PAIRING_RATE_LIMITED = "PAIRING_RATE_LIMITED"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    correlation_id: UUID


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
