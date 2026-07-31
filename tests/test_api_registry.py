import ast
import importlib
from pathlib import Path
import unittest

import flowguard
from flowguard.api_registry import (
    build_public_api_registry,
    dedupe_public_names,
)


ROOT = Path(__file__).resolve().parents[1]


def legacy_dedupe_public_names(*groups: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


class PublicAPIRegistryTests(unittest.TestCase):
    def test_package_facade_has_unique_materialized_names(self):
        registry = build_public_api_registry(
            vars(flowguard),
            (tuple(flowguard.__all__),),
        )

        self.assertTrue(registry.ok, registry)
        self.assertEqual(tuple(flowguard.__all__), registry.names)

    def test_duplicate_and_missing_owners_are_visible(self):
        registry = build_public_api_registry(
            {"present": object()},
            (("present", "duplicate"), ("duplicate", "missing")),
        )

        self.assertFalse(registry.ok)
        self.assertEqual(("duplicate",), registry.duplicate_names)
        self.assertEqual(("duplicate", "missing"), registry.missing_names)

    def test_api_registry_does_not_import_package_facade(self):
        module = importlib.import_module("flowguard.api_registry")

        self.assertNotIn("flowguard", module.__dict__)

    def test_package_all_keeps_exact_pre_extraction_order_and_objects(self):
        groups = (
            flowguard.CORE_API,
            flowguard.CONTRACT_EXHAUSTION_MESH_API,
            flowguard.DEVELOPMENT_PROCESS_FLOW_ROUTE_API,
            flowguard.MODEL_MISS_REVIEW_ROUTE_API,
            flowguard.MODELING_HELPER_API,
            flowguard.REPORTING_HELPER_API,
            flowguard.EVIDENCE_API,
            flowguard.FLOWGUARD_GOVERNANCE_API,
            flowguard.PORTABLE_VERIFICATION_API,
            flowguard._PUBLIC_API_SUPPLEMENT,
        )

        expected = legacy_dedupe_public_names(*groups)
        self.assertEqual(expected, dedupe_public_names(*groups))
        self.assertEqual(expected, flowguard.__all__)

        imported: dict[str, object] = {}
        exec("from flowguard import *", {}, imported)
        self.assertEqual(set(expected), set(imported))
        for name in expected:
            self.assertIs(getattr(flowguard, name), imported[name], name)

    def test_extracted_helpers_have_one_owner_and_acyclic_import_edges(self):
        function_owners: dict[str, list[str]] = {
            "dedupe_public_names": [],
            "run_supervised": [],
            "write_terminal_artifact": [],
        }
        imports: dict[str, set[str]] = {}
        for path in sorted((ROOT / "flowguard").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports[path.name] = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name in function_owners
                ):
                    function_owners[node.name].append(path.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports[path.name].add(node.module.lstrip("."))
                elif isinstance(node, ast.Import):
                    imports[path.name].update(
                        alias.name for alias in node.names
                    )

        self.assertEqual(
            ["api_registry.py"],
            function_owners["dedupe_public_names"],
        )
        self.assertEqual(
            ["process_supervision.py"],
            function_owners["run_supervised"],
        )
        self.assertEqual(
            ["process_supervision.py"],
            function_owners["write_terminal_artifact"],
        )
        self.assertNotIn(
            "flowguard",
            imports["api_registry.py"],
        )
        self.assertNotIn(
            "model_regressions",
            imports["process_supervision.py"],
        )
        self.assertIn(
            "process_supervision",
            imports["model_regressions.py"],
        )


if __name__ == "__main__":
    unittest.main()
