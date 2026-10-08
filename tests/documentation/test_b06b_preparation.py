"""Bounded B06b handoff regressions; these do not validate runtime behavior."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "documents/verification/p2-b06b-next-contract.md"


def section(text, heading):
    marker = "## " + heading + "\n"
    assert text.count(marker) == 1, heading
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def publication_owner(text):
    scope = section(text, "Frontiera minimă de cod și reutilizare")
    assert "settings/skill_catalog.py" in scope
    assert "candidate_catalog.py" in scope
    assert "candidate_store.py" in scope


def historical_receive(text):
    body = section(text, "Istoric, calificare și admitere")
    for marker in ("§6.3", "M1", "M2", "REVALIDATION_REQUIRED", "INELIGIBLE",
                   "receive-only", "HELD_FOR_RECONCILIATION", "fără wake/model/dispatch",
                   "payload diferit", "autoritatea curentă"):
        assert marker in body, marker


def record_order(text):
    body = section(text, "Ordinea producătorilor și consumatorilor")
    for marker in ("ExecutionSelection", "NO_MODEL", "ProcedureBinding", "CriterionBinding",
                   "TaskResult persistat → MethodCheck", "fără refs inverse",
                   "delivered", "admitted", "turn_completed", "domain_result_consumed"):
        assert marker in body, marker


def gate_boundaries(text):
    body = section(text, "Gates core versus breadth ulterioară")
    rows = [line for line in body.splitlines() if line.startswith("| H0")]
    assert [line.split("|")[1].strip() for line in rows] == [f"H{i:02d}" for i in range(3, 9)]
    for line in rows:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 3 and all(cells), line
    for marker in ("B06c", "B06m", "P4a", "P2-live", "B18a.r", "CHECK_ONLY",
                   "G-METHOD-core", "G-REVISION-core", "NOT_RUN", "BLOCKED"):
        assert marker in body, marker


def traceability(text):
    body = section(text, "Matrice bounded cerință → owner → probă")
    rows = [line for line in body.splitlines() if re.match(r"^\| C\d{2} \|", line)]
    assert [line.split("|")[1].strip() for line in rows] == [f"C{i:02d}" for i in range(1, 13)]
    for line in rows:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 5 and all(cells), line
        assert "Pozitiv:" in cells[3] and "Negativ:" in cells[3], line


class B06bPreparationTests(unittest.TestCase):
    def text(self):
        return CONTRACT.read_text(encoding="utf-8")

    def test_publish_owner_is_inside_allowed_frontier(self):
        publication_owner(self.text())

    def test_history_is_not_new_admission(self):
        historical_receive(self.text())

    def test_record_order_and_ack_states_are_explicit(self):
        record_order(self.text())

    def test_native_core_is_not_model_gate(self):
        gate_boundaries(self.text())

    def test_each_requirement_has_owner_positive_negative_and_gate(self):
        traceability(self.text())

    def test_changed_producer_cannot_inherit_old_qualification(self):
        body = section(self.text(), "Frontiera minimă de cod și reutilizare")
        for marker in ("BEHAVIOR_FILES", "fingerprint", "artefactul final", "snapshot vechi",
                       "nu eliminăm fișiere din closure", "fixture nouă"):
            self.assertIn(marker, body)

    def test_same_valid_contract_detects_removed_guards(self):
        text = self.text()
        controls = (
            (publication_owner, "settings/skill_catalog.py"),
            (historical_receive, "HELD_FOR_RECONCILIATION"),
            (record_order, "turn_completed"),
            (gate_boundaries, "| H08 |"),
            (traceability, "| C12 |"),
        )
        for validate, marker in controls:
            with self.subTest(marker=marker):
                validate(text)
                self.assertIn(marker, text)
                with self.assertRaises(AssertionError):
                    validate(text.replace(marker, "REMOVED-GUARD"))


if __name__ == "__main__":
    unittest.main()
