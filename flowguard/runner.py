"""Low-friction orchestration for model-first FlowGuard checks."""

from __future__ import annotations

from typing import Any

from .audit import audit_model
from .contract import check_trace_contracts
from .explorer import Explorer
from .minimize import minimize_report_counterexample
from .plan import FlowGuardCheckPlan, ScenarioMatrixConfig
from .progress import check_progress
from .review import review_scenarios
from .scenario import run_exact_sequence
from .scenario_matrix import ScenarioMatrixBuilder
from .summary_report import (
    FlowGuardSection,
    FlowGuardSummaryReport,
    section_from_audit_report,
    section_from_check_report,
    section_from_ok_report,
    section_from_scenario_report,
)


AUTO_SCENARIO_RISKS = frozenset(
    {
        "deduplication",
        "idempotency",
        "retry",
        "cache",
        "side_effect",
        "side_effects",
    }
)


def run_model_first_checks(plan: FlowGuardCheckPlan) -> FlowGuardSummaryReport:
    """Run a lightweight model-first helper workflow.

    This is an optional convenience layer. Direct `Explorer` usage remains the
    minimal and fully supported path.
    """

    sections: list[FlowGuardSection] = []
    artifacts: dict[str, Any] = {"plan": plan}

    risk_profile = plan.risk_profile
    risk_classes = risk_profile.risk_classes if risk_profile is not None else ()
    skipped_steps = tuple(
        f"{item.name}: {item.status}; {item.reason}"
        for item in risk_profile.skipped_checks
    ) if risk_profile is not None else ()

    audit_report = audit_model(
        workflow=plan.workflow,
        invariants=plan.invariants,
        external_inputs=plan.external_inputs,
        max_sequence_length=plan.max_sequence_length,
        scenarios=plan.scenarios,
        contracts=plan.contracts,
        progress_config=plan.progress_config,
        conformance_status=plan.conformance_status,
        declared_risk_classes=risk_classes,
        skipped_steps=skipped_steps,
        risk_profile=risk_profile,
    )
    artifacts["audit_report"] = audit_report
    sections.append(section_from_audit_report(audit_report))

    scenarios, generated_scenarios = _plan_or_generated_scenarios(plan)
    if generated_scenarios:
        sections.append(
            FlowGuardSection(
                name="scenario_matrix",
                status="pass_with_gaps",
                summary=(
                    f"auto-generated scenarios={len(generated_scenarios)}; "
                    "input-shape coverage only, not a business oracle"
                ),
                findings=(
                    "auto-generated scenarios exercise repeated/order input shapes; they default to "
                    "needs_human_review until domain expectations or oracles are supplied",
                ),
                metadata={"scenarios": generated_scenarios},
            )
        )
        artifacts["generated_scenarios"] = generated_scenarios

    model_report = None
    try:
        model_report = Explorer(
            workflow=plan.workflow,
            initial_states=plan.initial_states,
            external_inputs=plan.external_inputs,
            invariants=plan.invariants,
            max_sequence_length=plan.max_sequence_length,
        ).explore()
        sections.append(section_from_check_report(model_report))
        artifacts["model_check_report"] = model_report
    except Exception as exc:
        sections.append(
            FlowGuardSection(
                name="model_check",
                status="failed",
                summary="Explorer raised before producing a CheckReport",
                findings=(f"{type(exc).__name__}: {exc}",),
                metadata={"exception_type": type(exc).__name__, "exception_message": str(exc)},
            )
        )

    minimization = _minimize_first_invariant_violation(plan, model_report)
    if minimization is not None:
        artifacts["counterexample_minimization"] = minimization
        status = "pass" if minimization.status in {"reduced", "no_reduction_found"} else "pass_with_gaps"
        sections.append(
            FlowGuardSection(
                name="counterexample_minimization",
                status=status,
                summary=(
                    f"{minimization.status}: original_length={len(minimization.original_sequence)} "
                    f"minimized_length={len(minimization.minimized_sequence)}"
                ),
                findings=(
                    f"original_sequence={minimization.original_sequence!r}",
                    f"minimized_sequence={minimization.minimized_sequence!r}",
                ),
                metadata={"report": minimization},
            )
        )
    elif model_report is not None:
        sections.append(
            FlowGuardSection(
                name="counterexample_minimization",
                status="not_run",
                summary="no invariant violation counterexample to minimize",
                findings=("not_run because Explorer produced no invariant violation",),
            )
        )

    if scenarios:
        try:
            scenario_report = review_scenarios(scenarios)
            artifacts["scenario_report"] = scenario_report
            scenario_section = section_from_scenario_report(scenario_report)
            if generated_scenarios:
                scenario_section = FlowGuardSection(
                    name=scenario_section.name,
                    status=scenario_section.status,
                    summary=(
                        scenario_section.summary
                        + " auto_generated=true needs_domain_expectations=true"
                    ),
                    findings=scenario_section.findings,
                    metadata=scenario_section.metadata + (("auto_generated", True),),
                )
            sections.append(scenario_section)
        except Exception as exc:
            sections.append(
                FlowGuardSection(
                    name="scenario_review",
                    status="failed",
                    summary="scenario review raised",
                    findings=(f"{type(exc).__name__}: {exc}",),
                    metadata={"exception_type": type(exc).__name__, "exception_message": str(exc)},
                )
            )
    else:
        sections.append(
            FlowGuardSection(
                name="scenario_review",
                status="not_run",
                summary="no scenarios provided or generated",
                findings=("not_run is a scenario coverage gap, not a failure",),
            )
        )

    _append_progress_section(sections, artifacts, plan)
    _append_contract_section(sections, artifacts, plan, model_report)
    _append_conformance_section(sections, artifacts, plan)

    return FlowGuardSummaryReport.from_sections(
        sections,
        metadata=artifacts,
    )


