import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
import json
from pathlib import Path

from flowguard.model_authority import (
    LIFECYCLE_ACTIVE,
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    ROLLBACK_RESULT_EXACT,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelActivationReceipt,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelInputRef,
    ModelInstanceRef,
    ModelRelation,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelRollbackReceipt,
    ModelSystemSnapshot,
    RevisionEvidenceRef,
    RevisionMemberChange,
    canonical_fingerprint,
)
from flowguard.model_revision_set import (
    MODEL_REVISION_SET_CURRENT_SCHEMA,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from flowguard.model_authority_store import (
    _load_bound_read_projection,
    _collect_rebuild_reachable_artifacts,
    activate_model_revision_set,
    audit_model_authority,
    bootstrap_model_authority,
    load_current_accepted_revision_set,
    load_current_model_authority_state,
    load_observed_model_system,
    rollback_observed_model_system,
)
from flowguard.model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    verify_model_intent_sources,
)
from flowguard.model_intent_authority import (
    CurrentEffectiveIntentView,
    EffectiveIntentTransition,
    LEGACY_CURRENT_REVISION_SCHEMA,
    _bootstrap_source_audit,
    bootstrap_current_effective_intent_view,
    build_current_effective_intent_view,
    build_current_intent_bootstrap_receipt,
)
from flowguard.existing_model_preflight import (
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)
from flowguard.project_manifest import project_manifest_lock
from flowguard.model_system_inventory import ManifestModelInventory
from flowguard.source_identity import source_file_fingerprint
from tests.test_model_maturation import _path_quality




def test_r9_e05_01_new_test_duplicated_legacy_read_appears_in_total_despite_cache195(tmp_path):
    from flowguard.model_authority_store import ReadAccounting, _SelectedReadContext, _selected_file_bytes
    accounting = ReadAccounting()
    context = _SelectedReadContext(tmp_path, accounting=accounting)
    for number in range(195):
        path = "input-%03d.json" % number
        raw = (json.dumps({"input": number}) + "\n").encode("utf-8")
        (tmp_path / path).write_bytes(raw)
        assert context.artifact_bytes(path) == raw
        assert context.artifact_bytes(path) == raw
    # Account a real unshared legacy read at its reader boundary. It must
    # remain visible even though the byte cache's diagnostic count is 195.
    raw = _selected_file_bytes(tmp_path, "input-000.json")
    accounting.record("input-000.json", raw, "legacy_unshared")
    assert len(context.payloads) == sum(context.read_counts.values()) == 195
    assert len(accounting.calls) == 196
    assert accounting.calls[:-1] == [
        (path, "initial", len(value)) for path, value in context.payloads.items()
    ]
    assert accounting.calls[-1] == ("input-000.json", "legacy_unshared", len(raw))
    assert [phase for path, phase, _ in accounting.calls if path == "input-000.json"] == [
        "initial", "legacy_unshared"
    ]


def _r9_accounting_observation(tmp_path, accounting):
    from flowguard.model_authority_store import _SelectedReadContext, _section, freeze_selected_read_observation
    manifest = tmp_path / ".flowguard/project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('[flowguard]\nadopted_package_version = "0.68.15"\n', encoding="utf-8")
    head = bootstrap_model_authority(tmp_path, snapshot("git:" + "a" * 40, SHA_A, "r9-counter-fixture"),
        bootstrap_evidence_fingerprint=SHA_D)
    context = _SelectedReadContext(tmp_path, accounting=accounting)
    context.authority_section = _section(context.artifact_bytes(".flowguard/project.toml").decode("utf-8"))
    (tmp_path / "finite.json").write_bytes(b'{"actual":true}\n')
    context.artifact_bytes("finite.json")
    context.missing_paths.add("absent.json")
    return context, freeze_selected_read_observation(context)


def test_r9_e05_02_new_test_ending_reread_counted_separately(tmp_path):
    from flowguard.model_authority_store import ReadAccounting, verify_selected_read_observation
    accounting = ReadAccounting()
    context, observation = _r9_accounting_observation(tmp_path, accounting)
    first = tuple(accounting.calls)
    guard = verify_selected_read_observation(observation, accounting=accounting)
    assert guard.ok, guard.to_dict()
    assert accounting.calls[:len(first)] == list(first)
    assert all(phase == "initial" for _, phase, _ in first)
    assert all(phase == "endguard" for _, phase, _ in accounting.calls[len(first):])
    assert {path for path, _, _ in first} == {path for path, _, _ in accounting.calls[len(first):]}
    ending = accounting.calls[len(first):]
    assert len(first) == len(ending) == len(context.payloads)
    assert len(accounting.calls) == 2 * len(context.payloads)
    assert {(path, size) for path, _, size in first} == {
        (path, len(value)) for path, value in context.payloads.items()
    }
    assert {(path, size) for path, _, size in ending} == {
        (path, len(value)) for path, value in context.payloads.items()
    }
    assert len({path for path, _, _ in ending}) == len(ending)
    assert accounting.existence_check_count == 1


def test_r9_e05_03_new_test_counter_off_on_cannot_change_public_payload_semantic_fingerprint(tmp_path):
    from flowguard.__main__ import _read_operation
    import flowguard.model_authority_store as store
    from flowguard.model_authority_store import ReadAccounting, _SelectedReadContext, freeze_selected_read_observation, verify_selected_read_observation
    counted, _ = _r9_accounting_observation(tmp_path, ReadAccounting())
    uncounted = _SelectedReadContext(tmp_path)
    for path in counted.payloads:
        assert uncounted.artifact_bytes(path) == counted.artifact_bytes(path)
        assert uncounted.functional_fingerprint(path) == counted.functional_fingerprint(path)
    uncounted.authority_section = dict(counted.authority_section)
    uncounted.missing_paths = set(counted.missing_paths)
    before = freeze_selected_read_observation(counted)
    without = freeze_selected_read_observation(uncounted)
    assert before == without
    measured = verify_selected_read_observation(before, accounting=counted.accounting)
    plain = verify_selected_read_observation(without)
    assert measured.ok and plain.ok
    assert canonical_fingerprint(measured.to_dict()) == canonical_fingerprint(plain.to_dict())
    assert "accounting" not in measured.to_dict()
    # Counter selection also cannot change the genuine public lifecycle's
    # payload, including its honest bootstrap-only blocker. This fixture is
    # deliberately not relabelled as a current accepted functional system.
    query = {"operation": "read", "target_id": "flowguard", "scope": ["authority"], "read_batch": True}
    plain_public = _read_operation(tmp_path, query, {})
    sink = ReadAccounting()
    constructor = store._SelectedReadContext
    def counted_context(root, **kwargs):
        kwargs["accounting"] = sink
        return constructor(root, **kwargs)
    with patch.object(store, "_SelectedReadContext", new=counted_context):
        counted_public = _read_operation(tmp_path, query, {})
    assert sink.calls
    assert canonical_fingerprint(counted_public) == canonical_fingerprint(plain_public)


def test_r9_e05_04_new_test_unavailable_llm_usage_stays_not_measured(tmp_path):
    from flowguard.model_authority_store import ReadAccounting
    raw = b'{"input":"actual bytes, no LLM API invocation"}\n'
    path = tmp_path / "actual.json"
    path.write_bytes(raw)
    sink = ReadAccounting()
    observed = path.read_bytes()
    assert observed == raw
    sink.record("actual.json", observed, "initial")
    assert vars(sink) == {
        "calls": [("actual.json", "initial", len(raw))],
        "existence_check_count": 0,
    }


def _rebind_fixture_quality(root, revision_set):
    """Produce and retain actual same-review details for this finite store fixture."""
    from flowguard.model_path_quality import (
        NecessityWitness, derive_retained_elements, lightweight_path_review,
        normalized_model_facts_fingerprint,
    )
    from flowguard.model_authority_store import _write_immutable_json
    from tests.test_model_path_quality import clean_facts
    facts = clean_facts()
    retained = tuple(derive_retained_elements(facts))
    obligations = tuple(sorted("obligation:" + element for element, _ in retained))
    subjects, results = [], []
    for prior in revision_set.path_quality_subjects:
        subject = replace(prior,
            intent_fingerprint=revision_set.current_effective_intent_view.fingerprint,
            normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts),
            retained_element_inventory_fingerprint=canonical_fingerprint(dict(retained)),
            obligation_fingerprint=canonical_fingerprint(list(obligations)))
        witnesses = tuple(NecessityWitness(
            witness_id="witness:" + element, subject_fingerprint=subject.fingerprint,
            element_id=element, element_kind=kind, obligation_id="obligation:" + element,
            counterexample_id="counterexample:" + element, oracle_id="oracle:" + element,
            evidence_fingerprint=canonical_fingerprint({"fixture_witness": element}),
            evidence_currentness_id=subject.currentness_id) for element, kind in retained)
        details = []
        result = lightweight_path_review(subject, facts, necessity_witnesses=witnesses,
            active_obligation_ids=obligations, detail_collector=details)
        assert len(details) == 1 and details[0].fingerprint == result.detail_evidence_fingerprint
        _write_immutable_json(root, "path-quality-details", details[0].fingerprint, details[0].to_dict())
        subjects.append(subject)
        results.append(result)
    return replace(revision_set, path_quality_subjects=tuple(subjects),
        path_quality_results=tuple(results), path_quality_result_set_fingerprint="")


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def model(sha: str) -> ModelInstanceRef:
    return ModelInstanceRef(
        logical_model_id="authority",
        model_kind="workflow",
        model_path=".flowguard/authority/model.py",
        model_sha256=sha,
        runner_path=".flowguard/authority/run_checks.py",
        runner_sha256=SHA_D,
        purpose_closure_fingerprint=SHA_C,
        inputs=(
            ModelInputRef(".flowguard/authority/model.py", sha),
            ModelInputRef(".flowguard/authority/run_checks.py", SHA_D),
        ),
    )


