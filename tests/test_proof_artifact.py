import unittest

import flowguard
from flowguard import (
    LEGACY_PATH_DELEGATED,
    LEGACY_PATH_KIND_FIELD,
    LEGACY_PATH_UNKNOWN,
    PROOF_ARTIFACT_SCOPE_INTERNAL_PATH,
    PROOF_ARTIFACT_STATUS_FAILED,
    PROOF_ARTIFACT_STATUS_PASSED,
    LegacyPathDisposition,
    ProofArtifactRef,
    legacy_path_disposition_from_field_row,
    proof_artifact_gap_codes,
    review_legacy_path_dispositions,
)


def artifact(**kwargs):
    defaults = {
        "artifact_id": "proof:unit",
        "producer_route": "test_proof_artifact",
        "command": "python -m pytest tests/test_proof_artifact.py -q",
        "result_status": PROOF_ARTIFACT_STATUS_PASSED,
        "exit_code": 0,
        "result_path": "tmp/unit.json",
        "started_at": "2026-08-02T00:00:00+00:00",
        "finished_at": "2026-08-02T00:00:01+00:00",
        "subject_id": "subject:unit",
        "subject_fingerprint": "sha256:subject-unit",
        "artifact_fingerprints": {"tmp/unit.json": "sha256:unit"},
        "covered_obligation_ids": ("model:r1",),
    }
    defaults.update(kwargs)
    return ProofArtifactRef(**defaults)


