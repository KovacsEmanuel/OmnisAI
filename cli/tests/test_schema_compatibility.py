"""Exact current-schema admission; old schema remains an explicit update boundary."""

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from omnis_cli.instance import InvalidInstance, load_instance
from omnis_cli.lifecycle import StartError

start = importlib.import_module("omnis_cli.start")


class SchemaCompatibilityTest(unittest.TestCase):
    def test_database_identity_accepts_only_0010(self):
        identity = str(uuid4())
        queries = {
            "SELECT system_identifier FROM pg_control_system()": "12345",
            "SELECT instance_id FROM instance_control WHERE id = 1": identity,
            "SELECT version_num FROM alembic_version": "0010_catalog_publications",
        }

        def psql(ident, query):
            self.assertEqual(ident, "private-db")
            self.assertTrue(query.startswith("SELECT "))
            return queries[query]

        runtime = SimpleNamespace(psql=psql)
        self.assertEqual(start.database_identity(runtime, "private-db"), ("12345", identity))
        for previous in ("0009_catalog_candidates", "0008_engagement_edit"):
            queries["SELECT version_num FROM alembic_version"] = previous
            with self.assertRaises(StartError) as error:
                start.database_identity(runtime, "private-db")
            self.assertEqual(
                (error.exception.reason, error.exception.code), ("SCHEMA_UPDATE_REQUIRED", 3)
            )

    def test_private_instance_accepts_only_0010(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            record = {
                "version": 1,
                "instance_id": str(uuid4()),
                "release": "0.1.0",
                "schema": "0010_catalog_publications",
                "project": "omnis-local-1",
                "origin": "http://127.0.0.1:8765",
            }
            path = root / "instance.json"
            path.write_text(json.dumps(record))
            path.chmod(0o600)
            self.assertEqual(load_instance(root).schema, "0010_catalog_publications")
            for previous in ("0009_catalog_candidates", "0008_engagement_edit"):
                record["schema"] = previous
                path.write_text(json.dumps(record))
                before = path.read_bytes()
                with self.assertRaises(InvalidInstance):
                    load_instance(root)
                self.assertEqual(path.read_bytes(), before)
