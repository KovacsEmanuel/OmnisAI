"""Instruction drift checks; no claim of model enforcement or product acceptance."""
from pathlib import Path
import hashlib
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def direction(agents, runtime, team):
    assert "API-key-only" in agents and "OpenRouter/OrcaRouter" in agents
    assert "T0" in agents and "cinci contracte" in agents
    assert "LEGACY" in runtime
    assert "Do not replace Hermes with another agent framework" not in runtime
    assert "developerul desemnat" in team
    assert "FREEZE" in team and "nu este acceptare" in team


class GovernanceTests(unittest.TestCase):
    def sources(self):
        return [(ROOT / p).read_text() for p in (
            "AGENTS.md", ".hermes/skills/omnis-hermes-runtime/SKILL.md",
            ".hermes/skills/omnis-delivery/templates/team-slice.md")]

    def test_direction_and_ownership(self):
        direction(*self.sources())

    def test_stale_direction_retirement_and_ownership_controls(self):
        sources = self.sources()
        direction(*sources)
        for index, old, new in (
            (0, "API-key-only", "Hermes-only"),
            (1, "LEGACY", "ACTIVE"),
            (2, "developerul desemnat", "autor nedeclarat"),
        ):
            with self.subTest(marker=old):
                changed = sources.copy()
                changed[index] = changed[index].replace(old, new)
                with self.assertRaises(AssertionError):
                    direction(*changed)
        with self.assertRaises(AssertionError):
            direction(sources[0], sources[1] + "Do not replace Hermes with another agent framework", sources[2])

    def test_current_inventory_is_exact_and_qualification_is_snapshot_bound(self):
        manifest = json.loads((ROOT / "tools/development/skills-manifest.json").read_text())
        paths = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / ".hermes/skills").glob("*/SKILL.md")}
        self.assertEqual(manifest["count"], 13)
        self.assertEqual({e["path"] for e in manifest["skills"]}, set(paths))
        for entry in manifest["skills"]:
            self.assertEqual(entry["sha256"], hashlib.sha256(paths[entry["path"]].read_bytes()).hexdigest())
            self.assertIn(entry["native_read"], {"NOT_RUN", "PASS"})
            self.assertIn(entry["scanner_verdict"], {"NOT_RUN", "safe", "BLOCKED"})
            if entry["native_read"] != "NOT_RUN" or entry["scanner_verdict"] != "NOT_RUN":
                self.assertEqual(entry.get("tested_sha256"), entry["sha256"])
                self.assertTrue(entry.get("checked_at_utc"))
                self.assertTrue(entry.get("evidence"), "Native claims need exact-snapshot evidence")

    def test_moved_reference_sibling_links_resolve(self):
        for skill, document, label, target in (
            ("omnis-release-ops", "packaging-platform.md", "startup failure boundaries", "startup-failure-boundaries.md"),
            ("omnis-review-qa", "ipc-process-packaging.md", "private NSS procedure", "private-nss-audit.md"),
        ):
            with self.subTest(document=document):
                source = ROOT / ".hermes/skills" / skill / "references" / document
                link = re.search(r"\[" + re.escape(label) + r"\]\(([^)]+)\)", source.read_text())
                assert link is not None, "Missing moved-reference link"
                destination = (source.parent / link.group(1)).resolve()
                self.assertEqual(destination, source.with_name(target))
                self.assertTrue(destination.is_file())