def _plan_or_generated_scenarios(plan: FlowGuardCheckPlan) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    if plan.scenarios:
        return plan.scenarios, ()
    risk_profile = plan.risk_profile
    risks = set(risk_profile.risk_classes if risk_profile is not None else ())
    if not risks.intersection(AUTO_SCENARIO_RISKS):
        return (), ()

    config = plan.scenario_matrix_config or ScenarioMatrixConfig()
    if not config.enabled:
        return (), ()
    name_prefix = config.name_prefix or (
        risk_profile.modeled_boundary.replace(" ", "_").lower()
        if risk_profile is not None and risk_profile.modeled_boundary
        else "model_first"
    )
    max_sequence_length = config.max_sequence_length
    if max_sequence_length is None:
        max_sequence_length = max(3, plan.max_sequence_length)
    builder = ScenarioMatrixBuilder(
        name_prefix=name_prefix,
        initial_states=plan.initial_states,
        inputs=plan.external_inputs,
        workflow=plan.workflow,
        invariants=plan.invariants,
        max_sequence_length=max_sequence_length,
        max_scenarios=config.max_scenarios,
        tags=tuple(sorted(risks.intersection(AUTO_SCENARIO_RISKS))) + ("auto_generated",),
        notes=config.notes or "auto-generated by run_model_first_checks",
    )
    if config.include_single_inputs:
        builder.single_inputs()
    if config.include_repeat_same:
        builder.repeat_same(max_repeats=2)
    if config.include_pairwise_orders:
        builder.pairwise_orders()
    if config.include_aba:
        builder.aba()
    generated = builder.build()
    return generated, generated


def _minimize_first_invariant_violation(
    plan: FlowGuardCheckPlan,
    model_report: Any,
) -> Any:
    if model_report is None or not getattr(model_report, "violations", ()):
        return None
    violation = model_report.violations[0]
    failing_sequence = tuple(getattr(violation.trace, "external_inputs", ()) or ())
    if not failing_sequence:
        return None
    initial_state = getattr(violation.trace, "initial_state", None)
    violation_name = getattr(violation, "invariant_name", None)

    def run_sequence(sequence: tuple[Any, ...]) -> Any:
        return run_exact_sequence(
            workflow=plan.workflow,
            initial_state=initial_state,
            external_input_sequence=sequence,
            invariants=plan.invariants,
        ).model_report

    return minimize_report_counterexample(
        run_sequence,
        failing_sequence,
        violation_name=violation_name,
    )