def snapshot(revision: str, sha: str, snapshot_id: str) -> ModelSystemSnapshot:
    member = model(sha)
    purpose_ref = AuthorityEndpointRef(
        endpoint_kind="parent_closure",
        endpoint_id="purpose:authority",
        fingerprint=member.purpose_closure_fingerprint,
        owner_route="model_test_alignment",
    )
    realization = ModelRelation(
        relation_id="relation:model-realizes-purpose:authority",
        kind="realizes",
        source=AuthorityEndpointRef(
            endpoint_kind="model_instance",
            endpoint_id="model:authority",
            fingerprint=member.fingerprint,
            owner_route="model_regression_manifest",
        ),
        target=purpose_ref,
        evidence_fingerprints=(member.purpose_closure_fingerprint,),
    )
    dimensions = tuple(
        CoverageDimension(
            dimension_id=value,
            required_ids=(f"{value}:one",),
            covered_ids=(f"{value}:one",),
        )
        for value in sorted(
            {
                "external_surfaces",
                "behavior_commitments",
                "model_instances",
                "fields_state_side_effects",
                "code_contracts",
                "tests_evidence",
            }
        )
    )
    return ModelSystemSnapshot(
        snapshot_id=snapshot_id,
        system_id="flowguard",
        subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
        lifecycle=LIFECYCLE_ACTIVE,
        subject_revision=revision,
        root_instance_fingerprints=(member.fingerprint,),
        model_instances=(member,),
        relations=(realization,),
        coverage=CoverageUniverse(
            boundary_id="store-test",
            source_inventory_fingerprint=SHA_A,
            dimensions=dimensions,
            claim_boundary=(
                "This finite store test boundary does not claim production "
                "software or unenumerated external behavior."
            ),
        ),
        owner_artifact_refs=(
            purpose_ref,
            AuthorityEndpointRef(
                endpoint_kind="development_process",
                endpoint_id="dpf:authority",
                fingerprint=SHA_B,
                owner_route="development_process_flow",
            ),
        ),
        unresolved_gap_ids=(),
        claim_boundary=(
            "This snapshot exists only for durable store transaction tests and "
            "does not claim production software behavior."
        ),
    )


def _current_intent(root: Path) -> ModelIntentContribution:
    source = root / "docs" / "authority-current-design.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text(
            "The authority model owns the durable pointer transaction.\n",
            encoding="utf-8",
        )
    return ModelIntentContribution(
        contribution_id="intent:current-design:authority",
        source_kind="design",
        source_ref=source.relative_to(root).as_posix(),
        source_fingerprint=source_file_fingerprint(source),
        subject_lane="normative_target",
        subject_role="design",
        lifecycle_state="candidate",
        decision_state="accepted",
        logical_model_id="model:authority",
        unresolved_owner_id="",
        supersedes_contribution_ids=(),
        conflicts_with_contribution_ids=(),
        target_obligation_ids=(),
        target_state_ids=(),
        target_transition_ids=(),
        target_invariant_ids=(),
        target_relation_ids=("relation:model-realizes-purpose:authority",),
        desired_terminal_state_ids=(),
        target_output_ids=(),
        declared_consumer_ids=(),
        effective_revision="current-design:authority",
        rationale=(
            "The durable authority transaction is owned by this exact model "
            "and remains traceable to one current design source."
        ),
    )


def revision(root: Path, head, base, candidate) -> ModelRevisionSet:
    if head.generation == 1:
        active_contributions = (_current_intent(root),)
        bootstrap_receipt = build_current_intent_bootstrap_receipt(
            root,
            receipt_id=f"receipt:intent-bootstrap:{candidate.snapshot_id}",
            candidate_snapshot=candidate,
            current_design_contributions=active_contributions,
            rationale=(
                "The store fixture explicitly binds its one current model owner "
                "to the exact current design without inferring historical intent."
            ),
        )
        current_effective_intent_view = bootstrap_current_effective_intent_view(
            candidate,
            active_contributions,
            verify_model_intent_sources(root, active_contributions),
            bootstrap_receipt,
        )
    else:
        current_revision = load_current_accepted_revision_set(
            root,
            head=head,
            snapshot=base,
        )
        if current_revision is None:
            raise AssertionError("current v5 revision fixture is missing")
        base_view = current_revision.current_effective_intent_view
        transitions = tuple(
            EffectiveIntentTransition(
                prior_contribution_id=item.contribution_id,
                prior_contribution_fingerprint=item.fingerprint,
                action="retain",
                replacement_contribution_ids=(),
                reason=(
                    "The exact current store design remains active across this "
                    "fixture revision without semantic replacement."
                ),
            )
            for item in base_view.active_contributions
        )
        current_effective_intent_view = build_current_effective_intent_view(
            base_view,
            candidate,
            base_view.active_contributions,
            verify_model_intent_sources(root, base_view.active_contributions),
            transitions,
        )
    diff = derive_revision_snapshot_diff(base, candidate)
    closure = derive_revision_affected_closure(base, candidate, diff)
    path_quality_rows = tuple(
        _path_quality(
            member.member_id,
            member.candidate_instance_fingerprint,
            candidate.fingerprint,
        )
        for member in diff.members
        if member.operation in {"add", "replace"}
    )
    ids_by_owner: dict[str, list[str]] = {}
    for affected_id, owner_route in closure.owner_bindings:
        ids_by_owner.setdefault(owner_route, []).append(affected_id)
    required = tuple(
        RevisionEvidenceRef(
            receipt_id=f"receipt:store:{index}",
            receipt_fingerprint=(
                "sha256:" + f"{index:x}"[-1] * 64
            ),
            owner_route=owner_route,
            subject_fingerprint=candidate.fingerprint,
            obligation_ids=(f"obligation:store:{index}",),
            affected_closure_fingerprint=closure.fingerprint,
            covered_affected_ids=tuple(ids_by_owner[owner_route]),
            candidate_snapshot_fingerprint=candidate.fingerprint,
            toolchain_fingerprint=SHA_C,
            environment_fingerprint=SHA_D,
            status=REVISION_EVIDENCE_REQUIRED,
            current=True,
            eligible=True,
        )
        for index, owner_route in enumerate(sorted(ids_by_owner), 1)
    )
    proposed = ModelRevisionSet(
        revision_set_id="revision:store",
        task_id="task:store",
        expected_head_fingerprint=head.fingerprint,
        base_snapshot_fingerprint=base.fingerprint,
        candidate_snapshot_fingerprint=candidate.fingerprint,
        members=diff.members,
        affected_closure_ids=closure.affected_ids,
        affected_closure_fingerprint=closure.fingerprint,
        affected_edge_ids=closure.edge_ids,
        affected_owner_bindings=closure.owner_bindings,
        snapshot_diff_fingerprint=diff.fingerprint,
        changed_root_ids=diff.changed_root_ids,
        changed_relation_ids=diff.changed_relation_ids,
        changed_source_surface_ids=diff.changed_source_surface_ids,
        changed_commitment_ids=diff.changed_commitment_ids,
        changed_field_ids=diff.changed_field_ids,
        changed_side_effect_ids=diff.changed_side_effect_ids,
        changed_contract_ids=diff.changed_contract_ids,
        changed_test_ids=diff.changed_test_ids,
        changed_system_property_ids=diff.changed_system_property_ids,
        changed_coverage_ids=diff.changed_coverage_ids,
        changed_gap_ids=diff.changed_gap_ids,
        changed_owner_artifact_ids=diff.changed_owner_artifact_ids,
        added_ids=diff.added_ids,
        removed_ids=diff.removed_ids,
        fingerprint_changed_ids=diff.fingerprint_changed_ids,
        current_effective_intent_view=current_effective_intent_view,
        no_declared_intent_rationale_id="no-intent:store-fixture",
        no_declared_intent_evidence_fingerprints=(
            ("fixture_scope", candidate.fingerprint),
        ),
        no_declared_intent_rationale=(
            "This isolated durable-store fixture has no external product intent "
            "beyond exercising its declared transaction boundary."
        ),
        required_evidence_refs=required,
        required_path_quality_model_ids=tuple(
            subject.model_id for subject, _result in path_quality_rows
        ),
        path_quality_subjects=tuple(
            subject for subject, _result in path_quality_rows
        ),
        path_quality_results=tuple(
            result for _subject, result in path_quality_rows
        ),
    )
    return _rebind_fixture_quality(root, proposed.accept(
        (
            *(
                replace(
                    item,
                    status=REVISION_EVIDENCE_PASS,
                )
                for item in required
            ),
        ),
        reason="store evidence passed",
    ))


def manifest_inventory() -> ManifestModelInventory:
    return ManifestModelInventory(
        declared_ids=("authority",),
        materialized_ids=("authority",),
        required_ids=("authority",),
        covered_ids=("authority",),
        missing_ids=(),
    )


