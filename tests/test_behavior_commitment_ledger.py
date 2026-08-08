import ast
import importlib.util
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flowguard import (
    BCL_ACTOR_END_USER,
    BCL_CHANGE_BOOTSTRAP_LEDGER,
    BCL_CHANGE_CHANGE_BEHAVIOR,
    BCL_COMMITMENT_WORKFLOW,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_MISS_ORIGIN_OBSERVED,
    BCL_MODEL_SYNC_OWNER_STALE,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_RELATION_DEPENDS_ON,
    BCL_REPLACEMENT_REPLACED,
    BCL_SCOPE_FULL,
    BCL_SCOPE_ROUTINE,
    BCL_SOURCE_AUTHORITY_OBSERVED,
    BCL_SOURCE_AUTHORITY_SUPPORTING,
    BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT,
    BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
    BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
    BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR,
    BCL_SOURCE_CLASSIFICATION_TEST,
    BCL_SOURCE_DOC,
    BCL_SOURCE_FRESHNESS_CHANGED,
    BCL_TEST_MESH_SHARD_MISSING,
    BehaviorCommitment,
    BehaviorCommitmentRelation,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorSourceSurface,
    audit_behavior_commitment_source_inventory,
    refresh_behavior_commitment_source_inventory,
    review_behavior_commitment_ledger,
)


def evidence(**kwargs):
    defaults = {
        "model_obligation_ids": ("obligation:workflow",),
        "code_contract_ids": ("contract:workflow",),
        "test_evidence_ids": ("test:workflow",),
        "risk_gate_ids": ("risk_gate:behavior_commitment_coverage:ledger",),
        "coverage_case_ids": ("bcl.full_inventory_mapping.workflow.doc.mapped",),
        "coverage_shard_ids": ("contract_shard:behavior_commitment_ledger:full_inventory_mapping",),
        "coverage_receipt_ids": ("contract_coverage:behavior_commitment_ledger",),
        "evidence_state": BCL_EVIDENCE_CURRENT_PASS,
        "current": True,
    }
    defaults.update(kwargs)
    return BehaviorEvidenceBinding(**defaults)


def surface(**kwargs):
    defaults = {
        "surface_id": "surface:docs-workflow",
        "surface_kind": BCL_SOURCE_DOC,
        "label": "docs workflow surface",
        "source_ref": "README.md#usage",
        "source_system_id": "repository-docs",
        "native_artifact_id": "README.md#usage",
        "content_fingerprint": "sha256:docs-workflow-content",
        "inventory_revision": "rev-1",
        "discovery_evidence_ids": ("inventory:rev-1",),
        "source_authority_role": "normative",
        "source_classification": BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT,
        "declared_semantics_fingerprint": "sha256:workflow-semantics",
        "coverage_disposition": "modeled",
        "freshness_state": "current",
        "commitment_ids": ("commitment:workflow",),
        "business_intent_ids": ("intent:workflow",),
        "owner": "docs-owner",
        "validation_boundary": "docs and tests",
        "rationale": "public docs expose the behavior",
    }
    defaults.update(kwargs)
    return BehaviorSourceSurface(**defaults)


def commitment(**kwargs):
    defaults = {
        "commitment_id": "commitment:workflow",
        "business_intent_id": "intent:workflow",
        "label": "run workflow",
        "commitment_kind": BCL_COMMITMENT_WORKFLOW,
        "behavior_plane": BCL_PLANE_PRODUCT_RUNTIME,
        "actor_kind": BCL_ACTOR_END_USER,
        "actor": "user",
        "trigger": "runs the documented command",
        "expected_result": "documented success or visible repairable error",
        "expected_terminal": "documented success or visible repairable error",
        "failure_boundary": "fail closed with repair information",
        "source_surface_ids": ("surface:docs-workflow",),
        "primary_owner_model_id": "model:workflow",
        "validation_boundary": "model, contract, and smoke test",
        "rationale": "external behavior promise",
        "evidence": evidence(),
    }
    defaults.update(kwargs)
    return BehaviorCommitment(**defaults)


