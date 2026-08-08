from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import mock

import pytest

from flowguard.__main__ import _run_flowguard_self_blueprint_check_command
from flowguard.architecture_reduction import (
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_MERGE_MODULES,
    PROOF_SAFE_BY_EQUIVALENCE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_MERGE,
)
from flowguard.blueprint_compact_projection import BlueprintCompactProjection
from flowguard.evidence_receipts import (
    canonical_receipt_json,
    fingerprint_value,
    load_evidence_receipt,
    receipt_path,
    save_evidence_receipt,
)
from flowguard.self_architecture_reduction import (
    SELF_REDUCTION_PARITY_OBLIGATION_IDS,
    SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT,
    SelfArchitectureReductionReview,
    SelfReductionEvidenceNeighborhood,
    SelfReductionEvidenceNeighborhoodCatalog,
    SelfReductionProofRecord,
    SelfReductionProofSelection,
    _VerifiedSelfReductionProof,
    _block_conflicting_candidate_actions,
    _candidate_semantic_bindings,
    _canonical_validation_owner_root,
    _candidate_binding,
    _discover_current_self_reduction_proofs,
    _derive_current_external_commitment_bindings,
    _derive_public_facade_binding,
    _execution_subject,
    _proof_contracts,
    _proof_record_matches_current_candidate,
    _recheck_verified_proof_currentness,
    _resolved_candidate_observable_contract,
    _review_current_flowguard_self_architecture_reduction,
    _self_reduction_completion_status,
    _self_step_assessments,
    _reverse_call_alias_index,
    _self_reduction_candidates,
    _validate_record_against_candidate,
    _validate_semantic_execution_result,
    _verify_proof_records,
    build_flowguard_self_architecture_reduction_review,
    execute_flowguard_self_reduction_proofs,
    review_flowguard_self_architecture_reduction as _review_flowguard_self_architecture_reduction,
)
from flowguard.self_reduction_inventory import derive_self_reduction_universe
from flowguard.self_reduction_inventory import (
    derive_self_reduction_retain_dispositions,
)
from flowguard.self_blueprint import SelfBlueprintBuildInputIdentity


@pytest.fixture(autouse=True)
def _isolate_external_commitment_inventory():
    """Synthetic review bundles do not own the repository's real BCL."""

    with mock.patch(
        "flowguard.self_architecture_reduction._derive_current_external_commitment_bindings",
        return_value={},
    ):
        yield


def test_verified_proof_proxy_exposes_only_its_finite_record_contract():
    proxy = SimpleNamespace(
        record=SimpleNamespace(
            proof_id="proof:current",
            implementation_detail="must-not-leak",
        )
    )

    assert _VerifiedSelfReductionProof.__getattr__(proxy, "proof_id") == "proof:current"
    with pytest.raises(AttributeError, match="does not expose"):
        _VerifiedSelfReductionProof.__getattr__(proxy, "implementation_detail")


def _build_input_identity(label="current"):
    value = f"sha256:{label}"
    return SelfBlueprintBuildInputIdentity(
        subject_revision=value,
        model_authority_audit_fingerprint=value,
        observed_snapshot_fingerprint=value,
        accepted_revision_set_fingerprint=value,
        definition_fingerprint=value,
        boundary_fingerprint=value,
        file_inventory_fingerprint=value,
        file_count=1,
        semantic_mesh_fingerprint=value,
        activation_receipt_fingerprint=value,
        model_regression_evidence_fingerprint=value,
        provider_contract_fingerprint=value,
    )


def _bundle(*, ok: bool = True, with_coverage: bool = False):
    if with_coverage:
        surfaces = tuple(
            SimpleNamespace(
                surface_id=f"surface:candidate-{name}",
                path=f"flowguard/large_{name}.py",
                symbol=f"candidate_{name}",
                line_start=1,
                line_end=6,
                structure_fingerprint="sha256:shared-candidate-shape",
                content_fingerprint=f"sha256:candidate-content-{name}",
                roles=("behavior",),
                surface_kind="function",
                calls=(f"prepare_{name}", f"finish_{name}"),
                state_reads=("value",),
                state_writes=("state",),
                side_effect_candidates=("record",),
                raised_errors=("negative",),
            )
            for name in ("a", "b", "c")
        )
    else:
        surfaces = tuple(
            SimpleNamespace(
                surface_id=f"surface:{index:02d}",
                path="flowguard/large.py",
                symbol=f"surface_{index:02d}",
                line_start=1,
                line_end=100 + index,
                structure_fingerprint=f"sha256:shape:{index:02d}",
                content_fingerprint=f"sha256:content:{index:02d}",
                roles=(),
                surface_kind="function",
                calls=(),
            )
            for index in range(151)
        )
    inventory = SimpleNamespace(
        boundary=SimpleNamespace(subject_revision=fingerprint_value("subject")),
        surfaces=surfaces,
        required_surface_ids=tuple(row.surface_id for row in surfaces),
        findings=(),
        file_dispositions=(),
        inventory_fingerprint=fingerprint_value("inventory"),
    )
    test_id = "test:external-equivalence"
    pytest_nodeid = (
        "tests/test_self_architecture_reduction.py::test_external_equivalence"
    )
    assertion_lines = {
        "a": {"input": 7, "output": 8, "state": 9, "effect": 10, "error": 11},
        "b": {"input": 13, "output": 14, "state": 15, "effect": 16, "error": 17},
        "c": {"input": 19, "output": 20, "state": 21, "effect": 22, "error": 23},
    }
    assertion_targets = {
        "input": 'result_{name}["input"] == 2',
        "output": 'result_{name}["output"] == 3',
        "state": 'result_{name}["state"] == 3',
        "effect": 'result_{name}["effect"] == "record"',
        "error": 'candidate_{name}(-1)["error"] == "negative"',
    }
    assertions = tuple(
        SimpleNamespace(
            assertion_id=f"assertion:{name}:{dimension}",
            assertion_kind="assert",
            target=assertion_targets[dimension].format(name=name),
            structure_fingerprint=fingerprint_value(
                assertion_targets[dimension].format(name=name)
            ),
            line_start=assertion_lines[name][dimension],
            line_end=assertion_lines[name][dimension],
        )
        for name in ("a", "b", "c")
        for dimension in ("input", "output", "state", "effect", "error")
    )
    contracts = tuple(
        SimpleNamespace(
            implementation_surface_id=f"surface:candidate-{name}",
            behavior_block_id=f"behavior:candidate-{name}",
            model_element_id=f"model:candidate-{name}",
            owner_contract_id=f"owner-contract:candidate-{name}",
            owner_id=f"owner:candidate-{name}",
            accepted=True,
            source_fingerprint=f"sha256:candidate-content-{name}",
            semantic_spec_ids=(f"semantic-spec:candidate-{name}",),
            oracle_ids=(f"oracle:candidate-{name}",),
            intent_contribution_ids=(f"intent:candidate-{name}",),
            fingerprint=f"sha256:contract:candidate-{name}",
        )
        for name in ("a", "b", "c")
    ) if with_coverage else ()
    case_contracts = tuple(
        SimpleNamespace(
            case_id=f"case:{name}:{kind}",
            behavior_block_id=f"behavior:candidate-{name}",
            case_kind=kind,
            input_values=(("value", "2" if kind == "good" else "-1"),),
            initial_state=(("state", "2" if kind == "good" else "-1"),),
            expected_output=(("return", "3" if kind == "good" else "None"),),
            expected_state=(("state", "3" if kind == "good" else "-1"),),
            expected_effects=(("record",) if kind == "good" else ("none",)),
            expected_errors=(() if kind == "good" else ("negative",)),
            oracle_id=f"oracle:candidate-{name}",
            content_fingerprint=fingerprint_value(
                {"candidate": name, "kind": kind}
            ),
        )
        for name in ("a", "b", "c")
        for kind in ("good", "bad")
    ) if with_coverage else ()
    cases_by_id = {row.case_id: row for row in case_contracts}
    assertion_by_id = {row.assertion_id: row for row in assertions}
    coverage_edges = tuple(
        SimpleNamespace(
            coverage_id=f"coverage:{name}:{dimension}",
            implementation_surface_id=f"surface:candidate-{name}",
            behavior_block_id=f"behavior:candidate-{name}",
            test_node_id=test_id,
            oracle_member_id=f"assertion:{name}:{dimension}",
            oracle_member_fingerprint=assertion_by_id[
                f"assertion:{name}:{dimension}"
            ].structure_fingerprint,
            case_id=f"case:{name}:{'bad' if dimension == 'error' else 'good'}",
            case_content_fingerprint=cases_by_id[
                f"case:{name}:{'bad' if dimension == 'error' else 'good'}"
            ].content_fingerprint,
            covered_dimensions=(dimension,),
            oracle_id=f"oracle:candidate-{name}",
        )
        for name in ("a", "b", "c")
        for dimension in ("input", "output", "state", "effect", "error")
    ) if with_coverage else ()
    behavior_report = SimpleNamespace(
        contracts=contracts,
        supporting_relations=(),
        case_contracts=case_contracts,
        coverage_edges=coverage_edges,
        coverage_execution_evidence=(),
        fingerprint=fingerprint_value("behavior"),
    )
    intent_contributions = tuple(
        SimpleNamespace(
            contribution_id=f"intent:candidate-{name}",
            disposition="accepted",
            target_ids=(f"model:candidate-{name}",),
            source_kind="current-effective-intent",
            source_id=f"source:candidate-{name}",
            source_owner_id=f"source-owner:candidate-{name}",
            expectation_id=f"expectation:candidate-{name}",
            source_fingerprint=f"sha256:intent-source:candidate-{name}",
            expectation_fingerprint=f"sha256:expectation:candidate-{name}",
            rationale=f"current candidate {name} behavior",
        )
        for name in ("a", "b", "c")
    ) if with_coverage else ()
    intent_authorities = tuple(
        SimpleNamespace(
            source_kind="current-effective-intent",
            source_id=f"source:candidate-{name}",
            source_owner_id=f"source-owner:candidate-{name}",
            expectation_id=f"expectation:candidate-{name}",
            current_source_fingerprint=f"sha256:intent-source:candidate-{name}",
            current_expectation_fingerprint=f"sha256:expectation:candidate-{name}",
            target_ids=(f"model:candidate-{name}",),
            status="current",
            fingerprint=f"sha256:intent-authority:candidate-{name}",
        )
        for name in ("a", "b", "c")
    ) if with_coverage else ()
    semantic_specs = tuple(
        SimpleNamespace(
            semantic_spec_id=f"semantic-spec:candidate-{name}",
            covered_model_element_ids=(f"model:candidate-{name}",),
            semantics=(
                ("input", "accept one current value"),
                ("output", f"candidate {name} current result"),
                ("state", "advance the declared state"),
                ("effect", "record the declared result"),
                ("error", "raise the declared negative error"),
            ),
            fingerprint=f"sha256:semantic-spec:candidate-{name}",
        )
        for name in ("a", "b", "c")
    ) if with_coverage else ()
    binding_rows = tuple(
        SimpleNamespace(
            implementation_surface_id=f"surface:candidate-{name}",
            model_element_id=f"model:candidate-{name}",
            owner_contract_id=f"owner-contract:candidate-{name}",
            implementation_content_fingerprint=f"sha256:candidate-content-{name}",
            semantic_spec_ids=(f"semantic-spec:candidate-{name}",),
            oracle_ids=(f"oracle:candidate-{name}",),
            test_evidence_ids=(test_id,),
            consumer_surface_ids=(f"consumer:candidate-{name}",),
            fingerprint=f"sha256:binding:candidate-{name}",
        )
        for name in ("a", "b", "c")
    ) if with_coverage else ()
    bundle = SimpleNamespace(
        ok=ok,
        build_input_identity=_build_input_identity(),
        inventory=inventory,
        implementation_inventory_audit=SimpleNamespace(
            ok=True,
            status="complete",
            inventory_fingerprint=inventory.inventory_fingerprint,
            findings=(),
            fingerprint="sha256:inventory-audit",
        ),
        behavior_report=behavior_report,
        intent_inventory=SimpleNamespace(
            complete=True,
            fingerprint=fingerprint_value(
                tuple(row.contribution_id for row in intent_contributions)
            ),
            contributions=intent_contributions,
            source_authorities=intent_authorities,
        ),
        binding_report=SimpleNamespace(
            ok=True,
            fingerprint=fingerprint_value(
                tuple(row.implementation_surface_id for row in binding_rows)
            ),
            bindings=binding_rows,
            semantic_specs=semantic_specs,
            oracles=tuple(
                SimpleNamespace(
                    oracle_id=f"oracle:candidate-{name}",
                    fingerprint=f"sha256:oracle:candidate-{name}",
                )
                for name in ("a", "b", "c")
            ) if with_coverage else (),
        ),
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
        target_system_report=SimpleNamespace(provider_results=()),
        resource_inventory=SimpleNamespace(members=()),
        test_inventory=SimpleNamespace(
            inventory_fingerprint=fingerprint_value("test-inventory"),
            nodes=(
                SimpleNamespace(
                    node_id=test_id,
                    path="tests/test_self_architecture_reduction.py",
                    pytest_nodeid=pytest_nodeid,
                    source_fingerprint="sha256:test-external-equivalence",
                    assertions=assertions,
                    disposition="required",
                ),
            ) if with_coverage else (),
            required_node_ids=((test_id,) if with_coverage else ()),
        ),
        qualification=SimpleNamespace(fingerprint="sha256:qualification"),
        static_readiness=SimpleNamespace(
            fingerprint="sha256:readiness"
        ),
    )
    bundle.to_dict = lambda: {
        "ok": bundle.ok,
        "inventory_fingerprint": bundle.inventory.inventory_fingerprint,
        "required_surface_ids": list(bundle.inventory.required_surface_ids),
        "behavior_report_fingerprint": bundle.behavior_report.fingerprint,
        "test_inventory_fingerprint": bundle.test_inventory.inventory_fingerprint,
    }
    return bundle


