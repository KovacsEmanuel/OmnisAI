"""Pure/no-effect controls for the one-off preservation recipe."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

RECIPE = Path(__file__).with_name("s1-logical-preserve.py")


class RecipeTest(unittest.TestCase):
    def test_restore_exact_owner_and_one_shot_before_ddl(self):
        spec = importlib.util.spec_from_file_location("preserve", RECIPE)
        if spec is None or spec.loader is None:
            self.fail("recipe loader missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = module.OUTPUT / "r/fixture.json"
        foreign = module.OUTPUT / "foreign-task/fixture.json"
        alias = module.OUTPUT / "r/../r/fixture.json"
        runtime, owner = mock.Mock(), mock.Mock()
        runtime.receipt.docker_id = "inert-daemon"
        owner.attest_fixture.return_value = {"container_id": "a" * 64}
        values: dict[Path, object] = {path: {"daemon_id": "inert-daemon"} for path in (fixture, foreign, alias)}
        values[module.OUTPUT / "archive-manifest.json"] = {"hashes": {}}
        owner_record = module.OUTPUT / "fixture-owner.json"
        claim = module.OUTPUT / "restore-claim.json"
        with (
            mock.patch.object(module, "helpers", return_value=(mock.Mock(return_value=runtime), owner)),
            mock.patch.object(module, "read", side_effect=lambda path, *args: module.json.dumps(values[path]).encode()),
            mock.patch.dict(module.os.environ, {"OMNIS_TEST_DB_PASSWORD": "inert"}, clear=True),
            mock.patch.object(module.os, "open") as opened,
            mock.patch.object(module.os, "fdopen") as fdopen,
            mock.patch.object(module.os, "fsync") as fsync,
            mock.patch.object(module.os, "close"),
            mock.patch.object(module, "native_file", side_effect=AssertionError("native forbidden")) as native,
        ):
            fdopen.return_value.__enter__.return_value.fileno.return_value = 11
            expected_opens = [
                mock.call(claim, module.os.O_CREAT | module.os.O_EXCL | module.os.O_WRONLY | module.os.O_NOFOLLOW, 0o600),
                mock.call(module.OUTPUT, module.os.O_RDONLY | module.os.O_DIRECTORY),
            ]

            def run(*args, **kwargs):
                if kwargs.get("effect"):
                    self.assertEqual(opened.call_args_list, expected_opens)
                    self.assertEqual(fsync.call_args_list, [mock.call(11), mock.call(12)])
                    raise RuntimeError("DDL_BOUNDARY")
                return mock.Mock(stdout="0")

            runtime.run.side_effect = run
            for supplied, recorded in ((foreign, foreign), (fixture, foreign), (alias, fixture)):
                with self.subTest(supplied=str(supplied), recorded=str(recorded)):
                    module.os.environ["OMNIS_TEST_FIXTURE"] = str(supplied)
                    values[owner_record] = {"fixture": str(recorded)}
                    runtime.run.reset_mock()
                    with self.assertRaisesRegex(ValueError, "RESTORE_FIXTURE_BINDING"):
                        module.restore()
                    runtime.run.assert_not_called()
                    opened.assert_not_called()

            module.os.environ["OMNIS_TEST_FIXTURE"] = str(fixture)
            values[owner_record] = {"fixture": str(fixture)}
            opened.side_effect = [11, 12, FileExistsError("claim already consumed")]
            runtime.run.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "DDL_BOUNDARY"):
                module.restore()
            owner.attest_fixture.assert_called_with(fixture)
            self.assertEqual(runtime.run.call_args.args[-1], "CREATE ROLE omnis NOLOGIN")
            written = fdopen.return_value.__enter__.return_value.write.call_args.args[0]
            self.assertEqual(module.json.loads(written), {"one_shot": True, "fixture": str(fixture), "cid": "a" * 64})
            runtime.run.reset_mock()
            with self.assertRaises(FileExistsError):
                module.restore()
            self.assertEqual(opened.call_args, expected_opens[0])
            runtime.run.assert_not_called()
            native.assert_not_called()

    def test_copy_oracle_and_denials(self):
        self.assertTrue(RECIPE.is_file(), "current-schema recipe is missing")
        spec = importlib.util.spec_from_file_location("preserve", RECIPE)
        if spec is None or spec.loader is None:
            self.fail("recipe loader missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        first = b"COPY public.table2 (id, payload) FROM stdin;\n2\tx\\ny\n1\t\\N\n\\.\n"
        reordered = b"COPY public.table2 (id, payload) FROM stdin;\n1\t\\N\n2\tx\\ny\n\\.\n"
        self.assertEqual(module.copy_projection(first), module.copy_projection(reordered))
        self.assertNotEqual(module.copy_projection(first), module.copy_projection(first.replace(b"x", b"z")))
        self.assertEqual(module.copy_projection(first)["tables"]["public.table2"]["count"], 2)
        quoted = first.replace(b"payload", b'"grant"')
        expected = module.copy_projection(first)
        expected["tables"]["public.table2"]["columns"] = 'id, "grant"'
        self.assertEqual(module.copy_projection(quoted), expected)
        self.assertNotEqual(module.copy_projection(quoted), module.copy_projection(quoted.replace(b'"grant"', b"grant")))
        for malformed in (b'"grant', b'grant"', b'""grant""', b'""', b'"gr"ant"'):
            with self.subTest(column=malformed), self.assertRaisesRegex(ValueError, "UNSUPPORTED_COPY_HEADER"):
                module.copy_projection(first.replace(b"payload", malformed))
        for invalid in (first[:-4], first + first, first.replace(b"public.table2", b"other.table2")):
            with self.assertRaises(ValueError):
                module.copy_projection(invalid)
        schema = b"-- PostgreSQL database dump\n\\restrict abc\nALTER TABLE public.t OWNER TO omnis;\n\\unrestrict abc\n"
        self.assertEqual(module.schema_bytes(schema), module.schema_bytes(schema.replace(b"abc", b"xyz")))
        self.assertNotEqual(module.schema_bytes(schema), module.schema_bytes(schema.replace(b"omnis", b"other")))
        endpoint = "unix:///owned-test.sock"
        command = ["docker", "--host", endpoint, "rm", "-f", "a" * 64]
        self.assertEqual(module.cleanup_command(command, endpoint), command[:4] + [command[5]])
        self.assertEqual(module.cleanup_command(["docker", "info"], endpoint), ["docker", "info"])
        for invalid in (command[:5] + [module.CIDS["db"]], command[:5] + ["foreign-name"], command + ["--volumes"]):
            with self.assertRaises(ValueError):
                module.cleanup_command(invalid, endpoint)


if __name__ == "__main__":
    unittest.main(verbosity=2)
