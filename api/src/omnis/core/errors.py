"""Typed, sanitized API errors and server-owned request correlation."""

from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from enum import StrEnum
from http import HTTPStatus
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
    ENGAGEMENT_CONFLICT = "ENGAGEMENT_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    WEB_UNAVAILABLE = "WEB_UNAVAILABLE"


class FieldError(BaseModel):
    field: str = Field(max_length=96)
    code: Literal["REQUIRED", "INVALID_VALUE", "TOO_LONG", "TOO_MANY", "UNKNOWN_FIELD"]


class ErrorDetail(BaseModel):
    code: ErrorCode
    correlation_id: UUID
    field_errors: list[FieldError] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


_FIELDS = {
    "name",
    "authorization",
    "owner",
    "statement",
    "valid_from",
    "valid_until",
    "scope",
    "origin",
    "port",
    "path_prefix",
    "exclusions",
    "access",
    "assessment_mode",
    "objective_text",
    "objective_constraints",
    "id",
    "kind",
    "text",
    "operation_refs",
    "workflow_profile_ref",
    "application_context",
    "seed_urls",
    "priority_workflows",
    "test_objects",
    "import_ref",
    "effect_rules",
    "effect_class",
    "decision",
    "note",
    "budgets",
    "max_requests",
    "max_duration_seconds",
    "max_storage_bytes",
    "validation_reserved_requests",
    "max_model_calls",
    "data_policy",
    "model_projection",
    "research_egress",
    "retention_days",
    "business_matrix",
    "business_rules_ref",
    "principal",
    "role",
    "tenant",
    "object",
    "operation",
    "expected",
    "source",
    "source_revision",
    "after",
    "limit",
    "if-match",
    "x-command-id",
}


def validation_field_errors(errors: Iterable[Mapping[str, object]]) -> list[FieldError]:
    """Expose only known field paths and stable reason codes, never input or exception text."""
    result: list[FieldError] = []
    for issue in errors:
        location = issue.get("loc", ())
        parts: list[str] = []
        if isinstance(location, (list, tuple)):
            for item in location[1:]:
                if isinstance(item, str) and item in _FIELDS:
                    parts.append(item)
                elif type(item) is int and 0 <= item <= 64:
                    parts.append(str(item))
                else:
                    break
        field = ".".join(parts) or "body"
        issue_type = issue.get("type")
        if issue_type == "focused_objective":
            field = "objective_text"
        elif issue_type == "authorization_window":
            field = "authorization.valid_until"
        elif issue_type == "invalid_budget_reserve":
            field = "budgets.validation_reserved_requests"
        code: FieldErrorCode
        if issue_type in {"missing", "string_too_short", "list_too_short"}:
            code = "REQUIRED"
        elif (
            issue_type == "string_too_long"
            or (issue_type == "too_long" and isinstance(issue.get("input"), str))
            or issue_type == "draft_too_large"
        ):
            code = "TOO_LONG"
        elif issue_type in {"too_long", "list_too_long"}:
            code = "TOO_MANY"
        elif issue_type == "extra_forbidden":
            code = "UNKNOWN_FIELD"
        else:
            code = "INVALID_VALUE"
        if not any(item.field == field for item in result):
            result.append(FieldError(field=field, code=code))
        if len(result) >= 16:
            break
    return result


type FieldErrorCode = Literal["REQUIRED", "INVALID_VALUE", "TOO_LONG", "TOO_MANY", "UNKNOWN_FIELD"]


def error_responses(*statuses: int) -> dict[int | str, dict[str, object]]:
    """Declare the same error DTO used by the HTTP boundary and exception handlers."""
    return {
        status: {"model": ErrorEnvelope, "description": HTTPStatus(status).phrase}
        for status in statuses
    }