def _same_commitment_candidate_bundle():
    bundle = _bundle(with_coverage=True)
    bundle.binding_report.semantic_specs = tuple(
        SimpleNamespace(
            **{
                **vars(spec),
                "semantics": (
                    ("input", "accept one current value"),
                    ("output", "one shared current result"),
                    ("state", "advance the declared state"),
                    ("effect", "record the declared result"),
                    ("error", "raise the declared negative error"),
                ),
            }
        )
        for spec in bundle.binding_report.semantic_specs
    )
    return bundle


def review_flowguard_self_architecture_reduction(
    *args,
    self_blueprint=None,
    **kwargs,
):
    """Exercise candidate internals with a trusted builder double."""

    if self_blueprint is None:
        return _review_flowguard_self_architecture_reduction(*args, **kwargs)
    proof_records = kwargs.pop("proof_records", None)
    if proof_records is not None and any(
        not isinstance(row, SelfReductionProofRecord) for row in proof_records
    ):
        raise TypeError(
            "self reduction proof registry requires SelfReductionProofRecord rows"
        )
    if proof_records is not None:
        proof_ids = tuple(row.proof_id for row in proof_records)
        if len(proof_ids) != len(set(proof_ids)):
            raise ValueError(
                "self reduction proof registry contains duplicate proof ids"
            )
        roots = {
            _PROOF_ROOT_BY_RECEIPT_ID[row.aggregate_receipt_id]
            for row in proof_records
        }
        if roots:
            assert len(roots) == 1
            if args or "root" in kwargs:
                raise AssertionError(
                    "proof helper owns its isolated repository root"
                )
            kwargs["root"] = roots.pop()
    root = kwargs.pop("root", args[0] if args else ".")
    if len(args) > 1:
        raise AssertionError("unexpected positional reduction-review arguments")
    discovery_patch = nullcontext()
    if proof_records is not None:
        discovery_patch = mock.patch(
            "flowguard.self_architecture_reduction._discover_current_self_reduction_proofs",
            side_effect=lambda discovery_root, bundle, candidates: (
                _verify_proof_records(
                    discovery_root,
                    bundle,
                    candidates,
                    tuple(proof_records),
                ),
                (),
            ),
        )
    with mock.patch(
        "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
        return_value=_build_input_identity(),
    ), discovery_patch:
        return _review_current_flowguard_self_architecture_reduction(
            root,
            bundle=self_blueprint,
            build_input_identity=_build_input_identity(),
            **kwargs,
        )


_PROOF_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []
_PROOF_ROOT_BY_RECEIPT_ID: dict[str, str] = {}


def test_proofless_risky_keep_passes_audit_without_cleanup_authority():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_same_commitment_candidate_bundle()
    )

    assert report.ok
    assert report.status == "pass"
    assert report.audit_accounted
    assert report.audit_complete
    assert report.action_authorized_candidate_ids == ()
    assert not report.cleanup_release_ready
    assert report.unresolved_member_ids == ()
    assert not report.step_decision_complete
    assert report.unresolved_step_ids
    assert report.denominator_complete
    assert report.candidate_review_complete
    assert report.reduction_universe_fingerprint != report.candidate_inventory_fingerprint
    assert len(report.reduction_universe.implementation_surface_ids) == 3
    assert report.reduction_universe.reduction_signal_ids
    assert all(
        row.disposition in {"retain", "contract", "unresolved"}
        for row in report.reduction_universe.members
    )
    assert len(report.candidates) == 1
    assert report.safe_unapplied_candidate_ids == ()
    assert report.candidates[0].proof_status == "risky_keep"
    assert report.candidates[0].target_action == "manual_review"
    assert report.candidates[0].metadata["disposition"] == "unresolved"
    assert report.reduction_report.decision == "no_ready_reduction_candidates"
    assert report.fingerprint.startswith("sha256:")
    assert report.review_fingerprint == report.fingerprint


def test_distinct_current_commitments_resolve_candidate_as_retain_and_close_cleanup():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(with_coverage=True)
    )

    candidate_retain_rows = tuple(
        row
        for row in report.retain_dispositions
        if row.basis == "different_current_semantics"
    )
    assert len(candidate_retain_rows) == len(report.candidates) == 1
    candidate = report.candidates[0]
    disposition = candidate_retain_rows[0]
    assert disposition.candidate_ids == (candidate.candidate_id,)
    assert candidate.candidate_id not in disposition.owner_refs
    step = report.reduction_report.step_assessments[0]
    assert step.candidate_id == candidate.candidate_id
    assert step.action == "retain"
    assert step.current_owner_ids == (
        "owner:candidate-a",
        "owner:candidate-b",
        "owner:candidate-c",
    )
    assert step.necessity_evidence_refs
    assert step.safety_inventory_complete
    assert report.candidate_review_complete
    assert report.step_decision_complete
    assert report.unresolved_step_ids == ()
    assert report.unresolved_member_ids == ()
    assert report.cleanup_release_ready


def test_same_commitment_candidate_remains_unresolved_even_when_members_have_owners():
    bundle = _same_commitment_candidate_bundle()

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)

    assert not any(
        row.basis == "different_current_semantics"
        for row in report.retain_dispositions
    )
    assert report.unresolved_member_ids == ()
    assert report.candidate_review_complete
    assert not report.step_decision_complete
    assert report.unresolved_step_ids == (
        "candidate-step:" + report.candidates[0].candidate_id,
    )
    assert report.reduction_report.step_assessments[0].action == "unresolved"
    assert report.audit_complete
    assert report.status == "pass"
    assert not report.cleanup_release_ready


def test_unreferenced_helpers_with_current_necessity_are_retained_without_delete_proof():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(with_coverage=True)
    )
    candidate = report.candidates[0]
    candidate = replace(
        candidate,
        metadata={
            **candidate.metadata,
            "signal": "unreferenced_helper",
            "caller_resolution_gap_ids": (
                "caller-resolution-gap:dynamic-framework-callback",
            ),
        },
    )
    member_necessity = tuple(
        row
        for row in report.retain_dispositions
        if row.basis == "current_necessity_witness"
    )

    step = _self_step_assessments(
        (candidate,),
        member_necessity,
    )[0]

    assert step.action == "retain"
    assert step.necessity_evidence_refs
    assert step.safety_inventory_complete
    assert not step.caller_inventory_complete
    assert step.unresolved_gap_ids == ()


@pytest.mark.parametrize(
    (
        "blueprint_ok",
        "denominator_complete",
        "candidate_review_complete",
        "step_decision_complete",
        "unresolved_member_ids",
        "unresolved_step_ids",
        "authorized_ids",
        "expected",
    ),
    (
        (True, True, True, True, (), (), (), (True, True, "pass")),
        (True, True, False, True, (), (), (), (True, False, "pass")),
        (
            True,
            True,
            True,
            False,
            (),
            ("candidate-step:proofless",),
            (),
            (True, False, "pass"),
        ),
        (
            True,
            True,
            False,
            False,
            ("candidate:proofless",),
            ("candidate-step:proofless",),
            (),
            (True, False, "pass"),
        ),
        (
            True,
            True,
            True,
            True,
            (),
            (),
            ("candidate:safe-unapplied",),
            (True, False, "blocked"),
        ),
        (False, True, True, True, (), (), (), (False, False, "blocked")),
        (True, False, True, True, (), (), (), (False, False, "blocked")),
    ),
)
def test_self_reduction_completion_states_are_distinct(
    blueprint_ok,
    denominator_complete,
    candidate_review_complete,
    step_decision_complete,
    unresolved_member_ids,
    unresolved_step_ids,
    authorized_ids,
    expected,
):
    assert _self_reduction_completion_status(
        blueprint_ok=blueprint_ok,
        reduction_report_ok=True,
        denominator_complete=denominator_complete,
        audit_accounted=True,
        candidate_review_complete=candidate_review_complete,
        step_decision_complete=step_decision_complete,
        unresolved_member_ids=unresolved_member_ids,
        unresolved_step_ids=unresolved_step_ids,
        action_authorized_candidate_ids=authorized_ids,
    ) == expected


def test_full_review_serialization_reuses_stored_review_fingerprint():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle()
    )
    original_identity_payload = SelfArchitectureReductionReview.identity_payload
    calls = []

    def counted_identity_payload(review):
        calls.append(review)
        return original_identity_payload(review)

    with mock.patch.object(
        SelfArchitectureReductionReview,
        "identity_payload",
        counted_identity_payload,
    ):
        payload = report.to_dict()

    assert calls == [report]
    assert payload["review_fingerprint"] == report.review_fingerprint
    assert payload["fingerprint"] == report.review_fingerprint


def test_compact_projection_reads_the_current_review_schema_property():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle()
    )

    assert "schema_version" not in report.__dict__
    payload = BlueprintCompactProjection.reduction(report)

    assert payload["schema_version"] == (
        "flowguard.self_architecture_reduction_review.v14"
        )
    assert "necessity_gap_counts_by_kind" in payload
    assert "necessity_gap_examples_by_kind" in payload
    assert set(payload["necessity_gap_examples_by_kind"]) == set(
        payload["necessity_gap_counts_by_kind"]
    )


def test_public_review_rejects_label_only_self_blueprint_bundle():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _review_flowguard_self_architecture_reduction(
            self_blueprint=_bundle()
        )


def test_self_reduction_cannot_pass_when_bound_self_blueprint_is_blocked():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(ok=False)
    )
    assert report.status == "blocked"
    assert not report.ok
    assert report.audit_accounted
    assert not report.audit_complete
    assert report.action_authorized_candidate_ids == ()
    assert not report.cleanup_release_ready


def test_self_reduction_denominator_does_not_shrink_to_empty_candidate_list():
    bundle = _bundle()
    bundle.inventory.surfaces = bundle.inventory.surfaces[:2]
    bundle.inventory.required_surface_ids = tuple(
        row.surface_id for row in bundle.inventory.surfaces
    )

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)

    assert report.candidates == ()
    assert report.denominator_complete
    assert not report.candidate_review_complete
    assert report.reduction_universe.implementation_surface_ids == (
        "surface:00",
        "surface:01",
    )


