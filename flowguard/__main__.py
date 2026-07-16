"""Thin command wrappers for flowguard's existing Python APIs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .adoption import ADOPTION_STATUSES
from .schema import SCHEMA_VERSION


def _parse_json_mapping_arg(value: str, option_name: str) -> dict[str, object]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{option_name} must be a JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{option_name} must be a JSON object.")
    return payload


def _run_benchmark() -> int:
    from examples.problem_corpus.executable import review_executable_corpus

    report = review_executable_corpus()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_coverage() -> int:
    from examples.problem_corpus.coverage_audit import review_benchmark_coverage

    report = review_benchmark_coverage()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_hardening() -> int:
    from examples.problem_corpus.hardening import review_benchmark_hardening

    report = review_benchmark_hardening()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_loop_review() -> int:
    from examples.looping_workflow.model import run_loop_review

    report = run_loop_review()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_scenario_review() -> int:
    from flowguard.review import review_scenarios
    from examples.job_matching.scenarios import all_job_matching_scenarios

    report = review_scenarios(all_job_matching_scenarios())
    print(report.format_text(max_counterexamples=1))
    return 0 if report.ok else 1


def _run_conformance() -> int:
    from examples.problem_corpus.conformance_seeds import review_conformance_seeds

    report = review_conformance_seeds()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_self_review() -> int:
    from examples.flowguard_self_review.model import run_self_review

    report = run_self_review()
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


def _run_self_conformance() -> int:
    from examples.flowguard_self_review.conformance import (
        generate_self_review_representative_traces,
        replay_self_review_trace,
    )
    from examples.flowguard_self_review.orchestrator import (
        BrokenNoConformanceOrchestrator,
        BrokenToolchainSubstituteOrchestrator,
        CorrectFlowguardOrchestrator,
    )

    traces = generate_self_review_representative_traces()
    conformance_trace = next(
        trace
        for trace in traces
        if trace.has_label("checks_passed") and "flowguard-conformance" in repr(trace.external_inputs)
    )
    toolchain_trace = next(trace for trace in traces if trace.has_label("toolchain_missing"))
    correct_reports = [replay_self_review_trace(trace, CorrectFlowguardOrchestrator()) for trace in traces]
    broken_reports = [
        replay_self_review_trace(conformance_trace, BrokenNoConformanceOrchestrator()),
        replay_self_review_trace(toolchain_trace, BrokenToolchainSubstituteOrchestrator()),
    ]
    print("=== flowguard self-review conformance ===")
    print(f"representative_traces: {len(traces)}")
    print(f"correct_status: {'OK' if all(report.ok for report in correct_reports) else 'VIOLATION'}")
    for report in broken_reports:
        print()
        print(report.format_text(max_examples=1))
    return 0 if all(report.ok for report in correct_reports) and all(not report.ok for report in broken_reports) else 1


def _run_schema_version() -> int:
    print(SCHEMA_VERSION)
    return 0


def _run_adoption_template() -> int:
    from .templates import ADOPTION_LOG_TEMPLATE

    print(ADOPTION_LOG_TEMPLATE)
    return 0


def _run_file_template(
    args: argparse.Namespace,
    *,
    template_name: str,
    files: tuple[object, ...],
) -> int:
    from .templates import write_template_files

    if args.output:
        written = write_template_files(args.output, files, overwrite=args.force)
        print(
            json.dumps(
                {
                    "artifact_type": "flowguard_template_write",
                    "template": template_name,
                    "files": [str(path) for path in written],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "artifact_type": "flowguard_template",
                "template": template_name,
                "files": [
                    {"path": file.path, "content": file.content}
                    for file in files
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


@dataclass(frozen=True)
class FileTemplateCommand:
    name: str
    help_text: str
    template_name: str
    factory_name: str


FILE_TEMPLATE_COMMANDS: tuple[FileTemplateCommand, ...] = (
    FileTemplateCommand(
        "project-template",
        "Print or write the basic FlowGuard project model template.",
        "project",
        "project_template_files",
    ),
    FileTemplateCommand(
        "project-adoption-template",
        "Print or write the FlowGuard target-project AGENTS/manifest adoption template.",
        "project_adoption",
        "project_adoption_template_files",
    ),
    FileTemplateCommand(
        "spec-work-package-template",
        "Print or write a provider work-package binding and receipt-orchestration example.",
        "spec_work_package",
        "spec_work_package_template_files",
    ),
    FileTemplateCommand(
        "risk-intent-template",
        "Print or write the Risk Intent + CheckPlan template.",
        "risk_intent_check_plan",
        "risk_intent_template_files",
    ),
    FileTemplateCommand(
        "risk-template-library-template",
        "Print or write the public/local risk template library scaffold.",
        "risk_template_library",
        "risk_template_library_template_files",
    ),
    FileTemplateCommand(
        "plan-detailing-template",
        "Print or write the rough-plan to detailed FlowGuard plan template.",
        "plan_detailing",
        "plan_detailing_template_files",
    ),
    FileTemplateCommand(
        "primary-path-authority-template",
        "Print or write the Primary Path Authority no-fallback route template.",
        "primary_path_authority",
        "primary_path_authority_template_files",
    ),
    FileTemplateCommand(
        "behavior-commitment-ledger-template",
        "Print or write the Behavior Commitment Ledger full behavior inventory template.",
        "behavior_commitment_ledger",
        "behavior_commitment_ledger_template_files",
    ),
    FileTemplateCommand(
        "model-miss-template",
        "Print or write the bug-repair/model-miss review template.",
        "model_miss_review",
        "model_miss_review_template_files",
    ),
    FileTemplateCommand(
        "model-miss-full-template",
        "Print or write the full bug-repair/model-miss review template.",
        "model_miss_review_full",
        "model_miss_review_full_template_files",
    ),
    FileTemplateCommand(
        "model-test-alignment-template",
        "Print or write the model/test/code contract, code-boundary, and source-audit alignment template.",
        "model_test_alignment",
        "model_test_alignment_template_files",
    ),
    FileTemplateCommand(
        "model-test-alignment-full-template",
        "Print or write the full model/test/code contract, code-boundary, and source-audit alignment template.",
        "model_test_alignment_full",
        "model_test_alignment_full_template_files",
    ),
    FileTemplateCommand(
        "runtime-path-evidence-template",
        "Print or write the runtime path evidence model/code node alignment template.",
        "runtime_path_evidence",
        "runtime_path_evidence_template_files",
    ),
    FileTemplateCommand(
        "code-structure-recommendation-template",
        "Print or write the code structure recommendation template.",
        "code_structure_recommendation",
        "code_structure_recommendation_template_files",
    ),
    FileTemplateCommand(
        "ui-flow-structure-template",
        "Print or write the UI interaction flow and structure derivation template.",
        "ui_flow_structure",
        "ui_flow_structure_template_files",
    ),
    FileTemplateCommand(
        "ui-flow-structure-full-template",
        "Print or write the full UI interaction flow and structure derivation template.",
        "ui_flow_structure_full",
        "ui_flow_structure_full_template_files",
    ),
    FileTemplateCommand(
        "development-process-flow-template",
        "Print or write the DevelopmentProcessFlow lifecycle freshness template.",
        "development_process_flow",
        "development_process_flow_template_files",
    ),
    FileTemplateCommand(
        "workflow-step-contracts-template",
        "Print or write the workflow step contracts receipt-gate template.",
        "workflow_step_contracts",
        "workflow_step_contracts_template_files",
    ),
    FileTemplateCommand(
        "existing-model-preflight-template",
        "Print or write the existing FlowGuard model preflight template.",
        "existing_model_preflight",
        "existing_model_preflight_template_files",
    ),
    FileTemplateCommand(
        "model-angle-template",
        "Print or write the open-ended model-angle deliberation template.",
        "model_angle_deliberation",
        "model_angle_deliberation_template_files",
    ),
    FileTemplateCommand(
        "field-lifecycle-template",
        "Print or write the FieldLifecycleMesh field coverage and replacement disposition template.",
        "field_lifecycle",
        "field_lifecycle_template_files",
    ),
    FileTemplateCommand(
        "model-similarity-template",
        "Print or write the model similarity consolidation template.",
        "model_similarity_consolidation",
        "model_similarity_consolidation_template_files",
    ),
    FileTemplateCommand(
        "risk-evidence-ledger-template",
        "Print or write the risk evidence ledger final confidence template.",
        "risk_evidence_ledger",
        "risk_evidence_ledger_template_files",
    ),
    FileTemplateCommand(
        "layered-boundary-proof-template",
        "Print or write the layered parent/child/leaf boundary proof template.",
        "layered_boundary_proof",
        "layered_boundary_proof_template_files",
    ),
    FileTemplateCommand(
        "closure-contract-template",
        "Print or write the FlowGuard closure contract final confidence template.",
        "closure_contract",
        "closure_contract_template_files",
    ),
    FileTemplateCommand(
        "test-mesh-template",
        "Print or write the TestMesh validation hierarchy template.",
        "test_mesh",
        "test_mesh_template_files",
    ),
    FileTemplateCommand(
        "structure-mesh-template",
        "Print or write the StructureMesh refactor hierarchy template.",
        "structure_mesh",
        "structure_mesh_template_files",
    ),
    FileTemplateCommand(
        "maintenance-template",
        "Print or write the optional multi-role maintenance workflow template.",
        "maintenance_workflow",
        "maintenance_workflow_template_files",
    ),
    FileTemplateCommand(
        "maintenance-scan-template",
        "Print or write the FlowGuard maintenance scan router template.",
        "maintenance_scan",
        "maintenance_scan_template_files",
    ),
    FileTemplateCommand(
        "topology-hazard-template",
        "Print or write the model-topology hazard review template.",
        "model_topology_hazard_review",
        "topology_hazard_template_files",
    ),
)


def _run_file_template_command(args: argparse.Namespace, command: FileTemplateCommand) -> int:
    from . import templates

    factory = getattr(templates, command.factory_name)
    return _run_file_template(args, template_name=command.template_name, files=factory())


def _run_adoption_entry(args: argparse.Namespace) -> int:
    from .adoption import (
        AdoptionCommandResult,
        append_jsonl,
        append_markdown_log,
        make_adoption_log_entry,
    )

    failed_commands = tuple(args.failed_command or ())
    successful_commands = tuple(args.command or ())
    commands = tuple(
        AdoptionCommandResult(command, True)
        for command in successful_commands
    ) + tuple(
        AdoptionCommandResult(command, False)
        for command in failed_commands
    )
    root = Path(args.root)
    status = args.status
    if status == "auto" and args.default_status != "auto":
        status = args.default_status
    entry = make_adoption_log_entry(
        task_id=args.task_id,
        project=args.project or root.resolve().name,
        task_summary=args.task_summary,
        trigger_reason=args.trigger_reason,
        status=status,
        skill_decision=args.skill_decision,
        duration_seconds=args.duration_seconds,
        model_files=tuple(args.model_file or ()),
        commands=commands,
        findings=tuple(args.finding or ()),
        counterexamples=tuple(args.counterexample or ()),
        friction_points=tuple(args.friction_point or ()),
        skipped_steps=tuple(args.skipped_step or ()),
        risk_evidence_summary=tuple(args.risk_evidence or ()),
        next_actions=tuple(args.next_action or ()),
    )
    append_jsonl(root / ".flowguard" / "adoption_log.jsonl", entry)
    append_markdown_log(root / "docs" / "flowguard_adoption_log.md", entry)
    print(entry.to_json_text())
    return 0


def _run_project_adoption_command(args: argparse.Namespace) -> int:
    from .project_adoption import adopt_project, audit_project_adoption, upgrade_project

    if args.project_action == "audit":
        report = audit_project_adoption(args.root)
    elif args.project_action == "adopt":
        report = adopt_project(args.root)
    elif args.project_action == "upgrade":
        report = upgrade_project(
            args.root,
            records_only=args.records_only,
            dry_run=args.dry_run,
        )
    else:  # pragma: no cover
        raise ValueError(f"unknown project adoption action: {args.project_action}")
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_artifact_upgrade_command(args: argparse.Namespace) -> int:
    from .artifact_upgrade import review_artifact_upgrades

    report = review_artifact_upgrades(args.root, apply=args.apply, paths=tuple(args.path or ()))
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_behavior_commitment_query_command(args: argparse.Namespace) -> int:
    from .behavior_commitment_lookup import (
        BehaviorLookupQuery,
        query_behavior_commitments_from_path,
    )

    root = Path(args.root).resolve()
    ledger_path = Path(args.ledger)
    if not ledger_path.is_absolute():
        ledger_path = root / ledger_path
    query = BehaviorLookupQuery(
        task_summary=args.task_summary or "",
        primary_plane=args.plane or "",
        canonical_terms=tuple(args.term or ()),
        changed_paths=tuple(args.path or ()),
        tool_ids=tuple(args.tool_id or ()),
        error_signatures=tuple(args.error_signature or ()),
        workflow_families=tuple(args.workflow_family or ()),
        top_k=args.top_k,
    )
    report = query_behavior_commitments_from_path(ledger_path, query)
    if args.json:
        payload = report.to_dict()
        payload["query"] = query.to_dict()
        payload["ledger_path"] = str(ledger_path)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_search_command(args: argparse.Namespace) -> int:
    from .risk_templates import search_risk_templates

    report = search_risk_templates(
        args.query or "",
        workflow_families=tuple(args.workflow_family or ()),
        protected_error_classes=tuple(args.protected_error_class or ()),
        include_public=not args.no_public,
        include_local=not args.no_local,
        local_root=args.local_root,
        max_results=args.max_results,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_harvest_command(args: argparse.Namespace) -> int:
    from .risk_templates import harvest_risk_template_candidate

    report = harvest_risk_template_candidate(
        template_id=args.template_id,
        title=args.title,
        summary=args.summary,
        workflow_families=tuple(args.workflow_family or ()),
        protected_error_classes=tuple(args.protected_error_class or ()),
        required_state=tuple(args.required_state or ()),
        required_side_effects=tuple(args.required_side_effect or ()),
        required_evidence=tuple(args.required_evidence or ()),
        known_bad_cases=tuple(args.known_bad_case or ()),
        known_bad_proofs=tuple(_parse_json_mapping_arg(value, "--known-bad-proof") for value in (args.known_bad_proof or ())),
        merge_keys=tuple(args.merge_key or ()),
        local_root=args.local_root,
        write=not args.no_write,
        overwrite=args.force,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_harvest_review_command(args: argparse.Namespace) -> int:
    from .risk_templates import TemplateHarvestReview, review_template_harvest_closure

    review = TemplateHarvestReview(
        disposition=args.disposition,
        written_template_ids=tuple(args.written_template_id or ()),
        merged_template_ids=tuple(args.merged_template_id or ()),
        linked_template_ids=tuple(args.linked_template_id or ()),
        not_harvestable_reason=args.not_harvestable_reason,
        local_root=args.local_root or "",
        findings=tuple(args.finding or ()),
    )
    report = review_template_harvest_closure(review)
    payload = {
        "review": review.to_dict(),
        "report": report.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else "\n".join((review.format_text(), report.format_text())))
    return 0 if report.ok else 1


def _run_spec_work_package_audit_command(args: argparse.Namespace) -> int:
    from .spec_providers import discover_spec_work_packages
    from .spec_work_package import review_spec_work_package

    packages = discover_spec_work_packages(
        args.root,
        provider_id=args.provider,
        change_id=args.change,
        bindings_path=args.bindings or None,
    )
    reports = tuple(review_spec_work_package(package) for package in packages)
    payload = {
        "artifact_type": "flowguard_spec_work_package_audit",
        "provider": args.provider,
        "change": args.change,
        "package_count": len(packages),
        "ok": bool(reports) and all(report.ok for report in reports),
        "packages": [package.to_dict() for package in packages],
        "reports": [report.to_dict() for report in reports],
        "claim_boundary": (
            "Development-process reconciliation only; provider-native task, verification, and archive authority is preserved."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def _run_spec_session_begin_command(args: argparse.Namespace) -> int:
    from .spec_check_cache import begin_spec_session

    result = begin_spec_session(args.root, args.provider, args.work_package)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


def _run_spec_session_close_command(args: argparse.Namespace) -> int:
    from .spec_check_cache import close_spec_session

    result = close_spec_session(args.root, args.provider, args.work_package)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


def _run_spec_check_command(args: argparse.Namespace) -> int:
    from .spec_check_cache import run_spec_check
    from .spec_providers import load_openspec_work_package, load_speckit_work_package

    package = (
        load_openspec_work_package(args.root, args.work_package)
        if args.provider == "openspec"
        else load_speckit_work_package(args.root, args.work_package)
    )
    declared = next((item for item in package.checks if item.check_id == args.check_id), None)
    validation_ids = tuple(args.validation_obligation or ()) or (
        declared.validation_obligation_ids if declared is not None else ()
    )
    dependencies = tuple(args.depends_on or ()) or (declared.depends_on if declared is not None else ())
    timeout_seconds = args.timeout_seconds or (declared.timeout_seconds if declared is not None else 1800)
    expected_exit_code = (
        args.expected_exit_code
        if args.expected_exit_code is not None
        else declared.expected_exit_code
        if declared is not None
        else 0
    )
    cross_change_safe = bool(args.cross_change_safe or (declared.cross_change_safe if declared else False))
    command = tuple(args.inner_command or ())
    if command and command[0] == "--":
        command = command[1:]
    result = run_spec_check(
        args.root,
        provider_id=args.provider,
        work_package_id=args.work_package,
        check_id=args.check_id,
        semantic_id=args.semantic_id,
        command=command,
        validation_obligation_ids=validation_ids,
        coverage=tuple(args.coverage or ()),
        depends_on=dependencies,
        timeout_seconds=timeout_seconds,
        expected_exit_code=expected_exit_code,
        cross_change_safe=cross_change_safe,
        working_directory=args.cwd,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


def _portable_invalid_report(path: str, exc: Exception):
    from .portable_checker import PortableCheckReport, PortableFinding

    return PortableCheckReport(
        status="invalid",
        model_id=path,
        model_fingerprint="",
        findings=(PortableFinding("portable_artifact_invalid", str(exc)),),
    )


def _print_portable_report(report, *, as_json: bool) -> int:
    print(report.to_json_text() if as_json else report.format_text())
    return 0 if report.ok else 1


def _run_portable_model_validate_command(args: argparse.Namespace) -> int:
    from .portable_checker import PortableCheckReport
    from .portable_model import load_portable_model

    try:
        model = load_portable_model(args.model)
        report = PortableCheckReport(
            status="pass",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            checked_obligation_ids=("portable_model.structure.current",),
            claim_boundary="Validation proves the current portable artifact shape and identity only.",
        )
    except Exception as exc:
        report = _portable_invalid_report(args.model, exc)
    return _print_portable_report(report, as_json=args.json)


def _run_portable_model_check_command(args: argparse.Namespace) -> int:
    from .portable_checker import check_portable_model
    from .portable_model import load_portable_model

    try:
        report = check_portable_model(load_portable_model(args.model), max_states=args.max_states)
    except Exception as exc:
        report = _portable_invalid_report(args.model, exc)
    return _print_portable_report(report, as_json=args.json)


def _run_portable_model_refinement_command(args: argparse.Namespace) -> int:
    from .portable_checker import check_refinement
    from .portable_model import load_portable_model, load_refinement_binding

    try:
        report = check_refinement(
            load_portable_model(args.parent),
            load_portable_model(args.child),
            load_refinement_binding(args.binding),
        )
    except Exception as exc:
        report = _portable_invalid_report(args.child, exc)
    return _print_portable_report(report, as_json=args.json)


COMMANDS: dict[str, Callable[[], int]] = {
    "adoption-template": _run_adoption_template,
    "benchmark": _run_benchmark,
    "coverage": _run_coverage,
    "hardening": _run_hardening,
    "loop-review": _run_loop_review,
    "scenario-review": _run_scenario_review,
    "conformance": _run_conformance,
    "self-review": _run_self_review,
    "self-conformance": _run_self_conformance,
    "schema-version": _run_schema_version,
}


def _add_existing_command_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for command_name in sorted(COMMANDS):
        command_parser = subparsers.add_parser(command_name)
        command_parser.set_defaults(handler=lambda _args, name=command_name: COMMANDS[name]())


def _add_adoption_entry_args(
    parser: argparse.ArgumentParser,
    *,
    default_status: str,
) -> None:
    parser.add_argument("--root", default=".", help="Project root where adoption logs are written.")
    parser.add_argument("--task-id", required=True, help="Stable id for this model-first adoption task.")
    parser.add_argument("--project", default="", help="Project name. Defaults to the root directory name.")
    parser.add_argument("--task-summary", required=True, help="Short description of the task.")
    parser.add_argument("--trigger-reason", required=True, help="Why FlowGuard was used or skipped.")
    parser.add_argument(
        "--status",
        default="auto",
        choices=("auto",) + ADOPTION_STATUSES,
        help=f"Adoption status. Defaults to {default_status!r}.",
    )
    parser.add_argument("--skill-decision", default="used_flowguard")
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--model-file", action="append", default=[])
    parser.add_argument("--command", action="append", default=[], help="Successful command/check to record.")
    parser.add_argument("--failed-command", action="append", default=[], help="Failed command/check to record.")
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--counterexample", action="append", default=[])
    parser.add_argument("--friction-point", action="append", default=[])
    parser.add_argument("--skipped-step", action="append", default=[])
    parser.add_argument(
        "--risk-evidence",
        action="append",
        default=[],
        help="Final risk evidence ledger note, scoped boundary, or proof gap.",
    )
    parser.add_argument("--next-action", action="append", default=[])
    parser.set_defaults(handler=_run_adoption_entry, default_status=default_status)


def _add_file_template_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command: FileTemplateCommand,
) -> None:
    parser = subparsers.add_parser(command.name, help=command.help_text)
    parser.add_argument(
        "--output",
        help="Project root where template files should be written. If omitted, prints JSON to stdout.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    parser.set_defaults(
        handler=lambda args, template_command=command: _run_file_template_command(args, template_command)
    )


def _add_project_adoption_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command_name: str,
    *,
    action: str,
    help_text: str,
) -> None:
    parser = subparsers.add_parser(command_name, help=help_text)
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    if action == "upgrade":
        parser.add_argument(
            "--records-only",
            action="store_true",
            help="Only update AGENTS/manifest/adoption records; skip artifact/model/test upgrade scanning.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview files, semantic rule changes, suite findings, and revalidation without writing.",
        )
    else:
        parser.set_defaults(records_only=False, dry_run=False)
    parser.set_defaults(handler=_run_project_adoption_command, project_action=action)


def _add_artifact_upgrade_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "artifact-upgrade",
        help="Scan or apply deterministic upgrades for older FlowGuard artifacts.",
    )
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Specific file or directory to scan. May be passed more than once.",
    )
    parser.add_argument("--apply", action="store_true", help="Write deterministic upgrades.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_artifact_upgrade_command)


def _add_behavior_commitment_query_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    from .behavior_commitment import BCL_BEHAVIOR_PLANES

    parser = subparsers.add_parser(
        "behavior-commitment-query",
        help="Read-only plane-first lookup in a project's canonical behavior ledger.",
    )
    parser.add_argument("task_summary", nargs="?", default="", help="Short task or operation description.")
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument(
        "--ledger",
        default=".flowguard/behavior_commitment_ledger/ledger.json",
        help="Canonical ledger path, relative to --root unless absolute.",
    )
    parser.add_argument("--plane", choices=BCL_BEHAVIOR_PLANES, default="")
    parser.add_argument("--term", action="append", default=[], help="Canonical task or commitment term.")
    parser.add_argument("--path", action="append", default=[], help="Changed or operated path clue.")
    parser.add_argument("--tool-id", action="append", default=[], help="Tool identifier clue.")
    parser.add_argument("--error-signature", action="append", default=[], help="Observed error signature clue.")
    parser.add_argument("--workflow-family", action="append", default=[], help="Workflow-family clue.")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum hits per result group (1-50).")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.set_defaults(handler=_run_behavior_commitment_query_command)


def _add_risk_template_search_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-search",
        help="Search packaged public and per-machine local risk templates.",
    )
    parser.add_argument("query", nargs="?", default="", help="Search query for the modeled risk.")
    parser.add_argument("--workflow-family", action="append", default=[], help="Workflow family hint.")
    parser.add_argument("--protected-error-class", action="append", default=[], help="Protected error class hint.")
    parser.add_argument("--local-root", default=None, help="Override local template library root.")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--no-public", action="store_true", help="Do not search packaged public templates.")
    parser.add_argument("--no-local", action="store_true", help="Do not search per-machine local templates.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_search_command)


def _add_risk_template_harvest_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-harvest",
        help="Write a reusable local risk template candidate.",
    )
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--workflow-family", action="append", default=[])
    parser.add_argument("--protected-error-class", action="append", default=[])
    parser.add_argument("--required-state", action="append", default=[])
    parser.add_argument("--required-side-effect", action="append", default=[])
    parser.add_argument("--required-evidence", action="append", default=[])
    parser.add_argument("--known-bad-case", action="append", default=[])
    parser.add_argument(
        "--known-bad-proof",
        action="append",
        default=[],
        help="JSON object for one KnownBadProof, including case_id and observed_status.",
    )
    parser.add_argument("--merge-key", action="append", default=[])
    parser.add_argument("--local-root", default=None, help="Override local template library root.")
    parser.add_argument("--no-write", action="store_true", help="Validate the candidate without writing it.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing local template file.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_harvest_command)


def _add_risk_template_harvest_review_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-harvest-review",
        help="Review required template harvest closure after model creation or deepening.",
    )
    parser.add_argument(
        "--disposition",
        required=True,
        choices=("written", "merged", "duplicate_linked", "not_harvestable"),
    )
    parser.add_argument("--written-template-id", action="append", default=[])
    parser.add_argument("--merged-template-id", action="append", default=[])
    parser.add_argument("--linked-template-id", action="append", default=[])
    parser.add_argument("--not-harvestable-reason", default="")
    parser.add_argument("--local-root", default="")
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_harvest_review_command)


def _add_spec_work_package_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    audit = subparsers.add_parser(
        "spec-work-package-audit",
        help="Read-only provider task/obligation/check reconciliation under one project root.",
    )
    audit.add_argument("--root", default=".")
    audit.add_argument("--provider", choices=("auto", "openspec", "speckit"), default="auto")
    audit.add_argument("--change", default="")
    audit.add_argument("--bindings", default="")
    audit.add_argument("--json", action="store_true", help="Canonical JSON is always emitted.")
    audit.set_defaults(handler=_run_spec_work_package_audit_command)

    for command_name, help_text, handler in (
        ("spec-session-begin", "Capture the immutable begin snapshot for one provider work package.", _run_spec_session_begin_command),
        ("spec-session-close", "Capture the post snapshot and reject stale or incomplete closure.", _run_spec_session_close_command),
    ):
        parser = subparsers.add_parser(command_name, help=help_text)
        parser.add_argument("--root", default=".")
        parser.add_argument("--provider", choices=("openspec", "speckit"), required=True)
        parser.add_argument("--work-package", required=True)
        parser.add_argument("--json", action="store_true", help="Canonical JSON is always emitted.")
        parser.set_defaults(handler=handler)

    run = subparsers.add_parser(
        "spec-check-run",
        help="Run or safely reuse one exact check inside an active provider session.",
    )
    run.add_argument("--root", default=".")
    run.add_argument("--provider", choices=("openspec", "speckit"), required=True)
    run.add_argument("--work-package", required=True)
    run.add_argument("--check-id", required=True)
    run.add_argument("--semantic-id", required=True)
    run.add_argument("--validation-obligation", action="append", default=[])
    run.add_argument("--coverage", action="append", default=[])
    run.add_argument("--depends-on", action="append", default=[])
    run.add_argument("--timeout-seconds", type=int, default=0)
    run.add_argument("--expected-exit-code", type=int, default=None)
    run.add_argument("--cross-change-safe", action="store_true")
    run.add_argument("--cwd", default=".")
    run.add_argument("--json", action="store_true", help="Canonical JSON is always emitted.")
    run.add_argument("inner_command", nargs=argparse.REMAINDER)
    run.set_defaults(handler=_run_spec_check_command)


def _add_portable_model_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    validate = subparsers.add_parser(
        "portable-model-validate",
        help="Validate one current-schema portable finite model artifact.",
    )
    validate.add_argument("model", help="Portable model JSON path.")
    validate.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    validate.set_defaults(handler=_run_portable_model_validate_command)

    check = subparsers.add_parser(
        "portable-model-check",
        help="Run safety and temporal checks over one portable model.",
    )
    check.add_argument("model", help="Portable model JSON path.")
    check.add_argument("--max-states", type=int, default=10000)
    check.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    check.set_defaults(handler=_run_portable_model_check_command)

    refinement = subparsers.add_parser(
        "portable-model-refinement",
        help="Check an explicit child-to-parent portable refinement binding.",
    )
    refinement.add_argument("--parent", required=True, help="Parent portable model JSON path.")
    refinement.add_argument("--child", required=True, help="Child portable model JSON path.")
    refinement.add_argument("--binding", required=True, help="Refinement binding JSON path.")
    refinement.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    refinement.set_defaults(handler=_run_portable_model_refinement_command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard",
        description="Run flowguard checks through thin Python API wrappers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_existing_command_subparsers(subparsers)
    for command in FILE_TEMPLATE_COMMANDS:
        _add_file_template_parser(subparsers, command)
    _add_artifact_upgrade_parser(subparsers)
    _add_behavior_commitment_query_parser(subparsers)
    _add_risk_template_search_parser(subparsers)
    _add_risk_template_harvest_parser(subparsers)
    _add_risk_template_harvest_review_parser(subparsers)
    _add_spec_work_package_parsers(subparsers)
    _add_portable_model_parsers(subparsers)
    _add_project_adoption_parser(
        subparsers,
        "project-audit",
        action="audit",
        help_text="Read-only audit of target-project FlowGuard AGENTS/manifest adoption state.",
    )
    _add_project_adoption_parser(
        subparsers,
        "project-adopt",
        action="adopt",
        help_text="Write or refresh target-project FlowGuard AGENTS/manifest adoption records.",
    )
    _add_project_adoption_parser(
        subparsers,
        "project-upgrade",
        action="upgrade",
        help_text="Explicitly update target-project FlowGuard records to the installed package version.",
    )
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-start", help="Append an in-progress adoption log entry."),
        default_status="in_progress",
    )
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-finish", help="Append a final adoption log entry."),
        default_status="auto",
    )
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
