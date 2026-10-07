"""Direct-current explicit compiler owner admission, without running a compiler."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.implementation_inventory import implementation_surface_id
from flowguard.native_case_protocol import NativeCaseBinding, GOOD_DIMENSIONS, BAD_DIMENSIONS, BOUNDARY_DIMENSIONS
from scripts.compile_native_case_mapping import (
    CompileError, _producer_override_bindings, _validate_current_producer_extensions,
)


@pytest.fixture
def explicit_owner(tmp_path):
    model = "explicit_domain"
    mp = ".flowguard/models/owners/explicit_domain/model.py"
    rp = ".flowguard/verification/owners/explicit_domain/run_checks.py"
    for path in (mp, rp):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# actual fixture Source identity\nVALUE = 1\n", encoding="utf-8")
    good, bad = "case:explicit_domain:positive", "case:explicit_domain:reject_wrong_effect"
    boundary = "case:explicit_domain:boundary:finite-domain"
    purpose = build_model_purpose_closure(
        model_instance_id="regression:explicit_domain:current", reusable_model_type_id=model,
        task_intent_id="task:explicit-domain", guarded_purpose="Reject the declared wrong-effect finite counterexample.",
        protected_failure_ids=("wrong_effect",), known_good_case_id=good,
        failure_bindings=({"failure_id": "wrong_effect", "known_bad_case_id": bad, "oracle_id": "native:explicit-domain"},),
        claim_boundary="Only the explicitly declared finite fixture Source identities and native case contracts are admitted; no execution occurred.",
        evidence_check_ids=("check:explicit-domain",), model_sha256=file_fingerprint(tmp_path / mp), runner_sha256=file_fingerprint(tmp_path / rp),
    ).to_dict()
    manifest = {"models": [{"model_id": "historic"}, {"model_id": model, "model_kind": "native_check_contract", "model_path": mp, "runner": ["{python}", rp], "purpose_closure": purpose}]}
    surface_key = mp + "#<module>"
    surface_id = implementation_surface_id(mp, "<module>", "module")
    definition = tmp_path / ".flowguard/models/owners/authoritative_model_system/software_blueprint_definition.json"
    definition.parent.mkdir(parents=True)
    definition.write_text(json.dumps({"composite_behavior_contracts": [
        {"owner_id": "historic", "surface_key": "historical.py#<module>"},
        {"owner_id": model, "surface_key": surface_key},
    ]}), encoding="utf-8")
    def row(native, kind, failures=(), children=()):
        source_id = "boundary:" + model if children else native
        return NativeCaseBinding(
            owner_id="model:" + model, blueprint_case_id=f"behavior-case:{surface_id}:{kind}:{source_id}",
            blueprint_source_case_id=source_id, native_case_ids=(native,), case_kind=kind,
            evidence_scope="implementation_boundary", covered_dimensions=GOOD_DIMENSIONS if kind == "good" else BAD_DIMENSIONS if kind == "bad" else BOUNDARY_DIMENSIONS,
            expected_status="pass", expected_observed_status="violation" if kind == "bad" else "ok",
            protected_failure_ids=failures, required_child_case_ids=children,
        )
    bindings = (row(good, "good"), row(bad, "bad", ("wrong_effect",)), row(boundary, "boundary", children=(good, bad)))
    source = {"schema_version": "flowguard.native_case_producer_overrides.v2", "bindings": [], "composite_owner_declarations": [{
        "model_id": model, "model_path": mp, "runner_path": rp, "composite_surface_key": surface_key,
        "native_leaf_case_ids": [good, bad], "good_native_case_ids": [good],
        "protected_failure_bindings": [{"failure_id": "wrong_effect", "native_case_id": bad}],
        "boundary_native_case_id": boundary,
    }]}
    return tmp_path, manifest, source, bindings


def validate(fixture, *, manifest=None, source=None, bindings=None, surfaces=None):
    root, current, declaration, rows = fixture
    _validate_current_producer_extensions(
        root, current if manifest is None else manifest, {"historic"},
        {"historic", "explicit_domain"} if surfaces is None else surfaces,
        declaration if source is None else source, rows if bindings is None else bindings,
    )


def test_explicit_current_owner_is_admitted_without_custom_owner_name_registry(explicit_owner):
    validate(explicit_owner)


def test_unknown_override_owner_blocks_before_registry_compilation(explicit_owner):
    rows = (*explicit_owner[3], replace(explicit_owner[3][0], owner_id="model:foreign", blueprint_case_id="behavior:foreign"))
    with pytest.raises(CompileError, match="unknown current owner"):
        validate(explicit_owner, bindings=rows)


def test_missing_protected_failure_declaration_blocks(explicit_owner):
    source = deepcopy(explicit_owner[2])
    source["composite_owner_declarations"][0]["protected_failure_bindings"] = []
    with pytest.raises(CompileError, match="protected failures"):
        validate(explicit_owner, source=source)


def test_declared_surface_must_equal_actual_current_blueprint_source(explicit_owner):
    root, manifest, source, bindings = explicit_owner
    path = root / ".flowguard/models/owners/authoritative_model_system/software_blueprint_definition.json"
    definition = json.loads(path.read_text(encoding="utf-8"))
    definition["composite_behavior_contracts"][1]["surface_key"] = "other.py#<module>"
    path.write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(CompileError, match="surface does not match"):
        validate(explicit_owner)


@pytest.mark.parametrize("mutation", ["missing_boundary", "incomplete_children", "duplicate_boundary", "missing_atomic"])
def test_boundary_requires_exact_complete_atomic_denominator(explicit_owner, mutation):
    rows = explicit_owner[3]
    if mutation == "missing_boundary": rows = rows[:-1]
    elif mutation == "incomplete_children": rows = (*rows[:-1], replace(rows[-1], required_child_case_ids=(rows[0].native_case_ids[0],)))
    elif mutation == "duplicate_boundary": rows = (*rows, replace(rows[-1], blueprint_case_id="behavior:second-boundary"))
    else: rows = (rows[0], rows[2])
    with pytest.raises(CompileError, match="boundary|atomic"):
        validate(explicit_owner, bindings=rows)


def test_composite_inventory_and_current_source_drift_block(explicit_owner):
    with pytest.raises(CompileError, match="exactly match current manifest"):
        validate(explicit_owner, surfaces={"historic"})
    model_path = explicit_owner[0] / explicit_owner[2]["composite_owner_declarations"][0]["model_path"]
    model_path.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(CompileError, match="purpose/Source identity"):
        validate(explicit_owner)


@pytest.mark.parametrize("mutation", ["old_schema", "missing_declarations", "unknown_field", "duplicate_json_key", "nonfinite"])
def test_only_strict_current_v2_source_is_read(explicit_owner, mutation):
    root, manifest, source, bindings = explicit_owner
    source = deepcopy(source)
    source["bindings"] = [{key: value for key, value in row.to_dict(include_fingerprint=False).items() if key not in {"schema_version", "mapping_fingerprint"}} for row in bindings]
    if mutation == "old_schema": source["schema_version"] = "flowguard.native_case_producer_overrides.v1"
    elif mutation == "missing_declarations": del source["composite_owner_declarations"]
    elif mutation == "unknown_field": source["unknown"] = True
    path = root / "source.json"
    text = json.dumps(source)
    if mutation == "duplicate_json_key": text = text[:-1] + ',"bindings":[]}'
    elif mutation == "nonfinite": text = text[:-1] + ',"invalid":NaN}'
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CompileError):
        _producer_override_bindings(path, NativeCaseBinding)
