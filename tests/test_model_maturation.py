import hashlib
import json
import tempfile
import unittest
import pytest


@pytest.mark.parametrize("mutation", ("none", "omitted_owner", "forged_row", "foreign_basis", "changed_facts", "changed_proof"))
def test_r8_closed_demand_preserves_original_resolution_basis_exactly(mutation):
    from dataclasses import replace
    from flowguard.task_coverage_demand import project_owner_resolution_to_demand
    helper = ModelMaturationTests()
    facts = TaskFacts("task-compile", "compile independent pre-code coverage",
                      read_only=True, source_snapshots=_complete_source_snapshots())
    original = compile_task_coverage_demand(facts)
    seed = helper._intake(*(helper._contribution(owner, owner_route=owner)
                            for owner in original.required_owner_ids))
    contributions = []
    closed = original
    for contribution in sorted(seed.contributions, key=lambda c: c.owner_route):
        obligations = tuple(v for row in original.rows
                            if row.triggered and row.owner_route == contribution.owner_route
                            for v in row.coverage_ids)
        resolution = replace(contribution.owner_resolution,
                             demand_id=original.demand_id,
                             demand_fingerprint=original.fingerprint,
                             obligation_ids=obligations)
        proof = replace(contribution.evidence_ref,
                        producer_route=contribution.owner_route,
                        subject_fingerprint=resolution.fingerprint,
                        covered_obligation_ids=obligations)
        contributions.append(replace(contribution, owner_resolution=resolution,
                                     evidence_ref=proof, coverage_ids=obligations,
                                     required_probe_ids=tuple("probe:" + v for v in obligations)))
        closed = project_owner_resolution_to_demand(closed, resolution)
    intake = replace(seed, task_facts=facts, coverage_demand=closed,
                     contributions=tuple(contributions))
    if mutation == "omitted_owner":
        intake = replace(intake, contributions=intake.contributions[:-1])
    elif mutation == "forged_row":
        intake = replace(intake, coverage_demand=replace(closed,
            rows=(replace(closed.rows[0], reason="forged satisfied row"), *closed.rows[1:])))
    elif mutation == "foreign_basis":
        intake = replace(intake, coverage_demand=replace(closed,
                         resolution_basis_fingerprint=canonical_fingerprint({"foreign": True})))
    elif mutation == "changed_facts":
        intake = replace(intake, task_facts=replace(facts, release_requested=True))
    elif mutation == "changed_proof":
        intake = replace(intake, contributions=(replace(contributions[0],
            evidence_ref=replace(contributions[0].evidence_ref,
                                 subject_fingerprint=canonical_fingerprint({"foreign": True}))),
            *contributions[1:]))
    if mutation in {"omitted_owner", "forged_row", "foreign_basis", "changed_facts"}:
        with pytest.raises(ValueError):
            compile_model_maturation_plan(intake)
        return
    plan = compile_model_maturation_plan(intake)
    assert plan.coverage_demand_fingerprint == closed.fingerprint
    assert plan.coverage_resolution_basis_fingerprint == original.fingerprint
    report = review_model_maturation_loop(plan)
    if mutation == "changed_proof":
        assert not report.ok
    else:
        assert report.ok, [f.code for f in report.findings]
        roundtrip = ModelMaturationPlan.from_dict(plan.to_dict())
        assert review_model_maturation_loop(roundtrip).ok


def _r7_functional_fixture(root, *, requested_outcome_ids=("outcome:save",),
                           declared_output_ids=("outcome:save",)):
    from flowguard.task_coverage_demand import TaskFacts, TaskCoverageDemand, CoverageDemandRow
    from flowguard.model_authority_store import SelectedModelClosureRead
    from flowguard.model_intent_authority import CurrentEffectiveIntentView
    from flowguard.model_maturation_receipt import publish_model_maturation_receipt, verify_model_maturation_receipt
    from tests.test_model_maturation_receipt import ModelMaturationReceiptTests, _path_quality_material
    from tests.test_model_intent_authority import _snapshot, _contribution, _bootstrap_view, SHA_B
    from tests.test_model_path_quality import _r7_inventory, _r7_native_material
    inventory, bindings = _r7_inventory(root)
    w1 = next(row for row in inventory.surfaces if row.symbol == "W1")
    facts = TaskFacts("task:save", "Save the current function", requested_outcome_ids=requested_outcome_ids, affected_surface_ids=(w1.surface_id,), related_model_ids=("alpha",), implementation_requested=True)
    row = CoverageDemandRow("row:save", "rule:save", "model_first_function_flow", ("obligation:save",), True, "satisfied", "Original admitted finite owner", evidence_ids=("evidence:owner",), evidence_fingerprints=(_fingerprint("owner"),))
    unrelated = CoverageDemandRow("row:unrelated", "rule:unrelated", "structure_refactor_mesh", ("obligation:unrelated",), False, "not_triggered", "Function B has no dependency on A.")
    demand = TaskCoverageDemand("demand:save", facts.task_id, facts.fingerprint, "ordinary", (row, unrelated))
    candidate = _snapshot(("alpha", "beta"), snapshot_id="candidate", model_sha=SHA_B)
    contribution = replace(_contribution(root, "alpha"), target_obligation_ids=tuple(binding.model_element_id for binding in bindings.bindings), target_invariant_ids=("invariant:other-function",), target_output_ids=declared_output_ids)
    beta = _contribution(root, "beta", text="Unrelated function B remains outside the task A closure.\n")
    unrelated_path = root / "unrelated-B.py"
    unrelated_path.write_text("def B(value):\n    return value + 1\n", encoding="utf-8")
    view = _bootstrap_view(root, _snapshot(("alpha", "beta"), snapshot_id="base"), candidate, (contribution, beta))
    instance = next(row for row in candidate.model_instances if row.logical_model_id == "alpha")
    subject, result = _path_quality_material("alpha", instance.fingerprint)
    subject = replace(subject, intent_fingerprint=view.fingerprint, currentness_id=candidate.fingerprint)
    result = replace(result, subject_fingerprint=subject.fingerprint, currentness_id=subject.currentness_id)
    fixture = ModelMaturationReceiptTests(); fixture.setUp()
    fixture.report = replace(fixture.report, model_id="alpha", task_id=facts.task_id, coverage_universe_id=demand.demand_id, coverage_demand_fingerprint=demand.fingerprint,
        candidate_model_fingerprint=instance.fingerprint, required_path_quality_model_ids=("alpha",), path_quality_subjects=(subject,), path_quality_results=(result,), path_quality_subject_fingerprints=(), path_quality_result_fingerprints=(), path_quality_result_set_fingerprint="")
    receipt_root = root / "maturation-receipts"
    reference = publish_model_maturation_receipt(fixture.report, fixture.publication, output_directory=receipt_root)
    verification = verify_model_maturation_receipt(reference, fixture._contexts(receipt_root), output_directory=receipt_root)
    assert verification.ok and verification.verified_maturation.supports_full_confidence()
    selected = SelectedModelClosureRead("pass", "current", snapshot_fingerprint=candidate.fingerprint, subject_revision=candidate.subject_revision, authority_head_fingerprint=_fingerprint("head"), accepted_revision_set_fingerprint=_fingerprint("revision"),
        selected_model_ids=("alpha",), selected_models=(instance.to_dict(),), relations=tuple(relation.to_dict() for relation in candidate.relations), architecture={"effective_intent_view_fingerprint": view.fingerprint})
    native = _r7_native_material(root / "native")
    from flowguard.model_test_alignment import CodeContract
    native["code_contracts"] = (CodeContract("contract:save", path="src/writers.py", symbol="W1",
        implements_obligations=("element:W1", "element:module"), external_outputs=declared_output_ids),)
    target = "element:W1"
    refs = ({"outcome_id": "outcome:save", "contribution_id": contribution.contribution_id, "target_kind": "obligation", "target_id": target,
        "binding_fingerprints": [binding.fingerprint for binding in bindings.bindings], "native_case_binding_fingerprints": [native["native_bindings"][0].fingerprint]},)
    return {"task_facts": facts, "coverage_demand": demand, "maturation_report": fixture.report, "verified_maturation": verification.verified_maturation, "selected_read": selected, "current_effective_intent_view": view,
        "binding_report": bindings, "implementation_inventory": inventory, "outcome_refs": refs, "native_materials": native}


