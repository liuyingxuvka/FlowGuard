from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from flowguard.model_path_quality import (
    HARD_SEMANTIC_DIMENSIONS,
    NecessityWitness,
    PathCandidate,
    PathCostVector,
    PathQualityMaterialReview,
    PathQualityResult,
    PathQualitySubject,
    bounded_conclusion_text,
    canonical_fingerprint,
    collect_deep_review_triggers,
    compare_cost_vectors,
    derive_retained_elements,
    evaluate_deep_path_review,
    find_lightweight_findings,
    hard_semantic_mismatches,
    lightweight_path_review,
    normalized_model_facts_fingerprint,
    path_quality_result_set_fingerprint,
    review_path_quality_material,
    validate_necessity_witnesses,
)


def fp(value: str) -> str:
    return canonical_fingerprint({"value": value})


def subject(**overrides: object) -> PathQualitySubject:
    model_facts = overrides.pop("_model_facts", clean_facts())
    if not isinstance(model_facts, dict):
        raise TypeError("_model_facts must be a dictionary")
    active_obligation_ids = overrides.pop(
        "_active_obligation_ids",
        active_obligations_for(model_facts),
    )
    values: dict[str, object] = {
        "model_id": "workflow.order",
        "boundary_id": "behavior:order",
        "model_fingerprint": fp("model"),
        "normalized_facts_fingerprint": normalized_model_facts_fingerprint(model_facts),
        "retained_element_inventory_fingerprint": canonical_fingerprint(
            dict(derive_retained_elements(model_facts))
        ),
        "purpose_fingerprint": fp("purpose"),
        "intent_fingerprint": fp("intent"),
        "obligation_fingerprint": canonical_fingerprint(list(active_obligation_ids)),
        "provider_fingerprint": fp("provider"),
        "dependency_fingerprint": fp("dependency-set"),
        "code_fingerprint": fp("code-or-explicit-na"),
        "test_fingerprint": fp("test-set"),
        "oracle_fingerprint": fp("oracle-set"),
        "evidence_fingerprint": fp("evidence-set"),
        "currentness_id": "revision:17",
    }
    values.update(overrides)
    return PathQualitySubject(**values)  # type: ignore[arg-type]


def hard_semantics(**overrides: str) -> dict[str, str]:
    values = {name: fp(f"semantic:{name}") for name in HARD_SEMANTIC_DIMENSIONS}
    values.update(overrides)
    return values


def witness(
    owner: PathQualitySubject,
    witness_id: str,
    element_id: str,
    *,
    element_kind: str = "state",
    current: bool = True,
    subject_fingerprint: str = "",
    evidence_currentness_id: str = "",
    depends_on: tuple[str, ...] = (),
) -> NecessityWitness:
    return NecessityWitness(
        witness_id=witness_id,
        subject_fingerprint=subject_fingerprint or owner.fingerprint,
        element_id=element_id,
        element_kind=element_kind,
        obligation_id=f"obligation:{element_id}",
        counterexample_id=f"counterexample:{element_id}",
        oracle_id=f"oracle:{element_id}",
        evidence_fingerprint=fp(f"witness-evidence:{witness_id}"),
        evidence_currentness_id=evidence_currentness_id or owner.currentness_id,
        depends_on_witness_ids=depends_on,
        current=current,
    )


def active_obligations_for(model_facts: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        sorted(f"obligation:{element_id}" for element_id, _kind in derive_retained_elements(model_facts))
    )


def witnesses_for(owner: PathQualitySubject, model_facts: dict[str, object]) -> tuple[NecessityWitness, ...]:
    return tuple(
        witness(
            owner,
            f"witness:{element_id}",
            element_id,
            element_kind=kind,
        )
        for element_id, kind in derive_retained_elements(model_facts)
    )


def cost(
    candidate_model_fingerprint: str,
    candidate_id: str,
    values: dict[str, float],
    *,
    current: bool = True,
    units: dict[str, str] | None = None,
) -> PathCostVector:
    return PathCostVector(
        measurement_id=f"measurement:{candidate_id}",
        subject_fingerprint=candidate_model_fingerprint,
        currentness_id="revision:17",
        measurement_units=units or {name: "count" for name in values},
        measurement_evidence={name: fp(f"measure:{candidate_id}:{name}") for name in values},
        current=current,
        **values,
    )


