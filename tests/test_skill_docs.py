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
        self.assertIn("multi-model FlowGuard projects", text)
        self.assertIn("three or more local FlowGuard models", text)
        self.assertIn("model mesh", text)
        self.assertIn("evidence tiers", text)
        self.assertIn("references/model_mesh_protocol.md", text)
        self.assertIn("spec/SPAC", text)
        self.assertIn("upstream handoff", text)
        self.assertIn("must not block standalone FlowGuard use", text)
        self.assertIn("Risk Purpose Header", text)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", text)
        self.assertIn("which concrete bugs or invalid states it", text)
        self.assertIn("tmp/flowguard_background", text)
        self.assertIn("<name>.out.txt", text)
        self.assertIn("<name>.err.txt", text)
        self.assertIn("<name>.combined.txt", text)
        self.assertIn("<name>.exit.txt", text)
        self.assertIn("<name>.meta.json", text)
        self.assertIn("path-only report", text)
        self.assertIn("valid proof", text)
        self.assertIn("final report sections as live progress", text)
        self.assertIn("Pre-Implementation Model Hardening Gate", text)
        self.assertIn("risk-to-model coverage matrix", text)
        self.assertIn("representative bad variants must fail", text)
        self.assertIn("heavy model owns the", text)
        self.assertIn("current-project model names", text)
        self.assertIn("Preserve user and peer-agent changes", text)
        self.assertIn("treat that evidence as stale", text)
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
        self.assertIn("Check The Local Model Mesh Trigger", text)
        self.assertIn("three or more local FlowGuard models", text)
        self.assertIn("model-of-models", text)
        self.assertIn("Risk Purpose Header", text)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", text)

    def test_agents_snippet_carries_risk_purpose_header_rule(self):
        text = (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8")

        self.assertIn("Risk Purpose Header", text)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", text)
        self.assertIn("which concrete bugs or invalid states it", text)
        self.assertIn("no external planning", text)
        self.assertIn("tmp/flowguard_background", text)
        self.assertIn("<name>.exit.txt", text)
        self.assertIn("final report sections as live progress", text)
        self.assertIn("Pre-Implementation Model Hardening Gate", text)
        self.assertIn("risk-to-model coverage matrix", text)
        self.assertIn("A happy-path pass is not enough", text)
        self.assertIn("current-project model names", text)
        self.assertIn("Preserve user and peer-agent changes", text)

    def test_skill_orchestrator_collaboration_doc_defends_standalone_mode(self):
        text = (ROOT / "docs" / "skill_orchestrator_collaboration.md").read_text(encoding="utf-8")

        self.assertIn("Standalone mode", text)
        self.assertIn("Collaboration mode", text)
        self.assertIn("Fallback mode", text)
        self.assertIn("must remain fully useful without any external spec, SPAC", text)
        self.assertIn("H01", text)
        self.assertIn("side effects", text)
        self.assertIn("parallel ownership", text)
        self.assertIn("completion evidence", text)

    def test_model_mesh_protocol_reference_exists(self):
        text = (
            ROOT
            / ".agents"
            / "skills"
            / "model-first-function-flow"
            / "references"
            / "model_mesh_protocol.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Local Model Mesh Protocol", text)
        self.assertIn("three or more local FlowGuard models", text)
        self.assertIn("evidence tiers", text)
        self.assertIn("Prompt Template", text)
        self.assertIn("Required Hazards", text)


if __name__ == "__main__":
    unittest.main()
