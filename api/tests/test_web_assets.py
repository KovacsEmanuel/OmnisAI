"""Serve only a manifest-bound build, never arbitrary files from the release root."""

import hashlib
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from omnis.api import create_app

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def web_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    files = {
        "index.html": b'<!doctype html><script type="module" src="/assets/app-test.js"></script>',
        "assets/app-test.js": b'console.info("synthetic build fixture");',
    }
    for name, content in files.items():
        (root / name).write_bytes(content)
    (root / "omnis-web.json").write_text(
        json.dumps(
            {"version": 1, "files": {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}}
        )
    )
    monkeypatch.setenv("OMNIS_WEB_ROOT", str(root))
    return root


@pytest.mark.asyncio
async def test_serves_manifest_bound_assets_with_same_origin_boundary(web_build: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN) as client:
        index = await client.get("/")
        assert index.status_code == 200
        assert index.content == (web_build / "index.html").read_bytes()
        assert "default-src 'none'" in index.headers["content-security-policy"]
        assert "script-src 'self'" in index.headers["content-security-policy"]
        assert index.headers["cache-control"] == "no-store"
        assert index.headers["referrer-policy"] == "no-referrer"
        script = await client.get("/assets/app-test.js")
        assert script.status_code == 200 and "javascript" in script.headers["content-type"]
        assert (await client.get("/", headers={"host": "attacker.invalid"})).status_code == 400
        assert (await client.get("/", headers={"origin": "null"})).status_code == 403
        assert (await client.get("/api/session")).status_code == 401


@pytest.mark.parametrize("failure", ["missing", "changed", "symlink", "unlisted"])
@pytest.mark.asyncio
async def test_invalid_or_unlisted_asset_is_not_served(web_build: Path, failure: str) -> None:
    asset = web_build / "assets/app-test.js"
    if failure == "missing":
        asset.unlink()
    elif failure == "changed":
        asset.write_text("synthetic-untrusted-marker")
    elif failure == "symlink":
        outside = web_build.parent / "outside.js"
        outside.write_bytes(asset.read_bytes())
        asset.unlink()
        asset.symlink_to(outside)
    else:
        asset = web_build / "assets/unlisted.js"
        asset.write_text("synthetic-untrusted-marker")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN) as client:
        response = await client.get(f"/assets/{asset.name}")
        assert response.status_code in {404, 503}
        assert "synthetic-untrusted-marker" not in response.text
        if failure != "unlisted":
            assert (await client.get("/")).status_code == 503
        for path in ("/omnis-web.json", "/.env", "/documents/Omnis_UI_Prototype.html", "/unknown"):
            assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_absent_build_is_explicitly_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMNIS_WEB_ROOT", raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN) as client:
        response = await client.get("/")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "WEB_UNAVAILABLE"