def candidate(
    owner: PathQualitySubject,
    candidate_id: str,
    values: dict[str, float] | None,
    *,
    semantic_overrides: dict[str, str] | None = None,
    retained_elements: dict[str, str] | None = None,
    witnesses: tuple[NecessityWitness, ...] = (),
    current: bool = True,
    lane: str = "normative_target",
    subject_fingerprint: str = "",
    observed_baseline: bool = False,
    rewrite_rule_ids: tuple[str, ...] = (),
) -> PathCandidate:
    after = owner.model_fingerprint if observed_baseline else fp(f"candidate-model:{candidate_id}")
    if retained_elements is None:
        default_facts = clean_facts()
        retained = dict(derive_retained_elements(default_facts))
        if not witnesses:
            witnesses = witnesses_for(owner, default_facts)
    else:
        retained = retained_elements
    semantics = hard_semantics(**(semantic_overrides or {}))
    return PathCandidate(
        candidate_id=candidate_id,
        subject_fingerprint=subject_fingerprint or owner.fingerprint,
        before_model_fingerprint=owner.model_fingerprint,
        after_model_fingerprint=after,
        normalized_facts_fingerprint=(
            owner.normalized_facts_fingerprint
            if observed_baseline
            else fp(f"candidate-facts:{candidate_id}")
        ),
        retained_element_inventory_fingerprint=canonical_fingerprint(retained),
        hard_semantics=tuple(semantics.items()),
        retained_elements=tuple(retained.items()),
        necessity_witnesses=witnesses,
        rewrite_rule_ids=rewrite_rule_ids,
        affected_element_ids=("state:intermediate",) if rewrite_rule_ids else (),
        required_validation_ids=("validation:behavior",),
        evidence_fingerprints=(fp(f"candidate-evidence:{candidate_id}"),),
        cost=cost(after, candidate_id, values) if values is not None else None,
        lane="observed" if observed_baseline else lane,
        current=current,
    )


def deep_review(
    owner: PathQualitySubject,
    candidates: tuple[PathCandidate, ...],
    **kwargs: object,
) -> PathQualityResult:
    trigger_ids = tuple(kwargs.get("trigger_ids", ()))
    kwargs.setdefault(
        "trigger_evidence",
        {trigger_id: fp(f"trigger:{trigger_id}") for trigger_id in trigger_ids},
    )
    kwargs.setdefault("trigger_currentness_id", owner.currentness_id)
    kwargs.setdefault("active_obligation_ids", active_obligations_for(clean_facts()))
    if kwargs.get("candidate_set_exhausted") is True:
        kwargs.setdefault("expected_candidate_ids", tuple(sorted(row.candidate_id for row in candidates)))
        kwargs.setdefault("candidate_exhaustion_evidence_fingerprint", fp("candidate-exhaustion"))
        kwargs.setdefault("candidate_exhaustion_currentness_id", owner.currentness_id)
    if kwargs.get("rewrite_set_exhausted") is True:
        kwargs.setdefault("rewrite_currentness_id", owner.currentness_id)
    return evaluate_deep_path_review(owner, candidates, **kwargs)  # type: ignore[arg-type]


def clean_review(owner: PathQualitySubject | None = None, **kwargs: object) -> PathQualityResult:
    model_facts = clean_facts()
    owner = owner or subject(_model_facts=model_facts)
    return lightweight_path_review(
        owner,
        model_facts,
        necessity_witnesses=witnesses_for(owner, model_facts),
        active_obligation_ids=active_obligations_for(model_facts),
        **kwargs,
    )


def clean_facts() -> dict[str, object]:
    return {
        "states": [
            {"id": "start", "initial": True},
            {"id": "done", "terminal": True},
        ],
        "transitions": [
            {
                "id": "finish",
                "source": "start",
                "target": "done",
                "trigger": "request",
                "guard": "authorized",
                "outputs": ["result"],
                "effects": ["emit_result"],
            }
        ],
        "fields": [],
        "function_blocks": [],
        "outputs": [{"id": "result", "terminal": True}],
        "validations": [
            {
                "id": "validate-result",
                "obligation_id": "obligation:result",
                "oracle_id": "oracle:result",
                "subject_fingerprint": fp("validation-subject"),
                "evidence_boundary_id": "boundary:result",
            }
        ],
        "owners": [
            {
                "id": "owner:order",
                "intent_id": "intent:order",
                "boundary_id": "behavior:order",
                "current": True,
            }
        ],
    }


def test_path_quality_material_review_closes_exact_current_compact_bundle() -> None:
    owner = subject()
    result = clean_review(owner)

    review = review_path_quality_material(
        (owner.model_id,),
        (owner,),
        (result,),
        expected_currentness_id=owner.currentness_id,
        expected_model_fingerprints={owner.model_id: owner.model_fingerprint},
        require_exact_currentness=True,
        require_exact_model_fingerprints=True,
    )

    assert isinstance(review, PathQualityMaterialReview)
    assert review.ok
    assert review.verified_model_ids == (owner.model_id,)
    assert review.blocked_model_ids == ()
    assert review.result_set_fingerprint == path_quality_result_set_fingerprint(
        (owner.model_id,),
        (owner,),
        (result,),
    )
    compact = review.to_compact_dict()
    assert compact["subject_fingerprints"] == [owner.fingerprint]
    assert compact["result_fingerprints"] == [result.fingerprint]
    assert "candidate_bodies" not in compact
    assert "necessity_witnesses" not in compact


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("missing", "path_quality_result_missing"),
        ("stale", "path_quality_result_stale"),
        ("unresolved", "path_quality_result_unresolved"),
        ("foreign_currentness", "path_quality_result_currentness_mismatch"),
        ("foreign_model", "path_quality_subject_model_fingerprint_mismatch"),
        ("normative", "path_quality_normative_target_not_observed"),
    ),
)
def test_path_quality_material_review_blocks_non_current_or_non_observed_closure(
    mutation: str,
    expected_code: str,
) -> None:
    owner = subject()
    result = clean_review(owner)
    results: tuple[PathQualityResult, ...] = (result,)
    expected_model_fingerprint = owner.model_fingerprint
    if mutation == "missing":
        results = ()
    elif mutation == "stale":
        results = (replace(result, current=False),)
    elif mutation == "unresolved":
        results = (
            replace(
                result,
                conclusion="unresolved",
                unresolved_ids=("gap:path-quality",),
            ),
        )
    elif mutation == "foreign_currentness":
        results = (replace(result, currentness_id="revision:foreign"),)
    elif mutation == "foreign_model":
        expected_model_fingerprint = fp("different-current-model")
    elif mutation == "normative":
        observed = candidate(
            owner,
            "observed",
            {"steps": 2, "latency": 7},
            observed_baseline=True,
        )
        target = candidate(owner, "target", {"steps": 1, "latency": 5})
        results = (
            deep_review(
                owner,
                (observed, target),
                baseline_candidate_id="observed",
                trigger_ids=("multiple_hard_equivalent_candidates",),
                comparison_boundary_id="boundary:normative",
                required_cost_dimensions=("steps", "latency"),
            ),
        )

    review = review_path_quality_material(
        (owner.model_id,),
        (owner,),
        results,
        expected_currentness_id=owner.currentness_id,
        expected_model_fingerprints={owner.model_id: expected_model_fingerprint},
        require_exact_currentness=True,
        require_exact_model_fingerprints=True,
    )

    assert not review.ok
    assert owner.model_id in review.blocked_model_ids
    assert expected_code in {gap.code for gap in review.gaps}


