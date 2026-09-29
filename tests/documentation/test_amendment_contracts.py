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

    def test_package_and_child_contracts_are_typed_and_run_pinned(self):
        architecture = document("MVP_Architecture")
        packages = section(architecture, "### 9.4. Catalog: pachet, tehnică și procedură")
        briefing = section(architecture, "### 9.5. PromptBundleRevision, TaskBriefV1 și TaskResultV1")
        for contract in ["SkillPackageRevision", "TechniqueRevision", "ProcedureRevision"]:
            self.assertRegex(packages, rf"\| `{contract}` \|[^\n]+schema_version[^\n]+revision")
        for token in ["omnis.yaml", "references/technologies/", "templates/procedures/",
                      "baseline", "probe", "control", "cleanup", "false_positives",
                      "Draft → Review → Eval → Publish", "symlink", "methodology-only"]:
            self.assertIn(token, packages)
        for contract in ["PromptBundleRevision", "TaskBriefV1", "TaskResultV1"]:
            self.assertRegex(briefing, rf"\| `{contract}` \|[^\n]+schema_version")
        for token in ["RuntimeBinding", "mandatory", "auth_epoch", "result_schema_ref",
                      "consumed_input_refs", "UNKNOWN", "system prefix"]:
            self.assertIn(token, briefing)
        self.assertIn("UI14", document("Implementation_Plan"))
        self.assertIn("UI15", document("Implementation_Plan"))

    def test_real_tools_have_attribution_and_reuse_not_auto_verdicts(self):
        tools = section(document("MVP_Architecture"), "### 9.6. Unelte reale și invocări atribuite")
        for contract in ["ToolDefinition", "ToolInvocation", "ToolResult"]:
            self.assertRegex(tools, rf"\| `{contract}` \|[^\n]+schema_version")
        for token in ["zero sau mai multe", "Action", "Instalat", "permis",
                      "parser", "UNKNOWN", "fencing", "secret", "hardware"]:
            self.assertIn(token, tools)
        stack = document("Stack_Baseline")
        for component in ["Katana", "Nuclei", "Schemathesis", "typesafe-sdk",
                          "compile_plan", "repeatingDetector", "S01", "M09", "HM08"]:
            self.assertIn(component, stack)
        self.assertNotIn("Katana/Nuclei/sqlmap nu sunt dependențe baseline", stack)
        self.assertIn("UI16", document("Implementation_Plan"))

    def test_adaptive_loop_is_separate_from_first_finding(self):
        architecture = document("MVP_Architecture")
        for heading in ["### 5.1. Jev DecisionAdvisor", "### 6.1. Bucla de investigație condusă de Brain",
                        "### 6.2. Module versionate, research și improvement"]:
            self.assertTrue(heading in architecture, f"Missing normative heading: {heading}")
        plan = document("Implementation_Plan")
        for token in ["G-LOOP", "G-PATH", "G-AUTH-HTTP", "G-JEV", "G-MODULE",
                      "G-RESEARCH", "G-WORDLIST", "G-IMPROVE", "G-HERMES-BOUND"]:
            self.assertIn(token, plan)
        self.assertIn("Research este opțional", architecture)
        self.assertIn("nu prerechizit al primului finding", architecture)
        self.assertIn("WAITING_FOR_RUNTIME_SLOT", architecture)

    def test_amendment_matrix_and_comparison_cover_all_requirements(self):
        plan = document("Implementation_Plan")
        ids = re.findall(r"^\| (HF\d{2}) \|", plan, re.M)
        self.assertEqual(ids, [f"HF{i:02d}" for i in range(1, 11)])
        comparison = section(plan, "### Protocol comparativ Omnis–Strix")
        for token in ["held-out", "benign", "FOCUSED_TEST", "cauze-rădăcină",
                      "ratări", "FP", "replay", "cost", "latență", "intervenții",
                      "marja", "fără superioritate"]:
            self.assertTrue(token in comparison, f"Missing comparison criterion: {token}")
        for wave in ["E1", "E2", "E3", "E4"]:
            self.assertRegex(plan, rf"(?m)^\| {wave} \|")


if __name__ == "__main__":
    unittest.main()
