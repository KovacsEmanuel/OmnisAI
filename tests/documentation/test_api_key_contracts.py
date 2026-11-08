"""Approved API-key contracts: documentary guards, not runtime certification."""
import json
import re
import unittest

from test_amendment_contracts import DOCS, document, section


def runtime_contract(text):
    operation = section(text, "## 5. Runtime API-key-only și autoritatea execuției")
    fields = {
        "SystemOperationV1": ("operation_id", "command_id", "payload_digest", "config_snapshot_ref",
                              "instance_id", "generation", "owner_epoch", "cancel_epoch", "deadline",
                              "PENDING", "RUNNING", "STOPPING", "FINISHED", "NEEDS_RECONCILIATION"),
        "RuntimeTaskAttemptV2": ("run_id", "task_id", "attempt_id", "role", "capability_ids", "fencing_epoch"),
    }
    for name, required in fields.items():
        rows = re.findall(rf"(?m)^\| `{name}` \|[^\n]+$", operation)
        assert len(rows) == 1, name
        for token in required:
            assert token in rows[0], (name, token)
    for token in ("system_operation", "nu un managed-run fictiv", "409", "receive-only",
                  "InstanceControl → lease/fence → conexiune → operație → ledger → dispatch"):
        assert token in operation, token
    dispatch = section(text, "### 5.2. Model admission înainte de inferență")
    for token in ("ModelDispatchV2", "SYSTEM_OPERATION", "RUN", "SENT", "UNKNOWN",
                  "payload final", "conexiuni reutilizate", "fără retry/fallback implicit",
                  "300", "G-MODEL"):
        assert token in dispatch, token
    vault = section(text, "### 8.1. Stocare criptată comună și transfer write-only")
    for token in ("AEAD", "cheie master", "LOCKED", "write-only", "fsync", "DB",
                  "revocare", "backup", "same-UID", "niciodată regenerată automat"):
        assert token in vault, token
    selection = section(text, "### 5.3. Selecția modelelor, consum și HOLD")
    for token in ("ModelSelectionSnapshotV2", "MONITOR", "fără plafon total LLM",
                  "BRAIN", "INVESTIGATOR", "VALIDATOR", "HOLD", "reluare manuală",
                  "fără rezervă financiară VALIDATION", "limitele target"):
        assert token in selection, token
    outcome = section(text, "### 5.4. Outcome și API")
    for token in ("ModelOutcomeV2", "requested", "observed", "INCOMPLETE", "UNKNOWN",
                  "TRUNCATED", "cost_observed", "cost_estimate", "nu se adună"):
        assert token in outcome, token
    compatibility = section(text, "### 5.5. Distribuție și compatibilitate")
    for token in ("instanță separată", "receive-only", "0001–0013", "NOT_RUN",
                  "fără reluarea", "licențe", "Hermes/Codex"):
        assert token in compatibility, token


def t2_functional_core(text):
    """Guard the admitted delivery boundary, not runtime capability or parity."""
    contract = section(text, "### 7.2. Contract de portare pe consumer — S1–S7")
    required = {
        "S1-UX": ("SR08", "Activity", "Agents", "inspector"),
        "S1-core": ("stagn", "UNKNOWN"),
        "S2a": ("SR04", "SR05", "OPERATOR_CHECK", "identity"),
        "S2b": ("OBLIGATORIU_S7", "browser", "SANDBOX_EXEC", "G-NET"),
        "S3a": ("SR01", "SR02", "Brain", "brief"),
        "S3b": ("S2b", "browser", "provenien"),
        "S4a": ("SR03", "SR09", "D13", "D14", "D03"),
        "S4b": ("SR09", "HTML/JSON", "claim_revision", "AVAILABLE"),
        "S5": ("SR06", "G-LOOP", "consum", "UNKNOWN"),
        "S6": ("ShopShfere", "autonom", "D03"),
        "S7": ("S2b", "S3b", "S4b", "S5", "NOT_RUN"),
    }
    rows = re.findall(r"(?m)^\| (S[1-7][a-z]?(?:-[A-Za-z]+)?) \|(.+)$", contract)
    assert len(rows) == len(required), "unique consumer rows"
    assert {key for key, _ in rows} == set(required), "complete consumer inventory"
    for key, row in rows:
        assert len(row.split("|")) == 6, (key, "producer/reuse/consumer/check/exit columns")
        for token in required[key]:
            assert token in row, (key, token)
    assert "A = DEFERRED_BY_OPERATOR" in contract
    assert "nu blochează S7" in contract
    assert "nu certifică paritatea" in contract


