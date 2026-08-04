import json
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest

from flowguard.source_identity import source_file_fingerprint
from flowguard.test_inventory import (
    TEST_DISPOSITION_REQUIRED,
    TEST_DISPOSITION_SUPPORTING,
    ProjectTestInventory,
    TestFileDisposition,
    TestDiscoveryResult,
    TestInventoryError,
    TestNodeDisposition,
    audit_project_test_inventory,
    build_project_test_inventory,
    load_project_test_inventory,
    review_project_test_inventory,
    serialize_project_test_inventory,
    write_project_test_inventory,
)
from flowguard.test_inventory_python import (
    PYTHON_AST_TEST_ADAPTER_ID,
    discover_python_test_file,
)


TEST_SOURCE = '''import pytest

from app import schedule


class TestPlanner:
    @pytest.mark.parametrize(
        "value, expected",
        [(1, 2), (2, 3)],
        ids=["one", "two"],
    )
    def test_shift(self, value, expected):
        result = schedule(value)
        assert result == expected


def test_rejects_negative_value():
    with pytest.raises(ValueError):
        schedule(-1)
'''


class ProjectTestInventoryTests(unittest.TestCase):
    def test_python_discovery_records_exact_static_test_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)
            inventory = self._complete_inventory(root)
            report = review_project_test_inventory(
                inventory,
                root=root,
                discovery_adapters=self._adapters(),
            )

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(report.status, "complete")
            self.assertEqual(
                {item.path for item in inventory.files},
                {"tests/test_planner.py"},
            )
            file_record = inventory.files[0]
            self.assertEqual(file_record.test_class_names, ("TestPlanner",))
            self.assertEqual(
                file_record.test_function_names,
                ("TestPlanner.test_shift", "test_rejects_negative_value"),
            )
            self.assertTrue(file_record.source_fingerprint.startswith("sha256:"))
            self.assertTrue(file_record.structure_fingerprint.startswith("sha256:"))

            by_nodeid = {item.pytest_nodeid: item for item in inventory.nodes}
            self.assertEqual(
                set(by_nodeid),
                {
                    "tests/test_planner.py::TestPlanner::test_shift",
                    "tests/test_planner.py::test_rejects_negative_value",
                },
            )
            parameterized = by_nodeid[
                "tests/test_planner.py::TestPlanner::test_shift"
            ]
            self.assertEqual(parameterized.class_name, "TestPlanner")
            self.assertEqual(parameterized.function_name, "test_shift")
            self.assertIn("schedule", parameterized.calls)
            self.assertEqual(parameterized.assertion_count, 1)
            self.assertEqual(parameterized.assertion_kinds, ("assert",))
            self.assertEqual(parameterized.assertion_targets, ("result == expected",))
            self.assertEqual(len(parameterized.parameterization_markers), 1)
            marker = parameterized.parameterization_markers[0]
            self.assertEqual(marker.argument_names, ("value", "expected"))
            self.assertEqual(marker.case_count, 2)
            self.assertEqual(marker.case_ids, ("one", "two"))
            self.assertFalse(marker.dynamic)

            rejects = by_nodeid[
                "tests/test_planner.py::test_rejects_negative_value"
            ]
            self.assertIn("pytest.raises", rejects.calls)
            self.assertEqual(rejects.assertion_kinds, ("raises",))
            self.assertEqual(rejects.assertion_targets, ("ValueError",))

    def test_assertion_free_required_node_stays_blocked_despite_parent_pass(self) -> None:
        source = '''from helpers import assert_contract


def test_calls_only():
    assert_contract(1)
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::test_calls_only",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
                aggregate_parent_evidence_ids=("receipt:full-suite-green",),
            )
            report = review_project_test_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn(
                "assertion_free_required_test_node",
                {item.code for item in report.findings},
            )
            self.assertEqual(report.required_node_ids, inventory.required_node_ids)
            self.assertEqual(len(inventory.nodes), 1)
            self.assertEqual(inventory.nodes[0].assertion_count, 0)
            self.assertEqual(inventory.nodes[0].calls, ("assert_contract",))
            self.assertEqual(
                inventory.aggregate_parent_evidence_ids,
                ("receipt:full-suite-green",),
            )

    def test_missing_required_node_is_not_created_from_parent_evidence(self) -> None:
        source = '''def test_present():
    assert True
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::test_missing",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                    TestNodeDisposition(
                        "tests/test_planner.py::test_present",
                        TEST_DISPOSITION_SUPPORTING,
                        reason="helper-level smoke test only",
                    ),
                ),
                aggregate_parent_evidence_ids=("receipt:full-suite-green",),
            )
            report = review_project_test_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn(
                "missing_required_test_node",
                {item.code for item in report.findings},
            )
            self.assertNotIn(
                "tests/test_planner.py::test_missing",
                {item.pytest_nodeid for item in inventory.nodes},
            )

    def test_undeclared_discovered_node_remains_an_orphan(self) -> None:
        source = '''def test_unmapped():
    assert True
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(root, node_dispositions=())
            report = review_project_test_inventory(inventory)

            self.assertFalse(report.ok)
            codes = {item.code for item in report.findings}
            self.assertIn("orphan_test_node", codes)
            self.assertIn("unresolved_test_node_disposition", codes)
            self.assertEqual(inventory.nodes[0].disposition, "unresolved")

    def test_dynamic_parameterization_is_visible_instead_of_guessed(self) -> None:
        source = '''import pytest