def test_function_scope_closes_without_unrelated_architecture_expansion(tmp_path, monkeypatch):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path)
    from pathlib import Path
    reads = []
    original = Path.read_bytes
    def tracked(path):
        reads.append(path)
        assert path.name != "unrelated-B.py" and "beta" not in path.name
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", tracked)
    result = derive_functional_understanding(**values)
    assert result["stopping_disposition"] == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK, str(result["gap_ids"])
    assert result["satisfied_outcome_ids"] == ["outcome:save"] and result["selected_model_ids"] == ["alpha"]
    assert result["deepest_proven_layer"] == "unknown" and not result["missing_outcome_ids"]
    assert len(values["current_effective_intent_view"].active_contributions) == 2
    assert not values["coverage_demand"].rows[1].triggered and values["selected_read"].producer_count == 0
    assert reads and not any(path.name == "unrelated-B.py" for path in reads)


@pytest.mark.parametrize("summary_kind", ("foreign_target", "stale_revision", "same_identity_forged_depth"))
def test_unverified_blueprint_summary_cannot_promote_functional_depth(tmp_path, summary_kind):
    from flowguard.model_maturation import derive_functional_understanding
    from flowguard.target_system_blueprint import BlueprintUnderstandingSummary, SOFTWARE_BLUEPRINT_LAYER_ORDER
    values = _r7_functional_fixture(tmp_path)
    baseline = derive_functional_understanding(**values)
    summary = BlueprintUnderstandingSummary(
        scope="selected_dependency_closure",
        target_system_id="alpha",
        target_profile="software",
        subject_revision=values["selected_read"].subject_revision,
        descriptor_fingerprint=values["current_effective_intent_view"].fingerprint,
        blueprint_fingerprint=values["binding_report"].fingerprint,
        layer_plan_id="plan:constructed",
        layer_plan_fingerprint=values["coverage_demand"].fingerprint,
        layer_statuses=tuple((layer, "complete") for layer in SOFTWARE_BLUEPRINT_LAYER_ORDER),
        status="complete",
        deepest_proven_layer=SOFTWARE_BLUEPRINT_LAYER_ORDER[-1],
        first_gap=None,
        gap_count=0,
        implementation_admitted=True,
        affected_surface_ids=values["task_facts"].affected_surface_ids,
        required_path_quality_model_ids=values["maturation_report"].required_path_quality_model_ids,
    )
    if summary_kind == "foreign_target":
        summary = replace(summary, target_system_id="target:foreign")
    elif summary_kind == "stale_revision":
        summary = replace(summary, subject_revision="revision:stale")
    # Even matching all available task identities is not canonical blueprint
    # proof. The supplied layer/status and fingerprints are constructed data.
    result = derive_functional_understanding(**values, blueprint_summary=summary)
    assert result == baseline
    assert result["deepest_proven_layer"] == "unknown"
    assert result["stopping_disposition"] == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
    assert result["satisfied_outcome_ids"] == ["outcome:save"] and not result["gap_ids"]


@pytest.mark.parametrize("mutation", ("forged_report", "missing_verified", "foreign_task_demand", "stale_selected_source", "foreign_result_set", "foreign_owner_resolution"))
def test_missing_function_obligation_blocks_stopping(tmp_path, mutation):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path)
    if mutation == "forged_report": values["maturation_report"] = replace(values["maturation_report"], evidence_id="evidence:forged")
    elif mutation == "missing_verified": values["verified_maturation"] = None
    elif mutation == "foreign_task_demand": values["task_facts"] = replace(values["task_facts"], task_id="task:foreign")
    elif mutation == "stale_selected_source": values["selected_read"] = replace(values["selected_read"], selected_source_currentness="stale")
    elif mutation == "foreign_result_set":
        report = values["maturation_report"]
        result = replace(report.path_quality_results[0], detail_evidence_fingerprint="sha256:" + _fingerprint("foreign-detail"))
        values["maturation_report"] = replace(report, path_quality_results=(result,), path_quality_result_fingerprints=(), path_quality_result_set_fingerprint="")
    else: values["maturation_report"] = replace(values["maturation_report"], owner_resolution_fingerprints=(_fingerprint("foreign-owner"),))
    result = derive_functional_understanding(**values)
    assert result["stopping_disposition"] != MODEL_MATURATION_DECISION_CLOSED_FOR_TASK and result["missing_outcome_ids"] == ["outcome:save"]


@pytest.mark.parametrize("terminal", ("model_maturation_scope_excluded", "model_maturation_iteration_limit"))
def test_scoped_out_or_iteration_limit_is_not_function_completion(tmp_path, terminal):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path)
    values["maturation_report"] = replace(values["maturation_report"], decision=terminal, terminal_reason=terminal)
    assert derive_functional_understanding(**values)["stopping_disposition"] == terminal


@pytest.mark.parametrize("callable_symbol", ("W1", "foreign_function"))
def test_distinct_native_source_case_joins_actual_function_contract(tmp_path, callable_symbol):
    from flowguard.model_maturation import derive_functional_understanding
    from flowguard.model_test_alignment import CodeContract
    values = _r7_functional_fixture(tmp_path)
    material = dict(values["native_materials"])
    binding = replace(material["native_bindings"][0],
                      blueprint_source_case_id="native-source:alpha:save")
    material["native_bindings"] = (binding,)
    material["native_contracts"] = tuple(replace(row,
        callable_ref="src/writers.py#" + callable_symbol)
        for row in material["native_contracts"])
    owner_contract_id = values["binding_report"].bindings[0].owner_contract_id
    material["code_contracts"] = (CodeContract(owner_contract_id,
        path="src/writers.py", symbol="W1",
        implements_obligations=("element:W1", "element:module"), external_outputs=("outcome:save",)),)
    values["native_materials"] = material
    values["outcome_refs"] = ({**values["outcome_refs"][0],
        "native_case_binding_fingerprints": [binding.fingerprint]},)
    result = derive_functional_understanding(**values)
    assert (result["stopping_disposition"] == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK) == (callable_symbol == "W1")


def test_other_function_binding_cannot_satisfy_current_invariant_outcome(tmp_path):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path)
    values["outcome_refs"] = ({**values["outcome_refs"][0], "target_kind": "invariant", "target_id": "invariant:other-function"},)
    result = derive_functional_understanding(**values)
    assert result["missing_outcome_ids"] == ["outcome:save"] and "outcome_declared_output_mapping_missing:outcome:save" in result["gap_ids"]


@pytest.mark.parametrize("mutation", ("none", "undeclared_output", "wrong_contract_output",
    "cross_owner", "missing_binding", "wrong_native_binding"))