class ApiKeyContracts(unittest.TestCase):
    def test_runtime_contracts_have_real_roots_and_truthful_outcomes(self):
        runtime_contract(document("MVP_Architecture"))

    def test_missing_authority_secret_or_monitoring_guard_is_detected(self):
        original = document("MVP_Architecture")
        runtime_contract(original)
        for marker in ("config_snapshot_ref", "niciodată regenerată automat",
                       "fără plafon total LLM", "conexiuni reutilizate", "cost_observed"):
            with self.subTest(marker=marker), self.assertRaises(AssertionError):
                runtime_contract(original.replace(marker, "REMOVED_GUARD"))

    def test_sandbox_is_execution_capability_not_prompt_permission(self):
        tools = section(document("MVP_Architecture"), "### 9.6. Unelte reale și invocări atribuite")
        for token in ("SANDBOX_EXEC", "shell", "workspace", "fără Docker socket",
                      "promptul nu acordă", "Stop", "G-TOOLS"):
            self.assertIn(token, tools)

    def test_product_library_is_admitted_s0_isolated_and_legacy_is_not_active(self):
        baseline = json.loads((DOCS / "Omnis_Stack_Baseline.versions.json").read_text())
        policy = baseline["api_key_runtime"]
        self.assertEqual(policy["providers"], ["OpenRouter", "OrcaRouter"])
        self.assertEqual(policy["agent_library"]["package"], "openai-agents")
        self.assertEqual(policy["agent_library"]["status"], "ADMITTED_S0_ISOLATED")
        self.assertEqual(policy["agent_library"]["selected_version"], "0.19.0")
        self.assertEqual(policy["client_package"], "openai")
        self.assertEqual(policy["client_selected_version"], "2.45.0")
        self.assertEqual(policy["operator_environment"], "NOT_SYNCED")
        self.assertEqual(policy["runtime_s1"], "NOT_IMPLEMENTED_NOT_STARTED_NOT_ADMITTED")
        self.assertEqual(policy["llm_accounting"], "MONITOR")
        self.assertEqual(baseline["runtimes"]["hermes"]["product_scope"], "LEGACY_ONLY")

    def test_lab_uses_triage_and_validator_without_trusting_imported_skills(self):
        lab = section(document("MVP_Architecture"), "### 11.0. M-LAB — IDOR/BOLA, triage și validator")
        for token in ("TriageAssessmentV1", "orchestratorului", "QUARANTINED",
                      "CANDIDATE_SOURCE_PENDING", "never redact", "first-party",
                      "vulnerable/fixed/benign", "auth-invalid", "PACKAGE_EVAL",
                      "nu este CONFIRMED", "nu întregul MVP/M1"):
            self.assertIn(token, lab)

    def test_delivery_lab_and_hold_are_in_plan_ui_and_readiness(self):
        plan = document("Implementation_Plan")
        first = section(plan, "## 8. T1 — Settings și Test model independent")
        for token in ("system_operation", "fără engagement", "G-MODEL", "LOCKED",
                      "readback", "T2", "nu tool loop"):
            self.assertIn(token, first)
        lab = section(plan, "## 11. T4 — M-LAB IDOR/BOLA cu triage și validator")
        for token in ("triage", "CANDIDATE_SOURCE_PENDING", "PACKAGE_EVAL",
                      "fixed", "benign", "auth-invalid", "T5", "nu întregul MVP"):
            self.assertIn(token, lab)
        for name in ("Implementation_Plan", "UI_UX_Spec", "Implementation_Readiness_Review"):
            text = document(name)
            for token in ("API-key-only", "M-LAB", "HOLD", "MONITOR"):
                self.assertIn(token, text, (name, token))

    def test_post_migration_product_and_ui_roadmap_reuses_existing_slices(self):
        plan = section(document("Implementation_Plan"), "### 15.1. După migrare — funcționalități, skills, tooluri și UI")
        for token in ("nu finalul produsului", "IDOR/BOLA", "triage", "validator",
                      "T5", "T6", "E1–E4", "shell", "df17a29", "acord separat",
                      "Nu amânăm usability", "sursă/licență/digest"):
            self.assertIn(token, plan)
        ui = section(document("UI_UX_Spec"), "### 7.1. Evoluția UI după migrare")
        for token in ("§15.1", "T1", "T4", "T5", "T6", "unknown/stale", "Stop"):
            self.assertIn(token, ui)

    def test_t2_requires_the_complete_core_but_keeps_first_finding_intermediate(self):
        t2_functional_core(document("Implementation_Plan"))

    def test_t2_cannot_silently_drop_browser_reports_or_manual_pairing_disposition(self):
        original = document("Implementation_Plan")
        t2_functional_core(original)
        for token in ("OBLIGATORIU_S7", "A = DEFERRED_BY_OPERATOR", "| S4b |"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                t2_functional_core(original.replace(token, "REMOVED_REQUIREMENT"))


if __name__ == "__main__":
    unittest.main()