def test_self_reduction_inventory_covers_routes_adapters_helpers_and_validation_paths():
    rows = (
        SimpleNamespace(
            surface_id="route:a",
            path="flowguard/a.py",
            symbol="run_a",
            line_end=20,
            structure_fingerprint="sha256:route-a",
            roles=("entrypoint",),
            surface_kind="entrypoint",
            calls=("dispatch",),
        ),
        SimpleNamespace(
            surface_id="route:b",
            path="flowguard/b.py",
            symbol="run_b",
            line_end=20,
            structure_fingerprint="sha256:route-a",
            roles=("entrypoint",),
            surface_kind="entrypoint",
            calls=("dispatch",),
        ),
        SimpleNamespace(
            surface_id="adapter:a",
            path="flowguard/a_adapter.py",
            symbol="observe_a",
            line_end=20,
            structure_fingerprint="sha256:adapter-a",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="adapter:b",
            path="flowguard/b_provider.py",
            symbol="observe_b",
            line_end=20,
            structure_fingerprint="sha256:adapter-a",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="helper:a",
            path="flowguard/a.py",
            symbol="_normalize_a",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="helper:b",
            path="flowguard/b.py",
            symbol="_normalize_b",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="validation:a",
            path="flowguard/a.py",
            symbol="review_a",
            line_end=20,
            structure_fingerprint="sha256:validation-a",
            roles=(),
            surface_kind="function",
            calls=("qualify", "report"),
        ),
        SimpleNamespace(
            surface_id="validation:b",
            path="flowguard/b.py",
            symbol="check_b",
            line_end=20,
            structure_fingerprint="sha256:validation-a",
            roles=(),
            surface_kind="function",
            calls=("qualify", "report"),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    signals = {row.metadata["signal"] for row in report.candidates}

    assert signals >= {
        "duplicate_route",
        "adapter_layer",
        "unreferenced_helper",
        "validation_path",
    }
    assert all(row.proof_status == "risky_keep" for row in report.candidates)
    assert report.safe_unapplied_candidate_ids == ()
    assert all(
        row.required_next_route == ROUTE_STRUCTURE_MESH
        for row in report.candidates
        if row.affected_public_entrypoints
    )
    assert (
        ROUTE_DEVELOPMENT_PROCESS_FLOW
        in report.reduction_report.required_next_routes
    )


def test_self_reduction_audits_maintenance_serialization_and_uncalled_helper_signals():
    rows = (
        SimpleNamespace(
            surface_id="compat:a",
            path="flowguard/legacy_adapter.py",
            symbol="compat_alias",
            line_end=20,
            structure_fingerprint="sha256:compat",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
            state_reads=("authority",),
            state_writes=("authority",),
            side_effect_candidates=("write_pointer",),
            raised_errors=("ValueError",),
        ),
        SimpleNamespace(
            surface_id="compat:b",
            path="flowguard/compat_adapter.py",
            symbol="legacy_delegate",
            line_end=20,
            structure_fingerprint="sha256:compat",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        ),
        SimpleNamespace(
            surface_id="serialize:a",
            path="flowguard/a.py",
            symbol="to_dict",
            line_end=20,
            structure_fingerprint="sha256:serialize-a",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="serialize:b",
            path="flowguard/b.py",
            symbol="serialize_result",
            line_end=20,
            structure_fingerprint="sha256:serialize-a",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="helper:dead",
            path="flowguard/dead.py",
            symbol="_unused_helper",
            line_end=20,
            structure_fingerprint="sha256:dead",
            roles=(),
            surface_kind="function",
            calls=("leaf",),
        ),
        SimpleNamespace(
            surface_id="caller:a",
            path="flowguard/caller_a.py",
            symbol="call_a",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:caller-a",
            content_fingerprint="sha256:caller-a",
            roles=(),
            surface_kind="function",
            calls=("a._normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:b",
            path="flowguard/caller_b.py",
            symbol="call_b",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:caller-b",
            content_fingerprint="sha256:caller-b",
            roles=(),
            surface_kind="function",
            calls=("b._normalize",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    by_signal = {row.metadata["signal"]: row for row in report.candidates}

    assert {
        "fallback_alias_compatibility_path",
        "serialization_path",
        "unreferenced_helper",
    } <= set(by_signal)
    maintenance = by_signal["fallback_alias_compatibility_path"]
    contract = maintenance.metadata["observable_contract"]
    assert contract["state_reads"] == ("authority",)
    assert contract["state_writes"] == ("authority",)
    assert contract["side_effect_ids"] == ("write_pointer",)
    assert contract["raised_error_ids"] == ("ValueError",)
    assert {
        "current_observable_equivalence",
        "caller_consumer_parity",
        "state_parity",
        "side_effect_parity",
        "error_parity",
    } <= set(maintenance.metadata["missing_proof_obligations"])
    assert ROUTE_STRUCTURE_MESH in maintenance.metadata["required_route_ids"]
    assert (
        ROUTE_DEVELOPMENT_PROCESS_FLOW
        in maintenance.metadata["required_route_ids"]
    )
    assert all(row.proof_status == "risky_keep" for row in by_signal.values())
    assert report.safe_unapplied_candidate_ids == ()
    assert all(
        row.metadata["step_cost_evidence"]["measurement_mode"]
        == "static_inventory_projection"
        for row in by_signal.values()
    )
    step_assessments = report.reduction_report.step_assessments
    assert len(step_assessments) == len(report.candidates)
    assert {row.candidate_id for row in step_assessments} == {
        row.candidate_id for row in report.candidates
    }
    assert {row.action for row in step_assessments} == {"unresolved"}
    assert all(row.cost_evidence for row in step_assessments)
    assert all(row.unresolved_gap_ids for row in step_assessments)
    assert len(report.reduction_report.cost_priority_step_ids) == len(
        step_assessments
    )
    signal_members = tuple(
        row
        for row in report.reduction_universe.members
        if row.step_action
    )
    assert signal_members
    assert {row.step_action for row in signal_members} <= {
        "retain",
        "unresolved",
    }
    assert all(row.static_operation_count > 0 for row in signal_members)
    assert all(row.analysis_payload_bytes > 0 for row in signal_members)


def test_unreferenced_helpers_use_deterministic_finite_candidate_batches():
    helper_count = SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT + 2
    rows = tuple(
        SimpleNamespace(
            surface_id=f"helper:{index:02d}",
            path="flowguard/many_dead_helpers.py",
            symbol=f"_unused_{index:02d}",
            line_end=20 + index,
            structure_fingerprint=f"sha256:unused-{index:02d}",
            roles=(),
            surface_kind="function",
            calls=(f"leaf_{index:02d}",),
        )
        for index in range(helper_count)
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(
        row.surface_id for row in rows
    )

    report = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )
    candidates = tuple(
        row
        for row in report.candidates
        if row.metadata["signal"] == "unreferenced_helper"
    )

    assert len(candidates) == 2
    assert tuple(
        row.metadata["group_key"] for row in candidates
    ) == (
        "flowguard/many_dead_helpers.py#batch:0001",
        "flowguard/many_dead_helpers.py#batch:0002",
    )
    assert all(
        0 < len(row.metadata["member_ids"])
        <= SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
        for row in candidates
    )
    assert {
        member_id
        for row in candidates
        for member_id in row.metadata["member_ids"]
    } == {row.surface_id for row in rows}


def test_oversized_boundary_stays_a_structure_trigger_without_a_fake_split_candidate():
    rows = tuple(
        SimpleNamespace(
            surface_id=f"surface:large:{index:03d}",
            path="flowguard/large_owner.py",
            symbol=f"operation_{index:03d}",
            line_start=index * 20 + 1,
            line_end=index * 20 + 20,
            structure_fingerprint=f"sha256:unique:{index:03d}",
            content_fingerprint=f"sha256:content:{index:03d}",
            roles=("behavior",),
            surface_kind="function",
            calls=(f"prepare_{index:03d}", f"finish_{index:03d}"),
            state_reads=(),
            state_writes=(),
            side_effect_candidates=(),
            raised_errors=(),
        )
        for index in range(150)
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(
        row.surface_id for row in rows
    )
    universe = derive_self_reduction_universe(bundle)

    candidates, _, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
    )

    assert universe.oversized_boundaries
    assert not any(
        row.metadata["signal"] == "oversized_module"
        for row in candidates
    )


def test_same_member_group_from_branch_and_helper_signals_is_reviewed_once():
    rows = (
        SimpleNamespace(
            surface_id="helper:a",
            path="flowguard/a.py",
            symbol="_normalize",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:shared",
            content_fingerprint="sha256:a",
            roles=(),
            surface_kind="function",
            calls=("leaf",),
        ),
        SimpleNamespace(
            surface_id="helper:b",
            path="flowguard/b.py",
            symbol="_normalize",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:shared",
            content_fingerprint="sha256:b",
            roles=(),
            surface_kind="function",
            calls=("leaf",),
        ),
        SimpleNamespace(
            surface_id="caller:a",
            path="flowguard/caller_a.py",
            symbol="call_a",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:caller-a",
            content_fingerprint="sha256:caller-a",
            roles=(),
            surface_kind="function",
            calls=("helper:a",),
        ),
        SimpleNamespace(
            surface_id="caller:b",
            path="flowguard/caller_b.py",
            symbol="call_b",
            line_start=1,
            line_end=4,
            structure_fingerprint="sha256:caller-b",
            content_fingerprint="sha256:caller-b",
            roles=(),
            surface_kind="function",
            calls=("helper:b",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)
    universe = derive_self_reduction_universe(bundle)
    universe = replace(
        universe,
        members=tuple(
            replace(
                member,
                signal_kinds=("branch_signal", "helper_signal"),
                step_action="unresolved",
                static_operation_count=1,
                analysis_payload_bytes=1,
                cost_source_ref="test:self-reduction-group",
            )
            if member.member_id in {"helper:a", "helper:b"}
            else member
            for member in universe.members
        ),
        universe_fingerprint="",
    )

    candidates, _, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
    )

    matching = tuple(
        row
        for row in candidates
        if set(row.metadata["member_ids"]) == {"helper:a", "helper:b"}
    )
    assert len(matching) == 1
    assert matching[0].metadata["signal"] == "helper_path"


def test_model_and_checker_helpers_receive_independent_validation_retention():
    bundle = _bundle(with_coverage=True)
    surfaces = []
    for surface in bundle.inventory.surfaces:
        name = surface.surface_id.rsplit("-", 1)[-1]
        if name == "a":
            surfaces.append(
                SimpleNamespace(
                    **{
                        **vars(surface),
                        "path": ".flowguard/demo/model.py",
                        "symbol": "_canonical_json",
                        "calls": ("json.dumps",),
                    }
                )
            )
        elif name == "b":
            surfaces.append(
                SimpleNamespace(
                    **{
                        **vars(surface),
                        "path": ".flowguard/demo/run_checks.py",
                        "symbol": "_canonical_json",
                        "calls": ("json.dumps",),
                    }
                )
            )
        else:
            surfaces.append(
                SimpleNamespace(
                    **{
                        **vars(surface),
                        "structure_fingerprint": "sha256:other",
                        "calls": ("other",),
                    }
                )
            )
    bundle.inventory.surfaces = tuple(surfaces)
    universe = derive_self_reduction_universe(bundle)
    selected_ids = {"surface:candidate-a", "surface:candidate-b"}
    universe = replace(
        universe,
        members=tuple(
            replace(
                member,
                signal_kinds=("branch_signal",),
                step_action="unresolved",
                static_operation_count=1,
                analysis_payload_bytes=1,
                cost_source_ref="test:independent-validation",
            )
            if member.member_id in selected_ids
            else member
            for member in universe.members
        ),
        universe_fingerprint="",
    )
    candidates, _, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
    )
    candidate = next(
        row
        for row in candidates
        if set(row.metadata["member_ids"]) == selected_ids
    )
    retains = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(_candidate_binding(candidate),),
    )
    independent = next(
        row for row in retains if row.basis == "independent_validation_roles"
    )
    step = _self_step_assessments((candidate,), (independent,))[0]

    assert independent.candidate_ids == (candidate.candidate_id,)
    assert step.action == "retain"
    assert step.safety_inventory_complete


def test_exact_relation_groups_use_balanced_finite_candidate_batches():
    surface_count = SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT * 2 + 2
    rows = tuple(
        SimpleNamespace(
            surface_id=f"wrapper:{index:02d}",
            path=f"flowguard/wrapper_{index:02d}.py",
            symbol=f"wrap_{index:02d}",
            line_end=20,
            structure_fingerprint="sha256:shared-wrapper-shape",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        )
        for index in range(surface_count)
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(
        row.surface_id for row in rows
    )

    report = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )
    candidates = tuple(
        row
        for row in report.candidates
        if row.metadata["signal"] == "wrapper_or_facade"
    )

    assert len(candidates) == 3
    assert {len(row.metadata["member_ids"]) for row in candidates} == {6}
    assert all(
        row.metadata["relation_group_member_count"] == surface_count
        and row.metadata["batch_count"] == 3
        and row.metadata["batch_member_limit"]
        == SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
        for row in candidates
    )
    assert {
        member_id
        for row in candidates
        for member_id in row.metadata["member_ids"]
    } == {row.surface_id for row in rows}


def test_related_maintenance_named_surfaces_share_one_candidate_and_each_classification():
    rows = (
        SimpleNamespace(
            surface_id="legacy:a",
            path="flowguard/legacy_a.py",
            symbol="legacy_alias",
            line_end=20,
            structure_fingerprint="sha256:legacy-a",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        ),
        SimpleNamespace(
            surface_id="compat:b",
            path="flowguard/compat_b.py",
            symbol="compat_alias",
            line_end=20,
            structure_fingerprint="sha256:legacy-a",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)

    maintenance_candidates = tuple(
        row
        for row in report.candidates
        if row.metadata["signal"] == "fallback_alias_compatibility_path"
    )
    assert len(maintenance_candidates) == 1
    assert {tuple(row.metadata["member_ids"]) for row in maintenance_candidates} == {
        ("compat:b", "legacy:a"),
    }
    assert len(report.compatibility_classifications) == 2
    assert {
        tuple(row.code_node_ids) for row in report.compatibility_classifications
    } == {("legacy:a",), ("compat:b",)}
    assert all(
        len(row.candidate_ids) == 1
        for row in report.compatibility_classifications
    )


def test_maintenance_name_without_a_current_relation_is_classified_but_not_a_candidate():
    rows = (
        SimpleNamespace(
            surface_id="legacy:a",
            path="flowguard/legacy_a.py",
            symbol="legacy_alias",
            line_end=20,
            structure_fingerprint="sha256:legacy-a",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        ),
        SimpleNamespace(
            surface_id="compat:b",
            path="flowguard/compat_b.py",
            symbol="compat_alias",
            line_end=20,
            structure_fingerprint="sha256:compat-b",
            roles=(),
            surface_kind="function",
            calls=("delegate",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)

    assert not tuple(
        row
        for row in report.candidates
        if row.metadata["signal"] == "fallback_alias_compatibility_path"
    )
    assert len(report.compatibility_classifications) == 2
    assert all(
        row.candidate_ids == ()
        and row.classification == "current_contract"
        and row.recommended_action == "keep"
        for row in report.compatibility_classifications
    )


def _proof_for_candidate(
    bundle,
    candidate,
    *,
    pytest_module_prefix="",
):
    temporary = tempfile.TemporaryDirectory()
    _PROOF_TEMP_DIRS.append(temporary)
    root = Path(temporary.name)
    (root / "flowguard").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "flowguard" / "__init__.py").write_text("", encoding="utf-8")
    implementation_source = (
        "def candidate_{name}(value):\n"
        "    if value < 0:\n"
        "        return {{\"input\": value, \"output\": None, \"state\": value, \"effect\": \"none\", \"error\": \"negative\"}}\n"
        "    state = value + 1\n"
        "    return {{\"input\": value, \"output\": state, \"state\": state, \"effect\": \"record\", \"error\": None}}\n"
        "\n"
    )
    for name in ("a", "b", "c"):
        (root / "flowguard" / f"large_{name}.py").write_text(
            implementation_source.format(name=name),
            encoding="utf-8",
        )
    (root / "tests" / "test_self_architecture_reduction.py").write_text(
        pytest_module_prefix
        + "from flowguard.large_a import candidate_a\n"
        "from flowguard.large_b import candidate_b\n"
        "from flowguard.large_c import candidate_c\n"
        "\n"
        "def test_external_equivalence():\n"
        "    result_a = candidate_a(2)\n"
        "    assert result_a[\"input\"] == 2\n"
        "    assert result_a[\"output\"] == 3\n"
        "    assert result_a[\"state\"] == 3\n"
        "    assert result_a[\"effect\"] == \"record\"\n"
        "    assert candidate_a(-1)[\"error\"] == \"negative\"\n"
        "    result_b = candidate_b(2)\n"
        "    assert result_b[\"input\"] == 2\n"
        "    assert result_b[\"output\"] == 3\n"
        "    assert result_b[\"state\"] == 3\n"
        "    assert result_b[\"effect\"] == \"record\"\n"
        "    assert candidate_b(-1)[\"error\"] == \"negative\"\n"
        "    result_c = candidate_c(2)\n"
        "    assert result_c[\"input\"] == 2\n"
        "    assert result_c[\"output\"] == 3\n"
        "    assert result_c[\"state\"] == 3\n"
        "    assert result_c[\"effect\"] == \"record\"\n"
        "    assert candidate_c(-1)[\"error\"] == \"negative\"\n",
        encoding="utf-8",
    )
    universe = derive_self_reduction_universe(bundle, root=root)
    _, candidate_inventory_fingerprint, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
        proof_records=(),
    )
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=bundle.build_input_identity,
        ),
    ):
        proof, = execute_flowguard_self_reduction_proofs(
            str(root),
            expected_candidate_inventory_fingerprint=(
                candidate_inventory_fingerprint
            ),
            selections=(
                SelfReductionProofSelection(
                    candidate_id=candidate.candidate_id,
                    candidate_fingerprint=_candidate_binding(
                        candidate
                    ).fingerprint,
                ),
            ),
        )
    _PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id] = str(root)
    return proof


def test_proof_ready_candidate_becomes_contract_and_safe_unapplied():
    bundle = _bundle(with_coverage=True)
    initial = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    candidate = initial.candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    assert proof.candidate_inventory_fingerprint

    report = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle,
        proof_records=(proof,),
    )

    ready = next(row for row in report.candidates if row.candidate_id == candidate.candidate_id)
    root = _PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id]
    _validate_record_against_candidate(root, bundle, ready, proof)
    stale = SimpleNamespace(**vars(proof))
    stale.inventory_fingerprint = "sha256:stale"
    with pytest.raises(
        ValueError,
        match="proof inventory_fingerprint does not match",
    ):
        _validate_record_against_candidate(root, bundle, ready, stale)
    assert not _proof_record_matches_current_candidate(
        root,
        bundle,
        ready,
        stale,
    )
    assert ready.proof_status == PROOF_SAFE_BY_EQUIVALENCE
    assert ready.metadata["disposition"] == "contract"
    assert report.audit_complete
    assert report.action_authorized_candidate_ids == (
        candidate.candidate_id,
    )
    assert report.safe_unapplied_candidate_ids == (candidate.candidate_id,)
    disposition_by_id = {
        row.member_id: row.disposition for row in report.reduction_universe.members
    }
    assert all(
        disposition_by_id[member_id] == "contract"
        for member_id in candidate.metadata["member_ids"]
    )
    assert all(
        disposition_by_id[signal_id] == "contract"
        for signal_id in candidate.metadata["source_signal_ids"]
    )
    assert report.status == "blocked"
    assert not report.ok
    assert report.audit_accounted
    assert not report.cleanup_release_ready


def test_public_review_auto_discovers_canonical_aggregate_without_record_injection():
    bundle = _bundle(with_coverage=True)
    initial = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )
    candidate = initial.candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = _PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id]

    report = review_flowguard_self_architecture_reduction(
        root=root,
        self_blueprint=bundle,
    )

    ready = next(
        row
        for row in report.candidates
        if row.candidate_id == candidate.candidate_id
    )
    assert ready.proof_status == PROOF_SAFE_BY_EQUIVALENCE
    assert ready.metadata["proof_record_id"] == proof.proof_id


