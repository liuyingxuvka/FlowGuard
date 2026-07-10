import unittest

from flowguard.evidence_receipts import proof_artifact_binding_findings


def codes(value, **kwargs):
    return {item.code for item in proof_artifact_binding_findings(value, **kwargs)}


class ProofArtifactBindingTests(unittest.TestCase):
    def test_zero_exit_pass_without_obligations_is_diagnostic_not_proof(self):
        unbound_green = {
            "result_status": "pass",
            "exit_code": 0,
            "command": ["python", "-m", "pytest"],
            "working_directory_token": "<WORKSPACE>",
            "producer_id": "flowguard.pytest",
            "producer_version": "0.54.0",
            "environment_fingerprint": "sha256:environment",
            "contract_hash": "sha256:contract",
            "check_manifest_hash": "sha256:checks",
            "suite_map_hash": "sha256:suite",
            "input_snapshots": [
                {
                    "artifact_id": "source",
                    "hash_policy": "raw",
                    "raw_sha256": "sha256:source",
                }
            ],
            "proof_artifact_id": "proof:pytest",
            "proof_artifact_fingerprint": "sha256:proof",
            "result_fingerprint": "sha256:result",
            "covered_obligations": [],
        }

        finding_codes = codes(unbound_green)

        self.assertIn("proof_artifact_missing_obligation_coverage", finding_codes)
        self.assertIn("unbound_green_result", finding_codes)

    def test_missing_hash_bindings_keep_green_result_unbound(self):
        report = {
            "result_status": "pass",
            "exit_code": 0,
            "command": ["python", "check.py"],
            "working_directory_token": "<WORKSPACE>",
            "producer_id": "flowguard.check",
            "producer_version": "0.54.0",
            "covered_obligations": ["req.receipt"],
        }

        finding_codes = codes(report)

        self.assertIn("proof_artifact_missing_binding", finding_codes)
        self.assertIn("unbound_green_result", finding_codes)

    def test_aggregate_green_cannot_infer_a_missing_required_obligation(self):
        bound = {
            "result_status": "pass",
            "exit_code": 0,
            "command": ["python", "check.py"],
            "working_directory_token": "<WORKSPACE>",
            "producer_id": "flowguard.check",
            "producer_version": "0.54.0",
            "environment_fingerprint": "sha256:environment",
            "contract_hash": "sha256:contract",
            "check_manifest_hash": "sha256:checks",
            "suite_map_hash": "sha256:suite",
            "input_snapshots": [
                {
                    "artifact_id": "source",
                    "hash_policy": "raw",
                    "raw_sha256": "sha256:source",
                }
            ],
            "proof_artifact_id": "proof:check",
            "proof_artifact_fingerprint": "sha256:proof",
            "result_fingerprint": "sha256:result",
            "covered_obligations": ["req.one"],
        }

        finding_codes = codes(bound, required_obligation_ids=("req.one", "req.two"))

        self.assertIn("proof_artifact_missing_required_obligation", finding_codes)
        self.assertIn("unbound_green_result", finding_codes)

    def test_fully_bound_artifact_has_no_binding_findings(self):
        bound = {
            "result_status": "pass",
            "exit_code": 0,
            "command": ["python", "check.py"],
            "working_directory_token": "<WORKSPACE>",
            "producer_id": "flowguard.check",
            "producer_version": "0.54.0",
            "environment_fingerprint": "sha256:environment",
            "contract_hash": "sha256:contract",
            "check_manifest_hash": "sha256:checks",
            "suite_map_hash": "sha256:suite",
            "input_snapshots": [
                {
                    "artifact_id": "source",
                    "hash_policy": "raw",
                    "raw_sha256": "sha256:source",
                }
            ],
            "proof_artifact_id": "proof:check",
            "proof_artifact_fingerprint": "sha256:proof",
            "result_fingerprint": "sha256:result",
            "covered_obligations": ["req.one"],
        }

        self.assertEqual(set(), codes(bound, required_obligation_ids=("req.one",)))


if __name__ == "__main__":
    unittest.main()
