from pathlib import Path
import subprocess
import tempfile
import unittest

from flowguard.runtime_test_evidence import (
    RUNTIME_TEST_EXECUTION_NOT_RUN,
    RUNTIME_TEST_EXECUTION_REUSED,
    RUNTIME_TEST_OUTCOME_NOT_RUN,
    RuntimeTestEvidenceError,
    RuntimeTestEvidenceReport,
    classify_pytest_result,
    load_runtime_test_evidence,
    reconcile_pytest_execution,
    serialize_runtime_test_evidence,
    write_runtime_test_evidence,
)
from flowguard._hashing import source_file_fingerprint
from flowguard.test_inventory import (
    TEST_DISPOSITION_REQUIRED,
    TestFileDisposition,
    TestNodeDisposition,
    build_project_test_inventory,
)
from flowguard.test_inventory_python import (
    PYTHON_AST_TEST_ADAPTER_ID,
    discover_python_test_file,
)


SOURCE = '''import pytest


@pytest.mark.parametrize("value", [1, 2], ids=["one", "two"])
def test_shift(value):
    assert value > 0


def test_plain():
    assert True
'''


class RuntimeTestEvidenceTests(unittest.TestCase):
    def test_concrete_parameter_leaves_keep_parent_accounting_and_skip_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            parameter = "tests/test_planner.py::test_shift"
            plain = "tests/test_planner.py::test_plain"
            one = parameter + "[one]"
            two = parameter + "[two]"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:leaf-accounting",
                requested_pytest_nodeids=(parameter, plain),
                collected_pytest_nodeids=(one, two, plain),
                result_rows={
                    one: {"call": "passed"},
                    two: {"call": "skipped", "reason": "requires optional provider"},
                    plain: {"call": "passed"},
                },
                declared_parent_counts={
                    "planned_count": 3,
                    "selected_count": 3,
                    "executed_count": 3,
                    "not_run_count": 0,
                    "passed_count": 2,
                    "skipped_count": 1,
                },
                declared_parent_status="passed",
            )

            self.assertEqual(
                {
                    "planned_count": 3,
                    "selected_count": 3,
                    "explicitly_not_selected_count": 0,
                    "executed_count": 3,
                    "reused_count": 0,
                    "not_run_count": 0,
                    "passed_count": 2,
                    "failed_count": 0,
                    "skipped_count": 1,
                    "xfailed_count": 0,
                    "xpassed_count": 0,
                },
                report.counts,
            )
            self.assertFalse(report.ok)
            self.assertIn("runtime_test_leaf_skipped", self._codes(report))
            self.assertIn("parent_leaf_status_mismatch", self._codes(report))
            leaf = next(item for item in report.leaves if item.pytest_nodeid == two)
            self.assertEqual("skipped", leaf.outcome)
            self.assertEqual("requires optional provider", leaf.reason)
            self.assertEqual((), report.unrelated_pytest_nodeids)

    def test_legacy_parent_count_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            plain = "tests/test_planner.py::test_plain"
            with self.assertRaises(RuntimeTestEvidenceError):
                reconcile_pytest_execution(
                    inventory,
                    execution_id="run:legacy-count-alias",
                    requested_pytest_nodeids=(plain,),
                    collected_pytest_nodeids=(plain,),
                    result_rows={plain: {"call": "passed"}},
                    declared_parent_counts={"test_count": 1},
                )

    def test_parent_skip_total_mismatch_is_a_blocker_even_when_leaf_is_visible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            plain = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:skip-mismatch",
                requested_pytest_nodeids=(plain,),
                collected_pytest_nodeids=(plain,),
                result_rows={
                    plain: {"outcome": "skipped", "reason": "explicit test policy"},
                },
                declared_parent_counts={
                    "planned_count": 1,
                    "selected_count": 1,
                    "executed_count": 1,
                    "skipped_count": 0,
                },
            )

            self.assertFalse(report.ok)
            self.assertIn("parent_leaf_count_mismatch", self._codes(report))
            self.assertEqual(1, report.counts["skipped_count"])
            self.assertEqual(
                "explicit test policy",
                report.leaves[0].reason,
            )

    def test_deselected_requested_leaf_is_explicitly_not_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            plain = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:deselected",
                requested_pytest_nodeids=(plain,),
                collected_pytest_nodeids=(),
                deselected_pytest_nodeids=(plain,),
            )

            self.assertEqual(1, report.counts["planned_count"])
            self.assertEqual(0, report.counts["selected_count"])
            self.assertEqual(1, report.counts["explicitly_not_selected_count"])
            self.assertEqual(1, report.counts["not_run_count"])
            self.assertTrue(report.leaves[0].not_run)
            self.assertFalse(report.leaves[0].selected)
            self.assertIn("runtime_test_leaf_not_run", self._codes(report))

    def test_reused_and_missing_parameterized_leaves_are_separate_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            parameter = "tests/test_planner.py::test_shift"
            plain = "tests/test_planner.py::test_plain"
            one = parameter + "[one]"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:reuse-and-gap",
                requested_pytest_nodeids=(parameter, plain),
                collected_pytest_nodeids=(one,),
                reused_rows={one: {"outcome": "passed"}},
            )

            self.assertEqual(2, report.counts["planned_count"])
            self.assertEqual(0, report.counts["executed_count"])
            self.assertEqual(1, report.counts["reused_count"])
            self.assertEqual(1, report.counts["not_run_count"])
            reused = next(item for item in report.leaves if item.pytest_nodeid == one)
            missing = next(item for item in report.leaves if item.pytest_nodeid == plain)
            self.assertEqual(RUNTIME_TEST_EXECUTION_REUSED, reused.execution_status)
            self.assertTrue(reused.reused)
            self.assertFalse(reused.not_run)
            self.assertEqual(RUNTIME_TEST_EXECUTION_NOT_RUN, missing.execution_status)
            self.assertEqual(RUNTIME_TEST_OUTCOME_NOT_RUN, missing.outcome)
            self.assertTrue(missing.not_run)
            self.assertFalse(report.ok)
            self.assertIn("runtime_test_leaf_not_run", self._codes(report))

    def test_round_trip_preserves_leaf_and_parent_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            plain = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:round-trip",
                requested_pytest_nodeids=(plain,),
                collected_pytest_nodeids=(plain,),
                result_rows={plain: {"call": "passed"}},
                execution_owner_id="owner:pytest",
                environment_fingerprint="sha256:environment",
                toolchain_fingerprint="sha256:toolchain",
                command=("python", "-m", "pytest", plain),
            )
            path = Path(temporary) / "runtime-evidence.json"
            write_runtime_test_evidence(report, path)
            loaded = load_runtime_test_evidence(path)
            self.assertEqual(report, loaded)
            self.assertEqual(serialize_runtime_test_evidence(report), serialize_runtime_test_evidence(loaded))
            self.assertIsInstance(RuntimeTestEvidenceReport.from_dict(report.to_dict()), RuntimeTestEvidenceReport)

    def test_pytest_report_normalization_keeps_xfail_and_unknown_rows_non_green(self):
        xfailed = classify_pytest_result(
            {"setup": "passed", "call": "failed", "wasxfail": "known provider gap"}
        )
        xpassed = classify_pytest_result(
            {"call": "passed", "wasxfail": "known provider gap"}
        )
        unknown = classify_pytest_result({"setup": "passed"})
        self.assertEqual("xfailed", xfailed.outcome)
        self.assertEqual("known provider gap", xfailed.reason)
        self.assertEqual("xpassed", xpassed.outcome)
        self.assertIn("xfail", xpassed.reason)
        self.assertEqual("not_run", unknown.outcome)
        self.assertTrue(unknown.reason)

    def test_reused_leaf_without_receipt_or_reuse_identity_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            nodeid = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:missing-reuse-receipt",
                requested_pytest_nodeids=(nodeid,),
                collected_pytest_nodeids=(nodeid,),
                reused_rows={
                    nodeid: {
                        "outcome": "passed",
                        "result_fingerprint": "sha256:" + "1" * 64,
                    }
                },
            )
            codes = {finding.code for finding in report.findings}
            self.assertIn("runtime_test_reuse_producer_receipt_missing", codes)
            self.assertIn("runtime_test_reuse_receipt_fingerprint_missing", codes)
            self.assertIn("runtime_test_reuse_identity_missing", codes)
            self.assertFalse(report.ok)

    def test_fake_sha_prefix_is_blocked_even_before_strict_path_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            nodeid = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:fake-result-hash",
                requested_pytest_nodeids=(nodeid,),
                collected_pytest_nodeids=(nodeid,),
                result_rows={
                    nodeid: {
                        "outcome": "passed",
                        "result_fingerprint": "sha256:not-a-real-digest",
                    }
                },
            )
            self.assertIn(
                "runtime_test_result_fingerprint_invalid",
                {finding.code for finding in report.findings},
            )
            self.assertFalse(report.ok)

    def test_legacy_receipt_field_aliases_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            nodeid = "tests/test_planner.py::test_plain"
            with self.assertRaises(RuntimeTestEvidenceError):
                reconcile_pytest_execution(
                    inventory,
                    execution_id="run:legacy-receipt-aliases",
                    requested_pytest_nodeids=(nodeid,),
                    collected_pytest_nodeids=(nodeid,),
                    reused_rows={
                        nodeid: {
                            "outcome": "passed",
                            "result_fingerprint": "sha256:" + "8" * 64,
                            "receipt_id": "receipt:legacy",
                            "receipt_fingerprint": "sha256:" + "9" * 64,
                            "receipt_path": str(root / "receipt.json"),
                        }
                    },
                )

    def test_strict_reconciliation_rejects_shape_only_pass_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, inventory = self._inventory(Path(temporary))
            nodeid = "tests/test_planner.py::test_plain"
            report = reconcile_pytest_execution(
                inventory,
                execution_id="run:strict-shape-only",
                requested_pytest_nodeids=(nodeid,),
                collected_pytest_nodeids=(nodeid,),
                result_rows={
                    nodeid: {
                        "outcome": "passed",
                        "result_fingerprint": "sha256:" + "a" * 64,
                    }
                },
                require_verifiable_material=True,
            )
            codes = {finding.code for finding in report.findings}
            self.assertIn("proof_result_path_missing", codes)
            self.assertIn("proof_receipt_missing", codes)
            self.assertFalse(report.ok)

    @staticmethod
    def _codes(report):
        return {item.code for item in report.findings}

    @staticmethod
    def _inventory(root: Path):
        tests = root / "tests"
        tests.mkdir(parents=True)
        source = tests / "test_planner.py"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run(
            ["git", "init", "-q"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        parameter = "tests/test_planner.py::test_shift"
        plain = "tests/test_planner.py::test_plain"
        inventory = build_project_test_inventory(
            root,
            inventory_id="project-test-inventory:runtime-fixture",
            subject_revision="source:runtime-fixture",
            test_patterns=("tests/**/*.py",),
            file_dispositions=(
                TestFileDisposition(
                    path="tests/test_planner.py",
                    source_fingerprint=source_file_fingerprint(source),
                    disposition=TEST_DISPOSITION_REQUIRED,
                    adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
                ),
            ),
            node_dispositions=(
                TestNodeDisposition(parameter, TEST_DISPOSITION_REQUIRED),
                TestNodeDisposition(plain, TEST_DISPOSITION_REQUIRED),
            ),
            discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
        )
        return root, inventory


if __name__ == "__main__":
    unittest.main()