def test_public_review_rejects_caller_injected_proof_records():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _review_flowguard_self_architecture_reduction(
            ".",
            proof_records=(),
        )


def test_proof_batch_reuses_exact_current_aggregate_before_execution():
    bundle = _bundle(with_coverage=True)
    initial = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )
    candidate = initial.candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    universe = derive_self_reduction_universe(bundle, root=root)
    _, inventory_fingerprint, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
        proof_records=(),
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ) as build,
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=bundle.build_input_identity,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction._execute_semantic_proof_owner",
            side_effect=AssertionError("exact-current proof was re-executed"),
        ) as execute,
    ):
        records = execute_flowguard_self_reduction_proofs(
            str(root),
            expected_candidate_inventory_fingerprint=inventory_fingerprint,
            selections=(
                SelfReductionProofSelection(
                    candidate_id=candidate.candidate_id,
                    candidate_fingerprint=_candidate_binding(
                        candidate
                    ).fingerprint,
                ),
            ),
        )

    assert records == (proof,)
    build.assert_called_once_with(root)
    execute.assert_not_called()


def test_proof_batch_rejects_stale_inventory_or_candidate_selection():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    universe = derive_self_reduction_universe(bundle, root=root)
    _, inventory_fingerprint, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
        proof_records=(),
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction._execute_semantic_proof_owner",
            side_effect=AssertionError("stale selection executed"),
        ) as execute,
        pytest.raises(ValueError, match="selection inventory is stale"),
    ):
        execute_flowguard_self_reduction_proofs(
            str(root),
            expected_candidate_inventory_fingerprint="sha256:stale",
            selections=(
                SelfReductionProofSelection(
                    candidate_id=candidate.candidate_id,
                    candidate_fingerprint=_candidate_binding(
                        candidate
                    ).fingerprint,
                ),
            ),
        )
    execute.assert_not_called()

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction._execute_semantic_proof_owner",
            side_effect=AssertionError("stale selection executed"),
        ) as execute,
        pytest.raises(ValueError, match="candidate fingerprint is stale"),
    ):
        execute_flowguard_self_reduction_proofs(
            str(root),
            expected_candidate_inventory_fingerprint=inventory_fingerprint,
            selections=(
                SelfReductionProofSelection(
                    candidate_id=candidate.candidate_id,
                    candidate_fingerprint="sha256:stale",
                ),
            ),
        )
    execute.assert_not_called()


def test_two_exact_current_aggregate_receipts_for_one_candidate_block_review():
    from flowguard.validation_ownership import _content_addressed_receipt_id

    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    receipt_root = _canonical_validation_owner_root(root)
    aggregate = load_evidence_receipt(
        proof.aggregate_receipt_id,
        root,
        output_directory=receipt_root,
    )
    prefix = (
        "receipt:validation-owner:"
        + aggregate.subject_id.removeprefix("validation-owner:")
    )
    duplicate = replace(
        aggregate,
        receipt_id=prefix + ":" + "0" * 32,
        started_at="2000-01-01T00:00:00+00:00",
    )
    duplicate = replace(
        duplicate,
        receipt_id=_content_addressed_receipt_id(prefix, duplicate),
    )
    save_evidence_receipt(
        duplicate,
        root,
        output_directory=receipt_root,
    )

    with pytest.raises(ValueError, match="multiple exact-current"):
        review_flowguard_self_architecture_reduction(
            root=str(root),
            self_blueprint=bundle,
        )


def test_canonical_aggregate_record_reconstruction_rejects_unknown_fields():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    receipt_root = _canonical_validation_owner_root(root)
    aggregate = load_evidence_receipt(
        proof.aggregate_receipt_id,
        root,
        output_directory=receipt_root,
    )
    proof_path = receipt_root / str(aggregate.metadata["proof_relpath"])
    aggregate_payload = json.loads(
        proof_path.read_text(encoding="utf-8")
    )
    aggregate_payload["evidence_context"]["self_reduction_proof"][
        "legacy_alias"
    ] = True
    proof_path.write_text(
        json.dumps(aggregate_payload, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="current exact schema"):
        review_flowguard_self_architecture_reduction(
            root=str(root),
            self_blueprint=bundle,
        )


def test_trivial_assert_true_cannot_authorize_candidate_proof():
    bundle = _bundle(with_coverage=True)
    bundle.test_inventory.nodes[0].assertions[0].target = "True"
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]

    with pytest.raises(ValueError, match="trivial or non-semantic assertion"):
        _proof_for_candidate(bundle, candidate)


def test_skipped_candidate_test_is_not_a_green_proof():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]

    with pytest.raises(ValueError, match="did not reach a clean terminal pass"):
        _proof_for_candidate(
            bundle,
            candidate,
            pytest_module_prefix=(
                "import pytest\npytestmark = pytest.mark.skip(reason='not evidence')\n"
            ),
        )


def _valid_test_execution_result(subject):
    nodeid = subject["pytest_nodeids"][0]
    return {
        "schema_version": subject["result_schema_version"],
        "role": subject["role"],
        "subject_fingerprint": subject["subject_fingerprint"],
        "requested_nodeids": [nodeid],
        "collected_nodeids": [nodeid],
        "deselected_nodeids": [],
        "missing_nodeids": [],
        "unrelated_nodeids": [],
        "outcomes": {nodeid: "passed"},
        "counts": {
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "not_passed": 0,
        },
        "runtime_surface_results": [],
        "oracle_results": [],
        "pytest_exit_code": 0,
        "pytest_stdout_fingerprint": "sha256:pytest-stdout",
        "pytest_stderr_fingerprint": "sha256:pytest-stderr",
        "ok": True,
    }


@pytest.mark.parametrize(
    "mutation",
    (
        "deselected",
        "missing",
        "unrelated",
        "skipped",
        "xfailed",
        "xpassed",
    ),
)
def test_nonpass_collection_and_outcome_states_cannot_be_relabelled_green(mutation):
    subject = _execution_subject(
        role="test",
        pytest_nodeids=("tests/test_candidate.py::test_candidate",),
    )
    result = _valid_test_execution_result(subject)
    nodeid = subject["pytest_nodeids"][0]
    if mutation in {"deselected", "missing", "unrelated"}:
        result[f"{mutation}_nodeids"] = [nodeid]
    else:
        result["outcomes"][nodeid] = mutation
        result["counts"]["passed"] = 0
        result["counts"][mutation] = 1

    with pytest.raises(ValueError):
        _validate_semantic_execution_result(result, subject)


def test_test_and_parity_owners_both_execute_the_exact_pytest_runner():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    binding = candidate.metadata
    proof_payload = {
        "proof_id": "proof:command-shape",
        "subject_revision": bundle.inventory.boundary.subject_revision,
        "inventory_fingerprint": bundle.inventory.inventory_fingerprint,
        "test_inventory_fingerprint": bundle.test_inventory.inventory_fingerprint,
        "candidate_id": candidate.candidate_id,
        "candidate_signal": binding["signal"],
        "candidate_fingerprint": _candidate_binding(candidate).fingerprint,
        "candidate_inventory_fingerprint": candidate.inventory_revision,
        "member_ids": list(binding["member_ids"]),
        "source_signal_ids": list(binding["source_signal_ids"]),
        "caller_consumer_ids": list(binding["caller_ids"]),
        "public_entrypoint_ids": list(binding["public_entrypoint_ids"]),
        "proof_status": PROOF_SAFE_BY_EQUIVALENCE,
        "observable_contract_fingerprint": binding[
            "observable_contract_fingerprint"
        ],
        "test_evidence_ids": list(
            _resolved_candidate_observable_contract(bundle, candidate)[
                "test_node_ids"
            ]
        ),
        "coverage_ids": list(
            _resolved_candidate_observable_contract(bundle, candidate)[
                "coverage_ids"
            ]
        ),
        "parity_results": {
            obligation_id: "pass"
            for obligation_id in SELF_REDUCTION_PARITY_OBLIGATION_IDS
        },
        "public_facade_binding": None,
    }

    test_contract, parity_contract, _aggregate = _proof_contracts(
        bundle, candidate, proof_payload
    )
    assert test_contract.command[2] == parity_contract.command[2]
    assert "pytest.main" in test_contract.command[2]
    assert "metadata" not in parity_contract.command[2].lower()
    assert test_contract.command[3] != parity_contract.command[3]


