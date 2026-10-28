"""Synthetic documented schemas, not captured/live provider responses."""

import importlib.util
import json
from uuid import uuid4

import pytest

from omnis.api import create_app


def test_real_catalog_and_entry_routes_exist() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/settings/provider-catalog/search" in paths
    assert "/api/v1/model-test/entries" in paths


def test_exact_entry_admission_has_no_selection_authority() -> None:
    from uuid import uuid4

    from omnis.modules.runs.model_test_models import ModelTestControl

    intent = dict(
        op="entry_model_test",
        action="start",
        operation_id=str(uuid4()),
        entry_id=str(uuid4()),
        expected_entry_revision=1,
        expected_connection_revision=1,
        catalog_command_id=str(uuid4()),
        consent=True,
    )
    command = ModelTestControl.model_validate(intent)
    assert command.expected_selection_revision is None
    from omnis.modules.runs.model_test_operation import handle
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner

    legacy = object.__new__(NativeTaskOwner)

    async def reject_legacy() -> None:
        with pytest.raises(CatalogError, match="TASK_UNAVAILABLE"):
            await handle(legacy, command)

    import asyncio

    asyncio.run(reject_legacy())
    for extra in ({"expected_selection_revision": 1}, {"consent": 1}):
        with pytest.raises(ValueError):
            ModelTestControl.model_validate({**intent, **extra})


def test_entry_snapshot_ref_kinds_cannot_be_reinterpreted() -> None:
    from omnis.modules.runs.model_test_contract import EntryCapabilities, EntrySnapshot

    identity = str(uuid4())
    entry = dict(
        entry_id=identity,
        revision=1,
        connection_id=identity,
        connection_revision=1,
        model="Exact/model",
        output_tokens=64,
    )
    connection = dict(
        connection_id=identity,
        provider="openrouter",
        revision=1,
        enabled=True,
        secret_id=identity,
        credential_revision=1,
    )
    reference = dict(
        instance_id=identity, kind="foreign-kind", id=identity, digest="a" * 64, revision=1
    )
    for model, fields in (
        (
            EntrySnapshot,
            dict(
                entry=entry,
                connection=connection,
                capabilities_ref=reference,
                endpoint="https://openrouter.ai/api/v1",
            ),
        ),
        (
            EntryCapabilities,
            dict(entry=entry, connection=connection, catalog_ref=reference, max_output_tokens=128),
        ),
    ):
        with pytest.raises(ValueError):
            model.model_validate(fields)
        field, kind = (
            ("capabilities_ref", "model-entry-capabilities-v1")
            if model is EntrySnapshot
            else ("catalog_ref", "catalog-result")
        )
        assert (
            model.model_validate({**fields, field: {**reference, "kind": kind}}).model_dump()[
                field
            ]["kind"]
            == kind
        )


def test_catalog_normalization_is_provider_specific_and_exact() -> None:
    assert importlib.util.find_spec("omnis.modules.settings.provider_catalog") is not None
    from omnis.modules.settings.provider_catalog import normalize

    row = normalize(
        "openrouter",
        {
            "id": 'Vendor/Exact\\"',
            "name": "Name",
            "supported_parameters": ["max_tokens"],
            "top_provider": {"max_completion_tokens": 128},
        },
    )
    assert row.model == 'Vendor/Exact\\"' and row.name == "Name"
    assert row.max_output_tokens == 128 and row.supports_max_tokens is True
    orca = normalize("orcarouter", {"id": "same", "max_completion_tokens": 128})
    assert orca.max_output_tokens == 128 and orca.supports_max_tokens is None
    assert (
        normalize(
            "orcarouter",
            {
                "id": "same",
                "supported_parameters": ["max_tokens"],
                "top_provider": {"max_completion_tokens": 128},
            },
        ).max_output_tokens
        is None
    )
    for invalid in ("", " leading", "trailing ", "é", "x" * 257):
        with pytest.raises(ValueError):
            normalize("openrouter", {"id": invalid})


