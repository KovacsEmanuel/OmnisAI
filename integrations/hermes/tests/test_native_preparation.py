"""Source-unit contract/lifecycle seams, never installed native-loader evidence."""

import base64
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

import pytest
from omnis_hermes.runtime_host import RuntimeHost

LIMITS = {
    "max_packages": 2,
    "max_files": 16,
    "max_file_bytes": 8192,
    "max_total_raw_bytes": 16384,
    "max_bundle_envelope_bytes": 32768,
    "max_runtime_request_bytes": 49152,
    "max_worker_result_bytes": 32768,
    "max_runtime_response_bytes": 65536,
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def ref(kind):
    return {"kind": kind, "id": str(uuid4()), "revision": 1, "digest": "a" * 64}


def bundle():
    files = {
        "SKILL.md": b"---\nname: inert-probe\ndescription: Inert probe.\nversion: 0.1.0\nprovenance: Synthetic.\n---\nLiteral $(false) only.\n",
        "omnis.yaml": b"schema_version: 1\n",
    }
    envelope = {
        "schema_version": 1,
        "kind": "native-preparation-bundle",
        "id": str(uuid4()),
        "revision": 1,
        "payload": {
            "protocol": "omnis-native-preparation-v1",
            "owner_id": str(uuid4()),
            "selection_ref": ref("execution-selection"),
            "snapshot_ref": ref("run-snapshot"),
            "publication_ref": ref("catalog-publication"),
            "candidate_snapshot_ref": ref("candidate-snapshot"),
            "recipe_key": "inert-probe",
            "material_digest": "b" * 64,
            "resolved_index_digest": "c" * 64,
            "resolution": "NO_MODEL",
            "effective": None,
            "preprocess": False,
            "limits": LIMITS.copy(),
            "packages": [
                {
                    "package_ref": ref("package"),
                    "package_key": "inert-probe",
                    "native_name": "inert-probe",
                    "files": [
                        {
                            "path": name,
                            "size": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "content_b64": base64.b64encode(raw).decode(),
                        }
                        for name, raw in sorted(files.items())
                    ],
                }
            ],
        },
    }
    return seal(envelope)


def seal(envelope):
    envelope.pop("digest", None)
    envelope["digest"] = hashlib.sha256(canonical(envelope)).hexdigest()
    return {
        "bundle_ref": {key: envelope[key] for key in ("kind", "id", "revision", "digest")},
        "bundle": envelope,
    }


def body(host, payload=None):
    return {
        "version": 1,
        "id": str(uuid4()),
        "boot": host.boot,
        "capability": host.capability,
        "generation": 0,
        "epoch": 1,
        "op": "prepare",
        "deadline_ns": time.monotonic_ns() + 2_000_000_000,
        "payload": bundle() if payload is None else payload,
    }


def test_prepare_wire_admits_exact_bundle_before_spawn():
    host = RuntimeHost(Path("/nonexistent"))
    request = body(host)
    assert host._validate(request) == request
    assert host.process is None


def test_prepare_wire_rejects_invalid_bundle_before_spawn():
    host = RuntimeHost(Path("/nonexistent"))
    with pytest.raises(ValueError, match="preparation"):
        host._validate(body(host, {"bundle_ref": {}, "bundle": {}}))
    assert host.process is None


@pytest.mark.asyncio
async def test_prepare_requires_live_ready_authority():
    host = RuntimeHost(Path("/nonexistent"))
    with pytest.raises(ValueError, match="authority"):
        await host._prepare(body(host))


def test_staging_is_exact_read_only_and_rejects_link_substitution(tmp_path):
    from omnis_hermes.native_preparation_contract import validate_payload
    from omnis_hermes.native_preparation_worker import stage, verify_tree

    _, files = validate_payload(bundle())
    skills = tmp_path / "skills"
    stage(skills, files)
    verify_tree(skills, files)
    file = skills / "inert-probe" / "SKILL.md"
    assert file.stat().st_mode & 0o777 == 0o400
    assert file.parent.stat().st_mode & 0o777 == 0o500
    file.parent.chmod(0o700)
    file.unlink()
    file.symlink_to(tmp_path / "foreign")
    with pytest.raises(ValueError):
        verify_tree(skills, files)
    file.unlink()
    file.parent.chmod(0o700)
    skills.chmod(0o700)


def test_worker_installed_guard_refuses_host_without_native_import():
    import sys

    from omnis_hermes.native_preparation_worker import isolated_root

    with pytest.raises(ValueError):
        isolated_root()
    assert "tools.skills_tool" not in sys.modules
    assert "run_agent" not in sys.modules


@pytest.mark.asyncio
async def test_owned_worker_timeout_is_joined_and_tree_removed(tmp_path):
    import asyncio
    import sys

    from omnis_hermes.runtime_host import TestLaunch, TestPreparation

    tmp_path.chmod(0o700)
    spec = TestPreparation(
        (sys.executable, "-I", "-B", "-c", "import time; time.sleep(60)"), tmp_path
    )
    host = RuntimeHost(
        tmp_path,
        _test_launch=TestLaunch(
            (sys.executable, str(Path(__file__).with_name("peer_fixture.py"))), tmp_path
        ),
        _test_preparation=spec,
    )
    try:
        await host._launch(
            {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 2_000_000_000}
        )
        request = body(host)
        request["deadline_ns"] = time.monotonic_ns() + 600_000_000
        with pytest.raises((ValueError, TimeoutError)):
            await asyncio.wait_for(host._prepare(request), 1.1)
        assert host.preparation_process is None
        assert not list(tmp_path.glob("native-prep-*"))
    finally:
        await host.stop()


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "bool_size",
        "wrong_hash",
        "bad_base64",
        "path_escape",
        "hidden",
        "nested_skill",
        "missing_skill",
        "duplicate_path",
        "metadata",
        "requirements",
        "bom",
        "cr",
        "nul",
        "invalid_utf8",
        "bool_limit",
        "oversize",
        "bad_ref",
        "preprocess",
        "effective",
        "wrong_order",
    ],
)
def test_untrusted_bundle_rejections_before_native_import(mutation):
    from omnis_hermes.native_preparation_contract import validate_payload

    payload = bundle()
    envelope = payload["bundle"]
    data = envelope["payload"]
    files = data["packages"][0]["files"]
    target = files[0]
    raw = base64.b64decode(target["content_b64"])
    if mutation == "extra":
        data["argv"] = []
    elif mutation == "bool_size":
        target["size"] = True
    elif mutation == "wrong_hash":
        target["sha256"] = "0" * 64
    elif mutation == "bad_base64":
        target["content_b64"] += "="
    elif mutation in {"path_escape", "hidden", "nested_skill"}:
        target["path"] = {
            "path_escape": "../SKILL.md",
            "hidden": ".env",
            "nested_skill": "references/SKILL.md",
        }[mutation]
    elif mutation == "missing_skill":
        files.pop(0)
    elif mutation == "duplicate_path":
        files.append(target.copy())
    elif mutation == "bool_limit":
        data["limits"]["max_packages"] = True
    elif mutation == "bad_ref":
        data["selection_ref"]["revision"] = True
    elif mutation == "preprocess":
        data["preprocess"] = True
    elif mutation == "effective":
        data["effective"] = {"model": "unauthorized"}
    elif mutation == "wrong_order":
        files.reverse()
    else:
        if mutation in {"metadata", "requirements"}:
            raw = raw.replace(b"description:", mutation.encode() + b": {}\ndescription:")
        elif mutation == "bom":
            raw = b"\xef\xbb\xbf" + raw
        elif mutation == "cr":
            raw = raw.replace(b"\n", b"\r\n")
        elif mutation == "nul":
            raw += b"\0"
        elif mutation == "invalid_utf8":
            raw += b"\xff"
        elif mutation == "oversize":
            raw += b"x" * 8192
        target.update(
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            content_b64=base64.b64encode(raw).decode(),
        )
    with pytest.raises(ValueError):
        validate_payload(seal(envelope))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":1.1}',
        b'{"x":"\\u0000"}',
        b'{"x":"\xff"}',
        b'{"x":"\\ud800"}',
    ],
)
def test_strict_json_refuses_duplicate_nan_unicode(raw):
    from omnis_hermes.native_preparation_contract import loads

    with pytest.raises(ValueError):
        loads(raw, 1000)


