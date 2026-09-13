"""Run current-evidence closure checks for ordinary UI content admission."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "harden_ui_content_visibility_validation"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import model
from flowguard import (
    review_model_test_alignment,
    review_risk_evidence_ledger,
    review_test_mesh,
)
from flowguard.validation_ownership import nested_owner_launch_allowed


_ARTIFACT_PATHS = {
    "focused-ui-core": model.CORE_JUNIT,
    "ui-templates": model.TEMPLATE_JUNIT,
    "contract-matrix": model.MATRIX_JUNIT,
    "ui-flow-structure-model": model.UI_MODEL_RESULT,
    "real-surface-model": model.REAL_SURFACE_RESULT,
    "behavior-ledger-model": model.BEHAVIOR_LEDGER_RESULT,
    "field-lifecycle-model": model.FIELD_LIFECYCLE_RESULT,
}


def _artifact_fingerprint(path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError):
        return ""


def _junit_payload_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        root = ET.parse(path).getroot()
        suites = [root, *root.findall(".//testsuite")]
        tests = sum(int(item.attrib.get("tests", "0")) for item in suites)
        failures = sum(int(item.attrib.get("failures", "0")) for item in suites)
        errors = sum(int(item.attrib.get("errors", "0")) for item in suites)
        return tests > 0 and failures == 0 and errors == 0
    except (OSError, ET.ParseError, TypeError, ValueError):
        return False


def _child_payload_valid(payload: object, path: Path) -> bool:
    """Validate the child-owned shape instead of trusting only ``ok``."""

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return False
    if path == model.UI_MODEL_RESULT:
        return (
            isinstance(payload.get("check_count"), int)
            and payload["check_count"] > 0
            and isinstance(payload.get("passed_expectations"), int)
            and payload["passed_expectations"] == payload["check_count"]
        )
    if path == model.REAL_SURFACE_RESULT:
        cases = payload.get("cases")
        return isinstance(cases, list) and bool(cases) and all(
            isinstance(item, dict) and item.get("ok") is True for item in cases
        )
    if path == model.BEHAVIOR_LEDGER_RESULT:
        report = payload.get("report")
        return isinstance(report, dict) and report.get("ok") is True
    if path == model.FIELD_LIFECYCLE_RESULT:
        formal = payload.get("formal_report")
        handoff = payload.get("ui_reader_handoff")
        fields = payload.get("product_language_authority_fields")
        field_report = fields.get("report") if isinstance(fields, dict) else None
        return bool(
            payload.get("exact_workflow_ok") is True
            and isinstance(formal, dict)
            and formal.get("ok") is True
            and isinstance(handoff, dict)
            and handoff.get("ok") is True
            and isinstance(fields, dict)
            and fields.get("ok") is True
            and isinstance(field_report, dict)
            and field_report.get("ok") is True
        )
    return True


def _artifact_current(run_id: str, path: Path) -> bool:
    if run_id in {"focused-ui-core", "ui-templates", "contract-matrix"}:
        return _junit_payload_ok(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return _child_payload_valid(payload, path)


def _run(
    run_id: str,
    args: tuple[str, ...],
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    child_owner_id = {
        "focused-ui-core": "ui_flow_structure_skill",
        "ui-templates": "ui_flow_structure_skill",
        "contract-matrix": "model_test_code_alignment",
        "ui-flow-structure-model": "ui_flow_structure_skill",
        "real-surface-model": "harden_ui_real_surface_validation",
        "behavior-ledger-model": "behavior_commitment_ledger",
        "field-lifecycle-model": "default_replacement_field_lifecycle",
    }.get(run_id, run_id)
    parent_owner_id = "harden_ui_content_visibility_validation"
    if not nested_owner_launch_allowed(parent_owner_id, child_owner_id):
        artifact = _ARTIFACT_PATHS.get(run_id)
        if artifact is not None and _artifact_current(run_id, artifact):
            return {
                "run_id": run_id,
                "command": [sys.executable, *args],
                "exit_code": 0,
                "ok": True,
                "status": "reused_current",
                "artifact_path": str(artifact),
                "artifact_fingerprint": _artifact_fingerprint(artifact),
                "message": (
                    "outer validation plan selected this child owner; consumed "
                    "its current verified artifact without relaunch"
                ),
            }
        return {
            "run_id": run_id,
            "command": [sys.executable, *args],
            "exit_code": 2,
            "ok": False,
            "status": "reuse_required",
            "finding_code": "nested_owner_selected_reuse_required",
            "message": (
                "outer validation plan selected this child owner; consume its "
                "current receipt instead of relaunching"
            ),
        }
    env = os.environ.copy()
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        env["FLOWGUARD_OUTPUT_DIR"] = str(output_dir)
    completed = subprocess.run(
        (sys.executable, *args),
        cwd=model.ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    artifact = _ARTIFACT_PATHS.get(run_id)
    artifact_ok = (
        _artifact_current(run_id, artifact)
        if artifact is not None and completed.returncode == 0
        else False
    )
    return {
        "run_id": run_id,
        "command": [sys.executable, *args],
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0 and artifact_ok,
        "status": "executed_current" if completed.returncode == 0 and artifact_ok else "failed",
        "artifact_path": str(artifact) if artifact is not None else "",
        "artifact_fingerprint": _artifact_fingerprint(artifact) if artifact is not None else "",
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _child_payload_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return _child_payload_valid(payload, path)


def _run_record_ok(run: object) -> bool:
    return isinstance(run, dict) and run.get("ok") is True and run.get("status") in {
        "executed_current",
        "reused_current",
    }


def _gate(
    evidence_runs: list[dict[str, object]],
    child_results: dict[str, bool],
    reports: dict[str, object],
    canonical_chain_ok: bool,
) -> bool:
    required_runs = {
        "focused-ui-core",
        "ui-templates",
        "contract-matrix",
        "ui-flow-structure-model",
        "real-surface-model",
        "behavior-ledger-model",
        "field-lifecycle-model",
    }
    if {
        str(run.get("run_id")) for run in evidence_runs if isinstance(run, dict)
    } != required_runs:
        return False
    if not all(_run_record_ok(run) for run in evidence_runs):
        return False
    if set(child_results) != {
        "ui_flow_structure",
        "real_surface",
        "behavior_ledger",
        "field_lifecycle",
    } or not all(value is True for value in child_results.values()):
        return False
    required_reports = {
        "contract_exhaustion",
        "model_test_alignment",
        "test_mesh",
        "risk_evidence_ledger",
    }
    if set(reports) != required_reports:
        return False
    if not all(
        hasattr(report, "to_dict") and getattr(report, "ok", False) is True
        for report in reports.values()
    ):
        return False
    return canonical_chain_ok is True


def main() -> int:
    model.EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    evidence_runs = [
        _run("focused-ui-core", model.CORE_PYTEST_ARGS),
        _run("ui-templates", model.TEMPLATE_PYTEST_ARGS),
        _run("contract-matrix", model.MATRIX_PYTEST_ARGS),
        _run(
            "ui-flow-structure-model",
            (".flowguard/verification/owners/ui_flow_structure_skill/run_checks.py",),
            output_dir=model.UI_MODEL_RESULT.parent,
        ),
        _run(
            "real-surface-model",
            (".flowguard/verification/owners/harden_ui_real_surface_validation/run_checks.py",),
            output_dir=model.REAL_SURFACE_RESULT.parent,
        ),
        _run(
            "behavior-ledger-model",
            (".flowguard/verification/owners/behavior_commitment_ledger/run_checks.py",),
            output_dir=model.BEHAVIOR_LEDGER_RESULT.parent,
        ),
        _run(
            "field-lifecycle-model",
            (".flowguard/verification/owners/default_replacement_field_lifecycle/run_checks.py",),
            output_dir=model.FIELD_LIFECYCLE_RESULT.parent,
        ),
    ]
    child_results = {
        "ui_flow_structure": _child_payload_ok(model.UI_MODEL_RESULT),
        "real_surface": _child_payload_ok(model.REAL_SURFACE_RESULT),
        "behavior_ledger": _child_payload_ok(model.BEHAVIOR_LEDGER_RESULT),
        "field_lifecycle": _child_payload_ok(model.FIELD_LIFECYCLE_RESULT),
    }
    evidence_ok = all(_run_record_ok(run) for run in evidence_runs) and all(child_results.values())

    reports = {}
    canonical_chain_ok = False
    if evidence_ok:
        reports = {
            "contract_exhaustion": model.contract_exhaustion_report(),
            "model_test_alignment": review_model_test_alignment(model.model_test_alignment_plan()),
            "test_mesh": review_test_mesh(model.test_mesh_plan()),
            "risk_evidence_ledger": review_risk_evidence_ledger(model.risk_evidence_ledger_plan()),
        }
        canonical_chain_ok = model.canonical_contract_chain_ok()

    ok = _gate(evidence_runs, child_results, reports, canonical_chain_ok)

    def _native_case(
        name: str,
        value: bool,
        *,
        observed_status: str = "ok",
        case_kind: str = "good",
    ) -> dict[str, object]:
        return {
            "name": name,
            "ok": bool(value),
            "observed_status": observed_status,
            "case_kind": case_kind,
            "projection_priority": 60,
            "projection_source": "structured",
        }

    native_cases: list[dict[str, object]] = []
    for run in evidence_runs:
        run_id = str(run.get("run_id", ""))
        native_cases.append(_native_case(run_id, _run_record_ok(run)))
    for name, report in reports.items():
        native_cases.append(
            _native_case(
                name,
                hasattr(report, "to_dict") and getattr(report, "ok", False) is True,
            )
        )
    native_cases.append(_native_case("canonical_contract_chain", canonical_chain_ok))

    # Re-run the final parent gate against one pure mutation at a time.  These
    # are finite negative oracles over the already-computed evidence and never
    # relaunch a child owner or a test suite.
    base_runs = [dict(run) for run in evidence_runs]
    base_children = dict(child_results)
    base_reports = dict(reports)
    for run_id in (
        "focused-ui-core",
        "ui-templates",
        "contract-matrix",
        "ui-flow-structure-model",
        "real-surface-model",
        "behavior-ledger-model",
        "field-lifecycle-model",
    ):
        native_cases.append(
            _native_case(
                f"missing:{run_id}",
                not _gate(
                    [run for run in base_runs if run.get("run_id") != run_id],
                    base_children,
                    base_reports,
                    canonical_chain_ok,
                ),
                observed_status="violation",
                case_kind="bad",
            )
        )
        for status in ("failed", "stale", "not_run"):
            mutated_runs = [dict(run) for run in base_runs]
            for run in mutated_runs:
                if run.get("run_id") == run_id:
                    run["ok"] = False
                    run["status"] = status
                    break
            native_cases.append(
                _native_case(
                    f"{status}:{run_id}",
                    not _gate(mutated_runs, base_children, base_reports, canonical_chain_ok),
                    observed_status="violation",
                    case_kind="bad",
                )
            )
    for report_name in (
        "contract_exhaustion",
        "model_test_alignment",
        "test_mesh",
        "risk_evidence_ledger",
    ):
        missing_reports = dict(base_reports)
        missing_reports.pop(report_name, None)
        native_cases.append(
            _native_case(
                f"report_missing:{report_name}",
                not _gate(base_runs, base_children, missing_reports, canonical_chain_ok),
                observed_status="violation",
                case_kind="bad",
            )
        )
        forged_reports = dict(base_reports)
        forged_reports[report_name] = {"ok": True}
        native_cases.append(
            _native_case(
                f"forged_report:{report_name}",
                not _gate(base_runs, base_children, forged_reports, canonical_chain_ok),
                observed_status="violation",
                case_kind="bad",
            )
        )
    native_cases.append(
        _native_case(
            "canonical_chain_false",
            not _gate(base_runs, base_children, base_reports, False),
            observed_status="violation",
            case_kind="bad",
        )
    )
    forged_children = dict(base_children)
    forged_children["ui_flow_structure"] = _child_payload_valid(
        {"ok": True}, model.UI_MODEL_RESULT
    )
    native_cases.append(
        _native_case(
            "forged_green_child",
            not _gate(base_runs, forged_children, base_reports, canonical_chain_ok),
            observed_status="violation",
            case_kind="bad",
        )
    )
    payload = {
        "ok": ok,
        "evidence_generation_ok": evidence_ok,
        "canonical_contract_chain_ok": canonical_chain_ok,
        "evidence_runs": evidence_runs,
        "child_results": child_results,
        "reports": {name: report.to_dict() for name, report in reports.items()},
        "native_cases": native_cases,
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== FlowGuard UI content admission closure ===")
    print("status:", "OK" if ok else "FAILED")
    print("evidence_generation:", "OK" if evidence_ok else "FAILED")
    print("canonical_contract_chain:", "OK" if canonical_chain_ok else "FAILED")
    for run in evidence_runs:
        print(f"- run {run['run_id']}: {'OK' if run['ok'] else 'FAILED'}")
    for name, report in reports.items():
        print(f"- {name}: {report.decision} ({'OK' if report.ok else 'FAILED'})")
        if not report.ok:
            print(report.format_text())
    return 0 if ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:harden_ui_content_visibility_validation", main))
