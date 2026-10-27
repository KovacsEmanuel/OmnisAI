"""DEVELOPMENT SOURCE controls; OCI/SQL explicitly doubled, no operator fixture."""

import hashlib
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_recover
from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start_runtime import private_identity
from test_recover import RecoveryFixture
from test_stop import private_stop_fixture

start = importlib.import_module("omnis_cli.start")
stop = importlib.import_module("omnis_cli.stop")


def build_fixture(root, marker="one"):
    package = root / "api/src/omnis"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("# isolated synthetic package\n")
    web = root / "web/dist"
    (web / "assets").mkdir(parents=True, exist_ok=True)
    files = {
        "index.html": f"<html>{marker}</html>".encode(),
        "assets/app.js": f"/* {marker} */".encode(),
    }
    for name, content in files.items():
        (web / name).write_bytes(content)
    (web / "omnis-web.json").write_text(
        json.dumps(
            {"version": 1, "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
        )
    )
    return files


def develop(fixture, selected):
    fixture.record["development_workspace"] = selected
    for role in ("api", "supervisor"):
        for source, destination in (
            ("api/src/omnis", "/usr/local/lib/python3.13/site-packages/omnis"),
            *((("web/dist", "/opt/omnis/web"),) if role == "api" else ()),
        ):
            fixture.items[fixture.ids[role]]["Mounts"].append(
                dict(
                    Type="bind",
                    Source=selected + "/" + source,
                    Destination=destination,
                    RW=False,
                    Propagation="rprivate",
                )
            )
    write_record(fixture.root / "startup.json", fixture.record, replace=True)


class DevelopmentComposeTest(unittest.TestCase):
    def setUp(self):
        import subprocess
        from unittest.mock import Mock

        import test_provider_settings_profile

        fixture = test_provider_settings_profile.ProviderSettingsProfileTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.runtime = fixture.runtime
        self.runtime.development_workspace = "/checkout/plain"
        self.runtime.release = fixture.root / "release"
        ops = self.runtime.release / "ops"
        ops.mkdir(parents=True)
        (ops / "compose.yaml").write_bytes(
            (Path(__file__).resolve().parents[2] / "ops/compose.control.yaml").read_bytes()
        )
        self.env = start.environment(self.runtime, fixture.root, fixture.root / "control", 48765)
        self.rendered = {}

        def render(*args, env, cap, effect, stdin):
            self.assertFalse(effect)
            self.assertEqual(args[0], "compose")
            self.assertEqual(args[-3:], ("config", "--format", "json"))
            result = subprocess.run(
                ["docker", "--host", "unix:///nonexistent.sock", *args],
                input=stdin.decode(),
                env={**env, "PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
                cwd=fixture.root,
                text=True,
                capture_output=True,
                check=True,
                timeout=10,
            )
            self.rendered = json.loads(result.stdout)
            return result

        self.runtime.run = Mock(side_effect=render)

    def test_real_compose_omits_false_without_relaxing_mounts(self):
        import subprocess
        from copy import deepcopy

        start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_called_once()
        valid = self.rendered
        for role, index in (("api", -2), ("api", -1), ("supervisor", -1)):
            volume = valid["services"][role]["volumes"][index]
            self.assertEqual(volume["bind"], {"propagation": "rprivate"})
            explicit = deepcopy(valid)
            explicit["services"][role]["volumes"][index]["bind"]["create_host_path"] = False
            with patch.object(
                self.runtime,
                "compose",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(explicit)),
            ):
                start.validate_config(self.runtime, self.env)
            changes = [
                {"read_only": False},
                {"read_only": 1},
                {"source": "/foreign"},
                {"target": "/foreign"},
                {"unknown": False},
                {"bind": {"propagation": "rshared"}},
                {"bind": {"propagation": "rprivate", "unknown": False}},
                {"bind": {"propagation": "rprivate", "create_host_path": False, "unknown": False}},
                *(
                    {"bind": {"propagation": "rprivate", "create_host_path": value}}
                    for value in (True, 0, 0.0, None, "false", [])
                ),
            ]
            for change in changes:
                with self.subTest(role=role, index=index, change=change):
                    candidate = deepcopy(valid)
                    candidate["services"][role]["volumes"][index].update(change)
                    with patch.object(
                        self.runtime,
                        "compose",
                        return_value=subprocess.CompletedProcess([], 0, json.dumps(candidate)),
                    ):
                        with self.assertRaisesRegex(StartError, "COMPOSE_SERVICE_BINDING_INVALID"):
                            start.validate_config(self.runtime, self.env)
            for extra in (False, True):
                candidate = deepcopy(valid)
                volumes = candidate["services"][role]["volumes"]
                if extra:
                    volumes.append(deepcopy(volume))
                else:
                    volumes.pop(index)
                with (
                    self.subTest(role=role, index=index, extra=extra),
                    patch.object(
                        self.runtime,
                        "compose",
                        return_value=subprocess.CompletedProcess([], 0, json.dumps(candidate)),
                    ),
                ):
                    with self.assertRaisesRegex(StartError, "COMPOSE_SERVICE_BINDING_INVALID"):
                        start.validate_config(self.runtime, self.env)

    def test_real_compose_preserves_escaped_literal_sources(self):
        import subprocess
        from copy import deepcopy

        for selected in (
            "/checkout/$",
            '/checkout/${HOME}/"quoted"',
            r'/checkout/"quoted"\path',
            r'/checkout/$$HOME/${HOME}/"quoted"\path',
        ):
            with self.subTest(workspace=selected):
                self.runtime.development_workspace = selected
                start.validate_config(self.runtime, self.env)
                valid = self.rendered
                for role, index, suffix in (
                    ("api", -2, "api/src/omnis"),
                    ("api", -1, "web/dist"),
                    ("supervisor", -1, "api/src/omnis"),
                ):
                    literal = selected + "/" + suffix
                    source = valid["services"][role]["volumes"][index]["source"]
                    self.assertEqual(source, literal.replace("$", "$$"))
                    for changed in sorted(
                        {
                            "/checkout/foreign/" + suffix,
                            literal,
                            source.replace("$${HOME}", "/nonexistent"),
                            source.replace('"', ""),
                            source.replace("\\", ""),
                            source + "$",
                        }
                        - {source}
                    ):
                        with self.subTest(role=role, index=index, source=changed):
                            candidate = deepcopy(valid)
                            candidate["services"][role]["volumes"][index]["source"] = changed
                            with patch.object(
                                self.runtime,
                                "compose",
                                return_value=subprocess.CompletedProcess(
                                    [], 0, json.dumps(candidate)
                                ),
                            ):
                                with self.assertRaisesRegex(
                                    StartError, "COMPOSE_SERVICE_BINDING_INVALID"
                                ):
                                    start.validate_config(self.runtime, self.env)

    def test_inspect_requires_literal_not_renderer_escaped_sources(self):
        from copy import deepcopy
        from unittest.mock import Mock

        import test_start_attestation
        from runtime_inspect_fixture import image_item

        fixture = test_start_attestation.ProductAttestationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runtime = fixture.runtime
        selected = r'/checkout/$/${HOME}/"quoted"\path'
        runtime.development_workspace = selected
        valid = fixture.item("api")
        for suffix, target in (
            ("api/src/omnis", "/usr/local/lib/python3.13/site-packages/omnis"),
            ("web/dist", "/opt/omnis/web"),
        ):
            valid["Mounts"].append(
                dict(
                    Type="bind",
                    Source=selected + "/" + suffix,
                    Destination=target,
                    RW=False,
                    Propagation="rprivate",
                )
            )
        candidate = deepcopy(valid)
        runtime.inspect = Mock(
            side_effect=lambda kind, _ident: (
                image_item(runtime, "api")
                if kind == "image"
                else fixture.network
                if kind == "network"
                else candidate
            )
        )
        runtime.attest(fixture.cid, "api", fixture.root, fixture.control, fixture.port)
        for index in (-2, -1):
            for source in (valid["Mounts"][index]["Source"].replace("$", "$$"), "/foreign"):
                candidate = deepcopy(valid)
                candidate["Mounts"][index]["Source"] = source
                with self.subTest(index=index, source=source):
                    with self.assertRaisesRegex(StartError, "CONTAINER_IDENTITY_MISMATCH"):
                        runtime.attest(
                            fixture.cid, "api", fixture.root, fixture.control, fixture.port
                        )
        runtime.run.assert_not_called()
        self.runtime.run.assert_not_called()


class DevelopmentLifecycleTest(unittest.TestCase):
    def test_dashboard_reads_current_manifest_not_immutable_files_and_denies_drift(self):
        import omnis_cli.health as health

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            current = dict(instance_id="fixture", assessment_ready=False, shutdown_command_id=None)
            served = build_fixture(root)
            ready = json.dumps(
                dict(
                    api_ready=True,
                    dashboard_ready=True,
                    assessment_ready=False,
                    reason=None,
                    dashboard_reason=None,
                )
            ).encode()

            def probe(_port, route, *_args, **_kwargs):
                return (
                    ready
                    if route == "/health/ready"
                    else served["index.html" if route == "/" else route[1:]]
                )

            with (
                patch.object(health, "request", return_value=current),
                patch.object(health, "http_probe", side_effect=probe),
            ):
                for marker in ("one", "two"):
                    served = build_fixture(root, marker)
                    self.assertEqual(
                        health.dashboard(
                            root,
                            root,
                            8765,
                            "fixture",
                            {"web/index.html": b"immutable"},
                            100,
                            forwarded=True,
                            api_pid=2,
                            development_workspace=str(root),
                        ),
                        current,
                    )
                (root / "web/dist/assets/app.js").write_bytes(b"corrupt")
                with self.assertRaises(StartError):
                    health.dashboard(
                        root,
                        root,
                        8765,
                        "fixture",
                        {},
                        100,
                        forwarded=True,
                        api_pid=2,
                        development_workspace=str(root),
                    )
                served = build_fixture(root)
                with self.assertRaises(StartError):
                    health.dashboard(
                        root,
                        root,
                        8765,
                        "fixture",
                        {"web/index.html": b"immutable"},
                        100,
                        forwarded=True,
                        api_pid=2,
                    )

    def test_new_start_requires_owned_nonsymlink_package_and_valid_bounded_web(self):
        from omnis_cli import development

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            build_fixture(root)
            development.validate_new(str(root))
            package = root / "api/src/omnis"
            (package / "escape").symlink_to(Path.home())
            with self.assertRaises(StartError):
                development.validate_new(str(root))
            (package / "escape").unlink()
            package.chmod(0o777)
            with self.assertRaises(StartError):
                development.validate_new(str(root))
            package.chmod(0o755)
            manifest = root / "web/dist/omnis-web.json"
            for raw in (
                b"{}",
                b" " * 32769,
                b'{"version":true,"files":{}}',
                b'{"version":1,"version":1,"files":{}}',
            ):
                manifest.write_bytes(raw)
                with self.assertRaises(StartError):
                    development.validate_new(str(root))
            build_fixture(root)
            asset = root / "web/dist/assets/app.js"
            asset.unlink()
            asset.symlink_to(package / "__init__.py")
            with self.assertRaises(StartError):
                development.validate_new(str(root))

    def test_development_overlay_is_only_api_web_and_api_supervisor_package(self):
        import omnis_cli.start_runtime as runtime_source
        import test_provider_settings_profile

        fixture = test_provider_settings_profile.ProviderSettingsProfileTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runtime = fixture.runtime
        runtime.development_workspace = "/missing-content"
        overlay = runtime_source.provider_settings_overlay(
            runtime, {"OMNIS_STATE_ROOT": str(fixture.root)}
        )
        services = overlay["services"]
        self.assertEqual(set(services), {"api", "supervisor"})
        self.assertEqual(len(services["supervisor"]["volumes"]), 3)
        self.assertEqual(len(services["api"]["volumes"]), 2)
        for role in ("api", "supervisor"):
            mounts = services[role]["volumes"][-(2 if role == "api" else 1) :]
            self.assertTrue(
                all(
                    row["read_only"] is True
                    and row["bind"] == {"create_host_path": False, "propagation": "rprivate"}
                    for row in mounts
                )
            )
            self.assertEqual(mounts[0]["target"], "/usr/local/lib/python3.13/site-packages/omnis")
        self.assertEqual(services["api"]["volumes"][1]["target"], "/opt/omnis/web")

    def test_compose_serialization_escapes_dollars_without_changing_attestation_paths(self):
        from unittest.mock import Mock

        import test_provider_settings_profile

        fixture = test_provider_settings_profile.ProviderSettingsProfileTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runtime = fixture.runtime
        runtime.release = fixture.root / "release"
        runtime.development_workspace = '/checkout/${HOME}/"quoted"'
        runtime.run = Mock()
        runtime.compose({"OMNIS_STATE_ROOT": str(fixture.root)}, "config", "--format", "json")
        overlay = json.loads(runtime.run.call_args.kwargs["stdin"])
        self.assertEqual(
            overlay["services"]["api"]["volumes"][0]["source"],
            '/checkout/$${HOME}/"quoted"/api/src/omnis',
        )

    def test_rendered_compose_and_inspect_deny_development_mount_drift(self):
        import subprocess
        from copy import deepcopy
        from unittest.mock import Mock

        import test_start_attestation

        fixture = test_start_attestation.ProductAttestationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from omnis_cli.development import mounts

        runtime = fixture.runtime
        valid = fixture.config()
        runtime.receipt.profile = "t1-provider-settings"
        runtime.development_workspace = "/missing-checkout"
        for role in ("api", "supervisor"):
            if role == "supervisor":
                valid["services"][role]["environment"].update(
                    OMNIS_VAULT_DIR="/vault",
                    OMNIS_VAULT_KEY_DIR="/vault-key",
                    OMNIS_MODEL_EGRESS_DIR="/vault",
                )
                valid["services"][role]["volumes"].extend(
                    {"type": "bind", "source": str(fixture.root / name), "target": "/" + name}
                    for name in ("vault", "vault-key")
                )
            valid["services"][role]["volumes"].extend(mounts(runtime.development_workspace, role))
        runtime.compose = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(valid)))
        start.validate_config(runtime, fixture.env)
        for change in (
            {"read_only": False},
            {"source": "/home/kali"},
            {"target": "/whole-checkout"},
            {"bind": {"create_host_path": True, "propagation": "rprivate"}},
        ):
            candidate = deepcopy(valid)
            candidate["services"]["api"]["volumes"][-1].update(change)
            runtime.compose.return_value = subprocess.CompletedProcess([], 0, json.dumps(candidate))
            with self.assertRaises(StartError):
                start.validate_config(runtime, fixture.env)
        runtime.run.assert_not_called()
        # Same attestor used by the detached Stop owner, no filesystem content required.
        fixture2 = RecoveryFixture()
        self.addCleanup(fixture2.close)
        fixture2.prepare(live_control=True)
        develop(fixture2, "/missing-checkout")
        fixture2.runtime.development_workspace = "/missing-checkout"
        cid = fixture2.ids["api"]
        original = deepcopy(fixture2.items[cid])
        fixture2.runtime.attest(cid, "api", fixture2.root, fixture2.control, fixture2.port)
        for change in (
            {"RW": True},
            {"Source": "/home/kali"},
            {"Propagation": "rshared"},
            {"Destination": "/vault-key"},
        ):
            fixture2.items[cid] = deepcopy(original)
            fixture2.items[cid]["Mounts"][-1].update(change)
            with self.assertRaises(StartError):
                fixture2.runtime.attest(cid, "api", fixture2.root, fixture2.control, fixture2.port)
        fixture2.items[cid] = deepcopy(original)
        fixture2.items[cid]["Mounts"].append(deepcopy(original["Mounts"][-1]))
        with self.assertRaises(StartError):
            fixture2.runtime.attest(cid, "api", fixture2.root, fixture2.control, fixture2.port)

    def test_all_phases_accept_only_bounded_format5_selection_without_content_reads(self):
        with private_stop_fixture() as (_base, root, _foreign, _control, stopped, _runtime):
            stopped["format"] = 5
            for name, field in (("vault", "vault_identity"), ("vault-key", "vault_key_identity")):
                (root / name).mkdir(mode=0o700)
                stopped[field] = private_identity(root / name)
            selected = "/" + '"' * 255 + "/" + "\\" * 255
            stopped["development_workspace"] = selected
            extra = {"vault_identity", "vault_key_identity", "development_workspace"}
            for phase, fields in (
                ("STARTING", start.START_FIELDS),
                ("MIGRATING", start.START_FIELDS | {"system_id"}),
                ("SERVICES", start.START_FIELDS | {"system_id", "instance_id"}),
                ("VERIFYING", start.START_FIELDS | {"system_id", "instance_id"}),
                ("FORWARDING", start.READY_FIELDS - {"generation", "supervisor_epoch"}),
                ("READY", start.READY_FIELDS),
                ("STOPPING", start.STOP_FIELDS),
                ("STOPPED", start.STOP_FIELDS),
            ):
                record = {k: v for k, v in stopped.items() if k in fields | extra}
                record["phase"] = phase
                with self.subTest(phase=phase):
                    self.assertEqual(start._pgdata_receipt(record), stopped["pgdata_identity"])
                    if phase == "READY":
                        start._ready_record(record)
                    if phase in {"STOPPING", "STOPPED"}:
                        stop._stopping_record(record)
                    for value in (None, True, "relative", selected + "x", "/x/../y"):
                        with self.assertRaises(StartError):
                            start._pgdata_receipt({**record, "development_workspace": value})
                    with self.assertRaises(StartError):
                        start._pgdata_receipt({**record, "format": 2})

    def test_missing_development_content_and_config_drift_do_not_block_recovery_owner(self):
        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        selected = "/" + '"' * 255 + "/" + "\\" * 255
        develop(fixture, selected)
        directory = fixture.base / "config/omnis"
        directory.mkdir(parents=True, mode=0o700)
        path = directory / "config.toml"
        path.write_text('development_workspace = "/different-missing-workspace"\n')
        path.chmod(0o600)
        code, result = test_recover.RecoverTests().invoke(fixture)
        self.assertEqual((code, result["state"]), (0, "STOPPED"), result)
        self.assertEqual(result["mode"], "DEVELOPMENT")
        self.assertEqual(fixture.journal()["development_workspace"], selected)
        self.assertFalse(fixture.items)
        self.assertIsNone(fixture.network_item)
        self.assertEqual((fixture.root / "vault/sentinel").read_bytes(), b"retained")

    def test_recovery_route_proof_does_not_require_stable_mutable_readiness(self):
        import omnis_cli.recover as recovery

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        develop(fixture, "/missing-rebuilding")
        with patch.object(
            recovery,
            "http_probe",
            side_effect=[b'{"dashboard_ready":false}', b'{"dashboard_ready":true}'],
        ) as http:
            self.assertEqual(
                recovery._inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record, dead=True
                ),
                0,
            )
        self.assertEqual(
            [call.args[1] for call in http.call_args_list], ["/health/ready", "/health/ready"]
        )
        self.assertTrue(all(call.kwargs["statuses"] == (200, 503) for call in http.call_args_list))

    def test_invalid_build_still_allows_normal_stop_without_health_or_source_read(self):
        import omnis_cli.health as health
        from omnis_cli import development

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare(live_control=True)
        workspace = fixture.base / "checkout"
        build_fixture(workspace)
        develop(fixture, str(workspace))
        (workspace / "web/dist/omnis-web.json").write_bytes(b"rebuilding")
        fixture.items[fixture.ids["supervisor"]]["State"].update(
            Running=True, Status="running", Pid=fixture.processes["supervisor"].pid
        )
        fixture.current.update(
            generation=1,
            supervisor_epoch=1,
            admission_open=True,
            shutdown_command_id=None,
            quiesced_generation=None,
        )
        with self.assertRaises(StartError):
            development.web_files(str(workspace))
        with (
            patch.object(
                development, "web_files", side_effect=AssertionError("Stop cannot read web")
            ),
            patch.object(
                development, "validate_new", side_effect=AssertionError("Stop cannot read source")
            ),
            patch.object(
                health, "http_probe", side_effect=AssertionError("Stop cannot require healthy UI")
            ),
        ):
            code, result = test_recover.RecoverTests().invoke(fixture, "stop")
        self.assertEqual(
            (code, result["state"], result.get("mode")), (0, "STOPPED", "DEVELOPMENT"), result
        )
        self.assertFalse(fixture.items)

    def test_full_escaped_envelopes_use_real_inventory_grant_completion_and_restart_serializers(
        self,
    ):
        from omnis_cli.control import _stop_binding
        from omnis_cli.lifecycle import read_record
        from omnis_cli.restart import _prepare_reconciliation
        from omnis_cli.stop_receipt import (
            completed_receipt,
            encoded,
            fingerprint,
            persist,
            receipt_path,
            validate_grant,
            validate_inventory,
        )

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare(live_control=True)
        develop(fixture, "/" + '"' * 255 + "/" + "\\" * 255)
        fixture.items[fixture.ids["supervisor"]]["State"].update(
            Running=True, Status="running", Pid=fixture.processes["supervisor"].pid
        )
        fixture.current.update(
            generation=9223372036854775805,
            supervisor_epoch=9223372036854775807,
            admission_open=True,
            shutdown_command_id=None,
            quiesced_generation=None,
        )
        fixture.record.update(
            generation=fixture.current["generation"],
            supervisor_epoch=fixture.current["supervisor_epoch"],
        )
        write_record(fixture.root / "startup.json", fixture.record, replace=True)
        code, result = test_recover.RecoverTests().invoke(fixture, "stop")
        self.assertEqual((code, result["state"]), (0, "STOPPED"), result)
        record = fixture.journal()
        completion = read_record(receipt_path(fixture.root, record))
        grant = completion["grant"]
        inventory = grant["inventory"]
        # Pad kernel numeric fields only after real _entry/completion; this is a size fixture.
        maximum = 18446744073709551615
        record.update(system_id=str(maximum), port=65535, listener_inode=maximum)
        for key in ("pgdata_identity", "api_socket", "control_socket"):
            record[key] = [maximum, maximum]
        for key in ("vault_identity", "vault_key_identity"):
            record[key][:2] = [maximum, maximum]
        record["forwarder"].update(pid=2147483647, start_ticks=str(maximum))
        inventory.update(pgdata=record["pgdata_identity"], system_id=record["system_id"])
        inventory["forwarder"].update(
            pid=2147483647,
            start_ticks=str(maximum),
            identity=fingerprint(record["forwarder"]),
            listener=maximum,
            port=65535,
        )
        for key in ("api", "control", "api_lock", "control_lock", "cap"):
            inventory["ipc"][key] = [maximum, maximum]
        for key in ("owner", "launcher"):
            completion[key].update(pid=2147483647, start_ticks=str(maximum))
        stop._stopping_record(record)
        validate_inventory(inventory, record)
        validate_grant(grant, record, inventory)
        command = {
            k: v for k, v in grant.items() if k not in {"version", "state", "owner_uuid"}
        } | {"op": "arm_stop"}
        _stop_binding(command)
        payload = dict(
            root=str(fixture.root),
            control=str(fixture.control),
            data_home=str(fixture.data),
            record=record,
            grant=grant,
            deadline_ns=9223372036854775807,
            guard_fds=[2147483646, 2147483647],
        )
        write_record(fixture.base / "bounded-startup.json", record)
        persist(fixture.base / "bounded-completion.json", completion)
        completed_receipt(fixture.base / "bounded-completion.json", grant)
        raw = (fixture.base / "bounded-startup.json").read_bytes()
        complete_raw = (fixture.base / "bounded-completion.json").read_bytes()
        intent = _prepare_reconciliation(fixture.root, record, fixture.new_owner, raw, complete_raw)
        sizes = {
            "startup": len(raw),
            "completion": len(complete_raw),
            "inventory": len(encoded(inventory)),
            "grant": len(encoded(grant)),
            "control": len(
                json.dumps(dict(version=1, capability="a" * 64, command=command)).encode()
            )
            + 1,
            "handoff": len(encoded(payload)),
            "restart": len(encoded(intent)),
            "reconciliation": len(encoded(intent["request"])) + 1,
        }
        for key, value in sizes.items():
            self.assertLessEqual(
                value, {"inventory": 2900, "grant": 3600, "control": 4096}.get(key, 16384), key
            )
        print("DEVELOPMENT_FULL_ENVELOPE_BYTES " + json.dumps(sizes, sort_keys=True))

    def test_status_and_verified_pair_open_use_receipt_despite_selector_drift(self):
        import contextlib
        import io

        import omnis_cli.health as health
        import omnis_cli.verified as verified

        status = importlib.import_module("omnis_cli.status")
        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare(live_control=True)
        workspace = fixture.base / "checkout"
        served = build_fixture(workspace)
        develop(fixture, str(workspace))
        fixture.items[fixture.ids["supervisor"]]["State"].update(
            Running=True, Status="running", Pid=fixture.processes["supervisor"].pid
        )
        fixture.current.update(
            generation=1,
            supervisor_epoch=1,
            admission_open=True,
            shutdown_command_id=None,
            quiesced_generation=None,
        )
        directory = fixture.base / "config/omnis"
        directory.mkdir(parents=True, mode=0o700)
        config = directory / "config.toml"
        config.write_text('development_workspace = "/different-missing"\n')
        config.chmod(0o600)
        ready = json.dumps(
            dict(
                api_ready=True,
                dashboard_ready=True,
                assessment_ready=False,
                reason=None,
                dashboard_reason=None,
            )
        ).encode()

        def probe(_port, route, *_args, **_kwargs):
            return (
                ready
                if route == "/health/ready"
                else served["index.html" if route == "/" else route[1:]]
            )

        with contextlib.ExitStack() as scope:
            scope.enter_context(patch.dict(os.environ, fixture.environment))
            for module in (status, verified):
                scope.enter_context(patch.object(module, "state_dir", return_value=fixture.root))
                scope.enter_context(
                    patch.object(module, "control_dir", return_value=fixture.control)
                )
                scope.enter_context(
                    patch.object(module, "ControlRuntime", return_value=fixture.runtime)
                )
            scope.enter_context(patch.object(status, "request", return_value=fixture.current))
            scope.enter_context(patch.object(health, "request", return_value=fixture.current))
            scope.enter_context(patch.object(health, "http_probe", side_effect=probe))
            for valid in (True, False):
                if not valid:
                    (workspace / "web/dist/omnis-web.json").unlink()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = status.status(as_json=True)
                result = json.loads(output.getvalue())
                self.assertEqual(
                    (code, result["mode"], result["dashboard_ready"]),
                    (0 if valid else 3, "DEVELOPMENT", valid),
                )
                if valid:
                    with verified.verified_instance() as (result, _control):
                        self.assertEqual(result["mode"], "DEVELOPMENT")
                else:
                    with self.assertRaises(StartError):
                        with verified.verified_instance():
                            self.fail("Invalid UI cannot authorize Pair/Open")

    def test_start_reuse_conflicts_on_selector_before_duplicate_or_health(self):
        from omnis_cli.config import Config

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        for selected, configured in ((None, "/new"), ("/old", None), ("/old", "/new")):
            if selected is not None:
                fixture.record["development_workspace"] = selected
            else:
                fixture.record.pop("development_workspace", None)
            write_record(fixture.root / "startup.json", fixture.record, replace=True)
            with (
                self.subTest(selected=selected, configured=configured),
                patch.dict(os.environ, fixture.environment),
                patch.object(start, "state_dir", return_value=fixture.root),
                patch.object(start, "control_dir", return_value=fixture.control),
                patch.object(
                    start, "load_config", return_value=Config(development_workspace=configured)
                ),
                patch.object(start, "ControlRuntime", return_value=fixture.runtime),
                patch.object(start, "verify_running") as health,
            ):
                with self.assertRaises(StartError) as raised:
                    start.start_instance()
                self.assertEqual(raised.exception.reason, "CONFIG_MODE_CONFLICT")
                health.assert_not_called()
                fixture.runtime.run.assert_not_called()
