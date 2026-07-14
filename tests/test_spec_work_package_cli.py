import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flowguard.__main__ import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _project() -> tempfile.TemporaryDirectory:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    _write(root / "flowguard/source.py", "VALUE = 1\n")
    _write(root / "openspec/changes/cli-change/tasks.md", "# Tasks\n\n- [x] 1.1 CLI coverage\n")
    _write(
        root / "openspec/changes/cli-change/verification-contract.yaml",
        """contract_version: 3
obligations:
  - id: req.cli
    source: specs/cli/spec.md
    claim: CLI JSON is canonical.
    evidence: [check.cli]
checks:
  - id: check.cli
    kind: command
    command: python
    args: [-c, 'pass']
    covers: [req.cli]
    required: true
    expected:
      exit_code: 0
""",
    )
    bindings = {
        "packages": [
            {
                "provider_id": "openspec",
                "work_package_id": "cli-change",
                "task_binding_rules": [
                    {"task_prefix": "1.", "obligation_ids": ["req.cli"]}
                ],
                "check_policies": [
                    {
                        "check_id": "check.cli",
                        "validation_obligation_ids": ["validation:cli"],
                    }
                ],
            }
        ]
    }
    _write(
        root / ".flowguard/spec_provider_work_packages/bindings.json",
        json.dumps(bindings, indent=2) + "\n",
    )
    return temporary


def _invoke(arguments: list[str]) -> tuple[int, dict]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = main(arguments)
    return exit_code, json.loads(stream.getvalue())


class SpecWorkPackageCliTests(unittest.TestCase):
    def test_run_inherits_the_complete_canonical_owner_declaration(self) -> None:
        consumer = SimpleNamespace(
            check_id="owner.full",
            semantic_check_id="consumer.semantic",
            validation_obligation_ids=("consumer.validation",),
            depends_on=(),
            timeout_seconds=600,
            expected_exit_code=0,
            cross_change_safe=False,
            command=(),
        )
        owner = SimpleNamespace(
            check_id="owner.full",
            semantic_check_id="owner.semantic",
            validation_obligation_ids=("owner.validation",),
            depends_on=("owner.model",),
            timeout_seconds=7200,
            expected_exit_code=0,
            cross_change_safe=True,
            command=(sys.executable, "-c", "pass"),
        )
        result = SimpleNamespace(
            ok=True,
            to_dict=lambda: {"ok": True, "state": "executed"},
        )
        with (
            patch(
                "flowguard.spec_providers.load_openspec_work_package",
                return_value=SimpleNamespace(checks=(consumer,)),
            ),
            patch(
                "flowguard.spec_providers.load_openspec_canonical_checks",
                return_value=(owner,),
            ),
            patch("flowguard.spec_check_cache.run_spec_check", return_value=result) as run,
        ):
            exit_code, payload = _invoke(
                [
                    "spec-check-run",
                    "--provider",
                    "openspec",
                    "--work-package",
                    "change-one",
                    "--check-id",
                    "owner.full",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        call = run.call_args.kwargs
        self.assertEqual(call["semantic_id"], "owner.semantic")
        self.assertEqual(call["command"], owner.command)
        self.assertEqual(call["validation_obligation_ids"], ("owner.validation",))
        self.assertEqual(call["depends_on"], ("owner.model",))
        self.assertEqual(call["timeout_seconds"], 7200)
        self.assertTrue(call["cross_change_safe"])

    def test_audit_begin_run_and_close_emit_machine_json(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        exit_code, audit = _invoke(
            [
                "spec-work-package-audit",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--change",
                "cli-change",
                "--json",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["artifact_type"], "flowguard_spec_work_package_audit")
        self.assertEqual(audit["packages"][0]["behavior_plane"], "development_process")

        exit_code, begun = _invoke(
            [
                "spec-session-begin",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--work-package",
                "cli-change",
                "--json",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(begun["state"], "begun")
        self.assertTrue(begun["begin_fingerprint"].startswith("sha256:"))

        exit_code, executed = _invoke(
            [
                "spec-check-run",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--work-package",
                "cli-change",
                "--check-id",
                "check.cli",
                "--semantic-id",
                "semantic:cli",
                "--validation-obligation",
                "validation:cli",
                "--timeout-seconds",
                "5",
                "--json",
                "--",
                sys.executable,
                "-c",
                "pass",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(executed["state"], "executed")
        self.assertEqual(executed["terminal_status"], "pass")
        self.assertTrue(executed["receipt_id"])

        exit_code, closed = _invoke(
            [
                "spec-session-close",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--work-package",
                "cli-change",
                "--json",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(closed["state"], "closed")
        self.assertEqual(closed["begin_fingerprint"], closed["post_fingerprint"])

    def test_cli_dependency_failure_is_explicit_not_run_json(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        _invoke(
            [
                "spec-session-begin",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--work-package",
                "cli-change",
            ]
        )
        exit_code, result = _invoke(
            [
                "spec-check-run",
                "--root",
                str(root),
                "--provider",
                "openspec",
                "--work-package",
                "cli-change",
                "--check-id",
                "check.cli",
                "--semantic-id",
                "semantic:cli",
                "--validation-obligation",
                "validation:cli",
                "--depends-on",
                "check.parent",
                "--",
                sys.executable,
                "-c",
                "raise SystemExit('must not run')",
            ]
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["state"], "not-run")
        self.assertEqual(result["terminal_status"], "not_run_due_to_dependency")
        self.assertIn("dependency_not_passed:check.parent", result["blockers"])


if __name__ == "__main__":
    unittest.main()