def test_real_retained_fixture_passes_stdlib_validation():
    from omnis_hermes.native_preparation_contract import validate_payload

    source = (
        Path(__file__).resolve().parents[3]
        / "api/tests/fixtures/b06b_publication/source/b06b-publish-contract"
    )
    envelope = bundle()["bundle"]
    package = envelope["payload"]["packages"][0]
    package["native_name"] = package["package_key"] = "b06b-publish-contract"
    package["files"] = [
        {
            "path": str(path.relative_to(source)),
            "size": len(path.read_bytes()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content_b64": base64.b64encode(path.read_bytes()).decode(),
        }
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]
    _, files = validate_payload(seal(envelope))
    assert len(files) == 10
    assert sum(len(file.raw) for file in files) == 9703


@pytest.mark.parametrize("mode", ["stop", "cancel", "eof", "watchdog", "oversize", "bad_output"])
@pytest.mark.asyncio
async def test_worker_failure_paths_join_and_remove_exact_tree(tmp_path, mode):
    import asyncio
    import sys

    from omnis_hermes.runtime_host import TestLaunch, TestPreparation

    tmp_path.chmod(0o700)
    script = "import time; time.sleep(60)"
    if mode == "oversize":
        script = "import sys; sys.stdin.buffer.read(); print('x' * 40000)"
    elif mode == "bad_output":
        script = "import sys; sys.stdin.buffer.read(); print('{}')"
    host = RuntimeHost(
        tmp_path,
        _test_launch=TestLaunch(
            (sys.executable, str(Path(__file__).with_name("peer_fixture.py"))), tmp_path
        ),
        _test_preparation=TestPreparation((sys.executable, "-I", "-B", "-c", script), tmp_path),
    )
    operation = None
    watchdog = None
    try:
        await host._launch(
            {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 4_000_000_000}
        )
        reader = asyncio.StreamReader()
        request = body(host)
        operation = asyncio.create_task(host._prepare_connected(request, reader))
        async with asyncio.timeout(1):
            while host.preparation_process is None:
                await asyncio.sleep(0.001)
        worker = host.preparation_process
        assert worker is not None
        native = host.process
        assert native is not None
        # A second worker is rejected, not queued or launched with another home.
        with pytest.raises(ValueError, match="busy"):
            await host._prepare(body(host))
        if mode == "stop":
            await host.stop()
        elif mode == "cancel":
            operation.cancel()
        elif mode == "eof":
            reader.feed_eof()
        elif mode == "watchdog":
            host.deadline_ns = time.monotonic_ns() - 1
            watchdog = asyncio.create_task(host._watch())
        with pytest.raises((ValueError, asyncio.CancelledError, OSError)):
            await asyncio.wait_for(operation, 1)
        assert worker.returncode is not None
        assert not Path(f"/proc/{worker.pid}").exists()
        assert host.preparation_process is None
        assert host.preparation_root is None
        assert not list(tmp_path.glob("native-prep-*"))
        if mode not in {"stop", "watchdog"}:
            assert native.returncode is None
    finally:
        if operation is not None and not operation.done():
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        if watchdog is not None:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
        host._remove_preparation_home()
        await host.stop()


def test_worker_native_json_is_checked_without_mocking_loader(tmp_path):
    from omnis_hermes.native_preparation_contract import validate_payload
    from omnis_hermes.native_preparation_worker import checked_native

    _, files = validate_payload(bundle())
    file = files[1]
    value = {
        "success": True,
        "name": file.native_name,
        "content": file.raw.decode(),
        "file": file.path,
        "file_type": ".yaml",
        "_source_path": str(tmp_path / file.native_name / file.path),
    }
    checked_native(json.dumps(value), file, tmp_path)  # Schema-only, no loader invoked.
    for update in (
        {"unknown": True},
        {"_source_path": "/foreign"},
        {"content": "normalized"},
        {"is_binary": True},
    ):
        with pytest.raises(ValueError):
            checked_native(json.dumps({**value, **update}), file, tmp_path)


def test_empty_support_file_and_exact_16_file_limit():
    from omnis_hermes.native_preparation_contract import validate_payload

    envelope = bundle()["bundle"]
    files = envelope["payload"]["packages"][0]["files"]
    for i in range(14):
        files.append(
            {
                "path": f"references/f{i:02}.md",
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
                "content_b64": "",
            }
        )
    files.sort(key=lambda item: item["path"])
    _, accepted = validate_payload(seal(envelope))
    assert len(accepted) == 16
    files.append(
        {
            "path": "references/z.md",
            "size": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "content_b64": "",
        }
    )
    with pytest.raises(ValueError):
        validate_payload(seal(envelope))


@pytest.mark.asyncio
async def test_cleanup_uncertainty_still_stops_native_leader(tmp_path):
    import sys

    from omnis_hermes.runtime_host import TestLaunch

    tmp_path.chmod(0o700)
    host = RuntimeHost(
        tmp_path,
        _test_launch=TestLaunch(
            (sys.executable, str(Path(__file__).with_name("peer_fixture.py"))), tmp_path
        ),
    )
    await host._launch(
        {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 2_000_000_000}
    )
    process = host.process
    assert process is not None
    try:
        host.state = "UNCERTAIN"  # Root identity refusal must not strand the native leader.
        await host.stop()
        assert process.returncode is not None
        assert host.state == "UNCERTAIN"
    finally:
        # Test owns this still-parented child even when testing the pre-fix failure.
        if process.returncode is None:
            process.kill()
        await process.wait()
        if host.peer is not None:
            await host.peer.close()


def test_fresh_environment_and_cleanup_do_not_follow_links(tmp_path, monkeypatch):
    from omnis_hermes.native_preparation_worker import PATHS
    from omnis_hermes.runtime_host import NATIVE_ENV, TestPreparation

    tmp_path.chmod(0o700)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-do-not-copy")
    host = RuntimeHost(tmp_path, _test_preparation=TestPreparation(("unused",), tmp_path))
    root, env = host._preparation_home()
    foreign = tmp_path / "foreign"
    foreign.mkdir(mode=0o500)
    try:
        assert set(env) == set(NATIVE_ENV) | set(PATHS) | {"PYTHONDONTWRITEBYTECODE"}
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        for key, relative in PATHS.items():
            assert env[key] == str(root / relative)
            assert (root / relative).is_dir()
            assert (root / relative).stat().st_mode & 0o777 == 0o700
        assert "OPENAI_API_KEY" not in env
        assert not (root / "home" / ".env").exists()
        (root / "foreign-link").symlink_to(foreign)
        host._remove_preparation_home()
        assert foreign.stat().st_mode & 0o777 == 0o500
        assert not root.exists()
    finally:
        host._remove_preparation_home()
        foreign.chmod(0o700)


def test_frontmatter_rejects_yaml_unicode_line_break_directives():
    from omnis_hermes.native_preparation_contract import frontmatter

    for separator in ("\u2028", "\u2029"):
        raw = (
            "---\nname: inert-probe\ndescription: inert"
            + separator
            + "required_environment_variables:"
            + separator
            + "  - SECRET\n---\n"
        ).encode()
        with pytest.raises(ValueError):
            frontmatter(raw, "inert-probe")


@pytest.mark.asyncio
async def test_authenticated_prepare_eof_joins_worker_and_native():
    import asyncio
    import os
    import sys
    import tempfile

    from omnis_hermes.runtime_host import TestLaunch, TestPreparation

    # Short socket path independent of pytest node/parameter IDs.
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="np-") as name:
        root = Path(name)
        host = RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py"))), root
            ),
            _test_preparation=TestPreparation(
                (sys.executable, "-I", "-B", "-c", "import time; time.sleep(60)"), root
            ),
        )
        async with host:
            reader, writer = await asyncio.open_unix_connection(str(root / "runtime.sock"))
            request = body(host)
            launch = {k: v for k, v in request.items() if k != "payload"}
            launch["op"] = "launch"
            writer.write(canonical(launch) + b"\n")
            await writer.drain()
            assert json.loads(await reader.readline())["ok"] is True
            writer.write(canonical(body(host)) + b"\n")
            await writer.drain()
            async with asyncio.timeout(1):
                while host.preparation_process is None:
                    await asyncio.sleep(0.001)
            worker, native = host.preparation_process, host.process
            writer.close()
            await writer.wait_closed()
            async with asyncio.timeout(1.5):
                while host.owner_writer is not None:
                    await asyncio.sleep(0.005)
            assert worker is not None and worker.returncode is not None
            assert native is not None and native.returncode is not None
            assert not Path(f"/proc/{worker.pid}").exists()
            assert not Path(f"/proc/{native.pid}").exists()
            assert host.preparation_root is None
            assert not list(root.glob("native-prep-*"))
            assert host.state == "UNCERTAIN"  # Source seam is not an OCI proof.