def test_five_records_are_frozen_strict_roundtrippable_and_deterministic() -> None:
    owner = subject()
    retained_witness = witness(owner, "witness:start", "start")
    path_cost = cost(fp("candidate-model:only"), "only", {"steps": 2, "latency": 5})
    path_candidate = PathCandidate(
        candidate_id="only",
        subject_fingerprint=owner.fingerprint,
        before_model_fingerprint=owner.model_fingerprint,
        after_model_fingerprint=fp("candidate-model:only"),
        normalized_facts_fingerprint=fp("candidate-facts:only"),
        retained_element_inventory_fingerprint=canonical_fingerprint({"start": "state"}),
        hard_semantics=tuple(reversed(tuple(hard_semantics().items()))),
        retained_elements=(("start", "state"),),
        necessity_witnesses=(retained_witness,),
        cost=path_cost,
        evidence_fingerprints=(fp("candidate-evidence"),),
    )
    result = clean_review(owner)

    assert PathQualitySubject.from_dict(owner.to_dict()) == owner
    assert PathCostVector.from_dict(path_cost.to_dict()) == path_cost
    assert NecessityWitness.from_dict(retained_witness.to_dict()) == retained_witness
    assert PathCandidate.from_dict(path_candidate.to_dict()) == path_candidate
    assert PathQualityResult.from_dict(result.to_dict()) == result
    assert owner.to_json() == owner.to_json()
    assert path_candidate.to_json() == path_candidate.to_json()
    with pytest.raises(FrozenInstanceError):
        owner.model_id = "changed"  # type: ignore[misc]


def test_fingerprints_ignore_mapping_insertion_order_and_reject_stale_projection() -> None:
    assert canonical_fingerprint({"b": 2, "a": 1}) == canonical_fingerprint({"a": 1, "b": 2})
    owner = subject()
    payload = owner.to_dict()
    payload["model_id"] = "workflow.changed"
    with pytest.raises(ValueError, match="fingerprint is stale"):
        PathQualitySubject.from_dict(payload)
    payload = owner.to_dict()
    payload["extra"] = True
    with pytest.raises(ValueError, match="fields mismatch"):
        PathQualitySubject.from_dict(payload)


def test_invalid_records_reject_unknown_schema_incomplete_semantics_and_bad_measurement() -> None:
    with pytest.raises(ValueError, match="current schema"):
        subject(schema_version="flowguard.model-path-quality.v0")
    with pytest.raises(ValueError, match="hard_semantics is incomplete"):
        PathCandidate(
            candidate_id="bad",
            subject_fingerprint=subject().fingerprint,
            before_model_fingerprint=fp("before"),
            after_model_fingerprint=fp("after"),
            normalized_facts_fingerprint=fp("facts"),
            retained_element_inventory_fingerprint=canonical_fingerprint({}),
            hard_semantics=(("outputs", fp("outputs")),),
            retained_elements=(),
        )
    with pytest.raises(ValueError, match="measurement_units"):
        PathCostVector(
            measurement_id="bad-cost",
            subject_fingerprint=fp("path"),
            currentness_id="revision:1",
            steps=1,
            measurement_evidence={"steps": fp("measure")},
        )
    with pytest.raises(ValueError, match="finite non-negative"):
        cost(fp("path"), "bad", {"steps": float("nan")})


def test_ordinary_review_returns_compact_single_clear_path_without_deep_payload() -> None:
    result = clean_review()
    payload = result.to_compact_dict()
    assert result.conclusion == "single_clear_path"
    assert result.mode == "lightweight"
    assert result.trigger_ids == ()
    assert result.candidate_ids == ()
    assert result.candidate_set_fingerprint == ""
    assert result.rewrite_set_fingerprint == ""
    assert "candidates" not in payload
    assert "necessity_witnesses" not in payload
    assert "cost" not in payload
    assert len(result.to_json()) < 2_000


