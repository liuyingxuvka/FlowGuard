import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "model-first-function-flow"
SATELLITE_SKILLS = {
    "flowguard-model-test-alignment": "model_test_alignment_protocol.md",
    "flowguard-development-process-flow": "development_process_flow_protocol.md",
    "flowguard-model-miss-review": "model_miss_protocol.md",
    "flowguard-code-structure-recommendation": "code_structure_recommendation_protocol.md",
    "flowguard-ui-flow-structure": "ui_flow_structure_protocol.md",
    "flowguard-model-mesh": "model_mesh_protocol.md",
    "flowguard-test-mesh": "test_mesh_protocol.md",
    "flowguard-structure-mesh": "structure_mesh_protocol.md",
}


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
        self.assertIn("review_model_test_alignment()", text)
        self.assertIn("audit_python_code_contracts()", text)
        self.assertIn("audit_python_test_assertions()", text)
        self.assertIn("review_python_contract_source_audit()", text)
        self.assertIn("Standalone Satellite Skills", text)
        self.assertIn("flowguard-model-test-alignment", text)
        self.assertIn("flowguard-development-process-flow", text)
        self.assertIn("flowguard-ui-flow-structure", text)
        self.assertNotIn("Phase 11", text)
        self.assertNotIn("2100-case", text)

    def test_skill_kernel_routes_to_subprotocols(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        expected_routes = (
            "core_modeling",
            "code_structure_recommendation",
            "ui_flow_structure",
            "model_test_alignment",
            "model_mesh_maintenance",
            "test_mesh_maintenance",
            "structure_mesh_maintenance",
            "development_process_flow",
            "model_miss_review",
            "conformance_adoption",
            "long_check_observability",
            "framework_upgrade",
        )
        expected_refs = (
            "references/skill_kernel_protocol.md",
            "references/modeling_protocol.md",
            "references/code_structure_recommendation_protocol.md",
            "references/model_test_alignment_protocol.md",
            "references/model_mesh_protocol.md",
            "references/test_mesh_protocol.md",
            "references/structure_mesh_protocol.md",
            "references/development_process_flow_protocol.md",
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
        self.assertIn("ordinary test evidence", text)
        self.assertIn("parent reattachment gate", text)
        self.assertIn("affected sibling review", text)

    def test_standalone_satellite_skills_exist_with_references(self):
        skills_root = ROOT / ".agents" / "skills"

        for skill_name, reference_name in SATELLITE_SKILLS.items():
            with self.subTest(skill=skill_name):
                skill_root = skills_root / skill_name
                skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
                openai_yaml = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
                reference_text = (skill_root / "references" / reference_name).read_text(encoding="utf-8")

                self.assertIn(f"name: {skill_name}", skill_text)
                self.assertIn("standalone FlowGuard satellite skill", skill_text)
                self.assertIn("model-first-function-flow", skill_text)
                self.assertIn("real package", skill_text)
                self.assertIn("fake mini-framework", skill_text)
                self.assertIn("Non-Goals", skill_text)
                self.assertIn(skill_name, openai_yaml)
                self.assertGreater(len(reference_text), 200)

    def test_satellite_skills_keep_distinct_ownership(self):
        skills_root = ROOT / ".agents" / "skills"
        expectations = {
            "flowguard-model-test-alignment": (
                "review_model_test_alignment",
                "Do not invoke TestMesh",
            ),
            "flowguard-development-process-flow": (
                "review_development_process_flow",
                "does not inspect",
            ),
            "flowguard-model-miss-review": (
                "boundary_missing",
                "same-class generalized bad case",
                "parent reattachment gate",
            ),
            "flowguard-code-structure-recommendation": (
                "review_code_structure_recommendation",
                "FunctionBlock-to-module ownership",
            ),
            "flowguard-ui-flow-structure": (
                "review_ui_interaction_model",
                "UI event x UI state",
                "UIDisplayElement",
            ),
            "flowguard-model-mesh": (
                "review_hierarchical_mesh",
                "Required Hazards",
                "Child Reattachment Gate",
            ),
            "flowguard-test-mesh": (
                "review_test_mesh",
                "child test scripts",
            ),
            "flowguard-structure-mesh": (
                "review_structure_mesh",
                "dependency cycle",
            ),
        }

        for skill_name, phrases in expectations.items():
            with self.subTest(skill=skill_name):
                skill_root = skills_root / skill_name
                combined = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in (skill_root / "SKILL.md", *sorted((skill_root / "references").glob("*.md")))
                )
                for phrase in phrases:
                    self.assertIn(phrase, combined)

    def test_development_process_flow_triggers_for_staged_validation_work(self):
        skills_root = ROOT / ".agents" / "skills"
        satellite_root = skills_root / "flowguard-development-process-flow"
        kernel_root = skills_root / "model-first-function-flow"
        texts = "\n".join(
            (
                (satellite_root / "SKILL.md").read_text(encoding="utf-8"),
                (satellite_root / "agents" / "openai.yaml").read_text(encoding="utf-8"),
                (satellite_root / "references" / "development_process_flow_protocol.md").read_text(encoding="utf-8"),
                (kernel_root / "SKILL.md").read_text(encoding="utf-8"),
                (kernel_root / "references" / "modeling_protocol.md").read_text(encoding="utf-8"),
                (kernel_root / "references" / "development_process_flow_protocol.md").read_text(encoding="utf-8"),
                (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8"),
                (ROOT / "docs" / "development_process_flow.md").read_text(encoding="utf-8"),
                (ROOT / "README.md").read_text(encoding="utf-8"),
            )
        )

        self.assertIn("non-trivial staged development or modification", texts)
        self.assertIn("plan, edit, test, fix, and verify", texts)
        self.assertIn("touched artifacts", texts)
        self.assertIn("minimum revalidation", texts)
        self.assertIn("tiny typo fix", texts)
        self.assertIn("done/release/archive/publish", texts)
        self.assertIn("does not inspect", texts)
        self.assertNotIn("light_lifecycle_preflight", texts)
        self.assertNotIn("full_evidence_freshness_review", texts)

    def test_skill_kernel_has_soft_generic_oversize_hint(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        snippet = (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8")
        kernel = (SKILL_ROOT / "references" / "skill_kernel_protocol.md").read_text(encoding="utf-8")
        combined = "\n".join((text, snippet, kernel))

        self.assertIn("consider whether a parent/child split", text)
        self.assertIn("For models consider ModelMesh", text)
        self.assertIn("for tests consider TestMesh", text)
        self.assertIn("for long checks consider", text)
        self.assertIn("consider whether a parent/child split", snippet)
        self.assertIn("short consideration hint", kernel)
        self.assertIn("external planner handoffs remain optional", kernel)

        forbidden = (
            "OpenStack",
            "OpenSpac",
            "OpenSpec",
            "SPAC",
            "must split",
            "required after",
            "fixed runtime threshold",
            "Hierarchy Split Gate",
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, combined)

    def test_user_facing_diagram_guidance_is_lightweight(self):
        skills_root = ROOT / ".agents" / "skills"
        skill_texts = {
            skill_root.name: (skill_root / "SKILL.md").read_text(encoding="utf-8")
            for skill_root in sorted(skills_root.iterdir())
            if skill_root.is_dir()
        }
        kernel = skill_texts["model-first-function-flow"]
        combined = "\n".join(skill_texts.values())

        self.assertIn("default to a user-facing Mermaid", combined)
        self.assertIn("during the work", (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8"))
        self.assertIn("tiny", combined)
        self.assertIn("explain, not validate", kernel)
        self.assertIn("does not count as validation", combined)
        self.assertIn("validation evidence", combined)
        self.assertIn("major states, branches, gates, evidence, claim boundaries", (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8"))
        route_expectations = {
            "flowguard-code-structure-recommendation": ("FunctionBlock-to-module", "validation boundaries"),
            "flowguard-development-process-flow": ("artifact versions", "minimum revalidation"),
            "flowguard-model-mesh": ("what the mesh does or does not prove", "evidence tiers/freshness"),
            "flowguard-model-miss-review": ("observed failure", "same-class generalized bad case"),
            "flowguard-model-test-alignment": ("model obligations", "test evidence"),
            "flowguard-structure-mesh": ("public entrypoints", "facades"),
            "flowguard-test-mesh": ("parent gates", "evidence status"),
            "flowguard-ui-flow-structure": ("visible-control branches", "residual blindspots"),
        }
        for skill_name, phrases in route_expectations.items():
            with self.subTest(skill=skill_name):
                for phrase in phrases:
                    self.assertIn(phrase, skill_texts[skill_name])
        self.assertNotIn("must include a diagram", combined.lower())
        self.assertNotIn("diagram is validation", combined.lower())
        self.assertNotIn("tiny tasks must", combined.lower())

    def test_global_flowguard_routing_prefers_direct_satellites(self):
        kernel = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        snippet = (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8")
        combined = "\n".join((kernel, snippet))

        self.assertIn("use_direct_flowguard_skill", snippet)
        self.assertIn("use_model_first_kernel", snippet)
        self.assertIn("peer routes", combined)
        self.assertIn("matching satellite directly", combined)
        self.assertIn("model-first-function-flow", combined)
        self.assertIn("ordinary behavior/state modeling", combined)
        self.assertIn("unclear route selection", combined)
        self.assertIn("cross-route coordination", combined)

    def test_core_modeling_protocol_keeps_state_inventory_and_mesh_links(self):
        text = (ROOT / "docs" / "modeling_protocol.md").read_text(encoding="utf-8")

        self.assertIn("state write inventory", text)
        self.assertIn("multiple production write", text)
        self.assertIn("model-level confidence only", text)
        self.assertIn("Create Or Evolve The Model Script", text)
        self.assertIn("fit for the customer's risk", text)
        self.assertIn("Check The Local Model Mesh Trigger", text)
        self.assertIn("Check The Model-Test Alignment Trigger", text)
        self.assertIn("Model-Test Alignment is not a mesh route", text)
        self.assertIn("review_model_test_alignment", text)
        self.assertIn("three or more local FlowGuard models", text)
        self.assertIn("Check The TestMesh Trigger", text)
        self.assertIn("parent/child hierarchy mesh", text)
        self.assertIn("child suites or child test scripts", text)
        self.assertIn("docs/test_evidence_mesh.md", text)
        self.assertIn("Check The StructureMesh Trigger", text)
        self.assertIn("docs/structure_mesh.md", text)
        self.assertIn("Check The Code Structure Recommendation Route", text)
        self.assertIn("docs/code_structure_recommendation.md", text)
        self.assertIn("Check The UI Flow Structure Route", text)
        self.assertIn("docs/ui_flow_structure.md", text)
        self.assertIn("Check The DevelopmentProcessFlow Route", text)
        self.assertIn("docs/development_process_flow.md", text)

    def test_agents_snippet_uses_kernel_route_map(self):
        text = (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8")

        self.assertIn("Hard gates", text)
        self.assertIn("Route map", text)
        self.assertIn("core_modeling", text)
        self.assertIn("code_structure_recommendation", text)
        self.assertIn("ui_flow_structure", text)
        self.assertIn("test_mesh_maintenance", text)
        self.assertIn("model_test_alignment", text)
        self.assertIn("does not invoke", text)
        self.assertIn("tests split into child suites/scripts", text)
        self.assertIn("structure_mesh_maintenance", text)
        self.assertIn("development_process_flow", text)
        self.assertIn("model_miss_review", text)
        self.assertIn("long_check_observability", text)
        self.assertIn("framework_upgrade", text)
        self.assertIn("same-class", text)
        self.assertIn("generalized bad case", text)
        self.assertIn("bug-class responsibility", text)
        self.assertIn("affected sibling review", text)
        self.assertIn("in-progress background run", text)
        self.assertIn("A later green runtime check by itself does not close", text)
        self.assertIn("flowguard-model-test-alignment", text)
        self.assertIn("flowguard-development-process-flow", text)
        self.assertIn("flowguard-model-miss-review", text)
        self.assertIn("flowguard-code-structure-recommendation", text)
        self.assertIn("flowguard-ui-flow-structure", text)
        self.assertIn("flowguard-model-mesh", text)
        self.assertIn("flowguard-test-mesh", text)
        self.assertIn("flowguard-structure-mesh", text)
        self.assertIn("package helpers, not", text)

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
        code_structure = (SKILL_ROOT / "references" / "code_structure_recommendation_protocol.md").read_text(encoding="utf-8")
        ui_structure = (
            ROOT
            / ".agents"
            / "skills"
            / "flowguard-ui-flow-structure"
            / "references"
            / "ui_flow_structure_protocol.md"
        ).read_text(encoding="utf-8")
        development_process = (SKILL_ROOT / "references" / "development_process_flow_protocol.md").read_text(encoding="utf-8")

        self.assertIn("Code Structure Recommendation Protocol", code_structure)
        self.assertIn("FunctionBlock-to-module ownership", code_structure)
        self.assertIn("not a mandatory step", code_structure)
        self.assertIn("UI Flow Structure Protocol", ui_structure)
        self.assertIn("UI event x UI state", ui_structure)
        self.assertIn("first-level persistent controls", ui_structure)
        self.assertIn("Local Model Mesh Protocol", model_mesh)
        self.assertIn("Required Hazards", model_mesh)
        self.assertIn("target split derivation", model_mesh)
        self.assertIn("Child Reattachment Gate", model_mesh)
        self.assertIn("child_reattachment_required", model_mesh)
        self.assertIn("current bug instance", model_mesh)
        self.assertIn("Child boundary changes propagate upward", model_mesh)
        self.assertIn("Review affected siblings", model_mesh)
        self.assertIn("Background long-running checks are not pass evidence", model_mesh)
        self.assertIn("TestMesh Protocol", test_mesh)
        self.assertIn("test-side sibling of ModelMesh and StructureMesh", test_mesh)
        self.assertIn("target split derivation", test_mesh)
        self.assertIn("child test scripts", test_mesh)
        self.assertIn("become its own parent gate", test_mesh)
        self.assertIn("Routine And Release Scope", test_mesh)
        self.assertIn("StructureMesh Protocol", structure_mesh)
        self.assertIn("dependency cycle", structure_mesh)
        self.assertIn("Target Structure Derivation", structure_mesh)
        self.assertIn("mandatory for existing", structure_mesh)
        self.assertIn("DevelopmentProcessFlow Protocol", development_process)
        self.assertIn("sibling sub-protocol", development_process)
        self.assertIn("does not inspect", development_process)
        self.assertIn("minimum revalidation", development_process)

    def test_new_skill_kernel_protocol_references_exist(self):
        kernel = (SKILL_ROOT / "references" / "skill_kernel_protocol.md").read_text(encoding="utf-8")
        model_miss = (SKILL_ROOT / "references" / "model_miss_protocol.md").read_text(encoding="utf-8")
        conformance = (SKILL_ROOT / "references" / "conformance_adoption_protocol.md").read_text(encoding="utf-8")
        long_check = (SKILL_ROOT / "references" / "long_check_protocol.md").read_text(encoding="utf-8")
        framework = (SKILL_ROOT / "references" / "framework_upgrade_protocol.md").read_text(encoding="utf-8")

        self.assertIn("FlowGuard Skill Kernel Protocol", kernel)
        self.assertIn("Helper APIs Are Not Sub-Skills", kernel)
        self.assertIn("model_test_alignment", kernel)
        self.assertIn("development_process_flow", kernel)
        self.assertIn("Standalone Satellite Skills", kernel)
        self.assertIn("flowguard-model-mesh", kernel)
        self.assertIn("flowguard-ui-flow-structure", kernel)
        model_test_alignment = (SKILL_ROOT / "references" / "model_test_alignment_protocol.md").read_text(encoding="utf-8")
        self.assertIn("Model-Test Alignment Protocol", model_test_alignment)
        self.assertIn("CodeContract", model_test_alignment)
        self.assertIn("PythonCodeContractEvidence", model_test_alignment)
        self.assertIn("PythonTestAssertionEvidence", model_test_alignment)
        self.assertIn("code external contract", model_test_alignment)
        self.assertIn("covered code contract ids", model_test_alignment)
        self.assertIn("external_contract", model_test_alignment)
        self.assertIn("internal_path", model_test_alignment)
        self.assertIn("conservative source audit", model_test_alignment)
        self.assertIn("function signatures, return values, raises, assignments, and calls", model_test_alignment)
        self.assertIn("missing Python symbol", model_test_alignment)
        self.assertIn("missing input", model_test_alignment)
        self.assertIn("missing output", model_test_alignment)
        self.assertIn("missing state write", model_test_alignment)
        self.assertIn("extra side effect", model_test_alignment)
        self.assertIn("tests must call the declared code contract symbol", model_test_alignment)
        self.assertIn("assert or unittest assertion", model_test_alignment)
        self.assertIn("helper/internal path", model_test_alignment)
        self.assertIn("no assert", model_test_alignment)
        self.assertIn("missing_code_contract", model_test_alignment)
        self.assertIn("code_contract_extra_behavior", model_test_alignment)
        self.assertIn("code_contract_missing_behavior", model_test_alignment)
        self.assertIn("unknown_code_contract_reference", model_test_alignment)
        self.assertIn("does not split tests", model_test_alignment)
        self.assertIn("Do not invoke TestMesh", model_test_alignment)
        self.assertNotIn("review_hierarchical_mesh", model_test_alignment)
        self.assertNotIn("review_test_mesh", model_test_alignment)
        self.assertNotIn("review_structure_mesh", model_test_alignment)
        self.assertIn("Post-Runtime Model-Miss Protocol", model_miss)
        self.assertIn("boundary_missing", model_miss)
        self.assertIn("Generalized case", model_miss)
        self.assertIn("parent child-reattachment gate", model_miss)
        self.assertIn("same-class bug responsibility", model_miss)
        self.assertIn("affected sibling review", model_miss)
        self.assertIn("Progress is not", model_miss)
        self.assertIn("Conformance And Adoption Protocol", conformance)
        self.assertIn("shadow workspace", conformance)
        self.assertIn("Long Check Observability Protocol", long_check)
        self.assertIn("<name>.exit.txt", long_check)
        self.assertIn("final report sections as live progress", long_check)
        self.assertIn("in-progress liveness", long_check)
        self.assertIn("Framework Upgrade Protocol", framework)
        self.assertIn("risk-to-model coverage matrix", framework)
        self.assertIn("representative bad variants must fail", framework)


if __name__ == "__main__":
    unittest.main()
