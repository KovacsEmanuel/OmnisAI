"""SL04 installed stop/start proof on a fresh, owned P0 fixture only."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

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


def _upgrade_census_sql(table):
    if re.fullmatch(r"[a-z_0-9]+", table) is None:
        raise ValueError("Invalid census table")
    row = "to_jsonb(t)"
    if table == "provider_model_entry":
        row += " - 'removed_registry_revision'"
    return f"SELECT md5(coalesce(string_agg(({row})::text,',' ORDER BY ({row})::text),'')) FROM {table} t"


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


def upgrade_preflight(options):
    """Decode exact old/new bundle inputs without creating a fixture or daemon IO."""
    from omnis_cli.release import _manifest

    if not isinstance(options, dict) or set(options) != {"old_bundle", "bundle", "old_cli", "cli"}:
        raise ValueError("UPGRADE_PROBE_INPUTS")
    for name in options:
        path = Path(options[name])
        if not path.is_absolute() or path.resolve() != path or not path.exists():
            raise ValueError("UPGRADE_PROBE_INPUTS")
    for name, version, schema in (
        ("old_bundle", "0.1.0", "0016_provider_models"),
        ("bundle", "0.1.1", "0017_model_removal"),
    ):
        manifest = json.loads(_manifest(Path(options[name]))[0])
        if (manifest["release"], manifest["schema"], manifest.get("profile")) != (
            version,
            schema,
            "t1-provider-settings",
        ):
            raise ValueError("UPGRADE_PROBE_PROFILE")
    if not all(os.access(options[name], os.X_OK) for name in ("old_cli", "cli")):
        raise ValueError("UPGRADE_PROBE_CLI")


def run_installed_stop(
    data,
    receipt,
    cli,
    *,
    settings_browser=None,
    development=None,
    upgrade=None,
    upgrade_failure=False,
):
    """Opt-in finite Settings visits share this fixture and its normal Stop owner."""
    if upgrade is not None:
        upgrade_preflight(upgrade)
        if development is not None or settings_browser is not None:
            raise ValueError("UPGRADE_PROBE_PROFILE")
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
        census = {}
        vault_before = {}
        if upgrade is not None:
            # Synthetic disabled connection, model and role caps: never a provider request.
            connection, entry, secret, selection_id = (str(uuid4()) for _ in range(4))
            identity = record["instance_id"]
            runtime.run(
                "exec",
                record["containers"]["supervisor"],
                "python",
                "-I",
                "-c",
                "from pathlib import Path; from omnis.modules.settings.provider_vault import ProviderVault,CredentialRef; "
                + f"v=ProviderVault(Path('/vault'),Path('/vault-key'),{identity!r}); v.bootstrap(); v.put(CredentialRef({identity!r},{secret!r},1,'openrouter'),'synthetic-upgrade-key')",
                effect=True,
            )
            vault_before = {
                name: (root / name).read_bytes()
                for name in ("vault/vault.json", "vault-key/master.key")
            }
            choice = {
                "connection_id": connection,
                "connection_revision": 1,
                "model": "synthetic/upgrade",
                "output_tokens": 37,
            }
            payload = json.dumps(
                {"default": choice, "brain": choice, "investigator": None, "validator": None}
            )
            runtime.psql(
                db,
                f"INSERT INTO provider_connection_revision VALUES ('{identity}','{connection}','openrouter',1,false,'{secret}',1); INSERT INTO provider_model_registry_revision VALUES ('{identity}',1); INSERT INTO provider_model_entry VALUES ('{identity}','{entry}','{connection}','synthetic/upgrade'); INSERT INTO provider_model_entry_revision VALUES ('{identity}','{entry}',1,'{connection}',1,1,37); INSERT INTO provider_selection_revision VALUES ('{identity}','{selection_id}',1,'{payload}'::jsonb)",
            )
            operation_id, dispatch_id = str(uuid4()), str(uuid4())
            seed_history = Path(__file__).with_name("upgrade_history.py").read_text()
            runtime.run(
                "exec",
                record["containers"]["supervisor"],
                "python",
                "-I",
                "-c",
                seed_history,
                json.dumps(
                    dict(
                        instance=identity,
                        connection=connection,
                        entry_id=entry,
                        secret=secret,
                        operation_id=operation_id,
                        dispatch_id=dispatch_id,
                    )
                ),
                effect=True,
            )
            history_sql = (
                "SELECT jsonb_build_object('operation',to_jsonb(o),'dispatch',to_jsonb(d),"
                "'outcome',r.payload,'receipt',e.receipt_ref) FROM system_operation o "
                "JOIN model_dispatch_v2 d USING(instance_id,operation_id) "
                "JOIN model_record_v2 r ON r.instance_id=o.instance_id AND r.id::text=o.outcome_ref->>'id' "
                "JOIN model_dispatch_event_v2 e ON e.instance_id=o.instance_id AND e.dispatch_attempt_id=d.dispatch_attempt_id "
                f"WHERE o.operation_id='{operation_id}' AND e.state='SETTLED'"
            )
            history_before = json.loads(runtime.psql(db, history_sql))
            assert history_before["operation"]["operation_id"] == operation_id
            assert history_before["operation"]["command_id"] == operation_id
            assert history_before["operation"]["state"] == "FINISHED"
            assert history_before["dispatch"]["dispatch_attempt_id"] == dispatch_id
            assert history_before["receipt"] == history_before["operation"]["outcome_ref"]
            assert {
                key: history_before["outcome"][key]
                for key in (
                    "result_state",
                    "usage_state",
                    "input_tokens",
                    "output_tokens",
                    "cost_observed",
                )
            } == dict(
                result_state="UNKNOWN",
                usage_state="KNOWN",
                input_tokens=9,
                output_tokens=7,
                cost_observed="0.000016",
            )
            for table in (
                "provider_connection_revision",
                "provider_selection_revision",
                "provider_settings_command",
                "provider_model_registry_revision",
                "provider_model_entry",
                "provider_model_entry_revision",
                "provider_model_command",
                "model_record_v2",
                "system_operation",
                "model_command_v2",
                "model_dispatch_v2",
                "model_dispatch_event_v2",
                "system_operation_event",
            ):
                assert re.fullmatch(r"[a-z_0-9]+", table)
                if table in {
                    "model_record_v2",
                    "system_operation",
                    "model_command_v2",
                    "model_dispatch_v2",
                    "model_dispatch_event_v2",
                    "system_operation_event",
                }:
                    assert int(runtime.psql(db, f"SELECT count(*) FROM {table}")) > 0
                census[table] = runtime.psql(
                    db,
                    _upgrade_census_sql(table),
                )

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
        if upgrade is not None:
            old = json.loads(first_receipt)
            completion = root / ("stop-" + old["stop_command"] + ".json")
            completion_bytes = completion.read_bytes()
            cli = upgrade["cli"]
            assert (
                command("start", "--no-open", "--json", expected=2)["reason"] == "UPGRADE_REQUIRED"
            )
            assert (root / "startup.json").read_bytes() == first_receipt
            if upgrade_failure:
                # Test-only installed interpreter seam: fail before OPEN, never alter product bytes.
                script = (
                    "import sys,json,subprocess; from pathlib import Path; import omnis_cli.start as s; "
                    "from omnis_cli.lifecycle import StartError; from omnis_cli.main import main; "
                    "args=json.loads(sys.argv[1]); "
                    "exec('def fail(*a, **k):\\n"
                    ' cli=str(Path(sys.executable).with_name("omnis"))\\n'
                    ' other=args.copy(); other[4]+="-concurrent"\\n'
                    ' for argv in ([cli,"start","--no-open","--json"],[cli,*other]):\\n'
                    "  p=subprocess.run(argv,capture_output=True,text=True,timeout=15)\\n"
                    '  assert p.returncode==4 and json.loads(p.stdout)["reason"]=="UPGRADE_RECOVERY_REQUIRED"\\n'
                    ' raise StartError("SYNTHETIC_PREOPEN_FAILURE",3)\'); '
                    "s.wait_dashboard=fail; raise SystemExit(main(args))"
                )
                args = [
                    "upgrade",
                    "--bundle",
                    upgrade["bundle"],
                    "--backup",
                    str(state / "snapshot"),
                    "--json",
                ]
                driver_pending = True
                failed = subprocess.run(
                    [str(Path(cli).with_name("python")), "-I", "-c", script, json.dumps(args)],
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                driver_pending = False
                assert failed.returncode == 3
                assert json.loads(failed.stdout)["reason"] == "UPGRADE_ROLLED_BACK_STOPPED"
                intent = json.loads((data / "omnis/upgrade.json").read_text())
                assert intent["state"] == "ROLLED_BACK"
                assert (root / "restore-source/startup.json").read_bytes() == first_receipt
                assert (root / "restore-source/completion.json").read_bytes() == completion_bytes
                quarantine = Path(intent["quarantine"])
                assert quarantine.is_dir() and "open_command" not in json.loads(
                    (quarantine / "startup.json").read_text()
                )
                assert json.loads((data / "omnis/installed.json").read_text())["release"] == "0.1.0"
                runtime = ControlRuntime(data, time.monotonic() + 90)
                assert runtime.receipt.image_id == receipt["image_id"]
                assert not runtime.ids()
                cli = upgrade["old_cli"]
                wait_port()
                restored = command("start", "--no-open", "--json")
                assert (
                    restored["instance_id"] == started["instance_id"]
                    and restored["schema"] == "0016_provider_models"
                )
                record = json.loads((root / "startup.json").read_text())
                runtime.attempt = record["attempt"]
                assert (
                    json.loads(runtime.psql(record["containers"]["db"], history_sql))
                    == history_before
                )
                for table, expected in census.items():
                    assert (
                        runtime.psql(
                            record["containers"]["db"],
                            _upgrade_census_sql(table),
                        )
                        == expected
                    )
                assert (
                    runtime.psql(record["containers"]["db"], "SELECT value FROM sl04_sentinel")
                    == "7"
                )
                assert command("stop", "--json")["state"] == "STOPPED"
                record = json.loads((root / "startup.json").read_text())
                runtime.deadline = time.monotonic() + 90
                assert_resources_absent(runtime, root, control, record)
                proof = cleanup = True
                return
            # Candidate sources are mounted only after old0016 has stopped.
            source = Path(__file__).resolve().parents[2]
            shutil.copytree(
                source / "api/src/omnis",
                workspace / "api/src/omnis",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            shutil.copytree(Path(upgrade["bundle"]) / "web", workspace / "web/dist")
            validate_new(str(workspace))
            config.write_text(
                f"port = {port}\ndevelopment_workspace = {json.dumps(str(workspace))}\n"
            )
            upgrade_config = config.read_bytes()
            restarted = command(
                "upgrade",
                "--bundle",
                upgrade["bundle"],
                "--backup",
                str(state / "snapshot"),
                "--json",
                timeout=900,
            )
            runtime = ControlRuntime(data, time.monotonic() + 90)
            upgraded_record = json.loads((root / "startup.json").read_text())
            assert completion.read_bytes() == completion_bytes
            assert (
                root / ("stopped-" + old["stop_command"] + ".json")
            ).read_bytes() == first_receipt
            assert restarted["release"] == "0.1.1" and restarted["schema"] == "0017_model_removal"
            assert restarted["mode"] == "DEVELOPMENT"
            assert upgraded_record["development_workspace"] == str(workspace)
            assert config.read_bytes() == upgrade_config
            reused = command("start", "--no-open", "--json")
            assert reused["reused"] is True and reused["mode"] == "DEVELOPMENT"
            assert json.loads((root / "startup.json").read_text()) == upgraded_record
            assert config.read_bytes() == upgrade_config
            assert all(
                upgraded_record[key] == old[key]
                for key in (
                    "project",
                    "docker_id",
                    "docker_host",
                    "system_id",
                    "pgdata_identity",
                    "vault_identity",
                    "vault_key_identity",
                )
            )
            assert runtime.receipt.image_id != receipt["image_id"]
            assert all((root / name).read_bytes() == value for name, value in vault_before.items())
            assert (data / "omnis/releases/0.1.0/release.json").is_file()
            assert (
                json.loads(runtime.psql(upgraded_record["containers"]["db"], history_sql))
                == history_before
            )
            assert (
                runtime.psql(
                    upgraded_record["containers"]["db"],
                    "SELECT count(*) FROM provider_model_entry WHERE removed_registry_revision IS NOT NULL",
                )
                == "0"
            )
            for table, expected in census.items():
                assert (
                    runtime.psql(
                        upgraded_record["containers"]["db"],
                        _upgrade_census_sql(table),
                    )
                    == expected
                )
            assert (
                command(
                    "upgrade",
                    "--bundle",
                    upgrade["bundle"],
                    "--backup",
                    str(state / "second-snapshot"),
                    "--json",
                    expected=2,
                )["state"]
                == "REFUSED"
            )
        else:
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
