import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from flowguard.release_verification import (
    RELEASE_PHASE_LOCAL_CANDIDATE,
    RELEASE_PHASE_PUBLISHED,
    RELEASE_PHASE_TAG,
    RELEASE_VERIFICATION_SCHEMA,
    _command_runner,
    _model_authority_git_reachability_check,
    _remote_tag_commit,
    verify_local_candidate,
    verify_published_release,
    verify_tagged_release,
)
from flowguard.validation_ownership import (
    OWNER_EXECUTE,
    ValidationOwnerContract,
    ValidationOwnerPlanRow,
    build_owner_current,
    save_owner_receipt,
    save_parent_receipt,
)
from flowguard.validation_results import ValidationChildResult
from scripts import verify_flowguard_release as release_cli


class ReleaseVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".flowguard").mkdir()
        (self.root / ".flowguard" / "fixture-model").mkdir()
        (self.root / ".flowguard" / "model-mesh" / "snapshots").mkdir(
            parents=True
        )
        (self.root / ".flowguard" / "model-mesh" / "bootstraps").mkdir()
        (self.root / "dist").mkdir()
        (self.root / "flowguard").mkdir()
        (self.root / "flowguard" / "__init__.py").write_bytes(
            b"SCHEMA_VERSION = '1.0'\n"
        )
        (self.root / "pyproject.toml").write_bytes(
            b'[project]\nname="flowguard"\nversion="1.2.3"\n'
        )
        (self.root / ".flowguard" / "project.toml").write_bytes(
            b'[flowguard]\npackage_version="1.2.3"\nschema_version="1.0"\n'
            b'\n[model_authority]\n'
            b'observed_snapshot_path=".flowguard/model-mesh/snapshots/'
            + (b"a" * 64)
            + b'.json"\n'
            + b'observed_snapshot_fingerprint="sha256:'
            + (b"a" * 64)
            + b'"\n'
            + b'generation=1\n'
            + b'accepted_revision_set_fingerprint="sha256:'
            + (b"b" * 64)
            + b'"\n'
            + b'activation_receipt_fingerprint="sha256:'
            + (b"b" * 64)
            + b'"\n'
            + b'previous_snapshot_fingerprint=""\n'
        )
        model_path = ".flowguard/fixture-model/model.py"
        runner_path = ".flowguard/fixture-model/run_checks.py"
        (self.root / model_path).write_bytes(b"MODEL = 'fixture'\n")
        (self.root / runner_path).write_bytes(b"print('fixture')\n")
        (
            self.root
            / ".flowguard"
            / "model-mesh"
            / "snapshots"
            / (("a" * 64) + ".json")
        ).write_text(
            json.dumps(
                {
                    "model_instances": [
                        {
                            "inputs": [
                                {"path": model_path},
                                {"path": runner_path},
                            ]
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (
            self.root
            / ".flowguard"
            / "model-mesh"
            / "bootstraps"
            / (("b" * 64) + ".json")
        ).write_text("{}\n", encoding="utf-8")
        (self.root / "README.md").write_bytes(b"FlowGuard 1.2.3\n")
        (self.root / "CHANGELOG.md").write_bytes(b"## [1.2.3]\n")
        subprocess.run(("git", "init", "-q"), cwd=self.root, check=True)
        subprocess.run(
            ("git", "config", "user.email", "fixture@example.invalid"),
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ("git", "config", "user.name", "FlowGuard Fixture"),
            cwd=self.root,
            check=True,
        )
        subprocess.run(("git", "add", "."), cwd=self.root, check=True)
        subprocess.run(
            ("git", "commit", "-q", "-m", "fixture"),
            cwd=self.root,
            check=True,
        )

        self.receipt_root = (
            self.root / ".flowguard" / "evidence" / "validation-owners"
        )
        self.contract = ValidationOwnerContract(
            owner_id="fixture-owner",
            command=("python", str(self.root / "fixture-check.py")),
            input_patterns=(
                "flowguard/**/*",
                ".flowguard/project.toml",
                "pyproject.toml",
                "README.md",
                "CHANGELOG.md",
            ),
            obligation_ids=("obligation:fixture-release",),
        )
        current = build_owner_current(
            self.root,
            self.contract,
            all_contracts=(self.contract,),
        )
        child = ValidationChildResult(
            "fixture-owner",
            "pass",
            "fixture validation passed",
            claim_boundary="Fixture owner covers one release obligation.",
        )
        owner_receipt = save_owner_receipt(
            current,
            child,
            self.root,
            self.receipt_root,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
        )
        plan_row = ValidationOwnerPlanRow(
            "fixture-owner",
            OWNER_EXECUTE,
            current.owner_identity,
            "fixture owner executed",
            owner_receipt.receipt_id,
            owner_receipt.fingerprint,
        )
        self.parent_receipt = save_parent_receipt(
            self.root,
            self.receipt_root,
            contracts=(self.contract,),
            plan_rows=(plan_row,),
            child_receipts=(owner_receipt,),
            status="pass",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:02+00:00",
        )

    def _local(self, **overrides):
        arguments = {
            "parent_receipt": self.parent_receipt.receipt_id,
            "receipt_root": self.receipt_root,
            "installed_version": "1.2.3",
            "schema_version": "1.0",
            "source_path": self.root / "flowguard" / "__init__.py",
        }
        arguments.update(overrides)
        return verify_local_candidate(self.root, **arguments)

    def _tag(self) -> str:
        subprocess.run(
            ("git", "tag", "-a", "v1.2.3", "-m", "fixture release"),
            cwd=self.root,
            check=True,
        )
        return subprocess.run(
            ("git", "rev-parse", "v1.2.3^{commit}"),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    def _published_runner(
        self,
        commit: str,
        *,
        release_overrides: dict | None = None,
        remote_commit: str | None = None,
        include_peeled: bool = True,
    ):
        commands: list[tuple[str, ...]] = []
        release_payload = {
            "tagName": "v1.2.3",
            "isDraft": False,
            "isPrerelease": False,
            "url": "https://github.com/example/flowguard/releases/tag/v1.2.3",
            "targetCommitish": commit,
            "assets": [],
            "publishedAt": "2026-01-01T00:00:03Z",
        }
        release_payload.update(release_overrides or {})

        def runner(command, cwd):
            command = tuple(command)
            commands.append(command)
            if (
                command[:2] == ("git", "show-ref")
                or command[:4] == ("git", "rev-list", "-n", "1")
            ):
                return subprocess.run(
                    command,
                    cwd=cwd,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            if command == ("git", "remote", "get-url", "origin"):
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "https://github.com/example/flowguard.git\n",
                    "",
                )
            if command[:4] == ("git", "ls-remote", "--tags", "origin"):
                lines = ["tag-object refs/tags/v1.2.3"]
                if include_peeled:
                    lines.append(
                        f"{remote_commit or commit} refs/tags/v1.2.3^{{}}"
                    )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "\n".join(lines) + "\n",
                    "",
                )
            if command[:4] == ("gh", "release", "view", "v1.2.3"):
                return subprocess.CompletedProcess(
                    command,
                    0,
                    json.dumps(release_payload),
                    "",
                )
            raise AssertionError(f"unexpected release command: {command}")

        return runner, commands

    def test_local_candidate_consumes_exact_parent_and_binds_both_manifests(
        self,
    ) -> None:
        receipt = self._local()
        payload = receipt.to_dict()

        self.assertTrue(receipt.ok, payload)
        self.assertEqual(RELEASE_PHASE_LOCAL_CANDIDATE, receipt.phase)
        self.assertEqual(RELEASE_VERIFICATION_SCHEMA, payload["schema_version"])
        self.assertEqual(self.parent_receipt.receipt_id, receipt.parent_receipt_id)
        self.assertEqual(
            self.parent_receipt.fingerprint,
            receipt.parent_receipt_fingerprint,
        )
        self.assertTrue(receipt.validation_input_manifest_fingerprint)
        self.assertTrue(receipt.release_tree_manifest_fingerprint)
        self.assertEqual(
            [self.parent_receipt.receipt_id],
            payload["upstream_receipt_ids"],
        )
        self.assertNotIn("mtime", json.dumps(payload).lower())
        self.assertTrue(payload["receipt_id"].startswith(
            "receipt:release-verification:local-candidate:"
        ))

    def test_hand_written_green_json_is_not_accepted_as_parent_receipt(self) -> None:
        fake = self.root / "green.json"
        fake.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "broad_success": True,
                    "children": [{"status": "pass"}],
                }
            ),
            encoding="utf-8",
        )

        receipt = self._local(parent_receipt=fake)

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.parent_receipt_exact",
            receipt.to_dict()["blockers"],
        )
        self.assertFalse(receipt.parent_receipt_id)

    def test_content_change_with_preserved_mtime_invalidates_parent(self) -> None:
        source = self.root / "flowguard" / "__init__.py"
        original_mtime = source.stat().st_mtime_ns
        source.write_bytes(b"SCHEMA_VERSION = 'changed'\n")
        os.utime(source, ns=(original_mtime, original_mtime))

        receipt = self._local()

        self.assertFalse(receipt.ok)
        blockers = receipt.to_dict()["blockers"]
        self.assertIn("release.parent_receipt_exact", blockers)
        self.assertIn("release.validation_input_manifest_binding", blockers)
        self.assertIn("release.release_tree_manifest_binding", blockers)

    def test_mtime_only_change_keeps_exact_parent_current(self) -> None:
        source = self.root / "flowguard" / "__init__.py"
        changed = source.stat().st_mtime_ns + 5_000_000_000
        os.utime(source, ns=(changed, changed))

        receipt = self._local()

        self.assertTrue(receipt.ok, receipt.to_dict())

    def test_missing_local_metadata_returns_blocked_receipt_not_exception(
        self,
    ) -> None:
        (self.root / "README.md").unlink()

        receipt = self._local()

        self.assertFalse(receipt.ok)
        self.assertEqual("blocked", receipt.status)
        self.assertIn(
            "release.version_alignment",
            receipt.to_dict()["blockers"],
        )

    def test_version_matching_package_archive_blocks_source_only_release(
        self,
    ) -> None:
        wheel = self.root / "dist" / "flowguard-1.2.3-py3-none-any.whl"
        wheel.write_bytes(b"package archive is prohibited")

        receipt = self._local()

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.source_only_authority",
            receipt.to_dict()["blockers"],
        )

    def test_untracked_observed_model_input_blocks_local_candidate(self) -> None:
        model_path = ".flowguard/fixture-model/model.py"
        subprocess.run(
            ("git", "rm", "--cached", "--quiet", model_path),
            cwd=self.root,
            check=True,
        )

        receipt = self._local()

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.model_authority_git_reachability",
            receipt.to_dict()["blockers"],
        )
        check = next(
            item
            for item in receipt.checks
            if item.check_id == "release.model_authority_git_reachability"
        )
        self.assertEqual([model_path], check.details["missing_paths"])

    def test_untracked_observed_runner_input_blocks_same_class(self) -> None:
        runner_path = ".flowguard/fixture-model/run_checks.py"
        subprocess.run(
            ("git", "rm", "--cached", "--quiet", runner_path),
            cwd=self.root,
            check=True,
        )

        receipt = self._local()

        self.assertFalse(receipt.ok)
        check = next(
            item
            for item in receipt.checks
            if item.check_id == "release.model_authority_git_reachability"
        )
        self.assertEqual([runner_path], check.details["missing_paths"])

    def test_model_authority_reachability_does_not_put_inputs_on_command_line(
        self,
    ) -> None:
        snapshot = (
            self.root
            / ".flowguard"
            / "model-mesh"
            / "snapshots"
            / (("a" * 64) + ".json")
        )
        input_paths = [f".flowguard/models/model-{index}.py" for index in range(1000)]
        snapshot.write_text(
            json.dumps(
                {
                    "model_instances": [
                        {"inputs": [{"path": path} for path in input_paths]}
                    ]
                }
            ),
            encoding="utf-8",
        )
        tracked = "\0".join(
            [
                f".flowguard/model-mesh/snapshots/{'a' * 64}.json",
                f".flowguard/model-mesh/bootstraps/{'b' * 64}.json",
                *input_paths,
                "",
            ]
        )
        runner = mock.Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout=tracked,
                stderr="",
            )
        )

        with mock.patch(
            "flowguard.release_verification._command_runner",
            runner,
        ):
            check = _model_authority_git_reachability_check(self.root)

        self.assertEqual("pass", check.status)
        runner.assert_called_once_with(("git", "ls-files", "-z"), self.root)

    def test_tag_phase_compares_committed_tree_to_parent_manifest(self) -> None:
        local = self._local()
        commit = self._tag()

        receipt = verify_tagged_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
        )

        self.assertTrue(receipt.ok, receipt.to_dict())
        self.assertEqual(RELEASE_PHASE_TAG, receipt.phase)
        self.assertEqual(commit, receipt.commit)
        self.assertEqual((local.receipt_id,), receipt.upstream_receipt_ids)
        committed = next(
            check
            for check in receipt.checks
            if check.check_id == "release.committed_tree_manifest"
        )
        self.assertEqual(
            self.parent_receipt.metadata[
                "release_tree_manifest_fingerprint"
            ],
            committed.details["committed"],
        )

    def test_tag_phase_blocks_commit_tree_different_from_parent_manifest(
        self,
    ) -> None:
        (self.root / "README.md").write_bytes(
            b"FlowGuard 1.2.3 changed after final parent\n"
        )
        subprocess.run(("git", "add", "README.md"), cwd=self.root, check=True)
        subprocess.run(
            ("git", "commit", "-q", "-m", "post-parent change"),
            cwd=self.root,
            check=True,
        )
        self._tag()

        receipt = verify_tagged_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
        )

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.committed_tree_manifest",
            receipt.to_dict()["blockers"],
        )

    def test_tag_phase_requires_exact_tag_ref_not_same_named_branch(self) -> None:
        subprocess.run(
            ("git", "branch", "v1.2.3"),
            cwd=self.root,
            check=True,
        )

        receipt = verify_tagged_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
        )

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.local_tag_commit",
            receipt.to_dict()["blockers"],
        )

    def test_published_phase_requires_peeled_tag_and_final_zero_asset_release(
        self,
    ) -> None:
        commit = self._tag()
        runner, commands = self._published_runner(commit)

        receipt = verify_published_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            repository="example/flowguard",
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
            command_runner=runner,
        )

        self.assertTrue(receipt.ok, receipt.to_dict())
        self.assertEqual(RELEASE_PHASE_PUBLISHED, receipt.phase)
        self.assertEqual(commit, receipt.commit)
        self.assertTrue(any(command[0] == "gh" for command in commands))
        self.assertFalse(any(command[0].lower().startswith("python") for command in commands))
        self.assertFalse(
            any("check_flowguard_skill_suite" in " ".join(command) for command in commands)
        )
        remote_query = next(
            command
            for command in commands
            if command[:4] == ("git", "ls-remote", "--tags", "origin")
        )
        self.assertEqual(
            ("git", "ls-remote", "--tags", "origin", "refs/tags/v1.2.3*"),
            remote_query,
        )
        self.assertNotIn("^", " ".join(remote_query))

    def test_published_phase_rejects_unpeeled_remote_tag(self) -> None:
        commit = self._tag()
        runner, _commands = self._published_runner(
            commit,
            include_peeled=False,
        )

        receipt = verify_published_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            repository="example/flowguard",
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
            command_runner=runner,
        )

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.remote_peeled_tag",
            receipt.to_dict()["blockers"],
        )

    def test_published_phase_rejects_wrong_remote_commit(self) -> None:
        commit = self._tag()
        runner, _commands = self._published_runner(
            commit,
            remote_commit="0" * len(commit),
        )

        receipt = verify_published_release(
            self.root,
            parent_receipt=self.parent_receipt.receipt_id,
            receipt_root=self.receipt_root,
            repository="example/flowguard",
            installed_version="1.2.3",
            schema_version="1.0",
            source_path=self.root / "flowguard" / "__init__.py",
            command_runner=runner,
        )

        self.assertFalse(receipt.ok)
        self.assertIn(
            "release.remote_peeled_tag",
            receipt.to_dict()["blockers"],
        )

    def test_published_phase_rejects_draft_prerelease_assets_or_wrong_target(
        self,
    ) -> None:
        commit = self._tag()
        variants = (
            {"isDraft": True},
            {"isPrerelease": True},
            {"assets": [{"name": "flowguard.whl"}]},
            {"targetCommitish": "different-commit"},
            {"publishedAt": None},
        )
        for overrides in variants:
            with self.subTest(overrides=overrides):
                runner, _commands = self._published_runner(
                    commit,
                    release_overrides=overrides,
                )
                receipt = verify_published_release(
                    self.root,
                    parent_receipt=self.parent_receipt.receipt_id,
                    receipt_root=self.receipt_root,
                    repository="example/flowguard",
                    installed_version="1.2.3",
                    schema_version="1.0",
                    source_path=self.root / "flowguard" / "__init__.py",
                    command_runner=runner,
                )
                self.assertFalse(receipt.ok)
                self.assertIn(
                    "release.github_release",
                    receipt.to_dict()["blockers"],
                )

    def test_remote_tag_commit_requires_peeled_annotated_tag(self) -> None:
        output = (
            "tag-object refs/tags/v1.2.3\n"
            "release-commit refs/tags/v1.2.3^{}\n"
            "other-object refs/tags/v1.2.30\n"
        )

        commit, refs = _remote_tag_commit(output, "v1.2.3")

        self.assertEqual("release-commit", commit)
        self.assertEqual("tag-object", refs["refs/tags/v1.2.3"])
        lightweight, _ = _remote_tag_commit(
            "release-commit refs/tags/v1.2.3\n",
            "v1.2.3",
        )
        self.assertEqual("", lightweight)

    def test_cli_exposes_only_v2_phases_and_requires_parent_receipt(self) -> None:
        with self.assertRaises(SystemExit):
            release_cli.build_parser().parse_args(
                ["--phase", "local", "--parent-receipt", "receipt:old"]
            )
        with self.assertRaises(SystemExit):
            release_cli.build_parser().parse_args(
                ["--phase", RELEASE_PHASE_LOCAL_CANDIDATE]
            )
        parsed = release_cli.build_parser().parse_args(
            [
                "--phase",
                RELEASE_PHASE_LOCAL_CANDIDATE,
                "--parent-receipt",
                self.parent_receipt.receipt_id,
            ]
        )
        self.assertEqual(RELEASE_PHASE_LOCAL_CANDIDATE, parsed.phase)
        self.assertFalse(hasattr(parsed, "evidence"))
        with self.assertRaisesRegex(
            SystemExit,
            "v-prefixed",
        ):
            release_cli.main(
                [
                    "--phase",
                    RELEASE_PHASE_LOCAL_CANDIDATE,
                    "--parent-receipt",
                    self.parent_receipt.receipt_id,
                    "--tag",
                    "1.2.3",
                ]
            )

    def test_cli_dispatches_each_v2_phase(self) -> None:
        terminal = SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "schema_version": RELEASE_VERIFICATION_SCHEMA,
                "status": "pass",
            },
            format_text=lambda: "pass",
        )
        routes = (
            (RELEASE_PHASE_LOCAL_CANDIDATE, "verify_local_candidate"),
            (RELEASE_PHASE_TAG, "verify_tagged_release"),
            (RELEASE_PHASE_PUBLISHED, "verify_published_release"),
        )
        for phase, function_name in routes:
            with self.subTest(phase=phase):
                stdout = io.StringIO()
                with (
                    mock.patch.object(
                        release_cli,
                        function_name,
                        return_value=terminal,
                    ) as verifier,
                    contextlib.redirect_stdout(stdout),
                ):
                    exit_code = release_cli.main(
                        [
                            "--root",
                            str(self.root),
                            "--phase",
                            phase,
                            "--parent-receipt",
                            self.parent_receipt.receipt_id,
                            "--json",
                        ]
                    )
                self.assertEqual(0, exit_code)
                self.assertIn(RELEASE_VERIFICATION_SCHEMA, stdout.getvalue())
                verifier.assert_called_once()
                self.assertEqual(
                    self.parent_receipt.receipt_id,
                    verifier.call_args.kwargs["parent_receipt"],
                )

    @mock.patch("flowguard.release_verification.subprocess.run")
    @mock.patch("flowguard.release_verification.shutil.which")
    def test_command_runner_resolves_windows_pathext_shim(self, which, run) -> None:
        resolved = r"C:\tools\git.CMD"
        which.return_value = resolved
        completed = subprocess.CompletedProcess(
            [resolved, "--version"],
            0,
            "git version",
            "",
        )
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
    @mock.patch(
        "flowguard.release_verification.shutil.which",
        return_value=None,
    )
    def test_command_runner_reports_missing_executable_without_crashing(
        self,
        _which,
        run,
    ) -> None:
        run.side_effect = FileNotFoundError("missing command")

        result = _command_runner(("missing-tool", "--version"), self.root)

        self.assertEqual(127, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("missing command", result.stderr)


if __name__ == "__main__":
    unittest.main()