def test_external_outcome_requires_declared_same_owner_code_mapping(tmp_path, mutation):
    """Pure mapping boundary; native and maturation fixtures remain labelled fixtures."""
    from flowguard.model_maturation import review_functional_outcome_bindings
    values = _r7_functional_fixture(tmp_path)
    fields = ("task_facts", "selected_read", "current_effective_intent_view", "binding_report",
              "implementation_inventory", "outcome_refs", "native_materials")
    inputs = {name:values[name] for name in fields}
    material = dict(inputs["native_materials"])
    if mutation == "undeclared_output":
        inputs["task_facts"] = replace(inputs["task_facts"], requested_outcome_ids=("outcome:r8:invented",))
        inputs["outcome_refs"] = ({**inputs["outcome_refs"][0], "outcome_id":"outcome:r8:invented"},)
    elif mutation == "wrong_contract_output":
        material["code_contracts"] = (replace(material["code_contracts"][0], external_outputs=("outcome:r8:other",)),)
    elif mutation == "cross_owner":
        from flowguard.implementation_blueprint import review_model_implementation_bindings
        report = inputs["binding_report"]
        changed = tuple(replace(row, implementation_owner_id="model:beta") for row in report.bindings)
        inputs["binding_report"] = review_model_implementation_bindings(inputs["implementation_inventory"],
            required_model_element_ids=report.required_model_element_ids, bindings=changed,
            semantic_specs=report.semantic_specs, oracles=report.oracles)
        inputs["outcome_refs"] = ({**inputs["outcome_refs"][0],
            "binding_fingerprints":[row.fingerprint for row in changed]},)
    elif mutation == "missing_binding":
        inputs["outcome_refs"] = ({**inputs["outcome_refs"][0], "binding_fingerprints":[]},)
    elif mutation == "wrong_native_binding":
        inputs["outcome_refs"] = ({**inputs["outcome_refs"][0], "native_case_binding_fingerprints":["sha256:"+"0"*64]},)
    inputs["native_materials"] = material
    result = review_functional_outcome_bindings(**inputs)
    assert result["ok"] == (mutation == "none"), result
    if mutation != "none":
        assert result["missing_outcome_ids"] == list(inputs["task_facts"].requested_outcome_ids)


def test_each_external_output_of_one_contribution_requires_its_own_ref(tmp_path):
    from flowguard.model_maturation import review_functional_outcome_bindings
    names = ("outcome:r8:save", "outcome:r8:inspect")
    values = _r7_functional_fixture(tmp_path, requested_outcome_ids=names, declared_output_ids=names)
    material = dict(values["native_materials"])
    material["code_contracts"] = (replace(material["code_contracts"][0], external_outputs=names),)
    # The contribution has two obligations; this output's real binding covers
    # W1 only. Its code/native proof still retains the full declared code scope.
    w1 = next(row for row in values["binding_report"].bindings if row.model_element_id=="element:W1")
    ref = {**values["outcome_refs"][0], "binding_fingerprints":[w1.fingerprint]}
    inputs = {name:values[name] for name in ("selected_read", "current_effective_intent_view",
        "binding_report", "implementation_inventory")}
    inputs.update(native_materials=material)
    for name in names:
        result = review_functional_outcome_bindings(**inputs,
            task_facts=replace(values["task_facts"], requested_outcome_ids=(name,)),
            outcome_refs=({**ref,"outcome_id":name},))
        assert result["ok"], result
    facts = replace(values["task_facts"], requested_outcome_ids=names)
    missing = review_functional_outcome_bindings(**inputs, task_facts=facts,
        outcome_refs=({**ref,"outcome_id":names[0]},))
    assert missing["missing_outcome_ids"] == [names[1]] and not missing["ok"]
    complete = review_functional_outcome_bindings(**inputs, task_facts=facts,
        outcome_refs=tuple({**ref,"outcome_id":name} for name in names))
    assert complete["ok"], complete


def test_verified_maturation_still_needs_each_requested_outcome(tmp_path):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path, requested_outcome_ids=("outcome:save", "outcome:other"))
    result = derive_functional_understanding(**values)
    assert result["satisfied_outcome_ids"] == ["outcome:save"]
    assert result["missing_outcome_ids"] == ["outcome:other"]
    assert result["stopping_disposition"] != MODEL_MATURATION_DECISION_CLOSED_FOR_TASK


def test_model_policy_case_does_not_close_implementation_outcome(tmp_path):
    from flowguard.model_maturation import derive_functional_understanding
    values = _r7_functional_fixture(tmp_path)
    material = dict(values["native_materials"])
    policy_binding = replace(material["native_bindings"][0], evidence_scope="model_policy")
    material["native_bindings"] = (policy_binding,)
    material["native_contracts"] = tuple(replace(row, evidence_scope="model_policy") for row in material["native_contracts"])
    values["native_materials"] = material
    values["outcome_refs"] = ({**values["outcome_refs"][0], "native_case_binding_fingerprints": [policy_binding.fingerprint]},)
    result = derive_functional_understanding(**values)
    assert result["missing_outcome_ids"] == ["outcome:save"] and result["stopping_disposition"] != MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

from flowguard import (
    COVERAGE_DISPOSITION_SATISFIED,
    MATURITY_ACTION_ADD_MODEL_OBLIGATION,
    MATURITY_ACTION_ADD_STATE_FIELD,
    MATURITY_ACTION_DOWNGRADE_CLAIM,
    MATURITY_ACTION_REFRESH_EVIDENCE,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_DECISION_ITERATION_LIMIT,
    MODEL_MATURATION_DECISION_PROGRESS_STALLED,
    MODEL_MATURATION_DECISION_SCOPE_EXCLUDED,
    MODEL_MATURATION_DECISION_UPGRADE_REQUIRED,
    MODEL_MATURATION_PLAN_SCHEMA_VERSION,
    MODEL_MATURATION_RECEIPT_STATUS_PASS,
    MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
    MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
    MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
    ModelMaturationGapResolutionReceipt,
    ModelMaturationCoverageContribution,
    ModelMaturationIntake,
    ModelMaturationPlan,
    ModelMaturationSignal,
    OwnerCoverageResolution,
    ProofArtifactRef,
    compile_model_maturation_plan,
    review_model_maturation_loop,
    review_model_maturation_session,
    CoverageRule,
    TASK_FACT_SOURCE_CURRENT_MODEL,
    TASK_FACT_SOURCE_LIFECYCLE,
    TASK_FACT_SOURCE_PUBLIC_SURFACE,
    TASK_FACT_SOURCE_REQUEST,
    TaskFactSourceSnapshot,
    TaskFacts,
    compile_task_coverage_demand,
)
from flowguard.__main__ import main
from flowguard.model_path_quality import (
    NecessityWitness,
    PathQualitySubject,
    canonical_fingerprint,
    derive_retained_elements,
    lightweight_path_review,
    normalized_model_facts_fingerprint,
)


RETIRED_DISCOVERY_OWNER_IDS = (
    "model_angle",
    "maintenance_scan",
    "model_similarity",
    "analogous_scan",
    "defect_family",
)

MODEL_BASE_FP = canonical_fingerprint({"model": "base-1"})
MODEL_CANDIDATE_FP = canonical_fingerprint({"model": "candidate-1"})
MODEL_CANDIDATE_2_FP = canonical_fingerprint({"model": "candidate-2"})
MODEL_CANDIDATE_3_FP = canonical_fingerprint({"model": "candidate-3"})
COMPILE_CANDIDATE_FP = canonical_fingerprint({"model": "candidate-compile"})
NATIVE_EVIDENCE_FP = canonical_fingerprint({"evidence": "native"})


