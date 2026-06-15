import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
KERNEL_ROOT = SKILLS_ROOT / "model-first-function-flow"

SATELLITE_SKILLS = {
    "flowguard-agent-workflow-rehearsal": "agent_workflow_rehearsal_protocol.md",
    "flowguard-architecture-reduction": "architecture_reduction_protocol.md",
    "flowguard-code-structure-recommendation": "code_structure_recommendation_protocol.md",
    "flowguard-development-process-flow": "development_process_flow_protocol.md",
    "flowguard-existing-model-preflight": "existing_model_preflight_protocol.md",
    "flowguard-field-lifecycle-mesh": "field_lifecycle_mesh_protocol.md",
    "flowguard-model-mesh": "model_mesh_protocol.md",
    "flowguard-model-miss-review": "model_miss_protocol.md",
    "flowguard-model-test-alignment": "model_test_alignment_protocol.md",
    "flowguard-model-topology-hazard-review": "topology_hazard_protocol.md",
    "flowguard-plan-detailing-compiler": "plan_detailing_compiler_protocol.md",
    "flowguard-structure-mesh": "structure_mesh_protocol.md",
    "flowguard-test-mesh": "test_mesh_protocol.md",
    "flowguard-ui-flow-structure": "ui_flow_structure_protocol.md",
}

TEMPLATE_HARVEST_SKILLS = SATELLITE_SKILLS.keys() - {"flowguard-existing-model-preflight"}

KERNEL_HANDOFFS = {
    "model_test_alignment_protocol.md": (
        "flowguard-model-test-alignment",
        "model_test_alignment_protocol.md",
    ),
    "model_mesh_protocol.md": (
        "flowguard-model-mesh",
        "model_mesh_protocol.md",
    ),
    "development_process_flow_protocol.md": (
        "flowguard-development-process-flow",
        "development_process_flow_protocol.md",
    ),
    "test_mesh_protocol.md": (
        "flowguard-test-mesh",
        "test_mesh_protocol.md",
    ),
    "structure_mesh_protocol.md": (
        "flowguard-structure-mesh",
        "structure_mesh_protocol.md",
    ),
    "code_structure_recommendation_protocol.md": (
        "flowguard-code-structure-recommendation",
        "code_structure_recommendation_protocol.md",
    ),
    "model_miss_protocol.md": (
        "flowguard-model-miss-review",
        "model_miss_protocol.md",
    ),
}

REDUCED_FIELD_PROMPT_FILES = (
    SKILLS_ROOT
    / "flowguard-model-test-alignment"
    / "references"
    / "templates"
    / "model_test_alignment_prompt_template.md",
    SKILLS_ROOT
    / "flowguard-development-process-flow"
    / "references"
    / "development_process_flow_protocol.md",
    SKILLS_ROOT / "flowguard-test-mesh" / "references" / "test_mesh_protocol.md",
    SKILLS_ROOT / "model-first-function-flow" / "assets" / "adoption_log_template.md",
)


class SkillDocsTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_hot_path_prompt_budgets_are_enforced(self):
        kernel = self.read(KERNEL_ROOT / "SKILL.md")
        snippet = self.read(ROOT / "docs" / "agents_snippet.md")

        self.assertLessEqual(len(kernel.splitlines()), 130)
        self.assertLessEqual(len(snippet.splitlines()), 110)

        for skill_name in SATELLITE_SKILLS:
            with self.subTest(skill=skill_name):
                text = self.read(SKILLS_ROOT / skill_name / "SKILL.md")
                self.assertLessEqual(len(text.splitlines()), 65)
                self.assertLess(len(text), 3000)

    def test_kernel_is_compact_router_with_reference_handoffs(self):
        text = self.read(KERNEL_ROOT / "SKILL.md")

        expected = (
            "FlowGuard Skill Kernel",
            "use_flowguard",
            "skip_with_reason",
            "needs_human_review",
            "Input x State -> Set(Output x State)",
            "real package",
            "AGENTS.md managed",
            "fake mini-framework",
            "Risk Evidence Ledger",
            "template harvest closure",
            "Route Map",
            "Reference Map",
            "behavior_flow",
            "argument_flow",
            "decision_flow",
            "package helpers, not independently triggerable Codex skills",
        )
        for phrase in expected:
            self.assertIn(phrase, text)

        self.assertLess(text.index("## Minimum Valuable Model"), text.index("## Route Map"))
        for skill_name in SATELLITE_SKILLS:
            self.assertIn(skill_name, text)

        reference_paths = (
            "references/skill_kernel_protocol.md",
            "references/modeling_protocol.md",
            "references/model_test_alignment_protocol.md",
            "references/development_process_flow_protocol.md",
            "references/model_miss_protocol.md",
            "references/conformance_adoption_protocol.md",
            "references/long_check_protocol.md",
            "references/framework_upgrade_protocol.md",
        )
        for reference_path in reference_paths:
            self.assertIn(reference_path, text)

    def test_satellite_skills_are_concise_route_shells(self):
        route_expectations = {
            "flowguard-agent-workflow-rehearsal": (
                "SkillInventorySnapshot",
                "candidate skills",
                "continue/rework gates",
                "real-surface artifact payload proof",
            ),
            "flowguard-architecture-reduction": (
                "ObservableArchitectureContract",
                "contraction candidates",
                "required next route",
            ),
            "flowguard-code-structure-recommendation": (
                "FunctionBlock-to-module ownership",
                "code structure diagram",
                "validation boundaries",
            ),
            "flowguard-development-process-flow": (
                "artifact versions",
                "minimum revalidation",
                "review_auto_mesh_splits",
                "payload schemas",
            ),
            "flowguard-existing-model-preflight": (
                "existing model boundaries",
                "duplicate-boundary",
                "downstream route",
            ),
            "flowguard-field-lifecycle-mesh": (
                "FieldLifecyclePlan",
                "behavior-bearing fields",
                "old-field disposition",
            ),
            "flowguard-model-mesh": (
                "Child Reattachment Gate",
                "mesh diagram",
                "evidence tiers/freshness",
            ),
            "flowguard-model-miss-review": (
                "same-class generalized bad case",
                "root-cause backpropagation",
                "owner code contract",
                "miss-repair diagram",
                "boundary_missing",
            ),
            "flowguard-model-test-alignment": (
                "CodeContract",
                "ArtifactPayloadContract",
                "Full confidence requires",
                "coverage",
                "Do not invoke TestMesh",
            ),
            "flowguard-model-topology-hazard-review": (
                "future-use hazard",
                "topology anchor",
                "Risk Evidence Ledger",
            ),
            "flowguard-plan-detailing-compiler": (
                "PlanDetail",
                "review_plan_detail()",
                "step receipts",
                "payload cases for the real surface",
            ),
            "flowguard-structure-mesh": (
                "public entrypoints",
                "facades",
                "dependency cycles",
            ),
            "flowguard-test-mesh": (
                "child test scripts",
                "validation mesh diagram",
                "parent/child test hierarchy",
                "artifact-payload matrices",
            ),
            "flowguard-ui-flow-structure": (
                "UI event x UI state",
                "UI state diagram",
                "blindspots",
                "reachable enabled action",
            ),
        }

        for skill_name, reference_name in SATELLITE_SKILLS.items():
            with self.subTest(skill=skill_name):
                root = SKILLS_ROOT / skill_name
                text = self.read(root / "SKILL.md")
                openai_yaml = self.read(root / "agents" / "openai.yaml")
                reference = self.read(root / "references" / reference_name)

                self.assertIn(f"name: {skill_name}", text)
                self.assertIn("Standalone FlowGuard satellite skill", text)
                self.assertIn("model-first-function-flow", text)
                self.assertIn("real package", text)
                self.assertIn("AGENTS.md managed", text)
                self.assertIn("fake mini-framework", text)
                if skill_name in TEMPLATE_HARVEST_SKILLS:
                    self.assertIn("harvest closure", text.replace("-harvest", " harvest"))
                self.assertIn("Reference:", text)
                self.assertIn("Non-Goals", text)
                self.assertIn(reference_name, text)
                self.assertIn(skill_name, openai_yaml)
                self.assertGreater(len(reference), 200)
                for phrase in route_expectations[skill_name]:
                    self.assertIn(phrase, text)
                combined = f"{text}\n{reference}"
                self.assertNotIn("fake file/work-package", combined)

    def test_model_test_alignment_skill_does_not_teach_optional_code_contracts(self):
        checked = (
            SKILLS_ROOT / "flowguard-model-test-alignment" / "SKILL.md",
            SKILLS_ROOT / "flowguard-model-test-alignment" / "references" / "model_test_alignment_protocol.md",
            SKILLS_ROOT / "flowguard-model-test-alignment" / "references" / "templates" / "model_test_alignment_prompt_template.md",
            KERNEL_ROOT / "SKILL.md",
            KERNEL_ROOT / "references" / "skill_kernel_protocol.md",
            KERNEL_ROOT / "references" / "model_test_alignment_protocol.md",
        )

        for path in checked:
            with self.subTest(path=path):
                text = self.read(path)
                self.assertNotIn("optional code contracts", text)
                self.assertNotIn("optional code external contracts", text)
                self.assertNotIn("optional external code contracts", text)
                self.assertNotIn("model-test-only", text)

    def test_ui_flow_structure_teaches_soft_typography_handoff(self):
        skill = self.read(SKILLS_ROOT / "flowguard-ui-flow-structure" / "SKILL.md")
        openai_yaml = self.read(SKILLS_ROOT / "flowguard-ui-flow-structure" / "agents" / "openai.yaml")
        protocol = self.read(
            SKILLS_ROOT
            / "flowguard-ui-flow-structure"
            / "references"
            / "ui_flow_structure_protocol.md"
        )

        self.assertIn("calm typography guidance", skill)
        self.assertIn("calm visual handoff guidance", openai_yaml)
        self.assertIn("Visible surface", skill)
        self.assertIn("screenshot", skill)
        self.assertIn("DOM text", skill)
        self.assertIn("evidence kind", skill)
        self.assertIn("semantic hierarchy levels are not a command", protocol)
        self.assertIn("similar jobs", protocol)
        self.assertIn("one-off visual text style", protocol)
        self.assertIn("Visible Surface Review", protocol)
        self.assertIn("disabled control is visible without a reason", protocol)
        self.assertIn("screenshot", protocol)
        self.assertIn("DOM text", protocol)
        self.assertIn("evidence kind", protocol)
        self.assertNotIn("maximum font-size", protocol.lower())
        self.assertNotIn("font size limit", protocol.lower())
        self.assertNotIn("screenshot ban", protocol.lower())
        self.assertNotIn("screenshots are forbidden", protocol.lower())

    def test_kernel_satellite_reference_handoffs_are_compact(self):
        for kernel_reference, (skill_name, satellite_reference) in KERNEL_HANDOFFS.items():
            with self.subTest(reference=kernel_reference):
                stub = self.read(KERNEL_ROOT / "references" / kernel_reference)
                full_reference = self.read(SKILLS_ROOT / skill_name / "references" / satellite_reference)

                self.assertLessEqual(len(stub.splitlines()), 18)
                self.assertIn("compact handoff stub", stub)
                self.assertIn(skill_name, stub)
                self.assertIn(f"{skill_name}/references/{satellite_reference}", stub)
                self.assertGreater(len(full_reference), 200)

    def test_skill_references_do_not_duplicate_canonical_protocols(self):
        seen = {}
        for path in sorted(SKILLS_ROOT.glob("**/references/**/*.md")):
            text = self.read(path).strip()
            if not text:
                continue
            previous = seen.setdefault(text, path)
            self.assertEqual(
                previous,
                path,
                f"{path.relative_to(ROOT)} duplicates {previous.relative_to(ROOT)}",
            )

    def test_long_prompt_templates_are_lazy_loaded(self):
        model_test_alignment = self.read(
            SKILLS_ROOT
            / "flowguard-model-test-alignment"
            / "references"
            / "model_test_alignment_protocol.md"
        )
        model_test_alignment_template = self.read(
            SKILLS_ROOT
            / "flowguard-model-test-alignment"
            / "references"
            / "templates"
            / "model_test_alignment_prompt_template.md"
        )
        model_mesh = self.read(
            SKILLS_ROOT / "flowguard-model-mesh" / "references" / "model_mesh_protocol.md"
        )
        model_mesh_template = self.read(
            SKILLS_ROOT
            / "flowguard-model-mesh"
            / "references"
            / "templates"
            / "model_mesh_prompt_template.md"
        )

        self.assertIn("model_test_alignment_prompt_template.md", model_test_alignment)
        self.assertNotIn("Build a FlowGuard Model-Test Alignment review", model_test_alignment)
        self.assertIn("Build a FlowGuard Model-Test Alignment review", model_test_alignment_template)

        self.assertIn("model_mesh_prompt_template.md", model_mesh)
        self.assertNotIn("Build or update a FlowGuard model mesh", model_mesh)
        self.assertIn("Build or update a FlowGuard model mesh", model_mesh_template)

    def test_model_mesh_closure_liveness_is_documented_across_routes(self):
        model_mesh = self.read(
            SKILLS_ROOT / "flowguard-model-mesh" / "references" / "model_mesh_protocol.md"
        )
        model_mesh_template = self.read(
            SKILLS_ROOT
            / "flowguard-model-mesh"
            / "references"
            / "templates"
            / "model_mesh_prompt_template.md"
        )
        model_test_alignment = self.read(
            SKILLS_ROOT
            / "flowguard-model-test-alignment"
            / "references"
            / "model_test_alignment_protocol.md"
        )
        test_mesh = self.read(SKILLS_ROOT / "flowguard-test-mesh" / "references" / "test_mesh_protocol.md")
        model_miss = self.read(
            SKILLS_ROOT / "flowguard-model-miss-review" / "references" / "model_miss_protocol.md"
        )
        kernel = self.read(KERNEL_ROOT / "references" / "skill_kernel_protocol.md")

        for phrase in (
            "repeat-input tokens",
            "repair feedback",
            "blocker tokens",
            "closure model is required",
            "same packet",
        ):
            self.assertIn(phrase, model_mesh)
        self.assertIn("mesh_closure_required", model_mesh_template)
        self.assertIn("model_mesh_closure_to_transition_coverage", model_test_alignment)
        self.assertIn("happy-path, failure-path, negative-path, and replay", model_test_alignment)
        self.assertIn("model_mesh_closure_to_transition_coverage", test_mesh)
        self.assertIn("repair-feedback/no-delta behavior", test_mesh)
        self.assertIn("repeatedly returns the same packet", model_miss)
        self.assertIn("Model-Test Alignment/TestMesh", model_miss)
        self.assertIn("MODEL_MESH_CLOSURE_RETRY_TEST_KINDS", kernel)

    def test_reduced_field_prompts_use_grouped_families(self):
        model_test_alignment = self.read(
            SKILLS_ROOT
            / "flowguard-model-test-alignment"
            / "references"
            / "model_test_alignment_protocol.md"
        )
        development_process = self.read(
            SKILLS_ROOT
            / "flowguard-development-process-flow"
            / "references"
            / "development_process_flow_protocol.md"
        )
        test_mesh = self.read(SKILLS_ROOT / "flowguard-test-mesh" / "references" / "test_mesh_protocol.md")
        model_mesh = self.read(SKILLS_ROOT / "flowguard-model-mesh" / "references" / "model_mesh_protocol.md")
        adoption_log = self.read(KERNEL_ROOT / "assets" / "adoption_log_template.md")

        for phrase in ("identity", "required evidence", "external boundary", "result:", "freshness:"):
            self.assertIn(phrase, model_test_alignment)
        for phrase in ("Changed artifacts", "Process steps", "Validation evidence", "Freshness rules"):
            self.assertIn(phrase, development_process)
        for phrase in ("Parent gate", "Ownership map", "Child suite evidence", "Target split derivation"):
            self.assertIn(phrase, test_mesh)
        for phrase in ("`model`", "`interface`", "`ownership`", "`evidence`", "`deep_handoff`"):
            self.assertIn(phrase, model_mesh)
        for phrase in ("Task captures", "Artifacts include", "Evidence captures", "Gaps capture"):
            self.assertIn(phrase, adoption_log)

    def test_reduced_field_prompts_do_not_reintroduce_blank_field_lists(self):
        for path in REDUCED_FIELD_PROMPT_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path)
                colon_prompt_lines = [
                    line
                    for line in text.splitlines()
                    if line.strip().startswith("- ") and line.rstrip().endswith(":")
                ]
                self.assertEqual([], colon_prompt_lines)

    def test_current_satellite_topology_has_no_stale_fixed_count_model(self):
        satellite_names = sorted(path.name for path in SKILLS_ROOT.iterdir() if path.name.startswith("flowguard-"))
        topology_model = self.read(ROOT / ".flowguard" / "codex_skill_satellites" / "model.py")

        self.assertEqual(sorted(SATELLITE_SKILLS), satellite_names)
        self.assertIn(f"SATELLITE_COUNT = {len(SATELLITE_SKILLS)}", topology_model)
        self.assertIn("current directly invokable", topology_model)
        self.assertNotIn("seven satellites", topology_model)

    def test_agents_snippet_uses_compact_canonical_route_table(self):
        text = self.read(ROOT / "docs" / "agents_snippet.md")

        expected = (
            "Minimum Valuable Model",
            "Hard Gates",
            "Route Map",
            "Reference Handoff",
            "use_direct_flowguard_skill",
            "use_model_first_kernel",
            "skip_with_reason",
            "needs_human_review",
            "Input x State -> Set(Output x State)",
            "real package",
            "project-adopt",
            "project-upgrade",
            "Risk Evidence Ledger",
            "public/local risk template",
            "template harvest closure",
            "risk-template-harvest-review",
            "Package helpers",
            "not separate Codex skills",
        )
        for phrase in expected:
            self.assertIn(phrase, text)

        self.assertLess(text.index("### Minimum Valuable Model"), text.index("### Route Map"))
        for skill_name in SATELLITE_SKILLS:
            self.assertIn(skill_name, text)

        long_form_markers = (
            "Use Model-Test Alignment when",
            "For ModelMesh and TestMesh",
            "For post-runtime model misses",
            "Treat DevelopmentProcessFlow as another sibling route",
        )
        for marker in long_form_markers:
            self.assertNotIn(marker, text)

    def test_guidance_compression_model_exists(self):
        model = self.read(ROOT / ".flowguard" / "guidance_compression" / "model.py")
        run_checks = self.read(ROOT / ".flowguard" / "guidance_compression" / "run_checks.py")

        self.assertIn("Input x State -> Set(Output x State)", model)
        self.assertIn("no_done_without_full_sync", model)
        self.assertIn("installed skill", model)
        self.assertIn("shadow workspace", model)
        self.assertIn("local git", model)
        self.assertIn("broken_prompt_only_completion", run_checks)

    def test_field_prompt_reduction_model_exists(self):
        model = self.read(ROOT / ".flowguard" / "field_prompt_reduction" / "model.py")
        run_checks = self.read(ROOT / ".flowguard" / "field_prompt_reduction" / "run_checks.py")

        self.assertIn("Input x State -> Set(Output x State)", model)
        self.assertIn("grouped_fields_preserve_required_evidence", model)
        self.assertIn("installed_skills_synced", model)
        self.assertIn("shadow_workspace_synced", model)
        self.assertIn("git_evidence_recorded", model)
        self.assertIn("broken_drops_required_evidence", run_checks)


if __name__ == "__main__":
    unittest.main()
