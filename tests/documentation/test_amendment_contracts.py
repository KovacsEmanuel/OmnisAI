"""Normative amendment consistency; never runtime or G00 certification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"


def document(name):
    return (DOCS / f"Omnis_{name}.md").read_text(encoding="utf-8")


def section(text, heading):
    """Read this repo's column-zero ATX sections, never fenced examples."""
    lines = text.splitlines(keepends=True)
    headings = []
    fence = None
    for index, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", stripped)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        if re.fullmatch(r"#{1,3} .+", stripped):
            headings.append((index, stripped))
    matches = [index for index, title in headings if title == heading]
    if len(matches) != 1:
        raise AssertionError(f"Expected one normative heading: {heading}; found {len(matches)}")
    start = matches[0]
    end = next((index for index, _ in headings if index > start), len(lines))
    return "".join(lines[start + 1:end]).rstrip("\r\n")


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

    def test_source_manifest_units_and_ui_rows_resolve_in_canon(self):
        import json
        import markdown

        reuse = json.loads((DOCS / "verification/omnis-modularity-research-supplement.reuse.json").read_text())
        inventory = json.loads((DOCS / "verification/omnis-upgrade-review.inventory.json").read_text())
        stack = document("Stack_Baseline")
        ids = re.findall(r"^\| ((?:S|M|R|HM)\d{2}) \|", stack, re.M)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {unit["id"] for unit in reuse["units"]})
        self.assertEqual(len(ids), reuse["unit_count"])
        refs = [ref for unit in reuse["units"] for ref in unit["source_refs"] + unit["upstream_tests"]]
        self.assertEqual(len(refs), reuse["source_reference_count"])
        for unit in reuse["units"]:
            self.assertRegex(unit["revision"], r"^[0-9a-f]{40}$")
            self.assertIn(unit["revision"], stack)
            self.assertIn(unit["destination_proposed"], stack)
        for ref in refs:
            self.assertRegex(ref["file_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(ref["fragment_sha256"], r"^[0-9a-f]{64}$")
            self.assertLessEqual(ref["lines"][0], ref["lines"][1])
        files = inventory["strix_knowledge"]["files"]
        self.assertEqual(len({item["path"] for item in files}), len(files))
        self.assertEqual(sum(item["kind"] == "guide" for item in files), inventory["strix_knowledge"]["guides"])
        self.assertEqual(sum(item["category"] == "vulnerabilities" for item in files), inventory["strix_knowledge"]["vulnerability_guides"])
        plan = document("Implementation_Plan")
        breadth = plan.split("**Dispoziție exhaustivă a breadthului, fără scheduling inventat:**", 1)[1].split("În starea actuală", 1)[0]
        declared_guides = re.findall(r"`([a-z_]+)`", breadth)
        expected_guides = [Path(item["path"]).stem for item in files if item["category"] == "vulnerabilities"]
        self.assertCountEqual(declared_guides, expected_guides)
        rendered = markdown.markdown(plan, extensions=["tables", "fenced_code"])
        self.assertEqual(re.findall(r"<td>(UI\d{2})</td>", rendered), [f"UI{i:02d}" for i in range(1, 24)])

    def test_review_corrections_define_resolvable_contracts(self):
        architecture = document("MVP_Architecture")
        packages = section(architecture, "### 9.4. Catalog: pachet, tehnică și procedură")
        briefs = section(architecture, "### 9.5. PromptBundleRevision, TaskBriefV1 și TaskResultV1")
        self.assertIn("outcomes: ProcedureStatus[]", packages)
        self.assertNotIn("outcomes: Key[]", packages)
        for token in ["TemplateRef", "CaseSlotRef", "CaseSlot", "BoundProcedure", "slot_values", "file_bindings"]:
            self.assertIn(token, packages)
        for token in ["criterion_bindings: CriterionBinding[]", "criterion_results: CriterionResult[]"]:
            self.assertIn(token, briefs)
        for token in ["RecordEnvelope", "CanonicalJSON", "TaskResultV1", "nu hash-uri recursive"]:
            self.assertIn(token, section(architecture, "### 9.3. Misiune: general sau focalizat"))
        tools = section(architecture, "### 9.6. Unelte reale și invocări atribuite")
        self.assertIn("artifact: LocalArtifact/ServiceArtifact", tools)
        self.assertIn("attestation_receipt_ref", tools)


class SectionExtractionTests(unittest.TestCase):
    def test_only_actual_normative_headings_are_accepted(self):
        heading = "### 9.3. Misiune: general sau focalizat"
        self.assertEqual(section(heading + "\ncontent\n### Next\nother", heading), "content")
        for text in [f"```markdown\n{heading}\nexample\n```\n",
                     f"~~~\n{heading}\nexample\n~~~\n",
                     f"Quoted text {heading}\nexample\n",
                     f"> {heading}\nexample\n"]:
            with self.subTest(text=text), self.assertRaises(AssertionError):
                section(text, heading)

    def test_fenced_headings_do_not_terminate_a_real_section(self):
        text = "### Real\ntext\n```markdown\n## Example\n```\nkept\n## End\nother"
        self.assertIn("kept", section(text, "### Real"))
        self.assertNotIn("other", section(text, "### Real"))

    def test_duplicate_normative_heading_is_rejected(self):
        with self.assertRaises(AssertionError):
            section("### Real\none\n### Real\ntwo\n", "### Real")


if __name__ == "__main__":
    unittest.main()
