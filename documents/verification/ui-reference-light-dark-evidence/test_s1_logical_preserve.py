"""Pure/no-effect controls for the one-off preservation recipe."""
import importlib.util
from pathlib import Path
import unittest

RECIPE = Path(__file__).with_name("s1-logical-preserve.py")


class RecipeTest(unittest.TestCase):
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
