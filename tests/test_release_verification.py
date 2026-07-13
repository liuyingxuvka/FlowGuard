import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

from flowguard.release_verification import (
    REQUIRED_UNIFIED_CHILDREN,
    _command_runner,
    _remote_tag_commit,
    verify_local_release,
)


class ReleaseVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / ".flowguard" / "evidence" / "release" / "v1.2.3-local").mkdir(parents=True)
        (self.root / "dist").mkdir()
        (self.root / "flowguard").mkdir()
        (self.root / "flowguard" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "pyproject.toml").write_text('[project]\nname="flowguard"\nversion="1.2.3"\n', encoding="utf-8")
        (self.root / ".flowguard" / "project.toml").write_text(
            '[flowguard]\npackage_version="1.2.3"\nschema_version="1.0"\n',
            encoding="utf-8",
        )
        (self.root / "README.md").write_text("FlowGuard 1.2.3", encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("## [1.2.3]", encoding="utf-8")
        self.evidence = self.root / ".flowguard" / "evidence" / "release" / "v1.2.3-local" / "result.json"
        self.evidence.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "broad_success": True,
                    "blockers": [],
                    "skipped_checks": [],
                    "children": [
                        {
                            "child_id": child,
                            "status": "pass",
                            "receipt_id": "receipt:skillguard-parent",
                        }
                        for child in REQUIRED_UNIFIED_CHILDREN
                    ],
                }
            ),
            encoding="utf-8",
        )
        wheel = self.root / "dist" / "flowguard-1.2.3-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("flowguard-1.2.3.dist-info/METADATA", "Name: flowguard\nVersion: 1.2.3\n")
        sdist = self.root / "dist" / "flowguard-1.2.3.tar.gz"
        with tarfile.open(sdist, "w:gz"):
            pass
        self.parent_receipt_current = True

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _verify(self):
        return verify_local_release(
            self.root,
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
            receipt_consumer=lambda _root, _receipt_id: SimpleNamespace(
                ok=self.parent_receipt_current,
                findings=() if self.parent_receipt_current else ("portable_source_manifest_not_current",),
                minimum_revalidation=() if self.parent_receipt_current else ("owner.full",),
            ),
        )

    def test_local_release_requires_all_exact_children_and_built_artifacts(self) -> None:
        report = self._verify()
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual("pass", report.status)

    def test_missing_unified_child_blocks_release(self) -> None:
        payload = json.loads(self.evidence.read_text(encoding="utf-8"))
        payload["children"] = payload["children"][:-1]
        self.evidence.write_text(json.dumps(payload), encoding="utf-8")
        report = self._verify()
        self.assertFalse(report.ok)
        self.assertIn("release.local_evidence", report.to_dict()["blockers"])

    def test_wheel_metadata_version_mismatch_blocks_release(self) -> None:
        wheel = next((self.root / "dist").glob("*.whl"))
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("flowguard-1.2.3.dist-info/METADATA", "Name: flowguard\nVersion: 9.9.9\n")
        report = self._verify()
        self.assertFalse(report.ok)
        self.assertIn("release.built_artifacts", report.to_dict()["blockers"])

    def test_stale_parent_receipt_blocks_release(self) -> None:
        self.parent_receipt_current = False
        report = self._verify()
        self.assertFalse(report.ok)
        self.assertIn("release.evidence_freshness", report.to_dict()["blockers"])

    def test_openspec_bookkeeping_after_unified_result_does_not_stale_release(self) -> None:
        change = self.root / "openspec" / "changes" / "release-closure"
        change.mkdir(parents=True)
        bookkeeping = (change / "tasks.md", change / "verification-report.json")
        evidence_time = self.evidence.stat().st_mtime_ns
        for path in bookkeeping:
            path.write_text("{}\n" if path.suffix == ".json" else "- [x] done\n", encoding="utf-8")
            os.utime(path, ns=(evidence_time + 1_000_000_000, evidence_time + 1_000_000_000))
        report = self._verify()
        self.assertTrue(report.ok, report.to_dict())

    def test_canonical_openspec_spec_after_unified_result_stales_release(self) -> None:
        spec = self.root / "openspec" / "specs" / "release-contract" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# changed contract\n", encoding="utf-8")
        evidence_time = self.evidence.stat().st_mtime_ns
        os.utime(spec, ns=(evidence_time + 1_000_000_000, evidence_time + 1_000_000_000))
        self.parent_receipt_current = False
        report = self._verify()
        self.assertFalse(report.ok)
        self.assertIn("release.evidence_freshness", report.to_dict()["blockers"])

    @mock.patch("flowguard.release_verification.subprocess.run")
    @mock.patch("flowguard.release_verification.shutil.which")
    def test_command_runner_resolves_windows_pathext_shim(self, which, run) -> None:
        resolved = r"C:\tools\git.CMD"
        which.return_value = resolved
        completed = subprocess.CompletedProcess([resolved, "--version"], 0, "git version", "")
        run.return_value = completed

        result = _command_runner(("git", "--version"), self.root)

        self.assertIs(completed, result)
        which.assert_called_once_with("git")
        run.assert_called_once_with(
            [resolved, "--version"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )

    @mock.patch("flowguard.release_verification.subprocess.run")
    @mock.patch("flowguard.release_verification.shutil.which", return_value=None)
    def test_command_runner_reports_missing_executable_without_crashing(self, _which, run) -> None:
        run.side_effect = FileNotFoundError("missing command")

        result = _command_runner(("missing-tool", "--version"), self.root)

        self.assertEqual(127, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("missing command", result.stderr)

    def test_remote_tag_commit_prefers_annotated_tag_peeled_commit(self) -> None:
        output = (
            "tag-object refs/tags/v1.2.3\n"
            "release-commit refs/tags/v1.2.3^{}\n"
            "other-object refs/tags/v1.2.30\n"
        )

        commit, refs = _remote_tag_commit(output, "v1.2.3")

        self.assertEqual("release-commit", commit)
        self.assertEqual("tag-object", refs["refs/tags/v1.2.3"])

    def test_remote_tag_commit_supports_lightweight_tag(self) -> None:
        commit, refs = _remote_tag_commit("release-commit refs/tags/v1.2.3\n", "v1.2.3")

        self.assertEqual("release-commit", commit)
        self.assertEqual({"refs/tags/v1.2.3": "release-commit"}, refs)


if __name__ == "__main__":
    unittest.main()