class ModelAuthorityStoreTests(unittest.TestCase):
    def test_rebuild_reachability_walks_multiple_authority_generations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                '[flowguard]\nadopted_package_version = "0.68.15"\n',
                encoding="utf-8",
            )
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head_one = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_one = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted_one = revision(root, head_one, base, candidate_one)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_one,
            ):
                head_two, _receipt_one = activate_model_revision_set(
                    root,
                    candidate_one,
                    accepted_one,
                )

            candidate_two = snapshot("git:" + "c" * 40, SHA_C, "observed-c")
            accepted_two = revision(root, head_two, candidate_one, candidate_two)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_two,
            ):
                head_three, _receipt_two = activate_model_revision_set(
                    root,
                    candidate_two,
                    accepted_two,
                )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            # Historical reachability can authenticate old transitions, but
            # the public current reader still rejects a caller's old pair.
            with self.assertRaisesRegex(ModelAuthorityError, "supplied authority pair differs"):
                load_current_model_authority_state(root, head=head_two, snapshot=candidate_one)
            reachable = _collect_rebuild_reachable_artifacts(
                root,
                loaded_head,
                loaded_snapshot,
            )
            self.assertEqual(head_three, loaded_head)
            expected = {
                ("bootstraps", head_one.accepted_revision_set_fingerprint),
                ("revisions", accepted_one.fingerprint),
                ("revisions", accepted_two.fingerprint),
                ("activations", head_two.activation_receipt_fingerprint),
                ("activations", head_three.activation_receipt_fingerprint),
                ("snapshots", base.fingerprint),
                ("snapshots", candidate_one.fingerprint),
                ("snapshots", candidate_two.fingerprint),
            }
            for generation_head in (head_two, head_three):
                projection = _load_bound_read_projection(root, generation_head)
                expected.add(
                    ("read-projection-indexes", projection["index_fingerprint"])
                )
                for row in projection["index"]["models"].values():
                    expected.add(("read-model-shards", row["shard_fingerprint"]))
            for accepted in (accepted_one, accepted_two):
                for result in accepted.path_quality_results:
                    expected.add(("path-quality-details", result.detail_evidence_fingerprint))
                    self.assertTrue(
                        (root / ".flowguard/models/authority/path-quality-details" /
                         (result.detail_evidence_fingerprint.removeprefix("sha256:") + ".json")).is_file()
                    )
            self.assertEqual(expected, reachable)

    def test_bootstrap_and_activation_update_pointer_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text(
                '[flowguard]\nadopted_package_version = "0.61.0"\n',
                encoding="utf-8",
            )
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                next_head, receipt = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(next_head, loaded_head)
            self.assertEqual(candidate, loaded_snapshot)
            self.assertEqual(receipt.fingerprint, loaded_head.activation_receipt_fingerprint)
            self.assertTrue(
                (
                    root
                    / ".flowguard"
                    / "models"
                    / "authority"
                    / "revisions"
                    / f"{accepted.fingerprint.split(':')[1]}.json"
                ).is_file()
            )

    def test_historical_typed_transition_replay_skips_new_candidate_binding_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                next_head, _ = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            regression_manifest = (
                root / ".flowguard" / "model-regression-manifest.json"
            )
            regression_manifest.write_text("{}\n", encoding="utf-8")
            with patch(
                "flowguard.model_regressions.ModelRegressionManifest.load",
                side_effect=AssertionError(
                    "historical replay must not consult the live candidate manifest"
                ),
            ) as live_manifest_load, patch(
                "flowguard.model_authority_store."
                "validate_candidate_intent_source_input_bindings"
            ) as frozen_binding_check:
                loaded = load_current_accepted_revision_set(
                    root,
                    head=next_head,
                    snapshot=candidate,
                )

            self.assertEqual(accepted, loaded)
            live_manifest_load.assert_not_called()
            frozen_binding_check.assert_not_called()

    def test_new_activation_still_checks_live_candidate_manifest_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            (
                root
                / ".flowguard"
                / "models"
                / "regression-manifest.json"
            ).parent.mkdir(parents=True, exist_ok=True)
            (
                root
                / ".flowguard"
                / "models"
                / "regression-manifest.json"
            ).write_text(
                "{}\n",
                encoding="utf-8",
            )
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_regressions.ModelRegressionManifest.load",
                return_value=object(),
            ) as live_manifest_load, patch(
                "flowguard.model_regressions.audit_intent_source_input_bindings",
                return_value=(),
            ) as live_binding_audit, patch(
                "flowguard.model_authority_store."
                "validate_candidate_intent_source_input_bindings"
            ) as frozen_binding_check:
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            self.assertGreaterEqual(live_manifest_load.call_count, 1)
            self.assertEqual(
                live_manifest_load.call_count,
                live_binding_audit.call_count,
            )
            self.assertEqual(
                live_manifest_load.call_count,
                frozen_binding_check.call_count,
            )

    def test_stale_candidate_cannot_overwrite_advanced_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "mismatch|changed|rebase",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

    def test_activation_replays_lineage_instead_of_trusting_base_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            initial_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            first = revision(root, initial_head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, _receipt = activate_model_revision_set(
                    root,
                    candidate,
                    first,
                )

            next_candidate = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            valid_next = revision(
                root,
                current_head,
                candidate,
                next_candidate,
            )
            valid_view = valid_next.current_effective_intent_view
            forged_view = CurrentEffectiveIntentView(
                system_id=valid_view.system_id,
                subject_lane=valid_view.subject_lane,
                candidate_snapshot_fingerprint=(
                    valid_view.candidate_snapshot_fingerprint
                ),
                base_effective_intent_view_fingerprint=(
                    valid_view.base_effective_intent_view_fingerprint
                ),
                active_contributions=valid_view.active_contributions,
                verified_source_identities=valid_view.verified_source_identities,
                model_owner_ids=valid_view.model_owner_ids,
                owner_bindings=valid_view.owner_bindings,
                transitions=(),
            )
            forged_revision = replace(
                valid_next,
                current_effective_intent_view=forged_view,
            )
            forged_revision = _rebind_fixture_quality(root, forged_revision)
            before = manifest.read_bytes()

            with self.assertRaisesRegex(
                ModelAuthorityError,
                "every prior active intent requires",
            ):
                activate_model_revision_set(
                    root,
                    next_candidate,
                    forged_revision,
                )

            self.assertEqual(before, manifest.read_bytes())

    def test_failure_before_pointer_replacement_preserves_old_head_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_authority_store._write_immutable_json",
                side_effect=RuntimeError("injected immutable record failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

            self.assertEqual(before, manifest.read_bytes())
            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(head, loaded_head)
            self.assertEqual(base, loaded_snapshot)

    def test_final_live_resample_drift_preserves_old_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            drifted = replace(
                candidate,
                claim_boundary=(
                    "This final resample intentionally differs and therefore "
                    "cannot update the observed authority pointer."
                ),
            )
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=(candidate, drifted),
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "changed before pointer",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(head, load_observed_model_system(root)[0])

    def test_pointer_persistence_failure_preserves_old_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_authority_store.replace_project_manifest_locked",
                side_effect=RuntimeError("injected pointer persistence failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "pointer persistence"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(head, load_observed_model_system(root)[0])

    def test_two_candidates_from_one_head_have_one_cas_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_b = snapshot(
                "git:" + "b" * 40,
                SHA_B,
                "observed-b",
            )
            candidate_c = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            revision_b = revision(root, head, base, candidate_b)
            revision_c = replace(
                revision(root, head, base, candidate_c),
                revision_set_id="revision:store-c",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_b,
            ):
                winner_head, _ = activate_model_revision_set(
                    root,
                    candidate_b,
                    revision_b,
                )
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_c,
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "changed|rebase|base snapshot",
                ):
                    activate_model_revision_set(
                        root,
                        candidate_c,
                        revision_c,
                    )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(2, loaded_head.generation)
            self.assertEqual(winner_head, loaded_head)
            self.assertEqual(candidate_b, loaded_snapshot)

    def test_exact_rollback_activates_a_reverse_revision_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            initial_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            forward = revision(root, initial_head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, activation = activate_model_revision_set(
                    root,
                    candidate,
                    forward,
                )
            contract = ModelRollbackContract(
                contract_id="rollback:store",
                expected_head_fingerprint=current_head.fingerprint,
                originating_revision_set_fingerprint=forward.fingerprint,
                originating_activation_receipt_fingerprint=(
                    activation.fingerprint
                ),
                from_snapshot_fingerprint=candidate.fingerprint,
                to_snapshot_fingerprint=base.fingerprint,
                effects=(
                    ModelRollbackEffect(
                        effect_id="source",
                        kind="code_config",
                        disposition="restore",
                        required_evidence_fingerprints=(SHA_C,),
                    ),
                ),
                old_snapshot_conformance_evidence_fingerprints=(SHA_D,),
            )
            reverse = replace(
                revision(root, current_head, candidate, base),
                revision_set_id="revision:reverse-store",
                rollback_contract_fingerprint=contract.fingerprint,
                originating_revision_set_fingerprint=forward.fingerprint,
                originating_activation_receipt_fingerprint=(
                    activation.fingerprint
                ),
            )

            wrong_base_view = replace(
                reverse.current_effective_intent_view,
                base_effective_intent_view_fingerprint=SHA_D,
            )
            wrong_base_reverse = replace(
                reverse,
                current_effective_intent_view=wrong_base_view,
            )
            with self.assertRaisesRegex(
                ModelAuthorityError,
                "exact current base view",
            ):
                rollback_observed_model_system(
                    root,
                    contract,
                    base,
                    wrong_base_reverse,
                    completed_evidence_fingerprints=(SHA_C, SHA_D),
                    requested_result=ROLLBACK_RESULT_EXACT,
                    receipt_id="rollback:wrong-base",
                    reason="This reverse revision intentionally binds the wrong base.",
                )

            rollback_observations = 0

            def restore_then_peer_write(*_args, **_kwargs):
                nonlocal rollback_observations
                rollback_observations += 1
                if rollback_observations == 2:
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8")
                        + '\n[rollback_peer]\nmarker = "preserved"\n',
                        encoding="utf-8",
                    )
                return base

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=restore_then_peer_write,
            ):
                rolled_head, rollback_receipt = rollback_observed_model_system(
                    root,
                    contract,
                    base,
                    reverse,
                    completed_evidence_fingerprints=(SHA_C, SHA_D),
                    requested_result=ROLLBACK_RESULT_EXACT,
                    receipt_id="rollback:store-receipt",
                    reason="source restored and old snapshot reconformed",
                )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(3, rolled_head.generation)
            self.assertEqual(reverse.fingerprint, rolled_head.accepted_revision_set_fingerprint)
            self.assertTrue(
                rolled_head.activation_receipt_fingerprint.startswith("sha256:")
            )
            self.assertNotEqual(
                rollback_receipt.fingerprint,
                rolled_head.activation_receipt_fingerprint,
            )
            self.assertEqual(rolled_head, loaded_head)
            self.assertEqual(base, loaded_snapshot)
            self.assertIn(
                '[rollback_peer]\nmarker = "preserved"',
                manifest.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                reverse,
                load_current_accepted_revision_set(
                    root,
                    head=loaded_head,
                    snapshot=loaded_snapshot,
                ),
            )
            current_state = load_current_model_authority_state(
                root,
                head=loaded_head,
                snapshot=loaded_snapshot,
            )
            self.assertEqual("rollback", current_state.transition_kind)
            self.assertEqual(rollback_receipt, current_state.rollback_receipt)
            rollback_path = (
                root
                / ".flowguard"
                / "models"
                / "authority"
                / "rollbacks"
                / f"{rollback_receipt.fingerprint.split(':', 1)[1]}.json"
            )
            rollback_path.unlink()
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                missing_receipt_report = audit_model_authority(root)
            self.assertIn(
                "current_authority_transition_invalid",
                {finding.code for finding in missing_receipt_report.findings},
            )

    def test_shared_manifest_lock_blocks_activation_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)

            with project_manifest_lock(manifest):
                with self.assertRaisesRegex(Exception, "locked"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

    def test_generation_one_audit_requires_explicit_intent_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertEqual(base.fingerprint, report.observed_snapshot_fingerprint)
            self.assertEqual(
                "flowguard.model_authority_bootstrap.v1",
                report.accepted_revision_schema,
            )
            self.assertEqual(
                head.accepted_revision_set_fingerprint,
                report.accepted_revision_fingerprint,
            )
            self.assertEqual("bootstrap_required", report.intent_mode)
            self.assertEqual(0, report.active_intent_contribution_count)
            self.assertIn(
                "current_effective_intent_bootstrap_required",
                {finding.code for finding in report.findings},
            )

    def test_legacy_v4_audit_rejects_unproved_ancestry_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            legacy_head = replace(
                bootstrap_head,
                generation=52,
                accepted_revision_set_fingerprint=SHA_B,
                activation_receipt_fingerprint=SHA_C,
            )

            with patch(
                "flowguard.model_authority_store.load_observed_model_system",
                return_value=(legacy_head, base),
            ), patch(
                "flowguard.model_authority_store._accepted_revision_schema",
                return_value=LEGACY_CURRENT_REVISION_SCHEMA,
            ), patch(
                "flowguard.model_authority_store._load_accepted_revision_set",
            ) as load_revision, patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            load_revision.assert_not_called()
            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertEqual(
                LEGACY_CURRENT_REVISION_SCHEMA,
                report.accepted_revision_schema,
            )
            self.assertEqual("blocked", report.intent_mode)
            self.assertEqual(0, report.active_intent_contribution_count)
            self.assertIn(
                "legacy_authority_ancestry_invalid",
                {finding.code for finding in report.findings},
            )
            self.assertNotIn(
                "accepted_revision_invalid",
                {finding.code for finding in report.findings},
            )

    def test_legacy_ancestry_uses_exact_heads_and_traverses_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "legacy-base")
            bootstrap_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_one = snapshot(
                "git:" + "b" * 40,
                SHA_B,
                "legacy-one",
            )
            candidate_two = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "legacy-two",
            )
            prototype = revision(root, bootstrap_head, base, candidate_one)

            def write_artifact(category, fingerprint, payload):
                path = (
                    root
                    / ".flowguard"
                    / "models"
                    / "authority"
                    / category
                    / f"{fingerprint.split(':', 1)[1]}.json"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            def legacy_revision_payload(
                revision_id,
                expected_head,
                base_fingerprint,
                candidate_fingerprint,
                *,
                rollback_contract_fingerprint="",
                origin_revision_fingerprint="",
                origin_receipt_fingerprint="",
            ):
                payload = prototype.to_dict()
                payload["schema"] = LEGACY_CURRENT_REVISION_SCHEMA
                payload["revision_set_id"] = revision_id
                payload["expected_head_fingerprint"] = expected_head.fingerprint
                payload["base_snapshot_fingerprint"] = base_fingerprint
                payload["candidate_snapshot_fingerprint"] = candidate_fingerprint
                payload["rollback_contract_fingerprint"] = (
                    rollback_contract_fingerprint
                )
                payload["originating_revision_set_fingerprint"] = (
                    origin_revision_fingerprint
                )
                payload["originating_activation_receipt_fingerprint"] = (
                    origin_receipt_fingerprint
                )
                payload.pop("current_effective_intent_view")
                payload.pop("required_path_quality_model_ids")
                payload.pop("path_quality_subjects")
                payload.pop("path_quality_results")
                payload.pop("path_quality_result_set_fingerprint")
                payload["evidence_complete"] = True
                payload["intent_acceptance_ready"] = True
                identity = {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "fingerprint",
                        "evidence_complete",
                        "intent_acceptance_ready",
                    }
                }
                payload["fingerprint"] = canonical_fingerprint(identity)
                write_artifact("revisions", payload["fingerprint"], payload)
                return payload["fingerprint"]

            for item in (candidate_one, candidate_two):
                write_artifact("snapshots", item.fingerprint, item.to_dict())

            revision_one = legacy_revision_payload(
                "revision:legacy-one",
                bootstrap_head,
                base.fingerprint,
                candidate_one.fingerprint,
            )
            activation_one = ModelActivationReceipt(
                receipt_id="activation:legacy-one",
                system_id=base.system_id,
                revision_set_fingerprint=revision_one,
                expected_head_fingerprint=bootstrap_head.fingerprint,
                previous_snapshot_fingerprint=base.fingerprint,
                candidate_snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                next_generation=2,
            )
            write_artifact(
                "activations",
                activation_one.fingerprint,
                {**activation_one.to_dict(), "fingerprint": activation_one.fingerprint},
            )
            head_one = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                generation=2,
                accepted_revision_set_fingerprint=revision_one,
                previous_snapshot_fingerprint=base.fingerprint,
                activation_receipt_fingerprint=activation_one.fingerprint,
            )
            revision_two = legacy_revision_payload(
                "revision:legacy-two",
                head_one,
                candidate_one.fingerprint,
                candidate_two.fingerprint,
            )
            activation_two = ModelActivationReceipt(
                receipt_id="activation:legacy-two",
                system_id=base.system_id,
                revision_set_fingerprint=revision_two,
                expected_head_fingerprint=head_one.fingerprint,
                previous_snapshot_fingerprint=candidate_one.fingerprint,
                candidate_snapshot_fingerprint=candidate_two.fingerprint,
                subject_revision=candidate_two.subject_revision,
                next_generation=3,
            )
            write_artifact(
                "activations",
                activation_two.fingerprint,
                {**activation_two.to_dict(), "fingerprint": activation_two.fingerprint},
            )
            head_two = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_two.fingerprint,
                subject_revision=candidate_two.subject_revision,
                generation=3,
                accepted_revision_set_fingerprint=revision_two,
                previous_snapshot_fingerprint=candidate_one.fingerprint,
                activation_receipt_fingerprint=activation_two.fingerprint,
            )

            orphan = replace(
                activation_one,
                receipt_id="activation:unrelated-orphan",
            )
            write_artifact(
                "activations",
                orphan.fingerprint,
                {**orphan.to_dict(), "fingerprint": orphan.fingerprint},
            )
            activation_audit = _bootstrap_source_audit(
                root,
                head_two,
                candidate_two,
            )
            self.assertEqual(2, len(activation_audit.ancestry_revision_set_fingerprints))

            contract = ModelRollbackContract(
                contract_id="rollback:legacy-chain",
                expected_head_fingerprint=head_two.fingerprint,
                originating_revision_set_fingerprint=revision_two,
                originating_activation_receipt_fingerprint=activation_two.fingerprint,
                from_snapshot_fingerprint=candidate_two.fingerprint,
                to_snapshot_fingerprint=candidate_one.fingerprint,
                effects=(
                    ModelRollbackEffect(
                        effect_id="legacy-source",
                        kind="code_config",
                        disposition="restore",
                        required_evidence_fingerprints=(SHA_C,),
                    ),
                ),
                old_snapshot_conformance_evidence_fingerprints=(SHA_D,),
            )
            write_artifact(
                "rollback-contracts",
                contract.fingerprint,
                {**contract.to_dict(), "fingerprint": contract.fingerprint},
            )
            reverse_revision = legacy_revision_payload(
                "revision:legacy-reverse",
                head_two,
                candidate_two.fingerprint,
                candidate_one.fingerprint,
                rollback_contract_fingerprint=contract.fingerprint,
                origin_revision_fingerprint=revision_two,
                origin_receipt_fingerprint=activation_two.fingerprint,
            )
            rollback_receipt = ModelRollbackReceipt(
                receipt_id="rollback-receipt:legacy-chain",
                contract_fingerprint=contract.fingerprint,
                reverse_revision_set_fingerprint=reverse_revision,
                result=ROLLBACK_RESULT_EXACT,
                completed_evidence_fingerprints=(SHA_C, SHA_D),
                reason="The legacy rollback restored and reconformed the prior snapshot.",
            )
            write_artifact(
                "rollbacks",
                rollback_receipt.fingerprint,
                {
                    **rollback_receipt.to_dict(),
                    "fingerprint": rollback_receipt.fingerprint,
                },
            )
            rollback_head = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                generation=4,
                accepted_revision_set_fingerprint=reverse_revision,
                previous_snapshot_fingerprint=candidate_two.fingerprint,
                activation_receipt_fingerprint=rollback_receipt.fingerprint,
            )

            rollback_audit = _bootstrap_source_audit(
                root,
                rollback_head,
                candidate_one,
            )
            self.assertEqual(3, len(rollback_audit.ancestry_revision_set_fingerprints))
            self.assertEqual(
                rollback_receipt.fingerprint,
                rollback_audit.ancestry_activation_receipt_fingerprints[0],
            )

    def test_audit_validates_the_exact_accepted_revision_after_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual("pass", report.status)
            self.assertEqual(
                MODEL_REVISION_SET_CURRENT_SCHEMA,
                report.accepted_revision_schema,
            )
            self.assertEqual(
                accepted.fingerprint,
                report.accepted_revision_fingerprint,
            )
            self.assertEqual(
                accepted.current_effective_intent_view.fingerprint,
                report.current_effective_intent_view_fingerprint,
            )
            self.assertEqual("refine", report.intent_mode)
            self.assertEqual(1, report.active_intent_contribution_count)
            self.assertEqual(1, report.model_owner_denominator_count)
            self.assertEqual(1, report.owner_binding_count)

    def test_audit_blocks_when_current_transition_receipt_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, receipt = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )
            next_candidate = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            next_revision = revision(
                root,
                current_head,
                candidate,
                next_candidate,
            )
            receipt_path = (
                root
                / ".flowguard"
                / "models"
                / "authority"
                / "activations"
                / f"{receipt.fingerprint.split(':', 1)[1]}.json"
            )
            receipt_path.unlink()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=next_candidate,
            ), self.assertRaisesRegex(
                ModelAuthorityError,
                "exactly one typed transition receipt",
            ):
                activate_model_revision_set(
                    root,
                    next_candidate,
                    next_revision,
                )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertEqual(current_head.fingerprint, report.head_fingerprint)
            self.assertIn(
                "current_authority_transition_invalid",
                {finding.code for finding in report.findings},
            )

    def test_audit_reports_current_intent_source_staleness_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )
            source = root / "docs" / "authority-current-design.md"
            source.write_text(
                "The accepted design source changed after activation.\n",
                encoding="utf-8",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            codes = {finding.code for finding in report.findings}
            self.assertIn("current_intent_source_stale", codes)
            self.assertNotIn("accepted_revision_invalid", codes)

    def test_activation_replays_supersession_before_rechecking_current_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_one = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted_one = revision(root, head, base, candidate_one)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_one,
            ):
                current_head, _receipt = activate_model_revision_set(
                    root,
                    candidate_one,
                    accepted_one,
                )

            candidate_two = snapshot("git:" + "c" * 40, SHA_C, "observed-c")
            retained_revision = revision(
                root,
                current_head,
                candidate_one,
                candidate_two,
            )
            current_revision = load_current_accepted_revision_set(
                root,
                head=current_head,
                snapshot=candidate_one,
            )
            self.assertIsNotNone(current_revision)
            base_view = current_revision.current_effective_intent_view
            prior = base_view.active_contributions[0]
            source = root / prior.source_ref
            source.write_text(
                "The authority model now owns a revised durable pointer transaction.\n",
                encoding="utf-8",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_two,
            ), self.assertRaisesRegex(
                ModelAuthorityError,
                "intent source fingerprint is stale",
            ):
                activate_model_revision_set(
                    root,
                    candidate_two,
                    retained_revision,
                )

            replacement = replace(
                prior,
                contribution_id="intent:current-design:authority:v2",
                source_fingerprint=source_file_fingerprint(source),
                supersedes_contribution_ids=(prior.contribution_id,),
                effective_revision="current-design:authority:v2",
                rationale=(
                    "The exact changed design source explicitly supersedes its prior "
                    "contribution before the candidate inventory is reverified."
                ),
            )
            transition = EffectiveIntentTransition(
                prior_contribution_id=prior.contribution_id,
                prior_contribution_fingerprint=prior.fingerprint,
                action="supersede",
                replacement_contribution_ids=(replacement.contribution_id,),
                reason=(
                    "Replace the stale prior source identity with its exact current "
                    "successor before validating the folded active inventory."
                ),
            )
            candidate_view = build_current_effective_intent_view(
                base_view,
                candidate_two,
                (replacement,),
                verify_model_intent_sources(root, (replacement,)),
                (transition,),
            )
            disposition = ModelIntentDisposition(
                contribution_id=replacement.contribution_id,
                contribution_fingerprint=replacement.fingerprint,
                disposition="accepted",
                changed_obligation_ids=(),
                changed_state_ids=(),
                changed_transition_ids=(),
                changed_invariant_ids=(),
                changed_relation_ids=retained_revision.changed_relation_ids,
                scoped_gap_ids=(),
                conflict_ids=(),
                unresolved_effect_ids=(),
                unreachable_terminal_state_ids=(),
                unconsumed_output_ids=(),
                reason=(
                    "Accept the exact replacement because it owns the complete changed "
                    "relation set and leaves no unresolved intent effect."
                ),
            )
            replacement_revision = replace(
                retained_revision,
                revision_set_id="revision:store:source-replacement",
                intent_contributions=(replacement,),
                intent_dispositions=(disposition,),
                current_effective_intent_view=candidate_view,
                intent_contribution_inventory_fingerprint="",
                intent_conflict_ids=(),
                intent_unresolved_ids=(),
                no_declared_intent_rationale_id="",
                no_declared_intent_evidence_fingerprints=(),
                no_declared_intent_rationale="",
            )
            replacement_revision = _rebind_fixture_quality(root, replacement_revision)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_two,
            ):
                replacement_head, _receipt = activate_model_revision_set(
                    root,
                    candidate_two,
                    replacement_revision,
                )

            self.assertEqual(3, replacement_head.generation)
            self.assertEqual(
                candidate_two.fingerprint,
                replacement_head.snapshot_fingerprint,
            )

    def test_audit_distinguishes_missing_and_invalid_current_intent_sources(self):
        for mutation, expected_code in (
            ("missing", "current_intent_source_missing"),
            ("directory", "current_intent_source_invalid"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = root / ".flowguard" / "project.toml"
                manifest.parent.mkdir()
                manifest.write_text("[flowguard]\n", encoding="utf-8")
                base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
                head = bootstrap_model_authority(
                    root,
                    base,
                    bootstrap_evidence_fingerprint=SHA_D,
                )
                candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
                accepted = revision(root, head, base, candidate)
                with patch(
                    "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                    return_value=candidate,
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )
                source = root / "docs" / "authority-current-design.md"
                source.unlink()
                if mutation == "directory":
                    source.mkdir()

                with patch(
                    "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                    return_value=candidate,
                ), patch(
                    "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                    return_value=manifest_inventory(),
                ):
                    report = audit_model_authority(root)

                codes = {finding.code for finding in report.findings}
                self.assertIn(expected_code, codes)
                self.assertNotIn("accepted_revision_invalid", codes)

    def test_activation_final_reread_preserves_peer_manifest_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            calls = 0

            def observe_then_peer_write(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8")
                        + '\n[peer_agent]\nmarker = "preserved"\n',
                        encoding="utf-8",
                    )
                return candidate

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=observe_then_peer_write,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            self.assertIn(
                '[peer_agent]\nmarker = "preserved"',
                manifest.read_text(encoding="utf-8"),
            )

    def test_activation_final_cas_rejects_peer_authority_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            calls = 0

            def observe_then_change_authority(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    text = manifest.read_text(encoding="utf-8")
                    manifest.write_text(
                        text.replace(
                            "generation = 1",
                            "generation = 9",
                        ),
                        encoding="utf-8",
                    )
                return candidate

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=observe_then_change_authority,
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "authority section changed",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                    )

    def test_audit_keeps_leaf_reuse_and_live_staleness_as_parallel_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                )

            revision_path = (
                root
                / ".flowguard"
                / "models"
                / "authority"
                / "revisions"
                / f"{accepted.fingerprint.split(':', 1)[1]}.json"
            )
            payload = json.loads(revision_path.read_text(encoding="utf-8"))
            for key in ("required_evidence_refs", "completed_evidence_refs"):
                refs = payload[key]
                self.assertGreaterEqual(len(refs), 2)
                refs[1]["receipt_id"] = refs[0]["receipt_id"]
                refs[1]["receipt_fingerprint"] = refs[0][
                    "receipt_fingerprint"
                ]
            revision_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered_bytes = revision_path.read_bytes()
            stale_live = replace(
                candidate,
                claim_boundary=(
                    "This live re-observation intentionally differs from the "
                    "stored snapshot so both independent blockers stay visible."
                ),
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=stale_live,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            codes = {finding.code for finding in report.findings}
            self.assertIn("accepted_revision_invalid", codes)
            self.assertIn("observed_source_inventory_stale", codes)
            accepted_finding = next(
                finding
                for finding in report.findings
                if finding.code == "accepted_revision_invalid"
            )
            self.assertIn(
                "leaf receipt cannot be reused across native owners",
                accepted_finding.message,
            )
            self.assertEqual(tampered_bytes, revision_path.read_bytes())

    def test_audit_blocks_when_live_manifest_differs_from_stored_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            live = snapshot("git:" + "b" * 40, SHA_B, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=live,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertIn(
                "observed_model_inventory_stale",
                {finding.code for finding in report.findings},
            )

    def test_audit_reports_exact_declared_materialized_and_missing_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            incomplete = ManifestModelInventory(
                declared_ids=("authority", "missing"),
                materialized_ids=("authority",),
                required_ids=("authority", "missing"),
                covered_ids=("authority",),
                missing_ids=("missing",),
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=incomplete,
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual(("authority", "missing"), report.declared_model_ids)
            self.assertEqual(("authority",), report.materialized_model_ids)
            self.assertEqual(("missing",), report.missing_model_ids)
            self.assertIn(
                "live_model_manifest_incomplete",
                {finding.code for finding in report.findings},
            )

    def test_existing_model_preflight_does_not_use_observed_root_as_owner_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                preflight = existing_model_preflight_from_project(
                    root,
                    "Review authority ownership",
                    downstream_routes=("development_process_flow",),
                )
            report = review_existing_model_preflight(preflight)

            self.assertFalse(report.ok, report.format_text())
            self.assertEqual("blocked", preflight.authority_status)
            self.assertEqual("", preflight.authority_snapshot_fingerprint)
            self.assertEqual((), preflight.relevant_models)
            self.assertIn(
                "modeled_current_owner_unresolved",
                {finding.code for finding in report.findings},
            )


if __name__ == "__main__":
    unittest.main()

# R6 selected architecture tests consume finite immutable fixtures and mock
# storage/observer boundaries. They do not accept or execute the live project.
def _persist_fixture_architecture_details(root, details):
    """Persist the original finite detail bytes consumed by public raw refs."""
    from flowguard.model_authority_store import _artifact_path
    for detail in details:
        path = _artifact_path(Path(root), "path-quality-details", detail.fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(detail.to_dict(), ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw
        else:
            path.write_bytes(raw)

def _r6_architecture_read_fixture(tmp_path):
    from types import SimpleNamespace
    from flowguard.model_path_quality import lightweight_path_review, normalized_model_facts_fingerprint, derive_retained_elements
    from flowguard.model_intent import ArchitectureObjective, ArchitectureObjectiveSource
    from tests.test_model_revision_set import _accepted_revision
    from tests.test_model_path_quality import clean_facts, _r6_fact, fp
    revision_set = _accepted_revision(tmp_path)
    base_source = revision_set.current_effective_intent_view.active_contributions[0]
    objective = ArchitectureObjective("objective:fixture:service-layer-writer", True, ("alpha",), ("responsibility:A",), ("class:accepted",), "allowed_layers", {"layer_ids": ["layer:service"]}, "model:alpha", ("failure:wrong-layer",))
    source_bytes = ("Normative fixture.\n```flowguard-architecture-objectives\n" + json.dumps(ArchitectureObjectiveSource((objective,)).to_dict()) + "\n```\n").encode("utf-8")
    path = tmp_path / base_source.source_ref
    path.write_bytes(source_bytes)
    contribution = replace(base_source, source_fingerprint=source_file_fingerprint(path), target_invariant_ids=(objective.objective_id,))
    identity = replace(revision_set.current_effective_intent_view.verified_source_identities[0], source_fingerprint=contribution.source_fingerprint)
    view = replace(revision_set.current_effective_intent_view, bootstrap_receipt=None, base_effective_intent_view_fingerprint=fp("earlier-current"), active_contributions=(contribution,), verified_source_identities=(identity,))
    facts = clean_facts()
    facts["responsibilities"] = [_r6_fact(model="alpha", layer="layer:UI").to_dict()]
    required_gap = "required_architecture_objective_unmet:" + objective.objective_id
    facts["architecture"] = {"declared_source_fingerprint": fp("declared-source"), "effective_intent_view_fingerprint": view.fingerprint,
        "facts_scope": "model_behavior", "scope_coverage": {"claim_scope": "declared_model"}, "finding_ids": [], "observation_gap_ids": [], "improvement_gap_ids": [required_gap],
        "suggestions": [{"objective_id": objective.objective_id, "lane": "normative_target", "action": "relocate_responsibility", "owner_id": "model:alpha", "source_ref": contribution.source_ref, "source_fingerprint": contribution.source_fingerprint}]}
    subject = replace(revision_set.path_quality_subjects[0], intent_fingerprint=view.fingerprint, provider_fingerprint=fp("declared-source"), normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts), retained_element_inventory_fingerprint=canonical_fingerprint(dict(derive_retained_elements(facts))))
    details = []
    result = lightweight_path_review(subject, facts, detail_collector=details)
    _persist_fixture_architecture_details(tmp_path, details)
    revision_set = replace(revision_set, current_effective_intent_view=view, path_quality_subjects=(subject,), path_quality_results=(result,), path_quality_result_set_fingerprint="")
    head = SimpleNamespace(fingerprint=fp("head"), accepted_revision_set_fingerprint=revision_set.fingerprint, snapshot_fingerprint=revision_set.candidate_snapshot_fingerprint, fixture_root=tmp_path)
    model = {"fingerprint": subject.model_fingerprint, "model_path": "model.py", "runner_path": "runner.py", "inputs": []}
    shard = {"logical_model_id": "alpha", "model": model, "source_paths": {}, "intent_refs": [], "relations": [], "boundary_nodes": []}
    projection = {"index_fingerprint": fp("index"), "index": {"models": {"alpha": {"shard_fingerprint": fp("shard"), "model_fingerprint": subject.model_fingerprint}}, "revision_set_fingerprint": revision_set.fingerprint, "candidate_snapshot_fingerprint": head.snapshot_fingerprint, "subject_revision": "fixture", "unresolved_gap_count": 0}}
    def payload(root, category, fingerprint, **kwargs):
        if category == "revisions":
            assert fingerprint == revision_set.fingerprint
            return revision_set.to_dict()
        if category == "path-quality-details":
            assert fingerprint == details[0].fingerprint
            return details[0].to_dict()
        raise AssertionError("unrelated immutable artifact loaded: " + category)
    return head, projection, shard, payload, revision_set, details


def _r7_two_model_architecture_read_fixture(tmp_path):
    from flowguard.model_path_quality import lightweight_path_review, normalized_model_facts_fingerprint
    head, projection, alpha, _, revision, details = _r6_architecture_read_fixture(tmp_path)
    beta = json.loads(json.dumps(alpha))
    beta["logical_model_id"] = "beta"
    prior = revision.current_effective_intent_view
    (tmp_path / "beta-design.md").write_bytes(b"Finite beta design without architecture objectives.\n")
    contribution = replace(prior.active_contributions[0], contribution_id="intent:beta:finite-design", logical_model_id="model:beta", source_ref="beta-design.md", source_fingerprint=source_file_fingerprint(tmp_path / "beta-design.md"), target_invariant_ids=(), target_relation_ids=("relation:model-realizes-purpose:beta",))
    identity = replace(prior.verified_source_identities[0], contribution_id=contribution.contribution_id, source_ref=contribution.source_ref, resolved_project_ref=contribution.source_ref, source_fingerprint=contribution.source_fingerprint)
    owner = replace(prior.owner_bindings[0], model_owner_id="model-obligation:beta", logical_model_id="beta", realization_relation_id="relation:model-realizes-purpose:beta", contribution_ids=(contribution.contribution_id,))
    view = replace(prior, active_contributions=(*prior.active_contributions, contribution), verified_source_identities=(*prior.verified_source_identities, identity), model_owner_ids=(*prior.model_owner_ids, "model-obligation:beta"), owner_bindings=(*prior.owner_bindings, owner))
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    facts["architecture"]["effective_intent_view_fingerprint"] = view.fingerprint
    subject = replace(revision.path_quality_subjects[0], intent_fingerprint=view.fingerprint, normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts))
    beta_subject = replace(subject, model_id="beta")
    details = []
    results = tuple(lightweight_path_review(row, facts, detail_collector=details) for row in (subject, beta_subject))
    _persist_fixture_architecture_details(tmp_path, details)
    revision = replace(revision, required_path_quality_model_ids=("alpha", "beta"), current_effective_intent_view=view, path_quality_subjects=(subject, beta_subject), path_quality_results=results, path_quality_result_set_fingerprint="")
    head.accepted_revision_set_fingerprint = revision.fingerprint
    projection["index"]["revision_set_fingerprint"] = revision.fingerprint
    projection["index"]["models"]["beta"] = dict(projection["index"]["models"]["alpha"])
    detail_payloads = {row.fingerprint: row.to_dict() for row in details}
    def payload(root, category, fingerprint, **kwargs):
        if category == "revisions":
            assert fingerprint == revision.fingerprint
            return revision.to_dict()
        assert category == "path-quality-details"
        return detail_payloads[fingerprint]
    return head, projection, (alpha, beta), payload, revision, details


def _r7_bound_read_detail(head, projection, revision, facts, *, scope_evidence=None):
    from flowguard.model_path_quality import lightweight_path_review, normalized_model_facts_fingerprint, derive_retained_elements
    subject = replace(revision.path_quality_subjects[0], intent_fingerprint=revision.current_effective_intent_view.fingerprint,
        normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts), retained_element_inventory_fingerprint=canonical_fingerprint(dict(derive_retained_elements(facts))))
    if scope_evidence is not None:
        facts["architecture"]["scope_evidence"] = {**scope_evidence, "subject_fingerprint": subject.fingerprint}
    details = []
    result = lightweight_path_review(subject, facts, detail_collector=details)
    # The bound helper derives its fixture root from the canonical source path
    # retained by the caller's private fixture head.
    _persist_fixture_architecture_details(head.fixture_root, details)
    revision = replace(revision, path_quality_subjects=(subject,), path_quality_results=(result,), path_quality_result_set_fingerprint="")
    head.accepted_revision_set_fingerprint = revision.fingerprint
    projection["index"]["revision_set_fingerprint"] = revision.fingerprint
    def payload(root, category, fingerprint, **kwargs):
        if category == "revisions":
            assert fingerprint == revision.fingerprint
            return revision.to_dict()
        assert category == "path-quality-details" and fingerprint == details[0].fingerprint
        return details[0].to_dict()
    return revision, details, payload


def test_required_objective_scope_is_not_intersected_down(tmp_path):
    from flowguard.model_authority_store import derive_architecture_read_projection
    from flowguard.model_intent import ArchitectureObjective, ArchitectureObjectiveSource
    head, projection, shard, _, revision, details = _r6_architecture_read_fixture(tmp_path)
    prior = revision.current_effective_intent_view
    contribution = prior.active_contributions[0]
    objective = ArchitectureObjective("objective:fixture:service-layer-writer", True, ("alpha", "beta"), ("responsibility:A", "responsibility:B"), ("class:accepted",), "allowed_layers", {"layer_ids": ["layer:service"]}, "model:alpha", ("failure:wrong-layer",))
    source = tmp_path / contribution.source_ref
    source.write_text("```flowguard-architecture-objectives\n" + json.dumps(ArchitectureObjectiveSource((objective,)).to_dict()) + "\n```\n", encoding="utf-8", newline="\n")
    contribution = replace(contribution, source_fingerprint=source_file_fingerprint(source))
    identity = replace(prior.verified_source_identities[0], source_fingerprint=contribution.source_fingerprint)
    view = replace(prior, active_contributions=(contribution,), verified_source_identities=(identity,))
    revision = replace(revision, current_effective_intent_view=view)
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    facts["architecture"]["effective_intent_view_fingerprint"] = view.fingerprint
    revision, details, payload = _r7_bound_read_detail(head, projection, revision, facts)
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload), patch("flowguard.model_authority_store._load_selected_read_shards", return_value=(shard,)):
        read = derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    goal = read.objective_refs[0]["objective"]
    assert goal["model_ids"] == ["alpha", "beta"] and goal["responsibility_ids"] == ["responsibility:A", "responsibility:B"]
    assert "architecture_objective_scope_unknown:beta" in read.observation_gap_ids
    assert read.architecture_confidence == "not_proven"


def _r7_scope_read_fixture(tmp_path, *, file_names=("w1", "w2"), exclusions=(), base_fixture=None):
    from flowguard.implementation_inventory import SoftwareBoundary, ImplementationSurface, ImplementationFileDisposition, ImplementationSurfaceInventory
    from flowguard.implementation_blueprint import review_model_implementation_bindings
    from tests.test_implementation_blueprint import binding, spec, oracle
    from flowguard.validation_ownership import ValidationOwnerContract, _build_owner_current, _prepare_owner_receipt
    from flowguard.validation_results import ValidationChildResult
    from flowguard.evidence_receipts import evidence_storage_root, save_evidence_receipt
    from flowguard.model_revision_set import RevisionEvidenceRef
    from flowguard.model_revision_builder import _owner_toolchain_fingerprint
    from flowguard.source_identity import functional_source_fingerprint
    head, projection, shard, _, revision, details = base_fixture if base_fixture is not None else _r6_architecture_read_fixture(tmp_path)
    rows, surfaces, dispositions, bindings, semantics, oracles = [], [], [], [], [], []
    for name in file_names:
        path = tmp_path / f"{name}.py"
        path.write_text(f"def {name}():\n    return 1\n", encoding="utf-8")
        sha = functional_source_fingerprint(tmp_path, path.name)
        rows.append({"path": path.name, "sha256": sha})
        surfaces.append(ImplementationSurface(f"surface:{name}", path.name, name, "function", "", sha, canonical_fingerprint(name), "model_implementation", roles=("behavior",)))
        dispositions.append(ImplementationFileDisposition(path.name, "production", sha, "model_implementation", "finite original producer boundary", requires_adapter=False))
        bindings.append(binding(f"binding:{name}", f"model:{name}", f"surface:{name}", f"spec:{name}", f"oracle:{name}", implementation_fingerprint=sha))
        semantics.append(spec(f"spec:{name}", f"model:{name}"))
        oracles.append(oracle(f"oracle:{name}", f"model:{name}"))
    boundary = SoftwareBoundary("boundary:fixture", "fixture", production_patterns=("w*.py",), exclusions=exclusions)
    inventory = ImplementationSurfaceInventory("inventory:fixture", boundary, canonical_fingerprint(rows), tuple(dispositions), tuple(surfaces), (), "Frozen fixture software boundary")
    report = review_model_implementation_bindings(inventory, required_model_element_ids=tuple("model:" + name for name in file_names), bindings=bindings, semantic_specs=semantics, oracles=oracles)
    assert report.ok
    definition = tmp_path / "scope-definition.json"
    definition.write_text(json.dumps({"files": [name + ".py" for name in file_names]}), encoding="utf-8")
    refs = [{"path": definition.name, "source_fingerprint": functional_source_fingerprint(tmp_path, definition.name)}]
    input_manifest = sorted([*rows, {"path": refs[0]["path"], "sha256": refs[0]["source_fingerprint"]}], key=lambda row: row["path"])
    owner_id = dict(revision.affected_owner_bindings)["model_instance:model:alpha"]
    contract = ValidationOwnerContract(owner_id, ("python", "finite-fixture.py"), tuple(row["path"] for row in input_manifest), ("scope:inventory", "scope:bindings"))
    current = _build_owner_current(tmp_path, contract, all_contracts=(contract,), resolved_input_manifest=input_manifest)
    child = ValidationChildResult(contract.owner_id, "pass", payload={"implementation_inventory": inventory.to_dict(), "binding_report": report.to_dict(), "resolved_manifest_rows": rows,
        "source_refs": refs, "input_manifest": input_manifest, "input_fingerprint": canonical_fingerprint(input_manifest)})
    prepared = _prepare_owner_receipt(current, child, evidence_storage_root(tmp_path), started_at="2026-10-02T01:00:00+00:00", finished_at="2026-10-02T01:00:01+00:00", publication_kind="supervised_producer")
    prepared.proof_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.proof_path.write_bytes(prepared.proof_bytes)
    save_evidence_receipt(prepared.receipt, tmp_path)
    covered = tuple(sorted(key for key, owner in revision.affected_owner_bindings if owner == owner_id))
    ref = RevisionEvidenceRef(prepared.receipt.receipt_id, prepared.receipt.fingerprint, contract.owner_id, head.snapshot_fingerprint, contract.obligation_ids,
        revision.affected_closure_fingerprint, covered, head.snapshot_fingerprint, _owner_toolchain_fingerprint(prepared.receipt), current.environment_fingerprint, "pass", True, True)
    revision = replace(revision, required_evidence_refs=(*tuple(row for row in revision.required_evidence_refs if row.owner_route != owner_id), replace(ref, status="required")), completed_evidence_refs=(*tuple(row for row in revision.completed_evidence_refs if row.owner_route != owner_id), ref))
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    facts["architecture"]["facts_scope"] = "software_architecture"
    scope = {"claim_scope": "software_architecture", "implementation_inventory_id": inventory.inventory_id, "implementation_inventory_fingerprint": inventory.fingerprint,
        "binding_report_fingerprint": report.fingerprint, "claimed_surface_ids": list(inventory.required_surface_ids), "covered_surface_ids": list(inventory.required_surface_ids), "coverage_gap_ids": []}
    facts["architecture"]["scope_coverage"] = scope
    proof = {"schema": "flowguard.architecture_scope_evidence.v1", "claim_boundary": "complete_within_authenticated_frozen_boundary", "boundary": boundary.to_dict(), "inventory": inventory.to_dict(), "resolved_manifest_rows": rows,
        "binding_report": report.to_dict(), "source_refs": refs, "subject_fingerprint": revision.path_quality_subjects[0].fingerprint, "producer_owner_id": contract.owner_id,
        "producer_receipt_id": prepared.receipt.receipt_id, "producer_receipt_fingerprint": prepared.receipt.fingerprint, "producer_input_fingerprint": canonical_fingerprint(input_manifest)}
    revision, details, payload = _r7_bound_read_detail(head, projection, revision, facts, scope_evidence=proof)
    return head, projection, shard, payload, revision, details


def test_r8_unknown_changed_paths_remain_visible_beside_selected_model(tmp_path):
    """Real finite authenticated scope; no global discovery or owner execution."""
    import flowguard.model_authority_store as store
    head, projection, shard, payload, revision, details = _r7_scope_read_fixture(tmp_path)
    (tmp_path / "w3.py").write_text("def w3():\n    return 3\n", encoding="utf-8")
    with patch.object(store, "_read_content_addressed_payload", side_effect=payload), patch.object(store, "_load_selected_read_shards", return_value=(shard,)), patch.object(Path, "glob", side_effect=AssertionError("global discovery")), patch.object(Path, "rglob", side_effect=AssertionError("global discovery")), patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("owner")):
        read = store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",), changed_paths=("w1.py", "w3.py"))
    assert read.selected_model_ids == ("alpha",)
    assert read.checked_observed_paths == ("w1.py", "w3.py")
    assert [row["gap_id"] for row in read.growth_gaps] == ["model_growth_unbound:w3.py"]
    gap = read.growth_gaps[0]
    assert gap["affected_boundary_id"] == "boundary:fixture"
    assert gap["next_owner_id"] == "model:implementation_blueprint"
    assert gap["required_input_refs"] and gap["observation_fingerprint"] == read.observation_fingerprint
    assert read.producer_count == read.write_count == 0


def test_r8_growth_gap_closes_only_after_current_inventory_binding_acceptance(tmp_path):
    """Fixtures rebuild actual inventory/binding/producer proof, never force current."""
    import flowguard.model_authority_store as store
    head, projection, shard, payload, revision, details = _r7_scope_read_fixture(tmp_path)
    (tmp_path / "w3.py").write_text("def w3():\n    return 3\n", encoding="utf-8")
    def consume():
        with patch.object(store, "_read_content_addressed_payload", side_effect=payload), patch.object(store, "_load_selected_read_shards", return_value=(shard,)), patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("owner")):
            return store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",), changed_paths=("w3.py",))
    first = consume()
    assert first.growth_gaps and consume().growth_gaps == first.growth_gaps
    with patch.object(store, "_read_content_addressed_payload", side_effect=payload), patch.object(store, "_load_selected_read_shards", return_value=(shard,)):
        no_observation = store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    assert no_observation.live_unregistered_file_detection == "NOT_OBSERVED" and not no_observation.checked_observed_paths
    head, projection, shard, payload, _, _ = _r7_scope_read_fixture(tmp_path, file_names=("w1", "w2", "w3"), base_fixture=(head, projection, shard, payload, revision, details))
    accepted = consume()
    assert not accepted.growth_gaps and accepted.checked_observed_paths == ("w3.py",)
    (tmp_path / "w3.py").write_text("def w3():\n    return 4\n", encoding="utf-8")
    assert consume().growth_gaps  # Inventory presence alone cannot hide source drift.


