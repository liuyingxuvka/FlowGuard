"""Map-based replacements for the ledger-coupled project-inventory preflight tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flowguard import BehaviorCommitmentHit, REUSE_DECISION_NO_MODEL_FOUND, review_existing_model_preflight
from flowguard.existing_model_preflight import (
    PREFLIGHT_INVENTORY_BROAD,
    existing_model_preflight_from_project,
)
from flowguard.map.cli import main as map_main


def _project(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/router.py").write_text("from app import store\n\ndef dispatch(task):\n    return store.save(task)\n", encoding="utf-8")
    (tmp_path / "app/store.py").write_text("def save(task):\n    return task\n", encoding="utf-8")
    (tmp_path / "app/ui.py").write_text("def render():\n    return 'ui'\n", encoding="utf-8")
    models = tmp_path / ".flowguard/models"
    models.mkdir(parents=True)
    (models / "router.py").write_text(
        '"""FlowGuard model.\n\nPurpose: route each task exactly once.\nnever drops a task.\n\nGuards against: double dispatch.\n"""\n'
        "from flowguard import Workflow\n"
        "class RouterState:\n    pending: int = 0\n"
        "class DispatchTask: pass\n"
        'side_effects_owned = ("effect:dispatch",)\n'
        'fields_owned = ("field:dispatch_mode",)\n', encoding="utf-8")
    comp = lambda cid, files, deps=(), models=(), resp=("x",): {
        "id": cid, "layer": "", "summary": cid + " summary", "responsibilities": list(resp), "files": list(files),
        "entrypoints": [f"{files[0]}:main"], "state": [], "side_effects": [], "depends_on": list(deps),
        "tests": [], "models": list(models), "status": "draft", "fingerprint": ""}
    data = {"schema": "flowguard.map.v1", "project": "demo", "layers": [], "ignore": [], "components": [
        comp("router", ["app/router.py"], ["store"], [".flowguard/models/router.py"], ("route scheduling", "dispatch tasks")),
        comp("store", ["app/store.py"], resp=("persist tasks",)),
        comp("ui", ["app/ui.py"], resp=("render pages",)),
    ], "flows": [], "accepted_debts": []}
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    assert map_main(["--root", str(tmp_path), "confirm", "all"]) == 0
    return tmp_path


def test_changed_path_selects_owner_and_one_hop_dependency_light_vs_full(tmp_path):
    root = _project(tmp_path)
    light = existing_model_preflight_from_project(root, "change dispatch", changed_paths=("app/router.py",), mode="light")
    full = existing_model_preflight_from_project(root, "change dispatch", changed_paths=("app/router.py",), mode="full",
                                                 downstream_routes=("development_process_flow",))
    assert [h.model_id for h in light.relevant_models] == ["router", "store"]
    assert light.relevant_models[0].function_blocks == ()          # light never reads model bodies
    assert full.relevant_models[0].function_blocks == ("RouterState", "DispatchTask")
    assert full.relevant_models[0].state_owned == ("RouterState.pending",)
    assert full.relevant_models[0].side_effects_owned == ("effect:dispatch",)
    assert ("field:dispatch_mode", "router") in full.ownership_snapshot.field_owners
    assert full.canonical_relation_handoff.relation_ids == ("relation:router->store",)
    report = review_existing_model_preflight(full)
    assert report.ok, report.format_text()
    assert report.decision == "full_existing_model_preflight_can_continue"
    broad = existing_model_preflight_from_project(root, "audit", mode="light", inventory_scope=PREFLIGHT_INVENTORY_BROAD)
    assert len(broad.relevant_models) == 3


def test_stale_component_is_kept_as_of_but_blocks_current_claim(tmp_path):
    root = _project(tmp_path)
    (root / "app/router.py").write_text("def dispatch(task):\n    return None\n", encoding="utf-8")
    pre = existing_model_preflight_from_project(root, "change dispatch", changed_paths=("app/router.py",),
                                                downstream_routes=("development_process_flow",))
    assert pre.selected_source_currentness == "stale"
    assert "component_stale:router" in pre.stale_obligations
    router = next(h for h in pre.relevant_models if h.model_id == "router")
    assert router.evidence_current is False
    report = review_existing_model_preflight(pre)
    assert not report.ok
    assert "non_authoritative_model_promoted" in {f.code for f in report.findings}


def test_unmapped_changed_file_is_growth_gap(tmp_path):
    root = _project(tmp_path)
    (root / "app/new_feature.py").write_text("def new():\n    return 1\n", encoding="utf-8")
    pre = existing_model_preflight_from_project(root, "add feature", changed_paths=("app/new_feature.py", "app/deleted.py"),
                                                downstream_routes=("development_process_flow",))
    gaps = {g["path"]: g for g in pre.growth_gaps}
    assert set(gaps) == {"app/new_feature.py", "app/deleted.py"}
    assert gaps["app/deleted.py"]["observed_state"] == "missing"
    assert "model_growth_unbound" in {f.code for f in review_existing_model_preflight(pre).findings}


def test_blocked_commitment_lookup_never_falls_back_to_path_owner(tmp_path):
    root = _project(tmp_path)
    ledger = root / ".flowguard/behavior/inventory/ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    blocked = SimpleNamespace(status="blocked", selected_plane="", primary_hits=(BehaviorCommitmentHit("c:r", "agent_operation", "router", 100),),
                              related_hits=(), candidate_hits=(), plane_ambiguity=False, ledger_fingerprint="")
    with patch("flowguard.existing_model_preflight.query_behavior_commitments_from_path", return_value=blocked):
        pre = existing_model_preflight_from_project(root, "change router", changed_paths=("app/router.py",),
                                                    downstream_routes=("development_process_flow",))
    assert pre.relevant_models == () and pre.ownership_snapshot is None
    assert pre.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND
    codes = {f.code for f in review_existing_model_preflight(pre).findings}
    assert {"behavior_lookup_not_current", "modeled_current_owner_unresolved"} <= codes


def test_performed_commitment_lookup_selects_owner_by_model_path(tmp_path):
    root = _project(tmp_path)
    ledger = root / ".flowguard/behavior/inventory/ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    performed = SimpleNamespace(status="performed", selected_plane="agent_operation",
                                primary_hits=(BehaviorCommitmentHit("c:r", "agent_operation", ".flowguard/models/router.py", 100),),
                                related_hits=(), candidate_hits=(), plane_ambiguity=False, ledger_fingerprint="sha256:l")
    with patch("flowguard.existing_model_preflight.query_behavior_commitments_from_path", return_value=performed):
        pre = existing_model_preflight_from_project(root, "change router", downstream_routes=("development_process_flow",))
    assert [h.model_id for h in pre.relevant_models] == ["router", "store"]
    report = review_existing_model_preflight(pre)
    assert report.ok, report.format_text()


def test_ledger_present_but_unrelated_task_only_warns(tmp_path):
    from flowguard.templates import behavior_commitment_ledger_template_files, write_template_files

    root = _project(tmp_path)
    write_template_files(root, behavior_commitment_ledger_template_files())
    assert (root / ".flowguard/behavior/inventory/ledger.json").is_file()
    pre = existing_model_preflight_from_project(root, "rename internal store helper", changed_paths=("app/store.py",),
                                                mode="full", downstream_routes=("development_process_flow",))
    assert pre.behavior_lookup_required and not pre.primary_commitment_hits
    report = review_existing_model_preflight(pre)
    assert report.ok, report.format_text()
    warning = next(f for f in report.findings if f.code == "behavior_lookup_primary_owner_missing")
    assert warning.severity == "warning"
