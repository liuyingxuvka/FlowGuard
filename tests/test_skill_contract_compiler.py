from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowguard.skill_contracts import (
    CHECK_MANIFEST_FILE,
    CONTRACT_SOURCE_FILE,
    OUTPUT_FIELDS,
    WORK_CONTRACT_FILE,
    build_work_contract,
    compile_skill_contract,
    infer_source_requirements,
    validate_contract_source,
    work_contract_hash,
)


SKILL_TEXT = """---
name: fixture-native-skill
description: Use for a fixture-native route with current model evidence and closure gates.
---

# Fixture Native Skill

## Purpose
Own the fixture native route without creating a parallel route.

## Entrypoint Scope
Route id: `fixture_native_route`; role: public owner.

## Local Material Routing
Read `references/protocol.md` when detailed protocol evidence is required.

## Entrypoint Acceptance Map
- Accept only current native model and targeted test evidence.

## Use When
- Use when the fixture-native behavior boundary needs validation.

## Do Not Use When
- Do not use for unrelated routes or as a generic fallback.

## Required Workflow
1. Inventory the target and current evidence.
2. Execute the native route and required checks.
3. Close only after current receipts exist.

## Hard Gates
- Verify the native check; stale, skipped, or progress-only output must block closure.
- Never create a SkillGuard-owned parallel route.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, and typed_next_actions.

## SkillGuard Maintenance
- Edit contract-source.json, regenerate work-contract.json, and require deterministic parity.
"""


def source_payload() -> dict[str, object]:
    return {
        "schema_version": "flowguard.skill_contract_source.v1",
        "skill_id": "fixture-native-skill",
        "route_id": "fixture_native_route",
        "route_role": "public_owner",
        "native_owner": "fixture_native_route",
        "route_summary": "Validate one fixture-native behavior boundary.",
        "activation_keywords": ["fixture native", "fixture route"],
        "use_when": ["The fixture-native boundary needs current validation."],
        "do_not_use_when": ["The task belongs to another route."],
        "workflow": [
            {"phase_id": "intake", "summary": "Confirm the fixture boundary and claim."},
            {"phase_id": "inventory", "summary": "Inventory native artifacts and evidence."},
            {"phase_id": "execution", "summary": "Execute the fixture-native route."},
            {"phase_id": "checks", "summary": "Run the owner-specific native check."},
            {"phase_id": "closure", "summary": "Close only with current evidence."},
        ],
        "native_checks": [
            {
                "binding_id": "fixture_pytest_binding",
                "native_check_id": "fixture_pytest",
                "kind": "pytest",
                "summary": "Run the fixture owner test.",
                "command": "python -m pytest tests/test_fixture.py -q",
                "evidence_source": "current pytest command receipt",
            }
        ],
        "source_requirements": [
            {
                "requirement_id": "fixture.native.evidence",
                "category": "evidence",
                "summary": "Current native evidence is required before closure.",
            }
        ],
        "direct_references": ["references/protocol.md"],
        "downstream_targets": [
            {
                "target_kind": "internal_route",
                "target_id": "risk_evidence_ledger",
                "condition": "Broad confidence is requested.",
                "claim_scope": "current fixture route only",
            }
        ],
        "output_fields": list(OUTPUT_FIELDS),
        "layout_profiles": {
            "source": ".agents/skills/fixture-native-skill",
            "installed": ".codex/skills/fixture-native-skill",
        },
        "claim_boundary": "Only current fixture-native prompt/contract coverage is claimed.",
        "default_route": False,
    }


class SkillContractCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.skill = Path(self.temp.name) / "fixture-native-skill"
        (self.skill / ".skillguard").mkdir(parents=True)
        (self.skill / "references").mkdir()
        (self.skill / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
        (self.skill / "references" / "protocol.md").write_text("# Protocol\n", encoding="utf-8")
        (self.skill / CONTRACT_SOURCE_FILE).write_text(json.dumps(source_payload()), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_source_validation_requires_native_checks_and_five_phases(self) -> None:
        payload = source_payload()
        payload["native_checks"] = []
        self.assertIn("missing_native_checks", validate_contract_source(payload, self.skill))

    def test_parallel_skillguard_owner_field_is_not_a_valid_source_escape_hatch(self) -> None:
        payload = source_payload()
        payload["integration_mode"] = "skillguard-runtime"
        self.assertIn(
            "unknown_contract_source_field:integration_mode",
            validate_contract_source(payload, self.skill),
        )

    def test_missing_direct_reference_blocks_compilation(self) -> None:
        payload = source_payload()
        payload["direct_references"] = ["references/missing.md"]
        self.assertIn(
            "direct_reference_missing:references/missing.md",
            validate_contract_source(payload, self.skill),
        )

    def test_compiler_emits_native_integrated_non_parallel_contract(self) -> None:
        contract = build_work_contract(self.skill)
        self.assertEqual("native-integrated", contract["integration_mode"])
        self.assertFalse(contract["run_record_required"])
        self.assertFalse(contract["may_define_parallel_execution_route"])
        self.assertFalse(contract["may_define_skillguard_runtime_route"])
        self.assertTrue(contract["phase_native_bindings"])
        self.assertEqual(work_contract_hash(contract), contract["contract_hash"])

    def test_generation_is_deterministic_and_check_mode_detects_no_drift(self) -> None:
        _, _, findings, written = compile_skill_contract(self.skill, write=True)
        self.assertFalse(findings)
        self.assertGreaterEqual(len(written), 3)
        first_contract = (self.skill / WORK_CONTRACT_FILE).read_bytes()
        first_manifest = (self.skill / CHECK_MANIFEST_FILE).read_bytes()
        _, _, second_findings, second_written = compile_skill_contract(self.skill, write=True)
        self.assertFalse(second_findings)
        self.assertFalse(second_written)
        self.assertEqual(first_contract, (self.skill / WORK_CONTRACT_FILE).read_bytes())
        self.assertEqual(first_manifest, (self.skill / CHECK_MANIFEST_FILE).read_bytes())
        _, _, check_findings, _ = compile_skill_contract(self.skill, write=False)
        self.assertFalse(check_findings)

    def test_prompt_change_invalidates_generated_contract(self) -> None:
        compile_skill_contract(self.skill, write=True)
        (self.skill / "SKILL.md").write_text(SKILL_TEXT + "\n- New required evidence gate.\n", encoding="utf-8")
        _, _, findings, _ = compile_skill_contract(self.skill, write=False)
        self.assertIn("stale_generated_contract", {finding.code for finding in findings})

    def test_inferred_requirements_include_standard_boundaries(self) -> None:
        ids = {row["requirement_id"] for row in infer_source_requirements(SKILL_TEXT)}
        self.assertIn("target.entrypoint.acceptance", ids)
        self.assertIn("target.hard_gates", ids)
        self.assertIn("skillguard.native_route_binding", ids)


if __name__ == "__main__":
    unittest.main()
