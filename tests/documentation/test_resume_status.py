"""Resume markers preserve historical snapshots; no product acceptance claim."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def current_resume_markers(readme, contributing, plan):
    assert "SL04 nu este încă acceptat integral" not in readme
    assert "**Experiență instalată — CLOSED_SCOPED local:**" in readme
    assert "G00 local este CLOSED_SCOPED; CI remote rămâne separat" in contributing
    assert "Snapshot istoric al inventarului inițial" in plan
    assert "**§19.1 este un snapshot istoric" in plan
    assert "### 19.2. Următoarea felie implementabilă" in plan


class ResumeStatusTests(unittest.TestCase):
    def sources(self):
        return [(ROOT / path).read_text(encoding="utf-8") for path in (
            "README.md", "CONTRIBUTING.md", "documents/Omnis_Implementation_Plan.md",
        )]

    def test_current_resume_does_not_reopen_accepted_slices(self):
        current_resume_markers(*self.sources())

    def test_old_sl04_verdict_is_detected(self):
        sources = self.sources()
        current_resume_markers(*sources)
        sources[0] += "\nSL04 nu este încă acceptat integral\n"
        with self.assertRaises(AssertionError):
            current_resume_markers(*sources)

    def test_missing_history_markers_are_detected(self):
        sources = self.sources()
        current_resume_markers(*sources)
        for marker in ("Snapshot istoric al inventarului inițial", "**§19.1 este un snapshot istoric"):
            with self.subTest(marker=marker):
                changed = sources.copy()
                changed[2] = changed[2].replace(marker, "Inventar fără calificarea temporală")
                with self.assertRaises(AssertionError):
                    current_resume_markers(*changed)


if __name__ == "__main__":
    unittest.main()