def test_parity_bindings_cover_each_public_entrypoint_dimension():
    bundle = _bundle(with_coverage=True)
    public = SimpleNamespace(
        surface_id="surface:public-a",
        path="flowguard/public_a.py",
        symbol="public_a",
        line_start=1,
        line_end=3,
        structure_fingerprint="sha256:public-a-structure",
        content_fingerprint="sha256:public-a-content",
        roles=("entrypoint",),
        surface_kind="entrypoint",
        calls=("candidate_a",),
    )
    bundle.inventory.surfaces = (*bundle.inventory.surfaces, public)
    bundle.inventory.required_surface_ids = (
        *bundle.inventory.required_surface_ids,
        public.surface_id,
    )
    bundle.behavior_report.supporting_relations = (
        SimpleNamespace(
            supporting_surface_id=public.surface_id,
            behavior_block_id="behavior:candidate-a",
        ),
    )
    candidate = SimpleNamespace(
        metadata={"member_ids": ("surface:candidate-a",)},
        affected_public_entrypoints=(public.surface_id,),
    )
    coverage_ids = tuple(
        row.coverage_id
        for row in bundle.behavior_report.coverage_edges
        if row.implementation_surface_id == "surface:candidate-a"
    )

    bindings = _candidate_semantic_bindings(
        bundle,
        candidate,
        test_ids=("test:external-equivalence",),
        coverage_ids=coverage_ids,
    )

    dimensions_by_member = {
        member_id: {
            row["dimension"] for row in bindings if row["member_id"] == member_id
        }
        for member_id in ("surface:candidate-a", public.surface_id)
    }
    assert dimensions_by_member == {
        "surface:candidate-a": {"input", "output", "state", "effect", "error"},
        public.surface_id: {"input", "output", "state", "effect", "error"},
    }


def test_globally_known_but_candidate_unrelated_test_is_rejected():
    bundle = _bundle(with_coverage=True)
    bundle.test_inventory.nodes = (
        *bundle.test_inventory.nodes,
        SimpleNamespace(
            node_id="test:unrelated",
            path="tests/test_self_architecture_reduction.py",
            pytest_nodeid=(
                "tests/test_self_architecture_reduction.py::test_unrelated"
            ),
        ),
    )
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    with pytest.raises(ValueError, match="canonical semantic subject"):
        replace(
            proof,
            test_evidence_ids=("test:unrelated",),
        )


def test_proof_record_cannot_carry_caller_supplied_verification():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        replace(proof, receipt_verification=SimpleNamespace(ok=True))


def test_proof_execution_rejects_caller_supplied_facade_authority_fields():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        execute_flowguard_self_reduction_proofs(
            ".",
            expected_candidate_inventory_fingerprint="sha256:inventory",
            selections=(
                SelfReductionProofSelection(
                    candidate_id="candidate:facade",
                    candidate_fingerprint="sha256:candidate",
                ),
            ),
            public_facade_delegation_evidence_id="caller-asserted",
        )


def _facade_authority_fixture(tmp_path, *, code_contract_id="contract:facade-owner"):
    ledger_path = (
        tmp_path / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
    )
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("{}\n", encoding="utf-8")
    public = SimpleNamespace(
        surface_id="surface:facade",
        path="pkg/api.py",
        symbol="pkg.api.facade",
        structure_fingerprint="sha256:facade-structure",
        content_fingerprint="sha256:facade-content",
        roles=("entrypoint",),
        surface_kind="entrypoint",
    )
    owner = SimpleNamespace(
        surface_id="surface:owner",
        path="pkg/owner.py",
        symbol="pkg.owner.run",
        structure_fingerprint="sha256:owner-structure",
        content_fingerprint="sha256:owner-content",
        roles=("behavior",),
        surface_kind="function",
    )
    relation = SimpleNamespace(
        supporting_surface_id=public.surface_id,
        behavior_block_id="behavior:owner",
        relation_kind="delegates",
        evidence_id="supporting-edge:facade:owner",
        evidence_fingerprint=public.structure_fingerprint,
        to_dict=lambda: {
            "supporting_surface_id": public.surface_id,
            "behavior_block_id": "behavior:owner",
            "relation_kind": "delegates",
            "evidence_id": "supporting-edge:facade:owner",
            "evidence_fingerprint": public.structure_fingerprint,
        },
    )
    owner_contract = SimpleNamespace(
        implementation_surface_id=owner.surface_id,
        behavior_block_id="behavior:owner",
        owner_contract_id="contract:facade-owner",
        owner_id="owner:facade",
        model_element_id="model:facade",
        accepted=True,
        source_fingerprint=owner.content_fingerprint,
        to_dict=lambda: {
            "implementation_surface_id": owner.surface_id,
            "behavior_block_id": "behavior:owner",
            "owner_contract_id": "contract:facade-owner",
            "accepted": True,
            "source_fingerprint": owner.content_fingerprint,
        },
    )
    bundle = SimpleNamespace(
        inventory=SimpleNamespace(
            boundary=SimpleNamespace(subject_revision="sha256:facade-subject"),
            surfaces=(public, owner),
            required_surface_ids=(public.surface_id, owner.surface_id),
            inventory_fingerprint="sha256:facade-inventory",
        ),
        behavior_report=SimpleNamespace(
            contracts=(owner_contract,),
            supporting_relations=(relation,),
            fingerprint="sha256:facade-behavior",
        ),
    )
    source = SimpleNamespace(
        surface_id="ledger-surface:facade",
        source_ref="pkg/api.py#pkg.api.facade",
        native_artifact_id=public.surface_id,
        in_scope=True,
        freshness_state="current",
        coverage_disposition="modeled",
        source_authority_role="normative",
        declared_semantics_fingerprint="sha256:facade-semantics",
        delegates_to_primary_path=True,
        primary_path_id="path:facade-primary",
        commitment_ids=("commitment:facade",),
        business_intent_ids=("intent:facade",),
        content_fingerprint="sha256:ledger-facade-content",
        discovery_evidence_ids=("discovery:facade",),
        inventory_revision="revision:facade",
        to_dict=lambda: {
            "surface_id": "ledger-surface:facade",
            "native_artifact_id": public.surface_id,
            "primary_path_id": "path:facade-primary",
        },
    )
    evidence = SimpleNamespace(
        code_contract_ids=(code_contract_id,),
        has_current_pass=lambda: True,
        has_required_links=lambda: True,
    )
    path_authority = SimpleNamespace(
        path_sensitive=True,
        business_intent_id="intent:facade",
        behavior_commitment_id="commitment:facade",
        primary_path_id="path:facade-primary",
        ppa_passed=lambda: True,
    )
    commitment = SimpleNamespace(
        commitment_id="commitment:facade",
        business_intent_id="intent:facade",
        source_surface_ids=(source.surface_id,),
        in_scope=True,
        replacement_state="active",
        model_sync_state="owner_model_current",
        surface_delegation_only=False,
        evidence=evidence,
        path_authority=path_authority,
        active_external_commitment=lambda: True,
        to_dict=lambda: {
            "commitment_id": "commitment:facade",
            "business_intent_id": "intent:facade",
            "code_contract_ids": [code_contract_id],
            "primary_path_id": "path:facade-primary",
        },
    )
    ledger = SimpleNamespace(
        source_inventory_revision="revision:facade",
        source_surfaces=(source,),
        commitments=(commitment,),
    )
    candidate = SimpleNamespace(
        candidate_id="candidate:facade",
        affected_public_entrypoints=(public.surface_id,),
    )
    return bundle, candidate, ledger


def _external_commitment_fixture(
    tmp_path,
    *,
    code_contract_ids=None,
    commitment_test_evidence_ids=("test:current-owner",),
    binding_test_evidence_ids=("test:current-owner",),
):
    ledger_path = (
        tmp_path / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
    )
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("{}\n", encoding="utf-8")
    model_path = ".flowguard/current_owner/model.py"
    model_element_id = f"model-obligation:{model_path}"
    owner_contract_id = f"owner-contract:{model_path}"
    implementation_surface_id = "surface:flowguard.current_owner.handle"
    binding_id = f"binding:{model_element_id}:{implementation_surface_id}"
    surface_code_contract_id = "code-contract:" + binding_id
    evidence = SimpleNamespace(
        model_obligation_ids=("obligation:current-owner",),
        code_contract_ids=(
            tuple(code_contract_ids)
            if code_contract_ids is not None
            else (
                "contract:product-promise",
                owner_contract_id,
                surface_code_contract_id,
            )
        ),
        test_evidence_ids=tuple(commitment_test_evidence_ids),
        has_current_pass=lambda: True,
        has_required_links=lambda: True,
    )
    commitment = SimpleNamespace(
        commitment_id="commitment:current-owner",
        primary_owner_model_id=model_path,
        model_sync_state="owner_model_current",
        evidence=evidence,
        active_external_commitment=lambda: True,
        exact_external_semantics_key=lambda: (
            "product_runtime",
            "human",
            "flowguard user",
            "invoke current owner",
            ("current model is available",),
            "current result",
            "declared failure remains visible",
            ("current state",),
            ("current evidence",),
        ),
    )
    ledger = SimpleNamespace(commitments=(commitment,))
    owner_contract = SimpleNamespace(
        accepted=True,
        model_element_id=model_element_id,
        owner_contract_id=owner_contract_id,
    )
    implementation_binding = SimpleNamespace(
        binding_id=binding_id,
        model_element_id=model_element_id,
        implementation_surface_id=implementation_surface_id,
        owner_contract_id=owner_contract_id,
        test_evidence_ids=tuple(binding_test_evidence_ids),
    )
    bundle = SimpleNamespace(
        behavior_report=SimpleNamespace(contracts=(owner_contract,)),
        binding_report=SimpleNamespace(bindings=(implementation_binding,)),
    )
    review = SimpleNamespace(
        ok=True,
        covered_commitment_ids=(commitment.commitment_id,),
        to_dict=lambda: {
            "ok": True,
            "covered_commitment_ids": [commitment.commitment_id],
        },
    )
    return bundle, ledger, review, model_element_id, owner_contract_id


def test_external_commitments_are_reviewed_once_and_bound_to_current_owner(tmp_path):
    bundle, ledger, review, model_element_id, owner_contract_id = (
        _external_commitment_fixture(tmp_path)
    )
    load_mock = mock.Mock(return_value=ledger)
    review_mock = mock.Mock(return_value=review)
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            load_mock,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            review_mock,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger-current",
        ),
    ):
        bindings = _derive_current_external_commitment_bindings(tmp_path, bundle)

    load_mock.assert_called_once()
    review_mock.assert_called_once_with(ledger, project_root=tmp_path.resolve())
    row = bindings[model_element_id][0]
    assert row["commitment_id"] == "commitment:current-owner"
    assert row["owner_contract_id"] == owner_contract_id
    assert row["implementation_surface_id"] == (
        "surface:flowguard.current_owner.handle"
    )
    assert row["binding_id"].startswith("binding:model-obligation:")
    assert owner_contract_id in row["code_contract_ids"]
    assert "code-contract:" + row["binding_id"] in row["code_contract_ids"]
    assert row["test_evidence_ids"] == ("test:current-owner",)
    assert row["binding_fingerprint"].startswith("sha256:")


def test_external_commitment_without_exact_owner_contract_blocks(tmp_path):
    bundle, ledger, review, _, _ = _external_commitment_fixture(
        tmp_path,
        code_contract_ids=("contract:product-promise",),
    )
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=review,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger-current",
        ),
        pytest.raises(ValueError, match="exact current model/code/test binding"),
    ):
        _derive_current_external_commitment_bindings(tmp_path, bundle)


def test_external_commitment_without_exact_surface_contract_grants_no_binding(
    tmp_path,
):
    bundle, ledger, review, _, owner_contract_id = _external_commitment_fixture(
        tmp_path,
        code_contract_ids=(
            "contract:product-promise",
            "owner-contract:.flowguard/current_owner/model.py",
        ),
    )
    assert owner_contract_id == "owner-contract:.flowguard/current_owner/model.py"
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=review,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger-current",
        ),
    ):
        bindings = _derive_current_external_commitment_bindings(tmp_path, bundle)
    assert bindings == {}


def test_external_commitment_with_wrong_surface_tests_blocks(tmp_path):
    bundle, ledger, review, _, _ = _external_commitment_fixture(
        tmp_path,
        commitment_test_evidence_ids=("test:commitment",),
        binding_test_evidence_ids=("test:surface",),
    )
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=review,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger-current",
        ),
        pytest.raises(ValueError, match="stale or foreign implementation-surface"),
    ):
        _derive_current_external_commitment_bindings(tmp_path, bundle)


def test_public_facade_binding_is_derived_from_exact_current_authorities(tmp_path):
    bundle, candidate, ledger = _facade_authority_fixture(tmp_path)
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=SimpleNamespace(ok=True),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger",
        ),
    ):
        binding = _derive_public_facade_binding(tmp_path, bundle, candidate)

    assert binding["business_intent_id"] == "intent:facade"
    assert binding["behavior_commitment_id"] == "commitment:facade"
    assert binding["owner_code_contract_id"] == "contract:facade-owner"
    assert binding["delegation_only"] is True
    assert binding["independent_business_authority"] is False
    assert binding["public_facade_delegation_evidence_id"].startswith(
        "public-facade-delegation:"
    )