@pytest.mark.parametrize("base", ["https://openrouter.ai/api/v1/models", "/api/v1/models"])
@pytest.mark.parametrize("query", ["offset=1&limit=1000", "limit=1000&offset=1"])
def test_catalog_traversal_requires_exact_numeric_release_url_and_total(
    base: str, query: str
) -> None:
    assert importlib.util.find_spec("omnis.modules.settings.provider_catalog") is not None
    from omnis.modules.settings.provider_catalog import CatalogIngest

    ingest = CatalogIngest("openrouter")
    assert (
        ingest.add(
            {
                "data": [{"id": "a"}],
                "total_count": 2,
                "links": {"next": f"{base}?{query}"},
            }
        )
        == 1
    )
    assert ingest.add({"data": [{"id": "b"}], "total_count": 2, "links": {"next": None}}) is None
    assert ingest.complete and len(ingest.entries) == 2
    for next_url in (
        "https://evil.test/models?offset=1&limit=1000",
        "https://openrouter.ai/api/v1/models?offset=0&limit=1000",
        "https://openrouter.ai/api/v1/models?offset=1&limit=1000&token=x",
        "https://openrouter.ai/api/v1/models?offset=1&offset=1",
        "https://openrouter.ai/api/v1/models?limit=1000&limit=1000",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=1&offset=1",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=1#fragment",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=1#",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=1&",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=",
        "https://openrouter.ai/api/v1/models?limit=1000&offset=one",
        "https://user@openrouter.ai/api/v1/models?limit=1000&offset=1",
        "//openrouter.ai/api/v1/models?limit=1000&offset=1",
    ):
        partial = CatalogIngest("openrouter")
        assert (
            partial.add({"data": [{"id": "a"}], "total_count": 2, "links": {"next": next_url}})
            is None
        )
        assert not partial.complete and partial.reason == "CONTINUATION_UNSUPPORTED"
        assert list(partial.entries) == ["a"]
    duplicate = CatalogIngest("openrouter")
    duplicate.add({"data": [{"id": "a"}, {"id": "a"}], "total_count": 2})
    assert not duplicate.complete
    unknown = CatalogIngest("openrouter")
    unknown.add({"data": [{"id": "a"}]})
    assert not unknown.complete and list(unknown.entries) == ["a"]


@pytest.mark.asyncio
async def test_catalog_sender_grants_only_numeric_release_paging() -> None:
    from pathlib import Path

    import httpx

    from omnis.modules.runs.model_test_contract import ENDPOINTS
    from omnis.supervisor.model_sender import CURRENT, ModelSender, SendDenied
    from test_model_sender import guard

    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    requests: list[str] = []

    async def reply(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        permit = CURRENT.get()
        assert request.headers["authorization"] == "Bearer synthetic-key"
        assert permit.response_limit == 128 and not await request.aread()
        return httpx.Response(200, content=b'{"data":[]}')

    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(reply), follow_redirects=False, trust_env=False
    )
    try:
        assert await sender.metadata_page(
            ENDPOINTS["openrouter"], "synthetic-key", guard, 16, 128
        ) == ({"data": []}, 11)
        for endpoint, offset in (
            (ENDPOINTS["openrouter"] + "?key=x", 0),
            (ENDPOINTS["orcarouter"], 1),
            (ENDPOINTS["openrouter"], True),
            (ENDPOINTS["openrouter"], 8193),
        ):
            with pytest.raises(SendDenied):
                await sender.metadata_page(endpoint, "synthetic-key", guard, offset)
        assert requests == [ENDPOINTS["openrouter"] + "/models?offset=16&limit=1000"]
    finally:
        await sender.close()