def cases():
    return [1, 2]


@pytest.mark.parametrize("value", cases())
def test_dynamic(value):
    assert value > 0
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::test_dynamic",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
            )
            report = review_project_test_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertTrue(inventory.nodes[0].parameterization_markers[0].dynamic)
            self.assertIn(
                "dynamic_test_parameterization",
                {item.code for item in report.findings},
            )

    def test_class_level_parameterization_is_attached_to_each_test_node(self) -> None:
        source = '''import pytest


@pytest.mark.parametrize("value", [1, 2], ids=["one", "two"])
class TestGrouped:
    def test_positive(self, value):
        assert value > 0
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::TestGrouped::test_positive",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
            )

            self.assertEqual(len(inventory.nodes), 1)
            marker = inventory.nodes[0].parameterization_markers[0]
            self.assertEqual(marker.argument_names, ("value",))
            self.assertEqual(marker.case_count, 2)
            self.assertEqual(marker.case_ids, ("one", "two"))

    def test_unqualified_raises_helper_is_a_call_not_a_pytest_assertion(self) -> None:
        source = '''def raises(error):
    return error


def test_local_helper_only():
    raises(ValueError)
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::test_local_helper_only",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
            )
            report = review_project_test_inventory(inventory)

            self.assertEqual(inventory.nodes[0].calls, ("raises",))
            self.assertEqual(inventory.nodes[0].assertion_count, 0)
            self.assertFalse(report.ok)
            self.assertIn(
                "assertion_free_required_test_node",
                {item.code for item in report.findings},
            )

    def test_fixtures_unittest_warnings_and_subtest_cases_are_explicit(self) -> None:
        source = '''import unittest


class TestCases(unittest.TestCase):
    def test_case(self, tmp_path):
        with self.subTest(case="one"):
            with self.assertWarns(UserWarning):
                self.assertEqual(tmp_path.name, "one")
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source)
            inventory = self._inventory(
                root,
                node_dispositions=(
                    TestNodeDisposition(
                        "tests/test_planner.py::TestCases::test_case",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
            )
            node = inventory.nodes[0]

            self.assertEqual(("tmp_path",), node.fixture_names)
            self.assertIn("unittest_assertion", node.assertion_kinds)
            self.assertEqual(1, node.parameterization_markers[0].case_count)
            self.assertEqual(("case='one'",), node.parameterization_markers[0].case_ids)

    def test_current_root_audit_detects_source_and_structure_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)
            inventory = self._complete_inventory(root)
            path = root / "tests" / "test_planner.py"
            path.write_text(
                TEST_SOURCE.replace("assert result == expected", "assert result >= expected"),
                encoding="utf-8",
            )

            report = review_project_test_inventory(
                inventory,
                root=root,
                discovery_adapters=self._adapters(),
            )
            codes = {item.code for item in report.findings}
            self.assertFalse(report.ok)
            self.assertIn("stale_test_source_fingerprint", codes)
            self.assertIn("stale_test_structure_fingerprint", codes)

    def test_current_root_audit_detects_a_new_matching_test_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)
            inventory = self._complete_inventory(root)
            (root / "tests" / "test_added.py").write_text(
                "def test_added():\n    assert True\n",
                encoding="utf-8",
            )

            report = review_project_test_inventory(
                inventory,
                root=root,
                discovery_adapters=self._adapters(),
            )
            codes = {item.code for item in report.findings}
            self.assertFalse(report.ok)
            self.assertIn("stale_test_manifest_fingerprint", codes)
            self.assertIn("uninventoried_current_test_file", codes)

    def test_audit_rejects_internally_inconsistent_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)
            inventory = self._complete_inventory(root)
            first = inventory.nodes[0]
            tampered = replace(
                inventory,
                nodes=(
                    replace(first, source_fingerprint="sha256:" + ("0" * 64)),
                    *inventory.nodes[1:],
                ),
            )

            report = review_project_test_inventory(tampered)
            self.assertFalse(report.ok)
            self.assertIn(
                "test_node_source_identity_mismatch",
                {item.code for item in report.findings},
            )

    def test_builder_rejects_cross_identity_adapter_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)

            def injected_adapter(**kwargs):
                result = discover_python_test_file(**kwargs)
                self.assertIsNotNone(result.file_record)
                stale = "sha256:" + ("0" * 64)
                return TestDiscoveryResult(
                    adapter_id=result.adapter_id,
                    path=result.path,
                    file_record=replace(
                        result.file_record,
                        source_fingerprint=stale,
                    ),
                    nodes=tuple(
                        replace(item, source_fingerprint=stale)
                        for item in result.nodes
                    ),
                    findings=result.findings,
                )

            source = root / "tests" / "test_planner.py"
            inventory = build_project_test_inventory(
                root,
                inventory_id="project-test-inventory:untrusted-adapter",
                subject_revision="source:fixture",
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
                    TestNodeDisposition(
                        "tests/test_planner.py::TestPlanner::test_shift",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                    TestNodeDisposition(
                        "tests/test_planner.py::test_rejects_negative_value",
                        TEST_DISPOSITION_REQUIRED,
                    ),
                ),
                discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: injected_adapter},
            )

            self.assertEqual(inventory.files, ())
            self.assertEqual(inventory.nodes, ())
            self.assertIn(
                "test_discovery_record_identity_mismatch",
                {item.code for item in inventory.findings},
            )

    def test_serialization_loading_and_audit_are_canonical_and_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), TEST_SOURCE)
            inventory = self._complete_inventory(root)
            first = serialize_project_test_inventory(inventory)
            second = serialize_project_test_inventory(inventory)
            self.assertEqual(first, second)

            path = root / "test-inventory.json"
            write_project_test_inventory(inventory, path)
            loaded = load_project_test_inventory(path)
            self.assertIsInstance(loaded, ProjectTestInventory)
            self.assertEqual(loaded, inventory)
            self.assertEqual(loaded.inventory_fingerprint, inventory.inventory_fingerprint)

            before = self._snapshot(root)
            report = audit_project_test_inventory(
                path,
                root=root,
                discovery_adapters=self._adapters(),
            )
            after = self._snapshot(root)
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(before, after)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["unexpected"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(TestInventoryError, "fields differ"):
                load_project_test_inventory(path)

            payload.pop("unexpected")
            payload["inventory_fingerprint"] = "sha256:" + ("0" * 64)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(TestInventoryError, "fingerprint mismatch"):
                load_project_test_inventory(path)

    def _complete_inventory(self, root: Path) -> ProjectTestInventory:
        return self._inventory(
            root,
            node_dispositions=(
                TestNodeDisposition(
                    "tests/test_planner.py::TestPlanner::test_shift",
                    TEST_DISPOSITION_REQUIRED,
                ),
                TestNodeDisposition(
                    "tests/test_planner.py::test_rejects_negative_value",
                    TEST_DISPOSITION_REQUIRED,
                ),
            ),
        )

    def _inventory(
        self,
        root: Path,
        *,
        node_dispositions: tuple[TestNodeDisposition, ...],
        aggregate_parent_evidence_ids: tuple[str, ...] = (),
    ) -> ProjectTestInventory:
        source = root / "tests" / "test_planner.py"
        return build_project_test_inventory(
            root,
            inventory_id="project-test-inventory:fixture",
            subject_revision="source:fixture",
            test_patterns=("tests/**/*.py",),
            file_dispositions=(
                TestFileDisposition(
                    path="tests/test_planner.py",
                    source_fingerprint=source_file_fingerprint(source),
                    disposition=TEST_DISPOSITION_REQUIRED,
                    adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
                ),
            ),
            node_dispositions=node_dispositions,
            aggregate_parent_evidence_ids=aggregate_parent_evidence_ids,
            discovery_adapters=self._adapters(),
        )

    @staticmethod
    def _adapters():
        return {PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file}

    @staticmethod
    def _repository(root: Path, source: str) -> Path:
        tests = root / "tests"
        tests.mkdir(parents=True)
        (tests / "test_planner.py").write_text(source, encoding="utf-8")
        subprocess.run(
            ["git", "init", "-q"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return root

    @staticmethod
    def _snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file() and ".git" not in path.parts
        }


if __name__ == "__main__":
    unittest.main()
