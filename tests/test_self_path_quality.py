from __future__ import annotations

import json
from pathlib import Path

import pytest

from flowguard.model_path_quality import path_quality_result_set_fingerprint
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.model_regressions import MANIFEST_SCHEMA
from flowguard.model_system_inventory import build_manifest_model_system_snapshot
from flowguard.self_path_quality import (
    SelfPathQualityError,
    compile_flowguard_self_path_quality_material,
)


WORKFLOW_MODEL = '''
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

@dataclass(frozen=True)
class State:
    admitted: bool = False
    completed: bool = False

class Admit:
    name = "Admit"
    accepted_input_type = str
    reads = ("request",)
    writes = ("admitted",)

    def apply(self, input_obj, state):
        yield FunctionResult(input_obj, replace(state, admitted=True), label="admitted")

class Complete:
    name = "Complete"
    accepted_input_type = str
    reads = ("admitted",)
    writes = ("completed",)

    def apply(self, input_obj, state):
        yield FunctionResult("done", replace(state, completed=True), label="completed")

def completion_is_bound(state, _trace):
    return InvariantResult.pass_() if not state.admitted or state.completed else InvariantResult.fail("incomplete")

INVARIANTS = (
    Invariant("completion_is_bound", "Admitted work reaches the declared terminal state.", completion_is_bound),
)

def correct_workflow():
    return Workflow((Admit(), Complete()), name="two_step_current_path")
'''


EXPORT_MODEL = '''
from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="fixture-export",
        route_id="fixture_export",
        owner_id="fixture_export",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Preserve the explicit exported route and its native evidence boundary.",
        claim_boundary="Projection only; the fixture native runner remains the evidence owner.",
    )
'''


