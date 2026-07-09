"""FlowGuard self behavior commitment ledger.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: register FlowGuard's own external maintenance promises before broad
self-maintenance confidence.
Guards against: missing behavior registration, stale source surfaces, model
misses creating duplicate features, missing DCAR/TestMesh gates, or old paths
surviving as alternate success surfaces.
Use before editing: FlowGuard process guidance, behavior ledger logic, self
maintenance, model miss review, ContractExhaustionMesh, TestMesh, skills, and
AGENTS guidance.
Run: python .flowguard/behavior_commitment_ledger/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    BCL_CHANGE_BOOTSTRAP_LEDGER,
    BCL_COMMITMENT_PROCESS,
    BCL_COMMITMENT_WORKFLOW,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_MISS_ORIGIN_NONE,
    BCL_MODEL_SYNC_OWNER_CURRENT,
    BCL_REPLACEMENT_ACTIVE,
    BCL_SCOPE_FULL,
    BCL_SOURCE_CODE,
    BCL_SOURCE_DOC,
    BCL_SOURCE_FRESHNESS_CURRENT,
    BCL_SOURCE_OPENSPEC,
    BCL_SOURCE_PROCESS,
    BCL_SOURCE_SKILL,
    BCL_SOURCE_TEST,
    BCL_TEST_MESH_SHARD_CURRENT,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorSourceSurface,
)


def _surface(surface_id: str, surface_kind: str, source_ref: str, commitments: tuple[str, ...]) -> BehaviorSourceSurface:
    return BehaviorSourceSurface(
        surface_id,
        surface_kind=surface_kind,
        label=surface_id.removeprefix("surface:").replace("-", " "),
        source_ref=source_ref,
        commitment_ids=commitments,
        freshness_state=BCL_SOURCE_FRESHNESS_CURRENT,
        owner="flowguard_self_maintenance",
        validation_boundary="source reviewed during self-maintenance hardening",
        rationale="surface can create or change external FlowGuard maintenance promises",
    )


def _evidence(
    commitment_key: str,
    *,
    model_obligations: tuple[str, ...],
    code_contracts: tuple[str, ...],
    tests: tuple[str, ...],
    coverage_cases: tuple[str, ...],
    shards: tuple[str, ...],
) -> BehaviorEvidenceBinding:
    return BehaviorEvidenceBinding(
        model_obligation_ids=model_obligations,
        code_contract_ids=code_contracts,
        test_evidence_ids=tests,
        proof_artifact_ids=(f"proof:self-maintenance:{commitment_key}",),
        risk_gate_ids=(f"risk_gate:flowguard_self_maintenance:{commitment_key}",),
        coverage_case_ids=coverage_cases,
        coverage_shard_ids=shards,
        coverage_receipt_ids=("contract_coverage:behavior_commitment_ledger:self_maintenance",),
        evidence_state=BCL_EVIDENCE_CURRENT_PASS,
        test_mesh_state=BCL_TEST_MESH_SHARD_CURRENT,
        current=True,
    )


def _commitment(
    commitment_id: str,
    *,
    label: str,
    trigger: str,
    expected_result: str,
    failure_boundary: str,
    source_surface_ids: tuple[str, ...],
    primary_owner_model_id: str,
    tests: tuple[str, ...],
    coverage_cases: tuple[str, ...],
    shards: tuple[str, ...],
    kind: str = BCL_COMMITMENT_WORKFLOW,
    supporting_model_ids: tuple[str, ...] = (),
) -> BehaviorCommitment:
    commitment_key = commitment_id.removeprefix("commitment:").replace(":", "-")
    return BehaviorCommitment(
        commitment_id,
        label=label,
        commitment_kind=kind,
        actor="FlowGuard maintainer AI",
        trigger=trigger,
        expected_result=expected_result,
        failure_boundary=failure_boundary,
        source_surface_ids=source_surface_ids,
        primary_owner_model_id=primary_owner_model_id,
        supporting_model_ids=supporting_model_ids,
        replacement_state=BCL_REPLACEMENT_ACTIVE,
        model_sync_state=BCL_MODEL_SYNC_OWNER_CURRENT,
        miss_origin_state=BCL_MISS_ORIGIN_NONE,
        validation_boundary="model, code contract, tests, and self-maintenance child evidence stay aligned",
        rationale="external FlowGuard maintenance behavior, not a private helper detail",
        evidence=_evidence(
            commitment_key,
            model_obligations=(f"obligation:{primary_owner_model_id}:{commitment_key}",),
            code_contracts=(f"contract:{commitment_key}",),
            tests=tests,
            coverage_cases=coverage_cases,
            shards=shards,
        ),
    )


def build_flowguard_behavior_commitment_ledger() -> BehaviorCommitmentLedger:
    commitments = (
        _commitment(
            "commitment:behavior-ledger-current",
            label="broad behavior claims use a current behavior commitment ledger",
            kind=BCL_COMMITMENT_PROCESS,
            trigger="an agent claims broad FlowGuard behavior, done, release, archive, or publish confidence",
            expected_result=(
                "the agent classifies the ledger mode, checks current source surfaces, "
                "maps every external commitment to exactly one owner model, and blocks stale evidence"
            ),
            failure_boundary="broad confidence is blocked until the ledger is repaired",
            source_surface_ids=(
                "surface:project-rules",
                "surface:bcl-skill",
                "surface:bcl-open-spec",
                "surface:bcl-code",
                "surface:bcl-tests",
            ),
            primary_owner_model_id=".flowguard/behavior_commitment_ledger/model.py",
            tests=(
                "tests.test_behavior_commitment_ledger",
                "tests.test_behavior_commitment_primary_path",
                ".flowguard/behavior_commitment_ledger/run_checks.py",
            ),
            coverage_cases=(
                "bcl.full_inventory_mapping.source.current",
                "bcl.full_inventory_mapping.owner.current",
            ),
            shards=("contract_shard:behavior_commitment_ledger:self-current",),
            supporting_model_ids=(".flowguard/self_maintenance_mesh/model.py",),
        ),
        _commitment(
            "commitment:behavior-dcar-full-axis",
            label="behavior ledger coverage has DCAR axes and interaction groups",
            kind=BCL_COMMITMENT_PROCESS,
            trigger="the behavior ledger claims full source-to-commitment coverage",
            expected_result=(
                "ContractExhaustionMesh exposes change-mode, source-freshness, replacement, "
                "model-sync, TestMesh, and model-miss axes plus interaction groups"
            ),
            failure_boundary="broad ledger coverage is blocked until missing axes or groups are added",
            source_surface_ids=(
                "surface:contract-exhaustion-skill",
                "surface:bcl-open-spec",
                "surface:bcl-code",
                "surface:bcl-tests",
            ),
            primary_owner_model_id="flowguard.behavior_commitment.default_behavior_commitment_coverage_universe",
            tests=(
                "tests.test_behavior_commitment_contract_exhaustion",
                "tests.test_public_templates",
            ),
            coverage_cases=(
                "bcl.change_mode_source_freshness",
                "bcl.replacement_model_sync",
                "bcl.model_miss_backfeed",
            ),
            shards=("contract_shard:behavior_commitment_ledger:full-dcar",),
            supporting_model_ids=(".flowguard/behavior_commitment_ledger/model.py",),
        ),
        _commitment(
            "commitment:test-mesh-current-for-bcl",
            label="behavior ledger broad claims require current TestMesh shard evidence",
            kind=BCL_COMMITMENT_PROCESS,
            trigger="a behavior commitment is used in a broad/full FlowGuard claim",
            expected_result="missing, stale, progress-only, or release-only shard states block the claim",
            failure_boundary="the claim is blocked until TestMesh evidence is current",
            source_surface_ids=(
                "surface:test-mesh-skill",
                "surface:bcl-code",
                "surface:bcl-tests",
            ),
            primary_owner_model_id="flowguard.behavior_commitment._review_change_lifecycle",
            tests=(
                "tests.test_behavior_commitment_ledger.BehaviorCommitmentLedgerTests.test_missing_test_mesh_shard_blocks_broad_claim",
                "tests.test_api_surface",
            ),
            coverage_cases=("bcl.test_mesh_state.shard_missing.blocks",),
            shards=("contract_shard:behavior_commitment_ledger:test-mesh-state",),
        ),
        _commitment(
            "commitment:model-miss-backfeeds-existing-commitment",
            label="model miss review backfeeds existing commitments before adding new behavior",
            kind=BCL_COMMITMENT_PROCESS,
            trigger="runtime, test, replay, log, or manual validation finds a miss after FlowGuard passed",
            expected_result=(
                "the miss is first mapped to an existing commitment and owner model; "
                "a gap backfill happens only when the external behavior was never registered"
            ),
            failure_boundary="duplicate point-fix commitments are blocked",
            source_surface_ids=(
                "surface:model-miss-skill",
                "surface:existing-model-preflight-skill",
                "surface:bcl-open-spec",
                "surface:bcl-code",
                "surface:bcl-tests",
            ),
            primary_owner_model_id="flowguard.behavior_commitment._review_change_lifecycle",
            tests=(
                "tests.test_behavior_commitment_ledger.BehaviorCommitmentLedgerTests.test_model_miss_backfeed_requires_existing_commitment_model_and_dcar_case",
                "tests.test_behavior_commitment_ledger.BehaviorCommitmentLedgerTests.test_model_miss_on_existing_commitment_must_not_create_duplicate_commitment",
            ),
            coverage_cases=("bcl.model_miss_backfeed.existing_commitment_first",),
            shards=("contract_shard:behavior_commitment_ledger:model-miss-backfeed",),
            supporting_model_ids=(".flowguard/model_miss_review/model.py",),
        ),
        _commitment(
            "commitment:self-maintenance-child-gates",
            label="FlowGuard self-maintenance cannot finish without BCL, DCAR, TestMesh, and model-miss child gates",
            kind=BCL_COMMITMENT_WORKFLOW,
            trigger="FlowGuard self-maintenance claims broad done confidence",
            expected_result=(
                "route graph, field layers, behavior ledger, DCAR, TestMesh, model-miss backfeed, "
                "validation, install, shadow, and git gates are all current"
            ),
            failure_boundary="done is rejected if any required child gate is missing",
            source_surface_ids=(
                "surface:self-maintenance-model",
                "surface:self-maintenance-code",
                "surface:self-maintenance-tests",
                "surface:bcl-open-spec",
            ),
            primary_owner_model_id=".flowguard/self_maintenance_mesh/model.py",
            tests=(
                ".flowguard/self_maintenance_mesh/run_checks.py",
                "tests.test_api_surface.ApiSurfaceTests.test_broad_self_maintenance_requires_behavior_child_reports",
            ),
            coverage_cases=("self_maintenance.missing_child_gate.blocks",),
            shards=("contract_shard:self_maintenance:required-child-gates",),
            supporting_model_ids=("flowguard.review_flowguard_self_maintenance",),
        ),
        _commitment(
            "commitment:single-path-replacement-disposition",
            label="old fields, aliases, wrappers, or alternate paths are disposed instead of kept as success paths",
            kind=BCL_COMMITMENT_PROCESS,
            trigger="a FlowGuard change removes, replaces, or finds an old path or field",
            expected_result="the old surface is deleted, blocked, migrated, delegated, repaired, or scoped out with evidence",
            failure_boundary="broad confidence is blocked when the old surface can still succeed as a separate path",
            source_surface_ids=(
                "surface:project-rules",
                "surface:self-maintenance-code",
                "surface:agents-snippet",
                "surface:bcl-open-spec",
            ),
            primary_owner_model_id="flowguard.self_maintenance.default_field_layer_profiles",
            tests=(
                "tests.test_api_surface.ApiSurfaceTests.test_field_layer_profiles_are_entry_only_and_preserve_expansion",
                "tests.test_behavior_commitment_ledger.BehaviorCommitmentLedgerTests.test_replaced_behavior_requires_replacement_disposition",
            ),
            coverage_cases=("bcl.replacement_state.replaced.requires_disposition",),
            shards=("contract_shard:flowguard_self_maintenance:single-path-replacement",),
            supporting_model_ids=("flowguard.primary_path_authority",),
        ),
    )

    source_surfaces = (
        _surface(
            "surface:project-rules",
            BCL_SOURCE_PROCESS,
            "AGENTS.md#FlowGuard Project Rules",
            (
                "commitment:behavior-ledger-current",
                "commitment:single-path-replacement-disposition",
            ),
        ),
        _surface(
            "surface:agents-snippet",
            BCL_SOURCE_DOC,
            "docs/agents_snippet.md#Hard Gates",
            ("commitment:single-path-replacement-disposition",),
        ),
        _surface(
            "surface:bcl-skill",
            BCL_SOURCE_SKILL,
            ".agents/skills/flowguard-behavior-commitment-ledger/SKILL.md",
            ("commitment:behavior-ledger-current",),
        ),
        _surface(
            "surface:contract-exhaustion-skill",
            BCL_SOURCE_SKILL,
            ".agents/skills/flowguard-contract-exhaustion-mesh/SKILL.md",
            ("commitment:behavior-dcar-full-axis",),
        ),
        _surface(
            "surface:test-mesh-skill",
            BCL_SOURCE_SKILL,
            ".agents/skills/flowguard-test-mesh/SKILL.md",
            ("commitment:test-mesh-current-for-bcl",),
        ),
        _surface(
            "surface:model-miss-skill",
            BCL_SOURCE_SKILL,
            ".agents/skills/flowguard-model-miss-review/SKILL.md",
            ("commitment:model-miss-backfeeds-existing-commitment",),
        ),
        _surface(
            "surface:existing-model-preflight-skill",
            BCL_SOURCE_SKILL,
            ".agents/skills/flowguard-existing-model-preflight/SKILL.md",
            ("commitment:model-miss-backfeeds-existing-commitment",),
        ),
        _surface(
            "surface:bcl-open-spec",
            BCL_SOURCE_OPENSPEC,
            "openspec/changes/add-behavior-commitment-ledger/specs",
            (
                "commitment:behavior-ledger-current",
                "commitment:behavior-dcar-full-axis",
                "commitment:model-miss-backfeeds-existing-commitment",
                "commitment:self-maintenance-child-gates",
                "commitment:single-path-replacement-disposition",
            ),
        ),
        _surface(
            "surface:bcl-code",
            BCL_SOURCE_CODE,
            "flowguard/behavior_commitment.py",
            (
                "commitment:behavior-ledger-current",
                "commitment:behavior-dcar-full-axis",
                "commitment:test-mesh-current-for-bcl",
                "commitment:model-miss-backfeeds-existing-commitment",
            ),
        ),
        _surface(
            "surface:self-maintenance-code",
            BCL_SOURCE_CODE,
            "flowguard/self_maintenance.py",
            (
                "commitment:self-maintenance-child-gates",
                "commitment:single-path-replacement-disposition",
            ),
        ),
        _surface(
            "surface:self-maintenance-model",
            BCL_SOURCE_CODE,
            ".flowguard/self_maintenance_mesh/model.py",
            ("commitment:self-maintenance-child-gates",),
        ),
        _surface(
            "surface:bcl-tests",
            BCL_SOURCE_TEST,
            "tests/test_behavior_commitment_ledger.py; tests/test_behavior_commitment_contract_exhaustion.py",
            (
                "commitment:behavior-ledger-current",
                "commitment:behavior-dcar-full-axis",
                "commitment:test-mesh-current-for-bcl",
                "commitment:model-miss-backfeeds-existing-commitment",
            ),
        ),
        _surface(
            "surface:self-maintenance-tests",
            BCL_SOURCE_TEST,
            "tests/test_api_surface.py; .flowguard/self_maintenance_mesh/run_checks.py",
            (
                "commitment:self-maintenance-child-gates",
                "commitment:single-path-replacement-disposition",
            ),
        ),
    )

    return BehaviorCommitmentLedger(
        "flowguard-self-maintenance-ledger",
        project_boundary="FlowGuard self-maintenance behavior registration hardening",
        current_revision="2026-07-09-bcl-dcar-testmesh-modelmiss-self-maintenance",
        commitments=commitments,
        source_surfaces=source_surfaces,
        expected_commitment_ids=tuple(commitment.commitment_id for commitment in commitments),
        claim_scope=BCL_SCOPE_FULL,
        change_mode=BCL_CHANGE_BOOTSTRAP_LEDGER,
        require_current_evidence=True,
        owner="flowguard_self_maintenance",
        validation_boundary="behavior ledger review plus focused self-maintenance, API, template, and OpenSpec checks",
        rationale="FlowGuard should maintain its own behavior registration using the same hard gates it teaches agents",
        metadata={
            "spec_tooling_policy": "tool-agnostic source surfaces; OpenSpec is one current source, not the only supported spec workflow",
            "no_alternate_success_surface": True,
        },
    )


__all__ = ["build_flowguard_behavior_commitment_ledger"]
