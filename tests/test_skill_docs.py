import unittest
from pathlib import Path

from flowguard.prompt_budget import review_prompt_bundles


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
KERNEL_ROOT = SKILLS_ROOT / "flowguard"
DOMAIN_ROOT = KERNEL_ROOT / "references" / "domains"

# These are on-demand domain references, not public Codex skills.  Keeping the
# inventory here makes the current projection explicit without recreating the
# retired satellite directories.
DOMAINS = {
    "architecture-reduction",
    "behavior-commitment-ledger",
    "code-structure-recommendation",
    "contract-exhaustion-mesh",
    "development-process-flow",
    "existing-model-preflight",
    "field-lifecycle-mesh",
    "model-mesh",
    "model-miss-review",
    "model-test-alignment",
    "model-topology-hazard-review",
    "structure-mesh",
    "test-mesh",
    "ui-flow-structure",
}

REDUCED_FIELD_PROMPT_FILES = (
    DOMAIN_ROOT / "model-test-alignment" / "references" / "templates" / "model_test_alignment_prompt_template.md",
    DOMAIN_ROOT / "development-process-flow" / "references" / "development_process_flow_protocol.md",
    DOMAIN_ROOT / "test-mesh" / "references" / "test_mesh_protocol.md",
    KERNEL_ROOT / "assets" / "adoption_log_template.md",
)


class SkillDocsTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_hot_path_prompt_budgets_are_enforced(self):
        kernel = self.read(KERNEL_ROOT / "SKILL.md")
        snippet = self.read(ROOT / "docs" / "agents_snippet.md")
        self.assertLessEqual(len(kernel.splitlines()), 130)
        self.assertLessEqual(len(snippet.splitlines()), 110)
        for domain in sorted(DOMAINS):
            with self.subTest(domain=domain):
                text = self.read(DOMAIN_ROOT / domain / "protocol.md")
                self.assertLessEqual(len(text.splitlines()), 65)
                self.assertLess(len(text), 4600)

    def test_representative_first_read_bundles_are_budgeted(self):
        report = review_prompt_bundles(ROOT)
        self.assertTrue(report["ok"], report["failed_route_ids"])
        self.assertEqual(1, report["bundle_count"])
        bundle = report["bundles"][0]
        self.assertEqual("flowguard", bundle["route_id"])
        self.assertIn(".agents/skills/flowguard/SKILL.md", {x["path"] for x in bundle["components"]})
        self.assertTrue(bundle["headroom_ok"])
        self.assertGreaterEqual(bundle["headroom_ratio"], 0.10)
        self.assertEqual((bundle["utf8_bytes"] + 2) // 3, bundle["source_size_token_proxy"])
        persistent = bundle["persistent_context"]
        self.assertEqual("persistent_context", persistent["stage"])
        self.assertTrue(persistent["enforced"])
        self.assertTrue(persistent["ok"])
        self.assertGreaterEqual(persistent["headroom_ratio"], 0.10)
        persistent_paths = {x["path"] for x in persistent["components"]}
        self.assertIn(".agents/skills/flowguard/references/route_index.md", persistent_paths)
        self.assertIn(".agents/skills/flowguard/references/route_execution_common.md", persistent_paths)
        self.assertFalse(report["provider_token_usage_available"])

    def test_active_openspec_specs_have_real_purpose_text(self):
        for path in sorted((ROOT / "openspec" / "specs").glob("*/spec.md")):
            with self.subTest(spec=path.parent.name):
                text = self.read(path)
                self.assertIn("## Purpose", text)
                purpose = text.split("## Purpose", 1)[1].split("## Requirements", 1)[0]
                self.assertNotIn("TBD", purpose)
                self.assertNotIn("Update Purpose after archive", purpose)

    def test_kernel_is_compact_router_with_reference_handoffs(self):
        text = self.read(KERNEL_ROOT / "SKILL.md")
        for phrase in (
            "# FlowGuard", "read", "change", "release", "task-specific failure(s)",
            "native good/bad-per-failure/oracle/current evidence", "references/route_index.md",
            "references/domains/<subject>/", "Installation, parity, Git", "default result bounded",
        ):
            self.assertIn(phrase, text)
        self.assertEqual(
            (
                "## Fixed public lifecycle", "## Model-purpose gate", "## Read only what is selected",
                "## Hard boundaries", "## Result",
            ),
            tuple(line for line in text.splitlines() if line.startswith("## ")),
        )
        self.assertNotIn("SkillGuard", text)
        self.assertNotIn(".skillguard", text)

    def test_kernel_preserves_route_specific_diagram_intent(self):
        kernel = self.read(KERNEL_ROOT / "SKILL.md")
        evidence = self.read(KERNEL_ROOT / "references" / "modeling_evidence_protocol.md")
        self.assertNotIn("SourceGuard/TraceGuard/WorldGuard/LogicGuard diagrams", kernel)
        self.assertIn("must not flatten other Guard-family edge meanings", evidence)

    def test_kernel_keeps_static_design_execution_and_maturation_vocabulary_exact(self):
        evidence = self.read(KERNEL_ROOT / "references" / "modeling_evidence_protocol.md")
        alignment = self.read(DOMAIN_ROOT / "model-test-alignment" / "references" / "model_test_alignment_protocol.md")
        maturation = self.read(ROOT / "openspec" / "specs" / "model-maturation-iterative" / "spec.md")
        self.assertIn("`not_run` does not erase a complete static design", " ".join(evidence.split()))
        self.assertIn("blocks only executed/release claims", evidence)
        combined = f"{evidence}\n{alignment}\n{maturation}"
        for retired in ("`progress_stalled`", "`model_closed_for_task`", "`upgrade_required`", "`external_input_required`"):
            self.assertNotIn(retired, combined)
        for current in (
            "`model_maturation_progress_stalled`", "`model_maturation_closed_for_task`",
            "`model_maturation_upgrade_required`", "`model_maturation_external_input_required`",
        ):
            self.assertIn(current, combined)

    def test_per_model_path_quality_prompts_preserve_owner_depth_and_target_boundaries(self):
        kernel = self.read(KERNEL_ROOT / "SKILL.md")
        core = self.read(KERNEL_ROOT / "references" / "modeling_core_protocol.md")
        evidence = self.read(KERNEL_ROOT / "references" / "modeling_evidence_protocol.md")
        refs = {
            name: self.read(DOMAIN_ROOT / domain / "references" / filename)
            for name, domain, filename in (
                ("preflight", "existing-model-preflight", "existing_model_preflight_protocol.md"),
                ("mesh", "model-mesh", "model_mesh_protocol.md"),
                ("reduction", "architecture-reduction", "architecture_reduction_protocol.md"),
                ("alignment", "model-test-alignment", "model_test_alignment_protocol.md"),
                ("test_mesh", "test-mesh", "test_mesh_protocol.md"),
                ("process", "development-process-flow", "development_process_flow_protocol.md"),
                ("optimization", "development-process-flow", "process_optimization_protocol.md"),
            )
        }
        for text in (core, evidence, *refs.values()):
            self.assertIn("ModelMaturation", text)
        core_text = " ".join(core.split())
        self.assertIn("explicit finite model", kernel)
        for phrase in (
            "`lightweight_path_review(...)`", "With one clear path and no trigger",
            "deep review is admitted only for exact current evidence", "without a default scalar sum",
            "`observed` baseline", "non-code targets", "implementation-complete contract",
        ):
            self.assertIn(phrase, core_text)
        self.assertIn("No mode/fallback path", " ".join(kernel.split()))
        self.assertIn("Missing, stale, unresolved", " ".join(evidence.split()))
        self.assertIn("does not enumerate candidates", " ".join(refs["preflight"].split()))
        self.assertIn("do not copy deep candidates", " ".join(refs["mesh"].split()))
        self.assertIn("does not run a second model optimizer", " ".join(refs["reduction"].split()))
        self.assertIn("ModelMaturation alone owns light/deep path review", " ".join(refs["alignment"].split()))
        self.assertIn("does not create necessity witnesses", " ".join(refs["test_mesh"].split()))
        self.assertIn("owner and complete effective-intent closure", " ".join(refs["process"].split()))
        self.assertIn("no target-generation phase", " ".join(refs["process"].split()))
        optimization = " ".join(refs["optimization"].split())
        self.assertIn("Pareto-dominates every other eligible candidate", optimization)
        self.assertIn("Never claim a scalar minimum", optimization)
        self.assertIn("not a single-model path-quality conclusion", optimization)
        self.assertNotIn("plus their total", optimization)
        self.assertNotIn("unique lowest total", optimization)

    def test_domain_protocols_keep_route_specific_edge_semantics(self):
        expected = {
            "development-process-flow": "edges mean order, invalidation, or required revalidation",
            "ui-flow-structure": "edges mean reachable interaction transitions",
            "model-test-alignment": "edges mean covers, partially covers, or misses",
            "code-structure-recommendation": "edges mean owns, calls, adapts, exposes, or validates",
            "model-mesh": "edges mean delegates, reattaches, consumes output",
        }
        for domain, phrase in expected.items():
            with self.subTest(domain=domain):
                self.assertIn(phrase, self.read(DOMAIN_ROOT / domain / "protocol.md"))

    def test_domain_protocols_are_concise_and_not_public_skills(self):
        for domain in sorted(DOMAINS):
            with self.subTest(domain=domain):
                root = DOMAIN_ROOT / domain
                text = self.read(root / "protocol.md")
                self.assertTrue(text.startswith("# FlowGuard"))
                self.assertIn("Operation routing", text)
                self.assertIn("FlowGuard", text)
                self.assertGreaterEqual(sum(line.startswith("## ") for line in text.splitlines()), 5)
                self.assertNotIn("SkillGuard", text)
                self.assertNotIn(".skillguard", text)
                self.assertFalse((root / "SKILL.md").exists())
                self.assertFalse((root / "agents" / "openai.yaml").exists())

    def test_model_test_alignment_does_not_teach_optional_code_contracts(self):
        checked = (
            DOMAIN_ROOT / "model-test-alignment" / "protocol.md",
            DOMAIN_ROOT / "model-test-alignment" / "references" / "model_test_alignment_protocol.md",
            DOMAIN_ROOT / "model-test-alignment" / "references" / "templates" / "model_test_alignment_prompt_template.md",
            KERNEL_ROOT / "SKILL.md",
            KERNEL_ROOT / "references" / "skill_kernel_protocol.md",
            KERNEL_ROOT / "references" / "modeling_protocol.md",
        )
        for path in checked:
            text = self.read(path)
            self.assertNotIn("optional code contracts", text)
            self.assertNotIn("optional code external contracts", text)
            self.assertNotIn("optional external code contracts", text)
            self.assertNotIn("model-test-only", text)

    def test_ui_flow_structure_teaches_soft_typography_handoff(self):
        skill = self.read(DOMAIN_ROOT / "ui-flow-structure" / "protocol.md")
        protocol = self.read(DOMAIN_ROOT / "ui-flow-structure" / "references" / "ui_flow_structure_protocol.md")
        self.assertIn("structure, text hierarchy", skill)
        self.assertIn("visible surface", skill)
        self.assertIn("screenshot/DOM/event/result evidence", skill)
        for phrase in ("semantic hierarchy levels are not a command", "similar jobs", "one-off visual text style", "Observed Visible Surface Review", "disabled control is visible without a reason", "screenshot", "DOM text", "evidence kind"):
            self.assertIn(phrase, protocol)
        for phrase in ("maximum font-size", "font size limit", "screenshot ban", "screenshots are forbidden"):
            self.assertNotIn(phrase, protocol.lower())

    def test_retired_public_skill_surface_is_absent(self):
        self.assertEqual([], sorted(p.name for p in SKILLS_ROOT.iterdir() if p.name.startswith("flowguard-") and (p / "SKILL.md").is_file()))
        self.assertEqual(DOMAINS, {p.name for p in DOMAIN_ROOT.iterdir() if p.is_dir()})
        self.assertFalse(any(DOMAIN_ROOT.glob("*/SKILL.md")))
        self.assertFalse(any(DOMAIN_ROOT.glob("*/agents/openai.yaml")))

    def test_skill_references_do_not_duplicate_canonical_protocols(self):
        seen = {}
        for path in sorted(SKILLS_ROOT.glob("**/references/**/*.md")):
            text = self.read(path).strip()
            if not text:
                continue
            previous = seen.setdefault(text, path)
            self.assertEqual(previous, path, f"{path.relative_to(ROOT)} duplicates {previous.relative_to(ROOT)}")

    def test_long_prompt_templates_are_lazy_loaded(self):
        alignment = self.read(DOMAIN_ROOT / "model-test-alignment" / "references" / "model_test_alignment_protocol.md")
        alignment_template = self.read(DOMAIN_ROOT / "model-test-alignment" / "references" / "templates" / "model_test_alignment_prompt_template.md")
        mesh = self.read(DOMAIN_ROOT / "model-mesh" / "references" / "model_mesh_protocol.md")
        mesh_template = self.read(DOMAIN_ROOT / "model-mesh" / "references" / "templates" / "model_mesh_prompt_template.md")
        self.assertIn("model_test_alignment_prompt_template.md", alignment)
        self.assertNotIn("Build a FlowGuard Model-Test Alignment review", alignment)
        self.assertIn("Build a FlowGuard Model-Test Alignment review", alignment_template)
        self.assertIn("model_mesh_prompt_template.md", mesh)
        self.assertNotIn("Build or update a FlowGuard model mesh", mesh)
        self.assertIn("Build or update a FlowGuard model mesh", mesh_template)

    def test_conditional_protocol_splits_are_reachable(self):
        report = review_prompt_bundles(ROOT)
        self.assertEqual(("flowguard",), tuple(row["route_id"] for row in report["bundles"]))
        self.assertEqual(set(), {item["path"] for item in report["bundles"][0]["conditional_edges"]})
        self.assertEqual(DOMAINS, {p.name for p in DOMAIN_ROOT.iterdir() if p.is_dir()})

    def test_reduced_field_prompts_use_grouped_families(self):
        alignment = self.read(DOMAIN_ROOT / "model-test-alignment" / "references" / "model_test_alignment_protocol.md")
        process = self.read(DOMAIN_ROOT / "development-process-flow" / "references" / "development_process_flow_protocol.md")
        test_mesh = self.read(DOMAIN_ROOT / "test-mesh" / "references" / "test_mesh_protocol.md")
        mesh = self.read(DOMAIN_ROOT / "model-mesh" / "references" / "model_mesh_protocol.md")
        adoption = self.read(KERNEL_ROOT / "assets" / "adoption_log_template.md")
        for phrase in ("identity", "required evidence", "external boundary", "result:", "freshness:"):
            self.assertIn(phrase, alignment)
        for phrase in ("Changed artifacts", "Process steps", "Validation evidence", "Freshness rules"):
            self.assertIn(phrase, process)
        for phrase in ("Parent gate", "Ownership map", "Child suite evidence", "Target split derivation"):
            self.assertIn(phrase, test_mesh)
        for phrase in ("`model`", "`interface`", "`ownership`", "`evidence`", "`deep_handoff`"):
            self.assertIn(phrase, mesh)
        for phrase in ("Task captures", "Artifacts include", "Evidence captures", "Gaps capture"):
            self.assertIn(phrase, adoption)

    def test_reduced_field_prompts_do_not_reintroduce_blank_field_lists(self):
        for path in REDUCED_FIELD_PROMPT_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path)
                self.assertEqual([], [line for line in text.splitlines() if line.strip().startswith("- ") and line.rstrip().endswith(":")])

    def test_agents_snippet_uses_compact_canonical_route_table(self):
        text = self.read(ROOT / "docs" / "agents_snippet.md")
        for phrase in (
            "Minimum Valuable Model", "Hard Gates", "Route Map", "Reference Handoff", "use_flowguard",
            "skip_with_reason", "needs_human_review", "Input x State -> Set(Output x State)",
            "real FlowGuard check engine", "Risk Evidence Ledger", "public/local risk template",
            "template harvest closure", "risk-template-harvest-review", "Check-engine helpers",
            "not separate Codex skills", "Primary agent surface: the current clean consumer projection",
            "$CODEX_HOME/skills/flowguard/SKILL.md", "does not copy author controls",
            "not the AI-agent skill installation surface", "single public skill", "references/domains/",
            "not independent public skills",
        ):
            self.assertIn(phrase, text)
        self.assertLess(text.index("### Minimum Valuable Model"), text.index("### Route Map"))
        for marker in ("project-adopt", "project-upgrade", "Use Model-Test Alignment when", "For ModelMesh and TestMesh", "For post-runtime model misses", "Treat DevelopmentProcessFlow as another sibling route"):
            self.assertNotIn(marker, text)

    def test_readme_presents_flowguard_as_skill_suite_first(self):
        text = self.read(ROOT / "README.md")
        for phrase in ("An AI-agent skill suite powered by an executable check engine", "primary agent surface is `.agents/skills/`", ".agents/skills/flowguard/SKILL.md", "executable check scripts", "not the skill installation itself"):
            self.assertIn(phrase, text)
        self.assertNotIn("python -m pip install -e .", text)
        self.assertLess(text.index(".agents/skills/flowguard/SKILL.md"), text.index("python -m flowguard"))

    def test_active_guidance_does_not_reintroduce_old_process_entry_rules(self):
        paths = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "AGENTS.md", ROOT / "docs" / "agents_snippet.md", ROOT / "docs" / "api_surface.md", ROOT / "docs" / "modeling_protocol.md", ROOT / "docs" / "productized_helpers.md", KERNEL_ROOT / "SKILL.md", KERNEL_ROOT / "references" / "skill_kernel_protocol.md", KERNEL_ROOT / "references" / "modeling_protocol.md"]
        stale = ("Plan Detailing Compiler is the first FlowGuard route", "PlanDetailing is now the direct route", "direct route for non-trivial plan", "use Plan Detailing before writing the behavior model", "Global routing sends rough plan discussions to PlanDetailing", "first direct FlowGuard satellite", "plan detailing appears beside", "peer satellite route", "not as a hidden child", "Multi-skill workflow rehearsal routes directly", "This is a sibling sub-protocol", "rather than introducing separate named modes")
        for path in paths:
            if path.exists():
                text = self.read(path)
                for phrase in stale:
                    self.assertNotIn(phrase, text, path.name)


if __name__ == "__main__":
    unittest.main()