def test_crash_leftover_refused_not_adopted(tmp_path):
    from omnis_hermes.runtime_host import TestPreparation

    tmp_path.chmod(0o700)
    old = tmp_path / f"native-prep-{uuid4()}"
    old.mkdir(mode=0o700)
    marker = old / "keep"
    marker.write_bytes(b"retained evidence")
    host = RuntimeHost(tmp_path, _test_preparation=TestPreparation(("unused",), tmp_path))
    try:
        with pytest.raises(ValueError):
            host._preparation_home()
        assert marker.read_bytes() == b"retained evidence"
        assert host.preparation_root is None
    finally:
        host._remove_preparation_home()


@pytest.mark.asyncio
async def test_oversized_raw_request_is_denied_before_worker_spawn():
    import asyncio
    import os
    import sys
    import tempfile

    from omnis_hermes.runtime_host import TestLaunch, TestPreparation

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="np-") as name:
        root = Path(name)
        marker = root / "worker-started"
        script = f"from pathlib import Path; Path({str(marker)!r}).write_text('source-seam')"
        async with RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py"))), root
            ),
            _test_preparation=TestPreparation((sys.executable, "-I", "-B", "-c", script), root),
        ) as host:
            reader, writer = await asyncio.open_unix_connection(str(root / "runtime.sock"))
            try:
                launch = {k: v for k, v in body(host).items() if k != "payload"}
                launch["op"] = "launch"
                writer.write(canonical(launch) + b"\n")
                await writer.drain()
                assert json.loads(await reader.readline())["ok"] is True
                writer.write(canonical(body(host)) + b" " * 49152 + b"\n")
                await writer.drain()
                response = json.loads(await asyncio.wait_for(reader.readline(), 1))
                assert response["ok"] is False
                assert "preparation" not in response
                assert not marker.exists()
            finally:
                writer.close()
                await writer.wait_closed()