def _path_quality(model_id: str, model_fingerprint: str, currentness_id: str):
    identity = lambda name: canonical_fingerprint(
        {"model_id": model_id, "identity": name}
    )
    facts = {
        "states": (
            {"id": "start", "initial": True},
            {"id": "done", "terminal": True},
        ),
        "transitions": (
            {
                "id": "finish",
                "source": "start",
                "target": "done",
                "trigger": "request",
                "guard": "authorized",
                "outputs": ("result",),
                "effects": ("emit_result",),
            },
        ),
        "fields": (),
        "function_blocks": (),
        "outputs": ({"id": "result", "terminal": True},),
        "validations": (
            {
                "id": "validate-result",
                "obligation_id": "obligation:result",
                "oracle_id": "oracle:result",
                "subject_fingerprint": identity("validation-subject"),
                "evidence_boundary_id": "boundary:result",
            },
        ),
        "owners": (
            {
                "id": f"owner:{model_id}",
                "intent_id": f"intent:{model_id}",
                "boundary_id": f"behavior:{model_id}",
                "current": True,
            },
        ),
    }
    retained = tuple(derive_retained_elements(facts))
    active_obligation_ids = tuple(
        sorted(f"obligation:{element_id}" for element_id, _kind in retained)
    )
    subject = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"behavior:{model_id}",
        model_fingerprint=model_fingerprint,
        normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts),
        retained_element_inventory_fingerprint=canonical_fingerprint(dict(retained)),
        purpose_fingerprint=identity("purpose"),
        intent_fingerprint=identity("intent"),
        obligation_fingerprint=canonical_fingerprint(list(active_obligation_ids)),
        provider_fingerprint=identity("provider"),
        dependency_fingerprint=identity("dependencies"),
        code_fingerprint=identity("code"),
        test_fingerprint=identity("tests"),
        oracle_fingerprint=identity("oracles"),
        evidence_fingerprint=identity("evidence"),
        currentness_id=currentness_id,
    )
    witnesses = tuple(
        NecessityWitness(
            witness_id=f"witness:{element_id}",
            subject_fingerprint=subject.fingerprint,
            element_id=element_id,
            element_kind=element_kind,
            obligation_id=f"obligation:{element_id}",
            counterexample_id=f"counterexample:{element_id}",
            oracle_id=f"oracle:{element_id}",
            evidence_fingerprint=identity(f"witness:{element_id}"),
            evidence_currentness_id=currentness_id,
        )
        for element_id, element_kind in retained
    )
    result = lightweight_path_review(
        subject,
        facts,
        necessity_witnesses=witnesses,
        active_obligation_ids=active_obligation_ids,
    )
    return subject, result