def test_lightweight_review_reports_every_required_structural_finding() -> None:
    facts = {
        "states": [
            {"id": "start", "initial": True},
            {"id": "loop", "behaviorally_relevant": False},
            {"id": "dead"},
        ],
        "transitions": [
            {
                "id": "enter",
                "source": "start",
                "target": "loop",
                "trigger": "go",
                "guard": "allowed",
                "outputs": ["intermediate"],
                "state_updates": ["unused_field"],
                "effects": ["record"],
            },
            {
                "id": "enter-copy",
                "source": "start",
                "target": "loop",
                "trigger": "go",
                "guard": "allowed",
                "outputs": ["intermediate"],
                "state_updates": ["unused_field"],
                "effects": ["record"],
            },
            {"id": "spin", "source": "loop", "target": "loop", "trigger": "again"},
            {"id": "dead-spin", "source": "dead", "target": "dead", "trigger": "never"},
        ],
        "fields": [{"id": "unused_field", "declared": True, "writes_by": ["enter"]}],
        "function_blocks": [
            {
                "id": "forward",
                "inputs": ["input"],
                "outputs": ["input"],
                "state_input": "same",
                "state_output": "same",
            }
        ],
        "outputs": [{"id": "intermediate", "producer_id": "enter", "terminal": False}],
        "validations": [
            {
                "id": "validation-a",
                "obligation_id": "obligation:a",
                "oracle_id": "oracle:a",
                "subject_fingerprint": fp("validation-subject"),
                "evidence_boundary_id": "boundary:a",
            },
            {
                "id": "validation-b",
                "obligation_id": "obligation:a",
                "oracle_id": "oracle:a",
                "subject_fingerprint": fp("validation-subject"),
                "evidence_boundary_id": "boundary:a",
            },
        ],
        "owners": [
            {"id": "owner-a", "intent_id": "intent:a", "boundary_id": "boundary:a"},
            {"id": "owner-b", "intent_id": "intent:a", "boundary_id": "boundary:a"},
        ],
    }
    findings = find_lightweight_findings(facts)
    kinds = {finding.split(":", 1)[0] for finding in findings}
    assert {
        "unreachable_state",
        "unreachable_transition",
        "duplicate_transition",
        "behavior_irrelevant_state",
        "behavior_irrelevant_field",
        "pass_through_function_block",
        "unconsumed_output",
        "repeated_validation",
        "duplicate_current_owner",
        "no_progress_loop",
    } <= kinds
    result = lightweight_path_review(subject(_model_facts=facts), facts)
    assert result.conclusion == "unresolved"
    assert result.trigger_ids


def test_no_progress_loop_accepts_progress_retry_or_external_wait_boundary() -> None:
    for protection in (
        {"progress_measure": "remaining_items"},
        {"bounded_retry": True},
        {"external_wait": True},
    ):
        facts = {
            "states": [{"id": "wait", "initial": True}],
            "transitions": [
                {"id": "cycle", "source": "wait", "target": "wait", **protection}
            ],
        }
        assert not any(
            finding.startswith("no_progress_loop:")
            for finding in find_lightweight_findings(facts)
        )


def test_every_deep_trigger_is_exact_and_affected_model_scoped() -> None:
    triggers = collect_deep_review_triggers(
        (
            "unreachable_state:dead",
            "duplicate_transition:a:b",
            "pass_through_function_block:forward",
            "unconsumed_output:unused",
            "repeated_validation:a:b",
            "no_progress_loop:loop",
        ),
        explicit_request=True,
        declared_candidate_count=2,
        prior_counts={"states": 1, "transitions": 1, "branches": 1},
        current_counts={"states": 3, "transitions": 3, "branches": 3},
        growth_thresholds={"states": 1, "transitions": 1, "branches": 1},
        path_design_model_miss=True,
        missing_necessity_witness=True,
        high_cost_boundary=True,
        release_critical_boundary=True,
    )
    assert {
        "explicit_request",
        "multiple_hard_equivalent_candidates",
        "material_states_growth",
        "material_transitions_growth",
        "material_branches_growth",
        "path_design_model_miss",
        "missing_necessity_witness",
        "high_cost_boundary",
        "release_critical_boundary",
        "structural:unreachable_state",
        "structural:duplicate_transition",
        "structural:pass_through_function_block",
        "structural:unconsumed_output",
        "structural:repeated_validation",
        "structural:no_progress_loop",
    } <= set(triggers)
    assert collect_deep_review_triggers(()) == ()


def test_explicit_trigger_does_not_materialize_candidates_in_lightweight_result() -> None:
    result = clean_review(explicit_deep_request=True)
    assert result.conclusion == "unresolved"
    assert result.trigger_ids == ("explicit_request",)
    assert result.candidate_ids == ()
    assert result.candidate_set_fingerprint == ""
    assert "candidates" not in result.to_compact_dict()