def test_selected_read_consumes_authenticated_whole_scope_proof_without_producers(tmp_path):
    import flowguard.model_authority_store as store
    head, projection, shard, payload, revision, details = _r7_scope_read_fixture(tmp_path)
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    def consume():
        with patch.object(store, "_read_content_addressed_payload", side_effect=payload), patch.object(store, "_load_selected_read_shards", return_value=(shard,)), patch("flowguard.implementation_inventory._boundary_manifest", side_effect=AssertionError("scanner called")), patch("flowguard.implementation_inventory.build_implementation_surface_inventory", side_effect=AssertionError("inventory producer called")), patch("flowguard.validation_ownership.resolve_input_manifest", side_effect=AssertionError("selector called")), patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("owner called")), patch.object(Path, "write_bytes", side_effect=AssertionError("read wrote")), patch.object(Path, "write_text", side_effect=AssertionError("read wrote")), patch.object(Path, "glob", side_effect=AssertionError("read globbed")), patch.object(Path, "rglob", side_effect=AssertionError("read scanned")):
            return store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    good = consume()
    assert good.architecture["architecture_confidence"] == "complete", good.architecture["observation_gap_ids"]
    assert good.architecture["scope_proof_refs"][0]["live_unregistered_file_detection"] == "NOT_OBSERVED"
    assert good.producer_count == good.write_count == 0
    # Bare W3 is outside the frozen producer observation. Registration changes
    # are the explicit freshness input; the reader does not discover W3.
    (tmp_path / "w3.py").write_text("def w3(): return 3\n", encoding="utf-8")
    assert consume().architecture["architecture_confidence"] == "complete"
    definition = tmp_path / "scope-definition.json"
    original = definition.read_bytes()
    definition.write_text('{"files":["w1.py","w2.py","w3.py"]}', encoding="utf-8")
    assert "implementation_scope_source_stale" in consume().architecture["observation_gap_ids"]
    definition.write_bytes(original)
    (tmp_path / "w2.py").write_text("def w2(): return 2\n", encoding="utf-8")
    assert consume().architecture["architecture_confidence"] == "not_proven"
    (tmp_path / "w2.py").write_text("def w2():\n    return 1\n", encoding="utf-8")
    for alteration in ("receipt", "omission", "consistent_omission", "missing"):
        altered = json.loads(json.dumps(facts))
        proof = altered["architecture"]["scope_evidence"]
        if alteration == "receipt": proof["producer_receipt_fingerprint"] = canonical_fingerprint("foreign")
        elif alteration == "omission": altered["architecture"]["scope_coverage"]["covered_surface_ids"] = ["surface:w1"]
        elif alteration == "consistent_omission":
            from flowguard.implementation_inventory import ImplementationSurfaceInventory
            from flowguard.model_path_quality import parse_architecture_binding_report
            from flowguard.implementation_blueprint import review_model_implementation_bindings
            full_inventory = ImplementationSurfaceInventory.from_dict(proof["inventory"])
            full_report = parse_architecture_binding_report(proof["binding_report"])
            rows = [row for row in proof["resolved_manifest_rows"] if row["path"] == "w1.py"]
            reduced = replace(full_inventory, manifest_fingerprint=canonical_fingerprint(rows), file_dispositions=tuple(row for row in full_inventory.file_dispositions if row.path == "w1.py"), surfaces=tuple(row for row in full_inventory.surfaces if row.path == "w1.py"))
            reduced_report = review_model_implementation_bindings(reduced, required_model_element_ids=("model:w1",), bindings=tuple(row for row in full_report.bindings if row.implementation_surface_id == "surface:w1"), semantic_specs=tuple(row for row in full_report.semantic_specs if "model:w1" in row.covered_model_element_ids), oracles=tuple(row for row in full_report.oracles if "model:w1" in row.covered_model_element_ids))
            assert reduced_report.ok
            proof.update(inventory=reduced.to_dict(), binding_report=reduced_report.to_dict(), resolved_manifest_rows=rows)
            altered["architecture"]["scope_coverage"].update(implementation_inventory_fingerprint=reduced.fingerprint, binding_report_fingerprint=reduced_report.fingerprint, claimed_surface_ids=["surface:w1"], covered_surface_ids=["surface:w1"])
        else: altered["architecture"]["scope_evidence"] = None
        revision, _, payload = _r7_bound_read_detail(head, projection, revision, altered, scope_evidence=proof if alteration != "missing" else None)
        bad = consume()
        assert bad.architecture["architecture_confidence"] == "not_proven" and bad.architecture["observation_gap_ids"]
        if alteration == "consistent_omission":
            assert "implementation_scope_producer_material_mismatch" in bad.architecture["observation_gap_ids"]
    # Restore the original immutable detail projection before checking missing
    # registered inputs and corruption of the retained producer artifact.
    revision, _, payload = _r7_bound_read_detail(head, projection, revision, json.loads(json.dumps(facts)), scope_evidence=facts["architecture"]["scope_evidence"])
    definition.unlink()
    assert consume().architecture["architecture_confidence"] == "not_proven"
    definition.write_bytes(original)
    from flowguard.evidence_receipts import receipt_path, EvidenceReceipt, evidence_storage_root
    original_proof = facts["architecture"]["scope_evidence"]
    receipt = EvidenceReceipt.from_dict(json.loads(receipt_path(original_proof["producer_receipt_id"], tmp_path).read_text(encoding="utf-8")))
    raw_proof = evidence_storage_root(tmp_path) / receipt.metadata["proof_relpath"]
    raw_proof.write_bytes(raw_proof.read_bytes() + b" ")
    assert "implementation_scope_producer_artifact_mismatch" in consume().architecture["observation_gap_ids"]


