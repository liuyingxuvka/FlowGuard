"""Run the development_process_flow rollout model checks."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "development_process_flow"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
from flowguard import Scenario, ScenarioExpectation, review_scenarios
import model
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from flowguard.process_supervision import run_supervised
from flowguard.validation_ownership import nested_owner_launch_allowed


REQUIRED_LABELS = ("validation_passed", "release_accepted")


def run_implementation_admission_model() -> bool:
    report = review_scenarios(
        (
            Scenario(
                "closed_model_admits_implementation",
                "current closed-for-task maturation admits the requested scope",
                model.admission_initial_state(),
                model.GOOD_CLOSED_ADMISSION_SEQUENCE,
                ScenarioExpectation(expected_status="ok"),
                workflow=model.build_admission_workflow(),
            ),
            Scenario(
                "exact_authorization_allows_scoped_attempt",
                "an exact authorization permits only its bounded scope without changing understanding",
                model.admission_initial_state(),
                model.GOOD_SCOPED_ADMISSION_SEQUENCE,
                ScenarioExpectation(expected_status="ok"),
                workflow=model.build_admission_workflow(),
            ),
            Scenario(
                "authorization_cannot_erase_gaps",
                "a mismatched authorization cannot manufacture full model confidence",
                model.admission_initial_state(),
                model.BROKEN_AUTHORIZATION_SEQUENCE,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(
                        "no_admission_without_task_sufficiency_or_exact_scope",
                    ),
                ),
                workflow=model.build_admission_workflow(broken=True),
            ),
        ),
        default_invariants=model.ADMISSION_INVARIANTS,
    )
    print(report.format_text())
    print()
    return report.ok


def run_release_identity_model() -> bool:
    scenarios = []
    for identity, sequence in model.STALE_OR_SUBSTITUTED_RELEASE_SEQUENCES:
        scenarios.append(
            Scenario(
                f"{identity}_stale_or_substituted_is_rejected",
                f"a stale or substituted {identity} identity cannot support release",
                model.initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("release_rejected",),
                    forbidden_trace_labels=("release_accepted",),
                ),
                workflow=model.build_correct_workflow(),
            )
        )
        scenarios.append(
            Scenario(
                f"broken_{identity}_substitution_is_detected",
                f"the known-bad gate exposes an accepted release with substituted {identity}",
                model.initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(
                        "no_release_with_stale_or_incomplete_evidence",
                    ),
                    required_trace_labels=("release_accepted",),
                ),
                workflow=model.build_broken_workflow(),
            )
        )
    report = review_scenarios(tuple(scenarios), default_invariants=model.INVARIANTS)
    print(report.format_text())
    print()
    return report.ok


def run_author_shadow_sync_model() -> bool:
    scenarios = [
        Scenario(
            "failed_author_activation_rolls_back_before_claim",
            "a failed author activation restores the prior shadow and cannot claim author currentness",
            model.author_sync_initial_state(),
            model.GOOD_AUTHOR_SYNC_ROLLBACK_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("author_sync_rolled_back",),
                forbidden_trace_labels=("author_sync_accepted",),
            ),
            workflow=model.build_author_sync_workflow(),
        )
    ]
    for case_id, _failure_id, invariant_id, sequence in model.AUTHOR_SYNC_FAILURE_CASES:
        scenarios.append(
            Scenario(
                f"{case_id}_is_rejected",
                f"the correct author-sync gate rejects {case_id.replace('_', ' ')}",
                model.author_sync_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("author_sync_rejected",),
                    forbidden_trace_labels=("author_sync_accepted",),
                ),
                workflow=model.build_author_sync_workflow(),
            )
        )
        scenarios.append(
            Scenario(
                f"broken_{case_id}",
                f"the known-bad author-sync gate exposes {case_id.replace('_', ' ')}",
                model.author_sync_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(invariant_id,),
                    required_trace_labels=("author_sync_accepted",),
                ),
                workflow=model.build_author_sync_workflow(broken=True),
            )
        )
    report = review_scenarios(
        tuple(scenarios),
        default_invariants=model.AUTHOR_SYNC_INVARIANTS,
    )
    print(report.format_text())
    print()
    exact_ok = run_exact_workflow_case(
        "correct_author_shadow_sync",
        workflow=model.build_author_sync_workflow(),
        initial_state=model.author_sync_initial_state(),
        external_input_sequence=model.GOOD_AUTHOR_SYNC_SEQUENCE,
        invariants=model.AUTHOR_SYNC_INVARIANTS,
        final_state_predicate=lambda state: state.claim == "accepted",
    )
    return report.ok and exact_ok


def run_path_quality_lifecycle_model() -> bool:
    scenarios = [
        Scenario(
            "ordinary_path_quality_stays_lightweight",
            "an ordinary change refreshes only the deterministic light review before activation",
            model.path_quality_lifecycle_initial_state(),
            model.GOOD_PATH_QUALITY_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("activation_bound_to_current_review",),
                forbidden_trace_labels=("deep_review_current",),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(),
        ),
        Scenario(
            "evidence_triggered_deep_review_stays_current",
            "a triggered deep review runs before implementation and again after the change",
            model.path_quality_lifecycle_initial_state(),
            model.GOOD_TRIGGERED_DEEP_PATH_QUALITY_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "deep_review_triggered",
                    "deep_review_current",
                    "activation_bound_to_current_review",
                ),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(),
        ),
    ]
    for case_id, sequence, rejected_label in model.PATH_QUALITY_FAILURE_SEQUENCES:
        scenarios.append(
            Scenario(
                f"{case_id}_is_rejected",
                f"the process rejects {case_id.replace('_', ' ')}",
                model.path_quality_lifecycle_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=(rejected_label,),
                    forbidden_trace_labels=("activation_bound_to_current_review",),
                ),
                workflow=model.build_path_quality_lifecycle_workflow(),
            )
        )
    stale_sequence = next(
        sequence
        for case_id, sequence, _label in model.PATH_QUALITY_FAILURE_SEQUENCES
        if case_id == "candidate_without_post_change_refresh"
    ) + (model.PathQualityLifecycleAction("activate", model.PATH_QUALITY_STALE_FINGERPRINT),)
    scenarios.append(
        Scenario(
            "broken_gate_exposes_stale_activation",
            "the known-bad gate exposes activation without a refreshed exact result",
            model.path_quality_lifecycle_initial_state(),
            stale_sequence,
            ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=(
                    "path_quality_activation_requires_current_exact_result",
                ),
                required_trace_labels=("activation_bound_to_current_review",),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(broken=True),
        )
    )
    report = review_scenarios(
        tuple(scenarios),
        default_invariants=model.PATH_QUALITY_LIFECYCLE_INVARIANTS,
    )
    print(report.format_text())
    print()
    return report.ok


def run_producer_episode_model() -> bool:
    good = run_exact_workflow_case(
        "producer_current_episode_publishes",
        workflow=model.build_producer_workflow(),
        initial_state=model.ProducerState(),
        external_input_sequence=model.PRODUCER_GOOD_SEQUENCE,
        invariants=model.PRODUCER_INVARIANTS,
        final_state_predicate=lambda state: state.receipt_published,
    )
    scenarios = []
    for case_id, _failure_id, sequence in model.PRODUCER_FAILURE_CASES:
        scenarios.extend((
            Scenario(
                f"producer_{case_id}_is_rejected",
                "The exact producer gate preserves the reservation/order/terminal boundary.",
                model.ProducerState(), sequence,
                ScenarioExpectation(expected_status="ok", required_trace_labels=(
                    "producer_reservation_blocked" if case_id == "duplicate_full_reservation"
                    else "producer_launch_blocked" if case_id in {"unknown_dependency", "unordered_shared_resource"}
                    else "producer_publication_blocked",
                )), workflow=model.build_producer_workflow(),
            ),
            Scenario(
                f"broken_producer_{case_id}",
                "A known-bad gate accepts the protected producer failure.",
                model.ProducerState(), sequence,
                ScenarioExpectation(expected_status="violation", expected_violation_names=("producer_exact_reservation_order_and_terminal",)),
                workflow=model.build_producer_workflow(broken=True),
            ),
        ))
    report = review_scenarios(tuple(scenarios), default_invariants=model.PRODUCER_INVARIANTS)
    print(report.format_text())
    # Retain each actual counterexample and its source-declared protected
    # failure identity. The generic invariant alone cannot prove eight
    # distinct producer failure obligations.
    protected = {f"broken_producer_{case_id}": failure_id
                 for case_id, failure_id, _sequence in model.PRODUCER_FAILURE_CASES}
    native_cases = []
    for result in report.results:
        failure_id = protected.get(result.scenario_name)
        if failure_id is None:
            continue
        run = result.scenario_run
        findings = list(run.observed_violation_names)
        if (result.ok and run.observed_status == "violation"
                and "producer_exact_reservation_order_and_terminal" in findings):
            findings.append(failure_id)
        native_cases.append({
            "name": result.scenario_name, "case_kind": "bad",
            "ok": result.ok, "observed_status": run.observed_status,
            "observed_finding_codes": findings,
            # This named owner projection contains more evidence than the
            # captured generic scenario report; preserve it in the native row.
            "projection_priority": 60,
            "projection_source": "owner-protected-counterexample",
        })
    print(json.dumps({"native_cases": native_cases}, sort_keys=True))
    return good and report.ok


def run_producer_implementation_contract() -> bool:
    """One contained pytest child proves the exact paired implementation oracles.

    Test identities come from pytest's own report.nodeid, never display names.
    Each selector receives its own observed JUnit verdict; an aggregate count,
    skipped case or unrelated passing test cannot stand in for an oracle.
    """
    if not nested_owner_launch_allowed("development_process_flow", "development_process_flow:native_pytest"):
        print("producer implementation blocked: another owner owns this child; no relaunch or inferred reuse")
        return False
    output_text = os.environ.get("FLOWGUARD_OUTPUT_DIR", "").strip()
    if not output_text:
        print("producer implementation blocked: exact run-local output directory is required")
        return False
    output = Path(output_text).resolve() / "producer-implementation"
    if output.exists():
        print("producer implementation blocked: child output identity already exists")
        return False
    output.mkdir(parents=True)
    junit_path, nodeids_path = output / "junit.xml", output / "nodeids.json"
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["FLOWGUARD_PYTEST_NODEIDS"] = str(nodeids_path)
    command = (sys.executable, "-B", "-m", "pytest", *model.NATIVE_PYTEST_SELECTORS,
               "-q", "-p", "no:cacheprovider", "-p", "flowguard.pytest_nodeid_recorder", f"--junitxml={junit_path}")
    result = run_supervised(command, cwd=_FLOWGUARD_PROJECT_ROOT, timeout_seconds=180, environment=environment)
    (output / "terminal.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (output / "stderr.log").write_text(result.stderr, encoding="utf-8")
    rows, findings = [], []
    try:
        nodes = json.loads(nodeids_path.read_text(encoding="utf-8"))
        if set(nodes) != {"schema_version", "nodeids", "exit_status"} or nodes["schema_version"] != "flowguard.pytest_nodeids.v1" or type(nodes["exit_status"]) is not int or nodes["exit_status"] != 0:
            raise ValueError("invalid exact pytest node-id contract")
        nodeids = nodes["nodeids"]
        if not isinstance(nodeids, list) or not all(isinstance(n, str) and n for n in nodeids) or len(set(nodeids)) != len(nodeids):
            raise ValueError("missing or duplicate executed pytest node identity")
        cases = ET.parse(junit_path).getroot().findall(".//testcase")
        if not cases or len(cases) != len(nodeids):
            raise ValueError("JUnit/executed node identity cardinality mismatch")
        for nodeid, case in zip(nodeids, cases, strict=True):
            matched = [s for s in model.NATIVE_PYTEST_SELECTORS if nodeid == s or nodeid.startswith(s + "[")]
            if len(matched) != 1:
                raise ValueError("foreign or ambiguous executed selector")
            outcome = "pass" if not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) else "nonpass"
            rows.append({"pytest_nodeid": nodeid, "selector": matched[0], "status": outcome})
        for selected in model.NATIVE_PYTEST_SELECTORS:
            observed = [r for r in rows if r["selector"] == selected]
            expected_count = 2 if selected.endswith("::test_authentic_cancelled_episode_cannot_publish_receipt") else 1
            if len(observed) != expected_count or any(r["status"] != "pass" for r in observed):
                findings.append("missing_or_nonpassing_oracle:" + selected)
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        findings.append("implementation_oracle_evidence_invalid:" + str(exc))
    if not result.ok:
        findings.append("implementation_child_not_current_terminal_zero_descendants")
    selector_ok = {s: bool([r for r in rows if r["selector"] == s]) and all(r["status"] == "pass" for r in rows if r["selector"] == s) for s in model.NATIVE_PYTEST_SELECTORS}
    payload = {
        "schema_version": "flowguard.development_producer_implementation.v1",
        "status": "pass" if not findings else "blocked",
        "claim_boundary": "Exact selected source implementation oracles for this current contained child; model-policy results remain separate.",
        "command": list(command), "executed_tests": rows, "findings": findings,
        "good_oracles": [{"selector": s, "passed": selector_ok[s]} for s in model.PRODUCER_GOOD_IMPLEMENTATION_SELECTORS],
        "protected_failure_oracles": [{"case_id": c, "protected_failure_id": next(f for case, f, _ in model.PRODUCER_FAILURE_CASES if case == c), "selector": s, "passed": selector_ok[s]} for c, s in model.PRODUCER_IMPLEMENTATION_ORACLES],
        "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (junit_path, nodeids_path, output / "terminal.json") if p.is_file()},
    }
    (output / "result.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("producer implementation:", payload["status"], "exact executed oracles:", len(rows))
    return not findings


def main() -> int:
    admission_ok = run_implementation_admission_model()
    release_identity_ok = run_release_identity_model()
    author_sync_ok = run_author_shadow_sync_model()
    path_quality_lifecycle_ok = run_path_quality_lifecycle_model()
    producer_model_ok = run_producer_episode_model()
    producer_implementation_ok = run_producer_implementation_contract()
    exact_ok = run_exact_workflow_case(
        "correct_development_process_flow",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.GOOD_RELEASE_SEQUENCE,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.release_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "development_process_flow",
        (
            FormalWorkflowCase("broken_reuses_stale_or_progress_evidence", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase(
                "broken_accepts_wrong_plane_action",
                model.build_broken_plane_workflow(),
                False,
                required_labels=("wrong_plane_action_accepted",),
            ),
            FormalWorkflowCase(
                "broken_accepts_mutating_spec_context",
                model.build_broken_workflow(),
                False,
                required_labels=("validation_passed", "release_accepted"),
                external_inputs=(
                    model.LifecycleAction(
                        "run_validation",
                        spec_context_read_only=False,
                        spec_receipt_bridge_present=True,
                    ),
                    model.LifecycleAction("claim_release"),
                ),
                max_sequence_length=2,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="stale_process_evidence",
    )
    return (
        0
        if admission_ok
        and release_identity_ok
        and author_sync_ok
        and path_quality_lifecycle_ok
        and producer_model_ok
        and producer_implementation_ok
        and exact_ok
        and report.ok
        else 1
    )

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:development_process_flow", main, declared_source_exporter=__import__('model').export_path_quality_source))