def test_public_facade_binding_rejects_unaligned_bcl_code_contract(tmp_path):
    bundle, candidate, ledger = _facade_authority_fixture(
        tmp_path,
        code_contract_id="contract:another-owner",
    )
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=SimpleNamespace(ok=True),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger",
        ),
        pytest.raises(ValueError, match="model/code/path authority"),
    ):
        _derive_public_facade_binding(tmp_path, bundle, candidate)


def test_public_facade_binding_rejects_file_only_source_ref(tmp_path):
    bundle, candidate, ledger = _facade_authority_fixture(tmp_path)
    ledger.source_surfaces[0].native_artifact_id = ""
    ledger.source_surfaces[0].source_ref = "pkg/api.py"
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=SimpleNamespace(ok=True),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger",
        ),
        pytest.raises(ValueError, match="unique current delegated"),
    ):
        _derive_public_facade_binding(tmp_path, bundle, candidate)


def test_public_facade_binding_rejects_near_match_source_anchor(tmp_path):
    bundle, candidate, ledger = _facade_authority_fixture(tmp_path)
    ledger.source_surfaces[0].native_artifact_id = ""
    ledger.source_surfaces[0].source_ref = "pkg/api.py#pkg.api.facade_extra"
    with (
        mock.patch(
            "flowguard.self_architecture_reduction.load_behavior_commitment_ledger",
            return_value=ledger,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_behavior_commitment_ledger",
            return_value=SimpleNamespace(ok=True),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.behavior_commitment_ledger_fingerprint",
            return_value="sha256:ledger",
        ),
        pytest.raises(ValueError, match="unique current delegated"),
    ):
        _derive_public_facade_binding(tmp_path, bundle, candidate)


def test_opaque_ids_and_bare_booleans_cannot_form_reduction_proof():
    bundle = _same_commitment_candidate_bundle()
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        SelfReductionProofRecord(
            proof_id="proof:opaque",
            proof_owner_id="caller-asserted-owner",
            subject_revision=bundle.inventory.inventory_fingerprint,
            candidate_signal=candidate.metadata["signal"],
            member_ids=tuple(candidate.metadata["member_ids"]),
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
            observable_contract_fingerprint=candidate.metadata[
                "observable_contract_fingerprint"
            ],
            evidence_refs=("receipt:invented",),
            test_evidence_ids=("test:invented",),
            current=True,
            caller_consumer_parity=True,
            state_parity=True,
            side_effect_parity=True,
            error_parity=True,
        )


def test_proof_identity_relabel_cannot_reuse_another_candidate_execution():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    with pytest.raises(ValueError, match="canonical semantic subject"):
        replace(proof, proof_id="proof:relabeled")


def test_caller_has_no_public_pass_receipt_saver():
    import flowguard.validation_ownership as validation_ownership

    assert not hasattr(validation_ownership, "save_owner_receipt")


def test_missing_parity_child_blocks_candidate_proof():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    receipt_root = _canonical_validation_owner_root(root)
    aggregate = load_evidence_receipt(
        proof.aggregate_receipt_id,
        root,
        output_directory=receipt_root,
    )
    parity = next(
        requirement
        for requirement in aggregate.required_child_receipts
        if "self-reduction-parity-" in requirement.subject_id
    )
    receipt_path(
        parity.receipt_id,
        root,
        output_directory=receipt_root,
    ).unlink()

    with pytest.raises(ValueError, match="canonical validation-owner receipt is missing"):
        review_flowguard_self_architecture_reduction(
            self_blueprint=bundle,
            proof_records=(proof,),
        )


def test_candidate_without_all_parity_dimensions_cannot_produce_proof():
    bundle = _bundle(with_coverage=True)
    bundle.behavior_report.coverage_edges = tuple(
        row
        for row in bundle.behavior_report.coverage_edges
        if row.coverage_id != "coverage:a:error"
    )
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]

    with pytest.raises(ValueError, match="input/output/state/effect/error"):
        _proof_for_candidate(bundle, candidate)


def test_conflicting_ready_actions_on_one_member_are_blocked_without_primary():
    base = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(with_coverage=True)
    ).candidates[0]
    first = replace(
        base,
        candidate_id="candidate:collapse",
        candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
        target_action=TARGET_ACTION_COLLAPSE,
        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
    )
    second = replace(
        base,
        candidate_id="candidate:merge",
        candidate_type=CANDIDATE_MERGE_MODULES,
        target_action=TARGET_ACTION_MERGE,
        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
    )

    blocked = _block_conflicting_candidate_actions((first, second))

    assert all(row.proof_status == "risky_keep" for row in blocked)
    assert all(row.target_action == "manual_review" for row in blocked)
    assert all(
        row.metadata["candidate_action_conflict_ids"]
        == ("candidate:collapse", "candidate:merge")
        for row in blocked
    )
    assert all(
        "unique_primary_candidate_action"
        in row.metadata["missing_proof_obligations"]
        for row in blocked
    )


def test_conflicting_candidate_actions_scan_the_candidate_tuple_constant_times():
    base = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(with_coverage=True)
    ).candidates[0]

    class CountedCandidates(tuple):
        def __new__(cls, values):
            value = super().__new__(cls, values)
            value.iteration_count = 0
            return value

        def __iter__(self):
            self.iteration_count += 1
            return super().__iter__()

    candidates = CountedCandidates(
        replace(
            base,
            candidate_id=f"candidate:{index:04d}",
            target_action=(
                TARGET_ACTION_COLLAPSE if index % 2 else TARGET_ACTION_MERGE
            ),
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
        )
        for index in range(200)
    )

    blocked = _block_conflicting_candidate_actions(candidates)

    assert len(blocked) == 200
    assert candidates.iteration_count == 3


@pytest.mark.parametrize(
    "receipt_changes",
    (
        {
            "result_status": "blocked",
            "exit_code": 1,
            "blockers": ("parity_failed",),
        },
        {"skipped_checks": ("state_parity",)},
    ),
)
def test_blocked_or_skipped_aggregate_cannot_upgrade_candidate(receipt_changes):
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    receipt_root = _canonical_validation_owner_root(root)
    aggregate = load_evidence_receipt(
        proof.aggregate_receipt_id,
        root,
        output_directory=receipt_root,
    )
    mutated = replace(aggregate, **receipt_changes)
    path = receipt_path(
        aggregate.receipt_id,
        root,
        output_directory=receipt_root,
    )
    path.write_text(canonical_receipt_json(mutated) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="content address mismatch"):
        review_flowguard_self_architecture_reduction(
            self_blueprint=bundle,
            proof_records=(proof,),
        )


def test_stale_candidate_identity_cannot_reuse_current_aggregate():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    bundle.inventory.inventory_fingerprint = fingerprint_value(
        "new-current-inventory"
    )
    universe = derive_self_reduction_universe(bundle, root=root)
    candidates, _, _, _ = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
        proof_records=(),
    )

    verified, historical = _discover_current_self_reduction_proofs(
        root,
        bundle,
        candidates,
    )

    assert verified == ()
    assert historical == (proof.aggregate_receipt_id,)


def test_public_review_has_no_caller_selectable_receipt_store():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _review_flowguard_self_architecture_reduction(
            ".",
            receipt_root="arbitrary-receipts",
        )


def test_canonical_proof_store_rejects_reparse_or_junction_component(tmp_path):
    canonical = tmp_path / ".flowguard" / "evidence" / "validation-owners"
    canonical.mkdir(parents=True)

    with (
        mock.patch(
            "flowguard.self_architecture_reduction._path_is_reparse",
            side_effect=lambda path: Path(path) == canonical,
        ),
        pytest.raises(ValueError, match="symlink, junction, or reparse point"),
    ):
        _canonical_validation_owner_root(tmp_path)


def test_review_verifies_semantic_proof_once_then_rechecks_owner_inputs():
    bundle = _bundle(with_coverage=True)
    bundle.build_input_identity = _build_input_identity()
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    call_count = 0

    def verify_then_mutate(*args, **kwargs):
        nonlocal call_count
        result = _verify_proof_records(*args, **kwargs)
        call_count += 1
        if call_count == 1:
            (root / "flowguard" / "large_a.py").write_text(
                "def candidate_a(value):\n    return value\n",
                encoding="utf-8",
            )
        return result

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=_build_input_identity(),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction._verify_proof_records",
            side_effect=verify_then_mutate,
        ) as semantic_verify,
        mock.patch(
            "flowguard.self_architecture_reduction._recheck_verified_proof_currentness",
            wraps=_recheck_verified_proof_currentness,
        ) as currentness_recheck,
        pytest.raises(ValueError, match="owner input identity changed before"),
    ):
        _review_flowguard_self_architecture_reduction(str(root))

    assert call_count == 1
    assert semantic_verify.call_count == 1
    assert currentness_recheck.call_count == 1


def test_review_rechecks_proof_artifact_identity_without_semantic_reverification():
    bundle = _bundle(with_coverage=True)
    bundle.build_input_identity = _build_input_identity()
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)
    root = Path(_PROOF_ROOT_BY_RECEIPT_ID[proof.aggregate_receipt_id])
    receipt_root = _canonical_validation_owner_root(root)
    aggregate = load_evidence_receipt(
        proof.aggregate_receipt_id,
        root,
        output_directory=receipt_root,
    )
    proof_path = receipt_root / str(aggregate.metadata["proof_relpath"])

    def verify_then_mutate(*args, **kwargs):
        result = _verify_proof_records(*args, **kwargs)
        proof_path.write_text(
            proof_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        return result

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=_build_input_identity(),
        ),
        mock.patch(
            "flowguard.self_architecture_reduction._verify_proof_records",
            side_effect=verify_then_mutate,
        ) as semantic_verify,
        pytest.raises(ValueError, match="proof artifact identity changed before"),
    ):
        _review_flowguard_self_architecture_reduction(str(root))

    assert semantic_verify.call_count == 1


def test_review_recomputes_build_inputs_and_blocks_toctou_change():
    initial = _bundle()
    initial_inputs = _build_input_identity("initial")
    changed_inputs = _build_input_identity("changed")
    initial.build_input_identity = initial_inputs

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=initial,
        ) as build,
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=changed_inputs,
        ) as capture,
        pytest.raises(ValueError, match="build inputs changed before"),
    ):
        _review_flowguard_self_architecture_reduction(".")

    assert build.call_count == 1
    assert capture.call_count == 1


def test_review_derives_denominator_once_when_build_inputs_remain_exact():
    bundle = _bundle()
    initial_universe = derive_self_reduction_universe(bundle)
    current_inputs = _build_input_identity()
    bundle.build_input_identity = current_inputs

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.derive_self_reduction_universe",
            return_value=initial_universe,
        ) as derive,
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=current_inputs,
        ) as capture,
    ):
        report = _review_flowguard_self_architecture_reduction(".")

    assert report.reduction_universe_fingerprint
    assert derive.call_count == 1
    assert capture.call_count == 1


def test_read_only_review_never_executes_candidate_proof():
    bundle = _bundle()
    with mock.patch(
        "flowguard.self_architecture_reduction._execute_semantic_proof_owner",
        side_effect=AssertionError("review executed proof"),
    ) as execute:
        review_flowguard_self_architecture_reduction(self_blueprint=bundle)

    execute.assert_not_called()


def test_missing_typed_proof_registry_row_is_rejected():
    bundle = _bundle()
    with pytest.raises(TypeError, match="SelfReductionProofRecord"):
        review_flowguard_self_architecture_reduction(
            self_blueprint=bundle,
            proof_records=(SimpleNamespace(proof_id="proof:opaque"),),
        )


def test_test_and_parity_registries_are_exact_receipt_bound_subjects():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)

    with pytest.raises(ValueError, match="canonical semantic subject"):
        replace(
            proof,
            test_evidence_ids=("test:relabeled",),
        )
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        replace(proof, parity_obligation_ids=("caller_consumer_parity",))


def test_duplicate_leaf_receipt_registry_is_rejected_before_candidate_upgrade():
    bundle = _bundle(with_coverage=True)
    candidate = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    ).candidates[0]
    proof = _proof_for_candidate(bundle, candidate)

    with pytest.raises(ValueError, match="duplicate proof ids"):
        review_flowguard_self_architecture_reduction(
            self_blueprint=bundle,
            proof_records=(proof, proof),
        )


def test_accounted_source_gap_blocks_audit_and_cleanup_readiness():
    bundle = _bundle()
    finding = SimpleNamespace(
        code="discovery_adapter_missing",
        message="one required adapter is unavailable",
        severity="blocker",
        path="flowguard/unobserved.py",
        surface_id="",
    )
    bundle.inventory.findings = (finding,)
    bundle.implementation_inventory_audit = SimpleNamespace(
        ok=False,
        status="blocked",
        inventory_fingerprint=bundle.inventory.inventory_fingerprint,
        findings=(finding,),
        fingerprint="sha256:inventory-audit-blocked",
    )

    report = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )

    assert report.audit_accounted
    assert not report.audit_complete
    assert report.action_authorized_candidate_ids == ()
    assert not report.cleanup_release_ready
    assert not report.ok
    assert report.status == "blocked"
    assert report.unresolved_member_ids
    assert set(report.unresolved_member_ids) == {
        row.member_id
        for row in report.reduction_universe.members
        if row.disposition == "unresolved"
    }