def test_selected_read_preserves_required_goal_and_current_gap(tmp_path):
    from flowguard.model_authority_store import derive_architecture_read_projection
    head, projection, shard, payload, revision_set, details = _r6_architecture_read_fixture(tmp_path)
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload), patch("flowguard.model_authority_store._load_selected_read_shards", return_value=(shard,)):
        read = derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    assert read.head_fingerprint == head.fingerprint
    assert read.objective_refs[0]["objective"]["objective_id"] == "objective:fixture:service-layer-writer"
    assert read.improvement_gap_ids == revision_set.path_quality_results[0].improvement_gap_ids
    assert read.suggestion_refs[0]["lane"] == "normative_target"
    assert read.architecture_confidence == "scoped"
    assert not read.observation_gap_ids


def test_goal_read_is_affected_only_zero_producers_zero_writes(tmp_path):
    from flowguard.model_authority_store import derive_architecture_read_projection, ModelRevisionSet
    head, projection, shard, payload, revision_set, details = _r6_architecture_read_fixture(tmp_path)
    files_before = tuple(sorted(str(x) for x in tmp_path.rglob("*")))
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload) as reads, patch("flowguard.model_authority_store._load_selected_read_shards", return_value=(shard,)), patch.object(ModelRevisionSet, "from_dict", side_effect=AssertionError("whole revision typed")), patch("flowguard.model_authority_store._write_immutable_json", side_effect=AssertionError("read wrote evidence")), patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read launched owner")):
        derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    assert [call.args[1] for call in reads.call_args_list] == ["revisions", "path-quality-details"]
    assert tuple(sorted(str(x) for x in tmp_path.rglob("*"))) == files_before


