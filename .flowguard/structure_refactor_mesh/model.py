"""FlowGuard rollout model for StructureMesh refactor governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for parent/child structure refactor
partitioning. It guards against treating a flat large-script split as trusted
parent confidence, accepting missing or duplicate ownership, losing public
entrypoints or facades, accepting target structures that were not derived from
a FlowGuard functional model, hiding dependency/config drift, overclaiming
behavior parity, and publishing without release-scope evidence.

Run:
python .flowguard/structure_refactor_mesh/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class StructureMeshCase:
    name: str
    parent_child_structure: bool = True
    target_structure_derived_from_model: bool = True
    target_structure_maps_model_boundaries: bool = True
    every_partition_owned: bool = True
    owners_registered: bool = True
    duplicate_partition_blocked: bool = True
    duplicate_state_blocked: bool = True
    duplicate_side_effect_blocked: bool = True
    duplicate_config_blocked: bool = True
    public_entrypoints_preserved: bool = True
    facades_retained: bool = True
    dependency_cycles_blocked: bool = True
    config_drift_blocked: bool = True
    parity_evidence_current: bool = True
    release_scope_blocks_missing_parity: bool = True
    adapters_collect_evidence_not_refactor: bool = True


@dataclass(frozen=True)
class StructureMeshPolicy:
    case_name: str = ""
    parent_child_structure: bool = False
    target_structure_derived_from_model: bool = False
    target_structure_maps_model_boundaries: bool = False
    every_partition_owned: bool = False
    owners_registered: bool = False
    duplicate_partition_blocked: bool = False
    duplicate_state_blocked: bool = False
    duplicate_side_effect_blocked: bool = False
    duplicate_config_blocked: bool = False
    public_entrypoints_preserved: bool = False
    facades_retained: bool = False
    dependency_cycles_blocked: bool = False
    config_drift_blocked: bool = False
    parity_evidence_current: bool = False
    release_scope_blocks_missing_parity: bool = False
    adapters_collect_evidence_not_refactor: bool = False


GOOD_PLAN = StructureMeshCase("good_structure_mesh_plan")
BROKEN_FLAT_SPLIT = StructureMeshCase("broken_flat_split", parent_child_structure=False)
BROKEN_TARGET_NOT_MODEL_DERIVED = StructureMeshCase(
    "broken_target_not_model_derived",
    target_structure_derived_from_model=False,
)
BROKEN_TARGET_BOUNDARY_MAP_MISSING = StructureMeshCase(
    "broken_target_boundary_map_missing",
    target_structure_maps_model_boundaries=False,
)
BROKEN_MISSING_OWNER = StructureMeshCase("broken_missing_owner", every_partition_owned=False)
BROKEN_UNREGISTERED_OWNER = StructureMeshCase("broken_unregistered_owner", owners_registered=False)
BROKEN_DUPLICATE_PARTITION = StructureMeshCase("broken_duplicate_partition", duplicate_partition_blocked=False)
BROKEN_DUPLICATE_STATE = StructureMeshCase("broken_duplicate_state", duplicate_state_blocked=False)
BROKEN_DUPLICATE_SIDE_EFFECT = StructureMeshCase("broken_duplicate_side_effect", duplicate_side_effect_blocked=False)
BROKEN_DUPLICATE_CONFIG = StructureMeshCase("broken_duplicate_config", duplicate_config_blocked=False)
BROKEN_PUBLIC_ENTRYPOINT = StructureMeshCase("broken_public_entrypoint", public_entrypoints_preserved=False)
BROKEN_MISSING_FACADE = StructureMeshCase("broken_missing_facade", facades_retained=False)
BROKEN_DEPENDENCY_CYCLE = StructureMeshCase("broken_dependency_cycle", dependency_cycles_blocked=False)
BROKEN_CONFIG_DRIFT = StructureMeshCase("broken_config_drift", config_drift_blocked=False)
BROKEN_STALE_PARITY = StructureMeshCase("broken_stale_parity", parity_evidence_current=False)
BROKEN_RELEASE_SCOPE = StructureMeshCase(
    "broken_release_scope",
    release_scope_blocks_missing_parity=False,
)
BROKEN_STRUCTUREMESH_REFACTORS = StructureMeshCase(
    "broken_structuremesh_refactors_directly",
    adapters_collect_evidence_not_refactor=False,
)


class EvaluateStructureMeshPlan:
    name = "EvaluateStructureMeshPlan"
    reads = ("StructureMeshPolicy",)
    writes = (
        "case_name",
        "parent_child_structure",
        "target_structure_derived_from_model",
        "target_structure_maps_model_boundaries",
        "every_partition_owned",
        "owners_registered",
        "duplicate_partition_blocked",
        "duplicate_state_blocked",
        "duplicate_side_effect_blocked",
        "duplicate_config_blocked",
        "public_entrypoints_preserved",
        "facades_retained",
        "dependency_cycles_blocked",
        "config_drift_blocked",
        "parity_evidence_current",
        "release_scope_blocks_missing_parity",
        "adapters_collect_evidence_not_refactor",
    )
    accepted_input_type = StructureMeshCase
    input_description = "structure mesh rollout case"
    output_description = "structure mesh rollout policy"
    idempotency = "same case produces one rollout policy"

    def apply(self, input_obj: StructureMeshCase, _state: StructureMeshPolicy):
        new_state = StructureMeshPolicy(
            case_name=input_obj.name,
            parent_child_structure=input_obj.parent_child_structure,
            target_structure_derived_from_model=input_obj.target_structure_derived_from_model,
            target_structure_maps_model_boundaries=input_obj.target_structure_maps_model_boundaries,
            every_partition_owned=input_obj.every_partition_owned,
            owners_registered=input_obj.owners_registered,
            duplicate_partition_blocked=input_obj.duplicate_partition_blocked,
            duplicate_state_blocked=input_obj.duplicate_state_blocked,
            duplicate_side_effect_blocked=input_obj.duplicate_side_effect_blocked,
            duplicate_config_blocked=input_obj.duplicate_config_blocked,
            public_entrypoints_preserved=input_obj.public_entrypoints_preserved,
            facades_retained=input_obj.facades_retained,
            dependency_cycles_blocked=input_obj.dependency_cycles_blocked,
            config_drift_blocked=input_obj.config_drift_blocked,
            parity_evidence_current=input_obj.parity_evidence_current,
            release_scope_blocks_missing_parity=input_obj.release_scope_blocks_missing_parity,
            adapters_collect_evidence_not_refactor=input_obj.adapters_collect_evidence_not_refactor,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected structure mesh rollout decision into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: StructureMeshPolicy) -> bool:
    return not state.case_name


def parent_child_structure_exists(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.parent_child_structure:
        return _fail("parent_child_structure_exists", "large refactor remains a flat split")
    return _pass()


def target_structure_is_model_derived(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.target_structure_derived_from_model:
        return _fail(
            "target_structure_is_model_derived",
            "target split structure is accepted without FlowGuard functional model evidence",
        )
    return _pass()


def target_structure_maps_model_boundaries(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.target_structure_maps_model_boundaries:
        return _fail(
            "target_structure_maps_model_boundaries",
            "target split structure lacks FunctionBlock/state/side-effect mapping",
        )
    return _pass()


def partition_ownership_is_complete(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.every_partition_owned:
        return _fail("partition_ownership_is_complete", "structure partition lacks an owner")
    if not state.owners_registered:
        return _fail("partition_ownership_is_complete", "partition owner module is not registered")
    return _pass()


def duplicate_owners_are_blocked(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.duplicate_partition_blocked:
        return _fail("duplicate_owners_are_blocked", "duplicate partition owner is accepted")
    if not state.duplicate_state_blocked:
        return _fail("duplicate_owners_are_blocked", "duplicate state owner is accepted")
    if not state.duplicate_side_effect_blocked:
        return _fail("duplicate_owners_are_blocked", "duplicate side-effect owner is accepted")
    if not state.duplicate_config_blocked:
        return _fail("duplicate_owners_are_blocked", "duplicate config owner is accepted")
    return _pass()


def compatibility_stays_preserved(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.public_entrypoints_preserved:
        return _fail("compatibility_stays_preserved", "public entrypoint was removed")
    if not state.facades_retained:
        return _fail("compatibility_stays_preserved", "compatibility facade was removed")
    return _pass()


def dependency_and_config_gaps_block(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.dependency_cycles_blocked:
        return _fail("dependency_and_config_gaps_block", "unsafe dependency cycle is accepted")
    if not state.config_drift_blocked:
        return _fail("dependency_and_config_gaps_block", "config/default drift is hidden")
    return _pass()


def parity_evidence_stays_current(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.parity_evidence_current:
        return _fail("parity_evidence_stays_current", "stale behavior parity is accepted")
    return _pass()


def release_scope_requires_release_parity(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.release_scope_blocks_missing_parity:
        return _fail(
            "release_scope_requires_release_parity",
            "release scope accepts missing release-required parity",
        )
    return _pass()


def structuremesh_does_not_refactor_code(state: StructureMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.adapters_collect_evidence_not_refactor:
        return _fail(
            "structuremesh_does_not_refactor_code",
            "StructureMesh is treated as the code-moving refactor engine",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "parent_child_structure_exists",
        "Large refactors use parent/child structure evidence instead of one flat split.",
        parent_child_structure_exists,
    ),
    Invariant(
        "target_structure_is_model_derived",
        "StructureMesh target splits are derived from FlowGuard functional model boundaries.",
        target_structure_is_model_derived,
    ),
    Invariant(
        "target_structure_maps_model_boundaries",
        "StructureMesh target splits map FunctionBlocks, state, and side effects to owners.",
        target_structure_maps_model_boundaries,
    ),
    Invariant(
        "partition_ownership_is_complete",
        "Every structure partition has a registered owner.",
        partition_ownership_is_complete,
    ),
    Invariant(
        "duplicate_owners_are_blocked",
        "Duplicate partition, state, side-effect, and config owners block parent confidence.",
        duplicate_owners_are_blocked,
    ),
    Invariant(
        "compatibility_stays_preserved",
        "Public entrypoints and facades remain compatibility-preserved.",
        compatibility_stays_preserved,
    ),
    Invariant(
        "dependency_and_config_gaps_block",
        "Dependency cycles and config/default drift stay visible.",
        dependency_and_config_gaps_block,
    ),
    Invariant(
        "parity_evidence_stays_current",
        "Behavior parity evidence is current before parent confidence is trusted.",
        parity_evidence_stays_current,
    ),
    Invariant(
        "release_scope_requires_release_parity",
        "Release scope requires release-required parity evidence.",
        release_scope_requires_release_parity,
    ),
    Invariant(
        "structuremesh_does_not_refactor_code",
        "StructureMesh reviews structured evidence instead of moving project code directly.",
        structuremesh_does_not_refactor_code,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateStructureMeshPlan(),), name="structure_refactor_mesh_rollout")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    case: StructureMeshCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=StructureMeshPolicy(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "good_plan_passes",
        "A complete StructureMesh rollout plan passes.",
        GOOD_PLAN,
        _expect_ok("complete StructureMesh plan passes", labels=("good_structure_mesh_plan",)),
    ),
    scenario(
        "flat_split_fails",
        "Large refactors must not remain one flat split.",
        BROKEN_FLAT_SPLIT,
        _expect_violation("flat split fails", ("parent_child_structure_exists",)),
    ),
    scenario(
        "target_not_model_derived_fails",
        "Existing script splits require model-derived target code structure.",
        BROKEN_TARGET_NOT_MODEL_DERIVED,
        _expect_violation("target without model evidence fails", ("target_structure_is_model_derived",)),
    ),
    scenario(
        "target_boundary_map_missing_fails",
        "Target structure must map FunctionBlocks, state, and side effects.",
        BROKEN_TARGET_BOUNDARY_MAP_MISSING,
        _expect_violation("target without model boundary map fails", ("target_structure_maps_model_boundaries",)),
    ),
    scenario(
        "missing_owner_fails",
        "Every structure partition must have an owner.",
        BROKEN_MISSING_OWNER,
        _expect_violation("missing owner fails", ("partition_ownership_is_complete",)),
    ),
    scenario(
        "unregistered_owner_fails",
        "Partition owners must be registered child modules.",
        BROKEN_UNREGISTERED_OWNER,
        _expect_violation("unregistered owner fails", ("partition_ownership_is_complete",)),
    ),
    scenario(
        "duplicate_partition_fails",
        "Duplicate partition ownership must block parent confidence.",
        BROKEN_DUPLICATE_PARTITION,
        _expect_violation("duplicate partition fails", ("duplicate_owners_are_blocked",)),
    ),
    scenario(
        "duplicate_state_fails",
        "Duplicate state ownership must block parent confidence.",
        BROKEN_DUPLICATE_STATE,
        _expect_violation("duplicate state fails", ("duplicate_owners_are_blocked",)),
    ),
    scenario(
        "duplicate_side_effect_fails",
        "Duplicate side-effect ownership must block parent confidence.",
        BROKEN_DUPLICATE_SIDE_EFFECT,
        _expect_violation("duplicate side effect fails", ("duplicate_owners_are_blocked",)),
    ),
    scenario(
        "duplicate_config_fails",
        "Duplicate config ownership must block parent confidence.",
        BROKEN_DUPLICATE_CONFIG,
        _expect_violation("duplicate config fails", ("duplicate_owners_are_blocked",)),
    ),
    scenario(
        "public_entrypoint_removed_fails",
        "Public entrypoints must remain compatible.",
        BROKEN_PUBLIC_ENTRYPOINT,
        _expect_violation("removed public entrypoint fails", ("compatibility_stays_preserved",)),
    ),
    scenario(
        "missing_facade_fails",
        "Compatibility facades must remain visible.",
        BROKEN_MISSING_FACADE,
        _expect_violation("missing facade fails", ("compatibility_stays_preserved",)),
    ),
    scenario(
        "dependency_cycle_fails",
        "Unsafe dependency cycles must block parent confidence.",
        BROKEN_DEPENDENCY_CYCLE,
        _expect_violation("dependency cycle fails", ("dependency_and_config_gaps_block",)),
    ),
    scenario(
        "config_drift_fails",
        "Config/default drift must stay visible.",
        BROKEN_CONFIG_DRIFT,
        _expect_violation("config drift fails", ("dependency_and_config_gaps_block",)),
    ),
    scenario(
        "stale_parity_fails",
        "Stale behavior parity cannot count as current evidence.",
        BROKEN_STALE_PARITY,
        _expect_violation("stale parity fails", ("parity_evidence_stays_current",)),
    ),
    scenario(
        "release_scope_requires_release_parity",
        "Release scope must block missing release-required parity.",
        BROKEN_RELEASE_SCOPE,
        _expect_violation("missing release parity fails", ("release_scope_requires_release_parity",)),
    ),
    scenario(
        "structuremesh_does_not_refactor_directly",
        "StructureMesh must review structured evidence instead of moving code itself.",
        BROKEN_STRUCTUREMESH_REFACTORS,
        _expect_violation("direct refactor engine fails", ("structuremesh_does_not_refactor_code",)),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)


from flowguard.skill_contract_model import (  # noqa: E402
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing StructureMesh owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-structure-mesh",
        route_id="structure_mesh_maintenance",
        owner_id="structure_mesh_maintenance",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Derive and verify a model-owned structural split while preserving facades, configuration, dependencies, and parity.",
        claim_boundary="Projection only; partition ownership, facade compatibility, cycle checks, and parity evidence remain native StructureMesh authority.",
    )