def _fingerprint(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _complete_source_snapshots():
    return tuple(
        TaskFactSourceSnapshot(
            source_plane,
            f"artifact:{source_plane}",
            "sha256:" + source_plane.encode("utf-8").hex().ljust(64, "0")[:64],
        )
        for source_plane in (
            TASK_FACT_SOURCE_REQUEST,
            TASK_FACT_SOURCE_CURRENT_MODEL,
            TASK_FACT_SOURCE_PUBLIC_SURFACE,
            TASK_FACT_SOURCE_LIFECYCLE,
        )
    )


def _plan(**overrides):
    strong_material = overrides.pop("_strong_material", True)
    values = {
        "plan_id": "maturation-checkout",
        "task_id": "task-checkout",
        "task_purpose": "predict checkout failure behavior before release",
        "model_id": "checkout",
        "risk_id": "risk-checkout",
        "coverage_universe_id": "checkout-obligations-v1",
        "coverage_demand_fingerprint": canonical_fingerprint({"demand": "task-demand"}),
        "coverage_owner": "existing-model-preflight",
        "coverage_source_refs": ("model:checkout@base-1", "code-map:checkout@code-1"),
        "coverage_ids": ("checkout.failure",),
        "required_probe_ids": ("probe.checkout.failure",),
        "base_model_fingerprint": MODEL_BASE_FP,
        "candidate_model_fingerprint": MODEL_CANDIDATE_FP,
        "evidence_fingerprint": "evidence-1",
    }
    values.update(overrides)
    if "required_path_quality_model_ids" not in values:
        subject, result = _path_quality(
            str(values["model_id"]),
            str(values["candidate_model_fingerprint"]),
            f"maturation:{values['task_id']}",
        )
        values.update(
            {
                "required_path_quality_model_ids": (str(values["model_id"]),),
                "path_quality_subjects": (subject,),
                "path_quality_results": (result,),
            }
        )
    plan = ModelMaturationPlan(**values)
    if "coverage_universe_fingerprint" not in overrides:
        plan = replace(plan, coverage_universe_fingerprint=plan.expected_coverage_fingerprint())
    if strong_material and plan.coverage_ids:
        resolution = OwnerCoverageResolution(
            "resolution:model-miss-review",
            task_id=plan.task_id,
            demand_id=plan.coverage_universe_id,
            demand_fingerprint=plan.coverage_demand_fingerprint,
            owner_route="model_miss_review",
            disposition=COVERAGE_DISPOSITION_SATISFIED,
            obligation_ids=plan.coverage_ids,
            evidence_ids=("proof:model-miss-review",),
            evidence_fingerprints=(NATIVE_EVIDENCE_FP,),
        )
        proof = ProofArtifactRef(
            "proof:model-miss-review",
            producer_route="model_miss_review",
            command="python -m pytest tests/test_model_maturation.py -q",
            result_path="tmp/model-maturation.json",
            result_status="passed",
            exit_code=0,
            started_at="2026-08-02T00:00:00+00:00",
            finished_at="2026-08-02T00:00:01+00:00",
            subject_id=resolution.resolution_id,
            subject_fingerprint=resolution.resolution_fingerprint,
            artifact_fingerprints={"candidate": NATIVE_EVIDENCE_FP},
            covered_obligation_ids=plan.coverage_ids,
        )
        contribution = ModelMaturationCoverageContribution(
            "contribution:model-miss-review",
            owner_route="model_miss_review",
            task_id=plan.task_id,
            coverage_ids=plan.coverage_ids,
            evidence_ref=proof,
            owner_resolution=resolution,
            candidate_model_fingerprint=plan.candidate_model_fingerprint,
            subject_fingerprints={"candidate": NATIVE_EVIDENCE_FP},
        )
        plan = replace(
            plan,
            owner_resolution_ids=(resolution.resolution_id,),
            owner_resolution_fingerprints=(resolution.resolution_fingerprint,),
            owner_resolution_owner_ids=(resolution.owner_route,),
            owner_resolution_contributions=(contribution,),
        )
    return plan


def _open_signal(**overrides):
    values = {
        "signal_id": "gap-checkout-failure",
        "signal_type": MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
        "source_route": "model_miss_review",
        "coverage_id": "checkout.failure",
        "probe_id": "probe.checkout.failure",
        "resolution_class": MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
        "prediction": "the candidate represents the payment-decline branch",
        "falsifier": "a decline trace reaches an unmodeled state",
        "evidence_id": "trace-decline-1",
        "evidence_fingerprint": "trace-fingerprint-1",
        "current": True,
    }
    values.update(overrides)
    return ModelMaturationSignal(**values)


def _verified_signal(plan, **overrides):
    values = {
        "resolved": True,
        "receipt_id": "receipt-checkout-1",
        "receipt_fingerprint": "receipt-fingerprint-1",
        "receipt_status": MODEL_MATURATION_RECEIPT_STATUS_PASS,
        "receipt_task_id": plan.task_id,
        "receipt_probe_id": "probe.checkout.failure",
        "receipt_candidate_fingerprint": plan.candidate_model_fingerprint,
        "receipt_coverage_fingerprint": plan.coverage_universe_fingerprint,
        "receipt_evidence_fingerprint": "trace-fingerprint-1",
        "receipt_owner_route": "model_miss_review",
    }
    values.update(overrides)
    return _open_signal(**values)


def _gap_receipt(plan, gap, **overrides):
    values = {
        "receipt_id": "gap-receipt-2",
        "receipt_fingerprint": "gap-resolution-receipt-2",
        "gap_fingerprint": gap,
        "task_id": plan.task_id,
        "candidate_fingerprint": plan.candidate_model_fingerprint,
        "coverage_fingerprint": plan.coverage_universe_fingerprint,
        "evidence_fingerprint": plan.evidence_fingerprint,
        "owner_route": "model_miss_review",
        "status": MODEL_MATURATION_RECEIPT_STATUS_PASS,
        "current": True,
    }
    values.update(overrides)
    return ModelMaturationGapResolutionReceipt(**values)


class ModelMaturationTests(unittest.TestCase):
    def _demand(self, *owner_ids):
        rules = tuple(
            CoverageRule(
                f"rule:{owner}",
                owner,
                (f"demand:{owner}",),
                f"{owner} is required by this test task",
                always_for_non_trivial=True,
            )
            for owner in owner_ids
        )
        return compile_task_coverage_demand(
            TaskFacts(
                "task-compile",
                "compile independent pre-code coverage",
                source_snapshots=_complete_source_snapshots(),
            ),
            rules=rules,
        )

    def _contribution(self, contribution_id="requirements", **overrides):
        values = {
            "contribution_id": contribution_id,
            "owner_route": "existing_model_preflight",
            "task_id": "task-compile",
            "coverage_source_refs": ("spec:task-compile",),
            "coverage_ids": ("requirement:submit",),
            "required_probe_ids": ("probe:submit",),
            "subject_fingerprints": {"candidate": COMPILE_CANDIDATE_FP},
            "evidence_ref": ProofArtifactRef(
                f"proof:{contribution_id}",
                producer_route="existing_model_preflight",
                command="python -m pytest tests/test_model_maturation.py -q",
                result_path=f"tmp/{contribution_id}.json",
                result_status="passed",
                exit_code=0,
                started_at="2026-08-02T00:00:00+00:00",
                finished_at="2026-08-02T00:00:01+00:00",
                artifact_fingerprints={"candidate": COMPILE_CANDIDATE_FP},
                covered_obligation_ids=("requirement:submit",),
            ),
        }
        values.update(overrides)
        return ModelMaturationCoverageContribution(**values)

    def _intake(self, *contributions, **overrides):
        required_owner_ids = overrides.pop(
            "required_owner_ids",
            tuple(dict.fromkeys(item.owner_route for item in contributions)),
        )
        demand = self._demand(*required_owner_ids)
        canonical: list[ModelMaturationCoverageContribution] = []
        for contribution in contributions:
            proof = contribution.evidence_ref
            assert proof is not None
            demanded = tuple(
                coverage_id
                for row in demand.rows
                if row.triggered and row.owner_route == contribution.owner_route
                for coverage_id in row.coverage_ids
            )
            obligations = tuple(dict.fromkeys(contribution.coverage_ids + demanded))
            evidence_fingerprints = tuple(proof.artifact_fingerprints.values())
            resolution = OwnerCoverageResolution(
                f"resolution:{contribution.contribution_id}",
                task_id="task-compile",
                demand_id=demand.demand_id,
                demand_fingerprint=demand.fingerprint,
                owner_route=contribution.owner_route,
                disposition=COVERAGE_DISPOSITION_SATISFIED,
                obligation_ids=obligations,
                evidence_ids=(proof.artifact_id,),
                evidence_fingerprints=evidence_fingerprints,
            )
            canonical_proof = replace(
                proof,
                command=proof.command or "python -m pytest tests/test_model_maturation.py -q",
                result_path=proof.result_path or f"tmp/{contribution.contribution_id}.json",
                started_at=proof.started_at or "2026-08-02T00:00:00+00:00",
                finished_at=proof.finished_at or "2026-08-02T00:00:01+00:00",
                subject_id=resolution.resolution_id,
                subject_fingerprint=resolution.resolution_fingerprint,
                covered_obligation_ids=obligations,
            )
            canonical.append(
                replace(
                    contribution,
                    evidence_ref=canonical_proof,
                    owner_resolution=resolution,
                    candidate_model_fingerprint=COMPILE_CANDIDATE_FP,
                    subject_fingerprints=dict(canonical_proof.artifact_fingerprints),
                )
            )
        values = {
            "intake_id": "intake-compile",
            "plan_id": "plan-compile",
            "task_id": "task-compile",
            "task_purpose": "compile independent pre-code coverage",
            "model_id": "submit-model",
            "risk_id": "risk-submit",
            "base_model_fingerprint": "base-compile",
            "candidate_model_fingerprint": COMPILE_CANDIDATE_FP,
            "coverage_demand": demand,
            "contributions": tuple(canonical),
        }
        values.update(overrides)
        if "required_path_quality_model_ids" not in values:
            subject, result = _path_quality(
                str(values["model_id"]),
                str(values["candidate_model_fingerprint"]),
                f"maturation:{values['task_id']}",
            )
            values.update(
                {
                    "required_path_quality_model_ids": (
                        str(values["model_id"]),
                    ),
                    "path_quality_subjects": (subject,),
                    "path_quality_results": (result,),
                }
            )
        return ModelMaturationIntake(**values)

    def test_pre_code_intake_compiles_independent_coverage_and_exact_evidence(self):
        requirement = self._contribution()
        bcl = self._contribution(
            "behavior",
            owner_route="behavior_commitment_ledger",
            coverage_source_refs=("bcl:submit",),
            coverage_ids=("behavior:submit",),
            required_probe_ids=("probe:behavior:submit",),
            evidence_ref=ProofArtifactRef(
                "proof:behavior",
                producer_route="behavior_commitment_ledger",
                result_status="passed",
                exit_code=0,
                artifact_fingerprints={"candidate": COMPILE_CANDIDATE_FP},
                covered_obligation_ids=("behavior:submit",),
            ),
        )
        plan = compile_model_maturation_plan(self._intake(requirement, bcl))
        report = review_model_maturation_loop(plan)

        self.assertEqual(
            set(plan.coverage_ids),
            {
                "requirement:submit",
                "behavior:submit",
                "demand:existing_model_preflight",
                "demand:behavior_commitment_ledger",
            },
        )
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(report.coverage_demand_fingerprint, plan.coverage_demand_fingerprint)
        self.assertEqual(report.candidate_model_fingerprint, COMPILE_CANDIDATE_FP)

    def test_missing_or_stale_contribution_remains_an_open_gap(self):
        for owner in (
            "behavior",
            *RETIRED_DISCOVERY_OWNER_IDS,
            "ui",
            "field",
            "test",
        ):
            with self.subTest(owner=owner):
                missing_plan = compile_model_maturation_plan(
                    self._intake(
                        self._contribution(),
                        required_owner_ids=("existing_model_preflight", owner),
                    )
                )
                missing = review_model_maturation_loop(missing_plan)
                self.assertFalse(missing.ok)
                self.assertIn(f"missing-contribution:{owner}", missing_plan.coverage_ids)

        stale = self._contribution(current=False)
        stale_report = review_model_maturation_loop(
            compile_model_maturation_plan(self._intake(stale))
        )
        self.assertFalse(stale_report.ok)
        self.assertIn(
            "model_maturation_signal_stale",
            {finding.code for finding in stale_report.findings},
        )

    def test_low_risk_intake_does_not_invent_untriggered_specialists(self):
        plan = compile_model_maturation_plan(
            self._intake(self._contribution(), required_owner_ids=("existing_model_preflight",))
        )
        self.assertEqual(
            set(plan.coverage_ids),
            {"requirement:submit", "demand:existing_model_preflight"},
        )
        self.assertFalse(any(source.startswith("ui:") for source in plan.coverage_source_refs))
        for retired_owner in RETIRED_DISCOVERY_OWNER_IDS:
            with self.subTest(retired_owner=retired_owner):
                self.assertFalse(
                    any(retired_owner in coverage_id for coverage_id in plan.coverage_ids)
                )
                self.assertFalse(
                    any(retired_owner in source for source in plan.coverage_source_refs)
                )

    def test_duplicate_contribution_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            self._intake(self._contribution(), self._contribution())

    def test_empty_legacy_shape_is_blocked_instead_of_current(self):
        report = review_model_maturation_loop(ModelMaturationPlan(plan_id="shallow"))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn("missing_task_id", {finding.code for finding in report.findings})
        self.assertTrue(report.open_gap_fingerprints)

    def test_current_task_closes_only_with_exact_native_receipt(self):
        plan = _plan()
        report = review_model_maturation_loop(replace(plan, signals=(_verified_signal(plan),)))

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_CLOSED_FOR_TASK)
        self.assertEqual(report.terminal_reason, MODEL_MATURATION_DECISION_CLOSED_FOR_TASK)
        self.assertEqual(report.iteration_record.native_receipt_fingerprints, ("receipt-fingerprint-1",))

    def test_path_quality_denominator_and_exact_current_result_are_required(self):
        plan = _plan()
        missing_denominator = replace(
            plan,
            required_path_quality_model_ids=(),
            path_quality_subjects=(),
            path_quality_results=(),
            path_quality_result_set_fingerprint="",
        )
        report = review_model_maturation_loop(missing_denominator)
        self.assertIn(
            "missing_path_quality_denominator",
            {finding.code for finding in report.findings},
        )

        missing_result = replace(
            plan,
            path_quality_results=(),
            path_quality_result_set_fingerprint="",
        )
        report = review_model_maturation_loop(missing_result)
        self.assertIn(
            "path_quality_result_missing",
            {finding.code for finding in report.findings},
        )

    def test_stale_unresolved_or_foreign_path_quality_cannot_close(self):
        plan = _plan()
        subject = plan.path_quality_subjects[0]
        result = plan.path_quality_results[0]
        unresolved = lightweight_path_review(
            subject,
            {
                "states": (
                    {"id": "start", "initial": True},
                    {"id": "done", "terminal": True},
                ),
                "transitions": (
                    {
                        "id": "finish",
                        "source": "start",
                        "target": "done",
                        "trigger": "finish",
                        "outputs": ("result",),
                    },
                ),
                "outputs": ({"id": "result", "terminal": True},),
            },
            explicit_deep_request=True,
        )
        cases = (
            (replace(result, current=False), "path_quality_result_stale"),
            (
                replace(result, currentness_id="maturation:foreign"),
                "path_quality_currentness_mismatch",
            ),
            (unresolved, "path_quality_unresolved"),
            (
                replace(
                    result,
                    mode="deep",
                    trigger_ids=("explicit_request",),
                    candidate_ids=("candidate:observed", "candidate:target"),
                    conclusion="preferred_within_candidates",
                    selected_candidate_id="candidate:target",
                    selected_candidate_lane="normative_target",
                    comparison_boundary_id="boundary:declared-candidates",
                    candidate_set_fingerprint=canonical_fingerprint(
                        {"candidate_ids": ["candidate:observed", "candidate:target"]}
                    ),
                ),
                "path_quality_normative_target_not_observed",
            ),
        )
        for path_result, expected in cases:
            with self.subTest(expected=expected):
                candidate = replace(
                    plan,
                    path_quality_results=(path_result,),
                    path_quality_result_set_fingerprint="",
                )
                report = review_model_maturation_loop(candidate)
                self.assertFalse(report.ok)
                self.assertIn(
                    expected,
                    {finding.code for finding in report.findings},
                )

        stale_subject, stale_result = _path_quality(
            plan.model_id,
            canonical_fingerprint({"model": "stale-candidate"}),
            subject.currentness_id,
        )
        stale_plan = replace(
            plan,
            path_quality_subjects=(stale_subject,),
            path_quality_results=(stale_result,),
            path_quality_result_set_fingerprint="",
        )
        stale_report = review_model_maturation_loop(stale_plan)
        self.assertIn(
            "path_quality_subject_model_stale",
            {finding.code for finding in stale_report.findings},
        )

    def test_path_quality_result_changes_iteration_input_identity(self):
        first_plan = _plan()
        first = review_model_maturation_loop(
            replace(first_plan, signals=(_verified_signal(first_plan),))
        )
        changed_result = replace(
            first_plan.path_quality_results[0],
            producer_id="model_maturation:independent-review",
        )
        second_plan = replace(
            first_plan,
            path_quality_results=(changed_result,),
            path_quality_result_set_fingerprint="",
        )
        second = review_model_maturation_loop(
            replace(second_plan, signals=(_verified_signal(second_plan),))
        )
        self.assertTrue(first.ok and second.ok)
        self.assertNotEqual(
            first.path_quality_result_set_fingerprint,
            second.path_quality_result_set_fingerprint,
        )
        self.assertNotEqual(first.input_fingerprint, second.input_fingerprint)

    def test_raw_hand_filled_signal_cannot_close_broad_maturation(self):
        plan = _plan(_strong_material=False)
        report = review_model_maturation_loop(
            replace(plan, signals=(_verified_signal(plan),))
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn(
            "missing_owner_resolution_material",
            {finding.code for finding in report.findings},
        )

    def test_caller_resolved_boolean_is_not_evidence(self):
        plan = _plan()
        signal = _open_signal(resolved=True)
        report = review_model_maturation_loop(replace(plan, signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")
        codes = {finding.code for finding in report.findings}
        self.assertIn("unverified_signal_resolution", codes)
        self.assertIn(MATURITY_ACTION_REFRESH_EVIDENCE, report.recommended_actions)

    def test_wrong_receipt_bindings_cannot_close(self):
        for field, value in (
            ("receipt_task_id", "another-task"),
            ("receipt_probe_id", "another-probe"),
            ("receipt_candidate_fingerprint", "another-candidate"),
            ("receipt_coverage_fingerprint", "another-universe"),
            ("receipt_evidence_fingerprint", "another-evidence"),
            ("receipt_owner_route", "another-owner"),
            ("receipt_status", "failed"),
        ):
            with self.subTest(field=field):
                plan = _plan()
                report = review_model_maturation_loop(
                    replace(plan, signals=(_verified_signal(plan, **{field: value}),))
                )
                self.assertFalse(report.ok)
                self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)

    def test_required_contract_fields_and_independent_coverage_are_enforced(self):
        cases = (
            ("task_purpose", "", "missing_task_purpose"),
            ("coverage_source_refs", (), "missing_coverage_source_refs"),
            ("coverage_ids", (), "missing_coverage_universe"),
            ("required_probe_ids", (), "missing_required_probes"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                plan = _plan(**{field: value})
                report = review_model_maturation_loop(plan)
                self.assertIn(expected, {finding.code for finding in report.findings})
                self.assertFalse(report.ok)

    def test_coverage_inventory_cannot_be_silently_rewritten(self):
        plan = _plan(coverage_universe_fingerprint="caller-kept-old-fingerprint")
        report = review_model_maturation_loop(replace(plan, signals=(_verified_signal(plan),)))

        self.assertFalse(report.ok)
        self.assertIn(
            "coverage_universe_fingerprint_mismatch",
            {finding.code for finding in report.findings},
        )

    def test_every_required_probe_must_have_a_bound_signal(self):
        plan = _plan(required_probe_ids=("probe.checkout.failure", "probe.checkout.timeout"))
        signal = _verified_signal(plan)
        report = review_model_maturation_loop(replace(plan, signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertIn("missing_required_probe_signal", {finding.code for finding in report.findings})

    def test_open_addressable_gap_requires_another_iteration_not_terminal_stop(self):
        plan = _plan(signals=(_open_signal(),))
        report = review_model_maturation_loop(plan)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)

    def test_external_stop_requires_exact_input_owner_and_claim_boundary(self):
        complete = _open_signal(
            resolution_class=MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
            required_input="provider decline trace with correlation id",
            owner_boundary="payment-provider",
            affected_claim_scope="provider-decline recovery only",
        )
        report = review_model_maturation_loop(_plan(signals=(complete,)))
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED)
        self.assertEqual(report.terminal_reason, MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED)

        incomplete = replace(complete, owner_boundary="")
        report = review_model_maturation_loop(_plan(signals=(incomplete,)))
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn("incomplete_external_input_boundary", {finding.code for finding in report.findings})

    def test_scope_exclusion_is_visible_and_never_full_closure(self):
        signal = _open_signal(
            in_scope=False,
            resolution_class=MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
            affected_claim_scope="legacy provider behavior",
        )
        report = review_model_maturation_loop(_plan(signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_SCOPE_EXCLUDED)
        self.assertIn(MATURITY_ACTION_DOWNGRADE_CLAIM, report.recommended_actions)

    def test_prior_gap_cannot_disappear_without_a_resolution_receipt(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        prior_gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            evidence_fingerprint="evidence-2",
        )
        second_signal = _verified_signal(
            second_plan,
            receipt_id="receipt-checkout-2",
            receipt_fingerprint="receipt-fingerprint-2",
        )
        report = review_model_maturation_loop(replace(second_plan, signals=(second_signal,)))

        self.assertFalse(report.ok)
        self.assertIn(prior_gap, report.open_gap_fingerprints)
        self.assertIn("gap_deleted_without_resolution_receipt", {finding.code for finding in report.findings})

    def test_two_iteration_session_preserves_gap_and_closes_with_receipts(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        prior_gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        second_plan = replace(
            second_plan,
            resolved_gap_receipts={prior_gap: _gap_receipt(second_plan, prior_gap)},
        )
        second_signal = _verified_signal(
            second_plan,
            receipt_id="receipt-checkout-2",
            receipt_fingerprint="receipt-fingerprint-2",
        )
        second_plan = replace(second_plan, signals=(second_signal,))
        session = review_model_maturation_session((first_plan, second_plan), session_id="session-checkout")

        self.assertTrue(session.closed)
        self.assertEqual(len(session.iterations), 2)
        self.assertIn(prior_gap, session.iterations[1].resolved_gap_fingerprints)

    def test_untyped_or_wrong_gap_resolution_receipt_is_rejected(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        gap = first.open_gap_fingerprints[0]
        with self.assertRaises(ValueError):
            _plan(resolved_gap_receipts={gap: "caller-says-fixed"})

        second = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            evidence_fingerprint="evidence-2",
        )
        wrong = _gap_receipt(second, gap, task_id="another-task")
        signal = _verified_signal(second, receipt_id="receipt-2", receipt_fingerprint="receipt-fp-2")
        report = review_model_maturation_loop(
            replace(second, signals=(signal,), resolved_gap_receipts={gap: wrong})
        )
        self.assertFalse(report.ok)
        self.assertIn("gap_deleted_without_resolution_receipt", {item.code for item in report.findings})

    def test_evidence_acquisition_advances_without_pretending_to_close(self):
        first = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
                    ),
                )
            )
        )
        second = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_FP,
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        progress_signal = _verified_signal(
            second,
            resolved=False,
            resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
            evidence_id="trace-2",
            evidence_fingerprint="trace-fingerprint-2",
            receipt_evidence_fingerprint="trace-fingerprint-2",
            receipt_id="progress-receipt-2",
            receipt_fingerprint="progress-receipt-fp-2",
        )
        second = replace(second, signals=(progress_signal,))
        report = review_model_maturation_loop(second)
        self.assertTrue(report.progressed)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")

    def test_introduced_gap_remains_visible_during_candidate_progress(self):
        coverage = ("checkout.failure", "checkout.timeout")
        probes = ("probe.checkout.failure", "probe.checkout.timeout")
        base = _plan(coverage_ids=coverage, required_probe_ids=probes)
        timeout_pass = _verified_signal(
            base,
            signal_id="gap-checkout-timeout",
            coverage_id="checkout.timeout",
            probe_id="probe.checkout.timeout",
            receipt_probe_id="probe.checkout.timeout",
            receipt_id="receipt-timeout-1",
            receipt_fingerprint="receipt-timeout-fp-1",
        )
        first_plan = replace(base, signals=(_open_signal(), timeout_pass))
        first = review_model_maturation_loop(first_plan)
        old_gap = first.open_gap_fingerprints[0]

        second = _plan(
            coverage_ids=coverage,
            required_probe_ids=probes,
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        resolved_failure = _verified_signal(second, receipt_id="receipt-failure-2", receipt_fingerprint="receipt-failure-fp-2")
        new_timeout = _open_signal(
            signal_id="gap-checkout-timeout",
            coverage_id="checkout.timeout",
            probe_id="probe.checkout.timeout",
            prediction="timeout returns to the retryable state",
            falsifier="timeout reaches an absorbing unmodeled state",
            evidence_id="trace-timeout-2",
            evidence_fingerprint="trace-timeout-fp-2",
        )
        second = replace(
            second,
            signals=(resolved_failure, new_timeout),
            resolved_gap_receipts={old_gap: _gap_receipt(second, old_gap)},
        )
        report = review_model_maturation_loop(second)
        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertTrue(report.iteration_record.introduced_gap_fingerprints)

    def test_three_iteration_session_closes_only_on_final_candidate(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        second_signal = _verified_signal(
            second_plan,
            resolved=False,
            evidence_id="trace-2",
            evidence_fingerprint="trace-fingerprint-2",
            receipt_evidence_fingerprint="trace-fingerprint-2",
            receipt_id="progress-receipt-2",
            receipt_fingerprint="progress-receipt-fp-2",
        )
        second_plan = replace(second_plan, signals=(second_signal,))
        second = review_model_maturation_loop(second_plan)
        third_plan = _plan(
            iteration=2,
            prior_iteration_fingerprint=second.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_2_FP,
            prior_gap_fingerprints=second.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_2_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_3_FP,
            prior_evidence_fingerprint="evidence-2",
            evidence_fingerprint="evidence-3",
        )
        third_signal = _verified_signal(
            third_plan,
            evidence_id="trace-3",
            evidence_fingerprint="trace-fingerprint-3",
            receipt_evidence_fingerprint="trace-fingerprint-3",
            receipt_id="receipt-3",
            receipt_fingerprint="receipt-fp-3",
        )
        third_plan = replace(
            third_plan,
            signals=(third_signal,),
            resolved_gap_receipts={gap: _gap_receipt(third_plan, gap)},
        )
        session = review_model_maturation_session((first_plan, second_plan, third_plan))
        self.assertTrue(session.closed)
        self.assertEqual(len(session.iterations), 3)

    def test_session_rejects_predecessor_or_model_chain_mismatch(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        second = _plan(
            iteration=1,
            prior_iteration_fingerprint="wrong-predecessor",
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="wrong-base",
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            signals=(_open_signal(),),
        )
        session = review_model_maturation_session((first_plan, second))

        self.assertFalse(session.closed)
        self.assertIn("session_predecessor_mismatch", {finding.code for finding in session.findings})

    def test_session_rejects_task_purpose_drift(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        second = _plan(
            task_purpose="a different task was substituted",
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint=MODEL_CANDIDATE_FP,
            candidate_model_fingerprint=MODEL_CANDIDATE_2_FP,
            signals=(_open_signal(),),
        )
        session = review_model_maturation_session((first_plan, second))
        self.assertIn("session_identity_mismatch", {finding.code for finding in session.findings})

    def test_no_progress_and_iteration_limit_are_terminal(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        common = {
            "iteration": 1,
            "prior_iteration_fingerprint": first.iteration_record.fingerprint(),
            "prior_candidate_fingerprint": MODEL_CANDIDATE_FP,
            "prior_gap_fingerprints": first.open_gap_fingerprints,
            "base_model_fingerprint": MODEL_CANDIDATE_FP,
            "candidate_model_fingerprint": MODEL_CANDIDATE_FP,
            "prior_evidence_fingerprint": "evidence-1",
            "evidence_fingerprint": "evidence-1",
            "signals": (_open_signal(),),
        }
        stalled = review_model_maturation_loop(_plan(**common))
        self.assertEqual(stalled.decision, MODEL_MATURATION_DECISION_PROGRESS_STALLED)
        self.assertEqual(stalled.terminal_reason, MODEL_MATURATION_DECISION_PROGRESS_STALLED)

        limited = review_model_maturation_loop(_plan(**{**common, "max_iterations": 1}))
        self.assertEqual(limited.decision, MODEL_MATURATION_DECISION_ITERATION_LIMIT)

    def test_repeated_candidate_evidence_and_gap_state_is_oscillation(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        repeated_state = _fingerprint(
            {
                "candidate": MODEL_CANDIDATE_FP,
                "evidence": "evidence-1",
                "open_gaps": sorted(first.open_gap_fingerprints),
            }
        )
        report = review_model_maturation_loop(
            _plan(
                iteration=1,
                prior_iteration_fingerprint=first.iteration_record.fingerprint(),
                prior_candidate_fingerprint=MODEL_CANDIDATE_FP,
                prior_gap_fingerprints=first.open_gap_fingerprints,
                prior_state_fingerprints=(repeated_state,),
                base_model_fingerprint=MODEL_CANDIDATE_FP,
                candidate_model_fingerprint=MODEL_CANDIDATE_FP,
                prior_evidence_fingerprint="evidence-1",
                evidence_fingerprint="evidence-1",
                signals=(_open_signal(),),
            )
        )
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_PROGRESS_STALLED)
        self.assertIn("model_maturation_oscillation", {item.code for item in report.findings})

    def test_self_reported_understanding_is_rejected(self):
        report = review_model_maturation_loop(
            _plan(signals=(_open_signal(metadata={"understood": True, "understanding_level": "deep"}),))
        )
        self.assertIn("self_report_not_evidence", {finding.code for finding in report.findings})
        self.assertIn(MATURITY_ACTION_ADD_MODEL_OBLIGATION, report.recommended_actions)

    def test_gap_identity_does_not_change_when_evidence_changes(self):
        before = _open_signal(evidence_id="trace-1", evidence_fingerprint="evidence-1")
        after = replace(before, evidence_id="trace-2", evidence_fingerprint="evidence-2")
        self.assertEqual(before.gap_fingerprint(), after.gap_fingerprint())

    def test_current_schema_round_trips_and_former_payload_is_rejected(self):
        plan = _plan(signals=(_open_signal(),))
        self.assertEqual(ModelMaturationPlan.from_dict(plan.to_dict()), plan)
        former = dict(plan.to_dict())
        former.pop("schema_version")
        with self.assertRaises(ValueError):
            ModelMaturationPlan.from_dict(former)
        disguised_former = dict(plan.to_dict())
        disguised_former["claim_scope"] = "full"
        with self.assertRaises(ValueError):
            ModelMaturationPlan.from_dict(disguised_former)

    def test_resolution_class_cannot_hide_in_metadata(self):
        report = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        resolution_class="",
                        metadata={"resolution_class": MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED},
                    ),
                )
            )
        )
        self.assertIn("invalid_resolution_class", {item.code for item in report.findings})
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)

    def test_current_owner_result_is_kept_and_retired_cli_route_is_rejected(self):
        plan = _plan()
        plan = replace(plan, signals=(_verified_signal(plan),))
        report = review_model_maturation_loop(plan)
        self.assertTrue(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_CLOSED_FOR_TASK)

        # Model maturation remains a domain-owned result.  The compact public
        # boundary admits only read/change/release; it must reject the retired
        # command without reading a plan or starting a producer.
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["model-maturation-review", "--json"])
        terminal = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", terminal["status"])
        self.assertEqual("block", terminal["decision"])
        self.assertEqual(0, terminal["producer_count"])
        self.assertEqual(["read", "change", "release"], terminal["allowed_operations"])

    def test_signal_can_override_the_default_model_action(self):
        report = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                        suggested_actions=(MATURITY_ACTION_ADD_STATE_FIELD,),
                    ),
                )
            )
        )
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)

    def test_coverage_fingerprint_helper_matches_runtime_contract(self):
        plan = _plan()
        expected = _fingerprint(
            {
                "coverage_universe_id": plan.coverage_universe_id,
                "coverage_demand_fingerprint": plan.coverage_demand_fingerprint,
                "coverage_owner": plan.coverage_owner,
                "coverage_source_refs": list(plan.coverage_source_refs),
                "coverage_ids": list(plan.coverage_ids),
                "required_probe_ids": list(plan.required_probe_ids),
            }
        )
        self.assertEqual(plan.coverage_universe_fingerprint, expected)


