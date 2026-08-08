import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".flowguard" / "validation_evidence_gates"
RUNNER = MODEL_DIR / "run_checks.py"
RESULT_SCHEMA_V2 = "flowguard.validation-evidence-kernel-model-result.v2"
MAX_COMPACT_RESULT_BYTES = 256 * 1024
FORBIDDEN_RAW_TRACE_KEYS = {
    "counterexample_trace",
    "final_state",
    "model_report",
    "scenario_run",
    "steps",
    "traces",
}
PREEXISTING_SCENARIO_NAMES = (
    "terminal_current_exact_proof_passes",
    "progress_only_is_rejected",
    "known_bad_progress_only_acceptance_is_detected",
    "stale_is_rejected",
    "known_bad_stale_acceptance_is_detected",
    "failed_is_rejected",
    "known_bad_failed_acceptance_is_detected",
    "skipped_is_rejected",
    "known_bad_skipped_acceptance_is_detected",
    "not_run_is_rejected",
    "known_bad_not_run_acceptance_is_detected",
    "persistent_observation_authority_is_rejected",
    "known_bad_persistent_observation_authority_acceptance_is_detected",
    "missing_final_freshness_is_rejected",
    "known_bad_missing_final_freshness_acceptance_is_detected",
    "repeated_semantic_verification_is_rejected",
    "known_bad_repeated_semantic_verification_acceptance_is_detected",
    "per_leaf_source_current_rebuild_is_rejected",
    "known_bad_per_leaf_source_current_rebuild_acceptance_is_detected",
    "per_leaf_receipt_store_scan_is_rejected",
    "known_bad_per_leaf_receipt_store_scan_acceptance_is_detected",
    "missing_receipt_reconciliation_is_rejected",
    "known_bad_missing_receipt_reconciliation_acceptance_is_detected",
    "known_bad_hidden_failed_child_is_detected",
    "known_bad_hidden_skipped_child_is_detected",
    "known_bad_hidden_not_run_child_is_detected",
    "known_bad_duplicate_owner_is_detected",
    "known_bad_foreign_owner_is_detected",
    "known_bad_subject_fingerprint_drift_is_detected",
    "known_bad_source_inputs_fingerprint_drift_is_detected",
    "known_bad_spec_inputs_fingerprint_drift_is_detected",
    "known_bad_test_inputs_fingerprint_drift_is_detected",
    "known_bad_check_manifest_fingerprint_drift_is_detected",
    "known_bad_toolchain_fingerprint_drift_is_detected",
    "known_bad_environment_fingerprint_drift_is_detected",
    "known_bad_validation_head_fingerprint_drift_is_detected",
    "known_bad_proof_fingerprint_mismatch_is_detected",
    "known_bad_result_fingerprint_mismatch_is_detected",
    "known_bad_missing_real_input_is_detected",
    "known_bad_broad_claim_is_detected",
    "later_source_change_revokes_prior_claim",
    "explicit_recoverable_quarantine_is_delegated",
    "ordinary_automatic_purge_is_blocked",
    "known_bad_automatic_purge_is_detected",
)
NEW_COMPACT_SCENARIO_NAME = "known_bad_repeated_inline_raw_traces_are_detected"


def _recompute_scenario_evidence():
    model_name = "model"
    runner_name = "_flowguard_validation_evidence_gate_runner_test"
    prior_model = sys.modules.get("model")
    try:
        model_spec = importlib.util.spec_from_file_location(
            model_name,
            MODEL_DIR / "model.py",
        )
        assert model_spec is not None and model_spec.loader is not None
        model_module = importlib.util.module_from_spec(model_spec)
        sys.modules[model_name] = model_module
        model_spec.loader.exec_module(model_module)

        runner_spec = importlib.util.spec_from_file_location(runner_name, RUNNER)
        assert runner_spec is not None and runner_spec.loader is not None
        runner_module = importlib.util.module_from_spec(runner_spec)
        sys.modules[runner_name] = runner_module
        runner_spec.loader.exec_module(runner_module)

        identity, _ = runner_module.build_current_identity(ROOT)
        raw_report = model_module.run_review(identity)
        return {
            row.scenario_name: {
                "raw_scenario_result_fingerprint": runner_module._fingerprint(
                    row.to_dict()
                ),
                "counterexample_trace_fingerprint": (
                    runner_module._fingerprint(row.counterexample_trace.to_dict())
                    if row.counterexample_trace is not None
                    else None
                ),
                "observed_violation_names": list(
                    row.scenario_run.observed_violation_names
                ),
            }
            for row in raw_report.results
        }
    finally:
        if prior_model is None:
            sys.modules.pop("model", None)
        else:
            sys.modules["model"] = prior_model
        sys.modules.pop(runner_name, None)


def _all_mapping_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_mapping_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_mapping_keys(child)


def test_runner_emits_complete_compact_v2_scenario_evidence(tmp_path):
    env = os.environ.copy()
    env["FLOWGUARD_OUTPUT_DIR"] = str(tmp_path)
    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    result_path = tmp_path / "result.json"
    result_bytes = result_path.read_bytes()
    payload = json.loads(result_bytes)
    review = payload["scenario_review"]
    results = review["results"]

    assert payload["schema_version"] == RESULT_SCHEMA_V2
    assert payload["ok"] is True
    assert review["ok"] is True
    assert len(PREEXISTING_SCENARIO_NAMES) == 44
    assert review["total_scenarios"] == 45
    assert tuple(row["scenario_name"] for row in results) == (
        *PREEXISTING_SCENARIO_NAMES,
        NEW_COMPACT_SCENARIO_NAME,
    )
    assert len({row["scenario_name"] for row in results}) == 45
    assert "known_limitations" in review
    assert len(result_bytes) < MAX_COMPACT_RESULT_BYTES
    assert not (set(_all_mapping_keys(payload)) & FORBIDDEN_RAW_TRACE_KEYS)

    recomputed = _recompute_scenario_evidence()

    for row in results:
        expected = recomputed[row["scenario_name"]]
        assert row["raw_scenario_result_fingerprint"] == expected[
            "raw_scenario_result_fingerprint"
        ]
        assert row["counterexample_trace_fingerprint"] == expected[
            "counterexample_trace_fingerprint"
        ]
        assert row["observed_violation_names"] == expected[
            "observed_violation_names"
        ]
        assert set(row) == {
            "scenario_name",
            "status",
            "ok",
            "status_explanation",
            "expected_summary",
            "observed_summary",
            "evidence",
            "observed_violation_names",
            "raw_scenario_result_fingerprint",
            "counterexample_trace_fingerprint",
        }
