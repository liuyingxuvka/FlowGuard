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


def test_empty_facts_block_but_ordinary_review_does_not_require_witnesses() -> None:
    empty_owner = subject(_model_facts={}, _active_obligation_ids=())
    empty = lightweight_path_review(empty_owner, {})
    assert empty.conclusion == "unresolved"
    assert "provider_fact_missing:model_elements" in empty.unresolved_ids

    facts = clean_facts()
    owner = subject(_model_facts=facts)
    witnessless = lightweight_path_review(owner, facts)
    assert witnessless.conclusion == "single_clear_path"
    assert witnessless.unresolved_ids == ()
    assert witnessless.necessity_witness_set_fingerprint == canonical_fingerprint([])


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

# R6 pure-kernel fixtures. Receipt admission is tested separately; these rows
# represent its mocked terminal projection, never native validation evidence.
from flowguard.model_path_quality import (
    ArchitectureResponsibilityFact, DeclaredPathQualitySource,
    PathQualityGapProjection, PathQualityArchitectureDetail,
    ResponsibilitySemanticEvidenceReview,
    compile_declared_path_quality_source, verify_declared_path_quality_source,
    verify_declared_source_scope_coverage, verify_responsibility_semantic_evidence,
    derive_architecture_relation_candidates, evaluate_architecture_objectives,
)
from flowguard.model_intent import ArchitectureObjective, BoundArchitectureObjective


def _r6_fact(name="A", *, model=None, classes=("class:accepted",), owner="owner:service", layer="layer:service", semantics=None, contract=None):
    return ArchitectureResponsibilityFact(
        responsibility_id=f"responsibility:{name}", model_id=model or f"model:{name}",
        element_ids=(f"element:{name}",), owner_id=owner, boundary_id="boundary:writer",
        layer_id=layer, applicable_input_class_ids=classes,
        hard_semantics=semantics or {x: {"contract": x} for x in HARD_SEMANTIC_DIMENSIONS},
        mechanism_id="mechanism:kernel", mechanism_fingerprint=fp("mechanism"),
        owner_code_contract_id=contract or f"contract:{name}", owner_code_contract_fingerprint=fp("contract:" + name),
        semantic_spec_ids=("spec:writer",), semantic_spec_fingerprints=(fp("spec"),),
        oracle_ids=("oracle:writer",), implementation_binding_fingerprint=fp("implementation:" + name),
        source_refs=({"path": "src/writer.py", "source_fingerprint": fp("source")},),
    )


def _r6_review(fact, scope="implementation_boundary"):
    from flowguard.model_path_quality import _responsibility_semantic_review
    return _responsibility_semantic_review(canonical_fingerprint(fact.to_dict()), canonical_fingerprint(fact.hard_semantics), scope, (), (fp("admitted-proof"),), ("relation:" + fact.responsibility_id.rsplit(":", 1)[-1],))


def _r6_objective(kind, facts, values):
    objective = ArchitectureObjective("objective:fixture:" + kind, True,
        tuple(sorted({x.model_id for x in facts})), tuple(sorted(x.responsibility_id for x in facts)),
        ("class:accepted",), kind, values, "owner:service", ("failure:fixture",))
    return BoundArchitectureObjective(objective, "contribution:fixture", fp("source-identity"), "docs/objective.md", fp("source"), fp("complete-intent"))


def _r6_declaration(facts=None, *, scope=None, graph_scope="model_behavior"):
    facts = clean_facts() if facts is None else facts
    refs = ({"path": "model.py", "source_fingerprint": fp("model-source")},)
    return compile_declared_path_quality_source(model_id="model:fixture", model_instance_fingerprint=fp("instance"),
        source_refs=refs, model_facts=facts,
        element_groundings={element: {"kind": "explicit_model_contract"} for element, _ in derive_retained_elements(facts)},
        scope_coverage=scope, graph_scope=graph_scope)


def test_declared_graph_keeps_unobserved_and_unreachable_elements():
    facts = clean_facts()
    facts["states"].extend([{"id": "state:rare", "terminal": True}, {"id": "state:dead"}])
    facts["transitions"].append({"id": "transition:rare", "source": "state:start", "target": "state:rare", "trigger": "rare"})
    source = _r6_declaration(facts)
    assert {"state:rare", "state:dead"} <= set(source.declared_element_ids)
    assert "unreachable_state:state:dead" in find_lightweight_findings(source.model_facts)
    assert "coverage" not in source.model_facts["states"][-1]


def test_trace_is_not_declared_graph_authority():
    with pytest.raises(ValueError, match="declared_source_missing"):
        compile_declared_path_quality_source(model_id="model:fixture", model_instance_fingerprint=fp("instance"), source_refs=[{"path": "model.py", "source_fingerprint": fp("source")}])
    source = _r6_declaration()
    payload = source.to_dict()
    payload["declared_element_ids"] = payload["declared_element_ids"][:-1]
    with pytest.raises(ValueError, match="declared_denominator_mismatch"):
        DeclaredPathQualitySource.from_dict(payload)


def test_declared_source_groundings_are_exact_current():
    source = _r6_declaration()
    for change in ("foreign", "stale", "unmapped"):
        payload = source.to_dict()
        element = source.declared_element_ids[0]
        if change == "foreign": payload["element_groundings"][element]["source_ref"] = "other.py"
        elif change == "stale": payload["element_groundings"][element]["source_fingerprint"] = fp("stale")
        else: del payload["element_groundings"][element]
        with pytest.raises(ValueError): DeclaredPathQualitySource.from_dict(payload)


def test_check_contract_does_not_license_software_architecture():
    source = compile_declared_path_quality_source(model_id="model:fixture", model_instance_fingerprint=fp("instance"),
        source_refs=[{"path": "model.py", "source_fingerprint": fp("source")}], graph_scope="native_check_contract", declared_contracts={"check:exact": {"obligations": ["obligation:known"]}})
    assert source.model_facts["states"] == []
    assert source.scope_coverage["claim_scope"] == "declared_model"
    scope = dict(source.scope_coverage, claim_scope="software_architecture")
    claimed = replace(source, scope_coverage=scope)
    assert verify_declared_source_scope_coverage(claimed) == ("implementation_scope_coverage_missing",)


def test_self_declared_matching_hashes_do_not_establish_equivalence():
    fact = _r6_fact(semantics=hard_semantics())
    with pytest.raises(TypeError):
        ResponsibilitySemanticEvidenceReview(canonical_fingerprint(fact.to_dict()), fp("caller"), "implementation_boundary", (), (fp("caller"),))
    review = verify_responsibility_semantic_evidence(fact)
    assert not review.ready
    relation = derive_architecture_relation_candidates((fact, _r6_fact("B", semantics=hard_semantics())))
    assert relation["rewrite_candidates"] == []
    assert relation["observation_gap_ids"]


def test_consistent_declared_omission_does_not_close_software_architecture():
    scoped = _r6_declaration()
    assert verify_declared_source_scope_coverage(scoped) == ()
    claimed = replace(scoped, scope_coverage=dict(scoped.scope_coverage, claim_scope="software_architecture"))
    assert "implementation_scope_coverage_missing" in verify_declared_source_scope_coverage(claimed)


def test_model_policy_proof_is_not_implementation_equivalence():
    a, b = _r6_fact(), _r6_fact("B")
    relation = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a, "model_policy"), _r6_review(b, "model_policy")))
    assert not relation["rewrite_candidates"]
    assert relation["observation_gap_ids"]


def test_cross_model_same_semantics_same_context_yields_rewrite_candidate():
    a, b = _r6_fact(), _r6_fact("B")
    relation = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a), _r6_review(b)))
    assert relation["relations"][0]["kind"] == "duplicate_boundary"
    assert relation["finding_ids"] == ["equivalent_responsibility_paths:responsibility:A:responsibility:B"]
    assert relation["relations"][0]["element_ids"] == ["element:A", "element:B"]
    assert relation["rewrite_candidates"][0]["lane"] == "normative_target"


