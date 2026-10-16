"""SOURCE: finite native config projection and exact private request mapping."""

from pathlib import Path

import pytest


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
        port: int, token: str, method: str, path: str, payload: dict[str, object] | None = None
    ) -> object:
        requests.append((method, path, payload))
        if method == "PUT":
            return {"ok": True}
        return None if missing else selected

    monkeypatch.setattr(management_http, "request", request)
    assert await management_http.configure(1, "synthetic", "save", selected) == selected
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
        await management_http.configure(1, "synthetic", "save", selected)
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
