"""Run FlowGuard checks for Primary Path Authority."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import review_primary_path_authority  # noqa: E402

from model import (  # noqa: E402
    broken_a_failed_b_success,
    broken_manual_recovery_auto_invoked,
    broken_missing_candidate_inventory,
    broken_old_field_fallback,
    broken_stale_material_evidence,
    broken_two_paths_same_exact_intent,
    complete_plan,
)


def finding_codes(report):
    return {finding.code for finding in report.findings}


def require_codes(report, *codes):
    missing = set(codes) - finding_codes(report)
    if missing:
        raise AssertionError(f"missing {sorted(missing)}\n{report.format_text()}")


def main() -> int:
    good = review_primary_path_authority(complete_plan())
    print(good.format_text())
    if not good.ok:
        raise AssertionError("complete primary path authority plan failed")

    bad = review_primary_path_authority(broken_a_failed_b_success())
    require_codes(bad, "primary_failure_masked_by_fallback_success")

    bad_field = review_primary_path_authority(broken_old_field_fallback())
    require_codes(bad_field, "fallback_candidate_unknown_disposition", "old_field_or_backup_cache_masks_primary_failure")

    bad_manual = review_primary_path_authority(broken_manual_recovery_auto_invoked())
    require_codes(bad_manual, "manual_recovery_auto_invoked")

    bad_duplicate = review_primary_path_authority(broken_two_paths_same_exact_intent())
    require_codes(bad_duplicate, "duplicate_primary_runtime_authority")

    bad_inventory = review_primary_path_authority(broken_missing_candidate_inventory())
    require_codes(bad_inventory, "expected_primary_path_candidate_missing", "expected_primary_path_surface_missing")

    bad_evidence = review_primary_path_authority(broken_stale_material_evidence())
    require_codes(bad_evidence, "primary_path_runtime_evidence_not_current")

    print("Primary Path Authority self-model checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
