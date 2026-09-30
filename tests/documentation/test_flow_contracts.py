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


    def test_replan_distinguishes_receipts_qualification_and_new_work(self):
        architecture = document("MVP_Architecture")
        rules = section(architecture, "### 6.3. Replan, rezultate întârziate și obligații stabile")
        for token in ["M1", "M2", "ResultQualification", "STOPPING", "RedeliveryKey",
                      "ExecutionKey", "CoveragePromiseRevision", "bootstrap_budget_ref",
                      "phase_key", "subphase_key", "instance_id"]:
            self.assertTrue(token in rules, f"Missing adaptive invariant: {token}")
        self.assertNotIn("Orice role/revision/input străin sau stale blochează consumul.", architecture)
        plan = document("Implementation_Plan")
        focused = re.findall(r"(?m)^\| P-FOCUS \| ([^|]+) \|", plan)
        self.assertEqual(focused, ["P5a+P6a, P-LOOP"])
        self.assertIn("ResultQualification", document("UI_UX_Spec"))


    def test_auxiliary_admission_gates_precede_first_use(self):
        plan = document("Implementation_Plan")
        rows = re.findall(r"(?m)^\| G-RESEARCH / B10c \|.*$", plan)
        self.assertEqual(len(rows), 1)
        self.assertIn("G-DATA-EARLY-RESEARCH", rows[0])
        self.assertNotIn("+ G-DATA +", rows[0])
        for token in ["G-HERMES-BOUND-CORE", "B14c.1", "B14c.2", "G-DATA-EARLY-MAINTENANCE"]:
            self.assertIn(token, plan)
        contexts = section(document("MVP_Architecture"), "### 9.7. Emitent și context înainte de primul copil")
        self.assertIn("MAINTENANCE_JOB", contexts)
        self.assertIn("MaintenanceSnapshot", contexts)


    def test_delivery_guide_and_runtime_flow_are_in_the_canonical_plan(self):
        plan = document("Implementation_Plan")
        flow = section(plan, "### 2.1. Fluxul operațional și livrarea lui")
        self.assertEqual(re.findall(r"(?m)^\| (RF\d{2}) \|", flow), [f"RF{i:02d}" for i in range(1, 13)])
        guide = section(plan, "### 4.2. Subfelii: ce păstrăm, modificăm și introducem")
        rows = [line for line in guide.splitlines() if re.match(r"^\| SL\d{2} \|", line)]
        ids = [row.split("|")[1].strip() for row in rows]
        self.assertEqual(ids, [f"SL{i:02d}" for i in range(1, 37)])
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(len(cells), 6, row)
            self.assertTrue(all(cells), row)
        closure = section(plan, "### 4.3. Închiderea milestone-urilor, fără scurtături")
        for gate in ["G-MODEL", "G-FOCUS", "G-RESEARCH", "G-WORDLIST", "G-IMPROVE", "G-HERMES-BOUND", "G08"]:
            self.assertIn(gate, closure)


    def test_wordlist_core_does_not_require_its_future_consumer(self):
        plan = document("Implementation_Plan")
        stage = re.findall(r"(?m)^\| P-WORDLIST \|.*$", plan)
        self.assertEqual(len(stage), 1)
        self.assertIn("G-WORDLIST-CORE", stage[0])
        core = re.findall(r"(?m)^\| G-WORDLIST-CORE / B10d \|.*$", plan)
        integrated = re.findall(r"(?m)^\| G-WORDLIST / B15 \|.*$", plan)
        self.assertEqual(len(core), 1)
        self.assertEqual(len(integrated), 1)
        self.assertIn("fără target IO", core[0])
        self.assertNotIn("randament", core[0])
        self.assertIn("randament", integrated[0])
        self.assertIn("G-WORDLIST-CORE", integrated[0])


if __name__ == "__main__":
    unittest.main()