def test_worker_result_exact_bytes_provenance_and_strict_ref():
    from omnis_hermes.native_preparation_contract import (
        BASE_COMMIT,
        PATCH_SHA256,
        SKILLS_SHA256,
        validate_payload,
        validate_result,
    )

    payload = bundle()
    ref, files = validate_payload(payload)
    worker_hash = "d" * 64
    # Parser fixture only: not a fake provider, native loader, or emitter process.
    result = {
        "schema_version": 1,
        "status": "PREPARED",
        "bundle_ref": ref,
        "loader": "tools.skills_tool.skill_view",
        "preprocess": False,
        "loaded": [file.loaded() for file in files],
        "native": {
            "base_commit": BASE_COMMIT,
            "patch_sha256": PATCH_SHA256,
            "skills_tool_sha256": SKILLS_SHA256,
            "worker_revision": worker_hash,
        },
    }
    assert validate_result(result, payload, worker_hash) == result
    bad = json.loads(json.dumps(result))
    bad["bundle_ref"]["revision"] = True
    with pytest.raises(ValueError):
        validate_result(bad, payload, worker_hash)
    for updates in (
        {"unknown": 1},
        {"loaded": result["loaded"][:-1]},
        {"preprocess": True},
        {"status": "READY"},
        {"native": {**result["native"], "worker_revision": "e" * 64}},
    ):
        with pytest.raises(ValueError):
            validate_result({**result, **updates}, payload, worker_hash)


def test_exact_total_raw_byte_limit_then_next_byte_refused():
    from omnis_hermes.native_preparation_contract import validate_payload

    envelope = bundle()["bundle"]
    files = envelope["payload"]["packages"][0]["files"]
    skill_size = files[0]["size"]

    def entry(path, size):
        raw = b"x" * size
        return {
            "path": path,
            "size": size,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content_b64": base64.b64encode(raw).decode(),
        }

    files[1] = entry("omnis.yaml", 8192)
    files.append(entry("references/boundary.md", 16384 - 8192 - skill_size))
    _, accepted = validate_payload(seal(envelope))
    assert sum(len(file.raw) for file in accepted) == 16384
    files[2] = entry("references/boundary.md", 16384 - 8192 - skill_size + 1)
    with pytest.raises(ValueError):
        validate_payload(seal(envelope))