def test_scoped_graph_read_does_not_claim_whole_software_understanding(tmp_path):
    from flowguard.model_authority_store import read_selected_model_projection
    head, projection, shard, payload, revision_set, details = _r6_architecture_read_fixture(tmp_path)
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload), patch("flowguard.model_authority_store._load_selected_read_shards", return_value=(shard,)):
        read = read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    assert read.selected_source_currentness == "current"
    assert read.producer_count == 0 and read.write_count == 0
    assert read.architecture["facts_scope"][0]["claim_scope"] == "declared_model"
    assert read.architecture["architecture_confidence"] == "scoped"
    assert read.architecture["suggestion_refs"][0]["action"] == "relocate_responsibility"


def test_path_quality_details_persist_before_single_head_cas(tmp_path):
    from types import SimpleNamespace
    from tests.test_model_intent_authority import _snapshot, SHA_B
    head, projection, shard, payload, revision_set, details = _r6_architecture_read_fixture(tmp_path)
    candidate = _snapshot(("alpha",), snapshot_id="observed-b", model_sha=SHA_B)
    receipt = SimpleNamespace(fingerprint=canonical_fingerprint("receipt"), to_dict=lambda: {"receipt_id": "fixture"})
    steps = []
    def write(root, category, fingerprint, value): steps.append(category)
    overrides = {"read_manifest_text": lambda _: "", "_load_observed_from_manifest_text": lambda *a: (head, candidate), "load_current_model_authority_state": lambda *a, **k: None,
        "_validate_revision_intent_activation": lambda *a, **k: None, "_load_accepted_boundary_contract": lambda *a: None,
        "_build_accepted_read_projection": lambda *a: (projection["index_fingerprint"], {}, {}),
        "validate_activation_plan": lambda *a, **k: (head, receipt), "write_content_addressed_snapshot": lambda *a: None,
        "_write_immutable_json": write, "_persist_accepted_read_projection": lambda *a: None,
        "render_model_authority_section": lambda *a, **k: "", "_replace_authority_section_cas": lambda *a, **k: steps.append("cas"),
        "_snapshot_path": lambda *a: "snapshot.json"}
    from contextlib import nullcontext
    overrides["project_manifest_lock"] = lambda _: nullcontext()
    with patch.multiple("flowguard.model_authority_store", **overrides), patch("flowguard.model_system_inventory.build_manifest_model_system_snapshot", return_value=candidate):
        activate_model_revision_set(tmp_path, candidate, revision_set, path_quality_details=details)
    assert steps.count("cas") == 1
    assert steps.index("path-quality-details") < steps.index("cas")