def test_composed_cli_rejects_accounted_but_not_release_ready_cleanup():
    bundle = _bundle()
    finding = SimpleNamespace(
        code="dynamic_surface_unresolved",
        message="one dynamic surface remains unresolved",
        severity="blocker",
        path="flowguard/dynamic.py",
        surface_id="",
    )
    bundle.inventory.findings = (finding,)
    bundle.implementation_inventory_audit = SimpleNamespace(
        ok=False,
        status="blocked",
        inventory_fingerprint=bundle.inventory.inventory_fingerprint,
        findings=(finding,),
        fingerprint="sha256:inventory-audit-dynamic-gap",
    )
    reduction = review_flowguard_self_architecture_reduction(
        self_blueprint=bundle
    )
    assert reduction.audit_accounted
    assert not reduction.cleanup_release_ready
    bundle.to_dict = mock.Mock(
        return_value={"ok": True, "fingerprint": "sha256:blueprint"}
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_architecture_reduction_review",
            return_value=(bundle, reduction),
        ),
        mock.patch("flowguard.__main__._emit_payload"),
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 1


def test_release_gate_rejects_complete_audit_with_unresolved_cleanup():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
    )
    bundle.to_dict = mock.Mock(return_value={"ok": True})
    reduction = SimpleNamespace(
        ok=True,
        cleanup_release_ready=False,
        to_dict=mock.Mock(
            return_value={
                "ok": True,
                "cleanup_release_ready": False,
                "review_fingerprint": "sha256:reduction",
            }
        ),
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
        require_cleanup_release_ready=True,
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_architecture_reduction_review",
            return_value=(bundle, reduction),
        ),
        mock.patch("flowguard.__main__._emit_payload") as emit,
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 1
    emitted = emit.call_args.args[0]
    assert emitted["cleanup_release_ready_required"] is True
    assert emitted["cleanup_release_ready_gate"] == "blocked"


def test_self_reduction_reverse_call_index_preserves_exact_short_and_qualified_callers():
    rows = (
        SimpleNamespace(
            surface_id="helper:a",
            path="flowguard/a.py",
            symbol="pkg.a._normalize",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="helper:b",
            path="flowguard/b.py",
            symbol="pkg.b._normalize",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="caller:short",
            path="flowguard/short.py",
            symbol="call_short",
            line_end=20,
            structure_fingerprint="sha256:caller-short",
            roles=(),
            surface_kind="function",
            calls=("_normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:qualified",
            path="flowguard/qualified.py",
            symbol="call_qualified",
            line_end=20,
            structure_fingerprint="sha256:caller-qualified",
            roles=(),
            surface_kind="function",
            calls=("pkg.a._normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:qualified-b",
            path="flowguard/qualified_b.py",
            symbol="call_qualified_b",
            line_end=20,
            structure_fingerprint="sha256:caller-qualified-b",
            roles=(),
            surface_kind="function",
            calls=("pkg.b._normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:unrelated",
            path="flowguard/unrelated.py",
            symbol="call_unrelated",
            line_end=20,
            structure_fingerprint="sha256:caller-unrelated",
            roles=(),
            surface_kind="function",
            calls=("normalize_other",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    helper_candidate = next(
        row for row in report.candidates if row.metadata["signal"] == "helper_path"
    )

    assert helper_candidate.metadata["caller_ids"] == (
        "caller:qualified",
        "caller:qualified-b",
    )
    assert helper_candidate.metadata["caller_resolution_gap_ids"]
    assert "canonical_caller_resolution" in helper_candidate.metadata[
        "missing_proof_obligations"
    ]
    assert report.audit_accounted
    assert not report.candidate_review_complete
    assert not report.cleanup_release_ready


def test_reverse_call_alias_index_reads_each_surface_call_list_once():
    class CountedSurface:
        def __init__(self, index: int) -> None:
            self.surface_id = f"surface:{index:04d}"
            self.call_reads = 0
            self._calls = (f"pkg.call_{index % 7}", "shared")

        @property
        def calls(self):
            self.call_reads += 1
            return self._calls

    surfaces = tuple(CountedSurface(index) for index in range(500))

    index = _reverse_call_alias_index(surfaces)

    assert all(row.call_reads == 1 for row in surfaces)
    assert index.callers_by_surface_id == {}
    assert index.gap_ids_by_surface_id == {}
    assert index.gaps == ()


def test_receiver_qualified_short_call_becomes_an_explicit_resolution_gap():
    target = SimpleNamespace(
        surface_id="helper:target",
        symbol="Example._normalize",
        calls=(),
    )
    caller = SimpleNamespace(
        surface_id="caller:self",
        symbol="Example.run",
        calls=("self._normalize",),
    )

    index = _reverse_call_alias_index((target, caller))

    assert index.callers_by_surface_id == {}
    assert index.gap_ids_by_surface_id["helper:target"]
    assert index.gaps[0]["raw_call"] == "self._normalize"
    assert index.gaps[0]["caller_surface_ids"] == ["caller:self"]
    assert index.gaps[0]["candidate_surface_ids"] == ["helper:target"]


def test_reverse_call_alias_index_aggregates_shared_ambiguity_without_cartesian_rows():
    targets = (
        SimpleNamespace(surface_id="target:a", symbol="pkg.a.shared", calls=()),
        SimpleNamespace(surface_id="target:b", symbol="pkg.b.shared", calls=()),
    )
    callers = tuple(
        SimpleNamespace(
            surface_id=f"caller:{index:04d}",
            symbol=f"caller_{index:04d}",
            calls=("shared",),
        )
        for index in range(200)
    )

    index = _reverse_call_alias_index((*targets, *callers))

    assert len(index.gaps) == 1
    gap = index.gaps[0]
    assert gap["raw_call"] == "shared"
    assert gap["candidate_surface_ids"] == ["target:a", "target:b"]
    assert gap["caller_surface_ids"] == [
        f"caller:{item:04d}" for item in range(200)
    ]
    assert index.gap_ids_by_surface_id["target:a"] == (gap["gap_id"],)
    assert index.gap_ids_by_surface_id["target:b"] == (gap["gap_id"],)


def test_self_reduction_indexes_signal_and_proof_sources_once_at_scale():
    class CountedRow:
        def __init__(self, **values):
            self._values = values
            self.reads = {name: 0 for name in values}

        def __getattr__(self, name):
            if name not in self._values:
                raise AttributeError(name)
            self.reads[name] += 1
            return self._values[name]

    surface_count = 120
    surfaces = tuple(
        SimpleNamespace(
            surface_id=f"surface:legacy:{index:04d}",
            path=f"flowguard/path_{index:04d}.py",
            symbol=f"legacy_path_{index:04d}",
            line_start=1,
            line_end=20,
            structure_fingerprint=f"sha256:shape:{index // 2:04d}",
            content_fingerprint=f"sha256:content:{index:04d}",
            roles=(),
            surface_kind="function",
            calls=(f"delegate_{index // 2:04d}",),
            state_reads=(),
            state_writes=(),
            side_effect_candidates=(),
            raised_errors=(),
        )
        for index in range(surface_count)
    )
    contracts = tuple(
        CountedRow(
            implementation_surface_id=surface.surface_id,
            behavior_block_id=f"behavior:direct:{index:04d}",
            model_element_id=f"model:{index:04d}",
            owner_id=f"owner:{index:04d}",
        )
        for index, surface in enumerate(surfaces)
    )
    supporting_relations = tuple(
        CountedRow(
            supporting_surface_id=surface.surface_id,
            behavior_block_id=f"behavior:supporting:{index:04d}",
        )
        for index, surface in enumerate(surfaces)
    )
    coverage_edges = tuple(
        row
        for index, surface in enumerate(surfaces)
        for row in (
            CountedRow(
                implementation_surface_id=surface.surface_id,
                behavior_block_id=f"behavior:direct:{index:04d}",
                coverage_id=f"coverage:direct:{index:04d}",
                test_node_id=f"test:direct:{index:04d}",
                covered_dimensions=("input",),
            ),
            CountedRow(
                implementation_surface_id=f"surface:other:{index:04d}",
                behavior_block_id=f"behavior:supporting:{index:04d}",
                coverage_id=f"coverage:supporting:{index:04d}",
                test_node_id=f"test:supporting:{index:04d}",
                covered_dimensions=("output",),
            ),
        )
    )
    coverage_execution = tuple(
        SimpleNamespace(
            coverage_id=str(row._values["coverage_id"]),
            disposition="pass",
            receipt_id=(
                "receipt:" + str(row._values["coverage_id"]).split(":", 1)[1]
            ),
        )
        for row in coverage_edges
    )
    signal_members = tuple(
        CountedRow(
            member_id=surface.surface_id,
            signal_kinds=("maintenance_name_signal",),
        )
        for index, surface in enumerate(surfaces)
    ) + tuple(
        CountedRow(
            member_id=f"surface:irrelevant:{index:04d}",
            signal_kinds=("maintenance_name_signal",),
        )
        for index in range(800)
    )
    class CountedManifest:
        def __init__(self):
            self.read_count = 0

        @property
        def fingerprint(self):
            self.read_count += 1
            return "sha256:blueprint"

    bundle = _bundle()
    bundle.manifest = CountedManifest()
    bundle.inventory.surfaces = surfaces
    bundle.inventory.required_surface_ids = tuple(
        row.surface_id for row in surfaces
    )
    bundle.behavior_report.contracts = contracts
    bundle.behavior_report.supporting_relations = supporting_relations
    bundle.behavior_report.coverage_edges = coverage_edges
    bundle.behavior_report.coverage_execution_evidence = coverage_execution

    candidates, _, _, catalog = _self_reduction_candidates(
        bundle,
        reduction_universe=SimpleNamespace(members=signal_members),
    )
    maintenance_candidates = tuple(
        sorted(
            (
                candidate
                for candidate in candidates
                if candidate.metadata["signal"]
                == "fallback_alias_compatibility_path"
            ),
            key=lambda candidate: candidate.metadata["member_ids"],
        )
    )

    assert len(maintenance_candidates) == surface_count // 2
    assert bundle.manifest.read_count == 1
    first_contract = maintenance_candidates[0].metadata["observable_contract"]
    assert set(first_contract).isdisjoint(
        {
            "test_node_ids",
            "coverage_ids",
            "covered_dimensions",
            "current_test_receipt_ids",
        }
    )
    assert first_contract["evidence_neighborhood_id"] in (
        catalog.neighborhood_ids
    )
    assert all(
        candidate.metadata["source_signal_ids"]
        == candidate.metadata["member_ids"]
        for candidate in maintenance_candidates
    )
    assert {
        member_id
        for candidate in maintenance_candidates
        for member_id in candidate.metadata["member_ids"]
    } == {surface.surface_id for surface in surfaces}
    assert sum(row.reads["member_id"] for row in signal_members) == len(
        signal_members
    )
    assert sum(row.reads["signal_kinds"] for row in signal_members) == len(
        signal_members
    )
    assert sum(
        row.reads["implementation_surface_id"] for row in contracts
    ) == len(contracts)
    assert sum(
        row.reads["supporting_surface_id"] for row in supporting_relations
    ) == len(supporting_relations)
    assert sum(
        row.reads["implementation_surface_id"] for row in coverage_edges
    ) == len(coverage_edges)
    assert sum(row.reads["behavior_block_id"] for row in coverage_edges) == len(
        coverage_edges
    )
    resolved_contract = _resolved_candidate_observable_contract(
        bundle,
        maintenance_candidates[0],
    )
    assert resolved_contract == {
        "caller_consumer_ids": (),
        "behavior_block_ids": (
            "behavior:direct:0000",
            "behavior:direct:0001",
            "behavior:supporting:0000",
            "behavior:supporting:0001",
        ),
        "model_element_ids": ("model:0000", "model:0001"),
        "owner_ids": ("owner:0000", "owner:0001"),
        "state_reads": (),
        "state_writes": (),
        "side_effect_ids": (),
        "raised_error_ids": (),
        "test_node_ids": (
            "test:direct:0000",
            "test:direct:0001",
            "test:supporting:0000",
            "test:supporting:0001",
        ),
        "coverage_ids": (
            "coverage:direct:0000",
            "coverage:direct:0001",
            "coverage:supporting:0000",
            "coverage:supporting:0001",
        ),
        "covered_dimensions": ("input", "output"),
        "current_test_receipt_ids": (
            "receipt:direct:0000",
            "receipt:direct:0001",
            "receipt:supporting:0000",
            "receipt:supporting:0001",
        ),
    }


def test_shared_behavior_evidence_neighborhood_is_materialized_once_for_300_candidates():
    candidate_count = 300
    surface_count = candidate_count * 2
    surfaces = tuple(
        SimpleNamespace(
            surface_id=f"surface:legacy:{index:04d}",
            path=f"flowguard/legacy_{index:04d}.py",
            symbol=f"legacy_path_{index:04d}",
            line_start=1,
            line_end=20,
            structure_fingerprint=f"sha256:shape:{index // 2:04d}",
            content_fingerprint=f"sha256:content:{index:04d}",
            roles=(),
            surface_kind="function",
            calls=(f"delegate_{index // 2:04d}",),
            state_reads=(),
            state_writes=(),
            side_effect_candidates=(),
            raised_errors=(),
        )
        for index in range(surface_count)
    )
    behavior_id = "behavior:shared"
    test_id = "test:external-equivalence"
    coverage_edges = tuple(
        SimpleNamespace(
            implementation_surface_id=surface.surface_id,
            behavior_block_id=behavior_id,
            coverage_id=f"coverage:shared:{index:04d}",
            test_node_id=test_id,
            covered_dimensions=("input", "output", "state", "effect", "error"),
        )
        for index, surface in enumerate(surfaces)
    )
    bundle = _bundle()
    bundle.inventory.surfaces = surfaces
    bundle.inventory.required_surface_ids = tuple(
        surface.surface_id for surface in surfaces
    )
    bundle.behavior_report.contracts = tuple(
        SimpleNamespace(
            implementation_surface_id=surface.surface_id,
            behavior_block_id=behavior_id,
            model_element_id=f"model:{index:04d}",
            owner_id=f"owner:{index:04d}",
        )
        for index, surface in enumerate(surfaces)
    )
    bundle.behavior_report.supporting_relations = ()
    bundle.behavior_report.coverage_edges = coverage_edges
    bundle.behavior_report.coverage_execution_evidence = tuple(
        SimpleNamespace(
            coverage_id=row.coverage_id,
            disposition="pass",
            receipt_id=f"receipt:{index:04d}",
        )
        for index, row in enumerate(coverage_edges)
    )
    universe = SimpleNamespace(
        members=tuple(
            SimpleNamespace(
                member_id=surface.surface_id,
                source_ref=surface.surface_id,
                signal_kinds=("maintenance_name_signal",),
            )
            for index, surface in enumerate(surfaces)
        )
    )

    candidates, _, _, catalog = _self_reduction_candidates(
        bundle,
        reduction_universe=universe,
    )
    maintenance_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.metadata["signal"]
        == "fallback_alias_compatibility_path"
    )

    assert len(maintenance_candidates) == candidate_count
    assert len(catalog.entries) == 1
    assert len(catalog.entries[0].coverage_ids) == surface_count
    assert catalog.entries[0].test_node_ids == (test_id,)
    assert {
        candidate.metadata["observable_contract"][
            "evidence_neighborhood_id"
        ]
        for candidate in maintenance_candidates
    } == {catalog.entries[0].neighborhood_id}
    assert all(
        set(candidate.metadata["observable_contract"]).isdisjoint(
            {
                "test_node_ids",
                "coverage_ids",
                "covered_dimensions",
                "current_test_receipt_ids",
            }
        )
        for candidate in maintenance_candidates
    )
    resolved = _resolved_candidate_observable_contract(
        bundle,
        maintenance_candidates[-1],
    )
    assert len(resolved["coverage_ids"]) == surface_count
    assert resolved["test_node_ids"] == (test_id,)


def test_self_reduction_review_rejects_inline_evidence_neighborhood_fallback():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_same_commitment_candidate_bundle()
    )
    candidate = report.candidates[0]
    contract = dict(candidate.metadata["observable_contract"])
    contract["coverage_ids"] = ()
    metadata = {
        **candidate.metadata,
        "observable_contract": contract,
        "observable_contract_fingerprint": fingerprint_value(contract),
    }
    forged = replace(candidate, metadata=metadata)

    with pytest.raises(ValueError, match="inline evidence neighborhood fallback"):
        replace(report, candidates=(forged, *report.candidates[1:]))


def test_self_reduction_review_rejects_unknown_neighborhood_reference():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_same_commitment_candidate_bundle()
    )
    candidate = report.candidates[0]
    contract = {
        **candidate.metadata["observable_contract"],
        "evidence_neighborhood_id": (
            "self-reduction-evidence-neighborhood:unknown"
        ),
        "evidence_neighborhood_fingerprint": "sha256:unknown",
    }
    metadata = {
        **candidate.metadata,
        "observable_contract": contract,
        "observable_contract_fingerprint": fingerprint_value(contract),
    }
    forged = replace(candidate, metadata=metadata)

    with pytest.raises(ValueError, match="unknown evidence neighborhood"):
        replace(report, candidates=(forged, *report.candidates[1:]))


def test_self_reduction_review_rejects_neighborhood_fingerprint_substitution():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_same_commitment_candidate_bundle()
    )
    candidate = report.candidates[0]
    contract = {
        **candidate.metadata["observable_contract"],
        "evidence_neighborhood_fingerprint": "sha256:substituted",
    }
    metadata = {
        **candidate.metadata,
        "observable_contract": contract,
        "observable_contract_fingerprint": fingerprint_value(contract),
    }
    forged = replace(candidate, metadata=metadata)

    with pytest.raises(ValueError, match="does not match the review catalog"):
        replace(report, candidates=(forged, *report.candidates[1:]))


def test_self_reduction_review_rejects_stale_catalog_fingerprint():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle()
    )

    with pytest.raises(ValueError, match="catalog fingerprint mismatch"):
        replace(
            report,
            candidate_evidence_neighborhood_catalog_fingerprint=(
                "sha256:stale"
            ),
        )


def test_self_reduction_catalog_rejects_duplicate_content_addressed_entry():
    entry = SelfReductionEvidenceNeighborhood(
        test_node_ids=("test:shared",),
        coverage_ids=("coverage:shared",),
        covered_dimensions=("input",),
        current_test_receipt_ids=("receipt:shared",),
    )

    with pytest.raises(ValueError, match="duplicate ids"):
        SelfReductionEvidenceNeighborhoodCatalog((entry, entry))


def test_self_reduction_catalog_rejects_foreign_entry_type():
    with pytest.raises(TypeError, match="requires typed entries"):
        SelfReductionEvidenceNeighborhoodCatalog(
            (SimpleNamespace(neighborhood_id="foreign"),)
        )


def test_self_reduction_review_rejects_orphan_neighborhood_catalog_entry():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle()
    )
    orphan = SelfReductionEvidenceNeighborhood(
        test_node_ids=("test:orphan",),
        coverage_ids=("coverage:orphan",),
        covered_dimensions=("input",),
        current_test_receipt_ids=("receipt:orphan",),
    )
    catalog = SelfReductionEvidenceNeighborhoodCatalog(
        (*report.candidate_evidence_neighborhood_catalog.entries, orphan)
    )

    with pytest.raises(ValueError, match="unreferenced or missing entry"):
        replace(
            report,
            candidate_evidence_neighborhood_catalog=catalog,
            candidate_evidence_neighborhood_catalog_fingerprint=(
                catalog.fingerprint
            ),
        )


