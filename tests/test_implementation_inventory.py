import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from flowguard.implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    ImplementationFileDisposition,
    ImplementationInventoryError,
    SoftwareBoundary,
    audit_implementation_surface_inventory,
    build_implementation_surface_inventory,
    implementation_surface_key,
    load_implementation_surface_inventory,
    review_implementation_surface_inventory,
    serialize_implementation_surface_inventory,
    write_implementation_surface_inventory,
)
from flowguard.implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    discover_python_implementation_surfaces,
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
