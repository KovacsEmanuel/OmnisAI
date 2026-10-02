"""Config/receipt composition at real P0 consumers, with resource seams blocked."""

import contextlib
import importlib
import io
import json
import os
import unittest
from unittest.mock import patch

import test_config as config_tests
from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.main import main
from test_stop import private_stop_fixture


class ConfigConsumersTest(unittest.TestCase):
    setUp = config_tests.ConfigTest.setUp
    write_config = config_tests.ConfigTest.write_config

    def test_stop_config_and_explicit_cli_budget_reach_runtime(self):
        stop = importlib.import_module("omnis_cli.stop")
        self.write_config("shutdown_timeout_seconds=15")
        for flags, seconds in (([], 15), (["--shutdown-timeout", "17"], 17)):
            with (
                self.subTest(flags=flags),
                patch.object(stop.time, "monotonic", return_value=100),
                patch.object(
                    stop, "ControlRuntime", side_effect=StartError("BUDGET_OBSERVED", 3)
                ) as runtime,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["stop", "--json", *flags]), 3)
                self.assertEqual(runtime.call_args.args[1], 100 + seconds)

    def test_cleanup_has_separate_configured_allowance_after_startup_expiry(self):
        from types import SimpleNamespace

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        self.write_config("startup_timeout_seconds=30\ncleanup_timeout_seconds=31")
        for index, (flags, allowance) in enumerate((([], 31), (["--cleanup-timeout", "40"], 40))):
            runtime = SimpleNamespace(
                receipt=SimpleNamespace(
                    project="omnis-local-" + "a" * 32,
                    image_id="sha256:" + "b" * 64,
                    docker_id="test-daemon",
                ),
                digest="c" * 64,
                host="unix:///run/docker.sock",
                uncertain=False,
                family_drained=True,
                inspect=lambda *args: None,
                network=lambda *args: None,
            )
            deadlines = []

            def construct(_data, deadline, runtime=runtime):
                runtime.deadline = deadline
                return runtime

            def inventory(runtime=runtime, deadlines=deadlines):
                deadlines.append(runtime.deadline)
                return []

            runtime.ids = inventory
            with (
                self.subTest(flags=flags),
                patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / f"s{index}")}),
                patch.object(start, "ControlRuntime", side_effect=construct),
                patch.object(start, "preflight_port"),
                patch.object(start.time, "monotonic", return_value=100) as clock,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):

                def expire(*args):
                    clock.return_value = 500
                    raise StartError("STARTUP_TIMEOUT", 3)

                with patch.object(start, "validate_config", side_effect=expire):
                    self.assertEqual(main(["start", "--no-open", "--json", *flags]), 3)
            self.assertEqual(deadlines[0], 130)
            self.assertEqual(deadlines[1:], [500 + allowance, 500 + allowance])
            self.assertEqual(json.loads(output.getvalue())["reason"], "STARTUP_TIMEOUT")

    def test_fresh_start_config_and_cli_precedence_reaches_port_and_deadline(self):
        from types import SimpleNamespace

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        cases = [
            (None, [], 8765, 180),
            ("port=9010\nstartup_timeout_seconds=31", [], 9010, 31),
            (
                "port=9010\nstartup_timeout_seconds=31",
                ["--port", "9011", "--startup-timeout", "40"],
                9011,
                40,
            ),
        ]
        for text, options, port, seconds in cases:
            with self.subTest(options=options, text=text):
                if text is not None:
                    self.write_config(text)
                with (
                    patch.object(start.time, "monotonic", return_value=100),
                    patch.object(
                        start, "ControlRuntime", return_value=SimpleNamespace()
                    ) as constructor,
                    patch.object(
                        start, "preflight_port", side_effect=StartError("PORT_OBSERVED", 3)
                    ) as selected,
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    code = main(["start", "--no-open", "--json", *options])
                self.assertEqual(code, 3)
                selected.assert_called_once_with(port)
                self.assertEqual(constructor.call_args.args[1], 100 + seconds)

    def test_port_conflict_preserves_receipts_before_resource_or_lock(self):
        with private_stop_fixture() as (base, root, _foreign, _control, record, _runtime):
            write_record(root / "startup.json", record)
            before = {p: p.read_bytes() for p in (root / "startup.json", root / "instance.json")}
            self.write_config("port = 1024\n")
            with patch.dict(
                os.environ,
                {
                    "XDG_STATE_HOME": str(base / "s"),
                    "XDG_DATA_HOME": str(base / "d"),
                    "XDG_RUNTIME_DIR": "",
                },
            ):
                for command in (
                    [],
                    ["start", "--no-open", "--json"],
                    ["status", "--json"],
                    ["pair"],
                    ["open"],
                    ["stop", "--json"],
                ):
                    with self.subTest(command=command), contextlib.ExitStack() as stack:
                        resources = []
                        for module_name in ("start", "stop", "status", "verified"):
                            module = importlib.import_module("omnis_cli." + module_name)
                            resources.append(
                                stack.enter_context(
                                    patch.object(
                                        module,
                                        "ControlRuntime",
                                        side_effect=StartError("RESOURCE_REACHED", 3),
                                    )
                                )
                            )
                        resources.append(
                            stack.enter_context(
                                patch(
                                    "omnis_cli.status.request",
                                    side_effect=AssertionError("UDS contacted"),
                                )
                            )
                        )
                        stack.enter_context(
                            patch("omnis_cli.pairing.interactive_tty", return_value=True)
                        )
                        out, err = io.StringIO(), io.StringIO()
                        stack.enter_context(contextlib.redirect_stdout(out))
                        stack.enter_context(contextlib.redirect_stderr(err))
                        self.assertEqual(main(command), 2)
                        self.assertIn("CONFIG_PORT_CONFLICT", out.getvalue() + err.getvalue())
                        self.assertNotIn(
                            "PORT_CHANGE_REQUIRES_STOP", out.getvalue() + err.getvalue()
                        )
                        for resource in resources:
                            resource.assert_not_called()
                        self.assertFalse((root / "lifecycle.lock").exists())
                        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_invalid_config_cannot_bypass_admission_via_direct_consumers(self):
        from omnis_cli.start import start_result
        from omnis_cli.status import status
        from omnis_cli.stop import stop
        from omnis_cli.verified import verified_instance

        self.write_config("port = true\n")
        with contextlib.ExitStack() as stack:
            for module_name in ("start", "stop", "status", "verified"):
                module = importlib.import_module("omnis_cli." + module_name)
                stack.enter_context(
                    patch.object(
                        module, "ControlRuntime", side_effect=AssertionError("resource reached")
                    )
                )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(start_result(None)[0], 2)
            self.assertEqual(stop(as_json=True), 2)
            self.assertEqual(status(as_json=True), 2)
            with self.assertRaises(StartError) as exc, verified_instance():
                self.fail("invalid config was yielded")
            self.assertEqual((exc.exception.reason, exc.exception.code), ("CONFIG_INVALID", 2))


if __name__ == "__main__":
    unittest.main()
