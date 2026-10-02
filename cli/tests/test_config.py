"""M22 config admission: real private files; no Docker/service authority."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.main import main


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m22-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config/omnis/config.toml"
        self.config.parent.mkdir(mode=0o700, parents=True)
        self.env = patch.dict(
            os.environ,
            {
                "HOME": str(self.root / "home"),
                "XDG_CONFIG_HOME": str(self.root / "config"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_RUNTIME_DIR": str(self.root / "ipc"),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_config(self, text):
        self.config.write_text(text)
        self.config.chmod(0o600)

    def test_unknown_secret_config_refused_before_every_cli_consumer(self):
        self.write_config('token = "synthetic-private-marker"\n')
        for args in (
            [],
            ["start", "--no-open", "--json"],
            ["status", "--json"],
            ["pair"],
            ["open"],
            ["stop", "--json"],
        ):
            with self.subTest(args=args), contextlib.ExitStack() as stack:
                effects = [
                    stack.enter_context(patch("omnis_cli.main." + name, return_value=0))
                    for name in ("start", "status", "pair", "open_verified", "stop")
                ]
                effects.append(
                    stack.enter_context(
                        patch("omnis_cli.main.start_result", return_value=(3, {"reason": "CUT"}))
                    )
                )
                out, err = io.StringIO(), io.StringIO()
                stack.enter_context(contextlib.redirect_stdout(out))
                stack.enter_context(contextlib.redirect_stderr(err))
                code = main(args)
                self.assertEqual(code, 2)
                self.assertIn("CONFIG_INVALID", out.getvalue() + err.getvalue())
                self.assertNotIn("synthetic-private-marker", out.getvalue() + err.getvalue())
                for effect in effects:
                    effect.assert_not_called()
                self.assertFalse((self.root / "state").exists())
                if "--json" in args:
                    self.assertFalse(json.loads(out.getvalue())["dashboard_ready"])
