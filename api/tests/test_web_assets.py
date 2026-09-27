"""Serve only a manifest-bound build, never arbitrary files from the release root."""

import asyncio
import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import URL

from conftest import connect_test_database
from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.core.web_assets import WebAssets
from omnis.modules.instance.domain import InstanceStatus
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import SessionStore, code_digest
from omnis.transport.local_control import LocalControl

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def web_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    files = {
        "index.html": b'<!doctype html><script type="module" src="/assets/app-test.js"></script>',
        "assets/app-test.js": b'console.info("synthetic build fixture");',
        "assets/fonts-OFL-test.txt": b"Synthetic license fixture",
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
        license_response = await client.get("/assets/fonts-OFL-test.txt")
        assert license_response.status_code == 200
        assert license_response.headers["content-type"].startswith("text/plain")
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


@pytest.mark.asyncio
async def test_dashboard_requires_assets_schema_and_live_private_control(
    web_build: Path,
    migrated_database_url: URL,
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = migrated_database_url.render_as_string(hide_password=False)
    monkeypatch.setenv("OMNIS_DATABASE_URL", url)
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(ipc_directory))
    engine = database_engine(url)
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    app = create_app()
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                # A live lease is NOT a working control socket.
                before = (await client.get("/health/ready")).json()
                assert before["api_ready"] and not before["dashboard_ready"]
                assert before["dashboard_reason"] == "CONTROL_UNAVAILABLE"
                async with LocalControl(ipc_directory, service, owner, epoch):
                    healthy = (await client.get("/health/ready")).json()
                    assert healthy["dashboard_ready"] is True
                    assert healthy["dashboard_reason"] is None
                    assert healthy["assessment_ready"] is False
                    store = SessionStore(engine)
                    await store.register(
                        code_digest("synthetic-p03-pairing-code"), issuance_id=uuid4()
                    )
                    await client.post(
                        "/api/pairing",
                        json={"code": "synthetic-p03-pairing-code"},
                        headers={"origin": ORIGIN},
                    )
                    view = (await client.get("/api/instance")).json()
                    assert view["dashboard_ready"] and not view["assessment_ready"]
                    assert not view["admission_open"]
                    (web_build / "assets/app-test.js").unlink()
                    degraded = (await client.get("/health/ready")).json()
                    assert degraded["api_ready"] and not degraded["dashboard_ready"]
                    assert degraded["dashboard_reason"] == "ASSETS_UNAVAILABLE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_reads_neither_extend_nor_resurrect_supervisor_lease(
    web_build: Path,
    migrated_database_url: URL,
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = migrated_database_url.render_as_string(hide_password=False)
    monkeypatch.setenv("OMNIS_DATABASE_URL", url)
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(ipc_directory))
    engine = database_engine(url)
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    app = create_app()
    try:
        async with LocalControl(ipc_directory, service, owner, epoch):
            with connect_test_database(migrated_database_url) as db:
                db.execute(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() + interval '2 seconds'"
                )
                expiry = db.execute("SELECT expires_at FROM supervisor_lease").fetchone()
            async with app.router.lifespan_context(app):
                async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                    assert (await client.get("/health/ready")).json()["dashboard_ready"]
                    with connect_test_database(migrated_database_url) as db:
                        assert (
                            db.execute("SELECT expires_at FROM supervisor_lease").fetchone()
                            == expiry
                        )
                    # Continue read traffic across expiry without the supervisor heartbeat loop.
                    for _ in range(8):
                        await client.get("/health/ready")
                        await asyncio.sleep(0.3)
                    result = (await client.get("/health/ready")).json()
                    assert result["api_ready"] and not result["dashboard_ready"]
                    assert result["dashboard_reason"] == "CONTROL_UNAVAILABLE"
                    with connect_test_database(migrated_database_url) as db:
                        assert (
                            db.execute("SELECT expires_at FROM supervisor_lease").fetchone()
                            == expiry
                        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stalled_asset_reads_are_bounded_and_share_one_worker(
    web_build: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    started = 0
    lock = threading.Lock()
    original = WebAssets.load

    def stalled(self: WebAssets) -> dict[str, bytes] | None:
        nonlocal started
        with lock:
            started += 1
        release.wait(10)
        return original(self)

    async def database_ready(engine: object) -> None:
        return None

    async def status(self: InstanceService) -> InstanceStatus:
        return InstanceStatus(uuid4(), 0, False, None, None, 1, True, False)

    monkeypatch.setattr(WebAssets, "load", stalled)
    monkeypatch.setattr("omnis.api.readiness_reason", database_ready)
    monkeypatch.setattr(InstanceService, "status", status)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
        try:
            for _ in range(2):
                try:
                    responses = await asyncio.wait_for(
                        asyncio.gather(
                            client.get("/"),
                            client.get("/health/ready"),
                            client.get("/assets/app-test.js"),
                        ),
                        timeout=1.7,
                    )
                except TimeoutError:
                    pytest.fail("Asset I/O outlived its response deadline")
                assert [r.status_code for r in responses] == [503, 200, 503]
                assert responses[1].json()["api_ready"] is True
                assert responses[1].json()["dashboard_reason"] == "ASSETS_UNAVAILABLE"
            assert started == 1, "Timed-out requests must not accumulate filesystem workers"
        finally:
            release.set()
        await asyncio.sleep(0.1)
        assert (await client.get("/")).status_code == 200


def test_stalled_asset_worker_does_not_hold_interpreter_exit() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """
import asyncio
import threading
from omnis.core.web_assets import WebAssets
class Stalled(WebAssets):
    def load(self):
        threading.Event().wait()
assets = Stalled(None)
assert asyncio.run(assets.read()) is None
print('BOUNDED_EXIT')
""",
        ],
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0 and result.stdout.strip() == "BOUNDED_EXIT"


@pytest.mark.asyncio
async def test_cancelled_asset_waiter_does_not_cancel_or_duplicate_worker(
    web_build: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets = WebAssets(str(web_build))
    release = threading.Event()
    started = threading.Event()
    original = WebAssets.load
    calls = 0

    def stalled(self: WebAssets) -> dict[str, bytes] | None:
        nonlocal calls
        calls += 1
        started.set()
        release.wait(5)
        return original(self)

    monkeypatch.setattr(WebAssets, "load", stalled)
    waiter = asyncio.create_task(assets.read())
    try:
        assert await asyncio.to_thread(started.wait, 1)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert await assets.read() is None
        assert calls == 1
    finally:
        release.set()
