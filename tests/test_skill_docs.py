import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "model-first-function-flow"


class SkillDocsTests(unittest.TestCase):
    def test_skill_kernel_is_compact_router_with_hard_gates(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        line_count = len(text.splitlines())

        self.assertLess(line_count, 220)
        self.assertIn("FlowGuard Skill Kernel", text)
        self.assertIn("use_flowguard", text)
        self.assertIn("skip_with_reason", text)
        self.assertIn("needs_human_review", text)
        self.assertIn("behavior_flow", text)
        self.assertIn("argument_flow", text)
        self.assertIn("decision_flow", text)
        self.assertIn("real package", text)
        self.assertIn("fake mini-framework", text)
        self.assertIn("Skipped is not", text)
        self.assertIn("peer-agent changes", text)
        self.assertIn("Input x State -> Set(Output x State)", text)
        self.assertIn("Helper APIs Are Not Sub-Skills", text)
        self.assertIn("RiskIntent", text)
        self.assertIn("review_test_mesh()", text)
        self.assertIn("review_structure_mesh()", text)
        self.assertNotIn("Phase 11", text)
        self.assertNotIn("2100-case", text)

    def test_skill_kernel_routes_to_subprotocols(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        expected_routes = (
            "core_modeling",
            "model_mesh_maintenance",
            "test_mesh_maintenance",
            "structure_mesh_maintenance",
            "model_miss_review",
            "conformance_adoption",
            "long_check_observability",
            "framework_upgrade",
        )
        expected_refs = (
            "references/skill_kernel_protocol.md",
            "references/modeling_protocol.md",
            "references/model_mesh_protocol.md",
            "references/test_mesh_protocol.md",
            "references/structure_mesh_protocol.md",
            "references/model_miss_protocol.md",
            "references/conformance_adoption_protocol.md",
            "references/long_check_protocol.md",
            "references/framework_upgrade_protocol.md",
        )
        for route in expected_routes:
            self.assertIn(route, text)
        for reference in expected_refs:
            self.assertIn(reference, text)
        self.assertIn("parent/child test hierarchy", text)

    def test_core_modeling_protocol_keeps_state_inventory_and_mesh_links(self):
        text = (ROOT / "docs" / "modeling_protocol.md").read_text(encoding="utf-8")

        self.assertIn("state write inventory", text)
        self.assertIn("multiple production write", text)
        self.assertIn("model-level confidence only", text)
        self.assertIn("Create Or Evolve The Model Script", text)
        self.assertIn("fit for the customer's risk", text)
        self.assertIn("Check The Local Model Mesh Trigger", text)
        self.assertIn("three or more local FlowGuard models", text)
        self.assertIn("Check The TestMesh Trigger", text)
        self.assertIn("parent/child hierarchy mesh", text)
        self.assertIn("child suites or child test scripts", text)
        self.assertIn("docs/test_evidence_mesh.md", text)
        self.assertIn("Check The StructureMesh Trigger", text)
        self.assertIn("docs/structure_mesh.md", text)

    def test_agents_snippet_uses_kernel_route_map(self):
        text = (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8")

        self.assertIn("Hard gates", text)
        self.assertIn("Route map", text)
        self.assertIn("core_modeling", text)
        self.assertIn("test_mesh_maintenance", text)
        self.assertIn("tests split into child suites/scripts", text)
        self.assertIn("structure_mesh_maintenance", text)
        self.assertIn("model_miss_review", text)
        self.assertIn("long_check_observability", text)
        self.assertIn("framework_upgrade", text)
        self.assertIn("same-class", text)
        self.assertIn("generalized bad case", text)
        self.assertIn("A later green runtime check by itself does not close", text)
        self.assertIn("not standalone sub-skills", text)

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

    def test_framework_rules_remain_in_reference_doc(self):
        text = (ROOT / "docs" / "framework_upgrade_checks.md").read_text(encoding="utf-8")

        self.assertIn("real_model_cases: 2100", text)
        self.assertIn("model_variant_total: 150", text)
        self.assertIn("benchmark_conformance_family_count = 25", text)
        self.assertIn("ordinary project", text)

    def test_existing_mesh_protocol_references_exist(self):
        model_mesh = (SKILL_ROOT / "references" / "model_mesh_protocol.md").read_text(encoding="utf-8")
        test_mesh = (SKILL_ROOT / "references" / "test_mesh_protocol.md").read_text(encoding="utf-8")
        structure_mesh = (SKILL_ROOT / "references" / "structure_mesh_protocol.md").read_text(encoding="utf-8")

        self.assertIn("Local Model Mesh Protocol", model_mesh)
        self.assertIn("Required Hazards", model_mesh)
        self.assertIn("TestMesh Protocol", test_mesh)
        self.assertIn("test-side sibling of ModelMesh and StructureMesh", test_mesh)
        self.assertIn("child test scripts", test_mesh)
        self.assertIn("become its own parent gate", test_mesh)
        self.assertIn("Routine And Release Scope", test_mesh)
        self.assertIn("StructureMesh Protocol", structure_mesh)
        self.assertIn("dependency cycle", structure_mesh)

    def test_new_skill_kernel_protocol_references_exist(self):
        kernel = (SKILL_ROOT / "references" / "skill_kernel_protocol.md").read_text(encoding="utf-8")
        model_miss = (SKILL_ROOT / "references" / "model_miss_protocol.md").read_text(encoding="utf-8")
        conformance = (SKILL_ROOT / "references" / "conformance_adoption_protocol.md").read_text(encoding="utf-8")
        long_check = (SKILL_ROOT / "references" / "long_check_protocol.md").read_text(encoding="utf-8")
        framework = (SKILL_ROOT / "references" / "framework_upgrade_protocol.md").read_text(encoding="utf-8")

        self.assertIn("FlowGuard Skill Kernel Protocol", kernel)
        self.assertIn("Helper APIs Are Not Sub-Skills", kernel)
        self.assertIn("Post-Runtime Model-Miss Protocol", model_miss)
        self.assertIn("boundary_missing", model_miss)
        self.assertIn("Generalized case", model_miss)
        self.assertIn("Conformance And Adoption Protocol", conformance)
        self.assertIn("shadow workspace", conformance)
        self.assertIn("Long Check Observability Protocol", long_check)
        self.assertIn("<name>.exit.txt", long_check)
        self.assertIn("final report sections as live progress", long_check)
        self.assertIn("Framework Upgrade Protocol", framework)
        self.assertIn("risk-to-model coverage matrix", framework)
        self.assertIn("representative bad variants must fail", framework)


if __name__ == "__main__":
    unittest.main()