def test_disjoint_context_variants_are_not_merged():
    a, b = _r6_fact(), _r6_fact("B", classes=("class:rejected",))
    relation = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a), _r6_review(b)))
    assert relation["relations"][0]["kind"] == "legitimate_variant"
    assert not relation["finding_ids"] and not relation["rewrite_candidates"]


def test_hard_behavior_difference_is_false_friend():
    a = _r6_fact()
    semantics = dict(a.hard_semantics, permissions={"contract": "denied"}, side_effects={"contract": "write"})
    b = _r6_fact("B", semantics=semantics)
    relation = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a), _r6_review(b)))
    assert relation["relations"][0]["kind"] == "false_friend"
    assert not relation["rewrite_candidates"]


def test_explicit_layer_objective_yields_normative_direction():
    ui = _r6_fact(layer="layer:UI")
    obj = _r6_objective("allowed_layers", (ui,), {"layer_ids": ["layer:service"]})
    result = evaluate_architecture_objectives((obj,), (ui,))
    assert result["improvement_gap_ids"]
    assert result["suggestions"][0]["action"] == "relocate_responsibility"
    assert result["suggestions"][0]["lane"] == "normative_target"
    assert ui.layer_id == "layer:UI"


def test_no_objective_does_not_invent_single_owner():
    result = evaluate_architecture_objectives((), (_r6_fact(owner="owner:UI"), _r6_fact("B")))
    assert result["architecture_objective_status"] == "no_declared_architecture_objective"
    assert not result["suggestions"] and not result["improvement_gap_ids"]


def test_identical_copies_do_not_satisfy_shared_mechanism_objective():
    a, b = _r6_fact(), _r6_fact("B")
    values = {"canonical_mechanism_id": "mechanism:kernel", "canonical_owner_code_contract_id": "contract:kernel", "mechanism_fingerprint": fp("mechanism"), "consumer_responsibility_ids": [a.responsibility_id, b.responsibility_id], "required_delegation_relation_ids": ["relation:A", "relation:B"]}
    obj = _r6_objective("shared_mechanism", (a, b), values)
    assert evaluate_architecture_objectives((obj,), (a, b))["improvement_gap_ids"]


def test_single_primary_with_two_current_delegates_satisfies_shared_mechanism():
    from flowguard.model_test_alignment import CodeContract
    a, b, primary = _r6_fact(), _r6_fact("B"), _r6_fact("kernel", contract="contract:kernel")
    values = {"canonical_mechanism_id": "mechanism:kernel", "canonical_owner_code_contract_id": "contract:kernel", "mechanism_fingerprint": fp("mechanism"), "consumer_responsibility_ids": [a.responsibility_id, b.responsibility_id], "required_delegation_relation_ids": ["relation:A", "relation:B"]}
    obj = _r6_objective("shared_mechanism", (a, b), values)
    contracts = (CodeContract("contract:kernel", path="kernel.py", symbol="write"), *(CodeContract(x.owner_code_contract_id, path=x.model_id + ".py", symbol="delegate", delegates_to_code_contract_id="contract:kernel", delegation_only=True, relation_ids=("relation:" + name,)) for x, name in ((a, "A"), (b, "B"))))
    proofs = {x.responsibility_id: (("relation:" + name, _r6_review(x)),) for x, name in ((a, "A"), (b, "B"))}
    result = evaluate_architecture_objectives((obj,), (a, b, primary), code_contracts=contracts, current_delegation_relation_ids=("relation:A", "relation:B"), delegation_evidence_bindings=proofs)
    assert not result["improvement_gap_ids"] and not result["observation_gap_ids"]
    proofs.pop(b.responsibility_id)
    assert evaluate_architecture_objectives((obj,), (a, b, primary), code_contracts=contracts, current_delegation_relation_ids=("relation:A", "relation:B"), delegation_evidence_bindings=proofs)["improvement_gap_ids"]


def test_wrong_native_owner_case_or_oracle_cannot_prove_semantic_relation():
    from flowguard.model_path_quality import ResponsibilitySemanticEvidenceBinding
    fact = _r6_fact()
    proof = ResponsibilitySemanticEvidenceBinding("accepted_inputs", "class:accepted", "spec:writer", "oracle:writer", fp("native"), "receipt:foreign", fp("receipt"), "owner:foreign", ("case:foreign",), "model_policy")
    review = verify_responsibility_semantic_evidence(replace(fact, semantic_evidence_bindings=(proof,)))
    assert not review.ready
    assert "responsibility_native_binding_invalid" in review.gap_ids


def test_unknown_gap_code_blocks_observation():
    result = replace(lightweight_path_review(subject(), clean_facts()), finding_ids=("unknown_future:element",), unresolved_ids=("unknown_future:element",), conclusion="unresolved")
    assert result.observation_gap_ids == ("unknown_future:element",)
    assert not result.improvement_gap_ids


def test_gap_projection_preserves_existing_result_wire_and_fingerprint():
    result = replace(lightweight_path_review(subject(), clean_facts()), finding_ids=("unreachable_state:dead",), unresolved_ids=("unreachable_state:dead",), conclusion="unresolved")
    before, identity = result.to_dict(), result.fingerprint
    assert result.improvement_gap_ids == ("unreachable_state:dead",)
    assert result.observation_gap_ids == ()
    assert result.to_dict() == before and result.fingerprint == identity
    assert result.schema_version == "flowguard.model-path-quality.v2"
    assert "observation_gap_ids" not in before and "improvement_gap_ids" not in before
    assert PathQualityResult.from_dict(before) == result


def test_architecture_detail_is_computed_once_and_exactly_bound():
    details = []
    result = lightweight_path_review(subject(), clean_facts(), detail_collector=details)
    assert len(details) == 1
    assert details[0].fingerprint == result.detail_evidence_fingerprint
    assert not details[0].binding_errors(subject(), result)
    assert PathQualityArchitectureDetail.from_dict(details[0].to_dict()) == details[0]
    payload = details[0].to_dict()
    payload["body"]["foreign"] = True
    with pytest.raises(ValueError): PathQualityArchitectureDetail.from_dict(payload)


def test_representation_equivalence_uses_same_declared_graph():
    source = _r6_declaration()
    reversed_facts = {key: list(reversed(value)) if isinstance(value, list) else value for key, value in source.model_facts.items()}
    other = _r6_declaration(reversed_facts)
    assert source.fingerprint == other.fingerprint
    assert source.declared_element_ids == other.declared_element_ids
    assert find_lightweight_findings(source.model_facts) == find_lightweight_findings(other.model_facts)


def test_equivalent_provider_representations_do_not_create_method_conflict():
    from flowguard.portable_model import PortableModel
    from flowguard.portable_path_quality import compile_portable_path_quality_facts
    from tests.test_portable_model import sample_model
    model = sample_model()
    # Provider-native object and its exact persisted transport describe the
    # same nondeterministic relation, with all branches still retained.
    facts_a = compile_portable_path_quality_facts(model)
    payload = model.to_dict()
    payload = {key: payload[key] for key in reversed(tuple(payload))}
    facts_b = compile_portable_path_quality_facts(PortableModel.from_dict(payload))
    source_a, source_b = _r6_declaration(facts_a), _r6_declaration(facts_b)
    assert source_a.fingerprint == source_b.fingerprint
    assert source_a.declared_element_ids == source_b.declared_element_ids
    assert len(source_a.model_facts["branches"]) == 1
    assert len(source_a.model_facts["transitions"]) == 2
    assert find_lightweight_findings(source_a.model_facts) == find_lightweight_findings(source_b.model_facts)
    assert not any("method_conflict" in finding for finding in find_lightweight_findings(source_a.model_facts))


