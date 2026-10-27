"""SL04 installed stop/start proof on a fresh, owned P0 fixture only."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from installed_pair_open import http_request, run_browser, tty_pair
from installed_start import (
    assert_resources_absent,
    resource_snapshot,
    save_probe,
    teardown,
)
from omnis_cli.control import request
from omnis_cli.development import selection, validate_new
from omnis_cli.health import http_probe
from omnis_cli.lifecycle import lifecycle_lock
from omnis_cli.start_runtime import ControlRuntime


def _lock_effect_snapshot(runtime, root, control, port, record):
    """Read the Stop lock boundary, including effects outside container state."""
    network_id = runtime.network(
        {cid for role, cid in record["containers"].items() if role != "runtime"}
    )
    assert network_id is not None
    network = runtime.inspect("network", network_id)
    assert network is not None and network["Id"] == network_id
    return {
        "containers": resource_snapshot(runtime, root, control, port),
        "network_id": network_id,
        "network": network,
        "control": request(control, {"op": "status"}),
        "db_barrier": runtime.psql(
            record["containers"]["db"],
            "SELECT instance_id, admission_open, shutdown_command_id, generation, "
            "quiesced_generation, quiesced_at FROM instance_control WHERE id = 1",
        ),
        "stop_receipts": sorted(path.name for path in root.glob("stop-*.json")),
        "unreconciled": os.path.lexists(root / "unreconciled.json"),
    }


def development_preflight(options):
    """No daemon/config effects; fail before creating the existing disposable fixture."""
    if not isinstance(options, dict) or set(options) != {"workspace", "node", "browser"}:
        raise ValueError("DEVELOPMENT_PROBE_INPUTS")
    browser = options["browser"]
    if not isinstance(browser, dict) or set(browser) != {"node", "cache", "playwright"}:
        raise ValueError("DEVELOPMENT_PROBE_INPUTS")
    for value in (options["workspace"], options["node"], *browser.values()):
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).exists():
            raise ValueError("DEVELOPMENT_PROBE_INPUTS")
    source = Path(options["workspace"])
    if source.resolve() != source or browser["node"] != options["node"]:
        raise ValueError("DEVELOPMENT_PROBE_INPUTS")
    for name in (
        "web/node_modules/vite/bin/vite.js",
        "web/index.html",
        "web/vite.config.ts",
        "web/scripts/build-manifest.mjs",
        "api/src/omnis/__init__.py",
    ):
        if not (source / name).is_file():
            raise ValueError("DEVELOPMENT_PROBE_INPUTS")
    validate_new(str(source))


def run_installed_stop(data, receipt, cli, *, settings_browser=None, development=None):
    """Opt-in finite Settings visits share this fixture and its normal Stop owner."""
    if development is not None:
        development_preflight(development)
        if settings_browser is not None or receipt.get("profile") != "t1-provider-settings":
            raise ValueError("DEVELOPMENT_PROBE_PROFILE")
    if settings_browser is not None:
        assert set(settings_browser) == {"node", "cache", "playwright"}
        assert all(
            Path(value).is_absolute() and Path(value).exists()
            for value in settings_browser.values()
        )
    state = Path(tempfile.mkdtemp(prefix="s4-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    cwd = state / "cwd"
    cwd.mkdir(mode=0o700)
    (cwd / "compose.yaml").write_text("foreign: ignored\n")
    config_home = state / "config"
    config_dir = config_home / "omnis"
    config_dir.mkdir(parents=True, mode=0o700)
    config_home.chmod(0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    config = config_dir / "config.toml"
    config.write_text(f"port = {port}\n")
    config.chmod(0o600)
    runtime = ControlRuntime(data, time.monotonic() + 30)
    assert runtime.receipt.image_id == receipt["image_id"]
    record = {}
    before = None
    before_journal = None
    proof = cleanup = False
    lock_probe_pending = False
    driver_pending = False
    provider_identity = None
    save_probe(
        state,
        data,
        receipt["project"],
        root,
        record,
        probe="PREPARED",
        cleanup="NOT_RUN",
    )

    def require_observer_settled():
        if (settings_browser is not None or development is not None) and (
            runtime.uncertain or not runtime.family_drained
        ):
            raise RuntimeError("Installed observer family unsettled")

    def command(*args, expected=0, timeout=330):
        nonlocal driver_pending
        require_observer_settled()
        prior_pending = driver_pending
        driver_pending = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PENDING",
            cleanup="UNCERTAIN",
        )
        result = subprocess.run(
            [cli, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode not in {0, 2, 3, 4}:
            raise RuntimeError("Unknown installed CLI child outcome")
        driver_pending = prior_pending
        assert result.returncode == expected, f"Installed {args[0]} exit {result.returncode}"
        assert "Traceback" not in result.stderr
        return json.loads(result.stdout)

    def settings_visit(mode):
        nonlocal driver_pending, provider_identity
        if settings_browser is None:
            return
        if receipt.get("profile") == "p4a-codex-auth":
            mode = "settings-auth" if mode == "settings-save" else "settings-auth-readback"
        require_observer_settled()
        assert runtime.native, "Settings requires the sealed native installation"
        identity = record["provider_identity"]
        if provider_identity is None:
            provider_identity = identity
        assert identity == provider_identity, "Provider directory replaced across restart"
        captures = state / "screens"
        captures.mkdir(mode=0o700, exist_ok=True)
        manifest = (runtime.release / "web/omnis-web.json").read_bytes().decode("utf-8")
        driver_pending = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PENDING",
            cleanup="UNCERTAIN",
        )
        code = tty_pair(cli, cwd, env)

        def joined():
            nonlocal driver_pending
            driver_pending = False

        run_browser(
            code,
            cwd,
            env,
            f"http://127.0.0.1:{port}",
            record["instance_id"],
            mode=mode,
            manifest=manifest,
            captures=captures,
            browser=settings_browser,
            on_joined=joined,
        )

    workspace = state / "development"
    package = workspace / "api/src/omnis/__init__.py"
    original_package = ""

    def build_development(marker):
        nonlocal driver_pending
        assert development is not None
        source = Path(development["workspace"])
        index = (source / "web/index.html").read_text()
        assert "</head>" in index
        (workspace / "web/index.html").write_text(
            index.replace(
                "</head>", f'<meta name="omnis-development-probe" content="{marker}"></head>'
            )
        )
        build_env = {
            "PATH": str(Path(development["node"]).parent) + ":/usr/bin:/bin",
            "HOME": str(state),
            "TMPDIR": str(state),
            "NODE_ENV": "production",
        }
        for script, args in (
            (source / "web/node_modules/vite/bin/vite.js", ["build"]),
            (workspace / "web/scripts/build-manifest.mjs", []),
        ):
            driver_pending = True
            result = subprocess.run(
                [development["node"], str(script), *args],
                cwd=workspace / "web",
                env=build_env,
                capture_output=True,
                timeout=90,
            )
            if result.returncode not in {0, 1}:
                raise RuntimeError("Development build observer unsettled")
            driver_pending = False
            assert result.returncode == 0, "Isolated Vite build failed"
        validate_new(str(workspace))

    def wait_port():
        until = time.monotonic() + 70
        while True:
            with socket.socket() as candidate:
                try:
                    candidate.bind(("127.0.0.1", port))
                    return
                except OSError:
                    if time.monotonic() >= until:
                        raise AssertionError("Owned listener did not release its port") from None
            time.sleep(0.2)

    def source_proof(marker):
        runtime.deadline = time.monotonic() + 30
        for role in ("api", "supervisor"):
            cid = record["containers"][role]
            runtime.attest(cid, role, root, control, port)
            assert f"OMNIS_DEV_SOURCE_{marker}" in runtime.run("logs", cid).stdout
            result = runtime.run(
                "exec",
                cid,
                "python",
                "-I",
                "-c",
                "import omnis; print(omnis.__file__); print(omnis.__omnis_development_probe__)",
            ).stdout
            assert result.splitlines()[-2:] == [
                "/usr/local/lib/python3.13/site-packages/omnis/__init__.py",
                marker,
            ]
        require_observer_settled()

    try:
        started = command("start", "--no-open", "--json")
        assert started["state"] == "READY" and started["assessment_ready"] is False
        assert started["origin"] == f"http://127.0.0.1:{port}"
        record = json.loads((root / "startup.json").read_text())
        assert record["port"] == port
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 30
        before = resource_snapshot(runtime, root, control, port)
        require_observer_settled()
        before_journal = (root / "startup.json").read_bytes()
        before_instance = (root / "instance.json").read_bytes()
        original_config = config.read_bytes()
        conflict_port = port + 1 if port < 65535 else port - 1
        try:
            config.write_text(f"port = {conflict_port}\n")
            conflicting = command("start", "--no-open", "--json", expected=2)
            assert conflicting["reason"] == "CONFIG_PORT_CONFLICT"
            assert (root / "startup.json").read_bytes() == before_journal
            assert (root / "instance.json").read_bytes() == before_instance
            assert resource_snapshot(runtime, root, control, port) == before
            require_observer_settled()
        finally:
            config.write_bytes(original_config)
            assert config.read_bytes() == original_config
        initial = request(control, {"op": "status"})
        assert initial["admission_open"] is True and initial["generation"] == 1
        db = record["containers"]["db"]
        runtime.psql(db, "CREATE TABLE sl04_sentinel (value integer NOT NULL)")
        require_observer_settled()
        runtime.psql(db, "INSERT INTO sl04_sentinel VALUES (7)")
        require_observer_settled()

        runtime.deadline = time.monotonic() + 30
        before_lock = _lock_effect_snapshot(runtime, root, control, port, record)
        require_observer_settled()
        assert before_lock["control"]["admission_open"] is True
        assert not before_lock["stop_receipts"] and not before_lock["unreconciled"]
        original_config = config.read_bytes()
        try:
            config.write_text(f"port = {port}\nshutdown_timeout_seconds = 15\n")
            began = time.monotonic()
            with lifecycle_lock(data / "omnis", began + 30):
                lock_probe_pending = True
                refused = command("stop", "--json", expected=2, timeout=25)
            elapsed = time.monotonic() - began
            assert refused["reason"] == "LIFECYCLE_BUSY" and not refused["dashboard_ready"]
            assert 14 <= elapsed < 22, "Configured Stop lock deadline was not measured"
            assert (root / "startup.json").read_bytes() == before_journal
            assert (root / "instance.json").read_bytes() == before_instance
            runtime.deadline = time.monotonic() + 30
            assert _lock_effect_snapshot(runtime, root, control, port, record) == before_lock
            require_observer_settled()
        finally:
            config.write_bytes(original_config)
            assert config.read_bytes() == original_config
        lock_probe_pending = False
        print(
            f"INSTALLED_STOP_LOCK_EXPIRY project={receipt['project']} exit=2 elapsed={elapsed:.3f}s shutdown_budget=15s effects=none",
            flush=True,
        )

        settings_visit("settings-save")
        require_observer_settled()
        driver_pending = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PENDING",
            cleanup="UNCERTAIN",
        )
        stopper = subprocess.Popen(
            [cli, "stop", "--json"],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            until = time.monotonic() + 40
            while time.monotonic() < until:
                if json.loads((root / "startup.json").read_text())["phase"] == "STOPPING":
                    break
                assert stopper.poll() is None, "Stop finished before durable intent was observed"
                time.sleep(0.005)
            else:
                raise AssertionError("Installed Stop did not publish STOPPING")
            stopping_status = subprocess.run(
                [cli, "status", "--json"],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=50,
            )
            queued = subprocess.run(
                [cli, "start", "--no-open", "--json"],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=220,
            )
            stop_out, stop_err = stopper.communicate(timeout=220)
            if all(
                code in {0, 2, 3, 4}
                for code in (
                    stopper.returncode,
                    queued.returncode,
                    stopping_status.returncode,
                )
            ):
                driver_pending = False
            assert stopper.returncode == 0 and "Traceback" not in stop_err
            stopped = json.loads(stop_out)
            assert queued.returncode == 4, "Start queued behind Stop must not become restart"
            assert json.loads(queued.stdout)["reason"] == "INSTANCE_SHUTTING_DOWN"
            assert stopping_status.returncode == 4
            stopping_view = json.loads(stopping_status.stdout)
            assert (stopping_view["state"], stopping_view["reason"]) in {
                ("STOP_REQUESTED", "STOP_BARRIER_UNCONFIRMED"),
                ("STOPPING", "INSTANCE_SHUTTING_DOWN"),
            }
            assert "admission_open" not in stopping_view and not stopping_view["dashboard_ready"]
        finally:
            stop_primary = sys.exception()
            try:
                if stopper.poll() is None:
                    stopper.terminate()  # Only this direct, still-live test child.
                    stopper.wait(timeout=30)
            except BaseException:
                if stop_primary is None:
                    raise
        assert stopped["state"] == "STOPPED"
        assert stopped["dashboard_ready"] is False and stopped["assessment_ready"] is False
        record = json.loads((root / "startup.json").read_text())
        assert record["phase"] == "STOPPED"
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        require_observer_settled()
        assert (root / "postgres").is_dir() and (root / "db-password").is_file()
        first_receipt = (root / "startup.json").read_bytes()
        assert command("stop", "--json", timeout=50)["state"] == "STOPPED"
        assert (root / "startup.json").read_bytes() == first_receipt
        status = command("status", "--json", timeout=50)
        assert status["state"] == "STOPPED" and status["dashboard_ready"] is False

        if development is not None:
            source = Path(development["workspace"])
            shutil.copytree(
                source / "api/src/omnis",
                workspace / "api/src/omnis",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            shutil.copytree(source / "web/src", workspace / "web/src")
            (workspace / "web/scripts").mkdir()
            for name in ("package.json", "vite.config.ts", "scripts/build-manifest.mjs"):
                shutil.copyfile(source / "web" / name, workspace / "web" / name)
            (workspace / "web/node_modules").symlink_to(
                source / "web/node_modules", target_is_directory=True
            )
            original_package = package.read_text()
            package.write_text(
                original_package
                + "\n__omnis_development_probe__ = 'one'\nprint('OMNIS_DEV_SOURCE_one', flush=True)\n"
            )
            build_development("initial")
            config.write_text(
                f"port = {port}\ndevelopment_workspace = {json.dumps(str(workspace))}\n"
            )
        # SO_REUSEADDR=False may retain TIME_WAIT; never adopt a foreign listener.
        wait_port()
        restarted = command("start", "--no-open", "--json")
        assert restarted["state"] == "READY" and restarted["generation"] > initial["generation"]
        assert restarted["origin"] == started["origin"]
        assert restarted["supervisor_epoch"] > initial["supervisor_epoch"]
        assert restarted["instance_id"] == started["instance_id"]
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 30
        assert runtime.psql(record["containers"]["db"], "SELECT value FROM sl04_sentinel") == "7"
        runtime.development_workspace = selection(record)
        require_observer_settled()
        assert command("status", "--json", timeout=50)["state"] == "READY"
        settings_visit("settings-readback")
        if development is not None:
            assert restarted["mode"] == "DEVELOPMENT"
            assert (root / "instance.json").read_bytes() == before_instance
            identity_keys = (
                "release_digest",
                "image_id",
                "system_id",
                "pgdata_identity",
                "vault_identity",
                "vault_key_identity",
            )
            old = json.loads(first_receipt)
            assert all(record[key] == old[key] for key in identity_keys)
            cids = dict(record["containers"])
            source_proof("one")
            for marker in ("one", "two"):
                build_development(marker)
                assert f'content="{marker}"'.encode() in http_probe(port, "/", time.monotonic() + 5)
                assert command("status", "--json")["mode"] == "DEVELOPMENT"
                assert json.loads((root / "startup.json").read_text())["containers"] == cids
            for path, headers, expected in (
                ("/", {"Host": "attacker.invalid"}, 400),
                ("/api/session", {"Origin": "http://attacker.invalid"}, 403),
                ("/api/session", {}, 401),
                ("/assets/not-listed.js", {}, 404),
                ("/api/logout", {}, 403),
            ):
                assert (
                    http_request(
                        port,
                        path,
                        method="POST" if path == "/api/logout" else "GET",
                        headers=headers,
                    )[0]
                    == expected
                )
            driver_pending = True
            code = tty_pair(cli, cwd, env)
            status_code, headers, paired = http_request(
                port,
                "/api/pairing",
                method="POST",
                body={"code": code},
                headers={"Origin": started["origin"]},
            )
            assert status_code == 200
            cookie = headers["set-cookie"].split(";", 1)[0]
            headers = {"Origin": started["origin"], "Cookie": cookie}
            assert http_request(port, "/api/logout", method="POST", headers=headers)[0] == 403
            assert (
                http_request(
                    port,
                    "/api/logout",
                    method="POST",
                    headers={**headers, "X-CSRF-Token": json.loads(paired)["csrf_token"]},
                )[0]
                == 204
            )
            code = tty_pair(cli, cwd, env)

            def joined():
                nonlocal driver_pending
                driver_pending = False

            run_browser(
                code,
                cwd,
                env,
                started["origin"],
                started["instance_id"],
                browser=development["browser"],
                on_joined=joined,
            )
            # Syntax-valid mode drift cannot block withdrawal; mutable bytes may be invalid.
            config.write_text(f"port = {port}\n")
            assert (
                command("start", "--no-open", "--json", expected=2)["reason"]
                == "CONFIG_MODE_CONFLICT"
            )
            (workspace / "web/dist/omnis-web.json").write_text("rebuilding")
            assert command("status", "--json", expected=3)["dashboard_ready"] is False
            assert command("stop", "--json")["mode"] == "DEVELOPMENT"
            record = json.loads((root / "startup.json").read_text())
            runtime.deadline = time.monotonic() + 30
            assert_resources_absent(runtime, root, control, record)
            package.write_text(
                original_package
                + "\n__omnis_development_probe__ = 'two'\nprint('OMNIS_DEV_SOURCE_two', flush=True)\n"
            )
            build_development("two")
            config.write_text(
                f"port = {port}\ndevelopment_workspace = {json.dumps(str(workspace))}\n"
            )
            wait_port()
            assert command("start", "--no-open", "--json")["mode"] == "DEVELOPMENT"
            record = json.loads((root / "startup.json").read_text())
            runtime.attempt = record["attempt"]
            source_proof("two")
            assert record["containers"] != cids
            assert command("stop", "--json")["state"] == "STOPPED"
            config.write_text(f"port = {port}\n")
            wait_port()
            assert command("start", "--no-open", "--json")["mode"] == "RELEASE"
            record = json.loads((root / "startup.json").read_text())
            runtime.attempt = record["attempt"]
            runtime.development_workspace = None
            runtime.deadline = time.monotonic() + 30
            assert (
                runtime.psql(record["containers"]["db"], "SELECT value FROM sl04_sentinel") == "7"
            )
            assert all(record[key] == old[key] for key in identity_keys)
            assert http_probe(port, "/", runtime.deadline) == runtime.files["web/index.html"]
            assert command("status", "--json")["mode"] == "RELEASE"
        assert command("stop", "--json")["state"] == "STOPPED"
        record = json.loads((root / "startup.json").read_text())
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        require_observer_settled()
        assert (root / "postgres").is_dir()
        proof = cleanup = True
    finally:
        # An ordinary RED refusal with unchanged READY authority remains a
        # test-owned healthy instance. Only then can the existing observer
        # dismantle it; a partial Stop keeps its locator and UNCERTAIN verdict.
        # A timed-out or malformed lock probe may have an unsettled child family;
        # preserve its locator instead of retiring an apparently unchanged READY.
        primary = sys.exception()
        try:
            if (
                not cleanup
                and not driver_pending
                and not lock_probe_pending
                and (
                    (settings_browser is None and development is None)
                    or (not runtime.uncertain and runtime.family_drained)
                )
                and os.path.lexists(root / "startup.json")
            ):
                record = json.loads((root / "startup.json").read_text())
                runtime.attempt = record["attempt"]
                runtime.development_workspace = selection(record)
                runtime.deadline = time.monotonic() + 110
                if record["phase"] == "STOPPED":
                    assert_resources_absent(runtime, root, control, record)
                    require_observer_settled()
                    cleanup = True
                elif record["phase"] == "READY":
                    current = request(control, {"op": "status"})
                    if current["admission_open"] is True and current["shutdown_command_id"] is None:
                        if (
                            before_journal is not None
                            and record["attempt"] == json.loads(before_journal)["attempt"]
                        ):
                            assert (root / "startup.json").read_bytes() == before_journal
                            assert resource_snapshot(runtime, root, control, port) == before
                            require_observer_settled()
                        if settings_browser is not None or development is not None:
                            # Reuse product cgroup/Engine owner, not the legacy observer teardown.
                            assert command("stop", "--json")["state"] == "STOPPED"
                            record = json.loads((root / "startup.json").read_text())
                            assert record["phase"] == "STOPPED"
                        else:
                            teardown(runtime, root, control, port, record)
                        assert_resources_absent(runtime, root, control, record)
                        require_observer_settled()
                        cleanup = True
        except BaseException:
            if primary is None:
                raise
        finally:
            try:
                # Absence does not settle the observer that performed the census.
                cleanup = (
                    cleanup
                    and not driver_pending
                    and not lock_probe_pending
                    and (
                        (settings_browser is None and development is None)
                        or (not runtime.uncertain and runtime.family_drained)
                    )
                )
                if cleanup and development is not None and workspace.exists():
                    shutil.rmtree(workspace)  # Only the retired fixture's synthetic source/build.
                save_probe(
                    state,
                    data,
                    receipt["project"],
                    root,
                    record,
                    probe="PASS" if proof and cleanup else "FAIL",
                    cleanup="VERIFIED" if cleanup else "UNCERTAIN",
                )
            except BaseException:
                if primary is None:
                    raise

    if proof and cleanup:
        print(
            f"INSTALLED_STOP_VERIFIED project={receipt['project']} restart=explicit data=retained development={development is not None}",
            flush=True,
        )


def run_emergency_stop(data, receipt, cli):
    """Unavailable own API is not a DB STOPPED receipt or permission to adopt peers."""
    state = Path(tempfile.mkdtemp(prefix="s4e-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    runtime = ControlRuntime(data, time.monotonic() + 30)
    record = {}
    proof = cleanup = False
    save_probe(
        state,
        data,
        receipt["project"],
        root,
        record,
        probe="PREPARED",
        cleanup="NOT_RUN",
    )
    try:
        started = subprocess.run(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=330,
        )
        assert started.returncode == 0
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 35
        assert set(resource_snapshot(runtime, root, control, port)) == set(
            record["containers"].values()
        )
        api = record["containers"]["api"]
        runtime.attest(api, "api", root, control, port)
        runtime.run("container", "stop", "--time", "15", api, cap=25, effect=True)
        assert runtime.attest(api, "api", root, control, port)["State"]["Running"] is False
        stopped = subprocess.run(
            [cli, "stop", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=220,
        )
        assert stopped.returncode == 4, f"Emergency must be UNCERTAIN, got {stopped.returncode}"
        result = json.loads(stopped.stdout)
        assert result["state"] == "UNCERTAIN" and result["dashboard_ready"] is False
        marker = root / "unreconciled.json"
        assert marker.is_file(), "Emergency took no durable unreconciled marker"
        receipt_bytes = marker.read_bytes()
        evidence = json.loads(receipt_bytes)
        assert evidence["instance_id"] == record["instance_id"]
        assert evidence["attempt"] == record["attempt"]
        assert evidence["project"] == receipt["project"]
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        refused = subprocess.run(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=50,
        )
        assert refused.returncode == 4 and json.loads(refused.stdout)["state"] == "UNCERTAIN"
        assert marker.read_bytes() == receipt_bytes, "Retry erased unreconciled intent"
        status = subprocess.run(
            [cli, "status", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=50,
        )
        assert status.returncode == 4
        assert json.loads(status.stdout)["state"] == "RECOVERY_REQUIRED"
        assert (root / "postgres").is_dir()
        proof = cleanup = True
    finally:
        if not cleanup and os.path.lexists(root / "startup.json"):
            record = json.loads((root / "startup.json").read_text())
            runtime.attempt = record["attempt"]
            runtime.deadline = time.monotonic() + 110
            if runtime.ids():
                # Observer-only rescue of this exact fresh fixture is not proof
                # of the emergency implementation; its probe remains FAIL.
                teardown(runtime, root, control, port, record)
            assert_resources_absent(runtime, root, control, record)
            cleanup = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PASS" if proof else "FAIL",
            cleanup="VERIFIED" if cleanup else "UNCERTAIN",
        )
    if proof and cleanup:
        print(f"INSTALLED_EMERGENCY_UNCERTAIN project={receipt['project']} marker=retained")
