import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from flowguard.implementation_inventory import (
    DynamicSelectorContract,
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    ImplementationDiscoveryResult,
    ImplementationFileDisposition,
    ImplementationInventoryError,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    audit_implementation_surface_inventory,
    build_implementation_surface_inventory,
    implementation_behavior_surface_ids,
    implementation_surface_id,
    implementation_surface_key,
    load_implementation_surface_inventory,
    review_implementation_surface_inventory,
    serialize_implementation_surface_inventory,
    write_implementation_surface_inventory,
)
from flowguard.implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    derive_static_dynamic_selector_contracts,
    discover_python_implementation_surfaces,
    project_python_implementation_observation,
)
from flowguard.source_identity import source_file_fingerprint


SOURCE = """STATE = {}

def _normalize(value):
    return str(value).strip()

class Service:
    def save(self, value):
        normalized = _normalize(value)
        STATE["last"] = normalized
        write_record(normalized)
        return normalized

def main():
    return Service().save("value")

if __name__ == "__main__":
    main()
"""


class ImplementationInventoryTests(unittest.TestCase):
    def test_provider_disposition_owns_behavior_denominator_without_losing_support_facts(self) -> None:
        owner = ImplementationSurface(
            surface_id="surface:owner",
            path="src/app.py",
            symbol="run",
            surface_kind="function",
            parent_surface_id="",
            content_fingerprint="fp:source",
            structure_fingerprint="fp:owner",
            disposition=IMPLEMENTATION_DISPOSITION_MODEL,
            roles=("behavior",),
        )
        delegated = ImplementationSurface(
            surface_id="surface:delegated",
            path="src/app.py",
            symbol="ModelBuilder",
            surface_kind="class",
            parent_surface_id="",
            content_fingerprint="fp:source",
            structure_fingerprint="fp:delegated",
            disposition=IMPLEMENTATION_DISPOSITION_SUPPORTING,
            owning_surface_id=owner.surface_id,
            roles=("state_writer",),
            state_writes=("state",),
        )
        inventory = ImplementationSurfaceInventory(
            inventory_id="inventory:provider-disposition",
            boundary=SoftwareBoundary(
                "boundary:provider-disposition",
                "revision:test",
                production_patterns=("src/**/*.py",),
            ),
            manifest_fingerprint="fp:manifest",
            file_dispositions=(),
            surfaces=(owner, delegated),
            findings=(),
            claim_boundary="provider-classified behavior denominator",
        )

        self.assertTrue(delegated.behavior_bearing)
        self.assertEqual(
            implementation_behavior_surface_ids(inventory),
            (owner.surface_id,),
        )
        self.assertTrue(
            review_implementation_surface_inventory(inventory).ok
        )

    def test_independent_manifest_and_python_ast_form_complete_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            inventory = self._complete_inventory(root)
            report = review_implementation_surface_inventory(inventory, root=root)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(report.status, "complete")
            self.assertEqual(report.inventory_fingerprint, inventory.inventory_fingerprint)
            self.assertEqual(report.required_surface_ids, inventory.required_surface_ids)
            self.assertTrue(report.required_surface_ids)

            by_symbol = {item.symbol: item for item in inventory.surfaces}
            self.assertEqual(
                set(by_symbol),
                {"<module>", "_normalize", "Service", "Service.save", "main"},
            )
            self.assertIn("helper", by_symbol["_normalize"].roles)
            self.assertEqual(
                by_symbol["_normalize"].owning_surface_id,
                by_symbol["Service.save"].surface_id,
            )
            self.assertIn("state_writer", by_symbol["Service.save"].roles)
            self.assertIn("effect_writer", by_symbol["Service.save"].roles)
            self.assertIn("entrypoint", by_symbol["main"].roles)
            self.assertIn("write_record", by_symbol["Service.save"].side_effect_candidates)
            self.assertEqual(
                by_symbol["Service.save"].parent_surface_id,
                by_symbol["Service"].surface_id,
            )

    def test_inventory_consumes_one_invocation_local_observation_without_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            file_disposition = self._python_file_disposition(path)
            keys = {
                symbol: implementation_surface_key("src/app.py", symbol)
                for symbol in ("<module>", "_normalize", "Service", "Service.save", "main")
            }
            dispositions = {
                keys["<module>"]: IMPLEMENTATION_DISPOSITION_MODEL,
                keys["_normalize"]: IMPLEMENTATION_DISPOSITION_SUPPORTING,
                keys["Service"]: IMPLEMENTATION_DISPOSITION_MODEL,
                keys["Service.save"]: IMPLEMENTATION_DISPOSITION_MODEL,
                keys["main"]: IMPLEMENTATION_DISPOSITION_MODEL,
            }
            raw = discover_python_implementation_surfaces(
                root=root,
                file_disposition=file_disposition,
            )
            projected = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                supporting_owners={keys["_normalize"]: keys["Service.save"]},
            )
            adapter_calls = 0

            def forbidden_adapter(**_kwargs):
                nonlocal adapter_calls
                adapter_calls += 1
                raise AssertionError("inventory reparsed an already observed file")

            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:observation-reuse",
                file_dispositions=(file_disposition,),
                surface_dispositions=dispositions,
                supporting_owners={keys["_normalize"]: keys["Service.save"]},
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: forbidden_adapter
                },
                discovery_results={"src/app.py": projected},
            )

            self.assertEqual(adapter_calls, 0)
            self.assertTrue(
                review_implementation_surface_inventory(inventory, root=root).ok
            )

    def test_python_provider_uses_one_immutable_source_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            path.write_bytes(SOURCE.replace("\n", "\r\n").encode("utf-8"))
            file_disposition = self._python_file_disposition(path)
            target_path = path.resolve()
            reads = {"bytes": 0, "text": 0}
            original_read_bytes = Path.read_bytes
            original_read_text = Path.read_text
            original_write_text = Path.write_text

            def read_bytes_then_change(candidate: Path) -> bytes:
                payload = original_read_bytes(candidate)
                if candidate.resolve() == target_path:
                    reads["bytes"] += 1
                    if reads["bytes"] == 1:
                        original_write_text(
                            candidate,
                            "def replacement():\n    return 42\n",
                            encoding="utf-8",
                        )
                return payload

            def count_text_reads(candidate: Path, *args, **kwargs) -> str:
                if candidate.resolve() == target_path:
                    reads["text"] += 1
                return original_read_text(candidate, *args, **kwargs)

            with mock.patch.object(Path, "read_bytes", read_bytes_then_change), (
                mock.patch.object(Path, "read_text", count_text_reads)
            ):
                discovery = discover_python_implementation_surfaces(
                    root=root,
                    file_disposition=file_disposition,
                )

            self.assertEqual(reads, {"bytes": 1, "text": 0})
            self.assertNotIn(
                "stale_file_fingerprint",
                {finding.code for finding in discovery.findings},
            )
            self.assertEqual(
                {surface.symbol for surface in discovery.surfaces},
                {"<module>", "_normalize", "Service", "Service.save", "main"},
            )
            self.assertNotIn(
                "replacement",
                {surface.symbol for surface in discovery.surfaces},
            )
            self.assertTrue(
                all(
                    surface.content_fingerprint
                    == file_disposition.content_fingerprint
                    for surface in discovery.surfaces
                )
            )

    def test_function_locals_parameters_and_exception_types_are_not_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source="""STATE = {}

def save(value):
    normalized = str(value).strip()
    if normalized == "rejected":
        raise ValueError("rejected-input")
    STATE["last"] = normalized
    return normalized
""",
            )
            path = root / "src" / "app.py"
            discovery = discover_python_implementation_surfaces(
                root=root,
                file_disposition=self._python_file_disposition(path),
            )
            save = next(item for item in discovery.surfaces if item.symbol == "save")

            self.assertNotIn("value", save.state_reads)
            self.assertNotIn("normalized", save.state_reads)
            self.assertNotIn("str", save.state_reads)
            self.assertNotIn("ValueError", save.state_reads)
            self.assertTrue(
                any(item.startswith("STATE[") for item in save.state_writes)
            )
            self.assertIn("ValueError", save.raised_errors)

    def test_missing_file_disposition_preserves_exact_denominator_as_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            config = root / "config.json"
            config.write_text('{"enabled":true}\n', encoding="utf-8")
            self._git_add(root)
            boundary = SoftwareBoundary(
                "boundary:test",
                "revision:test",
                production_patterns=("src/**/*.py",),
                config_patterns=("config.json",),
            )
            source_path = root / "src" / "app.py"
            inventory = build_implementation_surface_inventory(
                root,
                boundary,
                inventory_id="inventory:missing-config",
                file_dispositions=(self._python_file_disposition(source_path),),
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertEqual(
                {item.path for item in inventory.file_dispositions},
                {"src/app.py", "config.json"},
            )
            self.assertIn("missing_file_disposition", {item.code for item in report.findings})

    def test_tracked_file_outside_declared_categories_is_not_silently_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            (root / "UNCLASSIFIED.txt").write_text("must be classified\n", encoding="utf-8")
            self._git_add(root)
            path = root / "src" / "app.py"
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:unmatched",
                file_dispositions=(self._python_file_disposition(path),),
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn("UNCLASSIFIED.txt", {item.path for item in inventory.file_dispositions})
            self.assertIn("unmatched_boundary_file", {item.code for item in report.findings})

    def test_parse_and_dynamic_uncertainty_block_instead_of_being_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source="def run(name):\n    return getattr(plugin, name)()\n",
            )
            path = root / "src" / "app.py"
            dispositions = {
                implementation_surface_key("src/app.py", "<module>"): IMPLEMENTATION_DISPOSITION_MODEL,
                implementation_surface_key("src/app.py", "run"): IMPLEMENTATION_DISPOSITION_MODEL,
            }
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:dynamic",
                file_dispositions=(self._python_file_disposition(path),),
                surface_dispositions=dispositions,
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )
            self.assertFalse(review_implementation_surface_inventory(inventory).ok)
            self.assertIn("dynamic_python_surface", {item.code for item in inventory.findings})

        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source="def broken(:\n    pass\n")
            path = root / "src" / "app.py"
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:parse-failure",
                file_dispositions=(self._python_file_disposition(path),),
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )
            self.assertFalse(review_implementation_surface_inventory(inventory).ok)
            self.assertIn("python_parse_failure", {item.code for item in inventory.findings})

    def test_missing_required_discovery_adapter_is_an_explicit_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            disposition = ImplementationFileDisposition(
                path="src/app.py",
                category="production",
                content_fingerprint=source_file_fingerprint(path),
                disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                reason="production implementation",
                requires_adapter=True,
                adapter_id="adapter:missing",
            )
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:missing-adapter",
                file_dispositions=(disposition,),
                discovery_adapters={},
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn(
                "missing_discovery_adapter",
                {item.code for item in report.findings},
            )
            self.assertEqual({item.path for item in inventory.file_dispositions}, {"src/app.py"})

    def test_adapter_exception_cannot_become_empty_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            disposition = ImplementationFileDisposition(
                path="src/app.py",
                category="production",
                content_fingerprint=source_file_fingerprint(path),
                disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                reason="production implementation",
                requires_adapter=True,
                adapter_id="adapter:broken",
            )

            def broken_adapter(**_kwargs):
                raise RuntimeError("fixture adapter failed")

            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:broken-adapter",
                file_dispositions=(disposition,),
                discovery_adapters={"adapter:broken": broken_adapter},
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn(
                "discovery_adapter_failure",
                {item.code for item in report.findings},
            )

    def test_adapter_identity_mismatch_cannot_contribute_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            disposition = ImplementationFileDisposition(
                path="src/app.py",
                category="production",
                content_fingerprint=source_file_fingerprint(path),
                disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                reason="production implementation",
                requires_adapter=True,
                adapter_id="adapter:declared",
            )

            def counterfeit_adapter(**_kwargs):
                return ImplementationDiscoveryResult(
                    adapter_id="adapter:counterfeit",
                    path="src/app.py",
                    surfaces=(),
                )

            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:counterfeit-adapter",
                file_dispositions=(disposition,),
                discovery_adapters={"adapter:declared": counterfeit_adapter},
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertIn(
                "discovery_adapter_identity_mismatch",
                {item.code for item in report.findings},
            )

    def test_implementation_file_cannot_disable_discovery_and_stay_empty_green(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            path = root / "src" / "app.py"
            disposition = ImplementationFileDisposition(
                path="src/app.py",
                category="production",
                content_fingerprint=source_file_fingerprint(path),
                disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                reason="production implementation",
                requires_adapter=False,
                adapter_id="",
            )
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:disabled-discovery",
                file_dispositions=(disposition,),
                discovery_adapters={},
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertFalse(report.ok)
            self.assertEqual(inventory.surfaces, ())
            self.assertIn(
                "implementation_discovery_disabled",
                {item.code for item in report.findings},
            )

    def test_synthetic_non_python_non_code_adapter_can_supply_a_real_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workflow_repository(Path(temporary))
            workflow_path = root / "workflow" / "approval.workflow.json"
            adapter_id = "adapter:declarative-workflow"
            disposition = ImplementationFileDisposition(
                path="workflow/approval.workflow.json",
                category="production",
                content_fingerprint=source_file_fingerprint(workflow_path),
                disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                reason="declarative workflow implementation",
                requires_adapter=True,
                adapter_id=adapter_id,
            )

            def discover_workflow(*, file_disposition, **_kwargs):
                return ImplementationDiscoveryResult(
                    adapter_id=adapter_id,
                    path=file_disposition.path,
                    surfaces=(
                        ImplementationSurface(
                            surface_id="workflow-surface:approval-transition",
                            path="",
                            symbol="",
                            surface_kind="non_code",
                            parent_surface_id="",
                            content_fingerprint=file_disposition.content_fingerprint,
                            structure_fingerprint="sha256:workflow-structure",
                            disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                            roles=("entrypoint", "state_writer"),
                            parameters=("request", "current_state"),
                            state_reads=("approval_state",),
                            state_writes=("approval_state",),
                            returns_value=True,
                            discovery_adapter_id=adapter_id,
                        ),
                    ),
                )

            inventory = build_implementation_surface_inventory(
                root,
                SoftwareBoundary(
                    "boundary:workflow",
                    "revision:workflow",
                    production_patterns=("workflow/**/*.json",),
                ),
                inventory_id="inventory:workflow",
                file_dispositions=(disposition,),
                discovery_adapters={adapter_id: discover_workflow},
            )
            report = review_implementation_surface_inventory(inventory)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(len(inventory.surfaces), 1)
            surface = inventory.surfaces[0]
            self.assertEqual(surface.surface_kind, "non_code")
            self.assertEqual(surface.path, "")
            self.assertEqual(surface.symbol, "")
            self.assertIn(surface.surface_id, report.required_surface_ids)

    def test_literal_dynamic_access_can_be_explicitly_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source="def run(plugin):\n    return getattr(plugin, 'save')()\n",
            )
            path = root / "src" / "app.py"
            keys = {
                symbol: implementation_surface_key("src/app.py", symbol)
                for symbol in ("<module>", "run")
            }
            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:bounded-dynamic",
                file_dispositions=(self._python_file_disposition(path),),
                surface_dispositions={
                    keys["<module>"]: IMPLEMENTATION_DISPOSITION_MODEL,
                    keys["run"]: IMPLEMENTATION_DISPOSITION_MODEL,
                },
                dynamic_allowances={
                    keys["run"]: ("getattr:save", "invoke_result:getattr")
                },
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )

            report = review_implementation_surface_inventory(inventory)
            self.assertTrue(report.ok, report.to_dict())
            run = next(item for item in inventory.surfaces if item.symbol == "run")
            self.assertIn("dynamic_bounded", run.roles)
            self.assertNotIn("dynamic", run.roles)

    def test_dynamic_selector_contract_requires_exact_static_values_and_current_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source=(
                    "def bounded(value):\n"
                    "    for name in ('alpha', 'beta'):\n"
                    "        getattr(value, name, None)\n"
                    "    return value\n\n"
                    "def open_selector(value, name):\n"
                    "    return getattr(value, name, None)\n"
                ),
            )
            file_disposition = self._python_file_disposition(root / "src" / "app.py")
            raw = discover_python_implementation_surfaces(
                root=root,
                file_disposition=file_disposition,
            )
            by_symbol = {surface.symbol: surface for surface in raw.surfaces}
            bounded = by_symbol["bounded"]
            open_selector = by_symbol["open_selector"]
            bounded_key = implementation_surface_key("src/app.py", "bounded")
            open_key = implementation_surface_key("src/app.py", "open_selector")

            self.assertEqual(
                dict(bounded.dynamic_selector_values)["getattr"],
                ("alpha", "beta"),
            )
            self.assertNotIn("getattr", dict(open_selector.dynamic_selector_values))

            def contract(
                surface: ImplementationSurface,
                key: str,
                values: tuple[str, ...],
                *,
                owner_surface_id: str | None = None,
                structure_fingerprint: str | None = None,
            ) -> DynamicSelectorContract:
                return DynamicSelectorContract(
                    surface_key=key,
                    owner_surface_id=owner_surface_id or surface.surface_id,
                    surface_structure_fingerprint=(
                        structure_fingerprint or surface.structure_fingerprint
                    ),
                    selector_source_fingerprint=dict(
                        surface.dynamic_selector_source_fingerprints
                    )["getattr"],
                    operation="getattr",
                    selector_values=values,
                    rationale="fixture finite selector contract",
                )

            dispositions = {
                implementation_surface_key("src/app.py", surface.symbol): (
                    IMPLEMENTATION_DISPOSITION_MODEL
                )
                for surface in raw.surfaces
            }
            valid = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                dynamic_selector_contracts=(
                    contract(bounded, bounded_key, ("alpha", "beta")),
                ),
            )
            valid_codes = {finding.code for finding in valid.findings}
            self.assertNotIn("dynamic_selector_contract_values_mismatch", valid_codes)
            self.assertFalse(
                any(
                    finding.code == "dynamic_python_surface"
                    and finding.surface_id == bounded.surface_id
                    for finding in valid.findings
                )
            )
            self.assertTrue(
                any(
                    finding.code == "dynamic_python_surface"
                    and finding.surface_id == open_selector.surface_id
                    for finding in valid.findings
                )
            )

            wrong_values = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                dynamic_selector_contracts=(
                    contract(bounded, bounded_key, ("alpha",)),
                ),
            )
            self.assertIn(
                "dynamic_selector_contract_values_mismatch",
                {finding.code for finding in wrong_values.findings},
            )

            stale = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                dynamic_selector_contracts=(
                    contract(
                        bounded,
                        bounded_key,
                        ("alpha", "beta"),
                        structure_fingerprint="sha256:" + "0" * 64,
                    ),
                ),
            )
            self.assertIn(
                "dynamic_selector_contract_stale",
                {finding.code for finding in stale.findings},
            )

            wrong_owner = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                dynamic_selector_contracts=(
                    contract(
                        bounded,
                        bounded_key,
                        ("alpha", "beta"),
                        owner_surface_id="implementation-surface:" + "0" * 64,
                    ),
                ),
            )
            self.assertIn(
                "dynamic_selector_contract_owner_mismatch",
                {finding.code for finding in wrong_owner.findings},
            )

            open_contract = project_python_implementation_observation(
                raw,
                surface_dispositions=dispositions,
                dynamic_selector_contracts=(
                    contract(open_selector, open_key, ("alpha", "beta")),
                ),
            )
            self.assertIn(
                "dynamic_selector_contract_unbounded",
                {finding.code for finding in open_contract.findings},
            )

            with self.assertRaisesRegex(
                ImplementationInventoryError,
                "finite non-empty selector set",
            ):
                contract(bounded, bounded_key, ())

    def test_static_dynamic_selector_contracts_cover_comprehensions_without_authored_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source=(
                    "FIELDS = ('alpha', 'beta')\n\n"
                    "def projected(value):\n"
                    "    return tuple(getattr(value, name, None) for name in FIELDS)\n\n"
                    "def open_selector(value, name):\n"
                    "    return getattr(value, name, None)\n"
                ),
            )
            raw = discover_python_implementation_surfaces(
                root=root,
                file_disposition=self._python_file_disposition(
                    root / "src" / "app.py"
                ),
            )
            by_symbol = {surface.symbol: surface for surface in raw.surfaces}
            external_owner_id = "implementation-surface:" + "1" * 64
            contracts = derive_static_dynamic_selector_contracts(
                raw,
                supporting_owners={
                    "src/app.py#projected": external_owner_id,
                },
            )

            self.assertEqual(
                tuple(
                    (contract.surface_key, contract.operation, contract.selector_values)
                    for contract in contracts
                ),
                (("src/app.py#projected", "getattr", ("alpha", "beta")),),
            )
            self.assertEqual(
                contracts[0].owner_surface_id,
                external_owner_id,
            )
            projected = project_python_implementation_observation(
                raw,
                surface_dispositions={
                    implementation_surface_key("src/app.py", surface.symbol): (
                        IMPLEMENTATION_DISPOSITION_MODEL
                    )
                    for surface in raw.surfaces
                },
                supporting_owners={
                    "src/app.py#projected": external_owner_id,
                },
                dynamic_selector_contracts=contracts,
            )
            dynamic_gaps = {
                finding.surface_id
                for finding in projected.findings
                if finding.code == "dynamic_python_surface"
            }
            self.assertNotIn(by_symbol["projected"].surface_id, dynamic_gaps)
            self.assertIn(by_symbol["open_selector"].surface_id, dynamic_gaps)

    def test_serialization_is_canonical_strict_and_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            inventory = self._complete_inventory(root)
            first = serialize_implementation_surface_inventory(inventory)
            second = serialize_implementation_surface_inventory(inventory)
            self.assertEqual(first, second)

            path = root / "inventory.json"
            write_implementation_surface_inventory(inventory, path)
            loaded = load_implementation_surface_inventory(path)
            self.assertEqual(loaded, inventory)
            self.assertEqual(loaded.inventory_fingerprint, inventory.inventory_fingerprint)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["unexpected"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ImplementationInventoryError, "fields differ"):
                load_implementation_surface_inventory(path)

            payload.pop("unexpected")
            payload["inventory_fingerprint"] = "sha256:" + ("0" * 64)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ImplementationInventoryError, "fingerprint mismatch"):
                load_implementation_surface_inventory(path)

    def test_supporting_owner_can_use_one_exact_cross_file_surface_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(
                Path(temporary),
                source="def _helper(value):\n    return value\n",
            )
            owner_path = root / "src" / "owner.py"
            owner_path.write_text(
                "def run(value):\n    return value\n",
                encoding="utf-8",
            )
            self._git_add(root)
            owner_id = implementation_surface_id(
                "src/owner.py",
                "run",
                "function",
            )
            keys = {
                (path, symbol): implementation_surface_key(path, symbol)
                for path, symbols in {
                    "src/app.py": ("<module>", "_helper"),
                    "src/owner.py": ("<module>", "run"),
                }.items()
                for symbol in symbols
            }
            dispositions = {
                keys[("src/app.py", "<module>")]: IMPLEMENTATION_DISPOSITION_SUPPORTING,
                keys[("src/app.py", "_helper")]: IMPLEMENTATION_DISPOSITION_SUPPORTING,
                keys[("src/owner.py", "<module>")]: IMPLEMENTATION_DISPOSITION_SUPPORTING,
                keys[("src/owner.py", "run")]: IMPLEMENTATION_DISPOSITION_MODEL,
            }
            supporting_owners = {
                key: owner_id
                for key, disposition in dispositions.items()
                if disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING
            }
            file_dispositions = tuple(
                ImplementationFileDisposition(
                    path=relative_path,
                    category="production",
                    content_fingerprint=source_file_fingerprint(root / relative_path),
                    disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                    reason="cross-file owner fixture",
                    requires_adapter=True,
                    adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                )
                for relative_path in ("src/app.py", "src/owner.py")
            )

            inventory = build_implementation_surface_inventory(
                root,
                self._boundary(),
                inventory_id="inventory:cross-file-owner",
                file_dispositions=file_dispositions,
                surface_dispositions=dispositions,
                supporting_owners=supporting_owners,
                discovery_adapters={
                    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                },
            )

            report = review_implementation_surface_inventory(inventory, root=root)
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(
                {
                    surface.owning_surface_id
                    for surface in inventory.surfaces
                    if surface.disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING
                },
                {owner_id},
            )

            with self.assertRaisesRegex(
                ImplementationInventoryError,
                "unknown owner",
            ):
                build_implementation_surface_inventory(
                    root,
                    self._boundary(),
                    inventory_id="inventory:unknown-cross-file-owner",
                    file_dispositions=file_dispositions,
                    surface_dispositions=dispositions,
                    supporting_owners={
                        key: "implementation-surface:" + "0" * 64
                        for key in supporting_owners
                    },
                    discovery_adapters={
                        PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
                    },
                )

    def test_read_only_audit_does_not_change_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary), source=SOURCE)
            inventory = self._complete_inventory(root)
            path = root / "inventory.json"
            write_implementation_surface_inventory(inventory, path)
            before = self._file_snapshot(root)

            report = audit_implementation_surface_inventory(path, root=root)

            after = self._file_snapshot(root)
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(before, after)

    def _complete_inventory(self, root: Path):
        path = root / "src" / "app.py"
        keys = {
            symbol: implementation_surface_key("src/app.py", symbol)
            for symbol in ("<module>", "_normalize", "Service", "Service.save", "main")
        }
        dispositions = {
            keys["<module>"]: IMPLEMENTATION_DISPOSITION_MODEL,
            keys["_normalize"]: IMPLEMENTATION_DISPOSITION_SUPPORTING,
            keys["Service"]: IMPLEMENTATION_DISPOSITION_MODEL,
            keys["Service.save"]: IMPLEMENTATION_DISPOSITION_MODEL,
            keys["main"]: IMPLEMENTATION_DISPOSITION_MODEL,
        }
        return build_implementation_surface_inventory(
            root,
            self._boundary(),
            inventory_id="inventory:complete",
            file_dispositions=(self._python_file_disposition(path),),
            surface_dispositions=dispositions,
            supporting_owners={keys["_normalize"]: keys["Service.save"]},
            discovery_adapters={
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
            },
        )

    @staticmethod
    def _boundary() -> SoftwareBoundary:
        return SoftwareBoundary(
            "boundary:test",
            "revision:test",
            production_patterns=("src/**/*.py",),
        )

    @staticmethod
    def _python_file_disposition(path: Path) -> ImplementationFileDisposition:
        return ImplementationFileDisposition(
            path="src/app.py",
            category="production",
            content_fingerprint=source_file_fingerprint(path),
            disposition=IMPLEMENTATION_DISPOSITION_MODEL,
            reason="production implementation",
            requires_adapter=True,
            adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        )

    @staticmethod
    def _repository(root: Path, *, source: str) -> Path:
        source_path = root / "src" / "app.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source, encoding="utf-8")
        subprocess.run(("git", "init", "-q"), cwd=root, check=True)
        subprocess.run(
            ("git", "config", "user.email", "fixture@example.invalid"),
            cwd=root,
            check=True,
        )
        subprocess.run(
            ("git", "config", "user.name", "FlowGuard Fixture"),
            cwd=root,
            check=True,
        )
        ImplementationInventoryTests._git_add(root)
        return root

    @staticmethod
    def _workflow_repository(root: Path) -> Path:
        workflow_path = root / "workflow" / "approval.workflow.json"
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text(
            '{"states":["pending","approved"],"transition":"approve"}\n',
            encoding="utf-8",
        )
        subprocess.run(("git", "init", "-q"), cwd=root, check=True)
        subprocess.run(
            ("git", "config", "user.email", "fixture@example.invalid"),
            cwd=root,
            check=True,
        )
        subprocess.run(
            ("git", "config", "user.name", "FlowGuard Fixture"),
            cwd=root,
            check=True,
        )
        ImplementationInventoryTests._git_add(root)
        return root

    @staticmethod
    def _git_add(root: Path) -> None:
        subprocess.run(("git", "add", "."), cwd=root, check=True)
        subprocess.run(("git", "commit", "-q", "-m", "fixture"), cwd=root, check=True)

    @staticmethod
    def _file_snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }


if __name__ == "__main__":
    unittest.main()
