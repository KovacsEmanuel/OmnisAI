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


if __name__ == "__main__":
    unittest.main()
