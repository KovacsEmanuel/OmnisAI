"""Private owner configuration source and exact pre-initialization DATA reader.

CONFIG_SOURCE_READY is not model availability, compatibility or execution authority.
"""

from urllib.parse import urlsplit

from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import exact, integer, mapping, text

FIELDS = {
    "version",
    "decision_id",
    "provider",
    "model_id",
    "base_url",
    "api_mode",
    "reasoning_config",
    "max_tokens",
    "capabilities",
    "technical_caps",
    "native_config",
}
PROVENANCE = "PRIVATE_OWNER_CONFIGURATION_COMMAND_V1"


def exact_configuration_types(value: object, depth: int = 0) -> None:
    """Check before helpers serialize/normalize Python objects into JSON builtins."""
    if depth > 8:
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise CatalogError("MODEL_CONFIGURATION_REJECTED")
            exact_configuration_types(key, depth + 1)
            exact_configuration_types(child, depth + 1)
    elif type(value) is str:
        if any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in "\u2028\u2029" for c in value):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    elif type(value) not in (int, bool, type(None)):
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")


def validate_ready_source(value: object) -> dict[str, object]:
    exact_configuration_types(value)
    config = exact(value, FIELDS)
    integer(config["version"], 1, 1)
    uuid_string(config["decision_id"])
    for key in ("provider", "model_id"):
        source = text(config[key], 256)
        if source != source.strip() or any(ord(c) < 32 for c in source):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    source = text(config["base_url"], 1024)
    try:
        route = urlsplit(source)
        port = route.port
    except ValueError:
        raise CatalogError("MODEL_CONFIGURATION_REJECTED") from None
    if (
        source != source.strip()
        or any(ord(c) < 33 for c in source)
        or route.scheme != "https"
        or not route.hostname
        or route.username is not None
        or route.password is not None
        or "?" in source
        or "#" in source
        or route.netloc.endswith(":")
        or (port is not None and not 1 <= port <= 65535)
        or config["api_mode"] != "chat_completions"
    ):
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    reasoning = config["reasoning_config"]
    if reasoning is not None:
        r = exact(reasoning, {"enabled", "effort"})
        if type(r["enabled"]) is not bool:
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        if r["effort"] is not None:
            text(r["effort"], 64)  # preserve exact value; no compatibility claim
    caps = exact(config["technical_caps"], {"calls", "output_tokens", "wall_seconds"})
    integer(caps["calls"], 1, 1)
    output = integer(caps["output_tokens"], 1, 65536)
    integer(caps["wall_seconds"], 1, 1200)
    integer(config["max_tokens"], 1, output)
    capabilities = mapping(config["capabilities"])
    if len(capabilities) > 16 or any(
        type(k) is not str or not k or len(k) > 64 or type(v) is not bool
        for k, v in capabilities.items()
    ):
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    native = exact(
        config["native_config"],
        {"reasoning_echo", "prompt_caching", "context_length", "compression"},
    )
    if type(native["reasoning_echo"]) is not bool or type(native["prompt_caching"]) is not bool:
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    integer(native["context_length"], 1024, 900000)
    compression = exact(native["compression"], {"enabled"})
    if type(compression["enabled"]) is not bool:
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    if len(canonical(config)) > 2048:
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    # Detach nested caller aliases without introducing a permissive serializer.
    from omnis.modules.settings.catalog_schema import load_json

    return mapping(load_json(canonical(config)))


def initialization_data(config: object) -> bytes:
    source = validate_ready_source(config)
    return canonical({key: source[key] for key in FIELDS - {"version", "decision_id"}})
