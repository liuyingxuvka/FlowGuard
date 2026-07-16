import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _run_openspec(root: Path, *args: str) -> dict:
    executable = shutil.which("openspec")
    if not executable:
        raise unittest.SkipTest("OpenSpec CLI is not installed")
    environment = dict(os.environ)
    environment["OPENSPEC_TELEMETRY"] = "0"
    completed = subprocess.run(
        [executable, *args],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"OpenSpec did not return canonical JSON (exit={completed.returncode}): "
            f"{completed.stdout[-1000:]} {completed.stderr[-1000:]}"
        ) from exc
    if completed.returncode != 0:
        raise AssertionError(
            f"OpenSpec failed (exit={completed.returncode}): "
            f"issues={json.dumps(payload.get('issues', []), ensure_ascii=False)}; "
            f"tail={json.dumps(payload, ensure_ascii=False)[-2000:]}"
        )
    return payload


class OpenSpecFrozenResumeTests(unittest.TestCase):
    def test_resume_reuses_unchanged_independent_owner_and_reruns_changed_owner(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node.js is not installed")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec/changes/frozen-resume"
            _write(change / "tasks.md", "## 1. Test\n\n- [x] 1.1 Verify frozen resume\n")
            _write(root / "source/owner.txt", "owner-v1\n")
            _write(root / "source/child.txt", "child-v1\n")
            _write(
                change / "verification-contract.yaml",
                """contract_version: 1
change: frozen-resume
obligations:
  - id: req.resume
    source: specs/resume/spec.md
    claim: Frozen resume reuses only an exact current independent owner.
    required: true
    evidence: [check.owner, check.child]
checks:
  - id: check.owner
    kind: command
    semantic_check_id: test.frozen.owner
    execution_id: test.frozen.owner.v1
    validation_scope: full
    snapshot_policy: frozen
    toolchain_identity: node
    input_selectors: [source/owner.txt]
    depends_on_receipts: []
    command: node
    args: [-e, "process.stdout.write('child')"]
    timeout_seconds: 30
    required: true
    covers: [req.resume]
    expected: {exit_code: 0}
  - id: check.child
    kind: command
    semantic_check_id: test.frozen.child
    execution_id: test.frozen.child.v1
    validation_scope: full
    snapshot_policy: frozen
    toolchain_identity: node
    input_selectors: [source/child.txt]
    depends_on_receipts: []
    command: node
    args: [-e, 'process.exit(0)']
    timeout_seconds: 30
    required: true
    covers: [req.resume]
    expected: {exit_code: 0}
freshness:
  watch:
    - openspec/changes/frozen-resume/verification-contract.yaml
    - openspec/changes/frozen-resume/tasks.md
    - source/*.txt
  exclude:
    - '**/verification-report.json'
    - '**/verification-receipts/**'
""",
            )

            first = _run_openspec(root, "verify", "frozen-resume", "--mode", "full", "--json")
            first_checks = {row["id"]: row for row in first["checks"]}
            self.assertEqual("pass", first["status"])
            self.assertEqual("executed", first_checks["check.owner"]["accounting"])
            self.assertEqual("executed", first_checks["check.child"]["accounting"])

            _write(root / "source/child.txt", "child-v2\n")
            resumed = _run_openspec(root, "verify", "frozen-resume", "--resume", "--json")
            resumed_checks = {row["id"]: row for row in resumed["checks"]}

            self.assertEqual("pass", resumed["status"])
            self.assertEqual(2, resumed["run"]["attempt"])
            self.assertEqual(first["run"]["id"], resumed["run"]["resumed_from_run_id"])
            self.assertEqual("reused", resumed_checks["check.owner"]["accounting"])
            self.assertEqual("executed", resumed_checks["check.child"]["accounting"])
            self.assertEqual(
                first_checks["check.owner"]["receipt_id"],
                resumed_checks["check.owner"]["receipt_id"],
            )
            self.assertNotEqual(
                first_checks["check.child"]["receipt_id"],
                resumed_checks["check.child"]["receipt_id"],
            )
            self.assertEqual(
                first["run"]["snapshot_manifest_id"],
                resumed_checks["check.owner"]["reused_from_snapshot_manifest_id"],
            )


if __name__ == "__main__":
    unittest.main()
