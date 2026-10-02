"""Real console dispatch in an external cwd and private XDG, no installed services."""

import json
import os
import subprocess
import sys
import unittest

import test_config as config_tests


class ConfigConsoleTest(unittest.TestCase):
    setUp = config_tests.ConfigTest.setUp
    write_config = config_tests.ConfigTest.write_config

    def invoke(self, args):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "from omnis_cli.main import entrypoint; entrypoint()",
                *args,
            ],
            cwd=self.root,
            env=dict(os.environ),
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_absent_valid_and_home_fallback_are_real_console_inputs(self):
        for config in (
            None,
            "port=9010\nstartup_timeout_seconds=30\nshutdown_timeout_seconds=15\ncleanup_timeout_seconds=30",
        ):
            if config is not None:
                self.write_config(config)
            result = self.invoke(["status", "--json"])
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(json.loads(result.stdout)["state"], "NOT_INSTALLED")
        home_config = self.root / "home/.config/omnis"
        home_config.mkdir(mode=0o700, parents=True)
        self.config.rename(home_config / "config.toml")
        del os.environ["XDG_CONFIG_HOME"]
        self.assertEqual(self.invoke(["status", "--json"]).returncode, 3)
        (home_config / "config.toml").write_text("port = true")
        denied = self.invoke(["status", "--json"])
        self.assertEqual(
            (denied.returncode, json.loads(denied.stdout)["reason"]), (2, "CONFIG_INVALID")
        )
        self.assertFalse((self.root / "state").exists())

    def test_invalid_config_is_sanitized_before_each_real_console_consumer(self):
        values = [
            'token="synthetic-secret-marker"',
            "port=true",
            "port=1023",
            "port=65536",
            "startup_timeout_seconds=29",
            "startup_timeout_seconds=301",
            "shutdown_timeout_seconds=14",
            "shutdown_timeout_seconds=181",
            "cleanup_timeout_seconds=29",
            "cleanup_timeout_seconds=181",
            "cleanup_timeout_seconds=30.0",
            "[port]\nvalue=8765",
        ]
        for text in values:
            self.write_config(text)
            before = self.config.read_bytes()
            for args in (
                [],
                ["start", "--no-open", "--json"],
                ["stop", "--json"],
                ["status", "--json"],
                ["pair"],
                ["open"],
            ):
                with self.subTest(text=text, args=args):
                    result = self.invoke(args)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("CONFIG_INVALID", result.stdout + result.stderr)
                    self.assertNotIn("synthetic-secret-marker", result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(self.config.read_bytes(), before)
                    for directory in ("state", "data", "ipc"):
                        self.assertFalse((self.root / directory).exists())

    def test_excessive_toml_depth_is_refused_before_every_consumer(self):
        text = "port = " + "[" * 1200 + "1" + "]" * 1200 + "\n"
        self.assertLessEqual(len(text.encode()), 4096)
        self.write_config(text)
        before = self.config.read_bytes()
        for args in (
            [],
            ["start", "--no-open", "--json"],
            ["stop", "--json"],
            ["status", "--json"],
            ["pair"],
            ["open"],
        ):
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("CONFIG_INVALID", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.config.read_bytes(), before)
                for directory in ("state", "data", "ipc"):
                    self.assertFalse((self.root / directory).exists())