class ProofArtifactTests(unittest.TestCase):
    def test_required_obligations_use_all_coverage_not_any_coverage(self):
        proof = artifact(covered_obligation_ids=("one",))

        codes = {
            code
            for code, _ in proof_artifact_gap_codes(
                proof,
                required_obligation_ids=("one", "two"),
            )
        }

        self.assertIn("proof_artifact_missing_obligation", codes)

    def test_current_passing_artifact_has_no_gaps(self):
        self.assertEqual(
            (),
            proof_artifact_gap_codes(
                artifact(),
                declared_status=PROOF_ARTIFACT_STATUS_PASSED,
                required_obligation_ids=("model:r1",),
                require_result_path=True,
                require_fingerprints=True,
                require_external_scope=True,
            ),
        )

    def test_missing_artifact_blocks_strict_evidence(self):
        self.assertEqual(
            ("missing_proof_artifact",),
            tuple(code for code, _ in proof_artifact_gap_codes(None)),
        )

    def test_declared_pass_does_not_override_failed_artifact(self):
        codes = tuple(
            code
            for code, _ in proof_artifact_gap_codes(
                artifact(result_status=PROOF_ARTIFACT_STATUS_FAILED, exit_code=1),
                declared_status=PROOF_ARTIFACT_STATUS_PASSED,
            )
        )

        self.assertIn("proof_artifact_status_mismatch", codes)
        self.assertIn("proof_artifact_not_passing", codes)
        self.assertIn("proof_artifact_nonzero_exit", codes)

    def test_internal_artifact_cannot_prove_external_scope(self):
        codes = tuple(
            code
            for code, _ in proof_artifact_gap_codes(
                artifact(assertion_scope=PROOF_ARTIFACT_SCOPE_INTERNAL_PATH),
                require_external_scope=True,
            )
        )

        self.assertIn("proof_artifact_internal_path_only", codes)

    def test_missing_fingerprint_blocks_strict_evidence(self):
        codes = tuple(
            code
            for code, _ in proof_artifact_gap_codes(
                artifact(artifact_fingerprints={}),
                require_result_path=True,
                require_fingerprints=True,
            )
        )

        self.assertIn("proof_artifact_missing_fingerprint", codes)

    def test_caller_declared_pass_without_verifiable_material_is_not_current(self):
        weak = ProofArtifactRef(
            "proof:weak",
            result_status=PROOF_ARTIFACT_STATUS_PASSED,
            exit_code=0,
            current=True,
        )

        self.assertFalse(weak.has_current_pass())
        codes = {
            code
            for code, _ in proof_artifact_gap_codes(
                weak,
                require_verifiable_material=True,
            )
        }
        self.assertIn("proof_artifact_missing_command", codes)
        self.assertIn("proof_artifact_missing_result_path", codes)
        self.assertIn("proof_artifact_missing_finished_at", codes)
        self.assertIn("proof_artifact_missing_subject", codes)
        self.assertIn("proof_artifact_missing_fingerprint", codes)
        self.assertNotIn("proof_artifact_missing_exit_code", codes)

    def test_malformed_timestamp_or_fingerprint_is_not_current(self):
        weak = artifact(
            finished_at="not-a-time",
            subject_fingerprint="caller-says-current",
        )

        self.assertFalse(weak.has_current_pass())
        codes = {
            code
            for code, _ in proof_artifact_gap_codes(
                weak,
                require_verifiable_material=True,
            )
        }
        self.assertIn("proof_artifact_invalid_finished_at", codes)
        self.assertIn("proof_artifact_invalid_subject_fingerprint", codes)

    def test_missing_terminal_exit_code_is_not_current(self):
        weak = artifact(exit_code=None)

        self.assertFalse(weak.has_current_pass())
        self.assertIn(
            "proof_artifact_missing_exit_code",
            {
                code
                for code, _ in proof_artifact_gap_codes(
                    weak,
                    require_verifiable_material=True,
                )
            },
        )

    def test_legacy_path_unknown_blocks(self):
        report = review_legacy_path_dispositions(
            (LegacyPathDisposition("old-route", disposition=LEGACY_PATH_UNKNOWN),)
        )

        self.assertFalse(report.ok)
        self.assertEqual("legacy_path_disposition_unknown", report.findings[0].code)

    def test_field_row_can_be_reviewed_as_legacy_path_disposition(self):
        row = flowguard.FieldLifecycleRow(
            "field:old_mode",
            lifecycle=flowguard.FIELD_LIFECYCLE_REPLACED,
            replacement_field_id="field:mode",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            disposition_evidence_refs=("test_old_mode_migrates",),
        )

        disposition = legacy_path_disposition_from_field_row(row)
        report = review_legacy_path_dispositions((disposition,))

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(LEGACY_PATH_KIND_FIELD, disposition.path_kind)
        self.assertEqual("field:old_mode", disposition.field_id)

    def test_unknown_field_disposition_blocks_legacy_path_review(self):
        row = flowguard.FieldLifecycleRow(
            "field:old_mode",
            lifecycle=flowguard.FIELD_LIFECYCLE_REPLACED,
            replacement_field_id="field:mode",
            disposition=flowguard.FIELD_DISPOSITION_UNKNOWN,
        )

        report = review_legacy_path_dispositions((legacy_path_disposition_from_field_row(row),))

        self.assertFalse(report.ok)
        self.assertIn("legacy_path_disposition_unknown", [finding.code for finding in report.findings])

    def test_legacy_path_delegation_requires_artifact_in_strict_mode(self):
        blocked = review_legacy_path_dispositions(
            (
                LegacyPathDisposition(
                    "old-route",
                    disposition=LEGACY_PATH_DELEGATED,
                    repaired_contract_id="model:r1",
                ),
            ),
            require_proof_artifacts=True,
        )
        passed = review_legacy_path_dispositions(
            (
                LegacyPathDisposition(
                    "old-route",
                    disposition=LEGACY_PATH_DELEGATED,
                    repaired_contract_id="model:r1",
                    proof_artifact=artifact(),
                ),
            ),
            require_proof_artifacts=True,
        )

        self.assertFalse(blocked.ok)
        self.assertIn("legacy_path_missing_proof_artifact", [finding.code for finding in blocked.findings])
        self.assertTrue(passed.ok, passed.to_dict())


if __name__ == "__main__":
    unittest.main()
