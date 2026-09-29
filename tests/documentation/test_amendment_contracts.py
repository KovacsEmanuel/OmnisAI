"""Normative amendment consistency; never runtime or G00 certification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"


def document(name):
    return (DOCS / f"Omnis_{name}.md").read_text(encoding="utf-8")


def section(text, heading):
    if heading + "\n" not in text:
        raise AssertionError(f"Missing normative heading: {heading}")
    tail = text.split(heading + "\n", 1)[1]
    return re.split(r"\n#{1,3} ", tail, maxsplit=1)[0]


class AmendmentContracts(unittest.TestCase):
    def test_focused_mission_is_a_persisted_inert_setup_contract(self):
        architecture = document("MVP_Architecture")
        mission = section(architecture, "### 9.3. Misiune: general sau focalizat")
        for token in ["FULL_ASSESSMENT", "FOCUSED_TEST", "objective_text",
                      "8192", "MissionSpec", "FocusEnvelope", "append-only",
                      "zero LLM", "deferred-outside-objective", "CriterionOutcome",
                      "Stop", "LIMITED", "denominator_revision"]:
            self.assertIn(token, mission)
        ui = document("UI_UX_Spec")
        for label in ["Evaluare generală / Test focalizat", "Obiectiv / instrucțiuni pentru Brain"]:
            self.assertIn(label, ui)
        plan = document("Implementation_Plan")
        self.assertIn("G-FOCUS", plan)
        self.assertIn("HF01", plan)
        self.assertIn("HF02", plan)
        self.assertIn("HF03", plan)
        self.assertIn("409", mission)
        self.assertIn("nu procent global", mission)


if __name__ == "__main__":
    unittest.main()
