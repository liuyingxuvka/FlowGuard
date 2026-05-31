"""Template text for FlowGuard test mesh route."""

from __future__ import annotations

TEST_MESH_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a parent test gate can trust child suites/scripts as owned validation regions.
Guards against: flat test splits, stale child suites, hidden skips, progress-only background runs, duplicate ownership, and release checks blocking routine confidence.
Use before editing: Update this TestMesh when changing validation layout, test partitions, child test scripts, slow regression gates, or background evidence contracts.
Run: python .flowguard/test_mesh/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ProofArtifactRef,
    TestMeshPlan,
    TestPartitionItem,
    TestResultReuseTicket,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


def proof_artifact(suite_id: str) -> ProofArtifactRef:
    result_path = f"tmp/{suite_id}.json"
    return ProofArtifactRef(
        f"artifact:{suite_id}",
        result_status="passed",
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
    )


def reuse_ticket(suite_id: str) -> TestResultReuseTicket:
    return TestResultReuseTicket(
        suite_id,
        previous_evidence_id=f"{suite_id}@previous",
        reason="same command, source, tested artifact, dependency, environment, and result fingerprints",
        command_fingerprint="sha256:command",
        test_source_fingerprint="sha256:test-source",
        tested_artifact_fingerprint="sha256:tested-artifact",
        dependency_fingerprints={"flowguard": "template"},
        environment_fingerprint="python:template",
        result_fingerprint="sha256:result",
    )


def routine_plan() -> TestMeshPlan:
    return TestMeshPlan(
        parent_suite_id="project-validation",
        decision_scope="routine",
        partition_items=(
            TestPartitionItem("unit-fast", owner_suite_id="unit"),
            TestPartitionItem("runtime-contract", owner_suite_id="runtime"),
        ),
        child_suites=(
            TestSuiteEvidence(
                "unit",
                command="python -m unittest tests.test_fast",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=True,
                test_count=12,
                selected_count=12,
            ),
            TestSuiteEvidence(
                "runtime",
                command="python -m unittest tests.test_runtime_contract",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=True,
                test_count=8,
                selected_count=8,
                result_reused=True,
                reuse_ticket=reuse_ticket("runtime"),
                proof_artifact=proof_artifact("runtime"),
            ),
            TestSuiteEvidence(
                "release-full",
                command="python -m unittest discover -s tests",
                layer="release",
                result_status="not_run",
                evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
                release_required=True,
                not_run_reason="release-only regression deferred during routine check",
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "project-validation-model",
            target_suite_ids=("unit", "runtime", "release-full"),
            covered_partition_item_ids=("unit-fast", "runtime-contract"),
            rationale="derived from the parent validation FlowGuard model and release gate boundaries",
        ),
    )


def broken_plan() -> TestMeshPlan:
    return TestMeshPlan(
        parent_suite_id="project-validation",
        partition_items=(TestPartitionItem("runtime-contract", owner_suite_id="runtime"),),
        child_suites=(
            TestSuiteEvidence(
                "runtime",
                command="python -m unittest tests.test_runtime_contract",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=False,
                skipped_count=2,
                skipped_visible=False,
                stale_reasons=("source_changed",),
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "project-validation-model",
            target_suite_ids=("runtime",),
            covered_partition_item_ids=("runtime-contract",),
            rationale="derived from the parent validation FlowGuard model and runtime contract boundary",
        ),
    )


def run_checks():
    return review_test_mesh(routine_plan()), review_test_mesh(broken_plan())
'''

TEST_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the TestMesh template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=3))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

TEST_MESH_NOTES_TEMPLATE = """# FlowGuard TestMesh Notes

Use this scaffold to keep a project's validation hierarchy explicit.

## What TestMesh Reviews

- how a broad parent test gate is split into child suites or child scripts;
- which FlowGuard validation-structure model derived the target child
  suites/scripts before evidence is trusted;
- which child owns each behavior, state, command, invariant, or release
  partition;
- whether child suite/script evidence is current and strong enough for the
  parent;
- whether background logs include final exit/result artifacts;
- whether skipped, timed-out, not-run, or release-only checks remain visible.

TestMesh is parallel to ModelMesh and StructureMesh: the object being split is
the test structure. The parent should consume child ownership and evidence
contracts instead of expanding every child test case into one giant parent graph.
A child suite can become its own parent gate when it needs another layer.

The target child-suite layout should be recorded as a model-derived split
before parent confidence is claimed. A partition map by itself is not enough.

TestMesh does not run your tests. Project adapters should run pytest, unittest,
Playwright, simulation runners, or shell commands, then feed structured evidence
into the TestMesh model.
"""

__all__ = [
    'TEST_MESH_MODEL_TEMPLATE',
    'TEST_MESH_RUN_CHECKS_TEMPLATE',
    'TEST_MESH_NOTES_TEMPLATE',
]
