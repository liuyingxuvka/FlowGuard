import json
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from flowguard.behavior_plane import BCL_PLANE_DEVELOPMENT_PROCESS, BCL_PLANE_PRODUCT_RUNTIME
from flowguard.spec_providers import (
    SpecProviderError,
    discover_spec_work_packages,
    load_openspec_canonical_checks,
    load_openspec_work_package,
    load_speckit_work_package,
)
from flowguard.spec_work_package import (
    SPEC_BINDING_DIRECT,
    SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
    SPEC_PROVIDER_OPEN_SPEC,
    SpecCheckDefinition,
    SpecObligation,
    SpecProviderRef,
    SpecTask,
    SpecTaskObligationBinding,
    SpecWorkPackage,
    review_spec_work_package,
    spec_work_package_preflight_context,
    spec_work_package_to_development_process,
    spec_work_package_to_plan_detail,
    spec_work_package_to_test_mesh,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _bindings(root: Path, packages: list[dict]) -> None:
    path = root / ".flowguard/spec_provider_work_packages/bindings.json"
    _write(path, json.dumps({"packages": packages}, indent=2) + "\n")


def _openspec_change(root: Path, change_id: str = "change-one") -> Path:
    change = root / "openspec/changes" / change_id
    _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Implement the bridge\n")
    _write(
        change / "verification-contract.yaml",
        """contract_version: 3
obligations:
  - id: req.bridge
    source: specs/bridge/spec.md
    claim: The provider bridge remains read-only.
    evidence: [check.bridge]
checks:
  - id: check.bridge
    kind: command
    command: python
    args: [-c, 'pass']
    covers: [req.bridge]
    required: true
    expected:
      exit_code: 0
""",
    )
    return change


def _openspec_binding(change_id: str = "change-one") -> dict:
    return {
        "provider_id": "openspec",
        "work_package_id": change_id,
        "flowguard_obligation_map": {"req.bridge": ["obligation:spec-bridge"]},
        "task_binding_rules": [
            {
                "task_prefix": "1.",
                "obligation_ids": ["req.bridge"],
                "binding_kind": "direct",
            }
        ],
        "check_policies": [
            {
                "check_id": "check.bridge",
                "validation_obligation_ids": ["validation:bridge"],
            }
        ],
    }


def _valid_package() -> SpecWorkPackage:
    provider = SpecProviderRef(
        provider_id=SPEC_PROVIDER_OPEN_SPEC,
        root_token="openspec",
        mode=SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
        schema_version="3",
    )
    task = SpecTask("1.1", "Bridge", completed=True, source_ref="openspec/tasks.md:1")
    obligation = SpecObligation("req.bridge", check_ids=("check.bridge",))
    check = SpecCheckDefinition(
        "check.bridge",
        command=("python", "-c", "pass"),
        obligation_ids=("req.bridge",),
        validation_obligation_ids=("validation:bridge",),
    )
    binding = SpecTaskObligationBinding(
        "binding:1.1",
        task_ids=("1.1",),
        obligation_ids=("req.bridge",),
        check_ids=("check.bridge",),
        binding_kind=SPEC_BINDING_DIRECT,
    )
    return SpecWorkPackage(
        provider=provider,
        work_package_id="change-one",
        change_id="change-one",
        tasks=(task,),
        obligations=(obligation,),
        checks=(check,),
        bindings=(binding,),
    )


class SpecProviderAdapterTests(unittest.TestCase):
    def test_spec_provider_optional_dependency_extra_is_packaged(self) -> None:
        def contract_ok(text: str) -> bool:
            parsed = tomllib.loads(text)
            optional = parsed.get("project", {}).get("optional-dependencies", {})
            return optional.get("spec-providers") == ["PyYAML>=6.0"]

        canonical = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertTrue(contract_ok(canonical))
        self.assertFalse(contract_ok(canonical.replace('spec-providers = ["PyYAML>=6.0"]', 'spec-providers = []')))
        self.assertFalse(
            contract_ok(canonical.replace('spec-providers = ["PyYAML>=6.0"]', 'spec-providers = ["PyYAML>=5.0"]'))
        )

    def test_provider_contract_cannot_close_or_reexecute_flowguard_owner(self) -> None:
        package = _valid_package()
        for forbidden, finding_code in (
            ("spec-session-close", "provider_execution_lifecycle_cycle"),
            ("spec-check-run", "provider_reexecutes_flowguard_owner"),
        ):
            with self.subTest(command=forbidden):
                check = replace(
                    package.checks[0],
                    command=("python", "-m", "flowguard", forbidden),
                )
                review = review_spec_work_package(replace(package, checks=(check,)))
                self.assertIn(finding_code, review.finding_codes)

    def test_cross_change_owner_rejects_provider_lifecycle_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _openspec_change(root)
            binding = _openspec_binding()
            binding["canonical_checks"] = [
                {
                    "check_id": "check.bridge",
                    "command": ["python", "-c", "pass"],
                    "cross_change_safe": True,
                    "input_paths": ["flowguard/**/*.py", "openspec/changes/**"],
                    "validation_obligation_ids": ["validation:bridge"],
                }
            ]
            _bindings(root, [binding])

            with self.assertRaisesRegex(
                SpecProviderError,
                "cross-change-safe owner cannot consume provider lifecycle inputs",
            ):
                load_openspec_canonical_checks(root, "change-one")

    def test_external_receipt_only_package_does_not_require_a_second_flowguard_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec/changes/change-one"
            _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Consume the owner receipt\n")
            _write(
                change / "verification-contract.yaml",
                """contract_version: 3
obligations:
  - id: req.bridge
    source: specs/bridge/spec.md
    claim: Consume one external owner receipt without rerunning it.
    evidence: [owner.bridge]
checks:
  - id: owner.bridge
    kind: receipt
    semantic_check_id: semantic.bridge
    execution_id: owner.bridge.v1
    receipt_ref:
      provider_id: skillguard
      work_package_id: change-one
      adapter: portable-receipt.v1
      ref_path: <SPEC_EVIDENCE>/portable/change-one/ref.json
    consumer: openspec.change.change-one
    covers: [req.bridge]
    required: true
""",
            )
            _bindings(
                root,
                [
                    {
                        "provider_id": "openspec",
                        "work_package_id": "change-one",
                        "task_binding_rules": [
                            {"task_prefix": "1.", "obligation_ids": ["req.bridge"]}
                        ],
                    }
                ],
            )

            self.assertEqual((), load_openspec_canonical_checks(root, "change-one"))
            package = load_openspec_work_package(root, "change-one")
            review = review_spec_work_package(package)
            self.assertTrue(review.ok, review.finding_codes)

    def test_external_receipt_covers_are_the_single_owner_coverage_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec/changes/change-one"
            _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Implement owner\n")
            _write(
                change / "verification-contract.yaml",
                """contract_version: 3
evidence_roots:
  SPEC_EVIDENCE: .flowguard/evidence/spec-work-packages
obligations:
  - id: req.bridge
    source: specs/bridge/spec.md
    claim: Bridge coverage.
    evidence: [owner.bridge]
checks:
  - id: owner.bridge
    kind: receipt
    semantic_check_id: semantic.bridge
    execution_id: owner.bridge.v1
    receipt_ref:
      provider_id: openspec
      work_package_id: change-one
      adapter: portable-receipt.v1
      ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.bridge.json
    consumer: openspec.change.change-one
    required: true
    covers: [req.bridge]
""",
            )
            _bindings(
                root,
                [
                    {
                        "provider_id": "openspec",
                        "work_package_id": "change-one",
                        "canonical_checks": [
                            {
                                "check_id": "owner.bridge",
                                "semantic_check_id": "semantic.bridge",
                                "execution_id": "owner.bridge.v1",
                                "command": ["python", "-c", "pass"],
                                "validation_obligation_ids": ["validation:bridge"],
                                "coverage_ids": ["must-not-be-authoritative"],
                                "snapshot_policy": "live-scoped",
                            }
                        ],
                        "task_binding_rules": [
                            {"task_prefix": "1.", "obligation_ids": ["req.bridge"]}
                        ],
                    }
                ],
            )

            owners = load_openspec_canonical_checks(root, "change-one")
            package = load_openspec_work_package(root, "change-one")

            self.assertEqual(("req.bridge",), owners[0].coverage_ids)
            self.assertEqual(("req.bridge",), owners[0].obligation_ids)
            self.assertTrue(review_spec_work_package(package).ok)

    def test_aggregate_owner_cannot_claim_coverage_missing_from_children(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec/changes/change-one"
            _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Aggregate receipts\n")
            _write(
                change / "verification-contract.yaml",
                """contract_version: 3
evidence_roots:
  SPEC_EVIDENCE: .flowguard/evidence/spec-work-packages
obligations:
  - id: req.child
    source: specs/bridge/spec.md
    claim: Child coverage.
    evidence: [owner.child, owner.parent]
  - id: req.parent-only
    source: specs/bridge/spec.md
    claim: Missing child coverage.
    evidence: [owner.parent]
checks:
  - id: owner.child
    kind: receipt
    semantic_check_id: semantic.child
    execution_id: owner.child.v1
    receipt_ref: {provider_id: openspec, work_package_id: change-one, adapter: portable-receipt.v1, ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.child.json}
    consumer: openspec.change.change-one
    covers: [req.child]
  - id: owner.parent
    kind: receipt
    semantic_check_id: semantic.parent
    execution_id: owner.parent.v1
    receipt_ref: {provider_id: openspec, work_package_id: change-one, adapter: portable-receipt.v1, ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.parent.json}
    consumer: openspec.change.change-one
    covers: [req.child, req.parent-only]
""",
            )
            _bindings(
                root,
                [
                    {
                        "provider_id": "openspec",
                        "work_package_id": "change-one",
                        "canonical_checks": [
                            {
                                "check_id": "owner.child",
                                "semantic_check_id": "semantic.child",
                                "execution_id": "owner.child.v1",
                                "command": ["python", "-c", "pass"],
                                "validation_obligation_ids": ["validation:child"],
                            },
                            {
                                "check_id": "owner.parent",
                                "semantic_check_id": "semantic.parent",
                                "execution_id": "owner.parent.v1",
                                "execution_mode": "aggregate-child-receipts",
                                "child_check_ids": ["owner.child"],
                                "validation_obligation_ids": ["validation:parent"],
                            },
                        ],
                        "task_binding_rules": [
                            {
                                "task_prefix": "1.",
                                "obligation_ids": ["req.child", "req.parent-only"],
                            }
                        ],
                    }
                ],
            )

            with self.assertRaisesRegex(
                SpecProviderError,
                "aggregate check coverage must be provided by declared children",
            ):
                load_openspec_canonical_checks(root, "change-one")

    def test_openspec_adapter_is_read_only_and_preserves_stable_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = _openspec_change(root)
            _bindings(root, [_openspec_binding()])
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            package = load_openspec_work_package(root, "change-one")
            report = review_spec_work_package(package)

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertTrue(report.ok, report.finding_codes)
            self.assertEqual(package.work_package_id, "change-one")
            self.assertEqual(package.change_id, "change-one")
            self.assertEqual(package.tasks[0].task_id, "1.1")
            self.assertEqual(package.obligations[0].obligation_id, "req.bridge")
            self.assertEqual(package.checks[0].check_id, "check.bridge")
            self.assertTrue(package.provider.native_task_authority)
            self.assertTrue(package.provider.native_verification_authority)
            self.assertTrue(package.provider.native_archive_authority)
            self.assertFalse(package.provider_verified)
            self.assertFalse(package.provider_archive_ready)
            self.assertEqual(change.exists(), True)

    def test_openspec_current_contract_rejects_implicit_command_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = _openspec_change(root)
            contract = change / "verification-contract.yaml"
            contract.write_text(
                contract.read_text(encoding="utf-8").replace("    kind: command\n", ""),
                encoding="utf-8",
            )
            _bindings(root, [_openspec_binding()])

            report = review_spec_work_package(load_openspec_work_package(root, "change-one"))

            self.assertIn("check_kind_invalid", report.finding_codes)

    def test_speckit_artifact_adapter_and_auto_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".specify").mkdir()
            _write(
                root / "specs/feature-one/tasks.md",
                "# Tasks\n\n- [x] T001 [P] [US1] Implement adapter\n",
            )
            _write(root / "specs/feature-one/spec.md", "# Feature\n")
            _write(root / "specs/feature-one/plan.md", "# Plan\n")
            _write(root / "specs/feature-one/checklists/quality.md", "# Quality checklist\n")
            _bindings(
                root,
                [
                    {
                        "provider_id": "speckit",
                        "work_package_id": "feature-one",
                        "obligations": [
                            {
                                "obligation_id": "req.feature",
                                "claim": "Feature adapter",
                                "check_ids": ["check.feature"],
                            }
                        ],
                        "checks": [
                            {
                                "check_id": "check.feature",
                                "command": ["python", "-c", "pass"],
                                "obligation_ids": ["req.feature"],
                                "validation_obligation_ids": ["validation:feature"],
                            }
                        ],
                        "task_binding_rules": [
                            {"task_ids": ["T001"], "obligation_ids": ["req.feature"]}
                        ],
                    }
                ],
            )

            package = load_speckit_work_package(root, "feature-one")
            discovered = discover_spec_work_packages(root, provider_id="auto")

            self.assertTrue(review_spec_work_package(package).ok)
            self.assertEqual(package.tasks[0].metadata["user_story_id"], "US1")
            self.assertTrue(package.tasks[0].metadata["parallel"])
            self.assertIn("specs/feature-one/checklists/quality.md", package.artifact_refs)
            self.assertEqual([(item.provider.provider_id, item.change_id) for item in discovered], [("speckit", "feature-one")])

    def test_provider_paths_cannot_escape_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec/changes").mkdir(parents=True)
            (root / ".specify").mkdir()
            (root / "specs").mkdir()
            outside = root.parent / f"{root.name}-outside-bindings.json"
            outside.write_text("{}", encoding="utf-8")
            self.addCleanup(outside.unlink, missing_ok=True)

            for loader, unsafe_id in (
                (load_openspec_work_package, "../outside"),
                (load_speckit_work_package, "../outside"),
            ):
                with self.subTest(loader=loader.__name__):
                    with self.assertRaises(SpecProviderError):
                        loader(root, unsafe_id)
            _openspec_change(root)
            with self.assertRaises(SpecProviderError):
                load_openspec_work_package(root, "change-one", bindings_path=outside)


class SpecWorkPackageReviewTests(unittest.TestCase):
    def test_complete_bidirectional_mapping_is_ready(self) -> None:
        package = _valid_package()
        report = review_spec_work_package(package)
        self.assertTrue(report.ok)
        self.assertEqual(report.mapped_task_ids, ("1.1",))
        self.assertEqual(report.mapped_obligation_ids, ("req.bridge",))
        self.assertEqual(report.mapped_check_ids, ("check.bridge",))
        context = spec_work_package_preflight_context(package)
        self.assertEqual(context["behavior_plane"], BCL_PLANE_DEVELOPMENT_PROCESS)
        self.assertFalse(context["provider_owns_product_behavior"])

    def test_missing_forward_or_reverse_mapping_blocks(self) -> None:
        package = _valid_package()
        report = review_spec_work_package(replace(package, bindings=()))
        self.assertIn("unmapped_spec_task", report.finding_codes)
        self.assertIn("unmapped_spec_obligation", report.finding_codes)
        self.assertIn("unmapped_spec_check", report.finding_codes)

    def test_provider_authority_and_development_process_plane_are_hard_gates(self) -> None:
        package = _valid_package()
        provider = replace(package.provider, native_archive_authority=False)
        report = review_spec_work_package(
            replace(package, provider=provider, behavior_plane=BCL_PLANE_PRODUCT_RUNTIME)
        )
        self.assertIn("provider_native_authority_missing", report.finding_codes)
        self.assertIn("spec_work_package_wrong_plane", report.finding_codes)

    def test_duplicate_stable_identities_block(self) -> None:
        package = _valid_package()
        report = review_spec_work_package(replace(package, tasks=package.tasks + package.tasks))
        self.assertIn("duplicate_task_identity", report.finding_codes)

    def test_identity_fingerprint_excludes_localized_display_prose(self) -> None:
        package = _valid_package()
        localized = replace(
            package,
            tasks=(replace(package.tasks[0], title="本地化任务标题"),),
            obligations=(replace(package.obligations[0], claim="本地化说明"),),
        )
        self.assertEqual(package.identity_fingerprint, localized.identity_fingerprint)
        self.assertEqual(package.to_dict()["identity_fingerprint"], package.identity_fingerprint)

    def test_conflicting_primary_infrastructure_owner_blocks(self) -> None:
        package = _valid_package()
        conflicting = replace(
            package,
            bindings=package.bindings
            + (
                SpecTaskObligationBinding(
                    "binding:conflict",
                    obligation_ids=("req.bridge",),
                    check_ids=("check.bridge",),
                    binding_kind="infrastructure",
                    owner_id="other-owner",
                    reason="conflicting owner fixture",
                ),
                SpecTaskObligationBinding(
                    "binding:owner",
                    obligation_ids=("req.bridge",),
                    check_ids=("check.bridge",),
                    binding_kind="infrastructure",
                    owner_id="primary-owner",
                    reason="primary owner fixture",
                ),
            ),
        )
        report = review_spec_work_package(conflicting)
        self.assertIn("conflicting_primary_owner", report.finding_codes)

    def test_provider_schema_and_currentness_are_explicit_gates(self) -> None:
        package = _valid_package()
        provider = replace(package.provider, schema_version="1.0", current=False)
        report = review_spec_work_package(replace(package, provider=provider))
        self.assertIn("provider_schema_unsupported", report.finding_codes)
        self.assertIn("provider_context_stale", report.finding_codes)

    def test_owner_projections_preserve_task_obligation_check_and_consumer_identity(self) -> None:
        package = _valid_package()
        detail = spec_work_package_to_plan_detail(package)
        self.assertEqual(("1.1",), detail.steps[0].spec_task_ids)
        self.assertEqual(("req.bridge",), detail.validations[0].spec_obligation_ids)

        process = spec_work_package_to_development_process(package)
        self.assertEqual(
            (
                "spec_provider_read",
                "spec_reconcile",
                "spec_session_begin",
                "spec_check",
                "spec_post_snapshot",
                "spec_provider_verify",
                "spec_sync",
                "spec_archive_ready",
            ),
            tuple(action.action_type for action in process.actions),
        )
        self.assertTrue(process.require_spec_session_close)

        mesh = spec_work_package_to_test_mesh(package)
        self.assertEqual(
            set(mesh.required_spec_consumer_ids),
            {consumer.consumer_id for consumer in package.consumer_refs()},
        )


if __name__ == "__main__":
    unittest.main()
