"""Exactly three installed PURE transformations; no package code loading."""

from typing import Annotated, Literal

from pydantic import Field, ValidationError

from omnis.modules.settings.catalog_models import CatalogError, StrictDTO
from omnis.modules.settings.catalog_schema import canonical, load_json

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
CapturePath = Annotated[str, Field(pattern=r"^/[^\\\s]*$", max_length=240)]
Status = Annotated[int, Field(ge=100, le=599)]


class Capture(StrictDTO):
    capture: Annotated[str, Field(max_length=65536)]


class Record(StrictDTO):
    method: Method
    path: CapturePath
    status: Status


class Records(StrictDTO):
    records: Annotated[tuple[Record, ...], Field(max_length=128)]


class Operation(StrictDTO):
    method: Method
    path: CapturePath
    statuses: Annotated[tuple[Status, ...], Field(min_length=1, max_length=128)]


class Operations(StrictDTO):
    operations: Annotated[tuple[Operation, ...], Field(max_length=128)]


def run_handler(handler: str, input_object: object) -> object:
    try:
        if handler == "contract.parse-capture":
            capture = Capture.model_validate_json(canonical(input_object), strict=True)
            parsed = load_json(capture.capture)
            records = Records.model_validate_json(canonical({"records": parsed}), strict=True)
            return records.model_dump(mode="json")
        if handler == "contract.normalize-operations":
            records = Records.model_validate_json(canonical(input_object), strict=True)
            grouped: dict[tuple[str, str], set[int]] = {}
            for record in records.records:
                grouped.setdefault((record.path, record.method), set()).add(record.status)
            return {
                "operations": [
                    {"method": method, "path": path, "statuses": sorted(statuses)}
                    for (path, method), statuses in sorted(grouped.items())
                ]
            }
        if handler == "contract.build-map":
            operations = Operations.model_validate_json(canonical(input_object), strict=True)
            methods_by_path: dict[str, set[str]] = {}
            for operation in operations.operations:
                methods_by_path.setdefault(operation.path, set()).add(operation.method)
            return {
                "surface_map": [
                    {"path": path, "methods": sorted(methods), "operation_count": len(methods)}
                    for path, methods in sorted(methods_by_path.items())
                ]
            }
    except ValidationError:
        raise CatalogError("INVALID_PURE_INPUT") from None
    raise CatalogError("UNKNOWN_HANDLER")