def test_unverified_architecture_handoff_cannot_license_variant():
    fact = _r6_fact()
    baseline = derive_architecture_relation_candidates((fact,))
    assert baseline["relations"] == []
    assert baseline["observation_gap_ids"]
    for supplied in (
        {"licensed_adapter_pairs": (("responsibility:A", "responsibility:B"),)},
        {"canonical_relation_handoffs": ({"relation_id": "relation:caller-asserted", "current": True},)},
    ):
        with pytest.raises(ValueError, match="architecture_handoff_evidence_unknown"):
            derive_architecture_relation_candidates((fact,), **supplied)


def _r7_inventory(root, *, second_writer=False):
    from flowguard.implementation_inventory import SoftwareBoundary, ImplementationFileDisposition, build_implementation_surface_inventory, implementation_surface_key
    from flowguard.implementation_inventory_python import discover_python_implementation_surfaces, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID
    from flowguard.source_identity import source_file_fingerprint
    from flowguard.implementation_blueprint import review_model_implementation_bindings
    from tests.test_implementation_blueprint import binding, spec, oracle
    path = root / "src" / "writers.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def W1(store, value):\n    store['value'] = value\n    return value\n" + ("\ndef W2(store, value):\n    store['other'] = value\n    return value\n" if second_writer else ""), encoding="utf-8")
    digest = source_file_fingerprint(path)
    symbols = ("<module>", "W1", "W2") if second_writer else ("<module>", "W1")
    inventory = build_implementation_surface_inventory(root, SoftwareBoundary("boundary:writers", "revision:fixture", production_patterns=("src/**/*.py",)), inventory_id="inventory:writers",
        file_dispositions=(ImplementationFileDisposition("src/writers.py", "production", digest, "model_implementation", "actual finite source", True, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID),),
        surface_dispositions={implementation_surface_key("src/writers.py", symbol): "model_implementation" for symbol in symbols},
        discovery_adapters={PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces}, resolved_manifest=({"path": "src/writers.py", "sha256": digest},))
    rows, specs, oracles = [], [], []
    for surface in inventory.surfaces:
        if surface.symbol == "W2": continue
        element = "element:" + ("module" if surface.symbol == "<module>" else surface.symbol)
        spec_id, oracle_id = "spec:" + surface.symbol, "oracle:" + surface.symbol
        rows.append(replace(binding("binding:" + surface.symbol, element, surface.surface_id, spec_id, oracle_id, implementation_fingerprint=surface.content_fingerprint), implementation_owner_id="model:alpha"))
        specs.append(spec(spec_id, element)); oracles.append(oracle(oracle_id, element))
    report = review_model_implementation_bindings(inventory, required_model_element_ids=tuple(row.model_element_id for row in rows), bindings=tuple(rows), semantic_specs=tuple(specs), oracles=tuple(oracles))
    return inventory, report


def _r7_native_material(root, *, obligations=("element:W1", "element:module"), observed_source_inputs=(), semantic_checks=()):
    import hashlib, json
    from flowguard.evidence_receipts import save_evidence_receipt
    from flowguard.native_case_protocol import NativeCaseBinding
    from tests.test_native_case_protocol import _good_contract, _result
    from tests.test_evidence_receipts import receipt, current_context
    owner_receipt = receipt("receipt:validation-owner:model:alpha:fixture", subject_id="validation-owner:model:alpha", producer_id="validation-owner:model:alpha", covered=obligations)
    contract = replace(_good_contract(), evidence_scope="implementation_boundary")
    if semantic_checks:
        contract = replace(contract, oracle_member_ids=tuple(contract.owner_id + ":" + contract.source_case_id + ":" + dimension for dimension in contract.covered_dimensions))
    raw = root / "native.json"; raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(json.dumps({"fixture": "finite native oracle result",
        "architecture_material": {"observed_source_inputs": list(observed_source_inputs)},
        "semantic_checks": list(semantic_checks)}, sort_keys=True).encode() + b'\n')
    result = replace(_result(contract), result_artifact_fingerprint="sha256:" + hashlib.sha256(raw.read_bytes()).hexdigest(), raw_artifact_path="native.json", environment_fingerprint=owner_receipt.environment_fingerprint)
    if semantic_checks:
        result = replace(result, oracle_results=tuple({**row,
            "oracle_member_id": contract.owner_id + ":" + contract.source_case_id + ":" + row["dimension"],
            **({"observed": {"semantic_checks": list(semantic_checks)}} if row["dimension"] == "input" else {})}
            for row in result.oracle_results))
    binding = NativeCaseBinding(contract.owner_id, "blueprint:W1", "element:W1", (contract.source_case_id,), contract.case_kind, contract.evidence_scope, contract.covered_dimensions, contract.expected_status, mapping_fingerprint=fp("mapping"))
    envelope = root / "native-results.json"
    envelope.write_text(json.dumps({"schema_version": result.to_dict()["schema_version"], "results": [result.to_dict()]}), encoding="utf-8")
    envelope_fp = "sha256:" + hashlib.sha256(envelope.read_bytes()).hexdigest()
    proof = {"schema_version": "flowguard.validation_owner_receipt.v2", "child": {"payload": {"model_result": {"model_id": "alpha", "input_inventory_fingerprint": result.input_fingerprint, "native_case_result_artifact_path": "native-results.json", "native_case_result_artifact_fingerprint": envelope_fp, "executed_case_ids": [result.source_case_id], "native_case_results": [result.to_dict()]}}}}
    proof_bytes = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode(); proof_fp = "sha256:" + hashlib.sha256(proof_bytes).hexdigest()
    output = root / "receipts"; (output / "proofs").mkdir(parents=True, exist_ok=True); (output / "proofs" / "proof.json").write_bytes(proof_bytes)
    owner_receipt = replace(owner_receipt, proof_artifact_fingerprint=proof_fp, result_fingerprint=proof_fp, metadata={"proof_relpath": "proofs/proof.json"})
    save_evidence_receipt(owner_receipt, output_directory=output)
    context = current_context(owner_receipt, receipt_store_repository_root=str(root), receipt_store_output_directory=str(output))
    identities = {name: getattr(result, name) for name in ("input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint")}
    return {"native_contracts": (contract,), "native_bindings": (binding,), "native_results": (result,), "receipts": (owner_receipt,), "receipt_contexts": {owner_receipt.receipt_id: context}, "raw_artifact_root": root, "current_native_identities": {(contract.owner_id, contract.source_case_id): identities}}


def test_cost_bound_requires_independently_admitted_measurement():
    fact = _r6_fact()
    goal = _r6_objective("cost_bound", (fact,), {"dimension": "steps", "unit": "steps", "bound": 10, "measurement_evidence_ref": "measurement:fixture"})
    for value in (float("nan"), -1, True, 5, 11):
        result = evaluate_architecture_objectives((goal,), (fact,), measurements={fact.responsibility_id: {"steps": value}}, measurement_evidence={fact.responsibility_id: _r6_review(fact)})
        assert result["observation_gap_ids"] == ["cost_measurement_missing:" + goal.objective.objective_id]
        assert result["satisfied_objective_ids"] == result["suggestions"] == []
    for vector in (PathCostVector("measurement:current", fp("subject"), "current", steps=5, measurement_units=(("steps", "steps"),), measurement_evidence=(("steps", fp("measurement")),)), PathCostVector("measurement:stale", fp("subject"), "stale", steps=5, current=False, measurement_units=(("steps", "steps"),), measurement_evidence=(("steps", fp("measurement")),)), PathCostVector("measurement:unit", fp("subject"), "current", steps=5, measurement_units=(("steps", "bytes"),), measurement_evidence=(("steps", fp("measurement")),))):
        assert evaluate_architecture_objectives((goal,), (fact,), measurements={fact.responsibility_id: vector})["architecture_objective_status"] == "blocked"


