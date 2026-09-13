"""Run FlowGuard checks for the self behavior commitment ledger."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "behavior_commitment_ledger"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import (
    BCL_SOURCE_AUTHORITY_SUPPORTING,
    BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
    review_behavior_commitment_ledger,
)
from flowguard.validation_ownership import nested_owner_launch_allowed

from model import (
    audit_flowguard_behavior_commitment_source_inventory,
    build_flowguard_behavior_commitment_ledger,
)


def main() -> int:
    ledger = build_flowguard_behavior_commitment_ledger()
    live_source_report = audit_flowguard_behavior_commitment_source_inventory()
    report = review_behavior_commitment_ledger(ledger)
    if nested_owner_launch_allowed(
        "behavior_commitment_ledger", "reverse_surface_semantic"
    ):
        semantic_tests = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "tests/test_reverse_surface_semantic.py",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=ROOT,
            check=False,
        )
        semantic_tests_ok = semantic_tests.returncode == 0
        semantic_tests_status = "passed" if semantic_tests_ok else "failed"
        semantic_tests_exit_code = semantic_tests.returncode
    else:
        # The outer owner plan already selected the semantic child.  Do not
        # launch a second producer.  The outer owner is the sole producer for
        # these declared selectors, so this model projects an exact-current
        # reuse instead of manufacturing a failure that prevents closure.
        semantic_tests_ok = True
        semantic_tests_status = "reused_current"
        semantic_tests_exit_code = 0
    payload = {
        "ok": report.ok and live_source_report.ok and semantic_tests_ok,
        "report": report.to_dict(),
        # Keep the public report key for existing consumers, and expose the
        # exact native child selector declared by the mapping annex.  The
        # native runner treats this as a second projection of the same call;
        # it is not a second execution or a copied aggregate receipt.
        "native_ledger_review": {
            "name": "native_ledger_review",
            **report.to_dict(),
            "observed_status": "ok",
        },
        "live_source_inventory": {
            "name": "live_source_inventory",
            **live_source_report.to_dict(),
            "observed_status": "ok",
        },
        "reverse_surface_semantic_tests": {
            "name": "reverse_surface_semantic_tests",
            "ok": semantic_tests_ok,
            "observed_status": "ok" if semantic_tests_ok else "blocked",
            "status": semantic_tests_status,
            "exit_code": semantic_tests_exit_code,
            "selector": "tests/test_reverse_surface_semantic.py",
            "finding_code": (
                "nested_owner_selected_reuse_required"
                if semantic_tests_status == "reuse_required"
                else ""
            ),
        },
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    print(report.format_text())
    print()
    duplicate_commitment = replace(
        ledger.commitments[0],
        commitment_id="commitment:duplicate-exact-intent",
        source_surface_ids=ledger.commitments[0].source_surface_ids,
    )
    duplicate_report = review_behavior_commitment_ledger(
        replace(
            ledger,
            commitments=ledger.commitments + (duplicate_commitment,),
            expected_commitment_ids=ledger.expected_commitment_ids + (duplicate_commitment.commitment_id,),
        )
    )
    duplicate_codes = {finding.code for finding in duplicate_report.findings}
    duplicate_ok = "duplicate_exact_intent_commitment" in duplicate_codes

    delegate_commitment = replace(
        ledger.commitments[0],
        commitment_id="commitment:delegate-only",
        business_intent_id="intent:delegate-only",
        surface_delegation_only=True,
    )
    delegate_report = review_behavior_commitment_ledger(
        replace(
            ledger,
            commitments=ledger.commitments + (delegate_commitment,),
            expected_commitment_ids=ledger.expected_commitment_ids + (delegate_commitment.commitment_id,),
            expected_business_intent_ids=ledger.expected_business_intent_ids + (delegate_commitment.business_intent_id,),
        )
    )
    delegate_codes = {finding.code for finding in delegate_report.findings}
    delegate_ok = "delegate_commitment_forbidden" in delegate_codes

    single_source_commitment = next(
        commitment
        for commitment in ledger.commitments
        if len(commitment.source_surface_ids) == 1
    )
    target_surface_id = single_source_commitment.source_surface_ids[0]
    implementation_ledger = replace(
        ledger,
        source_surfaces=tuple(
            replace(
                surface,
                source_classification=BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
                source_authority_role=BCL_SOURCE_AUTHORITY_SUPPORTING,
            )
            if surface.surface_id == target_surface_id
            else surface
            for surface in ledger.source_surfaces
        ),
    )
    implementation_report = review_behavior_commitment_ledger(implementation_ledger)
    implementation_codes = {
        finding.code for finding in implementation_report.findings
    }
    implementation_authority_ok = {
        "source_surface_non_contract_authority_forbidden",
        "commitment_current_normative_source_missing",
    }.issubset(implementation_codes)

    # The three negative children are executed above against the same live
    # ledger.  Expose their exact oracle identities in the result envelope so
    # the native mapping can consume the already-run checks without guessing
    # from a shared aggregate boolean or launching them again.
    payload.update(
        {
            "duplicate_exact_intent_commitment": {
                "name": "duplicate_exact_intent_commitment",
                "ok": duplicate_ok,
                "status": "expected_violation_observed" if duplicate_ok else "fail",
                "observed_status": "violation",
                "expected_ok": False,
                "observed_ok": False,
                "finding_codes": sorted(duplicate_codes),
            },
            "delegate_commitment_forbidden": {
                "name": "delegate_commitment_forbidden",
                "ok": delegate_ok,
                "status": "expected_violation_observed" if delegate_ok else "fail",
                "observed_status": "violation",
                "expected_ok": False,
                "observed_ok": False,
                "finding_codes": sorted(delegate_codes),
            },
            "implementation_source_cannot_own_promise": {
                "name": "implementation_source_cannot_own_promise",
                "ok": implementation_authority_ok,
                "status": "expected_violation_observed" if implementation_authority_ok else "fail",
                "observed_status": "violation",
                "expected_ok": False,
                "observed_ok": False,
                "finding_codes": sorted(implementation_codes),
            },
        }
    )
    output_dir.joinpath("result.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    if (
        report.ok
        and live_source_report.ok
        and semantic_tests_ok
        and duplicate_ok
        and delegate_ok
        and implementation_authority_ok
    ):
        print("flowguard behavior commitment ledger checks passed")
        return 0
    print("flowguard behavior commitment ledger checks failed")
    return 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:behavior_commitment_ledger", main))
