from types import SimpleNamespace
from unittest import mock

import pytest

from flowguard.blueprint_compact_projection import (
    BlueprintCompactProjection,
    _required_stored_or_property,
)


def test_required_compact_property_rejects_an_open_selector():
    subject = SimpleNamespace(schema_version="schema:current", fingerprint="fp")

    assert (
        _required_stored_or_property(
            subject,
            "schema_version",
            context="compact review",
        )
        == "schema:current"
    )
    with pytest.raises(ValueError, match="unsupported compact property"):
        _required_stored_or_property(
            subject,
            "fingerprint",
            context="compact review",
        )


def test_understanding_projection_never_serializes_summary_or_gap():
    gap = SimpleNamespace(
        gap_id="gap:1",
        layer="model_code_test",
        object_kind="owner",
        object_id="owner:a",
        status="blocked",
        owner_id="owner:a",
        evidence_ref="receipt:missing",
        message="exact leaf evidence is missing",
        to_dict=mock.Mock(side_effect=AssertionError("gap expanded")),
    )
    summary = SimpleNamespace(
        scope="affected",
        target_system_id="target:a",
        target_profile="software",
        subject_revision="sha256:subject",
        descriptor_fingerprint="sha256:descriptor",
        blueprint_fingerprint="sha256:blueprint",
        fingerprint="sha256:summary",
        layer_statuses=(("implementation_inventory", "complete"), ("model_code_test", "blocked")),
        deepest_proven_layer="implementation_inventory",
        first_gap=gap,
        gap_count=1,
        affected_surface_ids=("surface:a",),
        implementation_admitted=False,
        to_dict=mock.Mock(side_effect=AssertionError("summary expanded")),
    )

    payload = BlueprintCompactProjection.understanding(summary)

    assert payload["target_system_id"] == "target:a"
    assert payload["target_profile"] == "software"
    assert payload["affected_ids"] == ["surface:a"]
    assert payload["layer_statuses"] == [
        {"layer": "implementation_inventory", "status": "complete"},
        {"layer": "model_code_test", "status": "blocked"},
    ]
    assert payload["first_gap"]["object_id"] == "owner:a"
    assert payload["implementation_admitted"] is False
    summary.to_dict.assert_not_called()
    gap.to_dict.assert_not_called()


def test_self_qualification_projection_never_serializes_blueprint():
    bundle = SimpleNamespace(
        ok=False,
        manifest=SimpleNamespace(fingerprint="sha256:self"),
        inventory=SimpleNamespace(
            inventory_fingerprint="sha256:inventory",
            surfaces=(1, 2),
            required_surface_ids=("surface:a",),
        ),
        test_inventory=SimpleNamespace(
            inventory_fingerprint="sha256:tests",
            nodes=(1, 2, 3),
            required_node_ids=("test:a", "test:b"),
        ),
        behavior_report=SimpleNamespace(
            fingerprint="sha256:behavior",
            contracts=(1,),
            coverage_edges=(1, 2),
            findings=(1,),
        ),
        binding_report=SimpleNamespace(
            findings=(
                SimpleNamespace(
                    code="oracle_source_not_independent",
                    severity="blocked",
                    message="oracle source overlaps implementation source",
                    member_ids=("binding:a", "oracle:a", "source:a"),
                ),
                SimpleNamespace(
                    code="oracle_source_not_independent",
                    severity="blocked",
                    message="oracle source overlaps implementation source",
                    member_ids=("binding:b", "oracle:b", "source:b"),
                ),
            )
        ),
        model_test_alignment_report=SimpleNamespace(
            pre_code_status="ready",
            executed_evidence_status="not_run",
            findings=(
                SimpleNamespace(
                    code="test_evidence_not_passing",
                    severity="blocker",
                    message="planned checker has not run",
                    member_ids=("checker:a",),
                ),
            ),
        ),
        resource_inventory=SimpleNamespace(fingerprint="sha256:resources", complete=True),
        intent_inventory=SimpleNamespace(fingerprint="sha256:intent", complete=True),
        target_system_report=SimpleNamespace(
            fingerprint="sha256:target",
            status="blocked",
        ),
        normalized_projection=SimpleNamespace(
            blueprint_fingerprint="sha256:self"
        ),
        static_readiness=SimpleNamespace(
            status="blocked",
            fingerprint="sha256:readiness",
            behavior_report_fingerprint="sha256:behavior",
            resource_inventory_fingerprint="sha256:resources",
            intent_inventory_fingerprint="sha256:intent",
        ),
        understanding_summary=SimpleNamespace(
            blueprint_fingerprint="sha256:target",
            deepest_proven_layer="behavior",
            first_gap=None,
            gap_count=2,
            implementation_admitted=False,
        ),
        to_dict=mock.Mock(side_effect=AssertionError("blueprint expanded")),
    )

    payload = BlueprintCompactProjection.self_qualification(bundle)

    assert payload["self_blueprint_fingerprint"] == "sha256:self"
    assert payload["counts"]["implementation_surfaces"] == 2
    assert payload["counts"]["required_test_nodes"] == 2
    assert payload["gap_count"] == 2
    assert payload["blocking_finding_counts"] == {
        "binding:oracle_source_not_independent:blocked": 2
    }
    assert payload["execution_gap_counts"] == {
        "model_test_alignment:test_evidence_not_passing:blocker": 1
    }
    assert payload["execution_gap_examples"][0]["member_ids"] == ["checker:a"]
    assert payload["blocking_finding_examples"][0]["member_ids"] == [
        "binding:a",
        "oracle:a",
        "source:a",
    ]
    assert payload["implementation_admitted"] is False
    bundle.to_dict.assert_not_called()


