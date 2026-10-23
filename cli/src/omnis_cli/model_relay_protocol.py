"""Private finite model relay wire contract; mirrored byte-exact in the API wheel."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from uuid import UUID

MAX_INT = 9223372036854775807
HOSTS = {"openrouter": "openrouter.ai", "orcarouter": "api.orcarouter.ai"}


def canonical_uuid(value: object) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Noncanonical relay identity")
    return value


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid relay integer")
    return value


def utc(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("Invalid relay UTC")
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(0):
        raise ValueError("Invalid relay UTC")
    return result


def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate relay field")
        result[key] = value
    return result


def decode(raw: bytes) -> dict[str, object]:
    if len(raw) > 4096 or not raw.endswith(b"\n"):
        raise ValueError("Relay control limit")
    value: object = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Invalid relay object")
    return value


def encode(value: dict[str, object]) -> bytes:
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    decode(raw)
    return raw


@dataclass(frozen=True)
class Scope:
    instance_id: str
    kind: str
    id: str
    execution_owner_id: str
    generation: int
    owner_epoch: int
    cancel_epoch: int
    deadline: str
    provider: str

    @classmethod
    def parse(cls, value: object) -> "Scope":
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid relay scope")
        if value["kind"] not in ("MODEL_DISPATCH", "METADATA_COMMAND"):
            raise ValueError("Invalid relay purpose")
        if not isinstance(value["provider"], str) or value["provider"] not in HOSTS:
            raise ValueError("Invalid relay provider")
        kind, provider, deadline = value["kind"], value["provider"], value["deadline"]
        if (
            not isinstance(kind, str)
            or not isinstance(provider, str)
            or not isinstance(deadline, str)
        ):
            raise ValueError("Invalid relay strings")
        utc(deadline)
        return cls(
            canonical_uuid(value["instance_id"]),
            kind,
            canonical_uuid(value["id"]),
            canonical_uuid(value["execution_owner_id"]),
            integer(value["generation"], 0, MAX_INT),
            integer(value["owner_epoch"], 1, MAX_INT),
            integer(value["cancel_epoch"], 1, MAX_INT),
            deadline,
            provider,
        )

    def wire(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Authority:
    scope: Scope
    write_deadline: str


def validate(value: dict[str, object]) -> Scope:
    if (
        set(value)
        != {
            "version",
            "action",
            "request_id",
            "connection_id",
            "scope",
            "sequence",
            "size",
            "timeout_ms",
            "write_deadline",
            "capability",
        }
        or type(value["version"]) is not int
        or value["version"] != 1
    ):
        raise ValueError("Invalid relay envelope")
    action = value["action"]
    if action not in ("OPEN", "WRITE", "READ", "FENCE", "DRAIN"):
        raise ValueError("Invalid relay action")
    canonical_uuid(value["request_id"])
    if action in ("FENCE", "DRAIN"):
        if value["connection_id"] is not None:
            raise ValueError("Invalid relay fence target")
    else:
        canonical_uuid(value["connection_id"])
    integer(value["sequence"], 0, MAX_INT)
    integer(value["size"], 0, 65536)
    integer(value["timeout_ms"], 1, 300000)
    if action != "WRITE" and value["size"] != 0 and action != "READ":
        raise ValueError("Unexpected relay body")
    cap = value["capability"]
    if not isinstance(cap, str) or len(cap) != 64 or any(c not in "0123456789abcdef" for c in cap):
        raise ValueError("Invalid relay capability")
    if action == "WRITE":
        utc(value["write_deadline"])
    elif value["write_deadline"] is not None:
        raise ValueError("Unexpected relay write window")
    return Scope.parse(value["scope"])