def test_partial_context_overlap_preserves_each_variant_remainder():
    a = _r6_fact("A", classes=("online", "recovery")); b = _r6_fact("B", classes=("online", "batch"))
    result = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a), _r6_review(b)))
    duplicate = next(row for row in result["relations"] if row["kind"] == "duplicate_boundary")
    assert duplicate["input_class_ids"] == ["online"]
    assert duplicate["remaining_contexts"] == [{"responsibility_id": a.responsibility_id, "input_class_ids": ["recovery"]}, {"responsibility_id": b.responsibility_id, "input_class_ids": ["batch"]}]
    split = (replace(a, responsibility_id="A:online", applicable_input_class_ids=("online",)), replace(b, responsibility_id="B:online", applicable_input_class_ids=("online",)),
        replace(a, responsibility_id="A:recovery", applicable_input_class_ids=("recovery",), hard_semantics=dict(a.hard_semantics, **{HARD_SEMANTIC_DIMENSIONS[0]: {"different": "recovery"}})),
        replace(b, responsibility_id="B:batch", applicable_input_class_ids=("batch",), hard_semantics=dict(a.hard_semantics, **{HARD_SEMANTIC_DIMENSIONS[0]: {"different": "batch"}})))
    result = derive_architecture_relation_candidates(split, semantic_reviews=tuple(_r6_review(row) for row in split))
    assert [row["responsibility_ids"] for row in result["relations"] if row["kind"] == "duplicate_boundary"] == [["A:online", "B:online"]]
    mixed = derive_architecture_relation_candidates((a, b))
    assert not mixed["relations"] and len(mixed["observation_gap_ids"]) == 2


def test_missing_semantic_proof_yields_exact_evidence_pointer():
    from flowguard.model_path_quality import derive_architecture_improvement_pointers
    fact = _r6_fact(); pointers = derive_architecture_improvement_pointers(responsibilities=(fact,))
    assert len(pointers) == 1 and pointers[0].status == "needs_evidence"
    assert any(row["kind"] == "context_proof" and row["reference_id"] == fact.responsibility_id and row["next_owner_id"] == fact.owner_id for row in pointers[0].missing_input_refs)
    assert pointers[0].native_case_refs == ()
    policy = derive_architecture_improvement_pointers(responsibilities=(fact,), semantic_reviews=(_r6_review(fact, "model_policy"),))
    assert policy[0].status == "needs_evidence" and any(row["kind"] == "context_proof" for row in policy[0].missing_input_refs)


def test_independent_writer_inventory_exposes_consistently_omitted_model_element(tmp_path):
    from flowguard.model_path_quality import derive_architecture_model_gaps, derive_architecture_improvement_pointers
    inventory, report = _r7_inventory(tmp_path, second_writer=True); source = _r6_declaration()
    gaps = derive_architecture_model_gaps(source, implementation_inventory=inventory, binding_report=report, root=tmp_path)
    w2 = next(row for row in inventory.surfaces if row.symbol == "W2")
    assert any(row["surface_id"] == w2.surface_id and row["owner_boundary"] == "src/writers.py#W2" for row in gaps)
    exact_gap = next(row for row in gaps if row["surface_id"] == w2.surface_id)
    assert exact_gap["maturation_signal"]["required_input"] == "model_obligation_for:" + w2.surface_id
    assert exact_gap["maturation_signal"]["required"] and not exact_gap["maturation_signal"]["resolved"]
    pointers = derive_architecture_improvement_pointers(model_gaps=gaps)
    assert any(row.kind == "model_gap" and any(item["reference_id"] == "model_obligation_for:" + w2.surface_id for item in row.missing_input_refs) for row in pointers)
    assert not report.ok and source.scope_coverage["claim_scope"] == "declared_model"


def test_architecture_suggestion_names_exact_function_obligations_and_native_owner(tmp_path):
    from flowguard.model_path_quality import verify_architecture_native_case_refs, ArchitectureImprovementPointer
    material = _r7_native_material(tmp_path)
    from flowguard.evidence_receipts import verify_evidence_receipt
    from flowguard.model_path_quality import _receipt_binds_native_result
    receipt = material["receipts"][0]; context = material["receipt_contexts"][receipt.receipt_id]
    verification = verify_evidence_receipt(receipt, context)
    assert verification.current and verification.eligible, str(verification.to_dict())
    assert _receipt_binds_native_result(receipt, context, material["native_results"][0])
    refs, gaps = verify_architecture_native_case_refs(**material, required_obligation_ids=("element:W1", "element:module"))
    assert not gaps and len(refs) == 1
    contract = material["native_contracts"][0]
    assert refs[0]["oracle_member_ids"] == sorted(contract.oracle_member_ids)
    assert refs[0]["callable_ref"] == contract.callable_ref and refs[0]["result_selector"] == contract.result_selector
    from flowguard.model_test_alignment import CodeContract
    from flowguard.model_path_quality import derive_architecture_improvement_pointers
    inventory, report = _r7_inventory(tmp_path)
    implementation = next(row for row in report.bindings if row.model_element_id == "element:W1")
    code = CodeContract(implementation.owner_contract_id, path="src/writers.py", symbol="W1", implements_obligations=("element:W1", "element:module"))
    from flowguard.implementation_blueprint import review_model_implementation_bindings
    implementation = replace(implementation, owner_contract_fingerprint=canonical_fingerprint(code.to_dict()))
    report = review_model_implementation_bindings(inventory, required_model_element_ids=report.required_model_element_ids,
        bindings=tuple(implementation if row.model_element_id == implementation.model_element_id else row for row in report.bindings),
        semantic_specs=report.semantic_specs, oracles=report.oracles)
    fact = replace(_r6_fact("writer", model="model:alpha", owner="model:alpha", layer="layer:UI", contract=code.code_contract_id), element_ids=(implementation.model_element_id,), owner_code_contract_fingerprint=canonical_fingerprint(code.to_dict()), implementation_binding_fingerprint=implementation.fingerprint)
    goal = _r6_objective("allowed_layers", (fact,), {"layer_ids": ["layer:service"]})
    owner = subject(model_id=fact.model_id, intent_fingerprint=goal.effective_intent_view_fingerprint)
    pointers = derive_architecture_improvement_pointers(responsibilities=(fact,), subjects=(owner,), objectives=(goal,), semantic_reviews=(_r6_review(fact),), code_contracts=(code,), binding_report=report, native_materials=material, objective_evaluation=evaluate_architecture_objectives((goal,), (fact,)), implementation_inventory=inventory, current_source_fingerprints={surface.path: surface.content_fingerprint for surface in inventory.surfaces})
    assert len(pointers) == 1 and pointers[0].status == "candidate", pointers
    assert pointers[0].retained_obligation_ids == ("element:W1", "element:module") and pointers[0].native_case_refs == refs
    target = pointers[0].action_targets[0]
    assert (target.path, target.symbol) == (code.path, code.symbol)
    assert {"path": target.path, "source_fingerprint": target.source_fingerprint} in pointers[0].source_refs
    assert target.source_fingerprint == next(row.content_fingerprint for row in inventory.surfaces if row.path == code.path and row.symbol == code.symbol)
    assert set(target.retained_obligation_ids) <= set(pointers[0].retained_obligation_ids)
    conflict = replace(fact, source_refs=({"path": code.path, "source_fingerprint": fp("stale-provenance")},))
    conflicted = derive_architecture_improvement_pointers(responsibilities=(conflict,), subjects=(owner,),
        objectives=(goal,), semantic_reviews=(_r6_review(conflict),), code_contracts=(code,),
        binding_report=report, native_materials=material,
        objective_evaluation=evaluate_architecture_objectives((goal,), (conflict,)),
        implementation_inventory=inventory,
        current_source_fingerprints={surface.path: surface.content_fingerprint for surface in inventory.surfaces})
    assert conflicted[0].status == "needs_evidence" and not conflicted[0].action_targets
    assert any(row["kind"] == "current_source" and row["reference_id"] == code.path for row in conflicted[0].missing_input_refs)
    pointer = ArchitectureImprovementPointer("", "goal_mismatch", "candidate", "normative_target", ("model:alpha",), (), ("element:W1",), ("online",), (), {"model:alpha": fp("subject")}, (), (), ("element:W1", "element:module"), refs, (), ("model:alpha",), ())
    assert ArchitectureImprovementPointer.from_dict(pointer.to_dict()) == pointer
    with pytest.raises(ValueError, match="every current subject"):
        replace(pointer, pointer_id="", observed_subject_fingerprints={})
    with pytest.raises(ValueError, match="kind/status/lane"):
        replace(pointer, pointer_id="", status="resolved")
    forged = pointer.to_dict(); forged["native_case_refs"][0]["oracle_ids"] = ["invented"]
    with pytest.raises(ValueError): ArchitectureImprovementPointer.from_dict(forged)
    wrong = dict(material); wrong["current_native_identities"] = {}
    assert verify_architecture_native_case_refs(**wrong)[1][0]["kind"] == "current_source"
    missing = dict(material); missing["receipts"] = ()
    assert verify_architecture_native_case_refs(**missing)[1][0]["kind"] == "owner_receipt"
    wrong_row = replace(material["native_results"][0], code_fingerprint=fp("foreign-code"))
    forged_material = dict(material, native_results=(wrong_row,), current_native_identities={key: dict(value, code_fingerprint=wrong_row.code_fingerprint) for key, value in material["current_native_identities"].items()})
    assert verify_architecture_native_case_refs(**forged_material)[1][0]["kind"] == "owner_receipt"
    envelope = tmp_path / "native-results.json"
    envelope.write_bytes(envelope.read_bytes() + b"\n")
    assert verify_architecture_native_case_refs(**material)[1][0]["kind"] == "owner_receipt"