def test_self_qualification_requires_direct_stored_aggregate_identities():
    bundle = SimpleNamespace(
        ok=False,
        inventory=SimpleNamespace(
            inventory_fingerprint="sha256:inventory",
            surfaces=(),
            required_surface_ids=(),
        ),
        test_inventory=SimpleNamespace(
            inventory_fingerprint="sha256:tests",
            nodes=(),
            required_node_ids=(),
        ),
        behavior_report=SimpleNamespace(contracts=(), coverage_edges=(), findings=()),
        resource_inventory=SimpleNamespace(complete=False),
        intent_inventory=SimpleNamespace(complete=False),
        target_system_report=SimpleNamespace(status="blocked"),
        normalized_projection=SimpleNamespace(
            blueprint_fingerprint="sha256:self"
        ),
        static_readiness=SimpleNamespace(
            status="blocked",
            resource_inventory_fingerprint="sha256:resources",
            intent_inventory_fingerprint="sha256:intent",
        ),
        understanding_summary=SimpleNamespace(
            blueprint_fingerprint="sha256:target",
            deepest_proven_layer="inventory",
            first_gap=None,
            gap_count=1,
            implementation_admitted=False,
        ),
    )

    with pytest.raises(ValueError, match="behavior_report_fingerprint"):
        BlueprintCompactProjection.self_qualification(bundle)


