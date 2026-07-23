import tempfile
import unittest
from pathlib import Path

from flowguard.project_manifest import (
    ProjectManifestError,
    atomic_write_project_manifest,
    manifest_text_fingerprint,
    project_manifest_lock,
    read_manifest_text,
)


class ProjectManifestTests(unittest.TestCase):
    def test_compare_and_swap_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".flowguard" / "project.toml"
            original = "[flowguard]\nversion = \"one\"\n"
            path.parent.mkdir()
            path.write_text(original, encoding="utf-8")

            result = atomic_write_project_manifest(
                path,
                "[flowguard]\nversion = \"two\"\n",
                expected_fingerprint=manifest_text_fingerprint(original),
            )

            self.assertEqual(
                result,
                manifest_text_fingerprint(read_manifest_text(path)),
            )
            self.assertIn('version = "two"', read_manifest_text(path))
            self.assertFalse(path.with_suffix(".toml.lock").exists())

    def test_stale_expected_fingerprint_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.toml"
            path.write_text("current\n", encoding="utf-8")

            with self.assertRaisesRegex(ProjectManifestError, "changed"):
                atomic_write_project_manifest(
                    path,
                    "candidate\n",
                    expected_fingerprint=manifest_text_fingerprint("old\n"),
                )

            self.assertEqual("current\n", path.read_text(encoding="utf-8"))

    def test_shared_lock_blocks_second_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.toml"
            with project_manifest_lock(path):
                with self.assertRaisesRegex(ProjectManifestError, "locked"):
                    atomic_write_project_manifest(
                        path,
                        "candidate\n",
                        expected_fingerprint=manifest_text_fingerprint(""),
                    )


if __name__ == "__main__":
    unittest.main()
