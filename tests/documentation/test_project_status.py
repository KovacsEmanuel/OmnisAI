"""The status map is a complete projection, never a competing implementation plan."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "documents/Omnis_Implementation_Plan.md"
STATUS = ROOT / "documents/verification/implementation-status.md"


def rows(text, pattern):
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if re.match(r"^\| " + pattern + r" \|", line)
    ]


class ProjectStatusMapTests(unittest.TestCase):
    def text(self):
        self.assertTrue(STATUS.is_file(), "Missing versioned project-wide status map")
        return STATUS.read_text(encoding="utf-8")

    def test_all_canonical_slices_and_extension_waves_once(self):
        plan = PLAN.read_text(encoding="utf-8")
        text = self.text()
        for pattern in (r"SL\d+", r"E\d+"):
            expected = rows(plan, pattern)
            actual = rows(text, pattern)
            with self.subTest(pattern=pattern):
                self.assertTrue(expected, "Canonical registry must not be empty")
                ids = [row[0] for row in actual]
                self.assertEqual(len(ids), len(set(ids)), "Duplicate status IDs")
                self.assertEqual(set(ids), {row[0] for row in expected})
        phases = {row[0]: row[1].split(";")[0] for row in rows(plan, r"SL\d+")}
        for row in rows(text, r"SL\d+"):
            self.assertEqual(row[1], phases[row[0]], row[0])

    def test_code_proof_review_and_source_are_separate(self):
        for row in rows(self.text(), r"(?:SL\d+|E\d+)"):
            with self.subTest(id=row[0]):
                self.assertEqual(len(row), 8)
                self.assertIn(row[3], {"IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"})
                self.assertIn(row[4], {"PASS_LOCAL_RECORDED", "NOT_RUN", "PARTIAL", "FAIL", "BLOCKED"})
                self.assertIn(row[5], {"APPROVED_SCOPED", "IN_REVIEW", "NOT_REVIEWED", "CHANGES_REQUESTED"})
                self.assertTrue(row[6], "Remaining work/dependency must be explicit")
                self.assertTrue(row[7], "Source/evidence reference required")
                if row[3] == "NOT_IMPLEMENTED":
                    self.assertNotEqual(row[4], "PASS_LOCAL_RECORDED")
                    self.assertNotEqual(row[5], "APPROVED_SCOPED")

    def test_map_preserves_global_limits_and_unscheduled_breadth(self):
        text = self.text()
        for marker in ("G00", "M0", "M1", "M2", "G08", "G-OPS", "G-DATA",
                       "CI remote", "NOT-RUN", "assessment_ready=false", "B21m",
                       "EXECUTION_UNSCHEDULED", "SL03", "SL04", "SK01", "RF",
                       "revizie", "scope", "nu un plan concurent"):
            self.assertIn(marker, text)
        plan = PLAN.read_text(encoding="utf-8")
        unscheduled = plan.split("**METHODOLOGY_ONLY / EXECUTION_UNSCHEDULED**", 1)[1].split("Nu dispar", 1)[0]
        for name in re.findall(r"`([^`]+)`", unscheduled):
            self.assertIn(f"`{name}`", text)

    def test_local_links_resolve(self):
        for target in re.findall(r"\]\(([^)]+)\)", self.text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = target.split("#", 1)[0]
            with self.subTest(target=target):
                self.assertTrue((STATUS.parent / path).is_file())


class ProjectStatusSkillTests(unittest.TestCase):
    def skill(self):
        path = ROOT / ".hermes/skills/omnis-project-status/SKILL.md"
        self.assertTrue(path.is_file(), "Missing project-local handoff skill")
        return path.read_text(encoding="utf-8")

    def test_project_local_skill_has_bounded_trigger_and_two_modes(self):
        text = self.skill()
        self.assertTrue(text.startswith("---\n"))
        metadata, body = text[4:].split("\n---\n", 1)
        description_match = re.search(r'^description: "([^"]+)"$', metadata, re.M)
        assert description_match is not None, "Missing concise skill description"
        description = description_match.group(1)
        self.assertLessEqual(len(description), 60)
        self.assertTrue(description.startswith("Use when "))
        self.assertTrue(description.endswith("."))
        for marker in ("ORIENT", "CLOSE", "read-only", "implementation-status.md",
                       "git status --short --branch", "git rev-parse HEAD",
                       "git diff --cached", "git worktree list", "templates/handoff.md"):
            self.assertIn(marker, body)
        self.assertNotIn("/home/kali", text)
        related = re.search(r"related_skills: \[([^]]+)\]", metadata)
        assert related is not None, "Missing project-local skill links"
        for name in related.group(1).split(","):
            self.assertTrue((ROOT / ".hermes/skills" / name.strip() / "SKILL.md").is_file())

    def test_handoff_cannot_turn_a_summary_into_approval(self):
        text = self.skill()
        for marker in ("snapshot", "scope", "părinte", "NOT_REVIEWED", "IN_REVIEW",
                       "APPROVED_SCOPED", "CHANGES_REQUESTED", "întârziat",
                       "fără commit gol", "nu este enforcement", "nu porni cron"):
            self.assertIn(marker, text)
        template = ROOT / ".hermes/skills/omnis-project-status/templates/handoff.md"
        self.assertTrue(template.is_file())
        body = template.read_text(encoding="utf-8")
        for marker in ("HEAD", "MVP", "post-MVP", "În review", "Aprobat", "Neaprobat",
                       "NOT-RUN", "Următoarea felie", "Scope", "Cleanup"):
            self.assertIn(marker, body)

    def test_real_handoff_has_actual_matrix_without_per_response_cadence(self):
        path = ROOT / ".hermes/skills/omnis-project-status/templates/handoff.md"
        body = path.read_text(encoding="utf-8")
        headers = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in body.splitlines()
            if line.startswith("| Zonă / felie |")
        ]
        self.assertEqual(headers, [[
            "Zonă / felie", "Implementare", "Probe", "Review", "Poziție / pas următor",
        ]])
        for marker in ("direct în chat", "nu înlocuiește matricea", "pentru agenți",
                       "ORIENT", "CLOSE", "fără editări"):
            self.assertIn(marker, body)
        self.assertIn("matrix directly in chat", self.skill())
        self.assertIn("Nu este obligatorie pentru fiecare răspuns scurt", body)
        self.assertIn("milestone", body)
        self.assertNotIn("La finalul fiecărei sarcini Omnis", body)

    def test_delivery_review_and_contributing_route_to_status(self):
        for relative in (".hermes/skills/omnis-delivery/SKILL.md",
                         ".hermes/skills/omnis-review-qa/SKILL.md", "CONTRIBUTING.md"):
            with self.subTest(path=relative):
                self.assertIn("omnis-project-status", (ROOT / relative).read_text(encoding="utf-8"))


class ProductDeliveryFocusTests(unittest.TestCase):
    """Instruction drift checks, not enforcement of future agent behavior."""

    def test_work_admission_and_preflight_are_explicit(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for marker in ("## Execuție orientată spre produs",
                       "cerință → consumer → risc → decizie",
                       "### Preflight fără efecte",
                       "Nu porni un verifier pentru verifier",
                       "comanda/argv", "pozitiv și negativ",
                       "### Continuitate și dovezi"):
            with self.subTest(marker=marker):
                self.assertTrue(marker in text, "Missing execution rule: " + marker)

    def test_existing_skills_use_the_same_execution_contract(self):
        for name in ("omnis-delivery", "omnis-review-qa", "omnis-project-status"):
            text = (ROOT / ".hermes/skills" / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertTrue("CONTRIBUTING.md" in text, "Missing execution contract link: " + name)
                self.assertTrue("Execuție orientată spre produs" in text, "Missing execution contract: " + name)

    def test_historical_p2_prompt_retains_evidence_but_cannot_resume(self):
        path = ROOT / "documents/verification/p2-next-session-implementation.md"
        prompt = path.read_text(encoding="utf-8")
        self.assertIn("ISTORIC / NEEXECUTABIL", prompt)
        self.assertIn("nu autorizează reluarea", prompt)
        for marker in ("DOAR ÎN SESIUNEA FRESH", "HANDOFF_ONLY",
                       "orchestrator", "dezvoltator", "reviewer", "QA",
                       "finite2-coherent-factory-feasibility.json",
                       "cerință → consumer → risc → decizie",
                       "preflight fără efecte", "Nu porni un verifier pentru verifier",
                       "Nu preda după fiecare fix", "BLOCKED/NOT_RUN",
                       "P2-inert", "P4a-minim", "P2-live"):
            with self.subTest(marker=marker):
                self.assertTrue(marker in prompt, "Missing active P2 instruction: " + marker)


if __name__ == "__main__":
    unittest.main()