def test_measured_cost_requires_current_evidence_and_admits_deep_review() -> None:
    model_facts = clean_facts()
    owner = subject(_model_facts=model_facts)
    measurement = fp("cost-measurement")
    result = lightweight_path_review(
        owner,
        model_facts,
        necessity_witnesses=witnesses_for(owner, model_facts),
        active_obligation_ids=active_obligations_for(model_facts),
        measured_costs={"steps": 64},
        cost_thresholds={"steps": 64},
        cost_evidence={"steps": measurement},
        trigger_evidence={
            "high_cost_boundary": fp("trigger:high-cost"),
        },
        trigger_currentness_id=owner.currentness_id,
    )
    assert result.optimization_depth == "deep_required"
    assert result.trigger_ids == ("high_cost_boundary",)
    assert result.cost_measurements == (("steps", 64.0),)
    assert result.cost_detail_evidence_fingerprint.startswith("sha256:")
    assert result.trigger_evidence_fingerprint.startswith("sha256:")
    assert "deep_review_required:high_cost_boundary" in result.unresolved_ids


def test_necessity_witness_validation_rejects_missing_duplicate_stale_and_circular_rows() -> None:
    owner = subject()
    retained = {"state:a": "state", "state:b": "state"}
    duplicate_a = (
        witness(owner, "witness:a1", "state:a"),
        witness(owner, "witness:a2", "state:a"),
    )
    gaps = validate_necessity_witnesses(owner, retained, duplicate_a)
    assert "duplicate_necessity_witness:state:a" in gaps
    assert "missing_necessity_witness:state:b" in gaps

    stale = witness(owner, "witness:stale", "state:a", current=False)
    gaps = validate_necessity_witnesses(owner, {"state:a": "state"}, (stale,))
    assert "stale_witness:witness:stale" in gaps

    circular = (
        witness(owner, "witness:a", "state:a", depends_on=("witness:b",)),
        witness(owner, "witness:b", "state:b", depends_on=("witness:a",)),
    )
    gaps = validate_necessity_witnesses(owner, retained, circular)
    assert any(gap.startswith("circular_witness:") for gap in gaps)


def test_necessity_witness_rejects_stale_subject_evidence_and_self_licensing() -> None:
    owner = subject()
    wrong_subject = witness(
        owner,
        "witness:wrong-subject",
        "state:a",
        subject_fingerprint=fp("other-subject"),
    )
    wrong_evidence = witness(
        owner,
        "witness:wrong-evidence",
        "state:b",
        evidence_currentness_id="revision:old",
    )
    gaps = validate_necessity_witnesses(
        owner,
        {"state:a": "state", "state:b": "state"},
        (wrong_subject, wrong_evidence),
    )
    assert "stale_witness_subject:witness:wrong-subject" in gaps
    assert "stale_witness_evidence:witness:wrong-evidence" in gaps
    with pytest.raises(ValueError, match="cannot be self-description"):
        NecessityWitness(
            witness_id="witness:self",
            subject_fingerprint=owner.fingerprint,
            element_id="state:self",
            element_kind="state",
            obligation_id="obligation:self",
            counterexample_id="counterexample:self",
            oracle_id="oracle:self",
            evidence_fingerprint=fp("self"),
            evidence_currentness_id=owner.currentness_id,
            evidence_kind="path_quality_result",
        )


def test_hard_semantic_mismatch_is_never_ranked_as_a_cheaper_equivalent() -> None:
    owner = subject()
    baseline = candidate(owner, "baseline", {"steps": 3}, observed_baseline=True)
    changed = candidate(
        owner,
        "changed",
        {"steps": 1},
        semantic_overrides={"side_effects": fp("different-effects")},
    )
    assert hard_semantic_mismatches(baseline, changed) == ("side_effects",)
    result = deep_review(
        owner,
        (baseline, changed),
        baseline_candidate_id="baseline",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:finite-two",
        required_cost_dimensions=("steps",),
    )
    assert result.conclusion == "unresolved"
    assert "normative_target_semantic_change:changed:side_effects" in result.unresolved_ids
    assert result.selected_candidate_id == ""


def test_normative_semantic_change_remains_explicit_and_does_not_replace_observed() -> None:
    owner = subject()
    baseline = candidate(owner, "observed", {"steps": 3}, observed_baseline=True)
    target = candidate(
        owner,
        "target",
        {"steps": 1},
        semantic_overrides={"outputs": fp("desired-new-output")},
        lane="normative_target",
    )
    result = deep_review(
        owner,
        (baseline, target),
        baseline_candidate_id="observed",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:normative",
        required_cost_dimensions=("steps",),
    )
    assert result.conclusion == "unresolved"
    assert "normative_target_semantic_change:target:outputs" in result.unresolved_ids


def test_pareto_tradeoff_is_non_dominated_without_scalar_sum() -> None:
    owner = subject()
    quick_steps = candidate(
        owner,
        "quick-steps",
        {"steps": 1, "latency": 10},
        observed_baseline=True,
    )
    quick_latency = candidate(owner, "quick-latency", {"steps": 2, "latency": 5})
    assert compare_cost_vectors(
        quick_steps.cost,  # type: ignore[arg-type]
        quick_latency.cost,  # type: ignore[arg-type]
        ("steps", "latency"),
    ) == "tradeoff"
    result = deep_review(
        owner,
        (quick_steps, quick_latency),
        baseline_candidate_id="quick-steps",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:pareto",
        required_cost_dimensions=("steps", "latency"),
    )
    assert result.conclusion == "non_dominated_within_boundary"
    assert result.selected_candidate_id == ""
    assert "total" not in quick_steps.cost.to_dict()  # type: ignore[union-attr]


