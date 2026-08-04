"""Thin command wrappers for flowguard's existing Python APIs."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import threading
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


def _read_json_object(path: str | Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON artifact must be an object: {path}")
    return payload


def _emit_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _run_model_system_command(args: argparse.Namespace) -> int:
    from .model_authority import (
        ModelRevisionSet,
        ModelRollbackContract,
        load_model_system_snapshot,
    )
    from .model_authority_store import (
        activate_model_revision_set,
        audit_model_authority,
        bootstrap_model_authority,
        rollback_observed_model_system,
    )
    from .model_system_inventory import (
        build_manifest_model_system_snapshot,
    )

    try:
        if args.model_system_action == "audit":
            report = audit_model_authority(args.root)
            _emit_payload(report.to_dict(), as_json=args.json)
            return 0 if report.ok else 1
        if args.model_system_action == "bootstrap":
            snapshot = (
                load_model_system_snapshot(args.snapshot)
                if args.snapshot
                else build_manifest_model_system_snapshot(
                    args.root,
                    snapshot_id=args.snapshot_id,
                )
            )
            head = bootstrap_model_authority(
                args.root,
                snapshot,
                bootstrap_evidence_fingerprint=args.evidence_fingerprint,
            )
            _emit_payload(
                {
                    "status": "pass",
                    "head": head.to_dict(),
                    "snapshot": snapshot.to_dict(),
                },
                as_json=args.json,
            )
            return 0
        if args.model_system_action == "build":
            from .model_intent import (
                ModelIntentContribution,
                ModelIntentDisposition,
            )
            from .model_revision_builder import (
                build_current_model_revision,
                load_revision_removal_dispositions,
            )

            dispositions = (
                load_revision_removal_dispositions(args.removal_dispositions)
                if args.removal_dispositions
                else ()
            )
            intent_contributions = ()
            intent_dispositions = ()
            if args.intent_inventory:
                intent_payload = _read_json_object(args.intent_inventory)
                if set(intent_payload) != {"contributions", "dispositions"}:
                    raise ValueError(
                        "intent inventory must contain exactly contributions and dispositions"
                    )
                intent_contributions = tuple(
                    ModelIntentContribution.from_dict(item)
                    for item in intent_payload["contributions"]
                )
                intent_dispositions = tuple(
                    ModelIntentDisposition.from_dict(item)
                    for item in intent_payload["dispositions"]
                )
            no_intent_evidence = ()
            if args.no_declared_intent_evidence_fingerprints:
                evidence_payload = json.loads(
                    args.no_declared_intent_evidence_fingerprints
                )
                if not isinstance(evidence_payload, dict):
                    raise ValueError(
                        "no-declared-intent evidence fingerprints must be a JSON object"
                    )
                no_intent_evidence = tuple(
                    (str(role), str(fingerprint))
                    for role, fingerprint in evidence_payload.items()
                )
            report = build_current_model_revision(
                args.root,
                model_parent_receipt=args.model_parent_receipt,
                revision_set_id=args.revision_set_id,
                task_id=args.task_id,
                snapshot_id=args.snapshot_id,
                receipt_root=args.receipt_root or None,
                output_root=args.output_root or None,
                removal_dispositions=dispositions,
                intent_contributions=intent_contributions,
                intent_dispositions=intent_dispositions,
                no_declared_intent_rationale_id=(
                    args.no_declared_intent_rationale_id
                ),
                no_declared_intent_evidence_fingerprints=no_intent_evidence,
                no_declared_intent_rationale=(
                    args.no_declared_intent_rationale
                ),
                decision_reason=args.decision_reason,
            )
            _emit_payload(report.to_dict(), as_json=args.json)
            return 0
        if args.model_system_action == "activate":
            candidate = load_model_system_snapshot(args.candidate_snapshot)
            revision = ModelRevisionSet.from_dict(
                _read_json_object(args.revision_set)
            )
            head, receipt = activate_model_revision_set(
                args.root,
                candidate,
                revision,
                receipt_id=args.receipt_id,
            )
            _emit_payload(
                {
                    "status": "pass",
                    "head": head.to_dict(),
                    "receipt": receipt.to_dict(),
                },
                as_json=args.json,
            )
            return 0
        contract = ModelRollbackContract.from_dict(
            _read_json_object(args.contract)
        )
        rollback_candidate = load_model_system_snapshot(
            args.candidate_snapshot
        )
        reverse_revision = ModelRevisionSet.from_dict(
            _read_json_object(args.reverse_revision_set)
        )
        head, receipt = rollback_observed_model_system(
            args.root,
            contract,
            rollback_candidate,
            reverse_revision,
            completed_evidence_fingerprints=(
                args.completed_evidence_fingerprint
            ),
            requested_result=args.result,
            receipt_id=args.receipt_id,
            reason=args.reason,
        )
        _emit_payload(
            {
                "status": "pass",
                "head": head.to_dict(),
                "receipt": receipt.to_dict(),
            },
            as_json=args.json,
        )
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        _emit_payload(
            {"status": "blocked", "error": str(exc)},
            as_json=args.json,
        )
        return 1


def _run_model_maturation_review_command(args: argparse.Namespace) -> int:
    from .model_maturation import ModelMaturationPlan, review_model_maturation_loop, review_model_maturation_session

    try:
        plans = [ModelMaturationPlan.from_dict(_read_json_object(path)) for path in args.plan]
        if not plans:
            raise ValueError("at least one --plan JSON artifact is required")
        if len(plans) == 1:
            report = review_model_maturation_loop(plans[0])
            payload = report.to_dict()
            ok = report.ok
        else:
            session = review_model_maturation_session(plans, session_id=args.session_id)
            payload = session.to_dict()
            ok = session.closed
        _emit_payload(payload, as_json=args.json)
        return 0 if ok else 1
    except (OSError, ValueError, TypeError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_task_coverage_demand_command(args: argparse.Namespace) -> int:
    from .task_coverage_demand import TaskFacts, compile_task_coverage_demand

    try:
        facts = TaskFacts(**_read_json_object(args.facts))
        demand = compile_task_coverage_demand(facts)
        _emit_payload(
            {**demand.to_dict(), "fingerprint": demand.fingerprint},
            as_json=args.json,
        )
        return 0
    except (OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_model_maturation_receipt_verify_command(args: argparse.Namespace) -> int:
    from .evidence_receipts import ReceiptVerificationContext
    from .model_maturation_receipt import (
        ModelMaturationReceiptRef,
        ModelMaturationVerificationContext,
        verify_model_maturation_receipt,
    )

    try:
        payload = _read_json_object(args.context)
        receipt_ref = ModelMaturationReceiptRef(**dict(payload["receipt_ref"]))
        raw_model_context = dict(payload["verification_context"])
        raw_receipt_context = dict(raw_model_context.pop("receipt_context"))
        raw_snapshots = raw_receipt_context.get("input_snapshots", {})
        if isinstance(raw_snapshots, list):
            raw_receipt_context["input_snapshots"] = {
                str(item["artifact_id"]): item for item in raw_snapshots
            }
        receipt_context = ReceiptVerificationContext(**raw_receipt_context)
        context = ModelMaturationVerificationContext(
            receipt_context=receipt_context,
            **raw_model_context,
        )
        result = verify_model_maturation_receipt(
            receipt_ref,
            context,
            args.root,
            output_directory=args.receipt_root or None,
        )
        _emit_payload(result.to_dict(), as_json=args.json)
        return 0 if result.verified_maturation is not None else 1
    except (KeyError, OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_model_understanding_status_command(args: argparse.Namespace) -> int:
    from .understanding_readiness import (
        UnderstandingReadinessInput,
        compose_understanding_status,
    )

    def optional_artifact(path: str) -> dict[str, object]:
        return _read_json_object(path) if path else {}

    try:
        status = compose_understanding_status(
            UnderstandingReadinessInput(
                task_facts=optional_artifact(args.task_facts),
                model_identity=optional_artifact(args.model_identity),
                coverage_demand=optional_artifact(args.coverage_demand),
                owner_resolutions=tuple(
                    _read_json_object(path) for path in args.owner_resolution
                ),
                maturation_report=optional_artifact(args.maturation_report),
                receipt_verification=optional_artifact(args.receipt_verification),
                implementation_admission=optional_artifact(
                    args.implementation_admission
                ),
                blueprint_summary=optional_artifact(args.blueprint_summary),
                blueprint_scope_required=args.blueprint_scope_required,
                user_choice=args.user_choice,
                flowguard_claim_requested=args.flowguard_claim_requested,
            )
        )
        _emit_payload(
            {**status.to_dict(), "fingerprint": status.fingerprint},
            as_json=args.json,
        )
        return 0 if status.ok else 1
    except (OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _add_model_system_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    audit = subparsers.add_parser(
        "model-system-audit",
        help="Audit the sole observed model-system authority.",
    )
    audit.add_argument("--root", default=".")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(
        handler=_run_model_system_command,
        model_system_action="audit",
    )

    bootstrap = subparsers.add_parser(
        "model-system-bootstrap",
        help="Establish the first observed model-system authority.",
    )
    bootstrap.add_argument("--root", default=".")
    bootstrap.add_argument(
        "--snapshot",
        default="",
        help="Existing snapshot JSON; otherwise build from current owners.",
    )
    bootstrap.add_argument(
        "--snapshot-id",
        default="snapshot:observed-bootstrap",
    )
    bootstrap.add_argument("--evidence-fingerprint", required=True)
    bootstrap.add_argument("--json", action="store_true")
    bootstrap.set_defaults(
        handler=_run_model_system_command,
        model_system_action="bootstrap",
    )

    build = subparsers.add_parser(
        "model-revision-build",
        help=(
            "Build one accepted current-format revision from an exact-current "
            "full model-regression parent receipt without activating it."
        ),
    )
    build.add_argument("--root", default=".")
    build.add_argument("--model-parent-receipt", required=True)
    build.add_argument("--revision-set-id", required=True)
    build.add_argument("--task-id", required=True)
    build.add_argument("--snapshot-id", required=True)
    build.add_argument(
        "--receipt-root",
        default="",
        help="Model owner receipt store; defaults to the project current store.",
    )
    build.add_argument(
        "--output-root",
        default="",
        help="Model-mesh output root; defaults to .flowguard/model-mesh.",
    )
    build.add_argument(
        "--removal-dispositions",
        default="",
        help="Current-schema JSON array covering every removed governed id.",
    )
    build.add_argument(
        "--intent-inventory",
        default="",
        help=(
            "Current contribution/disposition JSON for this revision. It is "
            "exclusive with the no-declared-intent rationale fields."
        ),
    )
    build.add_argument("--no-declared-intent-rationale-id", default="")
    build.add_argument(
        "--no-declared-intent-evidence-fingerprints",
        default="",
        help="JSON object mapping evidence roles to exact sha256 fingerprints.",
    )
    build.add_argument("--no-declared-intent-rationale", default="")
    build.add_argument(
        "--decision-reason",
        default=(
            "The exact-current terminal-pass full model-regression parent "
            "receipt covers every affected native owner."
        ),
    )
    build.add_argument("--json", action="store_true")
    build.set_defaults(
        handler=_run_model_system_command,
        model_system_action="build",
    )

    activate = subparsers.add_parser(
        "model-revision-activate",
        help="Activate one accepted whole-system revision set.",
    )
    activate.add_argument("--root", default=".")
    activate.add_argument("--candidate-snapshot", required=True)
    activate.add_argument("--revision-set", required=True)
    activate.add_argument("--receipt-id", required=True)
    activate.add_argument("--json", action="store_true")
    activate.set_defaults(
        handler=_run_model_system_command,
        model_system_action="activate",
    )

    rollback = subparsers.add_parser(
        "model-revision-rollback",
        help="Restore or compensate real effects before rewinding authority.",
    )
    rollback.add_argument("--root", default=".")
    rollback.add_argument("--contract", required=True)
    rollback.add_argument("--candidate-snapshot", required=True)
    rollback.add_argument("--reverse-revision-set", required=True)
    rollback.add_argument(
        "--completed-evidence-fingerprint",
        action="append",
        default=[],
    )
    rollback.add_argument(
        "--result",
        choices=("exact", "compensated", "forward_repair"),
        required=True,
    )
    rollback.add_argument("--receipt-id", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--json", action="store_true")
    rollback.set_defaults(
        handler=_run_model_system_command,
        model_system_action="rollback",
    )


def _add_model_maturation_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "model-maturation-review",
        help="Review one or more task-local model maturation iterations.",
    )
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        required=True,
        help="Current-schema model maturation plan JSON; repeat for candidate iterations.",
    )
    parser.add_argument("--session-id", default="")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.set_defaults(handler=_run_model_maturation_review_command)

    demand = subparsers.add_parser(
        "task-coverage-demand",
        help="Derive the minimum model coverage from frozen task facts.",
    )
    demand.add_argument("--facts", required=True, help="Current TaskFacts JSON artifact.")
    demand.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    demand.set_defaults(handler=_run_task_coverage_demand_command)

    receipt = subparsers.add_parser(
        "model-maturation-receipt-verify",
        help="Independently verify one canonical model-maturation receipt.",
    )
    receipt.add_argument("--context", required=True, help="Receipt reference and verification context JSON.")
    receipt.add_argument("--root", default=".", help="Repository root containing the receipt store.")
    receipt.add_argument("--receipt-root", default="", help="Optional explicit receipt output directory.")
    receipt.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    receipt.set_defaults(handler=_run_model_maturation_receipt_verify_command)

    status = subparsers.add_parser(
        "model-understanding-status",
        help=(
            "Read already-produced understanding artifacts without running "
            "owners or publishing evidence."
        ),
    )
    status.add_argument("--task-facts", default="", help="Exact TaskFacts JSON artifact.")
    status.add_argument("--model-identity", default="", help="Exact current model identity JSON artifact.")
    status.add_argument("--coverage-demand", default="", help="Exact TaskCoverageDemand JSON artifact.")
    status.add_argument(
        "--owner-resolution",
        action="append",
        default=[],
        help="Exact owner-resolution JSON artifact; repeat once per demanded owner.",
    )
    status.add_argument("--maturation-report", default="", help="Exact maturation report JSON artifact.")
    status.add_argument(
        "--receipt-verification",
        default="",
        help="Existing independent maturation receipt-verification JSON artifact.",
    )
    status.add_argument(
        "--implementation-admission",
        default="",
        help="Existing implementation-admission JSON artifact.",
    )
    status.add_argument(
        "--blueprint-summary",
        default="",
        help="Existing compact target-system blueprint summary JSON artifact.",
    )
    status.add_argument(
        "--blueprint-scope-required",
        choices=("none", "affected", "whole"),
        default="none",
        help="Require no blueprint, an affected summary, or a whole-target summary.",
    )
    status.add_argument(
        "--user-choice",
        choices=("model_first", "direct_user_choice", "no_code"),
        default="model_first",
    )
    status.add_argument(
        "--no-flowguard-claim",
        action="store_false",
        dest="flowguard_claim_requested",
        help="Report a lightweight/direct path without claiming FlowGuard readiness.",
    )
    status.set_defaults(flowguard_claim_requested=True)
    status.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    status.set_defaults(handler=_run_model_understanding_status_command)


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
        "work-context-template",
        "Print or write a provider-neutral read-only WorkContext example.",
        "work_context",
        "work_context_template_files",
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


def _run_work_context_command(args: argparse.Namespace) -> int:
    from .work_context import read_work_context, review_work_context

    declaration = (
        json.loads(args.declaration_json)
        if args.declaration_json
        else {}
    )
    review = review_work_context(
        read_work_context(
            args.root,
            args.work_id,
            adapter_id=args.adapter,
            declaration=declaration,
        )
    )
    print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    return 0 if review.ok else 1


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


def _run_portable_system_check_command(args: argparse.Namespace) -> int:
    from .portable_model import load_portable_model
    from .portable_system import load_portable_system, load_system_composition_request
    from .system_composition import SystemCompositionReport, check_system_composition

    try:
        system = load_portable_system(args.system)
        request = load_system_composition_request(args.request)
        models = tuple(load_portable_model(path) for path in args.component)
        report = check_system_composition(system, request, models)
    except Exception as exc:
        report = SystemCompositionReport(
            status="invalid",
            system_id=args.system,
            system_fingerprint="",
            request_fingerprint="",
            stages={
                "component_local": "not_run",
                "contract_composition": "not_run",
                "affected_slice": "not_run",
                "system_composition": "not_run",
            },
            findings=(str(exc),),
        )
    print(report.to_json_text() if args.json else report.format_text())
    return {"pass": 0, "fail": 1, "blocked": 2, "invalid": 3}[report.status]


def _simulator_listing(root: Path) -> tuple[dict[str, object], int]:
    from .model_regressions import ModelRegressionManifest, audit_manifest

    manifest = ModelRegressionManifest.load(root)
    audit = audit_manifest(root, manifest)
    models = []
    for entry in sorted(manifest.entries, key=lambda item: item.model_id):
        model_exists = (root / entry.model_path).is_file()
        runner_exists = len(entry.runner) >= 2 and (root / entry.runner[1]).is_file()
        models.append(
            {
                "model_id": entry.model_id,
                "tier": entry.tier,
                "distribution_policy": entry.distribution_policy,
                "available": model_exists and runner_exists and not entry.excluded,
                "native_runner": list(entry.runner),
                "exclusion_reason": entry.exclusion_reason,
            }
        )
    payload: dict[str, object] = {
        "schema_version": "flowguard.model_simulator_listing.v1",
        "command": "flowguard-simulator",
        "status": "pass" if audit.ok else "blocked",
        "manifest_audit": audit.to_dict(),
        "models": models,
        "claim_boundary": "Listing proves manifest accounting and availability only; no model was executed.",
    }
    return payload, 0 if audit.ok else 2


def _run_simulator_command(args: argparse.Namespace) -> int:
    from .evidence_lifecycle import default_run_directory
    from .model_regressions import ModelRegressionManifest, audit_manifest, run_manifest_regressions, select_entries

    root = Path(args.root).resolve()
    try:
        if args.list:
            payload, exit_code = _simulator_listing(root)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "\n".join(
                [f"status: {payload['status']}", f"registered: {len(payload['models'])}"]
                + [f"model: {item['model_id']} tier={item['tier']} available={str(item['available']).lower()}" for item in payload["models"]]
            ))
            return exit_code
        if args.all and args.model:
            raise ValueError("--all and --model are mutually exclusive")
        if not args.all and not args.model:
            raise ValueError("execution requires at least one --model selector or explicit --all")
        manifest = ModelRegressionManifest.load(root)
        audit = audit_manifest(root, manifest)
        if not audit.ok:
            payload = {
                "schema_version": "flowguard.validation_result.v1",
                "command": "flowguard-simulator",
                "status": "blocked",
                "exit_code": 2,
                "blockers": list(audit.errors),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "status: blocked\n" + "\n".join(f"blocker: {item}" for item in audit.errors))
            return 2
        available_ids = tuple(
            entry.model_id
            for entry in manifest.entries
            if not entry.excluded
            and (root / entry.model_path).is_file()
            and len(entry.runner) >= 2
            and (root / entry.runner[1]).is_file()
        )
        unmatched = [pattern for pattern in args.model if not any(fnmatch.fnmatchcase(model_id, pattern) for model_id in available_ids)]
        if unmatched:
            raise ValueError("model selector matched no available registered model: " + ", ".join(unmatched))
        selected = select_entries(manifest, tier=args.tier, model_patterns=args.model)
        if not selected:
            raise ValueError("execution selected zero models at the requested tier")
        output_dir = Path(args.output_dir).resolve() if args.output_dir else default_run_directory(root, "simulator")
        report = run_manifest_regressions(
            root,
            tier=args.tier,
            model_patterns=args.model,
            jobs=args.jobs,
            timeout=args.timeout,
            output_dir=output_dir,
            cancel_event=threading.Event(),
            command="flowguard-simulator",
        )
        validation = report.to_validation_result()
        if args.json:
            result_path = Path(report.output_dir) / "report.json"
            result_sha256 = (
                "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
                if result_path.is_file()
                else ""
            )
            print(
                validation.terminal_json_text(
                    run_id=Path(report.output_dir).name,
                    result_path=str(result_path),
                    result_sha256=result_sha256,
                )
            )
        else:
            print(validation.format_text(full=args.full))
        return validation.exit_code
    except (ValueError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.validation_result.v1",
            "command": "flowguard-simulator",
            "status": "invalid_input",
            "exit_code": 3,
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"status: invalid_input\nerror: {exc}")
        return 3


def _blueprint_error_payload(code: str, exc: Exception) -> dict[str, object]:
    return {
        "ok": False,
        "status": "invalid",
        "findings": [
            {
                "code": code,
                "message": str(exc),
                "member_ids": [],
                "severity": "blocked",
            }
        ],
    }


def _run_implementation_inventory_audit_command(args: argparse.Namespace) -> int:
    from .implementation_inventory import (
        ImplementationInventoryError,
        audit_implementation_surface_inventory,
    )

    try:
        report = audit_implementation_surface_inventory(args.inventory, root=args.root)
    except (ImplementationInventoryError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("implementation_inventory_invalid", exc),
            as_json=args.json,
        )
        return 2
    _emit_payload(report.to_dict(), as_json=args.json)
    return 0 if report.ok else 1


def _blueprint_current_maps(args: argparse.Namespace) -> tuple[dict[str, str], ...]:
    values: list[dict[str, str]] = []
    for option, raw in (
        ("--portable-owner-fingerprints", args.portable_owner_fingerprints),
        ("--resource-fingerprints", args.resource_fingerprints),
        ("--oracle-fingerprints", args.oracle_fingerprints),
    ):
        parsed = _parse_json_mapping_arg(raw, option)
        values.append({str(key): str(value) for key, value in parsed.items()})
    return tuple(values)


def _load_and_qualify_blueprint(args: argparse.Namespace):
    from .implementation_blueprint import (
        load_model_implementation_binding_report,
        load_reconstruction_evidence,
        load_software_blueprint_manifest,
        qualify_software_blueprint,
    )
    from .implementation_inventory import (
        load_implementation_surface_inventory,
        review_implementation_surface_inventory,
    )

    manifest = load_software_blueprint_manifest(args.manifest)
    binding_report = load_model_implementation_binding_report(args.binding_report)
    inventory = load_implementation_surface_inventory(args.inventory)
    inventory_audit = review_implementation_surface_inventory(inventory, root=args.root)
    if not inventory_audit.ok:
        raise ValueError("implementation inventory audit is blocked")
    reconstruction = (
        load_reconstruction_evidence(args.reconstruction_evidence)
        if args.reconstruction_evidence
        else None
    )
    portable, resources, oracles = _blueprint_current_maps(args)
    report = qualify_software_blueprint(
        manifest,
        binding_report,
        implementation_inventory=inventory,
        reconstruction_evidence=reconstruction,
        reconstruction_required=args.require_reconstruction,
        current_observed_snapshot_fingerprint=args.observed_snapshot_fingerprint,
        current_semantic_mesh_fingerprint=args.semantic_mesh_fingerprint,
        current_test_inventory_fingerprint=args.test_inventory_fingerprint,
        current_model_test_alignment_report_fingerprint=(
            args.model_test_alignment_report_fingerprint
        ),
        current_portable_owner_fingerprints=portable,
        current_resource_fingerprints=resources,
        current_oracle_fingerprints=oracles,
    )
    return manifest, binding_report, inventory, report


def _run_model_blueprint_check_command(args: argparse.Namespace) -> int:
    from .implementation_blueprint import BlueprintValidationError

    try:
        _manifest, _binding_report, _inventory, report = _load_and_qualify_blueprint(args)
    except (BlueprintValidationError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("software_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    _emit_payload(report.to_dict(), as_json=args.json)
    return 0 if report.ok else 1


def _run_model_blueprint_export_command(args: argparse.Namespace) -> int:
    from .implementation_blueprint import (
        BlueprintValidationError,
        project_software_blueprint,
        write_software_blueprint_projection,
    )

    try:
        manifest, binding_report, inventory, report = _load_and_qualify_blueprint(args)
        if not report.ok:
            _emit_payload(report.to_dict(), as_json=args.json)
            return 1
        projection = project_software_blueprint(
            manifest,
            binding_report,
            implementation_inventory=inventory,
        )
        written = write_software_blueprint_projection(projection, args.output)
    except (BlueprintValidationError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("software_blueprint_export_failed", exc),
            as_json=args.json,
        )
        return 2
    root = Path(args.output).resolve()
    payload: dict[str, object] = {
        "ok": True,
        "status": "complete",
        "blueprint_fingerprint": manifest.fingerprint,
        "projection_fingerprint": projection.fingerprint,
        "written_paths": [path.relative_to(root).as_posix() for path in written],
        "reconstruction_status": report.empirical_status,
        "claim_text": report.claim_text,
    }
    _emit_payload(payload, as_json=args.json)
    return 0


def _run_flowguard_self_blueprint_check_command(args: argparse.Namespace) -> int:
    """Build and qualify FlowGuard's current self-blueprint without writing it."""

    from .self_blueprint import FlowGuardSelfBlueprintError, build_flowguard_self_blueprint
    from .self_architecture_reduction import (
        review_flowguard_self_architecture_reduction,
    )

    try:
        bundle = build_flowguard_self_blueprint(args.root)
        reduction_report = (
            review_flowguard_self_architecture_reduction(
                args.root,
                self_blueprint=bundle,
            )
            if getattr(args, "include_architecture_reduction", False)
            else None
        )
    except (FlowGuardSelfBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("flowguard_self_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    if args.compact:
        required_test_ids = set(bundle.test_inventory.required_node_ids)
        payload = {
            "ok": bundle.ok,
            "owner_status": bundle.behavior_report.owner_structure_status,
            "behavior_status": bundle.behavior_report.behavior_closure_status,
            "resource_status": (
                "complete" if bundle.resource_inventory.complete else "incomplete"
            ),
            "intent_status": (
                "complete" if bundle.intent_inventory.complete else "incomplete"
            ),
            "static_blueprint_status": bundle.target_system_report.status,
            "static_readiness": bundle.static_readiness.status,
            "deepest_proven_layer": (
                bundle.understanding_summary.deepest_proven_layer
            ),
            "first_gap": (
                bundle.understanding_summary.first_gap.to_dict()
                if bundle.understanding_summary.first_gap
                else None
            ),
            "gap_count": bundle.understanding_summary.gap_count,
            "test_nodes_total": len(bundle.test_inventory.nodes),
            "test_nodes_required": len(required_test_ids),
            "test_nodes_supporting": (
                len(bundle.test_inventory.nodes) - len(required_test_ids)
            ),
            "real_coverage_edges": len(bundle.behavior_report.coverage_edges),
            "binding_finding_codes": sorted(
                {row.code for row in bundle.binding_report.findings}
            ),
            "behavior_finding_codes": sorted(
                {row.code for row in bundle.behavior_report.findings}
            ),
            "planned_checker_gaps": sum(
                row.code
                in {
                    "behavior_test_design_missing",
                    "coverage_oracle_member_missing",
                    "coverage_test_node_missing",
                }
                for row in bundle.behavior_report.findings
            ),
            "blueprint_fingerprint": bundle.target_system_report.fingerprint,
            "self_blueprint_fingerprint": bundle.manifest.fingerprint,
            "claim_boundary": (
                "Compact read-only self-blueprint status for current static model depth."
            ),
        }
    else:
        payload = bundle.to_dict()
        payload["self_blueprint_fingerprint"] = bundle.manifest.fingerprint
    if reduction_report is not None:
        payload["composed_self_maintenance_review"] = True
        payload["architecture_reduction_review"] = (
            _compact_self_architecture_reduction_payload(reduction_report)
            if args.compact
            else reduction_report.to_dict()
        )
        payload["composed_claim_boundary"] = (
            "Both bounded reviews consume one exact in-memory self-blueprint; "
            "no cache or target-system artifact is written."
        )
    _emit_payload(payload, as_json=args.json)
    return 0 if bundle.ok and (reduction_report is None or reduction_report.ok) else 1


def _compact_self_architecture_reduction_payload(report: Any) -> dict[str, Any]:
    signal_counts: dict[str, int] = {}
    disposition_counts: dict[str, int] = {}
    for candidate in report.candidates:
        signal = str(candidate.metadata.get("signal", "unclassified"))
        disposition = str(candidate.metadata.get("disposition", "unresolved"))
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
    return {
        "schema_version": report.schema_version,
        "status": report.status,
        "ok": report.ok,
        "fingerprint": report.fingerprint,
        "self_blueprint_fingerprint": report.self_blueprint_fingerprint,
        "candidate_inventory_fingerprint": report.candidate_inventory_fingerprint,
        "candidate_count": len(report.candidates),
        "candidate_counts_by_signal": dict(sorted(signal_counts.items())),
        "candidate_counts_by_disposition": dict(
            sorted(disposition_counts.items())
        ),
        "denominator_complete": report.denominator_complete,
        "safe_unapplied_candidate_ids": list(
            report.safe_unapplied_candidate_ids
        ),
        "decision": report.reduction_report.decision,
        "required_next_routes": list(
            report.reduction_report.required_next_routes
        ),
        "claim_boundary": report.claim_boundary,
    }


def _run_flowguard_self_architecture_reduction_command(
    args: argparse.Namespace,
) -> int:
    """Review exact self-blueprint contraction signals without writing code."""

    from .self_architecture_reduction import (
        review_flowguard_self_architecture_reduction,
    )
    from .self_blueprint import FlowGuardSelfBlueprintError

    try:
        report = review_flowguard_self_architecture_reduction(args.root)
    except (FlowGuardSelfBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload(
                "flowguard_self_architecture_reduction_invalid", exc
            ),
            as_json=args.json,
        )
        return 2
    payload = report.to_dict()
    if args.compact:
        payload = _compact_self_architecture_reduction_payload(report)
    _emit_payload(payload, as_json=args.json)
    return 0 if report.ok else 1


def _run_project_blueprint_audit_command(args: argparse.Namespace) -> int:
    """Build a declared target-system software blueprint in memory only."""

    from .implementation_inventory_python import (
        PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        discover_python_implementation_surfaces,
    )
    from .project_blueprint import (
        ProjectBlueprintError,
        build_project_blueprint,
        load_project_blueprint_document,
    )
    from .test_inventory_python import (
        PYTHON_AST_TEST_ADAPTER_ID,
        discover_python_test_file,
    )

    try:
        definition, evidence = load_project_blueprint_document(args.definition)
        bundle = build_project_blueprint(
            args.root,
            definition,
            evidence,
            discovery_adapters={
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: (
                    discover_python_implementation_surfaces
                )
            },
            test_discovery_adapters={
                PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
            },
        )
    except (ProjectBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("project_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    _emit_payload(bundle.to_dict(), as_json=args.json)
    return 0 if bundle.ok else 1


def _run_project_blueprint_candidate_command(args: argparse.Namespace) -> int:
    """Discover unresolved behavior candidates without writing the target."""

    from .implementation_inventory import (
        ImplementationInventoryError,
        load_implementation_surface_inventory,
        review_implementation_surface_inventory,
    )
    from .software_blueprint_readiness import generate_candidate_blueprint

    try:
        inventory = load_implementation_surface_inventory(args.inventory)
        audit = review_implementation_surface_inventory(inventory, root=args.root)
        if not audit.ok:
            raise ValueError("implementation inventory audit is blocked")
        candidate = generate_candidate_blueprint(
            inventory,
            target_kind=args.target_kind,
            observation_provider_ids=tuple(args.provider),
        )
    except (ImplementationInventoryError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("project_blueprint_candidate_invalid", exc),
            as_json=args.json,
        )
        return 2
    payload = candidate.to_dict()
    if args.compact:
        payload = {
            "schema_version": payload["schema_version"],
            "inventory_fingerprint": payload["inventory_fingerprint"],
            "target_kind": payload["target_kind"],
            "observation_provider_ids": payload["observation_provider_ids"],
            "status": payload["status"],
            "behavior_contract_count": len(candidate.behavior_contracts),
            "unresolved_count": len(candidate.unresolved_ids),
            "first_unresolved_id": (
                candidate.unresolved_ids[0] if candidate.unresolved_ids else ""
            ),
            "blockers": list(candidate.blockers),
            "claim_boundary": payload["claim_boundary"],
        }
    _emit_payload(payload, as_json=args.json)
    return 0 if candidate.status == "ready" else 1


def _print_lifecycle(payload: dict[str, object], *, as_json: bool) -> int:
    status = str(payload.get("status", "pass"))
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {status}")
        if "counts" in payload:
            print("counts: " + " ".join(f"{key}={value}" for key, value in sorted(dict(payload["counts"]).items())))
        if "plan_id" in payload:
            print(f"plan_id: {payload['plan_id']}")
        if "quarantine_id" in payload:
            print(f"quarantine_id: {payload['quarantine_id']}")
        for finding in payload.get("findings", ()):
            print(f"finding: {finding.get('code')}: {finding.get('message')}")
    return 0 if status == "pass" else 2


def _run_evidence_lifecycle_command(args: argparse.Namespace) -> int:
    from .evidence_lifecycle import (
        EvidenceLifecycleError,
        apply_evidence_gc,
        audit_evidence,
        plan_evidence_gc,
        purge_evidence_quarantine,
        restore_evidence_quarantine,
        settle_interrupted_execution_leases,
        write_json_atomic,
    )

    try:
        if args.evidence_action == "audit":
            payload = audit_evidence(args.root)
        elif args.evidence_action == "plan":
            payload = plan_evidence_gc(
                args.root,
                keep=args.keep,
                include_legacy=args.include_legacy,
                preserve_paths=tuple(args.preserve),
            )
            if args.output:
                write_json_atomic(args.output, payload)
        elif args.evidence_action == "apply":
            payload = apply_evidence_gc(args.root, args.plan)
        elif args.evidence_action == "restore":
            payload = restore_evidence_quarantine(args.root, args.quarantine_id)
        elif args.evidence_action == "settle_interruption":
            leases = []
            for index, serialized in enumerate(args.lease_json):
                try:
                    row = json.loads(serialized)
                except json.JSONDecodeError as exc:
                    raise EvidenceLifecycleError(
                        f"--lease-json row {index} is not valid JSON"
                    ) from exc
                if not isinstance(row, dict):
                    raise EvidenceLifecycleError(
                        f"--lease-json row {index} must be one JSON object"
                    )
                leases.append(row)
            payload = settle_interrupted_execution_leases(
                args.lock_root,
                {
                    "schema_version": "flowguard.evidence_interruption_settlement_request.v1",
                    "plan_id": args.plan_id,
                    "process_id": args.process_id,
                    "operator_reason": args.operator_reason,
                    "zero_descendant_observation": {
                        "descendant_process_ids": list(args.descendant_process_id),
                        "observed_at_epoch": args.observed_at_epoch,
                        "observed_by": args.observed_by,
                        "method": args.observation_method,
                    },
                    "leases": leases,
                },
            )
        else:
            payload = purge_evidence_quarantine(args.root, args.quarantine_id)
        return _print_lifecycle(dict(payload), as_json=args.json)
    except (EvidenceLifecycleError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.evidence_lifecycle_error.v1",
            "status": "blocked",
            "message": str(exc),
            "claim_boundary": "No lifecycle mutation is accepted after an identity, reachability, or containment failure.",
        }
        return _print_lifecycle(payload, as_json=args.json)


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


def _add_work_context_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "work-context",
        help="Read one declared provider work unit through a registered read-only adapter.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--declaration-json", default="")
    parser.add_argument("--json", action="store_true", help="Canonical JSON is always emitted.")
    parser.set_defaults(handler=_run_work_context_command)


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

    system_check = subparsers.add_parser(
        "portable-system-check",
        help="Check one strict bounded system definition and request through the canonical portable checker.",
    )
    system_check.add_argument("--system", required=True, help="Portable system definition JSON path.")
    system_check.add_argument("--request", required=True, help="System composition request JSON path.")
    system_check.add_argument("--component", action="append", required=True, help="Referenced portable component model JSON path; repeat for every component.")
    system_check.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    system_check.set_defaults(handler=_run_portable_system_check_command)


def _add_implementation_blueprint_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    inventory = subparsers.add_parser(
        "implementation-inventory-audit",
        help="Read-only audit of one current implementation-surface inventory.",
    )
    inventory.add_argument("--inventory", required=True)
    inventory.add_argument("--root", default=None, help="Optional current source root.")
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(handler=_run_implementation_inventory_audit_command)

    def add_blueprint_inputs(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--inventory", required=True)
        parser.add_argument("--root", default=None, help="Optional current source root for inventory freshness.")
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--binding-report", required=True)
        parser.add_argument("--observed-snapshot-fingerprint", required=True)
        parser.add_argument("--semantic-mesh-fingerprint", required=True)
        parser.add_argument("--test-inventory-fingerprint", required=True)
        parser.add_argument(
            "--model-test-alignment-report-fingerprint", required=True
        )
        parser.add_argument("--portable-owner-fingerprints", default="{}")
        parser.add_argument("--resource-fingerprints", default="{}")
        parser.add_argument("--oracle-fingerprints", default="{}")
        parser.add_argument("--reconstruction-evidence", default="")
        parser.add_argument(
            "--require-reconstruction",
            action="store_true",
            help="Require a supplied passing receipt; never launches reconstruction.",
        )
        parser.add_argument("--json", action="store_true")

    check = subparsers.add_parser(
        "model-blueprint-check",
        help="Read-only static/empirical blueprint qualification; never rebuilds software.",
    )
    add_blueprint_inputs(check)
    check.set_defaults(handler=_run_model_blueprint_check_command)

    export = subparsers.add_parser(
        "model-blueprint-export",
        help="Explicitly write one current deterministic blueprint projection.",
    )
    add_blueprint_inputs(export)
    export.add_argument("--output", required=True)
    export.set_defaults(handler=_run_model_blueprint_export_command)

    self_check = subparsers.add_parser(
        "flowguard-self-blueprint-check",
        help="Read-only audit of FlowGuard's current checked-in self-blueprint.",
    )
    self_check.add_argument("--root", default=".", help="FlowGuard repository root.")
    self_check.add_argument("--compact", action="store_true")
    self_check.add_argument(
        "--include-architecture-reduction",
        action="store_true",
        help=(
            "Reuse this exact in-memory self-blueprint for the read-only "
            "architecture-reduction review."
        ),
    )
    self_check.add_argument("--json", action="store_true")
    self_check.set_defaults(handler=_run_flowguard_self_blueprint_check_command)

    self_reduction = subparsers.add_parser(
        "flowguard-self-architecture-reduction-review",
        help=(
            "Read-only self-blueprint contraction audit; reports candidates "
            "and never rewrites production code."
        ),
    )
    self_reduction.add_argument(
        "--root", default=".", help="FlowGuard repository root."
    )
    self_reduction.add_argument("--compact", action="store_true")
    self_reduction.add_argument("--json", action="store_true")
    self_reduction.set_defaults(
        handler=_run_flowguard_self_architecture_reduction_command
    )

    project_check = subparsers.add_parser(
        "project-blueprint-audit",
        help=(
            "Read-only provider-neutral project blueprint audit; never writes the target "
            "or executes a target-system action."
        ),
    )
    project_check.add_argument("--root", required=True, help="Bounded project root.")
    project_check.add_argument(
        "--definition", required=True, help="Strict current project-blueprint JSON."
    )
    project_check.add_argument("--json", action="store_true")
    project_check.set_defaults(handler=_run_project_blueprint_audit_command)

    candidate = subparsers.add_parser(
        "project-blueprint-candidate",
        help=(
            "Read-only unresolved behavior candidate discovery from one current implementation inventory."
        ),
    )
    candidate.add_argument("--inventory", required=True)
    candidate.add_argument("--root", required=True, help="Bounded current project root.")
    candidate.add_argument("--target-kind", default="software")
    candidate.add_argument(
        "--provider",
        action="append",
        default=[],
        help=(
            "Exact observation provider id; repeatable. When omitted, current "
            "inventory surface provider identities are used."
        ),
    )
    candidate.add_argument(
        "--compact",
        action="store_true",
        help="Return only depth/count/first-gap data for ordinary AI routing.",
    )
    candidate.add_argument("--json", action="store_true")
    candidate.set_defaults(handler=_run_project_blueprint_candidate_command)


def _add_simulator_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "simulator",
        help="List or execute manifest-registered FlowGuard models through their native runners.",
    )
    parser.add_argument("--root", default=".", help="FlowGuard project root.")
    parser.add_argument("--list", action="store_true", help="Audit and list registered models without executing them.")
    parser.add_argument("--model", action="append", default=[], help="Exact model id or glob; repeatable.")
    parser.add_argument("--all", action="store_true", help="Explicitly execute every model eligible for --tier.")
    parser.add_argument("--tier", choices=("fast", "focused", "full"), default="focused")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=float, help="Override each native runner timeout in seconds.")
    parser.add_argument("--output-dir", help="Retained run directory; defaults under .flowguard/evidence/simulator.")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.add_argument("--full", action="store_true", help="Include complete bounded text summaries.")
    parser.set_defaults(handler=_run_simulator_command)


def _add_evidence_lifecycle_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    audit = subparsers.add_parser("evidence-audit", help="Read-only audit of FlowGuard evidence reachability and storage.")
    audit.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="audit")

    plan = subparsers.add_parser("evidence-gc-plan", help="Create an exact read-only evidence GC plan.")
    plan.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    plan.add_argument("--keep", type=int, default=2, help="Retain this many newest otherwise-collectible runs.")
    plan.add_argument("--include-legacy", action="store_true", help="Explicitly include lifecycle-unmanaged historical parents.")
    plan.add_argument(
        "--preserve",
        action="append",
        default=[],
        help="Exact audited run path to preserve; repeat for externally bound legacy evidence.",
    )
    plan.add_argument("--output", help="Optional plan artifact path.")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="plan")

    apply = subparsers.add_parser("evidence-gc-apply", help="Quarantine candidates from one exact current GC plan.")
    apply.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    apply.add_argument("--plan", required=True, help="GC plan JSON path.")
    apply.add_argument("--json", action="store_true")
    apply.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="apply")

    restore = subparsers.add_parser("evidence-gc-restore", help="Restore one exact evidence quarantine.")
    restore.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    restore.add_argument("--quarantine-id", required=True)
    restore.add_argument("--json", action="store_true")
    restore.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="restore")

    purge = subparsers.add_parser("evidence-gc-purge", help="Purge one exact quarantine after current/pin replay.")
    purge.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    purge.add_argument("--quarantine-id", required=True)
    purge.add_argument("--json", action="store_true")
    purge.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="purge")

    settle = subparsers.add_parser(
        "evidence-settle-interruption",
        help="Settle only named dead-process residual leases into immutable interrupted evidence.",
    )
    settle.add_argument("--lock-root", required=True, help="Exact execution-lease directory.")
    settle.add_argument("--plan-id", required=True, help="Exact frozen validation plan id.")
    settle.add_argument("--process-id", required=True, type=int, help="Former producer process id.")
    settle.add_argument("--operator-reason", required=True)
    settle.add_argument("--observed-by", required=True)
    settle.add_argument("--observation-method", required=True)
    settle.add_argument("--observed-at-epoch", required=True, type=float)
    settle.add_argument(
        "--descendant-process-id",
        action="append",
        type=int,
        default=[],
        help="Observed live descendant; any supplied id blocks settlement.",
    )
    settle.add_argument(
        "--lease-json",
        action="append",
        required=True,
        help=(
            "Exact JSON object with owner_id, resource_key, execution_key, and lease_token; repeat."
        ),
    )
    settle.add_argument("--json", action="store_true")
    settle.set_defaults(
        handler=_run_evidence_lifecycle_command,
        evidence_action="settle_interruption",
    )


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
    _add_work_context_parser(subparsers)
    _add_portable_model_parsers(subparsers)
    _add_implementation_blueprint_parsers(subparsers)
    _add_simulator_parser(subparsers)
    _add_evidence_lifecycle_parsers(subparsers)
    _add_model_system_parsers(subparsers)
    _add_model_maturation_parser(subparsers)
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
