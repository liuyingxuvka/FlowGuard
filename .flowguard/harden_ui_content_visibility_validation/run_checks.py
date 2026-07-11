"""Run current-evidence closure checks for ordinary UI content admission."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import model
from flowguard import (
    review_model_test_alignment,
    review_risk_evidence_ledger,
    review_test_mesh,
)


def _run(
    run_id: str,
    args: tuple[str, ...],
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
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
    return {
        "run_id": run_id,
        "command": [sys.executable, *args],
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
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
    return payload.get("ok") is True


def main() -> int:
    model.EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    evidence_runs = [
        _run("focused-ui-core", model.CORE_PYTEST_ARGS),
        _run("ui-templates", model.TEMPLATE_PYTEST_ARGS),
        _run("contract-matrix", model.MATRIX_PYTEST_ARGS),
        _run(
            "ui-flow-structure-model",
            (".flowguard/ui_flow_structure_skill/run_checks.py",),
            output_dir=model.UI_MODEL_RESULT.parent,
        ),
        _run(
            "real-surface-model",
            (".flowguard/harden_ui_real_surface_validation/run_checks.py",),
            output_dir=model.REAL_SURFACE_RESULT.parent,
        ),
        _run(
            "behavior-ledger-model",
            (".flowguard/behavior_commitment_ledger/run_checks.py",),
            output_dir=model.BEHAVIOR_LEDGER_RESULT.parent,
        ),
        _run(
            "field-lifecycle-model",
            (".flowguard/default_replacement_field_lifecycle/run_checks.py",),
            output_dir=model.FIELD_LIFECYCLE_RESULT.parent,
        ),
    ]
    child_results = {
        "ui_flow_structure": _child_payload_ok(model.UI_MODEL_RESULT),
        "real_surface": _child_payload_ok(model.REAL_SURFACE_RESULT),
        "behavior_ledger": _child_payload_ok(model.BEHAVIOR_LEDGER_RESULT),
        "field_lifecycle": _child_payload_ok(model.FIELD_LIFECYCLE_RESULT),
    }
    evidence_ok = all(bool(run["ok"]) for run in evidence_runs) and all(child_results.values())

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

    ok = evidence_ok and canonical_chain_ok and all(report.ok for report in reports.values())
    payload = {
        "ok": ok,
        "evidence_generation_ok": evidence_ok,
        "canonical_contract_chain_ok": canonical_chain_ok,
        "evidence_runs": evidence_runs,
        "child_results": child_results,
        "reports": {name: report.to_dict() for name, report in reports.items()},
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


if __name__ == "__main__":
    raise SystemExit(main())
