from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

from flowguard.skill_contracts import validate_contract_source


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "flowguard-agent-workflow-rehearsal": "examples/flowguard_agent_workflow_rehearsal/model.py",
    "flowguard-architecture-reduction": ".flowguard/architecture_reduction/model.py",
    "flowguard-behavior-commitment-ledger": ".flowguard/behavior_commitment_ledger/model.py",
    "flowguard-code-structure-recommendation": "examples/skill_contract_model_exports/code_structure_recommendation.py",
    "flowguard-contract-exhaustion-mesh": "examples/skill_contract_model_exports/contract_exhaustion_mesh.py",
    "flowguard-development-process-flow": ".flowguard/development_process_flow/model.py",
    "flowguard-existing-model-preflight": ".flowguard/existing_model_preflight/model.py",
    "flowguard-field-lifecycle-mesh": ".flowguard/default_replacement_field_lifecycle/model.py",
    "flowguard-model-mesh": ".flowguard/hierarchical_model_mesh/model.py",
    "flowguard-model-miss-review": ".flowguard/model_miss_review/model.py",
    "flowguard-model-test-alignment": ".flowguard/model_test_code_alignment/model.py",
    "flowguard-model-topology-hazard-review": ".flowguard/model_topology_hazard_review/model.py",
    "flowguard-plan-detailing-compiler": "examples/plan_detailing_compiler/model.py",
    "flowguard-structure-mesh": ".flowguard/structure_refactor_mesh/model.py",
    "flowguard-test-mesh": ".flowguard/test_evidence_mesh/model.py",
    "flowguard-ui-flow-structure": ".flowguard/ui_flow_structure_skill/model.py",
    "model-first-function-flow": ".flowguard/minimum_valuable_model_entry/model.py",
}


def load_module(path: Path):
    digest = hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()[:12]
    name = f"flowguard_current_projection_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SkillContractCurrentProjectionTests(unittest.TestCase):
    def test_all_sources_use_current_only_authority_and_honest_depth(self) -> None:
        for skill_id, model_path in SKILLS.items():
            with self.subTest(skill=skill_id):
                skill = ROOT / ".agents" / "skills" / skill_id
                source = json.loads(
                    (skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
                )
                self.assertEqual("skillguard.contract_source.v2", source["schema_version"])
                self.assertEqual(model_path, source["model_path"])
                self.assertTrue(source["confirmed"])
                self.assertFalse(source["release_eligible"])
                self.assertFalse(validate_contract_source(source, skill))
                self.assertNotIn("v1_runtime_authority", source)
                self.assertEqual("skill_maintainer_source", source["repository_role"])
                self.assertEqual(f"unit:{skill_id}", source["maintenance_unit_id"])
                self.assertEqual([skill_id], source["member_skill_ids"])
                self.assertEqual(
                    {
                        "projection_id": "projection:consumer-distribution",
                        "prohibited_path_prefixes": [".skillguard/"],
                        "prohibited_prompt_tokens": [
                            "SkillGuard",
                            ".skillguard",
                            "skillguard.py",
                        ],
                        "release_manifest_path": "consumer-release.json",
                    },
                    source["consumer_projection"],
                )
                self.assertEqual("native-integrated", source["integration_mode"])
                self.assertFalse(source["may_define_parallel_execution_route"])
                self.assertFalse(source["may_define_skillguard_runtime_route"])

                profile = source["depth_profile"]
                self.assertEqual("skillguard.depth_profile.v2", profile["schema_version"])
                self.assertEqual(skill_id, profile["target_skill_id"])
                self.assertEqual("native-integrated", profile["integration_mode"])
                self.assertFalse(profile["skillguard_adds_domain_route"])
                self.assertEqual("enforced", profile["enforcement_level"])
                self.assertEqual(["enforced"], profile["required_closure_profiles"])
                self.assertEqual(
                    {row["check_id"] for row in source["checks"]},
                    set(profile["native_check_ids"]),
                )
                self.assertEqual(
                    ["enforced"],
                    [row["profile_id"] for row in source["closure_profiles"]],
                )
                provider = profile["provider_runtime"]
                self.assertEqual("skillguard-local-provider", provider["provider_id"])
                self.assertEqual(
                    "skillguard-declared-check-supervision-current",
                    provider["required_runtime_contract_id"],
                )
                self.assertEqual("enrolled", provider["required_enrollment_status"])
                self.assertTrue(provider["required_capability_ids"])
                self.assertTrue(provider["readiness_check_ids"])
                self.assertIn("SkillGuard only reconciles", profile["claim_boundary"])
                self.assertNotIn("calibration", profile)
                self.assertNotIn("coverage_universes", profile)

    def test_generated_contracts_match_current_source_and_model_export(self) -> None:
        for skill_id, model_path in SKILLS.items():
            with self.subTest(skill=skill_id):
                skill = ROOT / ".agents" / "skills" / skill_id
                source = json.loads((skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))
                compiled = json.loads((skill / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8"))
                manifest = json.loads((skill / ".skillguard" / "check-manifest.json").read_text(encoding="utf-8"))
                module = load_module(ROOT / model_path)
                exported = module.export_contract_model()
                self.assertEqual("flowguard-executable-model", module.FLOWGUARD_MODEL_MARKER)
                self.assertEqual("skillguard.compiled_contract.v2", compiled["schema_version"])
                self.assertEqual("skillguard.check_manifest.v2", manifest["schema_version"])
                self.assertEqual(source["model_id"], exported["model_id"])
                self.assertEqual(exported["model_id"], compiled["model_id"])
                self.assertEqual(source["depth_profile"], compiled["depth_profile"])
                self.assertEqual("skill_maintainer_source", compiled["repository_role"])
                self.assertEqual(f"unit:{skill_id}", compiled["maintenance_unit_id"])
                self.assertEqual([skill_id], compiled["member_skill_ids"])
                self.assertEqual(source["consumer_projection"], compiled["consumer_projection"])
                self.assertEqual(source["consumer_projection"], manifest["consumer_projection"])
                self.assertEqual(compiled["contract_hash"], manifest["contract_hash"])
                self.assertEqual(
                    {row["route_id"] for row in exported["routes"]},
                    set(source["depth_profile"]["native_route_ids"]),
                )
                self.assertEqual(
                    {row["step_id"] for row in source["step_bindings"]},
                    {row["step_id"] for row in compiled["steps"] if not row.get("terminal_kind")},
                )

    def test_development_process_contract_owns_strategy_equivalence(self) -> None:
        skill = ROOT / ".agents" / "skills" / "flowguard-development-process-flow"
        compiled = json.loads((skill / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8"))
        manifest = json.loads((skill / ".skillguard" / "check-manifest.json").read_text(encoding="utf-8"))
        obligation = "obligation:flowguard-development-process-flow:process-strategy-equivalence"
        self.assertIn(obligation, {row["obligation_id"] for row in compiled["obligations"]})
        native = next(row for row in manifest["checks"] if row["check_id"].endswith(":native-authority"))
        self.assertIn(obligation, native["covers_obligation_ids"])
        self.assertIn("tests/test_development_process_strategy.py", native["args"])

    def test_suite_inventory_is_exactly_the_seventeen_current_sources(self) -> None:
        self.assertEqual(17, len(SKILLS))
        discovered = {
            path.parent.parent.name
            for path in (ROOT / ".agents" / "skills").glob("*/.skillguard/contract-source.json")
        }
        self.assertEqual(set(SKILLS), discovered)


if __name__ == "__main__":
    unittest.main()