def test_unique_dominating_candidate_is_minimum_only_for_exhausted_finite_set() -> None:
    owner = subject()
    smaller = candidate(owner, "smaller", {"steps": 1, "latency": 5})
    larger = candidate(owner, "larger", {"steps": 2, "latency": 7}, observed_baseline=True)
    preferred = deep_review(
        owner,
        (larger, smaller),
        baseline_candidate_id="larger",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:named",
        required_cost_dimensions=("steps", "latency"),
    )
    assert preferred.conclusion == "preferred_within_candidates"
    assert preferred.selected_candidate_id == "smaller"
    assert preferred.selected_candidate_lane == "normative_target"

    minimum = deep_review(
        owner,
        (larger, smaller),
        baseline_candidate_id="larger",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:finite-exhausted",
        required_cost_dimensions=("steps", "latency"),
        candidate_set_exhausted=True,
    )
    assert minimum.conclusion == "minimum_within_exhausted_finite_set"
    assert minimum.selected_candidate_id == "smaller"
    assert "finite" in bounded_conclusion_text(minimum)


def test_exhausted_current_rewrite_evidence_licenses_only_local_irreducibility() -> None:
    owner = subject()
    only = candidate(owner, "current", None, observed_baseline=True)
    result = deep_review(
        owner,
        (only,),
        baseline_candidate_id="current",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:declared-rewrites",
        rewrite_rule_ids=("remove_unreachable", "collapse_pass_through"),
        rewrite_dispositions={
            "remove_unreachable": "rejected",
            "collapse_pass_through": "rejected",
        },
        rewrite_evidence={
            "remove_unreachable": fp("rewrite-evidence:unreachable"),
            "collapse_pass_through": fp("rewrite-evidence:pass-through"),
        },
        rewrite_set_exhausted=True,
    )
    assert result.conclusion == "locally_irreducible_under_declared_rewrites"
    assert result.rewrite_set_exhausted
    assert "declared exhausted rewrite rules" in bounded_conclusion_text(result)


def test_ties_remain_non_dominated_or_unresolved_when_a_choice_is_required() -> None:
    owner = subject()
    left = candidate(owner, "left", {"steps": 2, "latency": 4}, observed_baseline=True)
    right = candidate(owner, "right", {"steps": 2, "latency": 4})
    non_dominated = deep_review(
        owner,
        (left, right),
        baseline_candidate_id="left",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:tie",
        required_cost_dimensions=("steps", "latency"),
    )
    assert non_dominated.conclusion == "non_dominated_within_boundary"
    unresolved = deep_review(
        owner,
        (left, right),
        baseline_candidate_id="left",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:tie-choice",
        required_cost_dimensions=("steps", "latency"),
        choice_required=True,
    )
    assert unresolved.conclusion == "unresolved"
    assert "non_dominated_choice_unresolved" in unresolved.unresolved_ids


def test_missing_or_differently_measured_cost_dimensions_remain_unresolved() -> None:
    owner = subject()
    complete = candidate(owner, "complete", {"steps": 1, "latency": 3}, observed_baseline=True)
    missing = candidate(owner, "missing", {"steps": 2})
    result = deep_review(
        owner,
        (complete, missing),
        baseline_candidate_id="complete",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:missing",
        required_cost_dimensions=("steps", "latency"),
    )
    assert result.conclusion == "unresolved"
    assert "cost_measurement_missing:missing:latency" in result.unresolved_ids

    different_unit_after = fp("candidate-model:different-unit")
    different_unit = PathCandidate(
        candidate_id="different-unit",
        subject_fingerprint=owner.fingerprint,
        before_model_fingerprint=owner.model_fingerprint,
        after_model_fingerprint=different_unit_after,
        normalized_facts_fingerprint=fp("candidate-facts:different-unit"),
        retained_element_inventory_fingerprint=canonical_fingerprint({}),
        hard_semantics=tuple(hard_semantics().items()),
        retained_elements=(),
        cost=cost(
            different_unit_after,
            "different-unit",
            {"latency": 1},
            units={"latency": "seconds"},
        ),
    )
    milliseconds = candidate(owner, "milliseconds", {"latency": 100})
    assert compare_cost_vectors(
        different_unit.cost,  # type: ignore[arg-type]
        milliseconds.cost,  # type: ignore[arg-type]
        ("latency",),
    ) == "incomparable"


def test_missing_witness_and_stale_candidate_identities_block_deep_result() -> None:
    owner = subject()
    missing = candidate(
        owner,
        "missing-witness",
        {"steps": 1},
        retained_elements={"state:required": "state"},
        observed_baseline=True,
    )
    stale = candidate(
        owner,
        "stale",
        {"steps": 2},
        current=False,
        subject_fingerprint=fp("old-subject"),
    )
    result = deep_review(
        owner,
        (missing, stale),
        baseline_candidate_id="missing-witness",
        trigger_ids=("missing_necessity_witness",),
        comparison_boundary_id="boundary:stale",
        required_cost_dimensions=("steps",),
    )
    assert result.conclusion == "unresolved"
    assert "missing_necessity_witness:state:required" in result.unresolved_ids
    assert "stale_candidate:stale" in result.unresolved_ids
    assert "stale_candidate_subject:stale" in result.unresolved_ids


