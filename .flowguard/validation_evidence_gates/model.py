"""Executable model for FlowGuard's permanent validation-evidence kernel.

The kernel answers one bounded question: may one declared validation claim use
one exact producer result as current proof?  It does not execute checks, own
domain-specific validation, synchronize installations, order releases, or
delete persistent evidence.

Function blocks use the FlowGuard shape ``Input x State -> Set(Output x State)``.
Run with ``python .flowguard/validation_evidence_gates/run_checks.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)
from flowguard.evidence_receipts import (
    RECEIPT_STATUS_FAIL,
    RECEIPT_STATUS_NOT_RUN,
    RECEIPT_STATUS_PASS,
    RECEIPT_STATUS_PROGRESS_ONLY,
    RECEIPT_STATUS_SKIPPED,
    RECEIPT_STATUS_STALE,
)
from flowguard.review import review_scenarios


MODEL_ID = "validation_evidence_gates"
FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
COMPACT_RESULT_SCHEMA_VERSION = "flowguard.validation-evidence-kernel-model-result.v2"
FORBIDDEN_COMPACT_TRACE_KEYS = (
    "counterexample_trace",
    "final_state",
    "model_report",
    "scenario_run",
    "steps",
    "traces",
)
LIFECYCLE_OWNER_ID = "flowguard.evidence_lifecycle"
CLAIM_SCOPE = "declared_validation_claim"
CLAIM_BOUNDARY = (
    "This kernel licenses only the declared claim whose exact subject, source, "
    "normative specification, test inventory, check manifest, producer, "
    "toolchain, environment, validation head, proof artifact, result, and "
    "covered obligations match one current terminal-pass receipt. It does not "
    "prove domain correctness, UI click-through, payload semantics, manual "
    "operability, installed-skill parity, release order, or lifecycle deletion."
)
SPECIALIST_DELEGATIONS = (
    "ui-flow-structure",
    "artifact-payload-owner",
    "manual-operability-owner",
    "skillguard-installation",
    "development-process-flow",
    LIFECYCLE_OWNER_ID,
)


# Continuing implementation ownership plus this model and its native runner.
SOURCE_INPUT_PATHS = (
    ".flowguard/validation_evidence_gates/model.py",
    ".flowguard/validation_evidence_gates/run_checks.py",
    "flowguard/baseline.py",
    "flowguard/evidence_fields.py",
    "flowguard/evidence_lifecycle.py",
    "flowguard/evidence_receipts.py",
    "flowguard/layered_proof.py",
    "flowguard/model_regressions.py",
    "flowguard/model_revision_owner_evidence.py",
    "flowguard/proof_artifact.py",
    "flowguard/validation_ownership.py",
    "flowguard/validation_results.py",
)
SPEC_INPUT_PATHS = (
    "openspec/specs/validation-evidence-gates/spec.md",
    "openspec/specs/flowguard-evidence-field-structure/spec.md",
    "openspec/specs/flowguard-evidence-receipts/spec.md",
    "openspec/specs/flowguard-validation-evidence-lifecycle/spec.md",
    "openspec/specs/proof-artifact-bound-evidence/spec.md",
)
TEST_INPUT_PATHS = (
    "tests/test_evidence_baseline.py",
    "tests/test_evidence_field_structure.py",
    "tests/test_evidence_lifecycle.py",
    "tests/test_evidence_receipts.py",
    "tests/test_proof_artifact.py",
    "tests/test_proof_artifact_binding.py",
    "tests/test_model_regression_manifest.py",
    "tests/test_model_revision_owner_evidence.py",
    "tests/test_validation_evidence_gate_runner.py",
    "tests/test_validation_execution_ownership.py",
)


def _is_sha256(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return False
    try:
        int(value[7:], 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class ValidationIdentity:
    """The proof subject and every freshness-relevant identity."""

    subject_id: str
    subject_fingerprint: str
    source_inputs_fingerprint: str
    spec_inputs_fingerprint: str
    test_inputs_fingerprint: str
    check_manifest_fingerprint: str
    toolchain_fingerprint: str
    environment_fingerprint: str
    validation_head_fingerprint: str

    def valid(self) -> bool:
        return bool(self.subject_id) and all(
            _is_sha256(value)
            for value in (
                self.subject_fingerprint,
                self.source_inputs_fingerprint,
                self.spec_inputs_fingerprint,
                self.test_inputs_fingerprint,
                self.check_manifest_fingerprint,
                self.toolchain_fingerprint,
                self.environment_fingerprint,
                self.validation_head_fingerprint,
            )
        )


@dataclass(frozen=True)
class EvidenceNeed:
    need_id: str
    claim_id: str
    claim_scope: str
    required_obligation_ids: tuple[str, ...]
    execution_owner_ids: tuple[str, ...]
    identity: ValidationIdentity
    source_input_paths: tuple[str, ...]
    spec_input_paths: tuple[str, ...]
    test_input_paths: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceObservation:
    need_id: str
    receipt_id: str
    execution_owner_id: str
    claim_id: str
    claim_scope: str
    covered_obligation_ids: tuple[str, ...]
    identity: ValidationIdentity
    result_status: str
    terminal: bool
    exit_code: int | None
    proof_artifact_id: str
    proof_artifact_fingerprint: str
    result_fingerprint: str
    observation_scope: str = "invocation_local"
    initial_observation_fingerprint: str = ""
    final_freshness_status: str = "not_run"
    final_freshness_fingerprint: str = ""
    complete_observation_count: int = 0
    semantic_verification_count: int = 0
    per_leaf_source_current_rebuild_count: int = 0
    per_leaf_receipt_store_scan_count: int = 0
    receipt_reconciliation_count: int = 0
    failed_ids: tuple[str, ...] = ()
    skipped_ids: tuple[str, ...] = ()
    not_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentEvidence:
    need_id: str
    receipt_id: str
    identity: ValidationIdentity
    proof_artifact_id: str
    proof_artifact_fingerprint: str
    result_fingerprint: str


@dataclass(frozen=True)
class ClaimRequest:
    need_id: str
    claim_id: str
    claim_scope: str


@dataclass(frozen=True)
class EvidenceCase:
    need: EvidenceNeed
    observation: EvidenceObservation
    current: CurrentEvidence
    claim: ClaimRequest
    post_claim_current: CurrentEvidence | None = None


@dataclass(frozen=True)
class LifecycleRequest:
    action_id: str
    action: str
    execution_owner_id: str
    explicit_boundary: bool
    recoverable_plan: bool
    automatic: bool = False
    prior_quarantine_id: str = ""


@dataclass(frozen=True)
class CompactEvidenceProjection:
    schema_version: str
    raw_scenario_result_fingerprints: tuple[str, ...]
    inline_raw_trace_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrozenEvidenceCase:
    case: EvidenceCase


@dataclass(frozen=True)
class ClassifiedEvidenceCase:
    case: EvidenceCase
    current: bool


@dataclass(frozen=True)
class ClaimDecision:
    need_id: str
    claim_id: str
    claim_scope: str
    authorized: bool
    finding_codes: tuple[str, ...]
    claim_boundary: str = CLAIM_BOUNDARY


@dataclass(frozen=True)
class ClaimDecidedCase:
    case: EvidenceCase
    decision: ClaimDecision


@dataclass(frozen=True)
class ClaimReviewComplete:
    decision: ClaimDecision
    current: bool


@dataclass(frozen=True)
class LifecycleDecision:
    action_id: str
    action: str
    authorized: bool
    finding_codes: tuple[str, ...]


@dataclass(frozen=True)
class CompactEvidenceProjectionDecision:
    current: bool
    finding_codes: tuple[str, ...]


@dataclass(frozen=True)
class State:
    case: EvidenceCase | None = None
    evidence_current: bool = False
    decision: ClaimDecision | None = None
    claim_active: bool = False
    claim_invalidated: bool = False
    lifecycle_request: LifecycleRequest | None = None
    lifecycle_decision: LifecycleDecision | None = None
    compact_evidence_projection: CompactEvidenceProjection | None = None
    compact_evidence_current: bool = False


def _exact_current(case: EvidenceCase, current: CurrentEvidence) -> bool:
    observation = case.observation
    need = case.need
    return (
        need.need_id == observation.need_id == current.need_id
        and need.identity == observation.identity == current.identity
        and observation.receipt_id == current.receipt_id
        and observation.proof_artifact_id == current.proof_artifact_id
        and observation.proof_artifact_fingerprint == current.proof_artifact_fingerprint
        and observation.result_fingerprint == current.result_fingerprint
        and observation.result_status != RECEIPT_STATUS_STALE
    )


def _claim_finding_codes(case: EvidenceCase, evidence_current: bool) -> tuple[str, ...]:
    need, observation, current, claim = (
        case.need,
        case.observation,
        case.current,
        case.claim,
    )
    findings: list[str] = []
    for actual, expected, name in (
        (need.source_input_paths, SOURCE_INPUT_PATHS, "source_input_inventory_mismatch"),
        (need.spec_input_paths, SPEC_INPUT_PATHS, "spec_input_inventory_mismatch"),
        (need.test_input_paths, TEST_INPUT_PATHS, "test_input_inventory_mismatch"),
    ):
        if actual != expected:
            findings.append(name)
    if not need.identity.valid():
        findings.append("invalid_frozen_identity")
    if len(need.execution_owner_ids) != 1 or len(set(need.execution_owner_ids)) != 1:
        findings.append("execution_owner_not_exact")
    elif observation.execution_owner_id != need.execution_owner_ids[0]:
        findings.append("foreign_execution_owner")
    if observation.result_status != RECEIPT_STATUS_PASS:
        findings.append(f"result_status_{observation.result_status}")
    if not observation.terminal:
        findings.append("result_not_terminal")
    if observation.exit_code != 0:
        findings.append("terminal_exit_not_zero")
    for values, code in (
        (observation.failed_ids, "failed_ids_visible"),
        (observation.skipped_ids, "skipped_ids_visible"),
        (observation.not_run_ids, "not_run_ids_visible"),
    ):
        if values:
            findings.append(code)
    if not observation.receipt_id:
        findings.append("missing_receipt_id")
    if not observation.proof_artifact_id or not _is_sha256(observation.proof_artifact_fingerprint):
        findings.append("invalid_proof_artifact_identity")
    if not _is_sha256(observation.result_fingerprint):
        findings.append("invalid_result_fingerprint")
    if observation.observation_scope != "invocation_local":
        findings.append("validation_observation_not_invocation_local")
    if not _is_sha256(observation.initial_observation_fingerprint):
        findings.append("initial_validation_observation_missing")
    if (
        observation.final_freshness_status != RECEIPT_STATUS_PASS
        or not _is_sha256(observation.final_freshness_fingerprint)
    ):
        findings.append("final_validation_freshness_not_pass")
    if observation.complete_observation_count != 2:
        findings.append("complete_validation_observation_count_not_minimal")
    if observation.semantic_verification_count != 1:
        findings.append("semantic_verification_repeated_or_missing")
    if observation.per_leaf_source_current_rebuild_count != 0:
        findings.append("per_leaf_source_current_rebuild_repeated")
    if observation.per_leaf_receipt_store_scan_count != 0:
        findings.append("per_leaf_receipt_store_scan_repeated")
    if observation.receipt_reconciliation_count != 1:
        findings.append("receipt_reconciliation_repeated_or_missing")
    if not _exact_current(case, current):
        findings.append("current_identity_mismatch")
    if not evidence_current:
        findings.append("evidence_not_current")
    if claim.claim_id != need.claim_id or observation.claim_id != need.claim_id:
        findings.append("claim_id_mismatch")
    if claim.claim_scope != need.claim_scope or observation.claim_scope != need.claim_scope:
        findings.append("claim_scope_mismatch")
    if not set(need.required_obligation_ids).issubset(observation.covered_obligation_ids):
        findings.append("required_obligations_not_covered")
    return tuple(dict.fromkeys(findings))


def _lifecycle_finding_codes(request: LifecycleRequest) -> tuple[str, ...]:
    if request.action == "retain":
        return ()
    findings: list[str] = []
    if request.action not in {"quarantine", "purge"}:
        findings.append("unknown_lifecycle_action")
    if request.execution_owner_id != LIFECYCLE_OWNER_ID:
        findings.append("foreign_lifecycle_owner")
    if not request.explicit_boundary:
        findings.append("missing_lifecycle_boundary")
    if not request.recoverable_plan:
        findings.append("missing_recoverable_plan")
    if request.action == "purge" and not request.prior_quarantine_id:
        findings.append("purge_without_exact_quarantine")
    if request.action == "purge" and request.automatic:
        findings.append("automatic_persistent_purge_forbidden")
    return tuple(dict.fromkeys(findings))


class FreezeEvidenceCase:
    name = "FreezeEvidenceCase"
    reads = ()
    writes = ("case", "evidence_current", "decision", "claim_active")
    accepted_input_type = EvidenceCase
    input_description = "Claim, owner, obligations, receipt, and current identity"
    output_description = "Frozen validation-evidence case"
    idempotency = "the same case freezes the same validation boundary"

    def apply(self, input_obj: EvidenceCase, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=FrozenEvidenceCase(input_obj),
            new_state=replace(
                state,
                case=input_obj,
                evidence_current=False,
                decision=None,
                claim_active=False,
                claim_invalidated=False,
            ),
            label="evidence_need_frozen",
            reason="froze one claim and its exact proof identities",
        )


class ClassifyEvidence:
    name = "ClassifyEvidence"
    reads = ("case",)
    writes = ("evidence_current",)
    accepted_input_type = FrozenEvidenceCase
    input_description = "Frozen receipt and independently observed current evidence"
    output_description = "Freshness classification without claim promotion"
    idempotency = "the same identities give the same currentness"

    def apply(self, input_obj: FrozenEvidenceCase, state: State) -> Iterable[FunctionResult]:
        current = _exact_current(input_obj.case, input_obj.case.current)
        yield FunctionResult(
            output=ClassifiedEvidenceCase(input_obj.case, current),
            new_state=replace(state, evidence_current=current),
            label="evidence_current" if current else "evidence_stale",
            reason="compared frozen, receipt, proof-artifact, result, and current-head identities",
        )


class DecideClaim:
    name = "DecideClaim"
    reads = ("case", "evidence_current")
    writes = ("decision", "claim_active")
    accepted_input_type = ClassifiedEvidenceCase
    input_description = "Classified evidence at one declared claim boundary"
    output_description = "Authorized or rejected claim decision"
    idempotency = "the same current proof gives the same claim decision"

    def apply(self, input_obj: ClassifiedEvidenceCase, state: State) -> Iterable[FunctionResult]:
        findings = _claim_finding_codes(input_obj.case, state.evidence_current)
        request = input_obj.case.claim
        decision = ClaimDecision(
            request.need_id,
            request.claim_id,
            request.claim_scope,
            not findings,
            findings,
        )
        yield FunctionResult(
            output=ClaimDecidedCase(input_obj.case, decision),
            new_state=replace(state, decision=decision, claim_active=decision.authorized),
            label="claim_authorized" if decision.authorized else "claim_rejected",
            reason=CLAIM_BOUNDARY if decision.authorized else ",".join(findings),
        )


class BrokenAuthorizeClaim(DecideClaim):
    """Known-bad implementation used only to prove the invariants execute."""

    name = "BrokenAuthorizeClaim"

    def apply(self, input_obj: ClassifiedEvidenceCase, state: State) -> Iterable[FunctionResult]:
        request = input_obj.case.claim
        decision = ClaimDecision(
            request.need_id,
            request.claim_id,
            request.claim_scope,
            True,
            (),
        )
        yield FunctionResult(
            output=ClaimDecidedCase(input_obj.case, decision),
            new_state=replace(state, decision=decision, claim_active=True),
            label="broken_claim_authorized",
            reason="known-bad claim bypass",
        )


class RefreshAfterClaim:
    name = "RefreshAfterClaim"
    reads = ("case", "decision", "claim_active")
    writes = ("evidence_current", "claim_active", "claim_invalidated")
    accepted_input_type = ClaimDecidedCase
    input_description = "Optional later current identity observed after claim decision"
    output_description = "Current claim or revoked stale claim"
    idempotency = "the same post-claim identity gives the same revocation decision"

    def apply(self, input_obj: ClaimDecidedCase, state: State) -> Iterable[FunctionResult]:
        later = input_obj.case.post_claim_current
        current = state.evidence_current if later is None else _exact_current(input_obj.case, later)
        invalidated = later is not None and state.claim_active and not current
        yield FunctionResult(
            output=ClaimReviewComplete(input_obj.decision, current),
            new_state=replace(
                state,
                evidence_current=current,
                claim_active=state.claim_active if later is None else state.claim_active and current,
                claim_invalidated=state.claim_invalidated or invalidated,
            ),
            label="evidence_invalidated" if invalidated else "claim_review_complete",
            reason="later governed-input drift revokes the active claim" if invalidated else "claim currentness retained",
        )


class ReviewLifecycleRequest:
    name = "ReviewLifecycleRequest"
    reads = ()
    writes = ("lifecycle_request", "lifecycle_decision")
    accepted_input_type = LifecycleRequest
    input_description = "Retain, quarantine, or purge handoff"
    output_description = "Lifecycle-owner admission without storage mutation"
    idempotency = "the same lifecycle request gives the same handoff decision"

    def apply(self, input_obj: LifecycleRequest, state: State) -> Iterable[FunctionResult]:
        findings = _lifecycle_finding_codes(input_obj)
        decision = LifecycleDecision(input_obj.action_id, input_obj.action, not findings, findings)
        yield FunctionResult(
            output=decision,
            new_state=replace(state, lifecycle_request=input_obj, lifecycle_decision=decision),
            label="lifecycle_handoff_authorized" if decision.authorized else "lifecycle_handoff_blocked",
            reason="classification only; the lifecycle owner performs any storage operation",
        )


class BrokenAuthorizeLifecycle(ReviewLifecycleRequest):
    name = "BrokenAuthorizeLifecycle"

    def apply(self, input_obj: LifecycleRequest, state: State) -> Iterable[FunctionResult]:
        decision = LifecycleDecision(input_obj.action_id, input_obj.action, True, ())
        yield FunctionResult(
            output=decision,
            new_state=replace(state, lifecycle_request=input_obj, lifecycle_decision=decision),
            label="broken_lifecycle_authorized",
            reason="known-bad persistent cleanup bypass",
        )


def _compact_projection_finding_codes(
    projection: CompactEvidenceProjection,
) -> tuple[str, ...]:
    findings: list[str] = []
    if projection.schema_version != COMPACT_RESULT_SCHEMA_VERSION:
        findings.append("compact_result_schema_not_current")
    if not projection.raw_scenario_result_fingerprints or any(
        not _is_sha256(value)
        for value in projection.raw_scenario_result_fingerprints
    ):
        findings.append("compact_result_scenario_fingerprint_invalid")
    forbidden = tuple(
        sorted(set(projection.inline_raw_trace_keys) & set(FORBIDDEN_COMPACT_TRACE_KEYS))
    )
    if forbidden:
        findings.append("compact_result_inlines_raw_trace_payload")
    return tuple(findings)


class ReviewCompactEvidenceProjection:
    name = "ReviewCompactEvidenceProjection"
    reads = ()
    writes = ("compact_evidence_projection", "compact_evidence_current")
    accepted_input_type = CompactEvidenceProjection
    input_description = "Versioned compact scenario evidence projection"
    output_description = "Current compact evidence decision without raw trace payloads"
    idempotency = "the same schema, fingerprints, and keys give the same currentness"

    def apply(
        self,
        input_obj: CompactEvidenceProjection,
        state: State,
    ) -> Iterable[FunctionResult]:
        findings = _compact_projection_finding_codes(input_obj)
        current = not findings
        yield FunctionResult(
            output=CompactEvidenceProjectionDecision(current, findings),
            new_state=replace(
                state,
                compact_evidence_projection=input_obj,
                compact_evidence_current=current,
            ),
            label="compact_evidence_current" if current else "compact_evidence_rejected",
            reason=(
                "current v2 projection retains scenario fingerprints without raw traces"
                if current
                else ",".join(findings)
            ),
        )


class BrokenAdmitInlineRawEvidence(ReviewCompactEvidenceProjection):
    """Known-bad implementation that marks duplicated raw traces current."""

    name = "BrokenAdmitInlineRawEvidence"

    def apply(
        self,
        input_obj: CompactEvidenceProjection,
        state: State,
    ) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=CompactEvidenceProjectionDecision(True, ()),
            new_state=replace(
                state,
                compact_evidence_projection=input_obj,
                compact_evidence_current=True,
            ),
            label="broken_inline_raw_evidence_admitted",
            reason="known-bad repeated raw trace payloads marked current",
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(message: str) -> InvariantResult:
    return InvariantResult.fail(message)


def current_kernel_inputs_are_bound(state: State, _trace: object) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    case = state.case
    if case is None or (
        case.need.source_input_paths != SOURCE_INPUT_PATHS
        or case.need.spec_input_paths != SPEC_INPUT_PATHS
        or case.need.test_input_paths != TEST_INPUT_PATHS
    ):
        return _fail("an active claim omits or substitutes permanent source/spec/test inputs")
    return _pass()


def claim_requires_exact_execution_owner(state: State, _trace: object) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    case = state.case
    if case is None or (
        len(case.need.execution_owner_ids) != 1
        or len(set(case.need.execution_owner_ids)) != 1
        or case.observation.execution_owner_id != case.need.execution_owner_ids[0]
    ):
        return _fail("an active claim lacks one exact matching execution owner")
    return _pass()


def claim_requires_terminal_pass(state: State, _trace: object) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    observation = state.case.observation if state.case is not None else None
    if observation is None or (
        observation.result_status != RECEIPT_STATUS_PASS
        or not observation.terminal
        or observation.exit_code != 0
        or observation.failed_ids
        or observation.skipped_ids
        or observation.not_run_ids
    ):
        return _fail("progress, stale, failed, skipped, not-run, or hidden child gaps supported a claim")
    return _pass()


def claim_requires_current_exact_proof(state: State, _trace: object) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    case = state.case
    if case is None:
        return _fail("an active claim lacks its proof case")
    observation, current = case.observation, case.current
    exact = (
        case.need.identity.valid()
        and _exact_current(case, current)
        and bool(observation.receipt_id)
        and bool(observation.proof_artifact_id)
        and _is_sha256(observation.proof_artifact_fingerprint)
        and _is_sha256(observation.result_fingerprint)
        and state.evidence_current
    )
    if not exact:
        return _fail("an active claim used stale or mismatched subject/input/toolchain/environment/head/proof identity")
    return _pass()


def claim_requires_bounded_observation_reuse(
    state: State,
    _trace: object,
) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    observation = state.case.observation if state.case is not None else None
    if observation is None or (
        observation.observation_scope != "invocation_local"
        or not _is_sha256(observation.initial_observation_fingerprint)
        or observation.final_freshness_status != RECEIPT_STATUS_PASS
        or not _is_sha256(observation.final_freshness_fingerprint)
        or observation.complete_observation_count != 2
        or observation.semantic_verification_count != 1
        or observation.per_leaf_source_current_rebuild_count != 0
        or observation.per_leaf_receipt_store_scan_count != 0
        or observation.receipt_reconciliation_count != 1
    ):
        return _fail(
            "a current claim repeated semantic verification or per-leaf source/receipt discovery, persisted a transient observation, or omitted its one final freshness and receipt reconciliation boundary"
        )
    return _pass()


def claim_scope_is_exact(state: State, _trace: object) -> InvariantResult:
    if not state.claim_active:
        return _pass()
    case, decision = state.case, state.decision
    if case is None or decision is None:
        return _fail("an active claim has no exact scope binding")
    need, observation = case.need, case.observation
    if (
        decision.claim_id != need.claim_id
        or decision.claim_scope != need.claim_scope
        or observation.claim_id != need.claim_id
        or observation.claim_scope != need.claim_scope
        or not set(need.required_obligation_ids).issubset(observation.covered_obligation_ids)
        or decision.claim_boundary != CLAIM_BOUNDARY
    ):
        return _fail("an active claim widened its id, scope, obligations, or claim boundary")
    return _pass()


def persistent_cleanup_requires_lifecycle_owner(state: State, _trace: object) -> InvariantResult:
    request, decision = state.lifecycle_request, state.lifecycle_decision
    if decision is None or not decision.authorized:
        return _pass()
    if request is None or _lifecycle_finding_codes(request):
        return _fail("ordinary validation authorized persistent cleanup without exact lifecycle evidence")
    return _pass()


def compact_evidence_forbids_inline_raw_traces(
    state: State,
    _trace: object,
) -> InvariantResult:
    if not state.compact_evidence_current:
        return _pass()
    projection = state.compact_evidence_projection
    if projection is None or _compact_projection_finding_codes(projection):
        return _fail(
            "current compact evidence used a stale schema, invalid scenario fingerprint, "
            "or inlined scenario/model/trace state"
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "current_kernel_inputs_are_bound",
        "Current claims bind permanent source, normative specification, and test inputs.",
        current_kernel_inputs_are_bound,
    ),
    Invariant(
        "claim_requires_exact_execution_owner",
        "Exactly one execution owner produces the receipt used by a claim.",
        claim_requires_exact_execution_owner,
    ),
    Invariant(
        "claim_requires_terminal_pass",
        "Only terminal pass with zero hidden failed/skipped/not-run ids supports a claim.",
        claim_requires_terminal_pass,
    ),
    Invariant(
        "claim_requires_current_exact_proof",
        "Subject, inputs, toolchain, environment, head, receipt, proof, and result remain exact-current.",
        claim_requires_current_exact_proof,
    ),
    Invariant(
        "claim_requires_bounded_observation_reuse",
        "One invocation verifies semantics once, performs one final identity comparison and one receipt reconciliation, performs no per-leaf source or receipt rediscovery, and persists no observation authority.",
        claim_requires_bounded_observation_reuse,
    ),
    Invariant(
        "claim_scope_is_exact",
        "A receipt supports only its declared claim, obligations, and boundary.",
        claim_scope_is_exact,
    ),
    Invariant(
        "persistent_cleanup_requires_lifecycle_owner",
        "Ordinary validation cannot authorize persistent evidence deletion.",
        persistent_cleanup_requires_lifecycle_owner,
    ),
    Invariant(
        "compact_evidence_forbids_inline_raw_traces",
        "Current compact evidence retains fingerprints instead of repeated raw execution traces.",
        compact_evidence_forbids_inline_raw_traces,
    ),
)


def evidence_workflow(*, broken_claim: bool = False) -> Workflow:
    return Workflow(
        (
            FreezeEvidenceCase(),
            ClassifyEvidence(),
            BrokenAuthorizeClaim() if broken_claim else DecideClaim(),
            RefreshAfterClaim(),
        ),
        name="broken_validation_evidence_claim" if broken_claim else "validation_evidence_kernel",
    )


def lifecycle_workflow(*, broken: bool = False) -> Workflow:
    return Workflow(
        (BrokenAuthorizeLifecycle() if broken else ReviewLifecycleRequest(),),
        name="broken_validation_evidence_lifecycle" if broken else "validation_evidence_lifecycle_handoff",
    )


def compact_evidence_workflow(*, broken: bool = False) -> Workflow:
    return Workflow(
        (BrokenAdmitInlineRawEvidence() if broken else ReviewCompactEvidenceProjection(),),
        name=(
            "broken_compact_validation_evidence_projection"
            if broken
            else "compact_validation_evidence_projection"
        ),
    )


def _need(identity: ValidationIdentity) -> EvidenceNeed:
    return EvidenceNeed(
        need_id="need:validation-evidence-kernel",
        claim_id="claim:validation-evidence-kernel-current",
        claim_scope=CLAIM_SCOPE,
        required_obligation_ids=("obligation:terminal-current-exact-proof",),
        execution_owner_ids=("validation-owner:evidence-kernel",),
        identity=identity,
        source_input_paths=SOURCE_INPUT_PATHS,
        spec_input_paths=SPEC_INPUT_PATHS,
        test_input_paths=TEST_INPUT_PATHS,
    )


def _observation(identity: ValidationIdentity) -> EvidenceObservation:
    need = _need(identity)
    return EvidenceObservation(
        need_id=need.need_id,
        receipt_id="receipt:validation-evidence-kernel:terminal",
        execution_owner_id=need.execution_owner_ids[0],
        claim_id=need.claim_id,
        claim_scope=need.claim_scope,
        covered_obligation_ids=need.required_obligation_ids,
        identity=identity,
        result_status=RECEIPT_STATUS_PASS,
        terminal=True,
        exit_code=0,
        proof_artifact_id="proof:validation-evidence-kernel:terminal",
        proof_artifact_fingerprint="sha256:" + "a" * 64,
        result_fingerprint="sha256:" + "b" * 64,
        observation_scope="invocation_local",
        initial_observation_fingerprint="sha256:" + "c" * 64,
        final_freshness_status=RECEIPT_STATUS_PASS,
        final_freshness_fingerprint="sha256:" + "d" * 64,
        complete_observation_count=2,
        semantic_verification_count=1,
        per_leaf_source_current_rebuild_count=0,
        per_leaf_receipt_store_scan_count=0,
        receipt_reconciliation_count=1,
    )


def _current(observation: EvidenceObservation) -> CurrentEvidence:
    return CurrentEvidence(
        observation.need_id,
        observation.receipt_id,
        observation.identity,
        observation.proof_artifact_id,
        observation.proof_artifact_fingerprint,
        observation.result_fingerprint,
    )


def _case(
    need: EvidenceNeed,
    observation: EvidenceObservation,
    *,
    current: CurrentEvidence | None = None,
    claim: ClaimRequest | None = None,
    post_claim_current: CurrentEvidence | None = None,
) -> EvidenceCase:
    return EvidenceCase(
        need,
        observation,
        current or _current(observation),
        claim or ClaimRequest(need.need_id, need.claim_id, need.claim_scope),
        post_claim_current,
    )


def _expect_ok(summary: str, labels: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=tuple(labels),
        summary=summary,
    )


def _expect_violation(summary: str, name: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=(name,),
        summary=summary,
    )


def _scenario(
    name: str,
    input_obj: object,
    expected: ScenarioExpectation,
    *,
    broken_claim: bool = False,
    lifecycle: bool = False,
    broken_lifecycle: bool = False,
    compact_evidence: bool = False,
    broken_compact_evidence: bool = False,
) -> Scenario:
    workflow = (
        compact_evidence_workflow(broken=broken_compact_evidence)
        if compact_evidence
        else (
            lifecycle_workflow(broken=broken_lifecycle)
            if lifecycle
            else evidence_workflow(broken_claim=broken_claim)
        )
    )
    return Scenario(
        name=name,
        description=name.replace("_", " "),
        workflow=workflow,
        initial_state=State(),
        external_input_sequence=(input_obj,),
        invariants=INVARIANTS,
        expected=expected,
    )


def build_scenarios(identity: ValidationIdentity) -> tuple[Scenario, ...]:
    """Build current-input good cases and executable known-bad variants."""

    need, good = _need(identity), _observation(identity)
    scenarios: list[Scenario] = [
        _scenario(
            "terminal_current_exact_proof_passes",
            _case(need, good),
            _expect_ok("terminal current exact proof passes", ("claim_authorized",)),
        )
    ]

    nonpass = (
        ("progress_only", replace(good, result_status=RECEIPT_STATUS_PROGRESS_ONLY, terminal=False, exit_code=None)),
        ("stale", replace(good, result_status=RECEIPT_STATUS_STALE)),
        ("failed", replace(good, result_status=RECEIPT_STATUS_FAIL, exit_code=1, failed_ids=("check:failed",))),
        ("skipped", replace(good, result_status=RECEIPT_STATUS_SKIPPED, exit_code=None, skipped_ids=("check:skipped",))),
        ("not_run", replace(good, result_status=RECEIPT_STATUS_NOT_RUN, terminal=False, exit_code=None, not_run_ids=("check:not-run",))),
    )
    for case_id, observation in nonpass:
        scenarios.extend(
            (
                _scenario(
                    f"{case_id}_is_rejected",
                    _case(need, observation),
                    _expect_ok(f"{case_id} is rejected", ("claim_rejected",)),
                ),
                _scenario(
                    f"known_bad_{case_id}_acceptance_is_detected",
                    _case(need, observation),
                    _expect_violation(
                        f"known-bad {case_id} acceptance is detected",
                        "claim_requires_terminal_pass",
                    ),
                    broken_claim=True,
                ),
            )
        )

    for case_id, observation in (
        (
            "persistent_observation_authority",
            replace(good, observation_scope="persistent_cache"),
        ),
        (
            "missing_final_freshness",
            replace(
                good,
                final_freshness_status=RECEIPT_STATUS_NOT_RUN,
                final_freshness_fingerprint="",
                complete_observation_count=1,
            ),
        ),
        (
            "repeated_semantic_verification",
            replace(good, semantic_verification_count=6),
        ),
        (
            "per_leaf_source_current_rebuild",
            replace(good, per_leaf_source_current_rebuild_count=6),
        ),
        (
            "per_leaf_receipt_store_scan",
            replace(good, per_leaf_receipt_store_scan_count=6),
        ),
        (
            "missing_receipt_reconciliation",
            replace(good, receipt_reconciliation_count=0),
        ),
    ):
        scenarios.extend(
            (
                _scenario(
                    f"{case_id}_is_rejected",
                    _case(need, observation),
                    _expect_ok(f"{case_id} is rejected", ("claim_rejected",)),
                ),
                _scenario(
                    f"known_bad_{case_id}_acceptance_is_detected",
                    _case(need, observation),
                    _expect_violation(
                        f"known-bad {case_id} acceptance is detected",
                        "claim_requires_bounded_observation_reuse",
                    ),
                    broken_claim=True,
                ),
            )
        )

    for case_id, observation in (
        ("hidden_failed_child", replace(good, failed_ids=("child:failed",))),
        ("hidden_skipped_child", replace(good, skipped_ids=("child:skipped",))),
        ("hidden_not_run_child", replace(good, not_run_ids=("child:not-run",))),
    ):
        scenarios.append(
            _scenario(
                f"known_bad_{case_id}_is_detected",
                _case(need, observation),
                _expect_violation(
                    f"known-bad {case_id} is detected",
                    "claim_requires_terminal_pass",
                ),
                broken_claim=True,
            )
        )

    duplicate_need = replace(
        need,
        execution_owner_ids=(need.execution_owner_ids[0], "validation-owner:duplicate"),
    )
    scenarios.extend(
        (
            _scenario(
                "known_bad_duplicate_owner_is_detected",
                _case(duplicate_need, good),
                _expect_violation("duplicate owner is detected", "claim_requires_exact_execution_owner"),
                broken_claim=True,
            ),
            _scenario(
                "known_bad_foreign_owner_is_detected",
                _case(need, replace(good, execution_owner_id="validation-owner:foreign")),
                _expect_violation("foreign owner is detected", "claim_requires_exact_execution_owner"),
                broken_claim=True,
            ),
        )
    )

    identity_fields = (
        "subject_fingerprint",
        "source_inputs_fingerprint",
        "spec_inputs_fingerprint",
        "test_inputs_fingerprint",
        "check_manifest_fingerprint",
        "toolchain_fingerprint",
        "environment_fingerprint",
        "validation_head_fingerprint",
    )
    for index, field_name in enumerate(identity_fields, start=1):
        changed = replace(identity, **{field_name: "sha256:" + f"{index:x}" * 64})
        scenarios.append(
            _scenario(
                f"known_bad_{field_name}_drift_is_detected",
                _case(need, good, current=replace(_current(good), identity=changed)),
                _expect_violation(
                    f"{field_name} drift is detected",
                    "claim_requires_current_exact_proof",
                ),
                broken_claim=True,
            )
        )

    for case_id, current in (
        ("proof_fingerprint_mismatch", replace(_current(good), proof_artifact_fingerprint="sha256:" + "c" * 64)),
        ("result_fingerprint_mismatch", replace(_current(good), result_fingerprint="sha256:" + "d" * 64)),
    ):
        scenarios.append(
            _scenario(
                f"known_bad_{case_id}_is_detected",
                _case(need, good, current=current),
                _expect_violation(f"{case_id} is detected", "claim_requires_current_exact_proof"),
                broken_claim=True,
            )
        )

    scenarios.extend(
        (
            _scenario(
                "known_bad_missing_real_input_is_detected",
                _case(replace(need, source_input_paths=SOURCE_INPUT_PATHS[:-1]), good),
                _expect_violation("missing permanent input is detected", "current_kernel_inputs_are_bound"),
                broken_claim=True,
            ),
            _scenario(
                "known_bad_broad_claim_is_detected",
                _case(
                    need,
                    good,
                    claim=ClaimRequest(need.need_id, need.claim_id, "broad_release"),
                ),
                _expect_violation("broad claim is detected", "claim_scope_is_exact"),
                broken_claim=True,
            ),
        )
    )

    drifted = replace(identity, source_inputs_fingerprint="sha256:" + "e" * 64)
    scenarios.append(
        _scenario(
            "later_source_change_revokes_prior_claim",
            _case(
                need,
                good,
                post_claim_current=replace(_current(good), identity=drifted),
            ),
            _expect_ok(
                "later source drift revokes the active claim",
                ("claim_authorized", "evidence_invalidated"),
            ),
        )
    )

    explicit_quarantine = LifecycleRequest(
        "lifecycle:quarantine:explicit",
        "quarantine",
        LIFECYCLE_OWNER_ID,
        True,
        True,
    )
    automatic_purge = LifecycleRequest(
        "lifecycle:purge:automatic",
        "purge",
        "validation-owner:evidence-kernel",
        False,
        False,
        automatic=True,
    )
    scenarios.extend(
        (
            _scenario(
                "explicit_recoverable_quarantine_is_delegated",
                explicit_quarantine,
                _expect_ok("explicit quarantine handoff is admitted", ("lifecycle_handoff_authorized",)),
                lifecycle=True,
            ),
            _scenario(
                "ordinary_automatic_purge_is_blocked",
                automatic_purge,
                _expect_ok("ordinary automatic purge is blocked", ("lifecycle_handoff_blocked",)),
                lifecycle=True,
            ),
            _scenario(
                "known_bad_automatic_purge_is_detected",
                automatic_purge,
                _expect_violation(
                    "known-bad automatic purge is detected",
                    "persistent_cleanup_requires_lifecycle_owner",
                ),
                lifecycle=True,
                broken_lifecycle=True,
            ),
        )
    )
    scenarios.append(
        _scenario(
            "known_bad_repeated_inline_raw_traces_are_detected",
            CompactEvidenceProjection(
                schema_version=COMPACT_RESULT_SCHEMA_VERSION,
                raw_scenario_result_fingerprints=("sha256:" + "f" * 64,),
                inline_raw_trace_keys=FORBIDDEN_COMPACT_TRACE_KEYS,
            ),
            _expect_violation(
                "known-bad repeated raw scenario and trace payloads are detected",
                "compact_evidence_forbids_inline_raw_traces",
            ),
            compact_evidence=True,
            broken_compact_evidence=True,
        )
    )
    return tuple(scenarios)


def run_review(identity: ValidationIdentity):
    return review_scenarios(build_scenarios(identity))


__all__ = [
    "CLAIM_BOUNDARY",
    "COMPACT_RESULT_SCHEMA_VERSION",
    "FLOWGUARD_MODEL_MARKER",
    "FORBIDDEN_COMPACT_TRACE_KEYS",
    "MODEL_ID",
    "SOURCE_INPUT_PATHS",
    "SPEC_INPUT_PATHS",
    "SPECIALIST_DELEGATIONS",
    "TEST_INPUT_PATHS",
    "ValidationIdentity",
    "build_scenarios",
    "run_review",
]
