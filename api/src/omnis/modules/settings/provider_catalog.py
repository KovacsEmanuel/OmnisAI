"""Documented provider shapes only; upstream continuation is data, never a URL grant."""

from urllib.parse import parse_qsl

from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.modules.settings.provider_catalog_models import CatalogModel, CatalogReason
from omnis.modules.settings.provider_key_models import Provider


def normalize(provider: Provider, raw: object) -> CatalogModel:
    if not isinstance(raw, dict):
        raise ValueError("Unknown model schema")
    name: object = raw.get("name")
    maximum: object = raw.get("max_completion_tokens")
    supported: bool | None = None
    if provider == "openrouter":
        top: object = raw.get("top_provider")
        maximum = top.get("max_completion_tokens") if isinstance(top, dict) else None
        parameters: object = raw.get("supported_parameters")
        if isinstance(parameters, list) and all(isinstance(x, str) for x in parameters):
            supported = "max_tokens" in parameters
    # Orca's endpoint types do not prove support for a particular parameter.
    return CatalogModel.model_validate(
        {
            "model": raw.get("id"),
            "name": name if isinstance(name, str) and len(name) <= 128 else None,
            "max_output_tokens": min(maximum, 65536)
            if type(maximum) is int and maximum > 0
            else None,
            "supports_max_tokens": supported,
        }
    )


class CatalogIngest:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.entries: dict[str, CatalogModel] = {}
        self.offset = 0
        self.pages = 0
        self.bytes = 0
        self.total: int | None = None
        self.complete = False
        self.reason: CatalogReason | None = None
        self.ambiguous: set[str] = set()

    def add(self, raw: object, secret: str | None = None) -> int | None:
        self.pages += 1
        if not isinstance(raw, dict) or not isinstance(raw.get("data"), list):
            self.reason = "SCHEMA_UNSUPPORTED"
            return None
        rows: list[object] = raw["data"]
        allowed = (
            {"data", "links", "total_count"}
            if self.provider == "openrouter"
            else {"object", "data"}
        )
        if set(raw) - allowed:
            self.reason = "SCHEMA_UNSUPPORTED"
        if self.provider == "orcarouter" and raw.get("object") != "list":
            self.reason = "SCHEMA_UNSUPPORTED"
        for raw_row in rows:
            try:
                row = normalize(self.provider, raw_row)
            except ValueError:
                self.reason = "ROW_UNSUPPORTED"
                continue
            if secret is not None and (
                secret in row.model or (row.name is not None and secret in row.name)
            ):
                self.reason = "ROW_UNSUPPORTED"
                continue
            previous = self.entries.get(row.model)
            if previous is not None and previous != row:
                self.ambiguous.add(row.model)
            if row.model in self.ambiguous:
                row = CatalogModel(model=row.model, reason="ROW_UNSUPPORTED")
            if row.model not in self.entries and len(self.entries) == 8192:
                self.reason = "CATALOG_LIMIT"
                return None
            self.entries[row.model] = row
        total: object = raw.get("total_count")
        if total is not None:
            if (
                type(total) is not int
                or total < 0
                or total > 8192
                or (self.total is not None and total != self.total)
            ):
                self.reason = "TOTAL_MISMATCH"
                return None
            self.total = total
        links: object = raw.get("links")
        if links is not None and not isinstance(links, dict):
            self.reason = "CONTINUATION_UNSUPPORTED"
            return None
        next_url: object = links.get("next") if isinstance(links, dict) else None
        self.offset += len(rows)
        if next_url is not None:
            base, _, query = next_url.partition("?") if isinstance(next_url, str) else ("", "", "")
            try:
                parameters = parse_qsl(query, strict_parsing=True, max_num_fields=2)
            except ValueError:
                parameters = []
            expected = ENDPOINTS[self.provider] + "/models"
            if (
                self.provider != "openrouter"
                or not rows
                or base not in (expected, expected.removeprefix("https://openrouter.ai"))
                or sorted(parameters) != [("limit", "1000"), ("offset", str(self.offset))]
                or self.pages >= 32
                or self.offset > 8192
            ):
                self.reason = "CONTINUATION_UNSUPPORTED"
                return None
            return self.offset
        if any(key in raw for key in ("next", "has_more", "next_page", "cursor")):
            self.reason = "CONTINUATION_UNSUPPORTED"
        if self.total is not None and (
            len(self.entries) != self.total or self.offset != self.total
        ):
            self.reason = "TOTAL_MISMATCH"
        if self.provider == "openrouter":
            if self.total is None:
                self.reason = "TOTAL_MISMATCH"
        elif links is not None or any(
            key in raw for key in ("next", "has_more", "next_page", "cursor")
        ):
            self.reason = "CONTINUATION_UNSUPPORTED"
        self.complete = self.reason is None
        return None
