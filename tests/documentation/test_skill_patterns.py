"""Original-note pattern guards: documentation only, not runtime gates."""
import re
import unittest

from test_amendment_contracts import DOCS, document, section


class SkillPatternContracts(unittest.TestCase):
    def test_common_recipe_is_not_an_agent_or_a_permission_grant(self):
        architecture = document("MVP_Architecture")
        pattern = section(architecture, "### 9.9. Pattern comun: skill, specializare și execuție")
        for token in ["AgentRecipe", "ExecutionPreference", "ExecutionSelection",
                      "WorkflowProfileRevision", "requested", "effective", "xhig",
                      "allowed_toolsets=()", "Skill ≠ agent", "B06", "G-SKILL"]:
            self.assertIn(token, pattern)
        package = section(architecture, "### 9.4. Catalog: pachet, tehnică și procedură")
        for token in ["verification_kind", "SECURITY", "CONTRACT", "non_applicable_groups",
                      "execution_preference", "work_kind"]:
            self.assertIn(token, package)
        brief = re.findall(r"(?m)^\| `TaskBriefV1` \|.*$", architecture)
        self.assertEqual(len(brief), 1)
        self.assertIn("execution_selection_ref", brief[0])
        self.assertIn("G-SKILL", document("Implementation_Plan"))


    def test_method_review_cannot_replace_validation_or_reset_work(self):
        architecture = document("MVP_Architecture")
        review = section(architecture, "### 9.10. Completitudine metodologică și rework")
        for token in ["MethodRequirement", "MethodPlan", "MethodCheck", "MethodReviewFeedback",
                      "MethodReviewReceipt", "MethodRequirementRef", "BoundPredicateRef",
                      "NOT_APPLICABLE", "NOT_RUN", "REVIEWER", "fără TARGET_IO",
                      "CHECK_ONLY", "INDEPENDENT", "max_rework_rounds", "după G06a",
                      "rezerva VALIDATION", "Stop", "LIMITED", "subject_result_ref"]:
            self.assertIn(token, review)
        brief = re.findall(r"(?m)^\| `TaskBriefV1` \|.*$", architecture)
        result = re.findall(r"(?m)^\| `TaskResultV1` \|.*$", architecture)
        self.assertEqual(len(brief), 1)
        self.assertEqual(len(result), 1)
        for token in ["BoundPredicateRef[]", "MethodRequirementRef[]", "method_plan", "review_request"]:
            self.assertIn(token, brief[0])
        for token in ["method_results", "method_review"]:
            self.assertIn(token, result[0])
        plan = document("Implementation_Plan")
        self.assertRegex(plan, r"(?m)^\| G-METHOD-core / B06b \|.*")
        self.assertRegex(plan, r"(?m)^\| G-METHOD / B18a\.r \|.*după G06a.*")
        self.assertIn("MethodReview", document("UI_UX_Spec"))


    def test_js_and_discovery_examples_keep_sources_and_effects_separate(self):
        architecture = document("MVP_Architecture")
        examples = section(architecture, "### 11.1. Exemple ale patternului: JS și content discovery")
        for token in ["js-analyze", "HISTORICAL", "LAZY_LOADED", "SOURCEMAP",
                      "JsAnalysisArtifactV1", "INFERRED", "PARTIAL", "source_refs",
                      "WordlistProposalV1", "quick_hits", "MODEL", "PURE", "TARGET_IO",
                      "G-WORDLIST-CORE", "G-HISTORY", "G-JS-DEBUG", "B15j.1"]:
            self.assertIn(token, examples)
        stack = section(document("Stack_Baseline"), "### 10.4. Notițe de skills: reutilizare și candidați")
        for token in ["JSLuice", "Waymore", "ffuf", "onelistforall", "CANDIDATE_NOT_ADMITTED"]:
            self.assertIn(token, stack)
        plan = document("Implementation_Plan")
        for gate in ["G-JS", "G-HISTORY", "G-JS-DEBUG"]:
            self.assertIn(gate, plan)
        self.assertIn("JsAnalysisArtifactV1", document("UI_UX_Spec"))


    def test_every_skill_has_an_authoring_route_without_delaying_first_bola(self):
        plan = document("Implementation_Plan")
        route = section(plan, "### 4.4. Cum livrăm orice skill și specializare")
        rows = [line for line in route.splitlines() if re.match(r"^\| SK\d{2} \|", line)]
        self.assertEqual([r.split("|")[1].strip() for r in rows],
                         [f"SK{i:02d}" for i in range(1, 11)])
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(len(cells), 5, row)
            self.assertTrue(all(cells), row)
        decisions = (DOCS / "verification/omnis-skill-pattern-amendment.md").read_text()
        self.assertEqual(re.findall(r"(?m)^\| (NS\d{2}) \|", decisions),
                         [f"NS{i:02d}" for i in range(1, 20)])
        closure = section(plan, "### 4.3. Închiderea milestone-urilor, fără scurtături")
        for gate in ["G-SKILL", "G-METHOD", "G-JS"]:
            self.assertIn(gate, closure)
        dag = section(plan, "### Ordine verificabilă")
        first = re.findall(r"(?m)^\| P5a\+P6a \| ([^|]+) \|", dag)
        self.assertEqual(first, ["P3-auth"])
        self.assertIn("CHECK_ONLY", route)
        self.assertIn("B15j.2", route)
        self.assertIn("B18a.r", route)


if __name__ == "__main__":
    unittest.main()
