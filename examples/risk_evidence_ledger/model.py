"""Executable rollout model for the risk evidence ledger confidence gate."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    Workflow,
    review_risk_evidence_ledger,
)


@dataclass(frozen=True)
class LedgerCase:
    case_id: str
    plan: RiskEvidenceLedgerPlan
    should_allow_full_claim: bool


@dataclass(frozen=True)
class ClaimAllowed:
    case_id: str
    decision: str


@dataclass(frozen=True)
class ClaimBlocked:
    case_id: str
    decision: str


@dataclass(frozen=True)
class ClaimState:
    allowed_cases: tuple[str, ...] = ()
    blocked_cases: tuple[str, ...] = ()
    gap_cases: tuple[str, ...] = ()


def _append_once(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)


def full_confidence_plan() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "full-confidence",
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                model_obligation_id="model:duplicate-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:duplicate-submit",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:duplicate-submit",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout",
                summary="external submit_order duplicate test passed",
            ),
        ),
    )


def internal_only_plan() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "internal-only",
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                model_obligation_id="model:duplicate-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:dedupe-helper",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:dedupe-helper",
                result_status=RISK_PROOF_STATUS_PASSED,
                assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH,
                producer_route="model_test_alignment",
                summary="helper-only test does not exercise the public API",
            ),
        ),
    )


def progress_only_plan() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "progress-only",
        rows=(
            RiskEvidenceRow(
                "release_regression",
                model_obligation_id="model:release-regression",
                proof_evidence_ids=("pytest:full-regression",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "pytest:full-regression",
                result_status=RISK_PROOF_STATUS_PROGRESS_ONLY,
                producer_route="test_mesh_maintenance",
                command="python -m pytest -q",
                summary="background run has not emitted final exit evidence",
            ),
        ),
    )


def ledger_cases() -> tuple[LedgerCase, ...]:
    return (
        LedgerCase("full-confidence", full_confidence_plan(), True),
        LedgerCase("internal-only", internal_only_plan(), False),
        LedgerCase("progress-only", progress_only_plan(), False),
    )


class RiskLedgerGate:
    name = "RiskLedgerGate"
    reads = ("allowed_cases", "blocked_cases", "gap_cases")
    writes = ("allowed_cases", "blocked_cases", "gap_cases")
    accepted_input_type = LedgerCase
    input_description = "LedgerCase"
    output_description = "ClaimAllowed or ClaimBlocked"
    idempotency = "A case is classified once; repeated review does not duplicate state."

    def apply(self, input_obj: LedgerCase, state: ClaimState) -> Iterable[FunctionResult]:
        report = review_risk_evidence_ledger(input_obj.plan)
        if report.ok:
            yield FunctionResult(
                ClaimAllowed(input_obj.case_id, report.decision),
                replace(state, allowed_cases=_append_once(state.allowed_cases, input_obj.case_id)),
                label="claim_allowed",
            )
            return
        yield FunctionResult(
            ClaimBlocked(input_obj.case_id, report.decision),
            replace(
                state,
                blocked_cases=_append_once(state.blocked_cases, input_obj.case_id),
                gap_cases=_append_once(state.gap_cases, input_obj.case_id),
            ),
            label="claim_blocked",
        )


class BrokenAllowAllRiskLedgerGate:
    name = "BrokenAllowAllRiskLedgerGate"
    reads = ("allowed_cases",)
    writes = ("allowed_cases",)
    accepted_input_type = LedgerCase

    def apply(self, input_obj: LedgerCase, state: ClaimState) -> Iterable[FunctionResult]:
        yield FunctionResult(
            ClaimAllowed(input_obj.case_id, "unreviewed_full_claim"),
            replace(state, allowed_cases=_append_once(state.allowed_cases, input_obj.case_id)),
            label="broken_claim_allowed_without_evidence",
        )


def no_known_gap_case_allowed(state: ClaimState, _trace) -> InvariantResult:
    known_gap_cases = {case.case_id for case in ledger_cases() if not case.should_allow_full_claim}
    bad = tuple(sorted(set(state.allowed_cases) & known_gap_cases))
    if bad:
        return InvariantResult.fail(
            f"ledger allowed known evidence gaps: {bad!r}",
            {"allowed_gap_cases": bad},
        )
    return InvariantResult.pass_()


def build_workflow(*, gate=None) -> Workflow:
    return Workflow((gate or RiskLedgerGate(),), name="risk_evidence_ledger_rollout")


def initial_state() -> ClaimState:
    return ClaimState()


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant(
            "no_known_gap_case_allowed",
            "Final confidence claims must be blocked when the ledger has known gaps.",
            no_known_gap_case_allowed,
        ),
    )
