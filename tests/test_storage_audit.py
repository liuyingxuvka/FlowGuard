import os
import json
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from flowguard.storage_audit import _extended_lstat_path, audit_storage
from flowguard.evidence_lifecycle import apply_evidence_gc, EvidenceLifecycleError
from flowguard.__main__ import main


class StorageAuditTests(unittest.TestCase):
    def test_single_walk_has_zero_content_reads_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".flowguard"
            (root / "models" / "owners").mkdir(parents=True)
            (root / "evidence" / "current-head").mkdir(parents=True)
            (root / "models" / "owners" / "model.py").write_text("model", encoding="utf-8")
            (root / "evidence" / "current-head" / "current.json").write_text("{}", encoding="utf-8")
            report = audit_storage(root)

        self.assertEqual("passed", report.status)
        self.assertEqual(1, report.directory_walk_count)
        self.assertEqual(0, report.content_file_read_count)
        self.assertEqual(0, report.content_hash_read_count)
        self.assertEqual(0, report.content_bytes_read)
        self.assertEqual(1, report.role_counts["models"]["files"])
        self.assertEqual(1, report.lifecycle_counts["current"]["files"])

    def test_largest_sample_is_bounded_and_unknown_evidence_is_conservative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".flowguard"
            evidence = root / "evidence"
            evidence.mkdir(parents=True)
            for index in range(5):
                (evidence / f"payload-{index}.json").write_bytes(b"x" * (index + 1))
            report = audit_storage(root, max_largest_items=2)

        self.assertEqual(2, len(report.largest_items))
        self.assertEqual(3, report.largest_items_omitted)
        self.assertEqual(5, report.lifecycle_counts["unknown"]["files"])

    def test_missing_root_blocks_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit_storage(Path(directory) / "missing")
        self.assertEqual("blocked", report.status)
        self.assertEqual(0, report.directory_walk_count)
        self.assertIn("root_missing", {item["code"] for item in report.findings})

    def test_retired_gc_plan_route_is_rejected_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / ".flowguard" / "evidence"
            evidence.mkdir(parents=True)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "evidence-gc-plan",
                        "--root",
                        str(evidence),
                        "--storage-audit",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

            self.assertEqual(2, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertIn("unknown operation", payload["error"])

    @unittest.skipUnless(os.name == "nt", "Windows extended paths are the subject of this regression")
    def test_long_history_path_uses_metadata_only_extended_path(self):
        directory = Path(tempfile.mkdtemp())
        try:
            root = Path(directory) / ".flowguard"
            deep_dir = root / "history"
            for index in range(24):
                deep_dir /= f"segment-{index:02d}-long-name"
            target = deep_dir / "result.json"
            os.makedirs(_extended_lstat_path(deep_dir), exist_ok=True)
            with open(_extended_lstat_path(target), "wb") as handle:
                handle.write(b"{}")

            report = audit_storage(root)

            self.assertEqual("passed", report.status)
            self.assertEqual(1, report.role_counts["history"]["files"])
            self.assertEqual(0, report.content_file_read_count)
            self.assertEqual(0, report.content_hash_read_count)
        finally:
            shutil.rmtree(_extended_lstat_path(directory), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
