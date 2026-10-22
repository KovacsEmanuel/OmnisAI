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


def active_resume(readme, status, old_prompt):
    assert readme.count("**CURRENT —") == 1
    current = readme.split("**CURRENT —", 1)[1].split("\n\n", 1)[0]
    assert "T0" in current and "cinci contracte aprobate" in current
    assert "T1 nu a început" in current
    assert "promptul nu autorizează lansarea" in current
    assert "nu relua joburile Codex/openfix/P2" in current
    assert "unicul CURRENT din README" in status
    assert "ISTORIC / NEEXECUTABIL" in old_prompt
    assert "nu autorizează reluarea" in old_prompt


class ResumeStatusTests(unittest.TestCase):
    def sources(self):
        return [(ROOT / path).read_text(encoding="utf-8") for path in (
            "README.md", "CONTRIBUTING.md", "documents/Omnis_Implementation_Plan.md",
        )]

    def test_current_resume_does_not_reopen_accepted_slices(self):
        current_resume_markers(*self.sources())

    def test_single_current_and_historical_retirement(self):
        sources = [(ROOT / p).read_text() for p in (
            "README.md", "documents/verification/implementation-status.md",
            "documents/verification/p2-next-session-implementation.md")]
        active_resume(*sources)
        for index, old, new in (
            (0, "T1 nu a început", "începe implementarea"),
            (0, "promptul nu autorizează lansarea", "lansează developerul"),
            (0, "nu relua joburile Codex/openfix/P2", "reia openfix"),
            (2, "ISTORIC / NEEXECUTABIL", "ACTIV"),
        ):
            with self.subTest(marker=old):
                changed = sources.copy()
                changed[index] = changed[index].replace(old, new)
                with self.assertRaises(AssertionError):
                    active_resume(*changed)
        with self.assertRaises(AssertionError):
            active_resume(sources[0] + "\n**CURRENT — reia jobul vechi**", *sources[1:])

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