def test_proofless_review_discovers_one_candidate_inventory_and_rechecks_sources():
    bundle = _bundle()
    universe = derive_self_reduction_universe(bundle)
    (
        expected_candidates,
        expected_fingerprint,
        expected_classifications,
        expected_catalog,
    ) = (
        _self_reduction_candidates(
            bundle,
            reduction_universe=universe,
            proof_records=(),
        )
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.derive_self_reduction_universe",
            return_value=universe,
        ) as derive,
        mock.patch(
            "flowguard.self_architecture_reduction.capture_flowguard_self_blueprint_build_input_identity",
            return_value=_build_input_identity(),
        ) as capture,
        mock.patch(
            "flowguard.self_architecture_reduction._self_reduction_candidates",
            wraps=_self_reduction_candidates,
        ) as discover,
    ):
        report = _review_current_flowguard_self_architecture_reduction(
            ".",
            bundle=bundle,
            build_input_identity=_build_input_identity(),
        )

    assert discover.call_count == 1
    assert derive.call_count == 1
    assert capture.call_count == 1
    assert tuple(row.to_dict() for row in report.candidates) == tuple(
        row.to_dict() for row in expected_candidates
    )
    assert report.candidate_inventory_fingerprint == expected_fingerprint
    assert (
        report.candidate_evidence_neighborhood_catalog_fingerprint
        == expected_catalog.fingerprint
    )
    assert (
        report.candidate_evidence_neighborhood_catalog.to_dict()
        == expected_catalog.to_dict()
    )
    assert tuple(row.to_dict() for row in report.compatibility_classifications) == tuple(
        row.to_dict() for row in expected_classifications
    )


def test_composed_self_check_builds_blueprint_once_and_reuses_exact_bundle():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
    )
    bundle.to_dict = mock.Mock(return_value={"ok": True, "fingerprint": "blueprint"})
    reduction = SimpleNamespace(ok=True)
    reduction.to_dict = mock.Mock(
        return_value={
            "ok": True,
            "self_blueprint_fingerprint": "sha256:blueprint",
        }
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_architecture_reduction_review",
            return_value=(bundle, reduction),
        ) as composed,
        mock.patch("flowguard.__main__._emit_payload") as emit,
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 0
    composed.assert_called_once_with(".")
    emitted = emit.call_args.args[0]
    assert emitted["architecture_reduction_review"]["ok"] is True
    assert emitted["composed_self_maintenance_review"] is True


def test_composed_builder_builds_current_bundle_once_and_reviews_that_bundle():
    current_identity = _build_input_identity()
    bundle = SimpleNamespace(ok=True, build_input_identity=current_identity)
    reduction = SimpleNamespace(ok=True)

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_blueprint",
            return_value=bundle,
        ) as build,
        mock.patch(
            "flowguard.self_architecture_reduction._review_current_flowguard_self_architecture_reduction",
            return_value=reduction,
        ) as review,
    ):
        actual_bundle, actual_review = (
            build_flowguard_self_architecture_reduction_review("current-root")
        )

    assert actual_bundle is bundle
    assert actual_review is reduction
    build.assert_called_once_with("current-root")
    review.assert_called_once_with(
        "current-root",
        bundle=bundle,
        build_input_identity=current_identity,
    )


def test_composed_self_check_fails_when_reduction_review_is_blocked():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
    )
    bundle.to_dict = mock.Mock(return_value={"ok": True, "fingerprint": "blueprint"})
    reduction = SimpleNamespace(ok=False)
    reduction.to_dict = mock.Mock(
        return_value={
            "ok": False,
            "self_blueprint_fingerprint": "sha256:blueprint",
        }
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_architecture_reduction_review",
            return_value=(bundle, reduction),
        ),
        mock.patch("flowguard.__main__._emit_payload"),
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 1


def test_compact_reduction_payload_never_expands_full_report():
    report = SimpleNamespace(
        schema_version="flowguard.self_architecture_reduction_review.v2",
        status="pass",
        ok=True,
        review_fingerprint="sha256:reduction",
        self_blueprint_fingerprint="sha256:blueprint",
        candidate_inventory_fingerprint="sha256:candidates",
        candidates=(),
        denominator_complete=True,
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(decision="retain", required_next_routes=()),
        claim_boundary="bounded",
        to_dict=mock.Mock(side_effect=AssertionError("full report expanded")),
    )

    payload = BlueprintCompactProjection.reduction(report)

    assert payload["review_fingerprint"] == "sha256:reduction"
    assert payload["projection_fingerprint"].startswith("sha256:")
    assert payload["projection_fingerprint"] != payload["review_fingerprint"]
    report.to_dict.assert_not_called()


def test_compact_composed_self_check_never_expands_full_blueprint():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
        behavior_report=SimpleNamespace(
            owner_structure_status="complete",
            pre_code_status="ready",
            executed_evidence_status="not_run",
            coverage_edges=(),
            findings=(),
        ),
        resource_inventory=SimpleNamespace(complete=True),
        intent_inventory=SimpleNamespace(complete=True),
        target_system_report=SimpleNamespace(
            status="complete",
            fingerprint="sha256:target",
        ),
        normalized_projection=SimpleNamespace(
            blueprint_fingerprint="sha256:blueprint",
        ),
        static_readiness=SimpleNamespace(
            status="ready",
            behavior_report_fingerprint="sha256:behavior",
            resource_inventory_fingerprint="sha256:resources",
            intent_inventory_fingerprint="sha256:intent",
        ),
        understanding_summary=SimpleNamespace(
            blueprint_fingerprint="sha256:target",
            deepest_proven_layer="static_blueprint",
            first_gap=None,
            gap_count=0,
        ),
        test_inventory=SimpleNamespace(nodes=(), required_node_ids=()),
        binding_report=SimpleNamespace(findings=()),
        to_dict=mock.Mock(side_effect=AssertionError("full blueprint expanded")),
    )
    reduction = SimpleNamespace(
        schema_version="flowguard.self_architecture_reduction_review.v2",
        status="pass",
        ok=True,
        review_fingerprint="sha256:reduction",
        self_blueprint_fingerprint="sha256:blueprint",
        candidate_inventory_fingerprint="sha256:candidates",
        candidates=(),
        denominator_complete=True,
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(decision="retain", required_next_routes=()),
        claim_boundary="bounded",
        to_dict=mock.Mock(side_effect=AssertionError("full reduction expanded")),
    )
    args = SimpleNamespace(
        root=".",
        compact=True,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_architecture_reduction.build_flowguard_self_architecture_reduction_review",
            return_value=(bundle, reduction),
        ),
        mock.patch("flowguard.__main__._emit_payload") as emit,
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 0
    bundle.to_dict.assert_not_called()
    reduction.to_dict.assert_not_called()
    assert emit.call_args.args[0]["composed_self_maintenance_review"] is True
