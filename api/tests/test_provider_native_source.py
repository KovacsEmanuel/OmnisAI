"""SOURCE: finite native config projection and exact private request mapping."""

import importlib
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

EXPECTED = {
    "model": {"provider": "openai-codex", "default": "gpt-6.1-sol"},
    "agent": {"reasoning_effort": "xhigh", "reasoning_overrides": {"gpt-6.1-sol": "xhigh"}},
    "auth": {"adopt_external_logins": False},
}


@pytest.mark.parametrize("state", ["ABSENT", "LOCAL_PRESENT", "LOCAL_EXPIRED", "LOCAL_UNKNOWN"])
def test_native_local_auth_projection_and_logout_readback(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from omnis_hermes import management_server

    assert hasattr(management_server, "auth_operation"), "native auth consumer missing"
    calls: list[str] = []
    cleared = False

    class MissingAuth(Exception):
        code = "codex_auth_missing"

    def resolve(*, read_only: bool) -> dict[str, object]:
        assert read_only is True
        calls.append("read")
        if cleared or state == "ABSENT":
            raise MissingAuth("synthetic-private-error-must-not-escape")
        return {"api_key": "synthetic-private-token-must-not-escape"}

    def clear(provider: str) -> bool:
        nonlocal cleared
        assert provider == "openai-codex"
        calls.append("clear")
        cleared = True
        return True

    native = SimpleNamespace(resolve_codex_runtime_credentials=resolve, clear_provider_auth=clear)
    constants = SimpleNamespace(
        _decode_jwt_claims=lambda _: {
            "exp": 1
            if state == "LOCAL_EXPIRED"
            else 9999999999
            if state == "LOCAL_PRESENT"
            else None
        }
    )
    config = SimpleNamespace(
        require_readable_config_before_write=lambda: deepcopy(EXPECTED),
        save_config=lambda *a, **k: None,
    )
    real_import = importlib.import_module
    modules = {
        "hermes_cli.auth": native,
        "hermes_cli.auth_constants": constants,
        "hermes_cli.config": config,
    }
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: modules[name] if name in modules else real_import(name),
    )
    monkeypatch.setenv("HERMES_OMNIS_MANAGEMENT", "1")
    monkeypatch.setenv("HERMES_HOME", "/state/provider")
    monkeypatch.setenv("HOME", "/state/provider/os-home")
    monkeypatch.setenv("CODEX_HOME", "/state/provider/codex")
    result = management_server.auth_operation("GET")
    assert result == {
        "selection": {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"},
        "authenticated": state,
    }
    assert calls == ["read"]
    result = management_server.auth_operation("DELETE")
    assert result["authenticated"] == "ABSENT"
    assert calls == ["read", "clear", "read"]
    monkeypatch.setenv("HERMES_HOME", "/foreign")
    with pytest.raises(ValueError):
        management_server.auth_operation("DELETE")
    assert calls == ["read", "clear", "read"]


@pytest.mark.parametrize(
    "section,key,value",
    [
        (None, "fallback_model", {"provider": "openrouter"}),
        (None, "providers", {"openai-codex": {"base_url": "https://synthetic.invalid"}}),
        (None, "delegation", {"provider": "openrouter"}),
        (None, "auxiliary", {"vision": {"provider": "openrouter"}}),
        ("agent", "extra", "foreign"),
        ("auth", "extra", "foreign"),
        ("auth", "adopt_external_logins", 0),
        ("agent", "reasoning_overrides", {"gpt-6.1-sol": "xhigh", "other": "low"}),
        (None, "_config_version", True),
        (None, "_config_version", 1.0),
        (None, "_config_version", 1),
    ],
)
def test_complete_native_config_refused_before_writer(
    monkeypatch: pytest.MonkeyPatch, section: str | None, key: str, value: object
) -> None:
    from omnis_hermes import management_server
    from omnis_hermes.management_contract import SELECTION

    stored: dict[str, object] = deepcopy(EXPECTED)
    writes = 0

    def read() -> dict[str, object]:
        return deepcopy(stored)

    def save(config: dict[str, object], *, strip_defaults: bool, merge_existing: bool) -> None:
        nonlocal writes
        assert strip_defaults is False and merge_existing is True
        writes += 1
        stored.update(deepcopy(config))

    native = SimpleNamespace(require_readable_config_before_write=read, save_config=save)
    real_import = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: native if name == "hermes_cli.config" else real_import(name),
    )
    assert management_server.config_operation("GET", None) == SELECTION
    assert management_server.config_operation("PUT", {"config": EXPECTED}) == {"ok": True}
    assert writes == 1
    target = stored if section is None else stored[section]
    assert isinstance(target, dict)
    target[key] = value
    before = deepcopy(stored)
    for method in ("GET", "PUT"):
        with pytest.raises(ValueError):
            management_server.config_operation(method, {"config": EXPECTED})
    assert stored == before and writes == 1
    stored.clear()
    assert management_server.config_operation("GET", None) is None
    assert management_server.config_operation("PUT", {"config": EXPECTED}) == {"ok": True}
    assert management_server.config_operation("GET", None) == SELECTION
    assert writes == 2
    stored.clear()
    monkeypatch.setattr(native, "save_config", lambda *a, **k: None)
    with pytest.raises(ValueError, match="readback mismatch"):
        management_server.config_operation("PUT", {"config": EXPECTED})


