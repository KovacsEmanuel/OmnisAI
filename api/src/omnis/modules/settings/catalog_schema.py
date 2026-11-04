"""Bounded, nonexecuting YAML/JSON and local JSON Schema 2020-12."""

import json
from collections.abc import Hashable
from typing import TypeVar, cast

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ValidationError
from yaml.events import AliasEvent, CollectionEndEvent, CollectionStartEvent, NodeEvent, ScalarEvent
from yaml.nodes import MappingNode

from .catalog_models import CatalogError, CoreManifest, CoreProfile, Manifest, Profile

MAX_BYTES = 1048576
T = TypeVar("T", bound=BaseModel)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def bounded(value: object, depth: int = 0) -> None:
    if depth > 32:
        raise CatalogError("DEPTH_LIMIT")
    if isinstance(value, dict):
        if len(value) > 128:
            raise CatalogError("COUNT_LIMIT")
        for key, item in value.items():
            if not isinstance(key, str):
                raise CatalogError("INVALID_KEY")
            bounded(key, depth + 1)
            bounded(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        if len(value) > 128:
            raise CatalogError("COUNT_LIMIT")
        for item in value:
            bounded(item, depth + 1)
    elif isinstance(value, str):
        if len(value) > 65536:
            raise CatalogError("TEXT_LIMIT")
    elif value is not None and type(value) not in (int, bool):
        raise CatalogError("INVALID_TYPE")
    elif type(value) is int and not -(2**63) <= value < 2**63:
        raise CatalogError("INTEGER_LIMIT")


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, object]:
        result: dict[Hashable, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise CatalogError("YAML_DUPLICATE_OR_KEY")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_yaml(raw: bytes) -> object:
    if len(raw) > 262144:
        raise CatalogError("SIZE_LIMIT")
    try:
        depth = 0
        for event in yaml.parse(raw):
            if isinstance(event, AliasEvent) or (
                isinstance(event, NodeEvent)
                and (
                    event.anchor is not None
                    or (
                        isinstance(event, (ScalarEvent, CollectionStartEvent))
                        and event.tag is not None
                    )
                )
            ):
                raise CatalogError("YAML_TAG_OR_ALIAS")
            if isinstance(event, CollectionStartEvent):
                depth += 1
                if depth > 32:
                    raise CatalogError("DEPTH_LIMIT")
            elif isinstance(event, CollectionEndEvent):
                depth -= 1
        value: object = yaml.load(raw, Loader=UniqueLoader)
        bounded(value)
        return value
    except (yaml.YAMLError, UnicodeError, RecursionError):
        raise CatalogError("INVALID_YAML") from None


def dto(raw: bytes, model: type[T]) -> T:
    try:
        value = load_yaml(raw)

        def literal_integers(item: object) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if (
                        key in ("schema_version", "brief_schema", "result_schema")
                        and type(child) is not int
                    ):
                        raise CatalogError("INVALID_DTO")
                    literal_integers(child)
            elif isinstance(item, list):
                for child in item:
                    literal_integers(child)

        literal_integers(value)
        return model.model_validate_json(canonical(value), strict=True)
    except ValidationError:
        raise CatalogError("INVALID_DTO") from None


def manifest_dto(raw: bytes) -> "Manifest | CoreManifest":
    from .catalog_models import CoreManifest, Manifest

    value = load_yaml(raw)
    if isinstance(value, dict) and type(value.get("schema_version")) is int:
        if value["schema_version"] == 2:
            return dto(raw, CoreManifest)
    return dto(raw, Manifest)


def profile_dto(raw: bytes) -> "Profile | CoreProfile":
    from .catalog_models import CoreProfile, Profile

    value = load_yaml(raw)
    if isinstance(value, dict) and type(value.get("schema_version")) is int:
        if value["schema_version"] == 2:
            return dto(raw, CoreProfile)
    return dto(raw, Profile)


def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise CatalogError("JSON_DUPLICATE")
        result[key] = value
    return result


def no_number(text: str) -> object:
    raise CatalogError("JSON_NON_INTEGER")


def load_json(raw: bytes | str) -> object:
    if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_BYTES:
        raise CatalogError("SIZE_LIMIT")
    try:
        value: object = json.loads(
            raw, object_pairs_hook=pairs, parse_float=no_number, parse_constant=no_number
        )
        bounded(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise CatalogError("INVALID_JSON") from None


def schema(raw: bytes) -> bytes:
    value = load_json(raw)
    if not isinstance(value, dict) or value.get("$schema") != (
        "https://json-schema.org/draft/2020-12/schema"
    ):
        raise CatalogError("SCHEMA_VERSION")
    supported = {
        "$schema",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "title",
        "description",
    }

    def check_subset(node: object) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            raise CatalogError("INVALID_SCHEMA")
        for keyword, child in node.items():
            if keyword in ("$ref", "$dynamicRef") and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                raise CatalogError("SCHEMA_EXTERNAL_REF")
            if keyword not in supported:
                raise CatalogError("SCHEMA_UNSUPPORTED")
            if keyword == "pattern" and child != r"^/[^\\\s]*$":
                raise CatalogError("SCHEMA_UNSUPPORTED")
            if keyword == "properties":
                if not isinstance(child, dict):
                    raise CatalogError("INVALID_SCHEMA")
                for subschema in child.values():
                    check_subset(subschema)
            elif keyword in ("items", "additionalProperties"):
                check_subset(child)

    check_subset(value)
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(child, str) or not child.startswith("#/$defs/")
                ):
                    raise CatalogError("SCHEMA_EXTERNAL_REF")
                if key in ("$id", "$anchor", "$dynamicAnchor", "format"):
                    raise CatalogError("SCHEMA_UNSUPPORTED")
                stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError:
        raise CatalogError("INVALID_SCHEMA") from None
    return canonical(value)


def validate(raw_schema: bytes, value: object) -> None:
    bounded(value)
    if len(canonical(value)) > MAX_BYTES:
        raise CatalogError("SIZE_LIMIT")
    parsed = cast(dict[str, object], load_json(raw_schema))
    validator = Draft202012Validator(parsed)
    if next(validator.iter_errors(value), None) is not None:
        raise CatalogError("SCHEMA_VALIDATION")