def test_catalog_caps_duplicates_unknown_fields_and_secret_echo() -> None:
    from omnis.modules.settings.provider_catalog import CatalogIngest

    for maximum in (None, True, "128", -1, 0):
        ingest = CatalogIngest("openrouter")
        ingest.add(
            {
                "data": [{"id": "exact", "top_provider": {"max_completion_tokens": maximum}}],
                "total_count": 1,
            }
        )
        assert ingest.entries["exact"].max_output_tokens is None
    conflict = CatalogIngest("openrouter")
    conflict.add(
        {
            "data": [
                {"id": "exact", "supported_parameters": ["max_tokens"]},
                {"id": "exact", "supported_parameters": []},
            ],
            "total_count": 2,
        }
    )
    assert conflict.entries["exact"].supports_max_tokens is None
    assert conflict.entries["exact"].reason == "ROW_UNSUPPORTED" and not conflict.complete
    secret = CatalogIngest("openrouter")
    secret.add(
        {"data": [{"id": "safe", "name": "synthetic-secret"}], "total_count": 1}, "synthetic-secret"
    )
    assert not secret.entries and not secret.complete
    cap = CatalogIngest("openrouter")
    cap.add({"data": [{"id": str(i)} for i in range(8193)], "total_count": 8193})
    assert len(cap.entries) == 8192 and cap.reason == "CATALOG_LIMIT"
    pages = CatalogIngest("openrouter")
    for i in range(32):
        result = pages.add(
            {
                "data": [{"id": str(i)}],
                "total_count": 33,
                "links": {"next": f"/api/v1/models?offset={i + 1}&limit=1000"},
            }
        )
        assert result == (i + 1 if i < 31 else None)
    assert not pages.complete and pages.pages == 32
    orca = CatalogIngest("orcarouter")
    orca.add({"object": "list", "data": [{"id": "exact"}]})
    assert orca.complete and orca.entries["exact"].max_output_tokens is None
    continuations: tuple[dict[str, object], ...] = (
        {"next": []},
        {"next": "/api/v1/models?offset=1&limit=500"},
    )
    for links in continuations:
        invalid = CatalogIngest("openrouter")
        invalid.add({"data": [{"id": "a"}], "total_count": 2, "links": links})
        assert not invalid.complete