if __name__ == "__main__":
    unittest.main()


def test_required_architecture_gap_blocks_improvement_completion():
    from flowguard.model_maturation_receipt import _path_quality_closure_findings
    subject, result = _path_quality("model:fixture", "sha256:" + "a" * 64, "revision:fixture")
    gap = "required_architecture_objective_unmet:objective:fixture:service-layer-writer"
    result = replace(result, finding_ids=(gap,), unresolved_ids=(gap,), conclusion="unresolved")
    assert not result.observation_gap_ids and result.improvement_gap_ids == (gap,)
    findings = _path_quality_closure_findings((subject.model_id,), (subject,), (result,), primary_model_id=subject.model_id, candidate_model_fingerprint=subject.model_fingerprint)
    assert "maturation_path_quality_improvement_incomplete" in findings
    assert "maturation_path_quality_unresolved" in findings


def test_architecture_direction_has_no_unrestricted_optimum_claim(tmp_path):
    from flowguard.model_intent import derive_architecture_objective_projection
    from flowguard.model_path_quality import evaluate_architecture_objectives
    from tests.test_model_intent import _r6_objective_view
    from tests.test_model_path_quality import _r6_fact
    view, contribution, source = _r6_objective_view(tmp_path)
    goals = derive_architecture_objective_projection(view, source_bytes_by_contribution_id={contribution.contribution_id: source})
    facts = (_r6_fact(model="alpha", layer="layer:UI"),)
    # Match the exact declared responsibility, without renaming runtime facts.
    facts = (replace(facts[0], responsibility_id="responsibility:writer"),)
    result = evaluate_architecture_objectives(goals, facts)
    assert result["suggestions"][0]["action"] == "relocate_responsibility"
    assert result["suggestions"][0]["lane"] == "normative_target"
    assert result["architecture_objective_status"] == "blocked"
    assert not any(word in json.dumps(result) for word in ("global_optimum", "unrestricted_optimum"))


def test_generic_architecture_direction_uses_current_facts_and_finite_goal(tmp_path):
    from flowguard.model_intent import derive_architecture_objective_projection
    from flowguard.model_path_quality import evaluate_architecture_objectives
    from tests.test_model_intent import _r6_objective_view
    from tests.test_model_path_quality import _r6_fact
    view, contribution, source = _r6_objective_view(tmp_path)
    goals = derive_architecture_objective_projection(view, source_bytes_by_contribution_id={contribution.contribution_id: source})
    writer = replace(_r6_fact(model="alpha", layer="layer:UI"), responsibility_id="responsibility:writer")
    before = writer.to_dict()
    unmet = evaluate_architecture_objectives(goals, (writer,))
    assert unmet["improvement_gap_ids"] == ["required_architecture_objective_unmet:objective:fixture:service-layer-writer"]
    assert writer.to_dict() == before
    moved = replace(writer, layer_id="layer:service")
    satisfied = evaluate_architecture_objectives(goals, (moved,))
    assert satisfied["satisfied_objective_ids"] == ["objective:fixture:service-layer-writer"]
    assert not satisfied["improvement_gap_ids"] and not satisfied["suggestions"]
