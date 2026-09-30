"""Cross-contract flow checks; not execution, inference or safety certification."""
import re
import unittest

from test_amendment_contracts import document, section


class FlowContracts(unittest.TestCase):
    def test_model_admission_is_delivered_before_first_live_call(self):
        architecture = document("MVP_Architecture")
        model = section(architecture, "### 5.2. Model admission înainte de inferență")
        for token in ["B06m", "ModelDispatch", "RESERVED", "SENT", "UNKNOWN",
                      "retry", "fallback", "VALIDATION", "G-MODEL", "B07"]:
            self.assertTrue(token in model, f"Missing model contract: {token}")
        plan = document("Implementation_Plan")
        self.assertLess(plan.index("**B06m / G-MODEL**"), plan.index("## 8. P4a"))
        live = re.findall(r"(?m)^\| P2-live \|.*$", plan)
        self.assertEqual(len(live), 1)
        self.assertIn("G-MODEL", live[0])
        owner = re.findall(r"(?m)^\| `policy/` \|.*$", architecture)
        self.assertEqual(len(owner), 1)
        self.assertIn("B06m", owner[0])


    def test_pre_run_checks_and_brain_have_honest_authority_contexts(self):
        architecture = document("MVP_Architecture")
        contexts = section(architecture, "### 9.7. Emitent și context înainte de primul copil")
        for token in ["RUN_TASK", "BRAIN_TURN", "OPERATOR_CHECK", "LOGIN_VERIFY",
                      "HEALTH_CHECK", "CheckReceipt", "cancel_epoch", "fără copil fictiv",
                      "snapshot_ref", "mission_ref", "G-AUTH-HTTP"]:
            self.assertTrue(token in contexts, f"Missing execution context rule: {token}")
        invocation = re.findall(r"(?m)^\| `ToolInvocation` \|.*$", architecture)
        self.assertEqual(len(invocation), 1)
        self.assertIn("context: ExecutionContext", invocation[0])
        ui = document("UI_UX_Spec")
        self.assertIn("Cancel check", ui)
        self.assertIn("OPERATOR_CHECK", document("Implementation_Plan"))


    def test_candidate_evaluation_precedes_publish_and_step_outputs_are_typed(self):
        architecture = document("MVP_Architecture")
        evaluation = section(architecture, "### 9.8. Evaluarea candidatului și publicarea fără ciclu")
        for token in ["CandidateSnapshot", "PACKAGE_EVAL", "CONTRACT_PROBE", "ASSESSMENT",
                      "STATIC_PASS", "PURE_PASS", "FIXTURE_PASS", "EvaluationReceipt",
                      "același digest", "operatorul unic", "autorul AI"]:
            self.assertTrue(token in evaluation, f"Missing evaluation rule: {token}")
        package = section(architecture, "### 9.4. Catalog: pachet, tehnică și procedură")
        for token in ["StepOutputRef", "STEP_OUTPUT", "output_name", "ciclu", "bound_procedure_ref"]:
            self.assertTrue(token in package, f"Missing step binding: {token}")
        self.assertIn("CandidateSnapshot", document("Implementation_Plan"))
        self.assertIn("candidatul", document("UI_UX_Spec"))


if __name__ == "__main__":
    unittest.main()
