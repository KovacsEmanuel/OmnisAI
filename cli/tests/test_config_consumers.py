"""Config/receipt composition at real P0 consumers, with resource seams blocked."""

import contextlib
import importlib
import io
import json
import os
import unittest
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.main import main
import test_config as config_tests
from test_stop import private_stop_fixture


class ConfigConsumersTest(unittest.TestCase):
    setUp = config_tests.ConfigTest.setUp
    write_config = config_tests.ConfigTest.write_config

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
                        self.assertIn("PORT_CHANGE_REQUIRES_STOP", out.getvalue() + err.getvalue())
                        for resource in resources:
                            resource.assert_not_called()
                        self.assertFalse((root / "lifecycle.lock").exists())
                        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_invalid_config_cannot_bypass_admission_via_direct_consumers(self):
        from omnis_cli.start import start_result
        from omnis_cli.stop import stop
        from omnis_cli.status import status
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