@pytest.mark.asyncio
@pytest.mark.parametrize("ack", [{"ok": 1}, {"ok": 1.0}, {"ok": True, "extra": False}])
async def test_native_ack_requires_exact_true(monkeypatch: pytest.MonkeyPatch, ack: object) -> None:
    from omnis_hermes import management_http
    from omnis_hermes.management_contract import SELECTION

    reply: object = {"ok": True}
    reads = 0

    async def request(
        port: int,
        token: str,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        dispatch_guard: Callable[[], None],
    ) -> object:
        nonlocal reads
        dispatch_guard()
        if method == "PUT":
            return reply
        reads += 1
        return dict(SELECTION)

    monkeypatch.setattr(management_http, "request", request)
    assert (
        await management_http.configure(
            1, "synthetic", "save", SELECTION, dispatch_guard=lambda: None
        )
        == SELECTION
    )
    assert reads == 1
    reply = ack
    with pytest.raises(ValueError, match="Unconfirmed native save"):
        await management_http.configure(
            1, "synthetic", "save", SELECTION, dispatch_guard=lambda: None
        )
    assert reads == 1


@pytest.mark.asyncio
async def test_native_request_is_allowlisted_and_readback_not_http_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes import management_http

    selected = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
    requests: list[tuple[str, str, object]] = []
    missing = False

    async def request(
        port: int,
        token: str,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        dispatch_guard: Callable[[], None],
    ) -> object:
        dispatch_guard()
        requests.append((method, path, payload))
        if method == "PUT":
            return {"ok": True}
        return None if missing else selected

    monkeypatch.setattr(management_http, "request", request)
    assert (
        await management_http.configure(
            1, "synthetic", "save", selected, dispatch_guard=lambda: None
        )
        == selected
    )
    assert requests == [
        (
            "PUT",
            "/api/config",
            {
                "config": {
                    "model": {"provider": "openai-codex", "default": "gpt-6.1-sol"},
                    "agent": {
                        "reasoning_effort": "xhigh",
                        "reasoning_overrides": {"gpt-6.1-sol": "xhigh"},
                    },
                    "auth": {"adopt_external_logins": False},
                }
            },
        ),
        ("GET", "/api/config?include_defaults=false", None),
    ]
    missing = True
    with pytest.raises(ValueError, match="readback mismatch"):
        await management_http.configure(
            1, "synthetic", "save", selected, dispatch_guard=lambda: None
        )
    assert len(requests) == 4  # No retry after an acknowledged write with missing readback.


def test_native_saved_projection_refuses_ambient_auth_without_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes.management_server import saved_selection

    assert saved_selection({}) is None
    with pytest.raises(ValueError):
        saved_selection({"auth": {"adopt_external_logins": True}})
    with pytest.raises(ValueError):
        saved_selection(
            {
                "model": {
                    "provider": "openai-codex",
                    "default": "gpt-6.1-sol",
                    "api_key": "synthetic-never-return",
                }
            }
        )
