"""Template text for FlowGuard development process flow route."""

from __future__ import annotations

DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE = '''"""FlowGuard model

Purpose: Review a development lifecycle as a sibling process route, tracking artifact versions and validation evidence freshness before done or release claims.
Guards against: stale validation after code/test/model/requirement/UI observed inventory/UI functional capability coverage/UI functional chain/UI source-baseline interaction/UI done-claim/payload-schema/field-lifecycle/contract-exhaustion interaction group, shard, or receipt changes, oversized direct model evidence, slow or broad direct validation evidence, progress-only evidence, hidden skips, missing V-style validation pairs, peer writes, and release overclaims.
Use before editing: Update this development process flow when changing development ordering, UI click-through, observed-inventory, functional capability coverage, functional-chain, source-baseline interaction, done-claim, payload-pack validation gates, ContractExhaustionMesh generated cases/shards/receipts, release readiness, or evidence freshness policy.
Run: python -m flowguard map models development_process_flow
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE,
    PROCESS_ARTIFACT_FIELD_LIFECYCLE,
    PROCESS_ARTIFACT_FIELD_PROJECTION,
    PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_ARTIFACT_UI_DONE_CLAIM,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN,
    PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY,
    PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE,
    PROCESS_EVIDENCE_FIELD_LIFECYCLE,
    PROCESS_EVIDENCE_FIELD_PROJECTION,
    PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE,
    PROCESS_EVIDENCE_MODEL_MISS_REVIEW,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_EVIDENCE_UI_DONE_CLAIM_REVIEW,
    PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_EVIDENCE_UI_FUNCTIONAL_CHAIN,
    PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,
    PROCESS_EVIDENCE_UI_OBSERVED_INVENTORY,
    PROCESS_SCOPE_RELEASE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


def fingerprint_value(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f".flowguard/cache/demo-proof/{artifact_id.replace(':', '_')}.json"
    result_bytes = json.dumps(
        {
            "artifact_id": artifact_id,
            "covered_obligation_ids": list(covered),
            "result_status": PROCESS_EVIDENCE_PASSED,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result_file = Path(result_path)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_bytes(result_bytes)
    result_fingerprint = "sha256:" + hashlib.sha256(result_bytes).hexdigest()
    return ProofArtifactRef(
        artifact_id,
        producer_route="test_mesh",
        command="python -m pytest tests/test_checkout.py",
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=result_path,
        started_at="2026-08-02T00:00:00+00:00",
        finished_at="2026-08-02T00:00:01+00:00",
        subject_id="model:checkout",
        subject_fingerprint=fingerprint_value({"subject_id": "model:checkout"}),
        artifact_fingerprints={"result": result_fingerprint},
        result_fingerprint=result_fingerprint,
        covered_obligation_ids=covered,
    )


def artifacts(code_version: str = "2", test_version: str = "1", requirement_version: str = "1"):
    return (
        ProcessArtifact("requirements.checkout", PROCESS_ARTIFACT_REQUIREMENT, requirement_version),
        ProcessArtifact(
            "model.checkout",
            PROCESS_ARTIFACT_MODEL,
            "1",
            upstream_artifact_ids=("requirements.checkout",),
        ),
        ProcessArtifact(
            "code.checkout",
            PROCESS_ARTIFACT_CODE,
            code_version,
            upstream_artifact_ids=("requirements.checkout", "model.checkout"),
        ),
        ProcessArtifact("tests.checkout", PROCESS_ARTIFACT_TEST, test_version),
    )


def routine_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-development-lifecycle",
        require_proof_artifacts=True,
        artifacts=artifacts(code_version="2"),
        actions=(
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("claim-done", action_type="claim_done", required_validation_ids=("unit-current",)),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "2", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m pytest tests/test_checkout.py",
                proof_artifact=proof_artifact("artifact:unit-pass", "unit-current"),
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                v_model_pair=True,
                command="python -m pytest tests/test_checkout.py",
            ),
        ),
    )


def broken_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-broken-lifecycle",
        artifacts=artifacts(code_version="2", requirement_version="2"),
        actions=(
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("edit-requirement", writes_artifacts=("requirements.checkout",)),
            ProcessAction(
                "claim-release",
                action_type="claim_release",
                required_evidence_ids=("unit-pass",),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "1", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m pytest tests/test_checkout.py",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                evidence_ids=("unit-pass",),
                v_model_pair=True,
                command="python -m pytest tests/test_checkout.py",
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "requirements-affect-code-validation",
                upstream_artifact_id="requirements.checkout",
                invalidates_artifact_ids=("code.checkout", "model.checkout"),
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
    )


def run_checks():
    return (
        review_development_process_flow(routine_plan()),
        review_development_process_flow(broken_plan()),
    )
'''

DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE = '''"""Run the DevelopmentProcessFlow template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=6))
    print()
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
'''

DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE = """# FlowGuard DevelopmentProcessFlow Notes

Use this scaffold to model a development lifecycle as a stateful process.

## What DevelopmentProcessFlow Reviews

- versioned requirements, designs, models, code, tests, docs, release assets,
  adapters, field lifecycle meshes, field projections, replacement
  dispositions, bug-repair closure rows, and route-owner report artifacts;
- ordered development actions that read, write, invalidate, or claim evidence;
- for each registered artifact with a non-empty `owner`, every writing or
  invalidating action uses an exactly matching `actor`, including before the
  first validation; generic actor labels do not bypass this blocker;
- validation evidence and the exact artifact versions it covers;
- UI observed inventory, functional capability coverage, functional-chain,
  source-baseline, done-claim, and real-surface artifact-payload case revisions
  when evidence covers them;
- ContractExhaustionMesh interaction groups, generated combination case ids,
  coverage shard ids, and model coverage receipt ids when evidence covers them;
- verifier changes, such as tests or model files changing after evidence was
  produced;
- freshness rules that propagate upstream changes to downstream artifacts;
- AutoSplit, ModelMesh, or TestMesh evidence ids when split review is
  relevant to the process claim;
- whether done, release, archive, or publish claims have current evidence;
- independent freshness for the shadow workspace, formal repository, editable
  package installation, installed skill suite, and local Git version;
- peer-write observations and post-write revalidation so synchronization
  preserves concurrent work instead of overwriting or rolling it back;
- the coverage-complete revalidation needed when evidence is stale or missing.
  Revalidation recommendations include the route that produced prior evidence,
  proof-artifact requirement, freshness gap codes, and claim scopes blocked
  until rerun. A measured finite candidate set may support a minimum claim;
  estimated inputs support only a preferred set.
- a conditional internal process optimization only when explicitly requested,
  several equivalent routes exist, rework risk is material, or a diagnostic
  boundary choice matters;
- a diagnostic boundary (`targeted`, `declared_complete`, or `budgeted`) and
  execution mode (`sequential` or `safe_parallel`) without prescribing one
  universal order;
- stable Finding Ledger references, relation-backed root-cause repair groups,
  visible hard blockers, and current affected-obligation revalidation.

For field-bearing work, add `PROCESS_ARTIFACT_FIELD_LIFECYCLE`,
`PROCESS_ARTIFACT_FIELD_PROJECTION`, `PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION`,
or `PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE` artifacts when those rows change. Pair
them with `PROCESS_EVIDENCE_FIELD_LIFECYCLE`,
`PROCESS_EVIDENCE_FIELD_PROJECTION`, `PROCESS_EVIDENCE_MODEL_MISS_REVIEW`, or
`PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE` evidence so later done/release claims can
see when field evidence became stale.

For UI work that claims user-visible functions are implemented or runnable,
track capability inventories or output-contract/binding rows with
`PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE` and pair them with
`PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE`. A later UI model,
feature-contract, task, output, or implementation change should stale that
evidence before release confidence.

## Route Owner Boundary

This is the development-process simulator front door and execution-freshness
owner. It can reference evidence produced by ModelMesh, TestMesh, StructureMesh,
Model-Test Alignment, LongCheck, or Conformance Adoption through evidence ids
and freshness metadata. It does not inspect, supervise, replace, or repair
those routes. If route-owner evidence is failed, stale, skipped, missing, or
progress-only, this route keeps that lifecycle gap visible for the current
process claim.

The internal mode order is `plan_detailing` -> `strategy_selection` ->
`agent_workflow` -> `execution_freshness`. The optimization mode stays inactive
for ordinary work. `agent_workflow` is an internal, risk-admitted rehearsal:
explicit user request, shared write, a write that can invalidate
post-validation evidence, an agent/route workflow change, or multiple
independent owners with irreversible side effects. An ordinary cross-owner
handoff alone uses execution freshness through this owner. Multiple skills,
tools, or an external-effect label alone do not admit rehearsal; simple
read-only, single-owner, single-tool, targeted-test work records
`not_triggered` and continues through the owning route. When optimization is
active, one declared candidate is an admissibility check without cost or Pareto
comparison; multiple candidates require the declared comparison evidence.
Hard blockers stop invalid downstream work, and material evidence stales the
decision.

When direct model/test evidence is large, incomplete, slow, broad,
progress-only, or release-only, run AutoSplit, ModelMesh, or TestMesh as its own
route and consume that route's evidence id or proof artifact here. Do not copy
AutoSplit metrics onto `ProcessEvidence`.

Use this route when development ordering, artifact overwrite, verification
freshness, or release readiness is the risk. It is not mandatory for every
small edit and it does not make FlowGuard a task orchestrator.
"""

DEVELOPMENT_PROCESS_STRATEGY_NOTES_TEMPLATE = """# FlowGuard Development-Process Strategy Notes

This is an internal capability of `development_process_flow`, not another
public route. Ordinary single-route work needs no optimization records.

Activate only for `explicit_request`, `multiple_equivalent_routes`,
`material_rework_risk`, or `diagnostic_boundary_choice`. Compare candidates
only after proving the same required outcome, evidence, safety, side effects,
dependency authority, and execution-owner authority.

One declared candidate is checked for admissibility without cost/Pareto
comparison. Multiple declared candidates need complete current comparison
evidence and retain unresolved ties or trade-offs.

Choose `targeted`, `declared_complete`, or `budgeted` diagnosis, then
`sequential` or isolation-proven `safe_parallel` execution. Keep diagnostic
counts in TestMesh, raw findings in the Finding Ledger, external planning
inputs in read-only provider-neutral WorkContexts, and model/code/test ownership in ordinary Model-Test
Alignment. Group findings only with relation evidence, repair the root cause,
and revalidate every affected obligation.

Hard blockers stop invalid downstream work. Material evidence stales the old
decision. Estimated evidence may support a preferred route; only measured
costs over an exhausted finite set may support a minimum claim, never a global
optimum.
"""

__all__ = [
    'DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE',
    'DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE',
    'DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE',
    'DEVELOPMENT_PROCESS_STRATEGY_NOTES_TEMPLATE',
]