def test_missing_goal_fact_preserves_exact_model_action_pointer():
    from flowguard.model_path_quality import derive_architecture_improvement_pointers
    fact = _r6_fact()
    goal = _r6_objective("allowed_layers", (fact,), {"layer_ids": ["layer:service"]})
    evaluation = evaluate_architecture_objectives((goal,), ())
    pointers = derive_architecture_improvement_pointers(objectives=(goal,), objective_evaluation=evaluation)
    assert len(pointers) == 1 and pointers[0].model_ids == (fact.model_id,) and pointers[0].status == "needs_evidence"
    assert any(row["reference_id"] == fact.responsibility_id for row in pointers[0].missing_input_refs)


def test_derived_architecture_output_has_no_subject_identity_cycle():
    from flowguard.model_path_quality import ArchitectureImprovementPointer
    def lightweight_path_review_with_detail(owner, facts):
        details = []
        result = lightweight_path_review(owner, facts, detail_collector=details)
        return result, details[0]
    facts = clean_facts(); facts["architecture"] = {"source_refs": [{"path": "model.py", "source_fingerprint": fp("source")}], "effective_intent_view_fingerprint": fp("intent")}
    owner = subject(_model_facts=facts, intent_fingerprint=fp("intent"))
    pointer = ArchitectureImprovementPointer("", "model_gap", "needs_evidence", "normative_target", (owner.model_id,), (), (), (), (), {owner.model_id: owner.fingerprint}, (), (), (), (), ({"kind": "model_binding", "model_id": owner.model_id, "responsibility_id": "", "reference_id": "missing-writer", "next_owner_id": ""},), (), ())
    _, before_detail = lightweight_path_review_with_detail(owner, facts)
    facts["architecture"]["improvement_pointers"] = [pointer.to_dict()]
    result, detail = lightweight_path_review_with_detail(owner, facts)
    assert normalized_model_facts_fingerprint(facts) == owner.normalized_facts_fingerprint
    assert detail.fingerprint != before_detail.fingerprint and detail.binding_errors(owner, result) == ()
    forged = replace(pointer, pointer_id="", observed_subject_fingerprints={owner.model_id: fp("foreign")})
    facts["architecture"]["improvement_pointers"] = [forged.to_dict()]
    bad_result, bad_detail = lightweight_path_review_with_detail(owner, facts)
    assert "architecture_pointer_subject_identity_mismatch" in bad_detail.binding_errors(owner, bad_result)
    for key, value in (("source_refs", [{"path": "model.py", "source_fingerprint": fp("changed")}]), ("objective_refs", [{"goal": "changed"}])):
        changed = dict(facts, architecture=dict(facts["architecture"], **{key: value}))
        assert normalized_model_facts_fingerprint(changed) != owner.normalized_facts_fingerprint


def test_scope_evidence_shape_preserves_current_typed_identity_without_self_cycle(tmp_path):
    from flowguard.model_path_quality import validate_architecture_scope_evidence_shape
    inventory, bindings = _r7_inventory(tmp_path)
    rows = [{"path": row.path, "sha256": row.content_fingerprint} for row in inventory.file_dispositions]
    proof = {"schema": "flowguard.architecture_scope_evidence.v1", "claim_boundary": "complete_within_authenticated_frozen_boundary", "boundary": inventory.boundary.to_dict(), "inventory": inventory.to_dict(), "resolved_manifest_rows": rows,
        "binding_report": bindings.to_dict(), "source_refs": [{"path": row["path"], "source_fingerprint": row["sha256"]} for row in rows], "subject_fingerprint": fp("subject"),
        "producer_owner_id": "owner:inventory", "producer_receipt_id": "receipt:inventory", "producer_receipt_fingerprint": fp("receipt"), "producer_input_fingerprint": fp("inputs")}
    assert validate_architecture_scope_evidence_shape(proof) == proof
    # Shape does not authenticate these receipt identifiers. That is the
    # selected accepted reader's existing receipt/currentness boundary.
    with pytest.raises(ValueError): validate_architecture_scope_evidence_shape(dict(proof, path_quality_result_fingerprint=fp("circular-result")))
    changed = dict(proof, resolved_manifest_rows=[dict(rows[0], sha256=fp("changed"))])
    with pytest.raises(ValueError, match="manifest identity"):
        validate_architecture_scope_evidence_shape(changed)