def test_selected_read_admits_only_detail_bound_structural_rewrite(tmp_path):
    from flowguard.model_authority_store import derive_architecture_read_projection
    from flowguard.model_path_quality import lightweight_path_review, normalized_model_facts_fingerprint
    head, projection, shard, _, revision, details = _r6_architecture_read_fixture(tmp_path)
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    relation_id = "architecture-relation:duplicate_boundary:finite-fixture"
    pair = ["responsibility:A", "responsibility:B"]
    architecture = facts["architecture"]
    architecture["relations"] = [{"relation_id": relation_id, "kind": "duplicate_boundary", "responsibility_ids": pair}]
    architecture["finding_ids"] = ["equivalent_responsibility_paths:" + ":".join(pair)]
    architecture["suggestions"] = [{"rewrite_rule_id": "share-primary:" + relation_id, "responsibility_ids": pair, "lane": "normative_target"}]
    subject = replace(revision.path_quality_subjects[0], normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts))
    derived = []
    result = lightweight_path_review(subject, facts, detail_collector=derived)
    _persist_fixture_architecture_details(tmp_path, derived)
    revision = replace(revision, path_quality_subjects=(subject,), path_quality_results=(result,), path_quality_result_set_fingerprint="")
    head.accepted_revision_set_fingerprint = revision.fingerprint
    projection["index"]["revision_set_fingerprint"] = revision.fingerprint
    def payload(root, category, fingerprint, **kwargs):
        return revision.to_dict() if category == "revisions" else derived[0].to_dict()
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload), patch("flowguard.model_authority_store._load_selected_read_shards", return_value=(shard,)):
        read = derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha",))
    assert not read.observation_gap_ids
    assert read.suggestion_refs[0]["rewrite_rule_id"] == "share-primary:" + relation_id
    assert "equivalent_responsibility_paths:" + ":".join(pair) in read.improvement_gap_ids


