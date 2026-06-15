"""Formal workflow-suite runner helpers for FlowGuard self-model evidence."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Iterable, Mapping, Sequence

from .explorer import Explorer
from .plan import FlowGuardCheckPlan
from .risk import RiskIntent, RiskProfile
from .risk_templates import (
    KnownBadProof,
    MinimumModelContract,
    TemplateHarvestReview,
    TemplateReuseReview,
)
from .runner import run_model_first_checks
from .summary_report import FlowGuardSummaryReport


BLOCKING_STATUSES = frozenset({"failed", "blocked"})
CAUGHT_LABEL_HINTS = (
    "reject",
    "blocked",
    "stale",
    "non_pass",
    "violation",
    "scoped",
    "missing",
    "invalid",
    "unsafe",
    "fail",
)


@dataclass(frozen=True)
class FormalWorkflowCase:
    """One expected result inside a formal FlowGuard workflow suite."""

    name: str
    workflow: Any
    expect_ok: bool
    required_labels: tuple[str, ...] = ()
    external_inputs: tuple[Any, ...] | None = None
    max_sequence_length: int | None = None
    terminal_predicate: Any = None
    protected_error_class: str = ""
    known_bad_labels: tuple[str, ...] = ()

    def __init__(
        self,
        name: str,
        workflow: Any,
        expect_ok: bool,
        *,
        required_labels: Sequence[str] = (),
        external_inputs: Sequence[Any] | None = None,
        max_sequence_length: int | None = None,
        terminal_predicate: Any = None,
        protected_error_class: str = "",
        known_bad_labels: Sequence[str] = (),
    ) -> None:
        object.__setattr__(self, "name", str(name))
        object.__setattr__(self, "workflow", workflow)
        object.__setattr__(self, "expect_ok", bool(expect_ok))
        object.__setattr__(self, "required_labels", tuple(str(label) for label in required_labels))
        object.__setattr__(self, "external_inputs", None if external_inputs is None else tuple(external_inputs))
        object.__setattr__(
            self,
            "max_sequence_length",
            None if max_sequence_length is None else int(max_sequence_length),
        )
        object.__setattr__(self, "terminal_predicate", terminal_predicate)
        object.__setattr__(self, "protected_error_class", str(protected_error_class or ""))
        object.__setattr__(self, "known_bad_labels", tuple(str(label) for label in known_bad_labels))


@dataclass(frozen=True)
class FormalWorkflowCaseResult:
    """Observed formal result for one workflow case."""

    name: str
    expected_ok: bool
    observed_ok: bool
    summary: FlowGuardSummaryReport

    @property
    def ok(self) -> bool:
        return self.expected_ok is self.observed_ok


@dataclass(frozen=True)
class FormalWorkflowSuiteReport:
    """Formal suite result with generated known-bad proof rows."""

    suite_name: str
    case_results: tuple[FormalWorkflowCaseResult, ...]
    known_bad_proofs: tuple[KnownBadProof, ...]
    findings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.findings and all(result.ok for result in self.case_results)

    def format_text(self, *, verbose: bool = False) -> str:
        lines = [
            f"=== flowguard formal workflow suite: {self.suite_name} ===",
            f"status: {'pass' if self.ok else 'failed'}",
            f"known_bad_proofs: {len(self.known_bad_proofs)}",
        ]
        for finding in self.findings:
            lines.append(f"- finding: {finding}")
        for result in self.case_results:
            status = "OK" if result.observed_ok else "VIOLATION"
            expected = "OK" if result.expected_ok else "VIOLATION"
            lines.append(
                f"- {result.name}: observed={status} expected={expected} "
                f"match={'yes' if result.ok else 'no'} formal={result.summary.overall_status}"
            )
            if verbose or not result.ok:
                lines.extend("  " + line for line in result.summary.format_text(verbose=verbose).splitlines())
        return "\n".join(lines)


def run_formal_workflow_suite(
    suite_name: str,
    cases: Sequence[FormalWorkflowCase],
    *,
    initial_states: Iterable[Any],
    external_inputs: Sequence[Any],
    invariants: Sequence[Any] = (),
    max_sequence_length: int = 1,
    terminal_predicate: Any = None,
    required_labels: Sequence[str] = (),
    protected_error_class: str = "self_model_known_bad_case",
    modeled_boundary: str | None = None,
    risk_classes: Sequence[str] = ("module_boundary",),
    print_reports: bool = True,
    verbose: bool = False,
    progress: bool = False,
) -> FormalWorkflowSuiteReport:
    """Run cases through formal CheckPlan evidence and current known-bad proof.

    The helper is intended for FlowGuard's repository-owned self-model runners.
    It keeps finite exploration inside package code while scripts consume
    `run_model_first_checks(...)` summaries and generated `KnownBadProof` rows.
    """

    normalized_cases = tuple(cases)
    base_initial_states = tuple(initial_states)
    base_external_inputs = tuple(external_inputs)
    base_invariants = tuple(invariants)
    base_required_labels = tuple(str(label) for label in required_labels)
    boundary = modeled_boundary or suite_name
    default_error = protected_error_class or "self_model_known_bad_case"

    proof_rows, proof_findings = _collect_known_bad_proofs(
        normalized_cases,
        initial_states=base_initial_states,
        external_inputs=base_external_inputs,
        invariants=base_invariants,
        max_sequence_length=max_sequence_length,
        terminal_predicate=terminal_predicate,
        required_labels=base_required_labels,
        protected_error_class=default_error,
        suite_name=suite_name,
    )

    results: list[FormalWorkflowCaseResult] = []
    for case in normalized_cases:
        plan = _build_plan(
            suite_name=suite_name,
            case=case,
            initial_states=base_initial_states,
            external_inputs=base_external_inputs,
            invariants=base_invariants,
            max_sequence_length=max_sequence_length,
            terminal_predicate=terminal_predicate,
            required_labels=base_required_labels,
            protected_error_class=default_error,
            modeled_boundary=boundary,
            risk_classes=risk_classes,
            known_bad_proofs=proof_rows,
        )
        summary = _run_model_first_checks(plan, progress=progress)
        results.append(
            FormalWorkflowCaseResult(
                name=case.name,
                expected_ok=case.expect_ok,
                observed_ok=_summary_observed_ok(summary),
                summary=summary,
            )
        )

    report = FormalWorkflowSuiteReport(
        suite_name=suite_name,
        case_results=tuple(results),
        known_bad_proofs=tuple(proof_rows),
        findings=tuple(proof_findings),
    )
    if print_reports:
        print(report.format_text(verbose=verbose))
        print()
    return report


def _run_model_first_checks(plan: FlowGuardCheckPlan, *, progress: bool) -> FlowGuardSummaryReport:
    if progress:
        return run_model_first_checks(plan)
    old_value = os.environ.get("FLOWGUARD_PROGRESS")
    os.environ["FLOWGUARD_PROGRESS"] = "0"
    try:
        return run_model_first_checks(plan)
    finally:
        if old_value is None:
            os.environ.pop("FLOWGUARD_PROGRESS", None)
        else:
            os.environ["FLOWGUARD_PROGRESS"] = old_value


def _collect_known_bad_proofs(
    cases: Sequence[FormalWorkflowCase],
    *,
    initial_states: tuple[Any, ...],
    external_inputs: tuple[Any, ...],
    invariants: tuple[Any, ...],
    max_sequence_length: int,
    terminal_predicate: Any,
    required_labels: tuple[str, ...],
    protected_error_class: str,
    suite_name: str,
) -> tuple[tuple[KnownBadProof, ...], tuple[str, ...]]:
    proofs: list[KnownBadProof] = []
    findings: list[str] = []

    for case in cases:
        case_error = case.protected_error_class or protected_error_class
        case_inputs = _case_external_inputs(case, external_inputs)
        case_length = _case_max_sequence_length(case, max_sequence_length)
        case_terminal = _case_terminal_predicate(case, terminal_predicate)
        case_labels = _case_required_labels(case, required_labels)
        probe = _run_probe(
            case.workflow,
            initial_states=initial_states,
            external_inputs=case_inputs,
            invariants=invariants,
            max_sequence_length=case_length,
            terminal_predicate=case_terminal,
            required_labels=case_labels,
        )
        if not case.expect_ok:
            observed_status = "failed" if not probe.ok else "passed"
            if probe.ok:
                findings.append(f"expected_bad_case_not_caught: {case.name}")
            proofs.append(
                KnownBadProof(
                    _case_id(case.name),
                    protected_error_class=case_error,
                    method="expected_bad_workflow",
                    expected_failure="failed",
                    observed_status=observed_status,
                    observed_failure=_report_failure_text(probe) if not probe.ok else "bad workflow passed cleanly",
                    evidence_id=f"{suite_name}:{case.name}:probe",
                )
            )
        else:
            for label in _case_known_bad_labels(case, case_labels):
                seen = _report_has_label(probe, label)
                observed_status = "rejected" if seen else "not_run"
                if not seen:
                    findings.append(f"handled_known_bad_label_missing: {case.name}:{label}")
                proofs.append(
                    KnownBadProof(
                        _case_id(f"{case.name}_{label}"),
                        protected_error_class=case_error,
                        method="handled_bad_label",
                        expected_failure="rejected",
                        observed_status=observed_status,
                        observed_failure=f"label reached: {label}" if seen else f"label not reached: {label}",
                        evidence_id=f"{suite_name}:{case.name}:label:{label}",
                    )
                )

    unique: dict[str, KnownBadProof] = {}
    for proof in proofs:
        unique.setdefault(proof.case_id, proof)
    if not unique:
        findings.append("missing_known_bad_proof_source")
    return tuple(unique.values()), tuple(dict.fromkeys(findings))


def _build_plan(
    *,
    suite_name: str,
    case: FormalWorkflowCase,
    initial_states: tuple[Any, ...],
    external_inputs: tuple[Any, ...],
    invariants: tuple[Any, ...],
    max_sequence_length: int,
    terminal_predicate: Any,
    required_labels: tuple[str, ...],
    protected_error_class: str,
    modeled_boundary: str,
    risk_classes: Sequence[str],
    known_bad_proofs: tuple[KnownBadProof, ...],
) -> FlowGuardCheckPlan:
    case_inputs = _case_external_inputs(case, external_inputs)
    case_labels = _case_required_labels(case, required_labels)
    case_length = _case_max_sequence_length(case, max_sequence_length)
    case_terminal = _case_terminal_predicate(case, terminal_predicate)
    known_bad_cases = tuple(proof.case_id for proof in known_bad_proofs)
    case_error = case.protected_error_class or protected_error_class
    state_fields = _state_field_names(initial_states)
    side_effects = _workflow_write_names(case.workflow)
    invariant_names = _invariant_names(invariants)
    completion = case_labels or ("model_check_report",)
    risk_intent = RiskIntent(
        failure_modes=(
            f"{case.name} can claim model confidence without catching its protected bad case",
        ),
        protected_error_classes=(case_error,),
        protected_harms=(
            f"{suite_name} self-maintenance evidence would overclaim {modeled_boundary}",
        ),
        must_model_state=state_fields or ("abstract_state",),
        must_model_side_effects=side_effects or ("modeled_state_transition",),
        completion_evidence=completion,
        adversarial_inputs=_input_type_names(case_inputs),
        hard_invariants=invariant_names or ("model_check_status",),
        known_bad_cases=known_bad_cases,
        template_no_match_reason="repository self-model runner uses project-specific maintenance evidence",
        blindspots=("production conformance is validated by the surrounding test suite when required",),
    )
    return FlowGuardCheckPlan(
        workflow=case.workflow,
        initial_states=initial_states,
        external_inputs=case_inputs,
        invariants=invariants,
        max_sequence_length=case_length,
        terminal_predicate=case_terminal,
        required_labels=case_labels,
        risk_profile=RiskProfile(
            modeled_boundary=f"{modeled_boundary}:{case.name}",
            risk_classes=tuple(risk_classes),
            risk_intent=risk_intent,
        ),
        template_reuse_review=TemplateReuseReview(
            no_match_reason="repository self-model runner uses project-specific maintenance evidence",
            searched_layers=("public", "local"),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=(case_error,),
            modeled_state=state_fields or ("abstract_state",),
            modeled_side_effects=side_effects or ("modeled_state_transition",),
            completion_evidence=completion,
            known_bad_cases=known_bad_cases,
        ),
        known_bad_proofs=known_bad_proofs,
        metadata={"suite_name": suite_name, "case_name": case.name},
    )


def _run_probe(
    workflow: Any,
    *,
    initial_states: tuple[Any, ...],
    external_inputs: tuple[Any, ...],
    invariants: tuple[Any, ...],
    max_sequence_length: int,
    terminal_predicate: Any,
    required_labels: tuple[str, ...],
) -> Any:
    return Explorer(
        workflow=workflow,
        initial_states=initial_states,
        external_inputs=external_inputs,
        invariants=invariants,
        max_sequence_length=max_sequence_length,
        terminal_predicate=terminal_predicate,
        required_labels=required_labels,
        progress_steps=0,
    ).explore()


def _summary_observed_ok(summary: FlowGuardSummaryReport) -> bool:
    sections = {section.name: section for section in summary.sections}
    model_section = sections.get("model_check")
    if model_section is None or model_section.status != "pass":
        return False
    for section_name in ("minimum_model_review", "known_bad_proof", "template_harvest_review"):
        section = sections.get(section_name)
        if section is None or section.status in BLOCKING_STATUSES:
            return False
    return summary.overall_status not in BLOCKING_STATUSES


def _case_required_labels(case: FormalWorkflowCase, fallback: tuple[str, ...]) -> tuple[str, ...]:
    return case.required_labels or fallback


def _case_known_bad_labels(case: FormalWorkflowCase, required_labels: tuple[str, ...]) -> tuple[str, ...]:
    if case.known_bad_labels:
        return case.known_bad_labels
    return tuple(label for label in required_labels if _label_looks_caught(label))


def _case_external_inputs(case: FormalWorkflowCase, fallback: tuple[Any, ...]) -> tuple[Any, ...]:
    return case.external_inputs if case.external_inputs is not None else fallback


def _case_max_sequence_length(case: FormalWorkflowCase, fallback: int) -> int:
    return case.max_sequence_length if case.max_sequence_length is not None else fallback


def _case_terminal_predicate(case: FormalWorkflowCase, fallback: Any) -> Any:
    return case.terminal_predicate if case.terminal_predicate is not None else fallback


def _label_looks_caught(label: str) -> bool:
    lowered = label.lower()
    return any(hint in lowered for hint in CAUGHT_LABEL_HINTS)


def _report_has_label(report: Any, label: str) -> bool:
    return any(trace.has_label(label) for trace in getattr(report, "traces", ()) or ())


def _report_failure_text(report: Any) -> str:
    violations = tuple(getattr(report, "violations", ()) or ())
    if violations:
        first = violations[0]
        return str(getattr(first, "message", first))
    failures = tuple(getattr(report, "reachability_failures", ()) or ())
    if failures:
        first = failures[0]
        return str(getattr(first, "message", first))
    dead = tuple(getattr(report, "dead_branches", ()) or ())
    if dead:
        return f"dead_branch: {dead[0]!r}"
    exceptions = tuple(getattr(report, "exception_branches", ()) or ())
    if exceptions:
        first = exceptions[0]
        return str(getattr(first, "message", first))
    return str(getattr(report, "summary", "model check failed"))


def _state_field_names(initial_states: tuple[Any, ...]) -> tuple[str, ...]:
    if not initial_states:
        return ()
    state = initial_states[0]
    if is_dataclass(state):
        return tuple(field.name for field in fields(state))
    if hasattr(state, "_fields"):
        return tuple(str(name) for name in getattr(state, "_fields"))
    if isinstance(state, Mapping):
        return tuple(str(name) for name in state)
    return (type(state).__name__,)


def _workflow_write_names(workflow: Any) -> tuple[str, ...]:
    names: list[str] = []
    for block in tuple(getattr(workflow, "blocks", ()) or ()):
        writes = getattr(block, "writes", ()) or ()
        names.extend(str(write) for write in writes if str(write))
    return tuple(dict.fromkeys(names))


def _invariant_names(invariants: tuple[Any, ...]) -> tuple[str, ...]:
    names = []
    for invariant in invariants:
        name = getattr(invariant, "name", None) or getattr(invariant, "__name__", None)
        if name:
            names.append(str(name))
    return tuple(dict.fromkeys(names))


def _input_type_names(inputs: tuple[Any, ...]) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(type(item).__name__ for item in inputs))
    return names or ("external_input",)


def _case_id(value: str) -> str:
    clean = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_") or "known_bad_case"


__all__ = [
    "FormalWorkflowCase",
    "FormalWorkflowCaseResult",
    "FormalWorkflowSuiteReport",
    "run_formal_workflow_suite",
]
