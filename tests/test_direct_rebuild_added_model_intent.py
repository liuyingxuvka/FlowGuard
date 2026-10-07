"""Current Source addition inputs, not executed native or accepted authority."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard.behavior_commitment import load_behavior_commitment_ledger
from flowguard.model_authority import ModelAuthorityError, build_model_instance_ref
from flowguard.model_intent import (
    ModelIntentContribution, ModelIntentDisposition, verify_model_intent_sources,
)
from flowguard.model_intent_authority import validate_candidate_intent_source_input_bindings
from flowguard.model_regressions import (
    ModelRegressionManifest, audit_intent_source_input_bindings,
    resolve_entry_input_inventory,
)
from scripts import build_direct_model_rebuild_inputs as direct


SOURCE = Path(__file__).resolve().parents[1]
ADDED_IDS = ("evidence_storage_lifecycle", "problem_corpus_coverage",
             "python_function_state_verification")


def _actual_addition_inputs():
    manifest = ModelRegressionManifest.load(SOURCE)
    entries = {x.model_id: x for x in manifest.entries}
    models = tuple(build_model_instance_ref(
        SOURCE, logical_model_id=owner, model_kind=entries[owner].model_kind,
        model_path=entries[owner].model_path, runner_path=entries[owner].runner[1],
        purpose_closure_fingerprint=entries[owner].purpose_closure.closure_fingerprint,
        input_paths=tuple(row["path"] for row in resolve_entry_input_inventory(
            SOURCE, entries[owner], additional_patterns=manifest.owner_patterns_for(owner))),
    ) for owner in ADDED_IDS)
    return (SimpleNamespace(model_instances=()),
            SimpleNamespace(model_instances=models),
            SimpleNamespace(members=tuple(SimpleNamespace(member_id=x, operation="add") for x in ADDED_IDS)))


@pytest.mark.parametrize("owner", ("evidence_storage_lifecycle", "problem_corpus_coverage",
                                   "python_function_state_verification"))
def test_added_owner_primary_normative_source_is_bound_in_real_preflight_inputs(owner):
    """Exercise both official preflight binding gates with actual Source inputs.

    This finite check covers the three additions, without executing a native
    owner or accepting a revision. Removing only one owner's document edge
    must fail even while the source author still supplies a valid contribution.
    """
    base, candidate, diff = _actual_addition_inputs()
    added = direct._added_model_intents(
        SOURCE, base, candidate, diff, ADDED_IDS,
        "revision:finite-primary-input", {x: () for x in ADDED_IDS})
    sources = verify_model_intent_sources(SOURCE, added)
    manifest = ModelRegressionManifest.load(SOURCE)
    # The production preflight audits the whole active view. This test's
    # authored contribution denominator is exactly the three added owners.
    selected_manifest = SimpleNamespace(entries=tuple(
        entry for entry in manifest.entries if entry.model_id in ADDED_IDS))
    document = "docs/functional_source_contracts.md"
    assert audit_intent_source_input_bindings(SOURCE, selected_manifest, added, sources) == ()
    validate_candidate_intent_source_input_bindings(candidate, added, sources)
    instance = next(item for item in candidate.model_instances if item.logical_model_id == owner)
    source = next(item for item in sources if item.contribution_id == next(
        contribution.contribution_id for contribution in added
        if contribution.logical_model_id == "model:" + owner))
    assert source.resolved_project_ref == document
    assert {item.path: item.sha256 for item in instance.inputs}[document] == source.source_fingerprint

    missing_declaration = SimpleNamespace(entries=tuple(
        replace(entry, intent_source_inputs=tuple(path for path in entry.intent_source_inputs
                                                 if path != document))
        if entry.model_id == owner else entry for entry in selected_manifest.entries))
    assert audit_intent_source_input_bindings(SOURCE, missing_declaration, added, sources) == (
        owner + ": missing intent-source input: " + document,)
    missing_candidate = SimpleNamespace(model_instances=tuple(
        replace(item, inputs=tuple(edge for edge in item.inputs if edge.path != document))
        if item.logical_model_id == owner else item for item in candidate.model_instances))
    with pytest.raises(ModelAuthorityError, match=(
            "candidate logical model omits or mismatches its exact intent-source input: "
            "owner=model:" + owner + "; source=" + document)):
        validate_candidate_intent_source_input_bindings(missing_candidate, added, sources)


def test_actual_new_owners_have_independent_typed_normative_additions(tmp_path, monkeypatch):
    base, candidate, diff = _actual_addition_inputs()
    added = direct._added_model_intents(SOURCE, base, candidate, diff, ADDED_IDS,
                                      "revision:finite-added-test", {x: () for x in ADDED_IDS})
    assert {x.logical_model_id for x in added} == {"model:" + x for x in ADDED_IDS}
    assert len({x.contribution_id for x in added}) == len(ADDED_IDS)
    for item in added:
        assert ModelIntentContribution.from_dict(item.to_dict()) == item
        assert item.source_ref == "docs/functional_source_contracts.md"
        assert not item.supersedes_contribution_ids
        assert item.subject_lane == "normative_target"
        assert len(item.target_obligation_ids) == 1
        disposition = ModelIntentDisposition(
            contribution_id=item.contribution_id,
            contribution_fingerprint=item.fingerprint, disposition="accepted",
            changed_obligation_ids=(), changed_state_ids=(), changed_transition_ids=(),
            changed_invariant_ids=(), scoped_gap_ids=(), conflict_ids=(),
            unresolved_effect_ids=(), unreachable_terminal_state_ids=(), unconsumed_output_ids=(),
            reason="Finite test author disposition; executed native evidence is independently pending.",
            changed_relation_ids=())
        assert ModelIntentDisposition.from_dict(disposition.to_dict()) == disposition
    # Exercise the real build output accounting: independent additions do not
    # supersede a retained predecessor or make the retain count negative.
    retained = replace(added[0], contribution_id="intent:retained-functional-fixture",
                       logical_model_id="model:development_process_flow",
                       rationale="Finite retained predecessor accounting fixture; this does not assert accepted model authority.")
    entries = {x.model_id: x for x in ModelRegressionManifest.load(SOURCE).entries}
    entry = entries["development_process_flow"]
    retained_model = build_model_instance_ref(SOURCE, logical_model_id=entry.model_id,
        model_kind=entry.model_kind, model_path=entry.model_path, runner_path=entry.runner[1],
        purpose_closure_fingerprint=entry.purpose_closure.closure_fingerprint,
        input_paths=(entry.model_path, entry.runner[1]))
    base = SimpleNamespace(model_instances=(retained_model,), system_id="flowguard",
        subject_lane="observed_implementation", lifecycle="active", fingerprint="sha256:" + "1" * 64)
    candidate = SimpleNamespace(model_instances=(*candidate.model_instances, retained_model),
        fingerprint="sha256:" + "2" * 64, relations=())
    diff.changed_relation_ids = ()
    revision = SimpleNamespace(current_effective_intent_view=SimpleNamespace(active_contributions=(retained,)))
    monkeypatch.setattr(direct, "load_observed_model_system", lambda root: (None, base))
    monkeypatch.setattr(direct, "load_current_accepted_revision_set", lambda *args, **kwargs: revision)
    monkeypatch.setattr(direct, "build_manifest_model_system_snapshot", lambda *args, **kwargs: candidate)
    monkeypatch.setattr(direct, "derive_revision_snapshot_diff", lambda *args: diff)
    monkeypatch.setattr(direct, "compile_flowguard_self_path_quality_material",
        lambda *args: SimpleNamespace(review=SimpleNamespace(subjects=(), results=())))
    result = direct.build_inputs(SOURCE, snapshot_id="snapshot:finite-addition",
        revision_token="revision:finite-added-test", reviewed_models=ADDED_IDS,
        relation_assignments={}, intent_output=tmp_path / "intent-inventory.json",
        path_quality_output=tmp_path / "path-quality.json")
    assert result["explicit_supersede_count"] == 0
    assert result["explicit_retain_count"] == 1
    assert result["added_model_count"] == len(ADDED_IDS)
    assert len(json.loads((tmp_path / "intent-inventory.json").read_text(encoding="utf-8"))["effective_intent_transitions"]) == 1


def test_foreign_or_replaced_model_cannot_enter_added_intent_route():
    base, candidate, diff = _actual_addition_inputs()
    foreign = SimpleNamespace(members=(*diff.members, SimpleNamespace(member_id="foreign", operation="add")))
    with pytest.raises(RuntimeError, match="exact typed candidate additions"):
        direct._added_model_intents(SOURCE, base, candidate, foreign, (*ADDED_IDS, "foreign"), "revision:foreign", {x: () for x in ADDED_IDS})
    replaced = SimpleNamespace(members=tuple(SimpleNamespace(member_id=x, operation="replace") for x in ADDED_IDS))
    with pytest.raises(RuntimeError, match="exact typed candidate additions"):
        direct._added_model_intents(SOURCE, base, candidate, replaced, ADDED_IDS, "revision:foreign", {x: () for x in ADDED_IDS})


def test_missing_or_foreign_normative_promise_blocks_real_addition(monkeypatch):
    base, candidate, diff = _actual_addition_inputs()
    ledger = load_behavior_commitment_ledger(SOURCE / ".flowguard/behavior/inventory/ledger.json")
    missing = replace(ledger, commitments=tuple(x for x in ledger.commitments
                      if x.metadata.get("primary_native_owner") != "evidence_storage_lifecycle"))
    monkeypatch.setattr("flowguard.behavior_commitment.load_behavior_commitment_ledger", lambda path: missing)
    with pytest.raises(RuntimeError, match="independent current normative functional promise"):
        direct._added_model_intents(SOURCE, base, candidate, diff, ADDED_IDS, "revision:missing", {x: () for x in ADDED_IDS})
    foreign = replace(ledger, commitments=tuple(replace(x, primary_owner_model_id="foreign.py")
                      if x.metadata.get("primary_native_owner") == "evidence_storage_lifecycle" else x for x in ledger.commitments))
    monkeypatch.setattr("flowguard.behavior_commitment.load_behavior_commitment_ledger", lambda path: foreign)
    with pytest.raises(RuntimeError, match="independent current normative functional promise"):
        direct._added_model_intents(SOURCE, base, candidate, diff, ADDED_IDS, "revision:foreign", {x: () for x in ADDED_IDS})


def test_existing_model_missing_prior_intent_still_blocks_build(tmp_path, monkeypatch):
    base = SimpleNamespace(system_id="flowguard", subject_lane="observed_implementation", lifecycle="active")
    candidate = SimpleNamespace()
    diff = SimpleNamespace(members=(SimpleNamespace(member_id="existing", operation="replace"),))
    revision = SimpleNamespace(current_effective_intent_view=SimpleNamespace(active_contributions=()))
    monkeypatch.setattr(direct, "load_observed_model_system", lambda root: (None, base))
    monkeypatch.setattr(direct, "load_current_accepted_revision_set", lambda *args, **kwargs: revision)
    monkeypatch.setattr(direct, "build_manifest_model_system_snapshot", lambda *args, **kwargs: candidate)
    monkeypatch.setattr(direct, "derive_revision_snapshot_diff", lambda *args: diff)
    monkeypatch.setattr(direct, "_intent_review_models", lambda *args, **kwargs: ("existing",))
    monkeypatch.setattr(direct, "_relation_targets", lambda *args, **kwargs: {"existing": ()})
    with pytest.raises(RuntimeError, match="changed models have no prior reviewed intent: existing"):
        direct.build_inputs(tmp_path, snapshot_id="snapshot:finite", revision_token="revision:finite",
                            reviewed_models=("existing",), relation_assignments={},
                            intent_output=tmp_path / "out/intent-inventory.json",
                            path_quality_output=tmp_path / "out/path-quality.json")
    assert not (tmp_path / "out").exists()
