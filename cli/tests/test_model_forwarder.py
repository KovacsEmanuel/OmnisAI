"""SOURCE finite model relay; never resolve or connect to a provider."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli import forwarder
from test_auth_forwarder import hello


class ModelRelayTest(unittest.IsolatedAsyncioTestCase):
    def test_model_allowlist_is_distinct_from_historical_oauth(self):
        for name in ("openrouter.ai", "api.orcarouter.ai"):
            self.assertEqual(forwarder.tls_destination(hello(name), model=True), name)
            with self.assertRaises(ValueError):
                forwarder.tls_destination(hello(name))
        for name in ("auth.openai.com", "chatgpt.com", "example.com", "127.0.0.1"):
            with self.assertRaises(ValueError):
                forwarder.tls_destination(hello(name), model=True)

    async def test_model_relay_boot_is_inert_and_owned_socket_drains(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            root.chmod(0o700)
            with patch("socket.getaddrinfo", side_effect=AssertionError("NO_BOOT_PROVIDER_IO")):
                listener = await forwarder.start_auth_forwarder(root, model=True)
                self.assertTrue((root / "model-egress.sock").is_socket())
                self.assertFalse((root / "auth-egress.sock").exists())
                listener.close()
                await asyncio.wait_for(listener.wait_closed(), 3)
                self.assertFalse((root / "model-egress.sock").exists())
