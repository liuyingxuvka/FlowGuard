from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from flowguard.validation_ownership import (
    ValidationOwnerContract,
    build_validation_owner_plan,
    build_validation_parent_current,
    manifest_fingerprint,
    resolve_input_manifest,
    topological_owner_contracts,
    validation_input_manifest,
)


def contract(
    owner_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    resources: tuple[str, ...] = (),
    external: tuple[tuple[str, str], ...] = (),
) -> ValidationOwnerContract:
    return ValidationOwnerContract(
        owner_id=owner_id,
        command=("python", "-c", "raise SystemExit(0)"),
        input_patterns=("source.txt",),
        obligation_ids=(f"obligation:{owner_id}",),
        dependency_owner_ids=dependencies,
        resource_keys=resources,
        external_component_bindings=external,
    )


class ValidationExecutionOwnershipTests(unittest.TestCase):
    def test_unknown_dependency_and_cycle_block(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            topological_owner_contracts((contract("a", dependencies=("missing",)),))
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            topological_owner_contracts(
                (
                    contract("a", dependencies=("b",)),
                    contract("b", dependencies=("a",)),
                )
            )

    def test_shared_resource_must_be_dependency_ordered(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource conflict"):
            topological_owner_contracts(
                (
                    contract("a", resources=("workspace",)),
                    contract("b", resources=("workspace",)),
                )
            )
        ordered = topological_owner_contracts(
            (
                contract("b", dependencies=("a",), resources=("workspace",)),
                contract("a", resources=("workspace",)),
            )
        )
        self.assertEqual(("a", "b"), tuple(item.owner_id for item in ordered))

    def test_external_component_mapping_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            digest = "sha256:" + "1" * 64
            with self.assertRaisesRegex(ValueError, "mapping is not exact"):
                build_validation_owner_plan(
                    root,
                    (contract("a"),),
                    receipt_root=root / "receipts",
                    required_external_components={"shadow:skills": digest},
                )
            plan = build_validation_owner_plan(
                root,
                (contract("a", external=(("shadow:skills", digest),)),),
                receipt_root=root / "receipts",
                required_external_components={"shadow:skills": digest},
            )
            self.assertFalse(plan.blocked)

    def test_source_drift_after_plan_freeze_blocks_parent_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            plan = build_validation_owner_plan(
                root,
                (contract("a"),),
                receipt_root=root / "receipts",
            )
            (root / "source.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed after owner-plan freeze"):
                build_validation_parent_current(root, plan)

    def test_evidence_outputs_do_not_refresh_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            before = manifest_fingerprint(validation_input_manifest(root))
            output = root / ".flowguard" / "evidence" / "run" / "result.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"status":"pass"}\n', encoding="utf-8")
            after = manifest_fingerprint(validation_input_manifest(root))
            self.assertEqual(before, after)

    def test_git_candidates_preserve_recursive_globs_without_walking_ignored_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            direct = root / "flowguard" / "direct.py"
            nested = root / "flowguard" / "nested" / "deep.py"
            ignored = root / ".flowguard" / "evidence" / "run" / "noise.py"
            lookalike = root / ".agents" / "skills" / "flowguard" / "noise.py"
            direct.parent.mkdir(parents=True)
            nested.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            lookalike.parent.mkdir(parents=True)
            direct.write_text("DIRECT = True\n", encoding="utf-8")
            nested.write_text("DEEP = True\n", encoding="utf-8")
            ignored.write_text("NOISE = True\n", encoding="utf-8")
            lookalike.write_text("LOOKALIKE = True\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                ".flowguard/evidence/\n",
                encoding="utf-8",
            )

            rows = resolve_input_manifest(
                root,
                ("flowguard/**/*.py", ".flowguard/**/*.py"),
            )
            paths = {row["path"] for row in rows}

            self.assertIn("flowguard/direct.py", paths)
            self.assertIn("flowguard/nested/deep.py", paths)
            self.assertNotIn(
                ".flowguard/evidence/run/noise.py",
                paths,
            )
            self.assertNotIn(".agents/skills/flowguard/noise.py", paths)

    @staticmethod
    def _repository(root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "source.txt").write_text("base\n", encoding="utf-8")
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
        subprocess.run(("git", "add", "."), cwd=root, check=True)
        subprocess.run(
            ("git", "commit", "-q", "-m", "fixture"),
            cwd=root,
            check=True,
        )
        return root


if __name__ == "__main__":
    unittest.main()