def test_final_dto_full_writer_budgets_and_legacy_limits() -> None:
    from omnis.modules.instance.schemas import ControlRequest
    from omnis.modules.runs.model_test_contract import EntryTestView, ModelTestView
    from omnis.modules.runs.model_test_models import EntryTestRequest, ModelTestControl
    from omnis.modules.settings.provider_catalog_models import (
        CatalogControl,
        CatalogModel,
        CatalogView,
        SearchCatalog,
    )
    from omnis.transport.local_control import decode_control_frame, encode_control_reply

    identity = str(uuid4())
    maximum = 9223372036854775807
    query = "\U0010ffff" * 256
    search = SearchCatalog(
        action="search",
        connection_id=identity,
        connection_revision=maximum,
        catalog_command_id=identity,
        query=query,
        offset=8176,
    )
    control = CatalogControl(op="provider_catalog", request=search)
    frame = (
        ControlRequest(version=1, capability="a" * 64, command=control).model_dump_json().encode()
        + b"\n"
    )
    escaped_frame = json.dumps(json.loads(frame)).encode() + b"\n"
    assert len(escaped_frame) <= 4096 and decode_control_frame(frame).command == control
    with pytest.raises(ValueError):
        SearchCatalog.model_validate({**search.model_dump(), "query": query + "x"})
    entries = [
        CatalogModel(
            model=('"\\' * 126) + f"{i:04b}".replace("0", chr(34)).replace("1", chr(92)),
            name="\U0010ffff" * 128,
            max_output_tokens=65536,
            supports_max_tokens=False,
            reason="CONTINUATION_UNSUPPORTED",
        )
        for i in range(16)
    ]
    catalog = CatalogView(
        connection_id=identity,
        connection_revision=maximum,
        provider="orcarouter",
        catalog_command_id=identity,
        state="PARTIAL",
        reason="CONTINUATION_UNSUPPORTED",
        query=query,
        offset=8176,
        total=8192,
        entries=entries,
    )
    catalog_reply = encode_control_reply(
        {
            "ok": True,
            "provider_catalog": catalog.model_dump(mode="json"),
            "correlation_id": identity,
        }
    )
    assert (
        json.loads(catalog_reply)["provider_catalog"]["entries"]
        == catalog.model_dump(mode="json")["entries"]
    )
    entry = EntryTestRequest(
        operation_id=identity,
        entry_id=identity,
        expected_entry_revision=maximum,
        expected_connection_revision=maximum,
        catalog_command_id=identity,
        consent=True,
    )
    entry_control = ModelTestControl.model_validate(
        {"op": "entry_model_test", "action": "start", **entry.model_dump()}
    )
    entry_frame = (
        ControlRequest(version=1, capability="a" * 64, command=entry_control)
        .model_dump_json()
        .encode()
        + b"\n"
    )
    assert len(entry_frame) <= 4096 and decode_control_frame(entry_frame).command == entry_control
    latest_control = ModelTestControl(op="entry_model_test", action="read", entry_id=identity)
    latest_frame = (
        ControlRequest(version=1, capability="a" * 64, command=latest_control)
        .model_dump_json()
        .encode()
        + b"\n"
    )
    assert len(latest_control.model_dump_json().encode()) == 324 and len(latest_frame) == 429
    assert decode_control_frame(latest_frame).command == latest_control
    for field, value in (
        ("operation_id", identity),
        ("command_id", identity),
        ("consent", True),
        ("expected_entry_revision", maximum),
        ("catalog_command_id", identity),
    ):
        invalid = {"op": "entry_model_test", "action": "read", "entry_id": identity, field: value}
        with pytest.raises(ValueError):
            decode_control_frame(
                json.dumps({"version": 1, "capability": "a" * 64, "command": invalid}).encode()
                + b"\n"
            )
    with pytest.raises(ValueError):
        decode_control_frame(latest_frame[:-1] + b" " * 4096 + b"\n")
    tested = EntryTestView(
        operation_id=identity,
        state="NEEDS_RECONCILIATION",
        state_revision=maximum,
        finish_reason="A" * 64,
        reason="A" * 64,
        requested_provider="orcarouter",
        requested_model='"\\' * 128,
        requested_output_tokens=65536,
        observed_model="\U0010ffff" * 256,
        provider_status="999",
        result_state="INCOMPLETE",
        output_state="TRUNCATED",
        response_text="\0" * 8192,
        input_tokens=9007199254740991,
        output_tokens=9007199254740991,
        reasoning_tokens=9007199254740991,
        cost_observed="\U0010ffff" * 128,
        entry_id=identity,
        entry_revision=maximum,
        connection_id=identity,
        connection_revision=maximum,
        current=False,
    )
    reply = encode_control_reply(
        {"ok": True, "entry_model_test": tested.model_dump(mode="json"), "correlation_id": identity}
    )
    assert (
        len(reply) <= 65536
        and json.loads(reply)["entry_model_test"]["response_text"] == "\0" * 8192
    )
    assert len(catalog_reply) <= 65536
    from starlette.responses import JSONResponse

    http_view = EntryTestView.model_validate(
        {**tested.model_dump(), "observed_model": "\0" * 256, "cost_observed": "\0" * 128}
    )
    http_body = JSONResponse(http_view.model_dump(mode="json")).body
    print(f"ENTRY_MAXIMUM_BYTES=http:{len(http_body)},reply:{len(reply)}")
    assert len(http_body) == 53101 and len(reply) == 55559
    for field, value in (
        ("response_text", "\0" * 8193),
        ("cost_observed", "\0" * 129),
        ("observed_model", "\U0010ffff" * 257),
        ("requested_model", "x" * 257),
        ("entry_revision", maximum + 1),
    ):
        with pytest.raises(ValueError):
            EntryTestView.model_validate({**tested.model_dump(), field: value})
    for key in ("provider_catalog", "entry_model_test", "provider_models"):
        refused = encode_control_reply({"ok": True, key: "x" * 65536, "correlation_id": identity})
        assert json.loads(refused)["error"] == "CONTROL_UNAVAILABLE"
    legacy_model = encode_control_reply(
        {
            "ok": True,
            "model_test": ModelTestView(response_text="a" * 8192).model_dump(mode="json"),
            "correlation_id": identity,
        }
    )
    legacy_native = encode_control_reply(
        {"ok": True, "native_task": "a" * 8192, "correlation_id": identity}
    )
    assert len(legacy_model) == 9021 and len(legacy_native) == 8282
    legacy = encode_control_reply(
        {"ok": True, "model_test": "x" * 65536, "correlation_id": identity}
    )
    assert json.loads(legacy)["ok"] is True  # No global clamp or changed legacy writer contract.
    oversized = frame[:-1] + b" " * 4096 + b"\n"
    with pytest.raises(ValueError):
        decode_control_frame(oversized)
    print(
        json.dumps(
            {
                "legacy_model_reply": len(legacy_model),
                "legacy_native_reply": len(legacy_native),
                "catalog_command": len(control.model_dump_json().encode()),
                "catalog_frame": len(frame),
                "catalog_escaped_frame": len(escaped_frame),
                "catalog_reply": len(catalog_reply),
                "entry_body": len(entry.model_dump_json().encode()),
                "entry_frame": len(entry_frame),
                "entry_reply": len(reply),
                "entry_http": len(http_body),
                "latest_entry_command": len(latest_control.model_dump_json().encode()),
                "latest_entry_frame": len(latest_frame),
            }
        )
    )