def test_reduction_projection_is_bounded_and_never_serializes_review():
    class StoredReview(SimpleNamespace):
        @property
        def fingerprint(self):
            raise AssertionError("large review fingerprint property invoked")

    candidates = tuple(
        SimpleNamespace(
            candidate_id=f"candidate:{index:02d}",
            target_action=(
                "retire_behavior" if index in {0, 1} else "manual_review"
            ),
            metadata={
                "signal": f"signal:{index:02d}",
                "disposition": "unresolved",
                "missing_proof_obligations": (
                    f"proof:{index:02d}",
                    "shared_proof",
                ),
            },
            to_dict=mock.Mock(side_effect=AssertionError("candidate expanded")),
        )
        for index in range(25)
    )
    review = StoredReview(
        schema_version="flowguard.self_architecture_reduction_review.v9",
        status="pass",
        ok=True,
        review_fingerprint="sha256:review",
        self_blueprint_fingerprint="sha256:self",
        candidate_inventory_fingerprint="sha256:candidates",
        reduction_universe_fingerprint="sha256:universe",
        reduction_universe=SimpleNamespace(
            members=tuple(
                SimpleNamespace(
                    disposition="unresolved",
                    member_kind=f"kind:{index:02d}",
                    to_dict=mock.Mock(
                        side_effect=AssertionError("universe member expanded")
                    ),
                )
                for index in range(40)
            )
        ),
        candidates=candidates,
        retain_dispositions=(),
        denominator_complete=True,
        candidate_review_complete=True,
        step_decision_complete=False,
        audit_accounted=True,
        audit_complete=True,
        action_authorized_candidate_ids=(),
        cleanup_release_ready=False,
        unresolved_member_ids=tuple(f"member:{index:02d}" for index in range(20)),
        unresolved_step_ids=tuple(f"step:{index:02d}" for index in range(80)),
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(
            decision="no_ready_reduction_candidates",
            required_next_routes=("structure_mesh_maintenance",),
            step_assessments=tuple(
                SimpleNamespace(
                    action="unresolved",
                    to_dict=mock.Mock(
                        side_effect=AssertionError("step assessment expanded")
                    ),
                )
                for _index in range(80)
            ),
        ),
        claim_boundary="bounded",
        to_dict=mock.Mock(side_effect=AssertionError("review expanded")),
    )

    payload = BlueprintCompactProjection.reduction(review, breakdown_limit=8)

    assert payload["candidate_count"] == 25
    assert len(payload["candidate_counts_by_signal"]) == 8
    assert payload["omitted_signal_count"] == 17
    assert payload["universe_member_count"] == 40
    assert payload["unresolved_candidate_count"] == 25
    assert payload["proof_required_candidate_count"] == 25
    assert payload["retirement_review_candidate_count"] == 2
    assert payload["missing_proof_obligation_count"] == 50
    assert len(payload["missing_proof_counts_by_kind"]) == 8
    assert payload["omitted_missing_proof_kind_count"] == 18
    assert sum(payload["candidate_counts_by_necessity_disposition"].values()) == 25
    assert payload["candidate_counts_by_necessity_disposition"] == {
        "unresolved": 25
    }
    assert payload["candidate_counts_by_metadata_disposition"] == {
        "unresolved": 25
    }
    assert payload["candidate_counts_by_disposition"] == {
        "unresolved": 25
    }
    assert payload["candidate_counts_by_disposition_basis"] == (
        "candidate.metadata.disposition"
    )
    assert len(payload["candidate_index"]) == 25
    assert payload["candidate_index"][0]["candidate_id"] == "candidate:00"
    assert payload["candidate_index"][0]["target_action"] == "retire_behavior"
    assert payload["omitted_candidate_index_count"] == 0
    assert payload["candidate_index"][0]["missing_proof_obligations"] == [
        "proof:00",
        "shared_proof",
    ]
    assert len(payload["unresolved_member_counts_by_kind"]) == 8
    assert payload["omitted_unresolved_member_kind_count"] == 32
    assert payload["step_assessment_count"] == 80
    assert payload["step_action_counts"] == {"unresolved": 80}
    assert payload["unresolved_step_count"] == 80
    assert payload["review_fingerprint"] == "sha256:review"
    assert payload["schema_version"] == (
        "flowguard.self_architecture_reduction_review.v9"
    )
    assert payload["projection_fingerprint"].startswith("sha256:")
    assert payload["projection_fingerprint"] != payload["review_fingerprint"]
    assert "fingerprint" not in payload
    assert payload["reduction_universe_fingerprint"] == "sha256:universe"
    assert payload["audit_accounted"] is True
    assert payload["audit_complete"] is True
    assert payload["step_decision_complete"] is False
    assert payload["action_authorized_candidate_ids"] == []
    assert payload["cleanup_release_ready"] is False
    assert len(payload["unresolved_member_ids"]) == 20
    assert payload["omitted_unresolved_member_count"] == 0
    assert len(payload["unresolved_step_ids"]) == 64
    assert payload["omitted_unresolved_step_count"] == 16
    assert all(candidate.to_dict.call_count == 0 for candidate in candidates)
    assert all(
        member.to_dict.call_count == 0
        for member in review.reduction_universe.members
    )
    assert all(
        step.to_dict.call_count == 0
        for step in review.reduction_report.step_assessments
    )
    review.to_dict.assert_not_called()


