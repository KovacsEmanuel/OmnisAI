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


if __name__ == "__main__":
    unittest.main()