def test_rewrite_exhaustion_requires_complete_current_dispositions_and_evidence() -> None:
    owner = subject()
    only = candidate(owner, "current", None, observed_baseline=True)
    result = deep_review(
        owner,
        (only,),
        baseline_candidate_id="current",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:incomplete-rewrites",
        rewrite_rule_ids=("remove_unreachable",),
        rewrite_dispositions={},
        rewrite_evidence={},
        rewrite_set_exhausted=True,
    )
    assert result.conclusion == "unresolved"
    assert "rewrite_disposition_incomplete" in result.unresolved_ids
    assert "rewrite_evidence_incomplete" in result.unresolved_ids


def test_global_optimum_conclusion_is_rejected_directly() -> None:
    compact = clean_review().to_dict()
    compact["conclusion"] = "global_optimum"
    compact["fingerprint"] = fp("irrelevant-stale-fingerprint")
    with pytest.raises(ValueError, match="bounded licensed vocabulary"):
        PathQualityResult.from_dict(compact)


def test_provider_neutral_facts_require_no_python_or_source_language_fields() -> None:
    process_facts = {
        "states": [
            {"id": "submitted", "initial": True},
            {"id": "approved", "terminal": True},
        ],
        "transitions": [
            {
                "id": "approve",
                "source": "submitted",
                "target": "approved",
                "trigger": "manager_approval",
                "outputs": ["approval_notice"],
                "effects": ["notify_requester"],
            }
        ],
        "outputs": [{"id": "approval_notice", "terminal": True}],
    }
    owner = subject(model_id="process.approval", _model_facts=process_facts)
    result = lightweight_path_review(
        owner,
        process_facts,
        necessity_witnesses=witnesses_for(owner, process_facts),
        active_obligation_ids=active_obligations_for(process_facts),
    )
    assert result.conclusion == "single_clear_path"
    assert "python" not in result.to_json().lower()


def test_empty_or_witnessless_fact_sets_cannot_claim_one_clear_path() -> None:
    empty_owner = subject(_model_facts={}, _active_obligation_ids=())
    empty = lightweight_path_review(empty_owner, {})
    assert empty.conclusion == "unresolved"
    assert "provider_fact_missing:model_elements" in empty.unresolved_ids

    facts = clean_facts()
    owner = subject(_model_facts=facts)
    witnessless = lightweight_path_review(owner, facts)
    assert witnessless.conclusion == "unresolved"
    assert "active_obligation_inventory_missing" in witnessless.unresolved_ids
    assert any(
        gap.startswith("missing_necessity_witness:") for gap in witnessless.unresolved_ids
    )


def test_caller_cannot_shrink_the_retained_element_denominator() -> None:
    facts = clean_facts()
    owner = subject(_model_facts=facts)
    result = lightweight_path_review(
        owner,
        facts,
        retained_elements={},
        active_obligation_ids=active_obligations_for(facts),
    )
    assert result.conclusion == "unresolved"
    assert "retained_element_inventory_mismatch" in result.unresolved_ids


def test_normalized_facts_are_current_and_row_order_is_not_authoritative() -> None:
    facts = clean_facts()
    owner = subject(_model_facts=facts)
    baseline = clean_review(owner)

    reordered = dict(facts)
    reordered["states"] = list(reversed(facts["states"]))  # type: ignore[index]
    reordered_result = lightweight_path_review(
        owner,
        reordered,
        necessity_witnesses=witnesses_for(owner, reordered),
        active_obligation_ids=active_obligations_for(reordered),
    )
    assert reordered_result.fingerprint == baseline.fingerprint

    changed = clean_facts()
    changed["transitions"][0]["trigger"] = "different"  # type: ignore[index]
    changed_result = lightweight_path_review(
        owner,
        changed,
        necessity_witnesses=witnesses_for(owner, changed),
        active_obligation_ids=active_obligations_for(changed),
    )
    assert changed_result.conclusion == "unresolved"
    assert "stale_normalized_model_facts" in changed_result.unresolved_ids


def test_currentness_cannot_be_overridden_outside_the_subject() -> None:
    facts = clean_facts()
    owner = subject(_model_facts=facts)
    with pytest.raises(TypeError, match="currentness_id"):
        lightweight_path_review(
            owner,
            facts,
            currentness_id="revision:other",  # type: ignore[call-arg]
        )


def test_deep_trigger_requires_known_current_evidence() -> None:
    owner = subject()
    baseline = candidate(owner, "baseline", {"steps": 2}, observed_baseline=True)
    target = candidate(owner, "target", {"steps": 1})
    with pytest.raises(ValueError, match="unknown triggers"):
        evaluate_deep_path_review(
            owner,
            (baseline, target),
            baseline_candidate_id="baseline",
            trigger_ids=("banana",),
            trigger_evidence={"banana": fp("banana")},
            trigger_currentness_id=owner.currentness_id,
            comparison_boundary_id="boundary:invalid-trigger",
            required_cost_dimensions=("steps",),
        )
    stale = deep_review(
        owner,
        (baseline, target),
        baseline_candidate_id="baseline",
        trigger_ids=("explicit_request",),
        trigger_evidence={},
        trigger_currentness_id="revision:old",
        comparison_boundary_id="boundary:stale-trigger",
        required_cost_dimensions=("steps",),
    )
    assert stale.conclusion == "unresolved"
    assert "trigger_evidence_incomplete" in stale.unresolved_ids
    assert "trigger_evidence_stale" in stale.unresolved_ids


