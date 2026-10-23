"""Exact current-schema admission; old schema remains an explicit update boundary."""

import ast
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
    def test_installed_topology_assertion_matches_actual_migration_head(self):
        root = Path(__file__).resolve().parents[2]
        revisions, parents = set(), set()
        for path in (root / "api/src/omnis/migrations/versions").glob("*.py"):
            for node in ast.parse(path.read_bytes()).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    if node.targets[0].id == "revision":
                        revisions.add(ast.literal_eval(node.value))
                    elif node.targets[0].id == "down_revision":
                        parents.add(ast.literal_eval(node.value))
        self.assertEqual(revisions - parents, {start.EXPECTED_SCHEMA})
        tree = ast.parse((root / "cli/integration/control_topology.py").read_bytes())
        checks: list[ast.stmt] = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Raise)
                and "Installed migration revision mismatch" in ast.unparse(child)
                for child in node.body
            )
        ]
        self.assertEqual(len(checks), 1)
        code = compile(ast.Module(body=checks, type_ignores=[]), "topology-schema", "exec")
        env: dict[str, object] = {
            key: None for key in ("host", "release", "project", "empty_env", "env")
        }
        env["EXPECTED_SCHEMA"] = start.EXPECTED_SCHEMA
        for revision in (
            start.EXPECTED_SCHEMA,
            "0014_provider_settings",
            "0013_mission_revisions",
            "synthetic_incompatible",
        ):
            env["_psql"] = lambda *args, revision=revision: revision
            if revision == start.EXPECTED_SCHEMA:
                exec(code, env)
            else:
                with self.assertRaisesRegex(
                    AssertionError, "Installed migration revision mismatch"
                ):
                    exec(code, env)

    def test_installed_start_negative_restores_schema_even_on_failure(self):
        root = Path(__file__).resolve().parents[2]
        tree = ast.parse((root / "cli/integration/installed_start.py").read_bytes())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_installed_start"
        )
        body = next(node for node in function.body if isinstance(node, ast.Try)).body
        first = next(
            index
            for index, node in enumerate(body)
            if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "db"
        )
        last = next(index for index in range(first, len(body)) if isinstance(body[index], ast.Try))
        code = compile(
            ast.Module(body=body[first : last + 1], type_ignores=[]), "start-schema", "exec"
        )

        def exercise(fail):
            schema = start.EXPECTED_SCHEMA
            queries = []

            def psql(db, query):
                nonlocal schema
                self.assertEqual(db, "private-db")
                queries.append(query)
                if query.startswith("UPDATE alembic_version SET version_num="):
                    schema = query.split("'")[1]
                else:
                    self.assertEqual(query, "SELECT version_num FROM alembic_version")
                    return schema

            def invoke(argv, expected):
                self.assertEqual(schema, "synthetic_incompatible")
                if fail:
                    raise RuntimeError("synthetic negative interrupted")
                return {"reason": "SCHEMA_UPDATE_REQUIRED"}

            env = {
                "runtime": SimpleNamespace(psql=psql),
                "record": {"containers": {"db": "private-db"}},
                "invoke": invoke,
                "EXPECTED_SCHEMA": start.EXPECTED_SCHEMA,
            }
            if fail:
                with self.assertRaisesRegex(RuntimeError, "synthetic negative interrupted"):
                    exec(code, env)
            else:
                exec(code, env)
            self.assertEqual(schema, start.EXPECTED_SCHEMA)
            self.assertGreaterEqual(queries.count("SELECT version_num FROM alembic_version"), 2)

        exercise(False)
        exercise(True)

    def test_database_identity_accepts_only_0014(self):
        identity = str(uuid4())
        queries = {
            "SELECT system_identifier FROM pg_control_system()": "12345",
            "SELECT instance_id FROM instance_control WHERE id = 1": identity,
            "SELECT version_num FROM alembic_version": "0015_model_test_v2",
        }

        def psql(ident, query):
            self.assertEqual(ident, "private-db")
            self.assertTrue(query.startswith("SELECT "))
            return queries[query]

        runtime = SimpleNamespace(psql=psql)
        self.assertEqual(start.database_identity(runtime, "private-db"), ("12345", identity))
        for previous in (
            "0014_provider_settings",
            "0013_mission_revisions",
            "0012_contract_methods",
            "0011_managed_tasks",
            "0010_catalog_publications",
            "0009_catalog_candidates",
            "0008_engagement_edit",
        ):
            queries["SELECT version_num FROM alembic_version"] = previous
            with self.assertRaises(StartError) as error:
                start.database_identity(runtime, "private-db")
            self.assertEqual(
                (error.exception.reason, error.exception.code), ("SCHEMA_UPDATE_REQUIRED", 3)
            )

    def test_private_instance_accepts_only_0015(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            record = {
                "version": 1,
                "instance_id": str(uuid4()),
                "release": "0.1.0",
                "schema": "0015_model_test_v2",
                "project": "omnis-local-1",
                "origin": "http://127.0.0.1:8765",
            }
            path = root / "instance.json"
            path.write_text(json.dumps(record))
            path.chmod(0o600)
            self.assertEqual(load_instance(root).schema, "0015_model_test_v2")
            for previous in (
                "0014_provider_settings",
                "0013_mission_revisions",
                "0012_contract_methods",
                "0011_managed_tasks",
                "0010_catalog_publications",
                "0009_catalog_candidates",
                "0008_engagement_edit",
            ):
                record["schema"] = previous
                path.write_text(json.dumps(record))
                before = path.read_bytes()
                with self.assertRaises(InvalidInstance):
                    load_instance(root)
                self.assertEqual(path.read_bytes(), before)
