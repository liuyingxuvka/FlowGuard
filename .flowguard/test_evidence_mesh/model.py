"""FlowGuard rollout model for TestMesh validation governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for parent/child test evidence
partitioning. It guards against treating a flat slow regression as trusted
parent confidence, accepting missing or duplicate suite ownership, hiding stale
or skipped test evidence, mistaking background progress for completion, and
publishing without release-scope evidence.

Run:
python .flowguard/test_evidence_mesh/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class TestMeshCase:
    name: str
    parent_child_partitions: bool = True
    every_partition_owned: bool = True
    owners_registered: bool = True
    duplicate_ownership_blocked: bool = True
    stale_evidence_visible: bool = True
    skipped_tests_visible: bool = True
    timeout_and_failed_visible: bool = True
    background_completion_artifacts: bool = True
    routine_release_split: bool = True
    release_scope_blocks_missing_release_suite: bool = True
    adapters_run_tests_not_testmesh: bool = True
    required_inventory_revision_declared: bool = True
    complete_inventory_owned: bool = True
    progress_never_counts_as_pass: bool = True
    final_receipt_complete: bool = True
    spec_consumer_fanout_complete: bool = True
    spec_cross_change_reuse_authorized: bool = True
    spec_receipt_not_duplicated: bool = True


@dataclass(frozen=True)
class TestMeshPolicy:
    case_name: str = ""
    parent_child_partitions: bool = False
    every_partition_owned: bool = False
    owners_registered: bool = False
    duplicate_ownership_blocked: bool = False
    stale_evidence_visible: bool = False
    skipped_tests_visible: bool = False
    timeout_and_failed_visible: bool = False
    background_completion_artifacts: bool = False
    routine_release_split: bool = False
    release_scope_blocks_missing_release_suite: bool = False
    adapters_run_tests_not_testmesh: bool = False
    required_inventory_revision_declared: bool = False
    complete_inventory_owned: bool = False
    progress_never_counts_as_pass: bool = False
    final_receipt_complete: bool = False
    spec_consumer_fanout_complete: bool = False
    spec_cross_change_reuse_authorized: bool = False
    spec_receipt_not_duplicated: bool = False


GOOD_PLAN = TestMeshCase("good_test_mesh_plan")
BROKEN_FLAT_GATE = TestMeshCase("broken_flat_gate", parent_child_partitions=False)
BROKEN_MISSING_OWNER = TestMeshCase("broken_missing_owner", every_partition_owned=False)
BROKEN_UNREGISTERED_OWNER = TestMeshCase("broken_unregistered_owner", owners_registered=False)
BROKEN_DUPLICATE_OWNER = TestMeshCase("broken_duplicate_owner", duplicate_ownership_blocked=False)
BROKEN_STALE_EVIDENCE = TestMeshCase("broken_stale_evidence", stale_evidence_visible=False)
BROKEN_HIDDEN_SKIPS = TestMeshCase("broken_hidden_skips", skipped_tests_visible=False)
BROKEN_TIMEOUT_HIDDEN = TestMeshCase("broken_timeout_hidden", timeout_and_failed_visible=False)
BROKEN_BACKGROUND_PROGRESS_ONLY = TestMeshCase(
    "broken_background_progress_only",
    background_completion_artifacts=False,
)
BROKEN_RELEASE_SCOPE = TestMeshCase(
    "broken_release_scope",
    release_scope_blocks_missing_release_suite=False,
)
BROKEN_TESTMESH_RUNS_TESTS = TestMeshCase("broken_testmesh_runs_tests", adapters_run_tests_not_testmesh=False)
BROKEN_MISSING_INVENTORY_REVISION = TestMeshCase(
    "broken_missing_inventory_revision",
    required_inventory_revision_declared=False,
)
BROKEN_CALLER_SUBSET_INVENTORY = TestMeshCase(
    "broken_caller_subset_inventory",
    complete_inventory_owned=False,
)
BROKEN_PROGRESS_AS_PASS = TestMeshCase(
    "broken_progress_as_pass",
    progress_never_counts_as_pass=False,
)
BROKEN_INCOMPLETE_FINAL_RECEIPT = TestMeshCase(
    "broken_incomplete_final_receipt",
    final_receipt_complete=False,
)
BROKEN_SPEC_CONSUMER_FANOUT = TestMeshCase("broken_spec_consumer_fanout", spec_consumer_fanout_complete=False)
BROKEN_SPEC_CROSS_CHANGE = TestMeshCase("broken_spec_cross_change", spec_cross_change_reuse_authorized=False)
BROKEN_SPEC_RECEIPT_DUPLICATE = TestMeshCase("broken_spec_receipt_duplicate", spec_receipt_not_duplicated=False)


class EvaluateTestMeshPlan:
    name = "EvaluateTestMeshPlan"
    reads = ("TestMeshPolicy",)
    writes = (
        "case_name",
        "parent_child_partitions",
        "every_partition_owned",
        "owners_registered",
        "duplicate_ownership_blocked",
        "stale_evidence_visible",
        "skipped_tests_visible",
        "timeout_and_failed_visible",
        "background_completion_artifacts",
        "routine_release_split",
        "release_scope_blocks_missing_release_suite",
        "adapters_run_tests_not_testmesh",
        "required_inventory_revision_declared",
        "complete_inventory_owned",
        "progress_never_counts_as_pass",
        "final_receipt_complete",
        "spec_consumer_fanout_complete",
        "spec_cross_change_reuse_authorized",
        "spec_receipt_not_duplicated",
    )
    accepted_input_type = TestMeshCase
    input_description = "test mesh rollout case"
    output_description = "test mesh rollout policy"
    idempotency = "same case produces one rollout policy"

    def apply(self, input_obj: TestMeshCase, _state: TestMeshPolicy):
        new_state = TestMeshPolicy(
            case_name=input_obj.name,
            parent_child_partitions=input_obj.parent_child_partitions,
            every_partition_owned=input_obj.every_partition_owned,
            owners_registered=input_obj.owners_registered,
            duplicate_ownership_blocked=input_obj.duplicate_ownership_blocked,
            stale_evidence_visible=input_obj.stale_evidence_visible,
            skipped_tests_visible=input_obj.skipped_tests_visible,
            timeout_and_failed_visible=input_obj.timeout_and_failed_visible,
            background_completion_artifacts=input_obj.background_completion_artifacts,
            routine_release_split=input_obj.routine_release_split,
            release_scope_blocks_missing_release_suite=input_obj.release_scope_blocks_missing_release_suite,
            adapters_run_tests_not_testmesh=input_obj.adapters_run_tests_not_testmesh,
            required_inventory_revision_declared=input_obj.required_inventory_revision_declared,
            complete_inventory_owned=input_obj.complete_inventory_owned,
            progress_never_counts_as_pass=input_obj.progress_never_counts_as_pass,
            final_receipt_complete=input_obj.final_receipt_complete,
            spec_consumer_fanout_complete=input_obj.spec_consumer_fanout_complete,
            spec_cross_change_reuse_authorized=input_obj.spec_cross_change_reuse_authorized,
            spec_receipt_not_duplicated=input_obj.spec_receipt_not_duplicated,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected test mesh rollout decision into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: TestMeshPolicy) -> bool:
    return not state.case_name


def parent_child_partitions_exist(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.parent_child_partitions:
        return _fail("parent_child_partitions_exist", "slow tests remain a flat parent gate")
    return _pass()


def partition_ownership_is_complete(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.every_partition_owned:
        return _fail("partition_ownership_is_complete", "test partition lacks an owner")
    if not state.owners_registered:
        return _fail("partition_ownership_is_complete", "partition owner suite is not registered")
    return _pass()


def duplicate_owners_are_blocked(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.duplicate_ownership_blocked:
        return _fail("duplicate_owners_are_blocked", "duplicate state or side-effect owner is accepted")
    return _pass()


def evidence_gaps_stay_visible(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.stale_evidence_visible:
        return _fail("evidence_gaps_stay_visible", "stale test evidence is hidden")
    if not state.skipped_tests_visible:
        return _fail("evidence_gaps_stay_visible", "skipped tests are hidden inside a green summary")
    if not state.timeout_and_failed_visible:
        return _fail("evidence_gaps_stay_visible", "failed or timeout suites are not blockers")
    return _pass()


def background_needs_completion_artifacts(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.background_completion_artifacts:
        return _fail(
            "background_needs_completion_artifacts",
            "background progress is reported as completion without exit/result artifacts",
        )
    return _pass()


def routine_and_release_scope_are_distinct(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.routine_release_split:
        return _fail("routine_and_release_scope_are_distinct", "routine and release gates are conflated")
    if not state.release_scope_blocks_missing_release_suite:
        return _fail(
            "routine_and_release_scope_are_distinct",
            "release scope accepts missing release-required evidence",
        )
    return _pass()


def testmesh_does_not_run_tests(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.adapters_run_tests_not_testmesh:
        return _fail("testmesh_does_not_run_tests", "TestMesh directly runs project test commands")
    return _pass()


def required_inventory_is_revisioned_and_complete(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.required_inventory_revision_declared:
        return _fail(
            "required_inventory_is_revisioned_and_complete",
            "required test inventory lacks an explicit revision",
        )
    if not state.complete_inventory_owned:
        return _fail(
            "required_inventory_is_revisioned_and_complete",
            "caller-selected subset is reported as complete inventory",
        )
    return _pass()


def progress_is_not_final_evidence(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.progress_never_counts_as_pass:
        return _fail(
            "progress_is_not_final_evidence",
            "running, heartbeat, log, PID, or progress-only evidence counts as pass",
        )
    if not state.final_receipt_complete:
        return _fail(
            "progress_is_not_final_evidence",
            "final receipt lacks terminal status, artifact, fingerprint, coverage, or versions",
        )
    return _pass()


def spec_receipt_topology_is_exact(state: TestMeshPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.spec_consumer_fanout_complete:
        return _fail("spec_receipt_topology_is_exact", "spec receipt omits required task or obligation consumers")
    if not state.spec_cross_change_reuse_authorized:
        return _fail("spec_receipt_topology_is_exact", "cross-change reuse lacks provider authorization")
    if not state.spec_receipt_not_duplicated:
        return _fail("spec_receipt_topology_is_exact", "one spec receipt was copied into several child executions")
    return _pass()


INVARIANTS = (
    Invariant(
        "parent_child_partitions_exist",
        "Slow validation is split into parent/child evidence layers.",
        parent_child_partitions_exist,
    ),
    Invariant(
        "partition_ownership_is_complete",
        "Every test partition has a registered owner.",
        partition_ownership_is_complete,
    ),
    Invariant(
        "duplicate_owners_are_blocked",
        "Duplicate state and side-effect owners block parent confidence.",
        duplicate_owners_are_blocked,
    ),
    Invariant(
        "evidence_gaps_stay_visible",
        "Stale, skipped, failed, and timeout suite evidence stays visible.",
        evidence_gaps_stay_visible,
    ),
    Invariant(
        "background_needs_completion_artifacts",
        "Background progress is not completion without exit/result artifacts.",
        background_needs_completion_artifacts,
    ),
    Invariant(
        "routine_and_release_scope_are_distinct",
        "Routine confidence and release confidence are separate decisions.",
        routine_and_release_scope_are_distinct,
    ),
    Invariant(
        "testmesh_does_not_run_tests",
        "TestMesh reviews structured evidence instead of running project tests directly.",
        testmesh_does_not_run_tests,
    ),
    Invariant(
        "required_inventory_is_revisioned_and_complete",
        "Required TestMesh inventory is explicit, revisioned, and fully owned.",
        required_inventory_is_revisioned_and_complete,
    ),
    Invariant(
        "progress_is_not_final_evidence",
        "Only current complete terminal receipts count as passing evidence.",
        progress_is_not_final_evidence,
    ),
    Invariant(
        "spec_receipt_topology_is_exact",
        "One receipt fans out to complete consumers and cross-change reuse is explicitly authorized.",
        spec_receipt_topology_is_exact,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateTestMeshPlan(),), name="test_evidence_mesh_rollout")


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
    case: TestMeshCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=TestMeshPolicy(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "good_plan_passes",
        "A complete TestMesh rollout plan passes.",
        GOOD_PLAN,
        _expect_ok("complete TestMesh plan passes", labels=("good_test_mesh_plan",)),
    ),
    scenario(
        "flat_gate_fails",
        "Slow validation must not remain one flat parent gate.",
        BROKEN_FLAT_GATE,
        _expect_violation("flat slow gate fails", ("parent_child_partitions_exist",)),
    ),
    scenario(
        "missing_owner_fails",
        "Every test partition must have an owner.",
        BROKEN_MISSING_OWNER,
        _expect_violation("missing owner fails", ("partition_ownership_is_complete",)),
    ),
    scenario(
        "unregistered_owner_fails",
        "Partition owners must be registered child suites.",
        BROKEN_UNREGISTERED_OWNER,
        _expect_violation("unregistered owner fails", ("partition_ownership_is_complete",)),
    ),
    scenario(
        "duplicate_owner_fails",
        "Duplicate state or side-effect ownership must block parent confidence.",
        BROKEN_DUPLICATE_OWNER,
        _expect_violation("duplicate owner fails", ("duplicate_owners_are_blocked",)),
    ),
    scenario(
        "stale_evidence_fails",
        "Stale evidence cannot count as current parent evidence.",
        BROKEN_STALE_EVIDENCE,
        _expect_violation("stale evidence fails", ("evidence_gaps_stay_visible",)),
    ),
    scenario(
        "hidden_skips_fail",
        "Skipped tests must stay visible.",
        BROKEN_HIDDEN_SKIPS,
        _expect_violation("hidden skipped tests fail", ("evidence_gaps_stay_visible",)),
    ),
    scenario(
        "timeout_or_failure_fails",
        "Failed or timeout suites must block parent confidence.",
        BROKEN_TIMEOUT_HIDDEN,
        _expect_violation("timeout/failure hiding fails", ("evidence_gaps_stay_visible",)),
    ),
    scenario(
        "background_progress_only_fails",
        "Background progress without final artifacts is not completion.",
        BROKEN_BACKGROUND_PROGRESS_ONLY,
        _expect_violation("background progress-only fails", ("background_needs_completion_artifacts",)),
    ),
    scenario(
        "release_scope_requires_release_evidence",
        "Release scope must block missing release-required evidence.",
        BROKEN_RELEASE_SCOPE,
        _expect_violation("missing release suite fails", ("routine_and_release_scope_are_distinct",)),
    ),
    scenario(
        "testmesh_does_not_run_tests_directly",
        "TestMesh must review structured evidence instead of running commands itself.",
        BROKEN_TESTMESH_RUNS_TESTS,
        _expect_violation("direct test running fails", ("testmesh_does_not_run_tests",)),
    ),
    scenario(
        "missing_inventory_revision_fails",
        "Required inventory must name its revision.",
        BROKEN_MISSING_INVENTORY_REVISION,
        _expect_violation("missing inventory revision fails", ("required_inventory_is_revisioned_and_complete",)),
    ),
    scenario(
        "caller_subset_inventory_fails",
        "A caller-selected subset cannot stand in for complete required inventory.",
        BROKEN_CALLER_SUBSET_INVENTORY,
        _expect_violation("caller subset inventory fails", ("required_inventory_is_revisioned_and_complete",)),
    ),
    scenario(
        "progress_as_pass_fails",
        "Liveness signals are not terminal evidence.",
        BROKEN_PROGRESS_AS_PASS,
        _expect_violation("progress as pass fails", ("progress_is_not_final_evidence",)),
    ),
    scenario(
        "incomplete_final_receipt_fails",
        "Passing evidence needs a complete final receipt.",
        BROKEN_INCOMPLETE_FINAL_RECEIPT,
        _expect_violation("incomplete final receipt fails", ("progress_is_not_final_evidence",)),
    ),
    scenario(
        "spec_consumer_fanout_fails",
        "Every mapped task and obligation remains a consumer of the one receipt.",
        BROKEN_SPEC_CONSUMER_FANOUT,
        _expect_violation("incomplete spec consumer fan-out fails", ("spec_receipt_topology_is_exact",)),
    ),
    scenario(
        "spec_cross_change_reuse_fails",
        "Cross-change reuse must be provider-authorized.",
        BROKEN_SPEC_CROSS_CHANGE,
        _expect_violation("unauthorized cross-change reuse fails", ("spec_receipt_topology_is_exact",)),
    ),
    scenario(
        "spec_receipt_copy_fails",
        "One immutable receipt cannot masquerade as several child executions.",
        BROKEN_SPEC_RECEIPT_DUPLICATE,
        _expect_violation("duplicated spec receipt fails", ("spec_receipt_topology_is_exact",)),
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
    """Project the existing TestMesh owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-test-mesh",
        route_id="test_mesh_maintenance",
        owner_id="test_mesh_maintenance",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Partition large validation evidence and close only on current terminal child receipts.",
        claim_boundary="Projection only; inventory ownership, terminal receipts, freshness, timeouts, and parent consumption remain native TestMesh authority.",
    )