def test_declared_candidate_count_must_be_an_integer() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        collect_deep_review_triggers((), declared_candidate_count=1.5)  # type: ignore[arg-type]


def test_observed_baseline_must_bind_the_current_model_and_facts() -> None:
    owner = subject()
    wrong = candidate(owner, "wrong", {"steps": 2}, lane="observed")
    target = candidate(owner, "target", {"steps": 1})
    result = deep_review(
        owner,
        (wrong, target),
        baseline_candidate_id="wrong",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:wrong-baseline",
        required_cost_dimensions=("steps",),
    )
    assert result.conclusion == "unresolved"
    assert "baseline_not_current_model:wrong" in result.unresolved_ids
    assert "baseline_facts_mismatch:wrong" in result.unresolved_ids

    current = candidate(owner, "current", {"steps": 2}, observed_baseline=True)
    stale_before = replace(target, before_model_fingerprint=fp("old-model"))
    result = deep_review(
        owner,
        (current, stale_before),
        baseline_candidate_id="current",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:stale-before",
        required_cost_dimensions=("steps",),
    )
    assert "stale_candidate_before_model:target" in result.unresolved_ids


def test_candidate_exhaustion_requires_independent_current_evidence() -> None:
    owner = subject()
    baseline = candidate(owner, "baseline", {"steps": 2}, observed_baseline=True)
    target = candidate(owner, "target", {"steps": 1})
    result = deep_review(
        owner,
        (baseline, target),
        baseline_candidate_id="baseline",
        trigger_ids=("multiple_hard_equivalent_candidates",),
        comparison_boundary_id="boundary:self-declared-exhaustion",
        required_cost_dimensions=("steps",),
        candidate_set_exhausted=True,
        expected_candidate_ids=(),
        candidate_exhaustion_evidence_fingerprint="",
        candidate_exhaustion_currentness_id="",
    )
    assert result.conclusion == "unresolved"
    assert "candidate_inventory_incomplete" in result.unresolved_ids
    assert "candidate_exhaustion_evidence_missing" in result.unresolved_ids
    assert "candidate_exhaustion_evidence_stale" in result.unresolved_ids


def test_applied_rewrite_cannot_self_license_local_irreducibility() -> None:
    owner = subject()
    baseline = candidate(owner, "current", None, observed_baseline=True)
    result = deep_review(
        owner,
        (baseline,),
        baseline_candidate_id="current",
        trigger_ids=("explicit_request",),
        comparison_boundary_id="boundary:unmapped-applied-rewrite",
        rewrite_rule_ids=("remove_unreachable",),
        rewrite_dispositions={"remove_unreachable": "applied"},
        rewrite_evidence={"remove_unreachable": fp("rewrite")},
        rewrite_set_exhausted=True,
    )
    assert result.conclusion == "unresolved"
    assert "applied_rewrite_candidate_missing:remove_unreachable" in result.unresolved_ids


def test_compact_result_rejects_impossible_resolved_combinations() -> None:
    owner = subject()
    with pytest.raises(ValueError, match="at least two candidates"):
        PathQualityResult(
            result_id="path-quality:impossible",
            subject_fingerprint=owner.fingerprint,
            mode="deep",
            trigger_ids=("explicit_request",),
            finding_ids=(),
            candidate_ids=(),
            rewrite_rule_ids=(),
            conclusion="non_dominated_within_boundary",
            unresolved_ids=(),
            selected_candidate_id="",
            selected_candidate_lane="",
            comparison_boundary_id="boundary:impossible",
            candidate_set_fingerprint="",
            rewrite_set_fingerprint="",
            necessity_witness_set_fingerprint=fp("witness-set"),
            detail_evidence_fingerprint=fp("detail"),
            producer_id="model_maturation",
            currentness_id=owner.currentness_id,
        )


def test_normalized_fact_booleans_and_nonfinite_values_fail_visibly() -> None:
    facts = clean_facts()
    facts["states"][0]["initial"] = "yes"  # type: ignore[index]
    with pytest.raises(ValueError, match="must be a boolean"):
        find_lightweight_findings(facts)
    with pytest.raises(ValueError, match="non-finite"):
        canonical_fingerprint({"bad": float("nan")})


def test_wire_records_reject_unknown_triggers_and_ambiguous_empty_costs() -> None:
    owner = subject()
    result_payload = clean_review(owner).to_compact_dict()
    result_payload["trigger_ids"] = ["banana"]
    result_payload["fingerprint"] = fp("irrelevant-stale-fingerprint")
    with pytest.raises(ValueError, match="unknown trigger ids"):
        PathQualityResult.from_dict(result_payload)

    candidate_payload = candidate(owner, "target", None).to_dict()
    candidate_payload["cost"] = {}
    candidate_payload["fingerprint"] = fp("irrelevant-stale-fingerprint")
    with pytest.raises(ValueError, match="fields mismatch"):
        PathCandidate.from_dict(candidate_payload)