def test_native_pointer_join_reads_shared_artifacts_once_per_invocation(tmp_path, monkeypatch):
    import hashlib, json
    from pathlib import Path
    import flowguard.native_case_protocol as protocol
    import flowguard.evidence_receipts as evidence
    from flowguard.model_path_quality import verify_architecture_native_case_refs
    from tests.test_native_case_protocol import _good_contract
    material = _r7_native_material(tmp_path)
    first = material["native_results"][0]
    contracts = tuple(replace(_good_contract(case=case), evidence_scope="implementation_boundary") for case in ("case:good", "case:2", "case:3"))
    rows = tuple(replace(first, source_case_id=contract.source_case_id) for contract in contracts)
    envelope = tmp_path / "native-results.json"
    envelope.write_text(json.dumps({"schema_version": first.to_dict()["schema_version"], "results": [row.to_dict() for row in rows]}), encoding="utf-8")
    proof_path = tmp_path / "receipts" / "proofs" / "many.json"
    proof = {"child": {"payload": {"model_result": {"model_id": "alpha", "input_inventory_fingerprint": first.input_fingerprint, "native_case_result_artifact_path": "native-results.json", "native_case_result_artifact_fingerprint": "sha256:" + hashlib.sha256(envelope.read_bytes()).hexdigest(), "executed_case_ids": [row.source_case_id for row in rows], "native_case_results": [row.to_dict() for row in rows]}}}}
    proof_path.write_bytes(json.dumps(proof, sort_keys=True, separators=(",", ":")).encode())
    proof_fp = "sha256:" + hashlib.sha256(proof_path.read_bytes()).hexdigest()
    receipt = replace(material["receipts"][0], receipt_id="receipt:validation-owner:model:alpha:many", proof_artifact_fingerprint=proof_fp, result_fingerprint=proof_fp, metadata={"proof_relpath": "proofs/many.json"})
    evidence.save_evidence_receipt(receipt, output_directory=tmp_path / "receipts")
    previous = next(iter(material["receipt_contexts"].values()))
    context = replace(previous, proof_artifact_fingerprint=proof_fp, result_fingerprint=proof_fp, receipt_store_receipt_ids=(receipt.receipt_id,))
    identity = next(iter(material["current_native_identities"].values()))
    material.update(native_contracts=contracts, native_results=rows, native_bindings=(replace(material["native_bindings"][0], native_case_ids=tuple(row.source_case_id for row in rows)),), receipts=(receipt,), receipt_contexts={receipt.receipt_id: context}, current_native_identities={(row.owner_id, row.source_case_id): dict(identity) for row in rows})
    counts = {"native": 0, "binding": 0, "receipt": 0}; reads = {}
    for module, name, key in ((protocol, "verify_native_model_cases", "native"), (protocol, "verify_native_case_bindings", "binding"), (evidence, "verify_evidence_receipt", "receipt")):
        actual = getattr(module, name)
        def counted(*args, _actual=actual, _key=key, **kwargs):
            counts[_key] += 1
            return _actual(*args, **kwargs)
        monkeypatch.setattr(module, name, counted)
    actual_bytes = Path.read_bytes
    def counted_read(path):
        key = path.resolve()
        reads[key] = reads.get(key, 0) + 1
        return actual_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", counted_read)
    refs, gaps = verify_architecture_native_case_refs(**material)
    assert not gaps and len(refs) == 3
    assert counts == {"native": 1, "binding": 1, "receipt": 1}
    assert reads[proof_path.resolve()] == reads[envelope.resolve()] == reads[(tmp_path / "native.json").resolve()] == 1
    wrong = dict(material, current_native_identities={key: dict(value) for key, value in material["current_native_identities"].items()})
    wrong["current_native_identities"][(first.owner_id, "case:2")]["code_fingerprint"] = fp("wrong-current-code")
    assert any(row["kind"] == "current_source" and row["reference_id"] == "case:2" for row in verify_architecture_native_case_refs(**wrong)[1])
    (tmp_path / "native.json").write_bytes(b"changed after first invocation\n")
    counts.update(native=0, binding=0, receipt=0); reads.clear()
    stale_refs, stale_gaps = verify_architecture_native_case_refs(**material)
    assert not stale_refs and len(stale_gaps) == 3
    assert counts == {"native": 1, "binding": 1, "receipt": 1}
    assert reads[(tmp_path / "native.json").resolve()] == 1


def test_r8_context_index_does_not_compare_unrelated_responsibilities(monkeypatch):
    import flowguard.model_path_quality as quality
    facts = tuple(replace(_r6_fact(str(index), semantics={
        **_r6_fact().hard_semantics, "outputs": {"contract": "output:" + str(index)}}),
        boundary_id="boundary:" + str(index), mechanism_id="mechanism:" + str(index))
        for index in range(32))
    reviews = tuple(_r6_review(fact) for fact in facts)
    calls = []
    original = quality.canonical_fingerprint
    def counted(value):
        if isinstance(value, dict) and "responsibility_id" in value:
            calls.append(value["responsibility_id"])
        return original(value)
    monkeypatch.setattr(quality, "canonical_fingerprint", counted)
    result = derive_architecture_relation_candidates(facts, semantic_reviews=reviews)
    assert result == {"relations": [], "finding_ids": [], "rewrite_candidates": [], "observation_gap_ids": []}
    assert len(calls) == len(facts)
    assert len(set(calls)) == len(facts)


def test_r8_context_index_preserves_real_conflict_overlap_and_remainders():
    facts = tuple(_r6_fact(name, classes=("class:online", "class:private:" + name)) for name in "ABCDE")
    relation = derive_architecture_relation_candidates(facts, semantic_reviews=tuple(_r6_review(fact) for fact in facts))
    duplicates = [row for row in relation["relations"] if row["kind"] == "duplicate_boundary"]
    assert len(duplicates) == 4
    assert set().union(*(set(row["responsibility_ids"]) for row in duplicates)) == {fact.responsibility_id for fact in facts}
    for row in duplicates:
        assert row["input_class_ids"] == ["class:online"]
        assert all(item["input_class_ids"] == ["class:private:" + item["responsibility_id"].split(":")[-1]] for item in row["remaining_contexts"])
    a = _r6_fact("hard:A", contract="contract:one")
    b = _r6_fact("hard:B", contract="contract:one", semantics={**a.hard_semantics, "permissions": {"contract": "denied"}})
    conflict = derive_architecture_relation_candidates((a, b), semantic_reviews=(_r6_review(a), _r6_review(b)))
    assert conflict["relations"][0]["kind"] == "false_friend"
    assert conflict["relations"][0]["hard_mismatch_ids"] == ["permissions"]
    assert not conflict["rewrite_candidates"]
    mixed = tuple(_r6_fact(name, semantics=a.hard_semantics if name in "ABC" else b.hard_semantics) for name in "ABCDE")
    mixed_reviews = tuple(_r6_review(fact) for fact in mixed)
    grouped = derive_architecture_relation_candidates(mixed, semantic_reviews=mixed_reviews)
    assert derive_architecture_relation_candidates(reversed(mixed), semantic_reviews=reversed(mixed_reviews)) == grouped
    duplicates = [row for row in grouped["relations"] if row["kind"] == "duplicate_boundary"]
    conflicts = [row for row in grouped["relations"] if row["kind"] == "false_friend"]
    assert len(duplicates) == 3 and len(conflicts) == 2
    assert set().union(*(set(row["responsibility_ids"]) for row in grouped["relations"])) == {fact.responsibility_id for fact in mixed}
    assert {row["responsibility_ids"][1] for row in conflicts} == {"responsibility:D", "responsibility:E"}
    variants = (_r6_fact("V1", classes=("class:online",)), _r6_fact("V2", classes=("class:offline",)))
    assert derive_architecture_relation_candidates(variants, semantic_reviews=tuple(_r6_review(fact) for fact in variants))["relations"][0]["kind"] == "legitimate_variant"