def _append_progress_section(
    sections: list[FlowGuardSection],
    artifacts: dict[str, Any],
    plan: FlowGuardCheckPlan,
) -> None:
    if plan.progress_config is None:
        sections.append(
            FlowGuardSection(
                name="progress_check",
                status="not_run",
                summary="progress_config not provided",
                findings=("not_run is a progress confidence gap, not a failure",),
            )
        )
        return
    try:
        progress_report = check_progress(plan.progress_config)
        artifacts["progress_report"] = progress_report
        sections.append(section_from_ok_report(progress_report, name="progress_check"))
    except Exception as exc:
        sections.append(
            FlowGuardSection(
                name="progress_check",
                status="failed",
                summary="progress check raised",
                findings=(f"{type(exc).__name__}: {exc}",),
                metadata={"exception_type": type(exc).__name__, "exception_message": str(exc)},
            )
        )


def _append_contract_section(
    sections: list[FlowGuardSection],
    artifacts: dict[str, Any],
    plan: FlowGuardCheckPlan,
    model_report: Any,
) -> None:
    if not plan.contracts:
        sections.append(
            FlowGuardSection(
                name="contract_check",
                status="not_run",
                summary="contracts not provided",
                findings=("not_run is a contract coverage gap, not a failure",),
            )
        )
        return
    traces = tuple(getattr(model_report, "traces", ()) or ())
    if not traces:
        sections.append(
            FlowGuardSection(
                name="contract_check",
                status="blocked",
                summary="contracts provided but no model traces were available",
                findings=("run model exploration successfully before checking trace contracts",),
            )
        )
        return

    reports = tuple(check_trace_contracts(trace, plan.contracts) for trace in traces)
    artifacts["contract_reports"] = reports
    failed = tuple(report for report in reports if not report.ok)
    findings = tuple(
        f"trace_report_{index}: {violation.name}: {violation.message}"
        for index, report in enumerate(reports, start=1)
        for violation in report.violations
    )
    sections.append(
        FlowGuardSection(
            name="contract_check",
            status="failed" if failed else "pass",
            summary=f"checked_traces={len(reports)} failed_reports={len(failed)}",
            findings=findings,
            metadata={"reports": reports},
        )
    )


def _append_conformance_section(
    sections: list[FlowGuardSection],
    artifacts: dict[str, Any],
    plan: FlowGuardCheckPlan,
) -> None:
    if plan.conformance_report is not None:
        artifacts["conformance_report"] = plan.conformance_report
        sections.append(section_from_ok_report(plan.conformance_report, name="conformance_replay"))
        return

    status = _normalize_conformance_status(plan.conformance_status)
    if status == "not_run":
        sections.append(
            FlowGuardSection(
                name="conformance_replay",
                status="not_run",
                summary="conformance_status not provided",
                findings=("not_run is a production confidence gap, not a failure",),
            )
        )
        return

    sections.append(
        FlowGuardSection(
            name="conformance_replay",
            status=status,
            summary=f"conformance_status={plan.conformance_status}",
            findings=("conformance status was recorded without a replay report",),
        )
    )


def _normalize_conformance_status(status: str | None) -> str:
    value = str(status or "not_run").strip().lower()
    if value in {"ok", "pass", "passed", "completed", "complete"}:
        return "pass"
    if value in {"failed", "failure", "violation"}:
        return "failed"
    if value in {"blocked"}:
        return "blocked"
    if value in {"skipped", "skipped_with_reason", "not_feasible"}:
        return "skipped_with_reason"
    if value in {"not_run", "none", ""}:
        return "not_run"
    return "pass_with_gaps"


__all__ = ["AUTO_SCENARIO_RISKS", "run_model_first_checks"]
