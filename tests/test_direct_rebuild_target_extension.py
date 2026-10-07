"""Finite authored-input fixtures; no native acceptance or current authority."""
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.build_direct_model_rebuild_inputs import (
    _authenticate_normative_target_extensions, _load_normative_target_extensions,
)
from flowguard.native_case_runner import r9_functional_code_contracts


def _fixture(tmp_path):
    source = Path(__file__).resolve().parents[1]
    fields = ("target_invariant_ids", "target_obligation_ids", "target_output_ids", "declared_consumer_ids")
    active, subjects = [], []
    for model, relative in (
        ("authoritative_model_system", "openspec/specs/task-aware-functional-map/spec.md"),
        ("model_maturation_loop", "openspec/specs/context-indexed-architecture-direction/spec.md"),
    ):
        text = (source / relative).read_text(encoding="utf-8")
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        goals = json.loads(re.search(r"```flowguard-architecture-objectives\n(.*?)\n```", text, re.S)[1])["objectives"]
        prior_goals = [g for g in goals if g["objective_id"].startswith("objective:r8:")]
        new_goals = [g for g in goals if g["objective_id"].startswith("objective:r9:")]
        consumer = (["consumer:python:flowguard.model_authority_store.read_selected_model_projection",
                     "consumer:python:flowguard.native_case_runner._r9_pointer_detail_observations"]
                    if model == "authoritative_model_system" else
                    ["consumer:python:scripts.produce_flowguard_task_context.main"])
        old = {"target_invariant_ids": tuple(sorted(g["objective_id"] for g in prior_goals)),
               "target_obligation_ids": ("obligation:prior",), "target_output_ids": ("outcome:prior",),
               "declared_consumer_ids": ("consumer:prior",)}
        active.append(SimpleNamespace(contribution_id="prior:" + model, logical_model_id="model:" + model,
            source_ref=relative, native_owner_id="model:" + model, work_context_id="",
            subject_lane="normative_target", **old))
        contracts = [c for c in r9_functional_code_contracts() if c.code_contract_id in {
            v for g in new_goals for v in g["constraint_values"]["required_code_contract_ids"]}]
        subjects.append({"logical_model_id": "model:" + model, "source_ref": relative,
            "target_invariant_ids": sorted(g["objective_id"] for g in new_goals),
            "target_obligation_ids": sorted({v for c in contracts for v in c.implements_obligations}),
            "target_output_ids": sorted({v for c in contracts for v in c.external_outputs}),
            "declared_consumer_ids": sorted(consumer)})
    modules = {
        "flowguard/functional_task_context.py": "def produce_functional_task_context(): pass\n",
        "flowguard/model_authority_store.py": "def _observe_growth_paths(): pass\ndef resolve_architecture_improvement_pointer(): pass\ndef read_selected_model_projection(): return _observe_growth_paths()\n",
        "flowguard/native_case_runner.py": "from .model_authority_store import resolve_architecture_improvement_pointer\ndef _r9_pointer_detail_observations(): return resolve_architecture_improvement_pointer()\n",
        "scripts/produce_flowguard_task_context.py": "from flowguard.functional_task_context import produce_functional_task_context\ndef main(): return produce_functional_task_context()\n",
    }
    for relative, text in modules.items():
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return active, {"schema": "flowguard.normative_target_extensions.v1", "subjects": subjects}, fields


def test_explicit_current_targets_extend_only_reviewed_normative_lineages(tmp_path):
    active, payload, fields = _fixture(tmp_path)
    result = _authenticate_normative_target_extensions(tmp_path, active,
        ("authoritative_model_system", "model_maturation_loop"), payload)
    assert set(result) == {x.contribution_id for x in active}
    for prior, row in zip(active, payload["subjects"]):
        for field in fields:
            assert set(result[prior.contribution_id][field]) == set(getattr(prior, field)) | set(row[field])


@pytest.mark.parametrize("mutation", ("foreign_source", "unreviewed", "goal_drop", "wrong_output", "missing_consumer", "foreign_callee", "duplicate", "foreign_field"))
def test_normative_target_extension_rejects_unlicensed_or_missing_source(tmp_path, mutation):
    active, payload, _ = _fixture(tmp_path)
    payload = copy.deepcopy(payload)
    reviewed = ["authoritative_model_system", "model_maturation_loop"]
    row = payload["subjects"][0]
    if mutation == "foreign_source": row["source_ref"] = "foreign.md"
    elif mutation == "unreviewed": reviewed.remove("authoritative_model_system")
    elif mutation == "goal_drop": row["target_invariant_ids"] = row["target_invariant_ids"][:1]
    elif mutation == "wrong_output": row["target_output_ids"] = ["outcome:invented"]
    elif mutation == "missing_consumer": (tmp_path / "flowguard/native_case_runner.py").write_text("def _r9_pointer_detail_observations(): pass\n", encoding="utf-8")
    elif mutation == "foreign_callee": (tmp_path / "flowguard/native_case_runner.py").write_text("from foreign import resolve_architecture_improvement_pointer\ndef _r9_pointer_detail_observations(): return resolve_architecture_improvement_pointer()\n", encoding="utf-8")
    elif mutation == "duplicate": payload["subjects"].append(row)
    elif mutation == "foreign_field": row["extra"] = True
    with pytest.raises(RuntimeError):
        _authenticate_normative_target_extensions(tmp_path, active, reviewed, payload)


@pytest.mark.parametrize("text", ('{"schema":"first","schema":"second"}', '{"subjects":[NaN]}'))
def test_normative_extension_cli_input_rejects_ambiguous_json(tmp_path, text):
    path = tmp_path / "extensions.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(RuntimeError):
        _load_normative_target_extensions(path)