def _r8_verified_function_material(root, *, check_change=""):
    """Finite test evidence through the real inventory, binding and receipt verifiers."""
    import json
    from flowguard.implementation_blueprint import review_model_implementation_bindings
    from flowguard.model_test_alignment import CodeContract
    from flowguard.model_path_quality import ARCHITECTURE_HARD_DIMENSION_PROJECTION, ResponsibilitySemanticEvidenceBinding
    inventory, previous = _r7_inventory(root)
    old_binding = next(row for row in previous.bindings if row.model_element_id == "element:W1")
    required = "obligation:functional-write"
    code = CodeContract("contract:save", path="src/writers.py", symbol="W1",
        implements_obligations=("element:W1", required), relation_code_obligation_ids=(required,))
    fact = replace(_r6_fact("writer", model="model:alpha", owner="model:alpha"),
        element_ids=("element:W1",), owner_code_contract_id=code.code_contract_id,
        owner_code_contract_fingerprint=canonical_fingerprint(code.to_dict()))
    semantics = tuple((dimension, json.dumps({"schema": "flowguard.architecture_hard_semantics.v1",
        "dimension": dimension, "input_class_ids": list(fact.applicable_input_class_ids),
        "hard_dimensions": {hard: fact.hard_semantics[hard] for hard in hard_names}}, sort_keys=True))
        for dimension, hard_names in sorted(ARCHITECTURE_HARD_DIMENSION_PROJECTION.items()))
    spec = replace(next(row for row in previous.semantic_specs if row.semantic_spec_id in old_binding.semantic_spec_ids),
        covered_dimensions=tuple(sorted(ARCHITECTURE_HARD_DIMENSION_PROJECTION)), semantics=semantics)
    oracle_id = "model:alpha:case:good:input"
    oracle = replace(next(row for row in previous.oracles if row.oracle_id in old_binding.oracle_ids),
        oracle_id=oracle_id, covered_dimensions=spec.covered_dimensions, semantics=semantics)
    binding = replace(old_binding, owner_contract_fingerprint=fact.owner_code_contract_fingerprint,
        model_obligation_ids=("element:W1", required), oracle_ids=(oracle_id,), required_dimensions=spec.covered_dimensions)
    report = review_model_implementation_bindings(inventory,
        required_model_element_ids=previous.required_model_element_ids,
        bindings=tuple(binding if row == old_binding else row for row in previous.bindings),
        semantic_specs=tuple(spec if row.semantic_spec_id == spec.semantic_spec_id else row for row in previous.semantic_specs),
        oracles=tuple(oracle if row.oracle_id in old_binding.oracle_ids else row for row in previous.oracles))
    assert report.ok, report.to_dict()
    pins = ({"path": code.path, "sha256": binding.implementation_content_fingerprint},)
    checks = [{"check_id": "semantic-check:" + fact.responsibility_id + ":" + hard + ":" + context,
        "responsibility_id": fact.responsibility_id, "hard_dimension_id": hard, "input_class_id": context,
        "args": {"store": "empty", "value": "finite"}, "observed": {"returned_value": "finite"},
        "expected": fact.hard_semantics[hard], "status": "pass"}
        for hard in HARD_SEMANTIC_DIMENSIONS for context in fact.applicable_input_class_ids]
    if check_change == "missing": checks.pop()
    elif check_change == "duplicate": checks.append(dict(checks[0]))
    elif check_change == "blocked": checks[0]["status"] = "blocked"
    elif check_change == "expected": checks[0]["expected"] = {"contract": "foreign"}
    elif check_change == "empty_observed": checks[0]["observed"] = {}
    material = _r7_native_material(root, obligations=("element:W1", "element:module", required),
        observed_source_inputs=pins, semantic_checks=checks)
    native = material["native_bindings"][0]
    receipt = material["receipts"][0]
    fact = replace(fact, semantic_spec_ids=(spec.semantic_spec_id,), semantic_spec_fingerprints=(spec.fingerprint,),
        oracle_ids=(oracle_id,), implementation_binding_fingerprint=binding.fingerprint,
        source_refs=({"path": code.path, "source_fingerprint": binding.implementation_content_fingerprint},),
        semantic_evidence_bindings=tuple(ResponsibilitySemanticEvidenceBinding(hard, context,
            spec.semantic_spec_id, oracle_id, native.fingerprint, receipt.receipt_id, receipt.fingerprint,
            fact.owner_id, native.native_case_ids, "implementation_boundary")
            for hard in HARD_SEMANTIC_DIMENSIONS for context in fact.applicable_input_class_ids))
    semantic_inputs = {**material, "binding_report": report, "implementation_inventory": inventory,
        "code_contracts": (code,), "observed_source_inputs": pins,
        "current_source_fingerprints": {code.path: binding.implementation_content_fingerprint},
        "native_input_class_ids": {(fact.owner_id, native.native_case_ids[0]): fact.applicable_input_class_ids}}
    review = verify_responsibility_semantic_evidence(fact, **semantic_inputs)
    return fact, code, inventory, report, material, semantic_inputs, review, required


def _r8_functional_goal(root, fact, code, required, *, desired="pass"):
    import json
    from flowguard.model_intent import ArchitectureObjective, ArchitectureObjectiveSource, derive_architecture_objective_projection
    from tests.test_model_intent_authority import _snapshot, _contribution, _bootstrap_view, SHA_B
    objective = ArchitectureObjective(objective_id="objective:functional-write", required=True,
        model_ids=(fact.model_id,), responsibility_ids=(fact.responsibility_id,),
        applicable_input_class_ids=fact.applicable_input_class_ids, constraint_kind="functional_obligations",
        constraint_values={"required_obligation_ids": [required], "required_code_contract_ids": [code.code_contract_id],
         "native_case_pairs": [{"owner_id": fact.owner_id, "source_case_id": "case:good", "satisfied_observed_status": desired}]},
        native_owner_id=fact.owner_id, protected_failure_ids=("failure:functional-write",))
    text = "Current finite functional target.\n```flowguard-architecture-objectives\n" + json.dumps(ArchitectureObjectiveSource((objective,)).to_dict()) + "\n```\n"
    contribution = replace(_contribution(root, "alpha", text=text),
        target_invariant_ids=(objective.objective_id,), target_obligation_ids=(required,))
    view = _bootstrap_view(root, _snapshot(("alpha",), snapshot_id="base"),
        _snapshot(("alpha",), snapshot_id="candidate", model_sha=SHA_B), (contribution,))
    goals = derive_architecture_objective_projection(view,
        source_bytes_by_contribution_id={contribution.contribution_id: (root / contribution.source_ref).read_bytes()})
    return goals, view


@pytest.mark.parametrize("change", ["", "missing", "duplicate", "blocked", "expected", "empty_observed", "current_native", "observed_source", "copied_result", "duplicate_native", "duplicate_receipt"])
def test_r8_owner_execution_fingerprint_is_distinct_from_observed_source(tmp_path, change):
    fact, code, inventory, report, material, inputs, review, required = _r8_verified_function_material(tmp_path,
        check_change=change if change in {"missing", "duplicate", "blocked", "expected", "empty_observed"} else "")
    row = material["native_results"][0]
    assert row.code_fingerprint != inputs["current_source_fingerprints"][code.path]
    if change == "current_native":
        inputs["current_native_identities"] = {(row.owner_id, row.source_case_id): {**inputs["current_native_identities"][(row.owner_id, row.source_case_id)], "code_fingerprint": fp("stale-owner-execution")}}
    elif change == "observed_source": inputs["observed_source_inputs"] = ({"path": code.path, "sha256": fp("stale-production")},)
    elif change == "copied_result": inputs["native_results"] = (replace(row, observed_status="copied-without-original-receipt"),)
    elif change == "duplicate_native": inputs["native_results"] = (row, row)
    elif change == "duplicate_receipt": inputs["receipts"] = (material["receipts"][0], material["receipts"][0])
    if change: review = verify_responsibility_semantic_evidence(fact, **inputs)
    assert review.ready is (change == ""), review.gap_ids
    if change: assert review.gap_ids


@pytest.mark.parametrize("change", ["", "unmet", "missing_native", "stale_source", "missing_inventory", "foreign_intent", "missing_semantic", "missing_code", "copied_goal", "target_source"])
def test_r8_functional_objectives_require_current_native_semantic_evidence(tmp_path, change):
    fact, code, inventory, report, material, inputs, review, required = _r8_verified_function_material(tmp_path)
    assert review.ready, review.gap_ids
    goals, view = _r8_functional_goal(tmp_path, fact, code, required, desired="goal-ok" if change == "unmet" else "pass")
    kwargs = {"code_contracts": (code,), "binding_report": report, "implementation_inventory": inventory,
        "semantic_reviews": (review,), "native_materials": material,
        "current_source_fingerprints": inputs["current_source_fingerprints"], "effective_intent_view": view, "root": tmp_path}
    if change == "missing_native": kwargs["native_materials"] = {}
    elif change == "stale_source": kwargs["current_source_fingerprints"] = {code.path: fp("changed")}
    elif change == "missing_inventory": kwargs["implementation_inventory"] = None
    elif change == "foreign_intent": kwargs["effective_intent_view"] = None
    elif change == "missing_semantic": kwargs["semantic_reviews"] = ()
    elif change == "missing_code": kwargs["code_contracts"] = ()
    elif change == "copied_goal":
        copied = replace(goals[0].objective, constraint_values={**goals[0].objective.constraint_values,
            "native_case_pairs": [{"owner_id": fact.owner_id, "source_case_id": "case:good", "satisfied_observed_status": "caller-changed"}]})
        goals = (replace(goals[0], objective=copied),)
    elif change == "target_source":
        (tmp_path / goals[0].source_ref).write_text("Changed actual normative source.\n", encoding="utf-8")
    result = evaluate_architecture_objectives(goals, (fact,), **kwargs)
    if not change:
        assert result["satisfied_objective_ids"] == [goals[0].objective.objective_id]
        assert not result["observation_gap_ids"] and not result["improvement_gap_ids"]
    elif change == "unmet":
        assert result["improvement_gap_ids"] == ["required_architecture_objective_unmet:objective:functional-write"]
        assert not result["observation_gap_ids"]
        assert result["suggestions"][0]["action"] == "satisfy_required_functional_obligations"
    else:
        assert not result["satisfied_objective_ids"]
        assert result["observation_gap_ids"] and result["missing_inputs"]
        assert all(set(item) == {"kind", "model_id", "responsibility_id", "reference_id", "next_owner_id"} for item in result["missing_inputs"])



