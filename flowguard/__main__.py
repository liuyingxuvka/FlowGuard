"""Thin command wrappers for flowguard's existing Python APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from .adoption import ADOPTION_STATUSES
from .schema import SCHEMA_VERSION


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
        next_actions=tuple(args.next_action or ()),
    )
    append_jsonl(root / ".flowguard" / "adoption_log.jsonl", entry)
    append_markdown_log(root / "docs" / "flowguard_adoption_log.md", entry)
    print(entry.to_json_text())
    return 0


def _run_maintenance_template(args: argparse.Namespace) -> int:
    from .templates import maintenance_workflow_template_files, write_template_files

    files = maintenance_workflow_template_files()
    if args.output:
        written = write_template_files(args.output, files, overwrite=args.force)
        print(
            json.dumps(
                {
                    "artifact_type": "flowguard_template_write",
                    "template": "maintenance_workflow",
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
                "template": "maintenance_workflow",
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
    parser.add_argument("--next-action", action="append", default=[])
    parser.set_defaults(handler=_run_adoption_entry, default_status=default_status)


def _add_maintenance_template_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "maintenance-template",
        help="Print or write the optional multi-role maintenance workflow template.",
    )
    parser.add_argument(
        "--output",
        help="Project root where template files should be written. If omitted, prints JSON to stdout.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    parser.set_defaults(handler=_run_maintenance_template)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard",
        description="Run flowguard checks through thin Python API wrappers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_existing_command_subparsers(subparsers)
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-start", help="Append an in-progress adoption log entry."),
        default_status="in_progress",
    )
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-finish", help="Append a final adoption log entry."),
        default_status="auto",
    )
    _add_maintenance_template_parser(subparsers)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
