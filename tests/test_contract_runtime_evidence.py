import tempfile
import json
import unittest
from pathlib import Path

from flowguard import (
    CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    ContractAxis,
    ContractCoverageUniverse,
    ContractExhaustionPlan,
    ContractInteractionGroup,
    ContractRuntimeEvidenceError,
    ContractRuntimeResult,
    load_contract_runtime_evidence,
    reconcile_contract_exhaustion_execution,
    review_contract_exhaustion,
    serialize_contract_runtime_evidence,
    sha256_fingerprint,
    write_contract_runtime_evidence,
)


class ContractRuntimeEvidenceTests(unittest.TestCase):
    def _report(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "contract-runtime",
                model_id="packet-router",
                axes=(
                    ContractAxis("packet_status", values=("missing", "wrong_type")),
                    ContractAxis("evidence_path", values=("missing_file", "old_dir")),
                ),
                interaction_groups=(
                    ContractInteractionGroup(
                        "packet-evidence",
                        axis_ids=("packet_status", "evidence_path"),
                        oracle_status=CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
                    ),
                ),
                require_model_coverage_receipt=True,
                coverage_universe=ContractCoverageUniverse(
                    "packet-runtime-universe",
                    required_axis_ids=("packet_status", "evidence_path"),
                    required_interaction_group_ids=("packet-evidence",),
                ),
            )
        )
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(4, len(report.generated_cases))
        return report

    @staticmethod
    def _passed():
        return ContractRuntimeResult(
            "passed",
            result_fingerprint="sha256:" + "1" * 64,
            observed_status=CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
        )

    def test_case_inventory_reconciles_executed_reused_and_not_run(self):
        report = self._report()
        case_ids = tuple(case.case_id for case in report.generated_cases)
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-1",
            result_rows={
                case_ids[0]: self._passed(),
                case_ids[1]: ContractRuntimeResult(
                    "skipped",
                    reason="platform fixture is unavailable",
                    result_fingerprint="sha256:" + "2" * 64,
                ),
            },
            reused_rows={case_ids[2]: ContractRuntimeResult(
                "passed",
                result_fingerprint="sha256:" + "3" * 64,
                producer_receipt_id="receipt:producer-case-2",
            )},
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
        )

        self.assertEqual(
            {
                "planned_count": 4,
                "selected_count": 4,
                "explicitly_not_selected_count": 0,
                "executed_count": 2,
                "reused_count": 1,
                "not_run_count": 1,
                "passed_count": 2,
                "failed_count": 0,
                "skipped_count": 1,
                "xfailed_count": 0,
                "xpassed_count": 0,
            },
            evidence.counts,
        )
        self.assertFalse(evidence.ok)
        self.assertEqual(
            "not_run",
            next(item for item in evidence.cases if item.case_id == case_ids[3]).outcome,
        )
        self.assertIn("contract_case_skipped", {item.code for item in evidence.findings})
        self.assertIn("contract_case_not_run", {item.code for item in evidence.findings})

    def test_explicit_not_selected_required_case_blocks_and_conserves_counts(self):
        report = self._report()
        first = report.generated_cases[0].case_id
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-2",
            requested_case_ids=(first,),
            result_rows={
                first: self._passed(),
                report.generated_cases[1].case_id: self._passed(),
            },
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py", "-k", first),
        )

        self.assertEqual(4, evidence.counts["planned_count"])
        self.assertEqual(1, evidence.counts["selected_count"])
        self.assertEqual(3, evidence.counts["explicitly_not_selected_count"])
        self.assertEqual(3, evidence.counts["not_run_count"])
        self.assertFalse(evidence.ok)
        self.assertEqual(
            3,
            sum(item.code == "required_contract_case_not_selected" for item in evidence.findings),
        )
        self.assertIn(
            "result_for_not_selected_contract_case",
            {item.code for item in evidence.findings},
        )

    def test_parent_count_and_status_mismatch_are_blockers(self):
        report = self._report()
        rows = {
            case.case_id: self._passed()
            for case in report.generated_cases
        }
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-3",
            result_rows=rows,
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
            declared_parent_counts={"planned_count": 4, "skipped_count": 1},
            declared_parent_status="passed",
        )

        self.assertFalse(evidence.ok)
        self.assertIn("parent_case_count_mismatch", {item.code for item in evidence.findings})

    def test_orphan_conflicting_and_oracle_mismatch_rows_are_visible(self):
        report = self._report()
        case_ids = tuple(case.case_id for case in report.generated_cases)
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-4",
            result_rows={
                case_ids[0]: ContractRuntimeResult(
                    "passed",
                    result_fingerprint="sha256:" + "4" * 64,
                ),
                case_ids[1]: ContractRuntimeResult(
                    "passed",
                    result_fingerprint="sha256:" + "5" * 64,
                    observed_status="wrong-oracle-status",
                ),
                "case:not-in-report": self._passed(),
            },
            reused_rows={case_ids[0]: ContractRuntimeResult(
                "passed",
                result_fingerprint="sha256:" + "6" * 64,
                producer_receipt_id="receipt:case-0",
            )},
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
        )

        codes = {item.code for item in evidence.findings}
        self.assertIn("duplicate_contract_result_source", codes)
        self.assertIn("result_contract_case_not_in_inventory", codes)
        self.assertIn("contract_oracle_status_mismatch", codes)
        self.assertIn("contract_case_not_run", codes)

    def test_round_trip_and_fingerprint_are_canonical(self):
        report = self._report()
        rows = {
            case.case_id: self._passed()
            for case in report.generated_cases
        }
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-round-trip",
            result_rows=rows,
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
        )
        self.assertTrue(evidence.ok, evidence.format_text())
        loaded = type(evidence).from_dict(evidence.to_dict())
        self.assertEqual(evidence.fingerprint, loaded.fingerprint)
        self.assertEqual(serialize_contract_runtime_evidence(evidence), serialize_contract_runtime_evidence(loaded))
        with tempfile.TemporaryDirectory() as directory:
            path = write_contract_runtime_evidence(evidence, Path(directory) / "evidence.json")
            self.assertEqual(evidence.fingerprint, load_contract_runtime_evidence(path).fingerprint)

    def test_result_without_observed_artifact_fingerprint_is_rejected(self):
        with self.assertRaises(ContractRuntimeEvidenceError):
            ContractRuntimeResult("passed")

    def test_legacy_receipt_field_aliases_are_rejected(self):
        with self.assertRaises(ContractRuntimeEvidenceError):
            ContractRuntimeResult.from_dict(
                {
                    "outcome": "passed",
                    "result_fingerprint": "sha256:" + "1" * 64,
                    "receipt_id": "receipt:legacy",
                }
            )

        report = self._report()
        case_id = report.generated_cases[0].case_id
        with self.assertRaises(ContractRuntimeEvidenceError):
            reconcile_contract_exhaustion_execution(
                report,
                execution_id="execution-legacy-count-alias",
                result_rows={case_id: self._passed()},
                execution_owner_id="owner:testmesh-contract",
                command=("pytest", "tests/test_packet_router.py"),
                declared_parent_counts={"test_count": 4},
            )

    def test_reused_case_requires_receipt_hash_and_reuse_identity(self):
        report = self._report()
        case_id = report.generated_cases[0].case_id
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-missing-reuse-binding",
            result_rows={
                case.case_id: self._passed()
                for case in report.generated_cases[1:]
            },
            reused_rows={
                case_id: {
                    "outcome": "passed",
                    "result_fingerprint": "sha256:" + "7" * 64,
                    "producer_receipt_id": "receipt:producer",
                }
            },
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
        )
        codes = {finding.code for finding in evidence.findings}
        self.assertIn("contract_reuse_receipt_fingerprint_missing", codes)
        self.assertIn("contract_reuse_identity_missing", codes)

    def test_fake_sha_prefix_is_a_blocker(self):
        report = self._report()
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-fake-hash",
            result_rows={
                case.case_id: ContractRuntimeResult(
                    "passed",
                    result_fingerprint="sha256:not-a-real-digest",
                )
                for case in report.generated_cases
            },
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
        )
        self.assertIn(
            "contract_result_fingerprint_invalid",
            {finding.code for finding in evidence.findings},
        )
        self.assertFalse(evidence.ok)

    def test_strict_reconciliation_accepts_current_native_result_files(self):
        report = self._report()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = {}
            source, model, toolchain, environment = ("sha256:" + c * 64 for c in "1234")
            for index, case in enumerate(report.generated_cases):
                result_path = root / f"result-{index}.json"
                result_path.write_text(json.dumps({"case_id": case.case_id, "status": "passed"}))
                result_hash = sha256_fingerprint(result_path.read_bytes())
                record_path = root / f"record-{index}.json"
                record = dict(schema_version="native-result.v1", receipt_id=f"native:{index}",
                              producer_id="owner:native", command="native-contract-check",
                              source_fingerprint=source, model_fingerprint=model,
                              toolchain_fingerprint=toolchain, environment_fingerprint=environment,
                              result_fingerprint=result_hash, result_status="passed", exit_code=0,
                              terminal_state="passed", cleanup_state="confirmed", cleanup_verified=True)
                record_path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")))
                rows[case.case_id] = ContractRuntimeResult(
                    "passed", observed_status=CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
                    result_path=str(result_path), result_fingerprint=result_hash,
                    producer_receipt_id=record["receipt_id"], producer_receipt_path=str(record_path),
                    producer_receipt_fingerprint=sha256_fingerprint(record_path.read_bytes()),
                    source_fingerprint=source, model_fingerprint=model,
                    toolchain_fingerprint=toolchain, environment_fingerprint=environment,
                    terminal_state="passed", cleanup_state="confirmed", cleanup_verified=True)
            evidence = reconcile_contract_exhaustion_execution(
                report, execution_id="native-files", result_rows=rows,
                execution_owner_id="owner:native", command=("native-contract-check",),
                environment_fingerprint=environment, toolchain_fingerprint=toolchain,
                require_verifiable_material=True)
            self.assertTrue(evidence.ok, evidence.format_text())
            result_path.write_text("tampered")
            stale = reconcile_contract_exhaustion_execution(
                report, execution_id="native-files-changed", result_rows=rows,
                execution_owner_id="owner:native", command=("native-contract-check",),
                environment_fingerprint=environment, toolchain_fingerprint=toolchain,
                require_verifiable_material=True)
            self.assertFalse(stale.ok)
            self.assertIn("proof_result_hash_mismatch", {f.code for f in stale.findings})

    def test_strict_reconciliation_rejects_shape_only_pass_rows(self):
        report = self._report()
        evidence = reconcile_contract_exhaustion_execution(
            report,
            execution_id="execution-strict-shape-only",
            result_rows={
                case.case_id: self._passed()
                for case in report.generated_cases
            },
            execution_owner_id="owner:testmesh-contract",
            command=("pytest", "tests/test_packet_router.py"),
            require_verifiable_material=True,
        )
        codes = {finding.code for finding in evidence.findings}
        self.assertIn("proof_result_path_missing", codes)
        self.assertIn("proof_receipt_missing", codes)
        self.assertFalse(evidence.ok)


if __name__ == "__main__":
    unittest.main()
