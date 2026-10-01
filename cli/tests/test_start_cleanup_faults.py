"""M20: actual cleanup predicate, inventory/daemon seams explicitly substituted."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from omnis_cli.lifecycle import StartError

start = importlib.import_module("omnis_cli.start")


class CleanupFaultTest(unittest.TestCase):
    def attempt(self, fault):
        resources = {"api": True, "supervisor": True, "db": True}
        effects = []
        runtime = SimpleNamespace(uncertain=False, family_drained=True, network=lambda _: None)

        def inventory():
            if fault == "inventory":
                raise StartError("SYNTHETIC_INVENTORY")
            return list(resources)

        def inspect(kind, cid):
            if cid not in resources:
                return None
            return {
                "Config": {"Labels": {"com.docker.compose.service": cid}},
                "State": {"Running": resources[cid]},
            }

        def attest(cid, *args):
            if fault == "identity" and cid == "api":
                raise StartError("SYNTHETIC_IDENTITY")
            return inspect("container", cid)

        def command(*args, **kwargs):
            effects.append(args)
            cid = args[-1]
            if args[:2] == ("container", "stop"):
                resources[cid] = False
            if args[:2] == ("container", "rm"):
                if fault == "removal" and cid == "api":
                    runtime.uncertain = True
                    raise StartError("SYNTHETIC_LOST_ACK")
                resources.pop(cid)

        runtime.ids, runtime.inspect, runtime.attest, runtime.run = (
            inventory,
            inspect,
            attest,
            command,
        )
        with tempfile.TemporaryDirectory(prefix="cf-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            (root / "postgres").mkdir()
            problems = start.cleanup_attempt(runtime, root, root / "control", 48765, None, -1)
            self.assertTrue((root / "postgres").is_dir())
        return resources, effects, problems

    def test_positive_same_cleanup_channel(self):
        resources, effects, problems = self.attempt(None)
        self.assertEqual(resources, {})
        self.assertEqual(problems, [])
        self.assertEqual(len(effects), 6)

    def test_inventory_failure_is_uncertain_without_unattested_effects(self):
        resources, effects, problems = self.attempt("inventory")
        self.assertIn("container inventory", problems)
        self.assertEqual(effects, [])
        self.assertEqual(set(resources), {"api", "supervisor", "db"})

    def test_identity_failure_continues_independent_cleanup_but_preserves_db(self):
        resources, effects, problems = self.attempt("identity")
        self.assertIn("identity", problems)
        self.assertIn("database retained under uncertain writers", problems)
        self.assertEqual(set(resources), {"api", "db"})
        self.assertEqual([args[-1] for args in effects], ["supervisor", "supervisor"])

    def test_removal_lost_ack_continues_independent_cleanup_but_preserves_db(self):
        resources, effects, problems = self.attempt("removal")
        self.assertIn("container removal", problems)
        self.assertIn("daemon outcome uncertain", problems)
        self.assertEqual(set(resources), {"api", "db"})
        self.assertTrue(resources["db"])
        self.assertEqual([args[-1] for args in effects], ["api", "api", "supervisor", "supervisor"])