def test_architecture_selected_read_hashes_shared_source_once_per_invocation(tmp_path):
    import flowguard.model_authority_store as store
    from flowguard.model_path_quality import lightweight_path_review
    head, projection, alpha_shard, _, revision, details = _r6_architecture_read_fixture(tmp_path)
    shared = tmp_path / "shared.py"
    shared.write_text("shared_source = 1\n", encoding="utf-8")
    expected = source_file_fingerprint(shared)
    alpha_shard["source_paths"] = {"shared.py": expected}
    beta_shard = json.loads(json.dumps(alpha_shard))
    beta_shard["logical_model_id"] = "beta"
    prior_view = revision.current_effective_intent_view
    beta_source = tmp_path / "beta-design.md"
    beta_source.write_text("Finite beta design with no architecture objective.\n", encoding="utf-8")
    beta_contribution = replace(prior_view.active_contributions[0],
        contribution_id="intent:beta:finite-design", logical_model_id="model:beta",
        source_ref="beta-design.md", source_fingerprint=source_file_fingerprint(beta_source),
        target_invariant_ids=(), target_relation_ids=("relation:model-realizes-purpose:beta",))
    beta_identity = replace(prior_view.verified_source_identities[0],
        contribution_id=beta_contribution.contribution_id, source_ref=beta_contribution.source_ref,
        source_fingerprint=beta_contribution.source_fingerprint)
    beta_owner = replace(prior_view.owner_bindings[0], model_owner_id="model-obligation:beta",
        logical_model_id="beta", realization_relation_id="relation:model-realizes-purpose:beta",
        contribution_ids=(beta_contribution.contribution_id,))
    view = replace(prior_view, active_contributions=(*prior_view.active_contributions, beta_contribution),
        verified_source_identities=(*prior_view.verified_source_identities, beta_identity),
        model_owner_ids=(*prior_view.model_owner_ids, "model-obligation:beta"),
        owner_bindings=(*prior_view.owner_bindings, beta_owner))
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    facts["architecture"]["effective_intent_view_fingerprint"] = view.fingerprint
    from flowguard.model_path_quality import normalized_model_facts_fingerprint
    alpha_subject = replace(revision.path_quality_subjects[0], intent_fingerprint=view.fingerprint,
        normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts))
    details = []
    alpha_result = lightweight_path_review(alpha_subject, facts, detail_collector=details)
    beta_subject = replace(alpha_subject, model_id="beta")
    beta_details = []
    beta_result = lightweight_path_review(beta_subject, facts, detail_collector=beta_details)
    _persist_fixture_architecture_details(tmp_path, (*details, *beta_details))
    revision = replace(revision, required_path_quality_model_ids=("alpha", "beta"),
        current_effective_intent_view=view,
        path_quality_subjects=(alpha_subject, beta_subject),
        path_quality_results=(alpha_result, beta_result),
        path_quality_result_set_fingerprint="")
    head.accepted_revision_set_fingerprint = revision.fingerprint
    projection["index"]["revision_set_fingerprint"] = revision.fingerprint
    projection["index"]["models"]["beta"] = dict(projection["index"]["models"]["alpha"])
    detail_payloads = {row.fingerprint: row.to_dict() for row in (*details, *beta_details)}
    def payload(root, category, fingerprint, **kwargs):
        return revision.to_dict() if category == "revisions" else detail_payloads[fingerprint]
    original_hash = store._selected_source_fingerprint
    hashes = []
    def actual_hash(root, relative, data):
        if relative == "shared.py": hashes.append(relative)
        return original_hash(root, relative, data)
    with patch.object(store, "_read_content_addressed_payload", side_effect=payload), patch.object(store, "_load_selected_read_shards", return_value=(alpha_shard, beta_shard)), patch.object(store, "_selected_source_fingerprint", side_effect=actual_hash):
        first = store.derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert not first.observation_gap_ids
        assert len(hashes) == 1
        # Reuse the actual bytes, but check the other subject's different
        # expected identity independently of the cached actual hash.
        beta_shard["source_paths"]["shared.py"] = canonical_fingerprint("wrong expected source")
        mismatch = store.derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert "declared_source_identity_mismatch:beta" in mismatch.observation_gap_ids
        assert "declared_source_identity_mismatch:alpha" not in mismatch.observation_gap_ids
        assert len(hashes) == 2
        beta_shard["source_paths"]["shared.py"] = expected
        shared.write_text("shared_source = 2\n", encoding="utf-8")
        changed = store.derive_architecture_read_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert {"declared_source_identity_mismatch:alpha", "declared_source_identity_mismatch:beta"} <= set(changed.observation_gap_ids)
        assert len(hashes) == 3
