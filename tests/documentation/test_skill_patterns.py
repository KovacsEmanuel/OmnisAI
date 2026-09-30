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


if __name__ == "__main__":
    unittest.main()
