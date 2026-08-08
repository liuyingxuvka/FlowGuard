"""Run the permanent validation-evidence-kernel model against current inputs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import flowguard

from model import (
    CLAIM_BOUNDARY,
    COMPACT_RESULT_SCHEMA_VERSION,
    MODEL_ID,
    SOURCE_INPUT_PATHS,
    SPEC_INPUT_PATHS,
    SPECIALIST_DELEGATIONS,
    TEST_INPUT_PATHS,
    ValidationIdentity,
    run_review,
)


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _input_set(root: Path, paths: tuple[str, ...]) -> tuple[str, tuple[dict[str, Any], ...]]:
    rows: list[dict[str, Any]] = []
    resolved_root = root.resolve()
    for relative in paths:
        path = (resolved_root / relative).resolve()
        if resolved_root not in path.parents:
            raise ValueError(f"governed input escapes repository: {relative}")
        data = path.read_bytes()
        rows.append(
            {
                "path": relative,
                "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    canonical = tuple(rows)
    return _fingerprint(canonical), canonical


def build_current_identity(root: Path) -> tuple[ValidationIdentity, dict[str, Any]]:
    source_fingerprint, source_rows = _input_set(root, SOURCE_INPUT_PATHS)
    spec_fingerprint, spec_rows = _input_set(root, SPEC_INPUT_PATHS)
    test_fingerprint, test_rows = _input_set(root, TEST_INPUT_PATHS)
    check_manifest_fingerprint = _fingerprint(
        {
            "model_id": MODEL_ID,
            "source_paths": SOURCE_INPUT_PATHS,
            "spec_paths": SPEC_INPUT_PATHS,
            "test_paths": TEST_INPUT_PATHS,
        }
    )
    toolchain_fingerprint = _fingerprint(
        {
            "python_implementation": sys.implementation.name,
            "python_version": platform.python_version(),
            "flowguard_schema_version": flowguard.SCHEMA_VERSION,
        }
    )
    environment_fingerprint = _fingerprint(
        {
            "os_name": os.name,
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "python_platform": sys.platform,
        }
    )
    subject_fingerprint = _fingerprint(
        {
            "source": source_fingerprint,
            "spec": spec_fingerprint,
            "test": test_fingerprint,
            "check_manifest": check_manifest_fingerprint,
        }
    )
    validation_head_fingerprint = _fingerprint(
        {
            "subject": subject_fingerprint,
            "toolchain": toolchain_fingerprint,
            "environment": environment_fingerprint,
        }
    )
    identity = ValidationIdentity(
        subject_id="flowguard:validation-evidence-kernel",
        subject_fingerprint=subject_fingerprint,
        source_inputs_fingerprint=source_fingerprint,
        spec_inputs_fingerprint=spec_fingerprint,
        test_inputs_fingerprint=test_fingerprint,
        check_manifest_fingerprint=check_manifest_fingerprint,
        toolchain_fingerprint=toolchain_fingerprint,
        environment_fingerprint=environment_fingerprint,
        validation_head_fingerprint=validation_head_fingerprint,
    )
    inputs = {
        "source": {"fingerprint": source_fingerprint, "items": source_rows},
        "spec": {"fingerprint": spec_fingerprint, "items": spec_rows},
        "test": {"fingerprint": test_fingerprint, "items": test_rows},
        "check_manifest_fingerprint": check_manifest_fingerprint,
        "toolchain_fingerprint": toolchain_fingerprint,
        "environment_fingerprint": environment_fingerprint,
        "validation_head_fingerprint": validation_head_fingerprint,
    }
    return identity, inputs


def _compact_scenario_result(result: Any) -> dict[str, Any]:
    """Project one fully reviewed scenario without persisting its raw trace tree."""

    raw_result = result.to_dict()
    scenario_run = result.scenario_run
    counterexample = result.counterexample_trace
    return {
        "scenario_name": result.scenario_name,
        "status": result.status,
        "ok": result.ok,
        "status_explanation": result.status_explanation,
        "expected_summary": result.expected_summary,
        "observed_summary": result.observed_summary,
        "evidence": list(result.evidence),
        "observed_violation_names": (
            list(scenario_run.observed_violation_names)
            if scenario_run is not None
            else []
        ),
        "raw_scenario_result_fingerprint": _fingerprint(raw_result),
        "counterexample_trace_fingerprint": (
            _fingerprint(counterexample.to_dict())
            if counterexample is not None
            else None
        ),
    }


def _compact_scenario_review(report: Any) -> dict[str, Any]:
    return {
        "ok": report.ok,
        "total_scenarios": report.total_scenarios,
        "passed": report.passed,
        "expected_violations_observed": report.expected_violations_observed,
        "unexpected_violations": report.unexpected_violations,
        "missing_expected_violations": report.missing_expected_violations,
        "needs_human_review": report.needs_human_review,
        "known_limitations": report.known_limitations,
        "oracle_mismatches": report.oracle_mismatches,
        "results": [_compact_scenario_result(result) for result in report.results],
    }


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    identity, governed_inputs = build_current_identity(repository_root)
    report = run_review(identity)
    payload = {
        "schema_version": COMPACT_RESULT_SCHEMA_VERSION,
        "model_id": MODEL_ID,
        "ok": report.ok,
        "governed_inputs": governed_inputs,
        "specialist_delegations": list(SPECIALIST_DELEGATIONS),
        "claim_boundary": CLAIM_BOUNDARY,
        "scenario_review": _compact_scenario_review(report),
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    result_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    result_bytes = result_text.encode("utf-8")
    output_dir.joinpath("result.json").write_bytes(result_bytes)
    result_fingerprint = "sha256:" + hashlib.sha256(result_bytes).hexdigest()

    print("=== flowguard validation evidence kernel ===")
    print("status:", "OK" if report.ok else "FAILED")
    print("scenarios:", report.total_scenarios)
    print("ordinary passes:", report.passed)
    print("known-bad violations observed:", report.expected_violations_observed)
    print("unexpected violations:", report.unexpected_violations)
    print("missing expected violations:", report.missing_expected_violations)
    print("oracle mismatches:", report.oracle_mismatches)
    print("result artifact: result.json")
    print("result fingerprint:", result_fingerprint)
    if not report.ok:
        failures = tuple(result for result in report.results if result.ok is not True)
        print("non-pass scenarios:", ",".join(result.scenario_name for result in failures[:5]))
        if len(failures) > 5:
            print("additional non-pass scenarios:", len(failures) - 5)
    print("claim boundary:", CLAIM_BOUNDARY)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
