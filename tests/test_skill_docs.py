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


if __name__ == "__main__":
    unittest.main()