def test_r9_action_targets_bind_actual_code_locations_and_retained_obligations(tmp_path):
    from flowguard.model_path_quality import (ArchitectureActionTarget, ArchitectureImprovementPointer,
        derive_architecture_improvement_pointers, derive_architecture_model_gaps,
        verify_architecture_action_targets)
    fact, code, inventory, report, material, inputs, review, required = _r8_verified_function_material(tmp_path / "bound")
    goal = _r6_objective("allowed_layers", (fact,), {"layer_ids": ["layer:other"]})
    owner = subject(model_id=fact.model_id, intent_fingerprint=goal.effective_intent_view_fingerprint)
    kwargs = dict(responsibilities=(fact,), subjects=(owner,), objectives=(goal,),
        semantic_reviews=(review,), code_contracts=(code,), binding_report=report,
        native_materials=material, implementation_inventory=inventory,
        current_source_fingerprints=inputs["current_source_fingerprints"])
    pointers = derive_architecture_improvement_pointers(**kwargs,
        objective_evaluation=evaluate_architecture_objectives((goal,), (fact,)))
    target = next(row for pointer in pointers if pointer.kind == "goal_mismatch" for row in pointer.action_targets)
    binding = next(row for row in report.bindings if row.fingerprint == fact.implementation_binding_fingerprint)
    assert target.operation == "supply_evidence"
    assert (target.path, target.symbol, target.surface_id) == (code.path, code.symbol, binding.implementation_surface_id)
    assert target.source_fingerprint == inputs["current_source_fingerprints"][code.path]
    assert target.code_contract_fingerprint == canonical_fingerprint(code.to_dict())
    assert target.owner_id == fact.owner_id and not target.requires_owner_admission
    assert required in target.retained_obligation_ids
    pointer = next(row for row in pointers if row.kind == "goal_mismatch")
    assert ArchitectureImprovementPointer.from_dict(pointer.to_dict()) == pointer
    assert verify_architecture_action_targets(pointer, implementation_inventory=inventory,
        binding_report=report, code_contracts=(code,), current_source_fingerprints=inputs["current_source_fingerprints"])
    # A resolver can use the independently authenticated accepted binding as
    # the exact contract identity without launching a native producer.
    assert verify_architecture_action_targets(pointer, implementation_inventory=inventory,
        binding_report=report, current_source_fingerprints=inputs["current_source_fingerprints"])
    for damage in (replace(target, code_contract_fingerprint=fp("foreign-contract")),
                   replace(target, surface_id="foreign-surface"),
                   replace(target, owner_id="model:foreign")):
        bad = replace(pointer, pointer_id="", action_targets=(damage,),
            next_owner_ids=tuple(sorted(set(pointer.next_owner_ids) | {damage.owner_id})))
        with pytest.raises(ValueError, match="architecture_action_target"):
            verify_architecture_action_targets(bad, implementation_inventory=inventory,
                binding_report=report, code_contracts=(code,), current_source_fingerprints=inputs["current_source_fingerprints"])
    with pytest.raises(ValueError, match="source_stale"):
        verify_architecture_action_targets(pointer, implementation_inventory=inventory,
            binding_report=report, current_source_fingerprints={code.path: fp("drift")})
    stale = derive_architecture_improvement_pointers(**dict(kwargs,
        current_source_fingerprints={code.path: fp("drift")}),
        objective_evaluation=evaluate_architecture_objectives((goal,), (fact,)))
    assert stale and all(row.status == "needs_evidence" and not row.action_targets for row in stale)
    duplicate = derive_architecture_improvement_pointers(**kwargs,
        relations={"relations": [{"kind": "duplicate_boundary", "responsibility_ids": [fact.responsibility_id],
            "input_class_ids": list(fact.applicable_input_class_ids), "remaining_contexts": []}]})
    assert any(row.operation == "review_shared_mechanism" for item in duplicate for row in item.action_targets)
    compromise = {"responsibility_ids": [fact.responsibility_id], "applicable_input_class_ids": list(fact.applicable_input_class_ids),
        "objective_ids": [goal.objective.objective_id], "next_owner_ids": [fact.owner_id],
        "element_ids": list(fact.element_ids), "functional_impact": {"obligation_ids": [required]},
        "revisit_triggers": [{"trigger_id": "trigger:actual", "source_ref": code.path,
            "source_fingerprint": target.source_fingerprint, "condition_ref": "next-current-review"}]}
    deferred = derive_architecture_improvement_pointers(**kwargs, compromises=(compromise,))
    assert any(row.operation == "revisit_compromise" for item in deferred for row in item.action_targets)
    gap_inventory, gap_report = _r7_inventory(tmp_path / "unbound", second_writer=True)
    gaps = derive_architecture_model_gaps(_r6_declaration(), implementation_inventory=gap_inventory,
        binding_report=gap_report, root=tmp_path / "unbound")
    unbound = derive_architecture_improvement_pointers(model_gaps=gaps,
        implementation_inventory=gap_inventory,
        current_source_fingerprints={row.path: row.content_fingerprint for row in gap_inventory.surfaces})
    gap_target = next(row for item in unbound for row in item.action_targets)
    assert gap_target.operation == "add_model_obligation" and gap_target.symbol == "W2"
    assert gap_target.owner_id == gap_target.code_contract_id == gap_target.code_contract_fingerprint == ""
    assert gap_target.requires_owner_admission and gap_target.surface_id
    bad_wire = pointer.to_dict(); bad_wire.pop("action_targets")
    with pytest.raises(ValueError, match="fields must be exact"):
        ArchitectureImprovementPointer.from_dict(bad_wire)
    bad_target = target.to_dict(); bad_target["invented"] = True
    with pytest.raises(ValueError, match="fields must be exact"):
        ArchitectureActionTarget.from_dict(bad_target)
    with pytest.raises(ValueError, match="admission"):
        replace(gap_target, requires_owner_admission=False)
    # An existing independent normative file with an absent declared goal is
    # a source repair location; no function or owner is guessed from a name.
    from flowguard.source_identity import functional_source_fingerprint
    spec_path = tmp_path / "bound" / "docs" / "goal.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("# Finite source with the declared objective still absent\n", encoding="utf-8")
    goal = replace(goal, source_ref="docs/goal.md", source_fingerprint=functional_source_fingerprint(tmp_path / "bound", "docs/goal.md"))
    repaired = derive_architecture_improvement_pointers(objectives=(goal,),
        objective_evaluation={"observation_gap_ids": ["functional_objective_evidence_missing:" + goal.objective.objective_id + ":" + goal.objective.objective_id],
            "missing_inputs": [{"kind": "objective_source", "model_id": "", "responsibility_id": "",
                "reference_id": goal.objective.objective_id, "next_owner_id": goal.objective.native_owner_id}]},
        current_source_fingerprints={goal.source_ref: goal.source_fingerprint})
    goal_pointer = next(row for row in repaired if row.action_targets)
    assert goal_pointer.action_targets[0].operation == "repair_goal_source"
    assert goal_pointer.action_targets[0].symbol == goal.objective.objective_id
    assert verify_architecture_action_targets(goal_pointer,
        current_source_fingerprints={goal.source_ref: goal.source_fingerprint})
