"""Guardrails for the opt-in installed-control topology probe."""

import os
import socket
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from control_topology import preflight_port, prepare_disposable_postgres, strict_probe_environment


class InstalledControlPreflightTest(unittest.TestCase):
    def test_pg18_bind_root_is_traversable_only_under_private_state(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name) / "state"
            state.mkdir(mode=0o700)
            postgres = prepare_disposable_postgres(state)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(postgres.stat().st_mode), 0o711)
            self.assertEqual(postgres.parent, state)

    def test_foreign_loopback_listener_is_refused_without_docker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as foreign:
            foreign.bind(("127.0.0.1", 0))
            foreign.listen(1)
            port = foreign.getsockname()[1]
            with self.assertRaises(ValueError):
                preflight_port(port)
            self.assertEqual(foreign.getsockname()[1], port)

    def test_ambient_docker_compose_and_libpq_overrides_are_refused(self):
        for key in ("DOCKER_CONTEXT", "COMPOSE_FILE", "PGSERVICE"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "foreign"}):
                with self.assertRaises(ValueError):
                    strict_probe_environment()

    def test_clean_environment_is_allowed(self):
        with patch.dict(
            os.environ,
            {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("DOCKER_", "COMPOSE_", "PG"))
            },
            clear=True,
        ):
            strict_probe_environment()
