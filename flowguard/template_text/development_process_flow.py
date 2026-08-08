"""Template text for FlowGuard development process flow route."""

from __future__ import annotations

DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review a development lifecycle as a sibling process route, tracking artifact versions and validation evidence freshness before done or release claims.
Guards against: stale validation after code/test/model/requirement/UI observed inventory/UI functional capability coverage/UI functional chain/UI source-baseline interaction/UI done-claim/payload-schema/field-lifecycle/contract-exhaustion interaction group, shard, or receipt changes, oversized direct model evidence, slow or broad direct validation evidence, progress-only evidence, hidden skips, missing V-style validation pairs, peer writes, and release overclaims.
Use before editing: Update this development process flow when changing development ordering, UI click-through, observed-inventory, functional capability coverage, functional-chain, source-baseline interaction, done-claim, payload-pack validation gates, ContractExhaustionMesh generated cases/shards/receipts, release readiness, or evidence freshness policy.
Run: python .flowguard/development_process_flow/run_checks.py
"""

from __future__ import annotations

from tempfile import TemporaryDirectory

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
    ImplementationAdmissionPlan,
    MODEL_MATURATION_CONFIDENCE_FULL,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,
    ModelMaturationReceiptPublication,
    ModelMaturationReceiptRef,
    ModelMaturationReport,
    ModelMaturationVerificationContext,
    ReceiptVerificationContext,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    build_model_maturation_receipt,
    fingerprint_value,
    review_development_process_flow,
    review_implementation_admission,
    save_evidence_receipt,
    snapshot_bytes,
    verify_model_maturation_receipt,
)
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject


def resolved_path_quality(model_id, model_fingerprint):
    def identity(name):
        return fingerprint_value({"model_id": model_id, "identity": name})

    subject = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"behavior:{model_id}",
        model_fingerprint=model_fingerprint,
        normalized_facts_fingerprint=identity("normalized-facts"),
        retained_element_inventory_fingerprint=identity("retained-elements"),
        purpose_fingerprint=identity("purpose"),
        intent_fingerprint=identity("intent"),
        obligation_fingerprint=identity("obligations"),
        provider_fingerprint=identity("provider"),
        dependency_fingerprint=identity("dependencies"),
        code_fingerprint=identity("code"),
        test_fingerprint=identity("tests"),
        oracle_fingerprint=identity("oracles"),
        evidence_fingerprint=identity("evidence"),
        currentness_id="revision:template-current",
    )
    result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
        subject_fingerprint=subject.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=identity("necessity-witnesses"),
        detail_evidence_fingerprint=identity("path-detail"),
        producer_id="model_maturation:path-quality",
        currentness_id=subject.currentness_id,
    )
    return subject, result


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{artifact_id.replace(':', '_')}.json"
    return ProofArtifactRef(
        artifact_id,
        producer_route="test_mesh_maintenance",
        command="python -m unittest tests.test_checkout",
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=result_path,
        started_at="2026-08-02T00:00:00+00:00",
        finished_at="2026-08-02T00:00:01+00:00",
        subject_id="model:checkout",
        subject_fingerprint="sha256:checkout",
        artifact_fingerprints={result_path: "sha256:template"},
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


def implementation_admission():
    model_id = "checkout-functional-model"
    candidate_model_fingerprint = fingerprint_value(
        {"model_id": model_id, "candidate": "template-current"}
    )
    path_quality_subject, path_quality_result = resolved_path_quality(
        model_id, candidate_model_fingerprint
    )
    report = ModelMaturationReport(
        ok=True,
        plan_id="plan:checkout",
        evidence_id="maturation:checkout",
        task_id="task:checkout",
        model_id=model_id,
        coverage_demand_fingerprint="sha256:demand",
        candidate_model_fingerprint=candidate_model_fingerprint,
        coverage_universe_id="coverage:checkout",
        coverage_universe_fingerprint="sha256:coverage",
        input_fingerprint="sha256:intake",
        evidence_fingerprint="sha256:evidence",
        decision=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
        confidence=MODEL_MATURATION_CONFIDENCE_FULL,
        terminal_reason=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
        required_path_quality_model_ids=(model_id,),
        path_quality_subjects=(path_quality_subject,),
        path_quality_results=(path_quality_result,),
        owner_resolution_ids=("resolution:checkout",),
        owner_resolution_fingerprints=("sha256:resolution-checkout",),
        owner_resolution_owner_ids=("model_first_function_flow",),
    )
    snapshot = snapshot_bytes(
        "artifact:checkout-model",
        b"checkout-model",
        path_token="<WORKSPACE>/.flowguard/checkout/model.py",
        obligation_ids=("obligation:checkout-maturation",),
    )
    environment = {"python_version": "template"}
    publication = ModelMaturationReceiptPublication(
        producer_id="flowguard.model_maturation",
        producer_version="template",
        command=("python", ".flowguard/checkout/run_checks.py"),
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        environment_metadata=environment,
        contract_hash="sha256:contract",
        check_manifest_hash="sha256:manifest",
        suite_map_hash="sha256:suite",
        input_snapshots=(snapshot,),
        covered_obligation_ids=("obligation:checkout-maturation",),
    )
    receipt = build_model_maturation_receipt(report, publication)
    with TemporaryDirectory() as receipt_root:
        save_evidence_receipt(receipt, output_directory=receipt_root)
        receipt_context = ReceiptVerificationContext(
            input_snapshots={snapshot.artifact_id: snapshot},
            contract_hash=publication.contract_hash,
            check_manifest_hash=publication.check_manifest_hash,
            suite_map_hash=publication.suite_map_hash,
            producer_id=publication.producer_id,
            producer_version=publication.producer_version,
            environment_fingerprint=fingerprint_value(environment),
            proof_artifact_fingerprint=report.evidence_fingerprint,
            result_fingerprint=fingerprint_value(report.to_dict()),
            command=publication.command,
            working_directory_token=publication.working_directory_token,
            proof_artifact_id=report.evidence_id,
            required_obligation_ids=publication.covered_obligation_ids,
            eligible_claim_scopes=(MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,),
            receipt_store_output_directory=receipt_root,
        )
        verification = verify_model_maturation_receipt(
            ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
            ModelMaturationVerificationContext(
                receipt_context=receipt_context,
                task_id=report.task_id,
                model_id=report.model_id,
                candidate_model_fingerprint=report.candidate_model_fingerprint,
                coverage_demand_fingerprint=report.coverage_demand_fingerprint,
                coverage_universe_id=report.coverage_universe_id,
                coverage_universe_fingerprint=report.coverage_universe_fingerprint,
                input_fingerprint=report.input_fingerprint,
                evidence_fingerprint=report.evidence_fingerprint,
                required_path_quality_model_ids=report.required_path_quality_model_ids,
                path_quality_subjects=report.path_quality_subjects,
                path_quality_results=report.path_quality_results,
                path_quality_result_set_fingerprint=report.path_quality_result_set_fingerprint,
                owner_resolution_ids=report.owner_resolution_ids,
                owner_resolution_fingerprints=report.owner_resolution_fingerprints,
                owner_resolution_owner_ids=report.owner_resolution_owner_ids,
                required_receipt_fingerprint=receipt.fingerprint,
            ),
            output_directory=receipt_root,
        )
    maturation = verification.verified_maturation
    if maturation is None:
        raise RuntimeError("template maturation receipt did not verify")
    return review_implementation_admission(
        ImplementationAdmissionPlan(
            "admission:checkout",
            maturation_evidence=maturation,
            implementation_requested=True,
            requested_path_ids=("checkout/orchestrator.py",),
        )
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
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "2", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
                proof_artifact=proof_artifact("artifact:unit-pass", "unit-current"),
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
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
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "1", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                evidence_ids=("unit-pass",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
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
        implementation_admission(),
    )
'''

DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE = '''"""Run the DevelopmentProcessFlow template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken, admission = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=6))
    print()
    print(admission.to_dict())
    return 0 if routine.ok and not broken.ok and admission.implementation_ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE = """# FlowGuard DevelopmentProcessFlow Notes

Use this scaffold to model a development lifecycle as a stateful process.

## What DevelopmentProcessFlow Reviews

- versioned requirements, designs, models, code, tests, docs, release assets,
  adapters, field lifecycle meshes, field projections, replacement
  dispositions, bug-repair closure rows, and route-owner report artifacts;
- ordered development actions that read, write, invalidate, or claim evidence;
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
- a separate implementation-admission result: `ready` only after exact
  closed-for-task maturation, `ready_scoped` only under exact bounded user
  authorization, `no_code_requested` for read-only work, otherwise blocked or
  stale. Authorization never rewrites the maturation decision.

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
for ordinary work. When active, it first proves hard equivalence, then chooses
one diagnostic boundary and one execution mode. Hard blockers always stop
invalid downstream work, and material evidence always stales the decision.

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