def test_reduction_projection_separates_typed_necessity_from_metadata_disposition():
    candidates = (
        SimpleNamespace(
            candidate_id="candidate:typed-retain",
            target_action="manual_review",
            metadata={
                "signal": "helper_path",
                "disposition": "contract",
                "missing_proof_obligations": ("caller_parity",),
            },
        ),
        SimpleNamespace(
            candidate_id="candidate:contract",
            target_action="retire_behavior",
            metadata={
                "signal": "duplicate_branch",
                "disposition": "contract",
                "missing_proof_obligations": (),
            },
        ),
        SimpleNamespace(
            candidate_id="candidate:unresolved",
            target_action="manual_review",
            metadata={
                "signal": "adapter_layer",
                "disposition": "unresolved",
                "missing_proof_obligations": (
                    "caller_parity",
                    "state_parity",
                ),
            },
        ),
    )
    review = SimpleNamespace(
        schema_version="flowguard.self_architecture_reduction_review.v9",
        status="pass",
        review_fingerprint="sha256:review",
        self_blueprint_fingerprint="sha256:self",
        candidate_inventory_fingerprint="sha256:candidates",
        reduction_universe_fingerprint="sha256:universe",
        candidates=candidates,
        retain_dispositions=(
            SimpleNamespace(candidate_ids=("candidate:typed-retain",)),
        ),
        reduction_universe=SimpleNamespace(
            members=(
                SimpleNamespace(
                    disposition="unresolved",
                    member_kind="implementation_surface",
                ),
                SimpleNamespace(
                    disposition="unresolved",
                    member_kind="implementation_surface",
                ),
                SimpleNamespace(
                    disposition="unresolved",
                    member_kind="check_owner",
                ),
                SimpleNamespace(
                    disposition="retain",
                    member_kind="test",
                ),
            )
        ),
        denominator_complete=True,
        candidate_review_complete=True,
        step_decision_complete=False,
        audit_accounted=True,
        audit_complete=True,
        action_authorized_candidate_ids=(),
        cleanup_release_ready=False,
        unresolved_member_ids=("member:a", "member:b", "member:c"),
        unresolved_step_ids=("step:unresolved",),
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(
            decision="no_ready_reduction_candidates",
            required_next_routes=("structure_mesh_maintenance",),
            step_assessments=(
                SimpleNamespace(action="retain"),
                SimpleNamespace(action="remove"),
                SimpleNamespace(action="unresolved"),
            ),
        ),
        claim_boundary="bounded",
    )

    payload = BlueprintCompactProjection.reduction(review)

    assert payload["candidate_counts_by_necessity_disposition"] == {
        "contract": 1,
        "retain": 1,
        "unresolved": 1,
    }
    assert payload["candidate_counts_by_metadata_disposition"] == {
        "contract": 2,
        "unresolved": 1,
    }
    assert payload["candidate_counts_by_disposition"] == (
        payload["candidate_counts_by_metadata_disposition"]
    )
    assert sum(payload["candidate_counts_by_necessity_disposition"].values()) == (
        payload["candidate_count"]
    )
    assert sum(payload["candidate_counts_by_metadata_disposition"].values()) == (
        payload["candidate_count"]
    )
    assert payload["unresolved_candidate_count"] == 1
    assert payload["proof_required_candidate_count"] == 2
    assert payload["retirement_review_candidate_count"] == 1
    assert payload["missing_proof_obligation_count"] == 3
    assert payload["missing_proof_counts_by_kind"] == {
        "caller_parity": 2,
        "state_parity": 1,
    }
    assert sum(payload["missing_proof_counts_by_kind"].values()) == (
        payload["missing_proof_obligation_count"]
    )
    assert payload["unresolved_member_counts_by_kind"] == {
        "check_owner": 1,
        "implementation_surface": 2,
    }
    assert sum(payload["unresolved_member_counts_by_kind"].values()) == 3
    assert payload["step_assessment_count"] == 3
    assert payload["step_action_counts"] == {
        "remove": 1,
        "retain": 1,
        "unresolved": 1,
    }
    assert sum(payload["step_action_counts"].values()) == (
        payload["step_assessment_count"]
    )
    assert payload["unresolved_step_count"] == 1


def test_reduction_projection_requires_stored_review_fingerprint_without_fallback():
    class PropertyOnlyReview:
        @property
        def fingerprint(self):
            raise AssertionError("large review fingerprint property invoked")

    with pytest.raises(ValueError, match="review_fingerprint"):
        BlueprintCompactProjection.reduction(PropertyOnlyReview())
