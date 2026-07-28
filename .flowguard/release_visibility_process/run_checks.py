"""Run the local v0.18.4 DevelopmentProcessFlow checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    release, broken = run_checks()
    print(release.format_text(max_findings=8))
    print()
    print(broken.format_text(max_findings=8))
    release_finding_codes = {finding.code for finding in release.findings}
    broken_finding_codes = {finding.code for finding in broken.findings}
    release_parent_gate_ok = (
        not release.ok
        and release_finding_codes == {"full_validation_parent_not_unique"}
    )
    stale_release_rejected = (
        not broken.ok
        and "stale_evidence_after_artifact_change" in broken_finding_codes
        and "full_validation_parent_not_unique" in broken_finding_codes
    )
    return 0 if release_parent_gate_ok and stale_release_rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