def ledger(*, commitments=None, surfaces=None, expected=None, **kwargs):
    defaults = {
        "ledger_id": "ledger",
        "project_boundary": "example project",
        "current_revision": "rev-1",
        "claim_scope": BCL_SCOPE_FULL,
        "owner": "maintainer",
        "validation_boundary": "full behavior claim",
        "rationale": "register all external behavior promises",
        "expected_commitment_ids": expected or ("commitment:workflow",),
        "expected_business_intent_ids": ("intent:workflow",),
        "expected_source_surface_ids": ("surface:docs-workflow",),
        "source_inventory_revision": "rev-1",
        "source_inventory_fingerprint": "sha256:inventory-rev-1",
        "source_inventory_evidence_ids": ("inventory:rev-1",),
        "require_complete_source_inventory": True,
        "source_surfaces": tuple(surfaces if surfaces is not None else (surface(),)),
        "commitments": tuple(commitments if commitments is not None else (commitment(),)),
    }
    defaults.update(kwargs)
    return BehaviorCommitmentLedger(**defaults)


def codes(report):
    return {finding.code for finding in report.findings}


def load_repo_model(relative_path: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BehaviorCommitmentLedgerTests(unittest.TestCase):
    def _live_ledger(self, root: Path, source_ref: str) -> BehaviorCommitmentLedger:
        candidate = ledger(
            surfaces=(
                surface(
                    source_ref=source_ref,
                    native_artifact_id=source_ref,
                    metadata={"authored": "preserved"},
                ),
            ),
        )
        return refresh_behavior_commitment_source_inventory(candidate, root)

    def test_live_source_audit_is_read_only_and_crlf_equivalent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "README.md"
            source.write_bytes(b"# Usage\n\nhello\n")
            refreshed = self._live_ledger(root, "README.md#Usage")
            source.write_bytes(b"# Usage\r\n\r\nhello\r\n")
            before = source.read_bytes()

            report = audit_behavior_commitment_source_inventory(refreshed, root)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(
                "preserved",
                refreshed.source_surfaces[0].metadata["authored"],
            )

    def test_composite_member_content_change_is_stale_without_membership_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.py").write_text("A = 1\n", encoding="utf-8")
            (root / "b.py").write_text("B = 1\n", encoding="utf-8")
            refreshed = self._live_ledger(root, "a.py; b.py")
            (root / "b.py").write_text("B = 2\n", encoding="utf-8")

            report = audit_behavior_commitment_source_inventory(refreshed, root)

            self.assertIn("source_surface_content_fingerprint_stale", codes(report))
            self.assertNotIn("source_surface_membership_stale", codes(report))
            self.assertIn("source_inventory_fingerprint_stale", codes(report))

    def test_bounded_glob_membership_change_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skills = root / "skills"
            skills.mkdir()
            (skills / "a.md").write_text("# A\n", encoding="utf-8")
            refreshed = self._live_ledger(root, "skills/*.md")
            (skills / "b.md").write_text("# B\n", encoding="utf-8")

            report = audit_behavior_commitment_source_inventory(refreshed, root)

            self.assertIn("source_surface_membership_stale", codes(report))
            self.assertIn("source_surface_content_fingerprint_stale", codes(report))

    def test_root_level_or_prefix_free_glob_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "root.md").write_text("# Root\n", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "child.md").write_text("# Child\n", encoding="utf-8")
            for source_ref in ("*.md", "**/*.md"):
                with self.subTest(source_ref=source_ref):
                    candidate = ledger(
                        surfaces=(
                            surface(
                                source_ref=source_ref,
                                native_artifact_id=source_ref,
                            ),
                        ),
                    )
                    report = audit_behavior_commitment_source_inventory(candidate, root)
                    self.assertIn("source_surface_glob_unbounded", codes(report))
                    with self.assertRaises(ValueError):
                        refresh_behavior_commitment_source_inventory(candidate, root)

    def test_duplicate_member_across_direct_and_glob_refs_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "sources"
            sources.mkdir()
            (sources / "a.md").write_text("# A\n", encoding="utf-8")
            candidate = ledger(
                surfaces=(
                    surface(
                        source_ref="sources/a.md; sources/*.md",
                        native_artifact_id="sources/a.md; sources/*.md",
                    ),
                ),
            )

            report = audit_behavior_commitment_source_inventory(candidate, root)

            self.assertIn("source_surface_member_duplicate", codes(report))
            with self.assertRaises(ValueError):
                refresh_behavior_commitment_source_inventory(candidate, root)

    def test_authored_surface_semantics_do_not_change_physical_inventory_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            refreshed = self._live_ledger(root, "source.py")
            changed_semantics = replace(
                refreshed,
                source_surfaces=(
                    replace(
                        refreshed.source_surfaces[0],
                        owner="different-authored-owner",
                        source_authority_role="supporting",
                    ),
                ),
            )

            report = audit_behavior_commitment_source_inventory(changed_semantics, root)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(
                refreshed.source_inventory_fingerprint,
                report.live_inventory_fingerprint,
            )

    def test_missing_anchor_file_empty_glob_and_escape_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "doc.md").write_text("# Present\n", encoding="utf-8")
            cases = {
                "doc.md#Absent": "source_surface_anchor_missing",
                "missing.md": "source_surface_ref_missing",
                "none/*.md": "source_surface_glob_empty",
                "../outside.md": "source_surface_ref_unsafe",
            }
            for source_ref, expected_code in cases.items():
                with self.subTest(source_ref=source_ref):
                    candidate = ledger(
                        surfaces=(
                            surface(
                                source_ref=source_ref,
                                native_artifact_id=source_ref,
                            ),
                        ),
                    )
                    report = audit_behavior_commitment_source_inventory(candidate, root)
                    self.assertIn(expected_code, codes(report))
                    with self.assertRaises(ValueError):
                        refresh_behavior_commitment_source_inventory(candidate, root)

    def test_symlink_escape_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as project_temporary, tempfile.TemporaryDirectory() as outside_temporary:
            root = Path(project_temporary)
            outside = Path(outside_temporary) / "outside.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            link = root / "linked.md"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError):
                self.skipTest("symlinks are unavailable in this environment")
            candidate = ledger(
                surfaces=(
                    surface(
                        source_ref="linked.md",
                        native_artifact_id="linked.md",
                    ),
                ),
            )

            report = audit_behavior_commitment_source_inventory(candidate, root)

            self.assertIn("source_surface_ref_unsafe", codes(report))

    def test_live_audit_rejects_stale_top_revision_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            refreshed = self._live_ledger(root, "source.py")
            stale = replace(
                refreshed,
                source_inventory_fingerprint="sha256:stale",
                source_inventory_revision="source-inventory:stale",
                source_inventory_evidence_ids=("source-inventory-discovery:stale",),
            )

            report = audit_behavior_commitment_source_inventory(stale, root)

            self.assertIn("source_inventory_fingerprint_stale", codes(report))
            self.assertIn("source_inventory_revision_stale", codes(report))
            self.assertIn("source_inventory_evidence_stale", codes(report))

    def test_review_can_bind_static_coverage_to_live_source_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            refreshed = self._live_ledger(root, "source.py")
            self.assertTrue(
                review_behavior_commitment_ledger(
                    refreshed,
                    project_root=root,
                ).ok
            )
            source.write_text("VALUE = 2\n", encoding="utf-8")

            report = review_behavior_commitment_ledger(
                refreshed,
                project_root=root,
            )

            self.assertFalse(report.ok)
            self.assertIn("source_surface_content_fingerprint_stale", codes(report))

    def test_native_runner_performs_one_live_source_scan(self):
        runner_path = (
            Path(__file__).resolve().parents[1]
            / ".flowguard/behavior_commitment_ledger/run_checks.py"
        )
        tree = ast.parse(runner_path.read_text(encoding="utf-8"))
        calls = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Call))
        live_audit_calls = tuple(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "audit_flowguard_behavior_commitment_source_inventory"
        )
        review_calls = tuple(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "review_behavior_commitment_ledger"
        )

        self.assertEqual(1, len(live_audit_calls))
        self.assertTrue(review_calls)
        self.assertFalse(
            any(
                keyword.arg == "project_root"
                for call in review_calls
                for keyword in call.keywords
            ),
            "the native runner must not repeat the live source scan through review()",
        )

    def test_change_mode_does_not_require_bootstrap_wide_inventory(self):
        affected = ledger(
            claim_scope=BCL_SCOPE_ROUTINE,
            change_mode=BCL_CHANGE_CHANGE_BEHAVIOR,
            require_complete_source_inventory=False,
            expected_source_surface_ids=(),
            source_inventory_revision="",
            source_inventory_fingerprint="",
            source_inventory_evidence_ids=(),
        )
        bootstrap = ledger(
            claim_scope=BCL_SCOPE_ROUTINE,
            change_mode=BCL_CHANGE_BOOTSTRAP_LEDGER,
            require_complete_source_inventory=False,
            expected_source_surface_ids=(),
            source_inventory_revision="",
            source_inventory_fingerprint="",
            source_inventory_evidence_ids=(),
        )

        affected_codes = codes(review_behavior_commitment_ledger(affected))
        bootstrap_codes = codes(review_behavior_commitment_ledger(bootstrap))

        self.assertNotIn("expected_source_inventory_missing", affected_codes)
        self.assertIn("expected_source_inventory_missing", bootstrap_codes)

    def test_complete_ledger_passes_and_exposes_downstream_ids(self):
        report = review_behavior_commitment_ledger(ledger())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("behavior_commitment_coverage_green", report.decision)
        self.assertIn("commitment:workflow", report.covered_commitment_ids)
        self.assertIn("risk_gate:behavior_commitment_coverage:ledger", report.required_risk_gate_ids)
        self.assertIn("contract_coverage:behavior_commitment_ledger", report.coverage_receipt_ids)

    def test_only_external_normative_contract_can_license_a_broad_commitment(self):
        observed = review_behavior_commitment_ledger(
            ledger(
                surfaces=(
                    surface(
                        source_classification=BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR,
                        source_authority_role=BCL_SOURCE_AUTHORITY_OBSERVED,
                    ),
                )
            )
        )
        self.assertIn("commitment_current_normative_source_missing", codes(observed))
        self.assertNotIn("source_surface_non_contract_authority_forbidden", codes(observed))

        for source_classification in (
            BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
            BCL_SOURCE_CLASSIFICATION_TEST,
            BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
        ):
            with self.subTest(source_classification=source_classification):
                report = review_behavior_commitment_ledger(
                    ledger(
                        surfaces=(
                            surface(
                                source_classification=source_classification,
                                source_authority_role=BCL_SOURCE_AUTHORITY_SUPPORTING,
                            ),
                        )
                    )
                )
                self.assertIn(
                    "source_surface_non_contract_authority_forbidden",
                    codes(report),
                )
                self.assertIn(
                    "commitment_current_normative_source_missing",
                    codes(report),
                )

    def test_source_classification_and_authority_role_must_agree(self):
        report = review_behavior_commitment_ledger(
            ledger(
                surfaces=(
                    surface(
                        source_classification=BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
                        source_authority_role="normative",
                    ),
                )
            )
        )

        self.assertIn("source_surface_classification_role_mismatch", codes(report))

    def test_project_ledger_uses_normative_contract_sources_and_separate_bindings(self):
        ledger_model = load_repo_model(
            ".flowguard/behavior_commitment_ledger/model.py",
            "flowguard_behavior_commitment_ledger_external_contract_test",
        )
        project_ledger = ledger_model.build_flowguard_behavior_commitment_ledger()

        self.assertTrue(project_ledger.source_surfaces)
        self.assertEqual(
            {BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT},
            {surface.source_classification for surface in project_ledger.source_surfaces},
        )
        self.assertTrue(
            all(surface.licenses_external_commitment() for surface in project_ledger.source_surfaces)
        )
        self.assertFalse(
            any(
                member.endswith(".py")
                for surface in project_ledger.source_surfaces
                for member in surface.metadata["live_source_identity"]["member_paths"]
            )
        )
        self.assertTrue(
            all(commitment.evidence.has_required_links() for commitment in project_ledger.commitments)
        )

    def test_permanent_owner_commitments_and_public_facade_evidence_are_current(self):
        ledger_model = load_repo_model(
            ".flowguard/behavior_commitment_ledger/model.py",
            "flowguard_behavior_commitment_ledger_permanent_owner_test",
        )
        project_ledger = ledger_model.build_flowguard_behavior_commitment_ledger()
        commitment_by_id = {
            commitment.commitment_id: commitment
            for commitment in project_ledger.commitments
        }

        expected_owners = {
            "commitment:validation-evidence-gates": ".flowguard/validation_evidence_gates/model.py",
            "commitment:user-facing-model-diagrams": ".flowguard/user_facing_model_diagrams/model.py",
            "commitment:codex-skill-satellites": ".flowguard/codex_skill_satellites/model.py",
        }
        for commitment_id, owner_model_id in expected_owners.items():
            with self.subTest(commitment_id=commitment_id):
                self.assertIn(commitment_id, commitment_by_id)
                self.assertEqual(
                    owner_model_id,
                    commitment_by_id[commitment_id].primary_owner_model_id,
                )

        public_api = commitment_by_id["commitment:flowguard-public-api-surface"]
        self.assertIn(
            ".flowguard/architecture_reduction/run_checks.py",
            public_api.path_authority.evidence_refs,
        )
        self.assertNotIn(
            ".flowguard/reduce_architecture_surface/run_checks.py",
            public_api.path_authority.evidence_refs,
        )

    def test_ui_content_admission_has_single_primary_owner(self):
        ledger_model = load_repo_model(
            ".flowguard/behavior_commitment_ledger/model.py",
            "flowguard_behavior_commitment_ledger_model_for_test",
        )
        closure_model = load_repo_model(
            ".flowguard/harden_ui_content_visibility_validation/model.py",
            "flowguard_ui_content_visibility_closure_model_for_test",
        )
        project_ledger = ledger_model.build_flowguard_behavior_commitment_ledger()
        commitments = tuple(
            item
            for item in project_ledger.commitments
            if item.commitment_id == closure_model.OBLIGATION_ID
        )

        self.assertEqual(1, len(commitments))
        commitment_row = commitments[0]
        self.assertEqual(
            ".flowguard/ui_flow_structure_skill/model.py",
            commitment_row.primary_owner_model_id,
        )
        self.assertNotIn(
            commitment_row.primary_owner_model_id,
            commitment_row.supporting_model_ids,
        )
        self.assertEqual(
            (closure_model.OBLIGATION_ID,),
            commitment_row.evidence.model_obligation_ids,
        )
        self.assertEqual(
            (
                closure_model.CODE_CONTRACT_ID,
                "owner-contract:.flowguard/ui_flow_structure_skill/model.py",
            ),
            commitment_row.evidence.code_contract_ids,
        )
        self.assertEqual(
            closure_model.TEST_EVIDENCE_IDS,
            commitment_row.evidence.test_evidence_ids,
        )

        contract_report = closure_model.contract_exhaustion_report()
        self.assertTrue(contract_report.ok, contract_report.format_text())
        self.assertEqual(
            tuple(case.case_id for case in contract_report.generated_cases),
            commitment_row.evidence.coverage_case_ids,
        )
        self.assertEqual(
            (closure_model.CONTRACT_SHARD_ID,),
            commitment_row.evidence.coverage_shard_ids,
        )
        self.assertEqual(
            (closure_model.CONTRACT_COVERAGE_RECEIPT_ID,),
            commitment_row.evidence.coverage_receipt_ids,
        )

    def test_every_active_flowguard_commitment_binds_its_current_blueprint_owner_contract(self):
        ledger_model = load_repo_model(
            ".flowguard/behavior_commitment_ledger/model.py",
            "flowguard_behavior_commitment_owner_contracts_for_test",
        )
        project_ledger = ledger_model.build_flowguard_behavior_commitment_ledger()

        for commitment in project_ledger.commitments:
            if not commitment.active_external_commitment():
                continue
            expected_owner_contract_id = (
                "owner-contract:"
                + commitment.primary_owner_model_id.replace("\\", "/")
            )
            with self.subTest(commitment_id=commitment.commitment_id):
                self.assertIn(
                    expected_owner_contract_id,
                    commitment.evidence.code_contract_ids,
                )

    def test_missing_expected_commitment_blocks(self):
        report = review_behavior_commitment_ledger(ledger(expected=("commitment:missing",)))

        self.assertFalse(report.ok)
        self.assertIn("expected_commitment_missing", codes(report))

    def test_source_surface_without_commitment_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(surfaces=(surface(commitment_ids=()),))
        )

        self.assertFalse(report.ok)
        self.assertIn("source_surface_missing_commitment", codes(report))
        self.assertIn("surface:docs-workflow", report.unmapped_surface_ids)

    def test_commitment_without_source_ref_blocks_as_extra_behavior(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(source_surface_ids=(), source_refs=()),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_missing_source_ref", codes(report))
        self.assertIn("commitment:workflow", report.extra_commitment_ids)

    def test_primary_owner_overlap_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(supporting_model_ids=("model:workflow",)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("primary_owner_also_supporting", codes(report))

    def test_unknown_dependency_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(
                        relations=(
                            BehaviorCommitmentRelation(
                                "commitment:missing",
                                BCL_RELATION_DEPENDS_ON,
                                rationale="workflow depends on missing external promise",
                            ),
                        ),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_relation_target_unknown", codes(report))

    def test_same_exact_intent_cannot_create_second_active_commitment(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(),
                    commitment(commitment_id="commitment:workflow-parallel"),
                ),
                surfaces=(
                    surface(
                        commitment_ids=(
                            "commitment:workflow",
                            "commitment:workflow-parallel",
                        )
                    ),
                ),
                expected=("commitment:workflow", "commitment:workflow-parallel"),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("duplicate_exact_intent_commitment", codes(report))

    def test_delegate_surface_must_not_be_registered_as_second_commitment(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(surface_delegation_only=True),))
        )

        self.assertFalse(report.ok)
        self.assertIn("delegate_commitment_forbidden", codes(report))

    def test_scoped_out_commitment_requires_disposition(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(
                        in_scope=False,
                        scoped_out_reason="",
                        owner="",
                        validation_boundary="",
                        rationale="",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("scoped_out_behavior_missing_disposition", codes(report))

    def test_changed_source_surface_blocks_broad_claim_until_ledger_is_refreshed(self):
        report = review_behavior_commitment_ledger(
            ledger(surfaces=(surface(freshness_state=BCL_SOURCE_FRESHNESS_CHANGED),))
        )

        self.assertFalse(report.ok)
        self.assertIn("source_surface_freshness_not_current", codes(report))

    def test_replaced_behavior_requires_replacement_disposition(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(replacement_state=BCL_REPLACEMENT_REPLACED),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_replacement_disposition_missing", codes(report))
        self.assertIn("commitment_lifecycle_disposition_missing", codes(report))

    def test_stale_owner_model_blocks_broad_claim(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(model_sync_state=BCL_MODEL_SYNC_OWNER_STALE),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_model_sync_not_current", codes(report))

    def test_missing_test_mesh_shard_blocks_broad_claim(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(evidence=evidence(test_mesh_state=BCL_TEST_MESH_SHARD_MISSING)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_test_mesh_not_current", codes(report))

    def test_model_miss_backfeed_requires_existing_commitment_model_and_dcar_case(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(
                        miss_origin_state=BCL_MISS_ORIGIN_OBSERVED,
                        model_sync_state=BCL_MODEL_SYNC_OWNER_STALE,
                        evidence=evidence(coverage_case_ids=()),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_model_miss_backfeed_incomplete", codes(report))

    def test_model_miss_on_existing_commitment_must_not_create_duplicate_commitment(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(miss_origin_state=BCL_MISS_ORIGIN_OBSERVED),
                    commitment(
                        label="duplicate point-fix commitment",
                        miss_origin_state=BCL_MISS_ORIGIN_OBSERVED,
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("duplicate_commitment_id", codes(report))


if __name__ == "__main__":
    unittest.main()
