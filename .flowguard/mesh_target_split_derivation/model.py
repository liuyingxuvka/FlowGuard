"""FlowGuard rollout model for mesh target split derivation.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the ModelMesh/TestMesh upgrade that requires target split
derivation before parent mesh confidence. It guards against accepting ad hoc
partition maps, missing FlowGuard source models, missing target children,
incomplete partition coverage, and fake prose-only derivations.

Run:
python .flowguard/mesh_target_split_derivation/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class MeshDerivationCase:
    name: str
    mesh_kind: str
    parent_boundary: bool = True
    source_flowguard_model: bool = True
    target_children: bool = True
    partition_coverage: bool = True
    ownership_maps: bool = True
    rationale: bool = True
    evidence_review_after_derivation: bool = True
    no_child_body_expansion: bool = True


@dataclass(frozen=True)
class MeshDerivationState:
    case_name: str = ""
    mesh_kind: str = ""
    parent_boundary: bool = False
    source_flowguard_model: bool = False
    target_children: bool = False
    partition_coverage: bool = False
    ownership_maps: bool = False
    rationale: bool = False
    evidence_review_after_derivation: bool = False
    no_child_body_expansion: bool = False


GOOD_MODEL_MESH = MeshDerivationCase("good_model_mesh_target_derivation", "model")
GOOD_TEST_MESH = MeshDerivationCase("good_test_mesh_target_derivation", "test")
BROKEN_MODEL_NO_SOURCE = MeshDerivationCase("broken_model_no_source", "model", source_flowguard_model=False)
BROKEN_MODEL_NO_TARGET = MeshDerivationCase("broken_model_no_target", "model", target_children=False)
BROKEN_MODEL_INCOMPLETE_COVERAGE = MeshDerivationCase(
    "broken_model_incomplete_coverage",
    "model",
    partition_coverage=False,
)
BROKEN_TEST_NO_SOURCE = MeshDerivationCase("broken_test_no_source", "test", source_flowguard_model=False)
BROKEN_TEST_NO_TARGET = MeshDerivationCase("broken_test_no_target", "test", target_children=False)
BROKEN_TEST_INCOMPLETE_COVERAGE = MeshDerivationCase(
    "broken_test_incomplete_coverage",
    "test",
    partition_coverage=False,
)
BROKEN_PROSE_ONLY = MeshDerivationCase(
    "broken_prose_only_derivation",
    "test",
    ownership_maps=False,
    rationale=True,
)
BROKEN_REVIEW_BEFORE_DERIVATION = MeshDerivationCase(
    "broken_review_before_derivation",
    "model",
    evidence_review_after_derivation=False,
)
BROKEN_CHILD_EXPANSION = MeshDerivationCase(
    "broken_child_expansion",
    "model",
    no_child_body_expansion=False,
)


class EvaluateMeshDerivation:
    name = "EvaluateMeshDerivation"
    reads = ("MeshDerivationState",)
    writes = tuple(MeshDerivationState.__dataclass_fields__.keys())
    accepted_input_type = MeshDerivationCase
    input_description = "mesh target split derivation rollout case"
    output_description = "mesh target split derivation policy state"
    idempotency = "same case overwrites the same rollout policy projection"

    def apply(self, input_obj: MeshDerivationCase, _state: MeshDerivationState):
        new_state = MeshDerivationState(
            case_name=input_obj.name,
            mesh_kind=input_obj.mesh_kind,
            parent_boundary=input_obj.parent_boundary,
            source_flowguard_model=input_obj.source_flowguard_model,
            target_children=input_obj.target_children,
            partition_coverage=input_obj.partition_coverage,
            ownership_maps=input_obj.ownership_maps,
            rationale=input_obj.rationale,
            evidence_review_after_derivation=input_obj.evidence_review_after_derivation,
            no_child_body_expansion=input_obj.no_child_body_expansion,
        )
        return (
            FunctionResult(
                output=input_obj.name,
                new_state=new_state,
                label=input_obj.name,
                reason="projected mesh target split derivation case",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: MeshDerivationState) -> bool:
    return not state.case_name


def parent_mesh_requires_derivation_source(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.parent_boundary:
        return _fail("parent_mesh_requires_derivation_source", "mesh has no parent boundary")
    if not state.source_flowguard_model:
        return _fail(
            "parent_mesh_requires_derivation_source",
            "target split derivation lacks a FlowGuard source structure model",
        )
    return _pass()


def target_children_are_derived(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.target_children:
        return _fail("target_children_are_derived", "target child model/suite layout is missing")
    return _pass()


def partition_coverage_is_derived(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.partition_coverage:
        return _fail(
            "partition_coverage_is_derived",
            "target split derivation does not cover parent partition items",
        )
    return _pass()


def ownership_maps_are_structured(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.ownership_maps:
        return _fail(
            "ownership_maps_are_structured",
            "target split derivation is prose-only and lacks ownership maps",
        )
    if not state.rationale:
        return _fail("ownership_maps_are_structured", "target split derivation lacks rationale")
    return _pass()


def evidence_review_follows_derivation(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.evidence_review_after_derivation:
        return _fail(
            "evidence_review_follows_derivation",
            "mesh evidence review ran before target split derivation was established",
        )
    return _pass()


def parent_mesh_consumes_child_contracts(state: MeshDerivationState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.no_child_body_expansion:
        return _fail(
            "parent_mesh_consumes_child_contracts",
            "parent mesh expands child model graphs or test internals instead of contracts",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "parent_mesh_requires_derivation_source",
        "Parent mesh target split derivation names a FlowGuard source structure model.",
        parent_mesh_requires_derivation_source,
    ),
    Invariant(
        "target_children_are_derived",
        "Target child model/suite layout is derived before review.",
        target_children_are_derived,
    ),
    Invariant(
        "partition_coverage_is_derived",
        "Target derivation covers parent partition items.",
        partition_coverage_is_derived,
    ),
    Invariant(
        "ownership_maps_are_structured",
        "Target derivation includes structured ownership maps and rationale.",
        ownership_maps_are_structured,
    ),
    Invariant(
        "evidence_review_follows_derivation",
        "Evidence review follows target split derivation.",
        evidence_review_follows_derivation,
    ),
    Invariant(
        "parent_mesh_consumes_child_contracts",
        "Parent mesh consumes child contracts rather than expanding child bodies.",
        parent_mesh_consumes_child_contracts,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateMeshDerivation(),), name="mesh_target_split_derivation_rollout")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="violation", expected_violation_names=tuple(names), summary=summary)


def scenario(
    name: str,
    description: str,
    case: MeshDerivationCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=MeshDerivationState(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "model_mesh_derivation_passes",
        "ModelMesh target split derivation has source, targets, coverage, ownership, and rationale.",
        GOOD_MODEL_MESH,
        _expect_ok("complete ModelMesh derivation passes", labels=("good_model_mesh_target_derivation",)),
    ),
    scenario(
        "test_mesh_derivation_passes",
        "TestMesh target split derivation has source, targets, coverage, ownership, and rationale.",
        GOOD_TEST_MESH,
        _expect_ok("complete TestMesh derivation passes", labels=("good_test_mesh_target_derivation",)),
    ),
    scenario(
        "model_mesh_source_required",
        "ModelMesh cannot accept a split with no FlowGuard source model.",
        BROKEN_MODEL_NO_SOURCE,
        _expect_violation("missing ModelMesh source fails", ("parent_mesh_requires_derivation_source",)),
    ),
    scenario(
        "model_mesh_target_required",
        "ModelMesh cannot accept a split with no target child layout.",
        BROKEN_MODEL_NO_TARGET,
        _expect_violation("missing ModelMesh targets fails", ("target_children_are_derived",)),
    ),
    scenario(
        "model_mesh_coverage_required",
        "ModelMesh target derivation must cover parent partitions.",
        BROKEN_MODEL_INCOMPLETE_COVERAGE,
        _expect_violation("incomplete ModelMesh coverage fails", ("partition_coverage_is_derived",)),
    ),
    scenario(
        "test_mesh_source_required",
        "TestMesh cannot accept a validation split with no FlowGuard source model.",
        BROKEN_TEST_NO_SOURCE,
        _expect_violation("missing TestMesh source fails", ("parent_mesh_requires_derivation_source",)),
    ),
    scenario(
        "test_mesh_target_required",
        "TestMesh cannot accept a validation split with no target child suites.",
        BROKEN_TEST_NO_TARGET,
        _expect_violation("missing TestMesh targets fails", ("target_children_are_derived",)),
    ),
    scenario(
        "test_mesh_coverage_required",
        "TestMesh target derivation must cover parent validation partitions.",
        BROKEN_TEST_INCOMPLETE_COVERAGE,
        _expect_violation("incomplete TestMesh coverage fails", ("partition_coverage_is_derived",)),
    ),
    scenario(
        "prose_only_derivation_fails",
        "A prose-only recommendation is not enough target split derivation.",
        BROKEN_PROSE_ONLY,
        _expect_violation("prose-only derivation fails", ("ownership_maps_are_structured",)),
    ),
    scenario(
        "review_before_derivation_fails",
        "Mesh review must not run before target split derivation exists.",
        BROKEN_REVIEW_BEFORE_DERIVATION,
        _expect_violation("review before derivation fails", ("evidence_review_follows_derivation",)),
    ),
    scenario(
        "child_expansion_fails",
        "Parent mesh must consume child contracts instead of expanding internals.",
        BROKEN_CHILD_EXPANSION,
        _expect_violation("child expansion fails", ("parent_mesh_consumes_child_contracts",)),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)
