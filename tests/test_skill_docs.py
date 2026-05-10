import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillDocsTests(unittest.TestCase):
    def test_skill_mentions_state_inventory_and_targeted_conformance(self):
        text = (ROOT / ".agents" / "skills" / "model-first-function-flow" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("state write inventory", text)
        self.assertIn("multiple production write points", text)
        self.assertIn("adoption-start", text)
        self.assertIn("docs/framework_upgrade_checks.md", text)
        self.assertIn("process-design work", text)
        self.assertIn("structured writing/argument", text)
        self.assertIn("decision/planning work", text)
        self.assertIn("behavior_flow", text)
        self.assertIn("argument_flow", text)
        self.assertIn("decision_flow", text)
        self.assertIn("defined terms", text)
        self.assertIn("commitments made", text)
        self.assertIn("process_preflight", text)
        self.assertIn("booking or purchase flows", text)
        self.assertIn("risk-discovery", text)
        self.assertIn("If no model exists", text)
        self.assertIn("shortest script", text)
        self.assertIn("living design artifacts", text)
        self.assertIn("Post-Runtime Model-Miss Review", text)
        self.assertIn("model-miss review trigger", text)
        self.assertIn("finding ledger", text)
        self.assertIn("point rule", text)
        self.assertIn("A later green runtime check by itself does", text)
        self.assertIn("risk-intent-template", text)
        self.assertIn("model-miss-template", text)
        self.assertNotIn("Phase 11", text)
        self.assertNotIn("2100-case", text)

    def test_framework_rules_remain_in_reference_doc(self):
        text = (ROOT / "docs" / "framework_upgrade_checks.md").read_text(encoding="utf-8")

        self.assertIn("real_model_cases: 2100", text)
        self.assertIn("model_variant_total: 150", text)
        self.assertIn("benchmark_conformance_family_count = 25", text)
        self.assertIn("ordinary project", text)

    def test_modeling_protocol_links_state_inventory(self):
        text = (ROOT / "docs" / "modeling_protocol.md").read_text(encoding="utf-8")

        self.assertIn("state write inventory", text)
        self.assertIn("multiple production write", text)
        self.assertIn("model-level confidence only", text)
        self.assertIn("Create Or Evolve The Model Script", text)
        self.assertIn("fit for the customer's risk", text)
        self.assertIn("Handle Post-Runtime Model Misses", text)
        self.assertIn("finding ledger", text)
        self.assertIn("point-rule patches", text)
        self.assertIn("A later green runtime check does not close a known model miss by itself", text)
        self.assertIn("risk-intent-template", text)
        self.assertIn("model-miss-template", text)


if __name__ == "__main__":
    unittest.main()