RUNNER = '''
from __future__ import annotations
import model

def main():
    value = getattr(model, "FLOWGUARD_MODEL_MARKER", "")
    return 0 if value else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _entry(root: Path, model_id: str, model_source: str) -> dict[str, object]:
    directory = root / ".flowguard" / model_id
    directory.mkdir(parents=True)
    model_path = directory / "model.py"
    runner_path = directory / "run_checks.py"
    model_path.write_text(model_source, encoding="utf-8")
    runner_path.write_text(RUNNER, encoding="utf-8")
    failure_id = f"failure.{model_id}.bypass"
    purpose = build_model_purpose_closure(
        model_instance_id=f"regression:{model_id}:current",
        reusable_model_type_id=model_id,
        task_intent_id=f"intent.{model_id}",
        guarded_purpose=(
            f"Exercise the exact current {model_id} model path and reject its protected bypass."
        ),
        protected_failure_ids=(failure_id,),
        known_good_case_id=f"case.{model_id}.good",
        failure_bindings=(
            {
                "failure_id": failure_id,
                "known_bad_case_id": f"case.{model_id}.bad",
                "oracle_id": f"oracle.{model_id}.native",
            },
        ),
        claim_boundary=(
            f"This fixture proves only the exact finite {model_id} model and its current native runner evidence."
        ),
        evidence_check_ids=(
            f"check:model-regression:{model_id}",
            f"check.{model_id}.native",
        ),
        model_sha256=file_fingerprint(model_path),
        runner_sha256=file_fingerprint(runner_path),
    )
    return {
        "model_id": model_id,
        "model_path": f".flowguard/{model_id}/model.py",
        "runner": ["{python}", f".flowguard/{model_id}/run_checks.py"],
        "tier": "fast",
        "timeout_seconds": 10,
        "shard_safe": False,
        "mutation_policy": "none",
        "input_globs": [
            f".flowguard/{model_id}/model.py",
            f".flowguard/{model_id}/run_checks.py",
        ],
        "expected_artifacts": [],
        "exclusion_reason": "",
        "distribution_policy": "required_public",
        "absence_reason": "",
        "purpose_closure": purpose.to_dict(),
    }


def _fixture_root(tmp_path: Path) -> Path:
    entries = (
        _entry(tmp_path, "workflow_owner", WORKFLOW_MODEL),
        _entry(tmp_path, "export_owner", EXPORT_MODEL),
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "governed_input_globs": [".flowguard/**/*.py"],
        "snapshot_only_input_globs": [],
        "shared_input_groups": [],
        "models": list(entries),
    }
    (tmp_path / ".flowguard" / "model-regression-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return tmp_path


def _snapshot(root: Path):
    return build_manifest_model_system_snapshot(
        root,
        snapshot_id="self-path-quality-fixture",
        system_id="self-path-quality-fixture",
    )


def test_compiles_dynamic_denominator_from_real_workflow_and_contract_export(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)

    material = compile_flowguard_self_path_quality_material(root, snapshot)

    assert material.ok
    assert material.required_model_ids == ("export_owner", "workflow_owner")
    assert material.review.verified_model_ids == material.required_model_ids
    assert material.deep_required_model_ids == ()
    assert material.triggered_model_ids == ()
    assert material.untriggered_model_ids == material.required_model_ids
    assert material.trigger_census_blocked_model_ids == ()
    assert tuple(item.model_id for item in material.deep_trigger_census) == (
        "export_owner",
        "workflow_owner",
    )
    assert all(
        not item.explicit_deep_request
        and item.declared_candidate_count == 0
        and not item.path_design_model_miss
        and not item.high_cost_boundary
        and not item.release_critical_boundary
        and item.finding_ids == ()
        and item.trigger_ids == ()
        and item.conclusion == "single_clear_path"
        and item.currentness_id == snapshot.fingerprint
        and item.current
        and item.result_available
        for item in material.deep_trigger_census
    )
    assert len(material.details) == 2
    details = {item.model_id: item for item in material.details}
    workflow = details["workflow_owner"]
    exported = details["export_owner"]
    assert workflow.provider_kind == "flowguard.executable-workflow-structure.v1"
    assert len(workflow.model_facts["function_blocks"]) == 2
    assert len(workflow.model_facts["states"]) == 3
    assert exported.provider_kind == "flowguard.executable-contract-export.v1"
    assert len(exported.model_facts["function_blocks"]) == 5
    assert all(
        len(item.necessity_witnesses) == len(item.retained_elements)
        and item.result.conclusion == "single_clear_path"
        for item in material.details
    )
    assert all("language" not in item.model_facts for item in material.details)
    assert material.review.result_set_fingerprint == path_quality_result_set_fingerprint(
        material.required_model_ids,
        material.subjects,
        material.results,
    )
    revision_wire = material.to_revision_material()
    assert set(revision_wire) == {"subjects", "results"}
    assert "details" not in revision_wire
    assert "deep_trigger_census" not in revision_wire
    assert all(
        subject.currentness_id == snapshot.fingerprint
        for subject in material.subjects
    )
    expected_fingerprints = {
        item.logical_model_id: item.fingerprint for item in snapshot.model_instances
    }
    assert {
        item.model_id: item.model_fingerprint for item in material.subjects
    } == expected_fingerprints

    repeated = compile_flowguard_self_path_quality_material(root, snapshot)
    assert repeated.fingerprint == material.fingerprint
    assert repeated.to_revision_material() == revision_wire
    audit = material.to_audit_dict()
    census = audit["deep_trigger_census"]
    assert census["denominator_model_ids"] == ["export_owner", "workflow_owner"]
    assert census["denominator_count"] == 2
    assert census["triggered_model_ids"] == []
    assert census["untriggered_model_ids"] == ["export_owner", "workflow_owner"]
    assert census["blocked_model_ids"] == []
    assert [item["model_id"] for item in census["models"]] == [
        "export_owner",
        "workflow_owner",
    ]


def test_exact_deep_trigger_stays_unresolved_without_candidate_synthesis(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)

    material = compile_flowguard_self_path_quality_material(
        root,
        snapshot,
        explicit_deep_model_ids=("workflow_owner",),
    )

    assert not material.ok
    assert material.deep_required_model_ids == ("workflow_owner",)
    assert material.triggered_model_ids == ("workflow_owner",)
    assert material.untriggered_model_ids == ("export_owner",)
    detail = next(item for item in material.details if item.model_id == "workflow_owner")
    assert detail.result.trigger_ids == ("explicit_request",)
    assert detail.result.conclusion == "unresolved"
    assert detail.result.candidate_ids == ()
    assert detail.result.rewrite_rule_ids == ()
    assert "deep_review_required:explicit_request" in detail.result.unresolved_ids
    census = next(
        item for item in material.deep_trigger_census if item.model_id == "workflow_owner"
    )
    assert census.explicit_deep_request
    assert census.declared_candidate_count == 0
    assert census.finding_ids == ()
    assert census.trigger_ids == ("explicit_request",)
    assert census.conclusion == "unresolved"
    assert census.currentness_id == snapshot.fingerprint
    assert census.current


def test_explicit_and_candidate_count_inputs_are_bound_to_final_trigger_census(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)

    material = compile_flowguard_self_path_quality_material(
        root,
        snapshot,
        explicit_deep_model_ids=("workflow_owner",),
        declared_candidate_counts={"workflow_owner": 2},
    )

    census = next(
        item for item in material.deep_trigger_census if item.model_id == "workflow_owner"
    )
    assert census.explicit_deep_request
    assert census.declared_candidate_count == 2
    assert census.trigger_ids == (
        "explicit_request",
        "multiple_hard_equivalent_candidates",
    )
    assert census.conclusion == "unresolved"
    assert census.result_available
    assert material.triggered_model_ids == ("workflow_owner",)
    assert material.untriggered_model_ids == ("export_owner",)
    assert next(
        item for item in material.details if item.model_id == "workflow_owner"
    ).result.candidate_ids == ()


def test_evidence_derived_trigger_inputs_are_bound_to_final_trigger_census(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)

    material = compile_flowguard_self_path_quality_material(
        root,
        snapshot,
        path_design_model_miss_ids=("workflow_owner",),
        high_cost_model_ids=("workflow_owner",),
        release_critical_model_ids=("workflow_owner",),
    )

    census = next(
        item for item in material.deep_trigger_census if item.model_id == "workflow_owner"
    )
    assert not census.explicit_deep_request
    assert census.declared_candidate_count == 0
    assert census.path_design_model_miss
    assert census.high_cost_boundary
    assert census.release_critical_boundary
    assert census.trigger_ids == (
        "high_cost_boundary",
        "path_design_model_miss",
        "release_critical_boundary",
    )
    assert census.conclusion == "unresolved"
    assert census.result_available
    assert material.triggered_model_ids == ("workflow_owner",)
    assert material.untriggered_model_ids == ("export_owner",)


def test_stale_candidate_snapshot_is_rejected_instead_of_downgraded(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)
    model_path = root / ".flowguard" / "workflow_owner" / "model.py"
    model_path.write_text(WORKFLOW_MODEL + "\n# changed after snapshot\n", encoding="utf-8")

    material = compile_flowguard_self_path_quality_material(root, snapshot)

    assert not material.ok
    assert any(
        gap.startswith("candidate_model_instance_inputs_stale:workflow_owner:")
        for gap in material.global_gaps
    )
    assert "workflow_owner" in material.review.blocked_model_ids
    census = next(
        item for item in material.deep_trigger_census if item.model_id == "workflow_owner"
    )
    assert not census.result_available
    assert census.conclusion == ""
    assert census.currentness_id == ""
    assert material.trigger_census_blocked_model_ids == ("workflow_owner",)


def test_manifest_change_after_snapshot_is_a_hard_currentness_block(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)
    manifest_path = root / ".flowguard" / "model-regression-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["snapshot_only_input_globs"] = [".flowguard/evidence/**/*"]
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SelfPathQualityError, match="exact current model manifest"):
        compile_flowguard_self_path_quality_material(root, snapshot)


def test_required_denominator_and_trigger_scope_reject_foreign_ids(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    snapshot = _snapshot(root)

    with pytest.raises(SelfPathQualityError, match="not current manifest owners"):
        compile_flowguard_self_path_quality_material(
            root,
            snapshot,
            required_model_ids=("foreign_owner",),
        )
    with pytest.raises(SelfPathQualityError, match="outside the required denominator"):
        compile_flowguard_self_path_quality_material(
            root,
            snapshot,
            required_model_ids=("workflow_owner",),
            high_cost_model_ids=("export_owner",),
        )
