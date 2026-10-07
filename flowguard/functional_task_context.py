"""Normal task-context producer and finite consumers of its independent inputs.

Only ``produce_functional_task_context`` writes task artifacts.  Reading a task
never starts native checks, model acceptance, maturation publication, or repair.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .functional_read import (
    exact_record, strict_json_bytes, read_root_reference, parse_task_facts,
    parse_task_coverage_demand, parse_model_maturation_report, functional_gap,
    normalize_observed_path_changes, observed_change_paths, observe_functional_growth_paths,
    load_functional_growth_observation, derive_functional_diagnostic_projection,
    PRODUCER_SOURCE_NAMES,
)

PRODUCER_ID = "flowguard.functional_task_context"
CHECK_IDS = ("existing_model_scope", "accepted_path_quality", "implementation_binding",
             "responsibility_semantics", "native_retained_obligations", "outcome_binding")
REQUEST_FIELDS = ("schema", "task_facts_ref", "primary_model_id", "accepted_head_fingerprint",
                  "producer_contract_ref", "check_manifest_ref", "suite_map_ref")
MATURATION_ROOT = ".flowguard/evidence/skill-native-receipts"
MODEL_ROOT = ".flowguard/evidence/model-owner-receipts"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _version():
    from importlib.metadata import version
    return version("flowguard")


def _raw_reference(root, path):
    path = Path(path)
    relative = path.relative_to(root).as_posix()
    from .model_authority_store import _selected_file_bytes
    return {"path": relative, "sha256": hashlib.sha256(_selected_file_bytes(root, relative)).hexdigest()}


def _write_json(root, output, name, payload):
    path = output / name
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("immutable functional output already exists: " + name)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    return _raw_reference(root, path)


def _read_material_json(root, path, context):
    from .model_authority_store import _selected_file_bytes
    # Preserve the lexical path so the byte supplier can reject every reparse
    # component before opening it; resolving here would conceal a link.
    relative = Path(path).absolute().relative_to(root).as_posix()
    if context is not None:
        return context.json_payload(relative)
    return strict_json_bytes(_selected_file_bytes(root, relative))


def _current_selected_state(root, primary_model_id, context, selected_read=None, required_model_ids=()):
    from .model_authority_store import (
        load_current_model_authority_state, read_selected_model_projection,
        _load_bound_read_projection, bind_selected_read_authority,
    )
    state = load_current_model_authority_state(root, read_context=context)
    if state.accepted_revision is None:
        raise ValueError("task context requires a current accepted revision")
    if selected_read is None:
        projection = _load_bound_read_projection(root, state.head, read_context=context)
        bind_selected_read_authority(context, head=state.head, projection=projection)
        selected = tuple(sorted({primary_model_id, *required_model_ids}))
        # The official selected closure resolves required-neighbor edges.
        selected_read = read_selected_model_projection(root, head=state.head, projection=projection,
            selected_model_ids=selected, read_context=context)
    if selected_read.authority_head_fingerprint != state.head.fingerprint:
        raise ValueError("task context accepted head differs from selected read")
    instances = {row.logical_model_id: row for row in state.snapshot.model_instances}
    if primary_model_id not in instances or primary_model_id not in selected_read.selected_model_ids:
        raise ValueError("task primary model is outside the actual selected closure")
    revision = state.accepted_revision
    subjects = tuple(row for row in revision.path_quality_subjects if row.model_id in selected_read.selected_model_ids)
    results = tuple(row for row in revision.path_quality_results if row.subject_fingerprint in {x.fingerprint for x in subjects})
    details = []
    from .model_path_quality import PathQualityArchitectureDetail
    for result in results:
        raw = context.artifact("path-quality-details", result.detail_evidence_fingerprint)
        detail = PathQualityArchitectureDetail.from_dict(raw)
        subject = next(row for row in subjects if row.fingerprint == result.subject_fingerprint)
        if detail.binding_errors(subject, result):
            raise ValueError("accepted path quality detail has an invalid subject/result binding")
        details.append(detail)
    return state, selected_read, subjects, results, tuple(details)


def _selected_native_leaf_refs(root: Path, state, selected_model_ids: tuple[str, ...], *, read_context):
    """Authenticate the complete parent index and return only named leaf refs.

    The index proves its original table identity, not unselected Source freshness.
    Each returned leaf is independently authenticated by _finite_native_material.
    """
    from .model_regressions import ModelRegressionManifest, _current_model_parent_artifact_path, _read_model_parent_artifact
    root = Path(root).resolve()
    if read_context.root != root or len(selected_model_ids) != len(set(selected_model_ids)):
        raise ValueError("selected native scope is duplicate or belongs to a foreign root")
    if not selected_model_ids:
        raise ValueError("selected native scope is empty")
    manifest_path = root / ".flowguard/models/regression-manifest.json"
    manifest = ModelRegressionManifest.from_payload(_read_material_json(root, manifest_path, read_context), root=root)
    inventory = tuple(row.model_id for row in manifest.entries)
    accepted = tuple(row.logical_model_id for row in state.snapshot.model_instances)
    if (len(inventory) != len(set(inventory)) or len(accepted) != len(set(accepted))
            or set(inventory) != set(accepted)):
        raise ValueError("selected native parent inventory differs from full accepted authority")
    if not set(selected_model_ids) <= set(accepted):
        raise ValueError("selected native owner is unknown")
    path = _current_model_parent_artifact_path(root / MODEL_ROOT / "model-parents", read_context=read_context)
    payload, selected, skipped, children = _read_model_parent_artifact(path, read_context=read_context)
    if (payload["status"] != "pass" or payload["tier"] != "full" or payload["claim_scope"] != "full"
            or skipped or set(selected) != set(inventory) or len(selected) != len(inventory)
            or payload["manifest_sha256"] != read_context.functional_fingerprint(".flowguard/models/regression-manifest.json")):
        raise ValueError("selected native parent index is not the exact full current manifest")
    by_model = {row["model_id"]: row for row in children}
    if len(by_model) != len(children) or set(by_model) != set(inventory):
        raise ValueError("selected native parent children are missing, duplicate or foreign")
    ids, fps = set(), set()
    for model, row in by_model.items():
        if (row["receipt_id"] == payload["execution_receipt_id"]
                or row["receipt_fingerprint"] == payload["execution_receipt_fingerprint"]
                or row["receipt_id"] in ids or row["receipt_fingerprint"] in fps):
            raise ValueError("selected native index contains duplicate, foreign or parent-as-leaf evidence")
        ids.add(row["receipt_id"]); fps.add(row["receipt_fingerprint"])
    return tuple({"owner_id": "model:" + model, **{key: by_model[model][key] for key in ("receipt_id", "receipt_fingerprint")}}
                 for model in sorted(selected_model_ids))


def _producer_source_fingerprint(root, name, context):
    """Use the same target bytes when its producer lives inside that target."""
    path = Path(__file__).parent / name
    if path.resolve().is_relative_to(root):
        raw = context.artifact_bytes(path.resolve().relative_to(root).as_posix())
    else:
        raw = path.read_bytes()
        if context.accounting is not None:
            context.accounting.record("flowguard/" + name, raw, "legacy_unshared")
    return hashlib.sha256(raw).hexdigest()


def _finite_native_material(root, state, leaf_refs, context):
    """Verify explicitly named original leaf receipts against current selected inputs.

    This does not rebuild a full model parent or discover unrelated owner inputs.
    The original proof, raw native result and independent source declarations are
    parsed; no binding or current native identity is inferred from a case name.
    """
    from .evidence_receipts import receipt_path, EvidenceReceipt, verify_evidence_receipt
    from .validation_ownership import _proof_path, _build_owner_current, build_owner_receipt_context
    from .model_regressions import ModelRegressionManifest, _model_owner_contract
    from .native_case_protocol import parse_native_architecture_material, NativeModelCaseContract, NativeCaseBinding, NativeModelCaseResult
    from .implementation_inventory import ImplementationSurfaceInventory
    from .model_path_quality import parse_architecture_binding_report, ResponsibilitySemanticEvidenceBinding
    from .model_test_alignment import CodeContract
    from .source_identity import functional_source_fingerprint
    receipt_root = root / MODEL_ROOT
    manifest_path = root / ".flowguard/models/regression-manifest.json"
    manifest = ModelRegressionManifest.from_payload(_read_material_json(root, manifest_path, context), root=root)
    entries = {row.model_id: row for row in manifest.entries}
    from .native_case_mapping import DEFAULT_NATIVE_CASE_MAPPING_PATH, NativeCaseMappingRegistry
    from .native_case_protocol import verify_native_case_bindings
    registry = NativeCaseMappingRegistry.from_payload(_read_material_json(root, root / DEFAULT_NATIVE_CASE_MAPPING_PATH, context))
    manifest_bytes = context.artifact_bytes(manifest_path.relative_to(root).as_posix())
    # The mapping's declared identity is source_file_fingerprint, which
    # canonicalizes text newlines. Keep the cached original bytes for raw
    # integrity joins and normalize only this independent source identity.
    canonical_manifest_bytes = manifest_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if registry.source_manifest_fingerprint != "sha256:" + hashlib.sha256(canonical_manifest_bytes).hexdigest():
        raise ValueError("native mapping manifest is stale")
    for path in registry.source_paths:
        context.artifact_bytes(path)
    instances = {row.logical_model_id: row for row in state.snapshot.model_instances}
    owners = set()
    materials, receipts, contracts, bindings, results = [], [], [], [], []
    receipt_contexts, identities, proof_bindings, classes = {}, {}, {}, {}
    for ref in leaf_refs:
        ref = exact_record(ref, ("owner_id", "receipt_id", "receipt_fingerprint"), "native owner receipt reference")
        owner = ref["owner_id"]
        if not isinstance(owner, str) or not owner.startswith("model:") or owner in owners:
            raise ValueError("duplicate or non-native leaf owner")
        owners.add(owner)
        model = owner.removeprefix("model:")
        if model not in instances or model not in entries:
            raise ValueError("native owner is outside current accepted model inventory")
        receipt = EvidenceReceipt.from_dict(_read_material_json(root, receipt_path(ref["receipt_id"], root, output_directory=receipt_root), context))
        if (receipt.receipt_id != ref["receipt_id"] or receipt.fingerprint != ref["receipt_fingerprint"]
                or receipt.subject_id != "validation-owner:" + owner):
            raise ValueError("original native leaf reference differs from canonical receipt")
        proof_path = _proof_path(receipt_root, receipt)
        if proof_path is None:
            raise ValueError("native leaf has no original proof artifact")
        proof = _read_material_json(root, proof_path, context)
        if context.raw_fingerprint(proof_path.resolve().relative_to(root).as_posix(), artifact=True) != receipt.proof_artifact_fingerprint:
            raise ValueError("original native proof artifact changed")
        # Original declarations may explain a stale finite boundary. They gain
        # no closure authority until all original leaf/current checks below pass.
        model_result = proof["child"]["payload"]["model_result"]
        native_path = Path(model_result["native_case_result_artifact_path"])
        if not native_path.is_absolute():
            native_path = root / native_path
        source = _read_material_json(root, native_path.with_name("native-source.json"), context)
        material = parse_native_architecture_material(source["architecture_material"])
        if material["model_id"] != model:
            raise ValueError("independent native material has a foreign owner")
        declared_inventory = ImplementationSurfaceInventory.from_dict(material["implementation_inventory"])
        declared_report = parse_architecture_binding_report(material["binding_report"])
        context.declared_scopes[declared_inventory.fingerprint] = (declared_inventory, declared_report)
        contract = _model_owner_contract(root, manifest, entries[model], read_context=context)
        rows = []
        for row in instances[model].inputs:
            current = context.functional_fingerprint(row.path)
            if current != row.sha256:
                raise ValueError("accepted native input changed: " + row.path)
            rows.append({"path": row.path, "sha256": current})
        current = _build_owner_current(root, contract, all_contracts=(contract,), resolved_input_manifest=rows)
        verification_context = build_owner_receipt_context(current, receipt, receipt_root, read_context=context)
        if verification_context is None or not verify_evidence_receipt(receipt, verification_context, read_context=context).ok:
            raise ValueError("original native leaf is not exact current")
        verification_context = replace(verification_context, receipt_store_repository_root=str(root),
            receipt_store_output_directory=str(receipt_root))
        receipt_contexts[receipt.receipt_id] = verification_context
        model_result = proof["child"]["payload"]["model_result"]
        native_path = Path(model_result["native_case_result_artifact_path"])
        if not native_path.is_absolute():
            native_path = root / native_path
        raw_results = _read_material_json(root, native_path, context)
        raw_native_bytes = context.artifact_bytes(native_path.resolve().relative_to(root).as_posix())
        if "sha256:" + hashlib.sha256(raw_native_bytes).hexdigest() != model_result["native_case_result_artifact_fingerprint"]:
            raise ValueError("original native result artifact changed")
        source = _read_material_json(root, native_path.with_name("native-source.json"), context)
        material = parse_native_architecture_material(source["architecture_material"])
        if material["model_id"] != model:
            raise ValueError("independent native material has a foreign owner")
        native_rows = raw_results["results"] if isinstance(raw_results, Mapping) else raw_results
        parsed_results = tuple(NativeModelCaseResult.from_dict(row) for row in native_rows)
        owner_bindings = tuple(row for row in registry.bindings if row.owner_id == owner)
        binding_check = verify_native_case_bindings(owner_bindings, parsed_results, mapping_fingerprint=registry.mapping_fingerprint)
        if not binding_check.ok:
            raise ValueError("current original native binding incomplete: " + ",".join(binding_check.findings))
        architecture_case_ids = {row["source_case_id"] for row in material["native_case_contracts"]}
        parsed_bindings = tuple(row for row in owner_bindings if set(row.native_case_ids) <= architecture_case_ids)
        if [row.to_dict() for row in parsed_results] != model_result["native_case_results"]:
            raise ValueError("native artifact differs from original producer projection")
        for row in (*material["source_refs"], *material["observed_source_inputs"]):
            expected = row.get("sha256", row.get("source_fingerprint"))
            if context.functional_fingerprint(row["path"]) != expected:
                raise ValueError("independent architecture input is stale: " + row["path"])
        materials.append(material); receipts.append(receipt)
        contracts.extend(NativeModelCaseContract.from_dict(row) for row in material["native_case_contracts"])
        bindings.extend(parsed_bindings); results.extend(parsed_results)
        for row in parsed_results:
            identities[(row.owner_id, row.source_case_id)] = {name: getattr(row, name) for name in (
                "input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint")}
        for row in material["responsibility_context_rows"]:
            matches = [binding for binding in parsed_bindings if binding.owner_id == owner and tuple(binding.native_case_ids) == tuple(row["source_case_ids"]) and binding.evidence_scope == "implementation_boundary"]
            if len(matches) != 1:
                raise ValueError("responsibility has no unique original native binding")
            binding = ResponsibilitySemanticEvidenceBinding(row["hard_dimension_id"], row["input_class_id"], row["semantic_spec_id"], row["oracle_id"], matches[0].fingerprint,
                receipt.receipt_id, receipt.fingerprint, owner, tuple(row["source_case_ids"]), "implementation_boundary")
            proof_bindings.setdefault(row["responsibility_id"], []).append(binding)
            for case in row["source_case_ids"]:
                classes.setdefault((owner, case), set()).add(row["input_class_id"])
    if not materials:
        raise ValueError("task has no original architecture native material")
    denominator = _combine_native_denominators(materials)
    # The finite native denominator is now independently current. This does
    # not add a software_architecture scope proof or raise global confidence.
    scope = (denominator["implementation_inventory"], denominator["binding_report"])
    context.declared_scopes[scope[0].fingerprint] = scope
    context.authenticated_scopes[scope[0].fingerprint] = scope
    for original in materials:
        inventory = ImplementationSurfaceInventory.from_dict(original["implementation_inventory"])
        report = parse_architecture_binding_report(original["binding_report"])
        context.authenticated_scopes[inventory.fingerprint] = (inventory, report)
    return {**denominator,
        "owner_materials": {"model:" + row["model_id"]:row for row in materials},
        "native_contracts": tuple(contracts), "native_bindings": tuple(bindings), "native_results": tuple(results),
        "receipts": tuple(receipts), "receipt_contexts": receipt_contexts, "raw_artifact_root": root,
        "current_native_identities": identities, "native_input_class_ids": {k:tuple(sorted(v)) for k,v in classes.items()},
        "responsibility_evidence_bindings": {k:tuple(v) for k,v in proof_bindings.items()}}


def _combine_native_denominators(materials):
    """Pure union of authenticated declarations; conflicts remain blocked."""
    from .implementation_inventory import ImplementationSurfaceInventory, SoftwareBoundary, review_implementation_surface_inventory
    from .implementation_blueprint import review_model_implementation_bindings
    from .model_path_quality import parse_architecture_binding_report
    from .model_test_alignment import CodeContract
    from .model_authority import canonical_fingerprint
    inventory_rows = {row["implementation_inventory"]["inventory_fingerprint"]: ImplementationSurfaceInventory.from_dict(row["implementation_inventory"]) for row in materials}
    parsed_reports = tuple(parse_architecture_binding_report(row["binding_report"]) for row in materials)
    reports = {row.fingerprint: row for row in parsed_reports}
    def unique(rows, key):
        values = {}
        for row in rows:
            identity = key(row)
            if identity in values and values[identity] != row:
                raise ValueError("independent architecture inputs conflict: " + str(identity))
            values[identity] = row
        return tuple(values[key] for key in sorted(values))
    observed = unique((row for material in materials for row in material["observed_source_inputs"]), lambda row: row["path"])
    codes = unique((CodeContract(**row) for material in materials for row in material["code_contracts"]), lambda row: row.code_contract_id)
    if len(inventory_rows) == len(reports) == 1:
        inventory, report = next(iter(inventory_rows.values())), next(iter(reports.values()))
    else:
        inventories = tuple(inventory_rows.values())
        if any(row.boundary.exclusions for row in inventories):
            raise ValueError("multiple independent boundaries require an explicit exclusion-union contract")
        groups = {name: tuple(sorted({path for row in inventories for path in row.boundary.pattern_groups()[name]})) for name in inventories[0].boundary.pattern_groups()}
        boundary = SoftwareBoundary("boundary:functional-union:" + canonical_fingerprint(sorted(inventory_rows)).removeprefix("sha256:"),
            "functional-view", **{name + "_patterns": paths for name,paths in groups.items()})
        manifest_rows = unique((row for material in materials for row in material["resolved_manifest_rows"]), lambda row: row["path"])
        inventory = ImplementationSurfaceInventory("inventory:functional-union:" + boundary.boundary_id.rsplit(":",1)[1], boundary,
            canonical_fingerprint(list(manifest_rows)), unique((row for inv in inventories for row in inv.file_dispositions), lambda row: row.path),
            unique((row for inv in inventories for row in inv.surfaces), lambda row: row.surface_id),
            unique((row for inv in inventories for row in inv.findings), lambda row: (row.code, row.path, row.surface_id)),
            "Finite union of independently authenticated current source boundaries; no additional software scope.")
        report = review_model_implementation_bindings(inventory,
            required_model_element_ids=tuple(sorted({value for row in reports.values() for value in row.required_model_element_ids})),
            bindings=unique((item for row in reports.values() for item in row.bindings), lambda row: row.binding_id),
            semantic_specs=unique((item for row in reports.values() for item in row.semantic_specs), lambda row: row.semantic_spec_id),
            oracles=unique((item for row in reports.values() for item in row.oracles), lambda row: row.oracle_id))
    if not review_implementation_surface_inventory(inventory).ok or not report.ok:
        raise ValueError("combined independent implementation scope is incomplete")
    return {"implementation_inventory": inventory, "binding_report": report, "code_contracts": codes,
        "observed_source_inputs": observed, "current_source_fingerprints": {row["path"]:row["sha256"] for row in observed}}


def _native_subset(material):
    names = ("code_contracts", "native_contracts", "native_bindings", "native_results", "receipts", "receipt_contexts", "raw_artifact_root", "current_native_identities")
    return {name: material[name] for name in names}


def _outcomes(facts, selected, view, material):
    """Join a declared external output to its actual code/owner obligations."""
    result = []
    binding_report = material["binding_report"]
    codes = {row.code_contract_id:row for row in material["code_contracts"]}
    cases = {(row.owner_id,row.source_case_id):row for row in material["native_contracts"]}
    for outcome in facts.requested_outcome_ids:
        for contribution in view.active_contributions:
            if contribution.logical_model_id.removeprefix("model:") not in selected.selected_model_ids:
                continue
            owner = "model:" + contribution.logical_model_id.removeprefix("model:")
            if outcome in contribution.target_obligation_ids:
                targets = (outcome,)
                output_codes = None
            elif outcome in contribution.target_output_ids:
                output_codes = {code.code_contract_id:code for code in codes.values()
                    if outcome in code.external_outputs and any(
                        binding.owner_contract_id == code.code_contract_id
                        and binding.implementation_owner_id == owner
                        and binding.implementation_surface_id in facts.affected_surface_ids
                        for binding in binding_report.bindings)}
                targets = tuple(sorted({target for code in output_codes.values()
                    for target in (*code.implements_obligations, *code.relation_code_obligation_ids)
                    if target in contribution.target_obligation_ids}))
            else:
                continue
            for target in targets:
                matches = [row for row in binding_report.bindings
                    if target in row.model_obligation_ids
                    and row.implementation_owner_id == owner
                    and (output_codes is None or row.owner_contract_id in output_codes)]
                native = [row for row in material["native_bindings"] if row.owner_id == owner
                    and row.native_case_ids and all(
                    (row.owner_id, case) in cases and any(item.owner_contract_id in codes
                        and cases[(row.owner_id,case)].callable_ref == codes[item.owner_contract_id].path + "#" + codes[item.owner_contract_id].symbol
                        and target in {*codes[item.owner_contract_id].implements_obligations, *codes[item.owner_contract_id].relation_code_obligation_ids}
                        for item in matches) for case in row.native_case_ids)]
                result.append({"outcome_id": outcome, "contribution_id": contribution.contribution_id,
                    "target_kind": "obligation", "target_id": target,
                    "binding_fingerprints": sorted(row.fingerprint for row in matches),
                    "native_case_binding_fingerprints": sorted(row.fingerprint for row in native)})
    return result


def review_functional_task_prerequisites(*, state, facts, selected_read, subjects, results, details,
                                        material, outcome_refs, preflight, preflight_report, growth_gaps=(), read_context=None):
    """Six independent preconditions, with no final report/receipt/Verified input."""
    from .model_path_quality import review_path_quality_material, ArchitectureResponsibilityFact, verify_responsibility_semantic_evidence, verify_architecture_native_case_refs
    from .implementation_inventory import review_implementation_surface_inventory
    from .implementation_blueprint import review_model_implementation_bindings
    from .model_maturation import review_functional_outcome_bindings
    inventory, binding_report = material["implementation_inventory"], material["binding_report"]
    repeated = review_model_implementation_bindings(inventory, required_model_element_ids=binding_report.required_model_element_ids,
        bindings=binding_report.bindings, semantic_specs=binding_report.semantic_specs, oracles=binding_report.oracles)
    quality = review_path_quality_material(selected_read.selected_model_ids, subjects, results,
        expected_currentness_id=state.snapshot.fingerprint,
        expected_model_fingerprints={row.logical_model_id:row.fingerprint for row in state.snapshot.model_instances
                                     if row.logical_model_id in selected_read.selected_model_ids},
        require_exact_currentness=True, require_exact_model_fingerprints=True)
    responsibility_gaps = []
    responsibility_count = 0
    semantic_args = {name: material[name] for name in ("binding_report", "implementation_inventory", "code_contracts", "native_contracts", "native_results", "native_bindings", "receipts", "receipt_contexts", "raw_artifact_root", "current_source_fingerprints", "current_native_identities", "native_input_class_ids", "observed_source_inputs")}
    for detail in details:
        for raw in detail.body.get("model_facts", {}).get("architecture", {}).get("responsibilities", ()):
            fact = ArchitectureResponsibilityFact.from_dict(raw)
            proofs = material["responsibility_evidence_bindings"].get(fact.responsibility_id, ())
            fact = replace(fact, semantic_evidence_bindings=tuple(proofs))
            original = material["owner_materials"].get(fact.owner_id)
            if original is None:
                raise ValueError("responsibility has no independent owner denominator")
            local_args = {**semantic_args,
                "observed_source_inputs": tuple(original["observed_source_inputs"]),
                "current_source_fingerprints": {row["path"]:row["sha256"] for row in original["observed_source_inputs"]}}
            review = verify_responsibility_semantic_evidence(fact, **local_args, read_context=read_context)
            responsibility_count += 1
            responsibility_gaps.extend(review.gap_ids)
    outcome = review_functional_outcome_bindings(task_facts=facts, selected_read=selected_read,
        current_effective_intent_view=state.accepted_revision.current_effective_intent_view,
        binding_report=binding_report, implementation_inventory=inventory, outcome_refs=outcome_refs, native_materials=_native_subset(material), read_context=read_context)
    payload = {k:v for k,v in _native_subset(material).items() if k != "code_contracts"}
    refs, missing = [], []
    for owner in sorted({row.owner_id for row in material["native_bindings"]}):
        bindings = tuple(row for row in material["native_bindings"] if row.owner_id == owner)
        code_ids = {row.owner_contract_id for row in binding_report.bindings if row.implementation_owner_id == owner}
        required = {value for row in material["code_contracts"] if row.code_contract_id in code_ids
                    for value in (*row.implements_obligations, *row.relation_code_obligation_ids)}
        local_refs, local_missing = verify_architecture_native_case_refs(**{**payload, "native_bindings":bindings},
            required_obligation_ids=tuple(sorted(required)), read_context=read_context)
        refs.extend(local_refs); missing.extend(local_missing)
    checks = [
        {"check_id": "existing_model_scope", "ok": preflight_report.ok and preflight.selected_source_currentness == "current" and not preflight.growth_gaps and not growth_gaps, "gap_ids": sorted({row.code for row in preflight_report.findings if row.severity == "blocker"} | {row["gap_id"] for row in growth_gaps})},
        {"check_id": "accepted_path_quality", "ok": quality.ok, "gap_ids": [row.code for row in quality.gaps]},
        {"check_id": "implementation_binding", "ok": review_implementation_surface_inventory(inventory).ok and repeated.ok and repeated.fingerprint == binding_report.fingerprint, "gap_ids": [] if repeated.ok else ["implementation_binding_incomplete"]},
        {"check_id": "responsibility_semantics", "ok": bool(responsibility_count) and not responsibility_gaps, "gap_ids": sorted(set(responsibility_gaps)) or ([] if responsibility_count else ["responsibility_semantics_missing"])},
        {"check_id": "native_retained_obligations", "ok": not missing and len(refs) == sum(len(row.native_case_ids) for row in material["native_bindings"]), "gap_ids": [row["kind"] + ":" + row["reference_id"] for row in missing]},
        {"check_id": "outcome_binding", "ok": outcome["ok"], "gap_ids": outcome["gap_ids"]},
    ]
    return {"schema": "flowguard.functional_task_prerequisites.v1", "task_id": facts.task_id,
        "task_fingerprint": facts.fingerprint, "accepted_head_fingerprint": state.head.fingerprint,
        "checks": checks, "ok": all(row["ok"] for row in checks), "native_execution_count": 0,
        "final_maturation_dependency_count": 0, "outcome_binding": outcome}


def _proof(*, artifact_id, route, command, result_ref, root, started, finished, subject_id,
           subject_fingerprint, obligations, fingerprints):
    from .proof_artifact import ProofArtifactRef
    return ProofArtifactRef(artifact_id, producer_route=route, command=command,
        result_path=str(root / result_ref["path"]), result_status="passed", exit_code=0,
        started_at=started, finished_at=finished, subject_id=subject_id,
        subject_fingerprint=subject_fingerprint, artifact_fingerprints=fingerprints,
        covered_obligation_ids=tuple(obligations))


def _maturation_contribution(facts, demand, report, ref, root, command, started, finished, candidate):
    from .task_coverage_demand import OwnerCoverageResolution
    from .evidence_receipts import fingerprint_value
    from .model_maturation import ModelMaturationCoverageContribution
    obligations = tuple(sorted({item for row in demand.rows if row.triggered and row.owner_route == "model_first_function_flow" for item in row.coverage_ids}))
    resolution_id = "resolution:functional-prerequisites:" + fingerprint_value(report).removeprefix("sha256:")[:24]
    proof_id = "proof:" + resolution_id
    resolution = OwnerCoverageResolution(resolution_id, facts.task_id, demand.demand_id, demand.fingerprint,
        "model_first_function_flow", "satisfied", obligations, evidence_ids=(proof_id,),
        evidence_fingerprints=("sha256:" + ref["sha256"],))
    fingerprints = {"prerequisite_report": "sha256:" + ref["sha256"]}
    proof = _proof(artifact_id=proof_id, route="model_first_function_flow", command=command, result_ref=ref, root=root,
        started=started, finished=finished, subject_id=resolution.resolution_id,
        subject_fingerprint=resolution.fingerprint, obligations=obligations, fingerprints=fingerprints)
    return ModelMaturationCoverageContribution("contribution:" + resolution_id, "model_first_function_flow", facts.task_id,
        coverage_source_refs=(ref["path"],), coverage_ids=obligations, required_probe_ids=CHECK_IDS,
        evidence_ref=proof, owner_resolution=resolution, candidate_model_fingerprint=candidate,
        subject_fingerprints=fingerprints)


def _verification_context(root, report, freeze, input_refs, request, read_context):
    from .evidence_receipts import ReceiptVerificationContext, snapshot_bytes, capture_environment_fingerprint, fingerprint_value
    from .model_maturation_receipt import ModelMaturationVerificationContext, MODEL_MATURATION_RECEIPT_CLAIM_SCOPE
    from .model_authority_store import _selected_file_bytes
    version = _version()
    environment = capture_environment_fingerprint(flowguard_version=version)
    if freeze["producer_id"] != PRODUCER_ID or freeze["producer_version"] != version or freeze["environment"] != environment.to_dict():
        raise ValueError("functional producer or environment changed")
    snapshots = []
    obligations = tuple(freeze["covered_obligation_ids"])
    for reference in input_refs:
        path = reference["path"]
        raw = read_context.artifact_bytes(path) if read_context is not None else _selected_file_bytes(root, path)
        current = (read_context.raw_fingerprint(path, artifact=True).removeprefix("sha256:")
                   if read_context is not None else hashlib.sha256(raw).hexdigest())
        if current != reference["sha256"]:
            raise ValueError("task publication input changed: " + path)
        snapshots.append(snapshot_bytes("functional-input:" + path, raw, path_token="<WORKSPACE>/" + path, obligation_ids=obligations))
    receipt_context = ReceiptVerificationContext(input_snapshots={row.artifact_id:row for row in snapshots},
        contract_hash="sha256:" + request["producer_contract_ref"]["sha256"],
        check_manifest_hash="sha256:" + request["check_manifest_ref"]["sha256"],
        suite_map_hash="sha256:" + request["suite_map_ref"]["sha256"],
        producer_id=PRODUCER_ID, producer_version=version, environment_fingerprint=environment.fingerprint,
        proof_artifact_fingerprint=report.evidence_fingerprint, proof_artifact_id=report.evidence_id,
        result_fingerprint=fingerprint_value(report.to_dict()), command=(freeze["command"],),
        working_directory_token="<WORKSPACE>", required_obligation_ids=obligations,
        eligible_claim_scopes=(MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,),
        receipt_store_repository_root=str(root), receipt_store_output_directory=str(root / MATURATION_ROOT))
    context = ModelMaturationVerificationContext(receipt_context, task_id=report.task_id, model_id=report.model_id,
        candidate_model_fingerprint=report.candidate_model_fingerprint, coverage_demand_fingerprint=report.coverage_demand_fingerprint,
        coverage_universe_id=report.coverage_universe_id, coverage_universe_fingerprint=report.coverage_universe_fingerprint,
        input_fingerprint=report.input_fingerprint, evidence_fingerprint=report.evidence_fingerprint,
        required_path_quality_model_ids=report.required_path_quality_model_ids,
        path_quality_subjects=report.path_quality_subjects, path_quality_results=report.path_quality_results,
        path_quality_result_set_fingerprint=report.path_quality_result_set_fingerprint,
        owner_resolution_ids=report.owner_resolution_ids, owner_resolution_fingerprints=report.owner_resolution_fingerprints,
        owner_resolution_owner_ids=report.owner_resolution_owner_ids)
    return context, tuple(snapshots), environment


def prepare_functional_growth_observation(*, repository_root, task_id, accepted_head_fingerprint,
                                         source_request_ref, declared_path_changes,
                                         output_directory, read_context):
    """Normal producer's exclusive publication of explicitly requested finite states."""
    from .model_authority import canonical_fingerprint
    changes = normalize_observed_path_changes(declared_path_changes)
    if not changes:
        return None
    root = Path(repository_root).resolve()
    source = read_root_reference(root, source_request_ref, read_context)
    if source.get("task_id") != task_id or source.get("declared_path_changes") != changes:
        raise ValueError("functional growth request declaration differs")
    payload = {"schema": "flowguard.functional_growth_observation.v1", "task_id": task_id,
        "accepted_head_fingerprint": accepted_head_fingerprint, "source_kind": "explicit_task_paths",
        "source_request_ref": source_request_ref, "declared_path_changes": changes,
        "observations": observe_functional_growth_paths(read_context, observed_change_paths(changes))}
    payload["observation_fingerprint"] = canonical_fingerprint(payload)
    return _write_json(root, Path(output_directory), "inputs/growth-observation.json", payload)


def _write_functional_diagnostic_context(*, root, output, facts, state, refs, context,
                                        request, command, leaf_refs=()):
    """Publish current original diagnostics, never a receipt or a Verified object."""
    from .model_authority_store import freeze_selected_read_observation, verify_selected_read_observation
    facts_ref = refs.get("facts") or _write_json(root, output, "task-facts.json", facts.to_dict())
    refs["facts"] = facts_ref
    request_ref = _write_json(root, output, "producer-request.json", request)
    # Retain all original bytes actually consumed, including raw Source inputs.
    for ref in refs.values():
        context.artifact_bytes(ref["path"])
    context.artifact_bytes(request_ref["path"])
    producer_sources = {name: _producer_source_fingerprint(root, name, context) for name in PRODUCER_SOURCE_NAMES}
    if not verify_selected_read_observation(freeze_selected_read_observation(context), accounting=context.accounting).ok:
        raise ValueError("functional diagnostic inputs changed during production")
    diagnostic = {"schema": "flowguard.functional_task_diagnostic.v1", "task_id": facts.task_id,
        "accepted_head_fingerprint": state.head.fingerprint, "task_facts_ref": facts_ref,
        "coverage_demand_ref": refs.get("demand") or refs.get("original_demand"),
        "maturation_report_ref": refs.get("report"), "preflight_report_ref": refs.get("preflight"),
        "prerequisite_report_ref": refs.get("prerequisites"),
        "input_refs": [{"path": path, "sha256": hashlib.sha256(raw).hexdigest()}
                       for path, raw in sorted(context.payloads.items())],
        "missing_paths": sorted(context.missing_paths),
        "producer_source_sha256": producer_sources,
        "command": command, "status": "needs_evidence", "first_gap": {}, "gap_ids": [],
        "next_actions": [], "terminal_reason": "needs_evidence",
        "claim_boundary": "diagnostic_observation_only", "growth_report_ref": refs.get("growth")}
    understanding = derive_functional_diagnostic_projection(repository_root=root, diagnostic=diagnostic,
        facts=facts, read_context=context)
    diagnostic.update(first_gap=understanding["first_gap"], gap_ids=understanding["gap_ids"],
        next_actions=understanding["next_actions"], terminal_reason=understanding["stopping_disposition"])
    diagnostic_ref = _write_json(root, output, "diagnostic-result.json", diagnostic)
    doc = {"schema": "flowguard.functional_read_context.v1", "task_id": facts.task_id,
        "context_kind": "diagnostic", "diagnostic_ref": diagnostic_ref, "task_facts_ref": facts_ref,
        "coverage_demand_ref": diagnostic["coverage_demand_ref"],
        "maturation_report_ref": diagnostic["maturation_report_ref"],
        "maturation_receipt_ref": None, "outcome_refs": [], "native_owner_receipt_refs": list(leaf_refs)}
    understanding["gap_report_ref"] = diagnostic_ref
    return {"status": "blocked", "task_context_ref": _write_json(root, output, "task-context.json", doc),
            "functional_understanding": understanding, "report_refs": refs}


def _write_growth_report(*, root, output, facts, state, growth_ref, context):
    from .model_authority_store import _observe_growth_paths
    observed = load_functional_growth_observation(repository_root=root, growth_observation_ref=growth_ref,
        accepted_head_fingerprint=state.head.fingerprint, task_id=facts.task_id, read_context=context)
    growth = _observe_growth_paths(context, observed_change_paths(observed["declared_path_changes"]))
    return _write_json(root, output, "growth-report.json", {
        "schema": "flowguard.functional_growth_report.v1", "task_id": facts.task_id,
        "accepted_head_fingerprint": state.head.fingerprint, "growth_observation_ref": growth_ref,
        **{key: list(value) if isinstance(value, tuple) else value for key, value in growth.items()}}), growth


def produce_functional_task_context(*, repository_root: Path, request: Mapping,
                                    output_directory: Path, command: str) -> Mapping:
    """Produce one task iteration from current domain proofs, without native execution."""
    from .model_authority_store import _SelectedReadContext, freeze_selected_read_observation, verify_selected_read_observation
    from .existing_model_preflight import existing_model_preflight_from_project, review_existing_model_preflight, project_existing_model_preflight_to_task_facts, existing_model_preflight_projection_obligation_ids, project_existing_model_preflight_maturation_contribution
    from .task_coverage_demand import compile_task_coverage_demand, project_owner_resolution_to_demand
    from .model_maturation import ModelMaturationIntake, compile_model_maturation_plan, review_model_maturation_loop
    from .model_maturation_receipt import ModelMaturationReceiptPublication, publish_model_maturation_receipt, verify_model_maturation_receipt
    from .evidence_receipts import capture_environment_fingerprint, fingerprint_value
    root, output = Path(repository_root).resolve(), Path(output_directory).resolve()
    relative_output = output.relative_to(root)
    if relative_output.parts[:3] != (".flowguard", "evidence", "task-contexts") or len(relative_output.parts) < 4:
        raise ValueError("normal task outputs must be inside the canonical task-context evidence root")
    started = _now()
    refs = {}
    authenticated = False
    phase = "input_admission"
    facts, state, context, leaf_refs, growth_ref = None, None, None, [], None
    try:
        request = exact_record(request, REQUEST_FIELDS, "functional producer request")
        if request["schema"] != "flowguard.functional_task_context_request.v1" or not isinstance(command, str) or not command:
            raise ValueError("invalid functional producer request identity")
        context = _SelectedReadContext(root)
        initial = parse_task_facts(read_root_reference(root, request["task_facts_ref"], context))
        manifest = exact_record(read_root_reference(root, request["check_manifest_ref"], context),
            ("schema", "check_ids", "input_refs", "accepted_head_fingerprint", "producer_contract_ref", "environment"), "functional check manifest")
        suite_map = exact_record(read_root_reference(root, request["suite_map_ref"], context),
            ("schema", "owners"), "functional suite map")
        from .model_authority_store import _selected_file_bytes
        contract_ref = exact_record(request["producer_contract_ref"], ("path", "sha256"), "producer contract")
        if contract_ref["path"] != "openspec/specs/model-maturation-receipt/spec.md":
            raise ValueError("producer contract must be the current canonical maturation specification")
        if hashlib.sha256(context.artifact_bytes(contract_ref["path"])).hexdigest() != contract_ref["sha256"]:
            raise ValueError("producer canonical contract changed")
        if (manifest["schema"] != "flowguard.functional_task_checks.v1" or suite_map["schema"] != "flowguard.functional_task_suite.v1"
            or manifest["check_ids"] != list(CHECK_IDS) or suite_map["owners"] != {"existing-model-owner": [CHECK_IDS[0]], "task-model-maturation": list(CHECK_IDS[1:])}
            or manifest["accepted_head_fingerprint"] != request["accepted_head_fingerprint"] or manifest["producer_contract_ref"] != contract_ref
            or manifest["environment"] != capture_environment_fingerprint(flowguard_version=_version()).to_dict()):
            raise ValueError("task check declarations do not cover the six independent prerequisites")
        if not isinstance(manifest["input_refs"], list) or request["task_facts_ref"] not in manifest["input_refs"]:
            raise ValueError("functional checks lack their actual task input")
        for ref in manifest["input_refs"]:
            read_root_reference(root, ref, context)
        state, selected, subjects, results, details = _current_selected_state(root, request["primary_model_id"], context, required_model_ids=initial.related_model_ids)
        if state.head.fingerprint != request["accepted_head_fingerprint"]:
            raise ValueError("functional task accepted head changed")
        snapshots = {row.source_plane:row for row in initial.source_snapshots}
        if set(snapshots) != {"request", "current_model", "public_surface", "lifecycle"}:
            raise ValueError("functional task needs four independently observed source planes")
        planes = {plane:read_root_reference(root, {"path":row.source_ref, "sha256":row.source_fingerprint.removeprefix("sha256:")}, context)
            for plane,row in snapshots.items()}
        if planes["current_model"] != {"accepted_head":state.head.to_dict(), "accepted_revision_fingerprint":state.accepted_revision.fingerprint} or planes["lifecycle"] != {"snapshot_fingerprint":state.snapshot.fingerprint, "lifecycle":state.snapshot.lifecycle, "subject_lane":state.snapshot.subject_lane}:
            raise ValueError("functional task source planes differ from actual accepted authority")
        public_surface = exact_record(planes["public_surface"],
            ("affected_surface_ids", "source", "growth_observation_ref"), "functional public surface plane")
        if public_surface["affected_surface_ids"] != list(initial.affected_surface_ids) or public_surface["growth_observation_ref"] is not None:
            raise ValueError("initial public surface is not an original unobserved demand")
        changes = normalize_observed_path_changes(planes["request"].get("declared_path_changes"))
        if planes["request"] != {"task_id": initial.task_id, "purpose": initial.task_purpose,
                "requested_outcome_ids": list(initial.requested_outcome_ids), "read_only": True,
                "implementation_requested": False, "release_requested": False, "declared_path_changes": changes}:
            raise ValueError("original request task differs")
        if not initial.read_only or initial.implementation_requested or initial.release_requested or initial.change_kinds:
            raise ValueError("this producer requires an honest postaccept readonly task")
        authenticated = True
        facts = initial
        phase = "growth_observation"
        original_request_ref = {"path": snapshots["request"].source_ref,
            "sha256": snapshots["request"].source_fingerprint.removeprefix("sha256:")}
        growth_ref = prepare_functional_growth_observation(repository_root=root, task_id=initial.task_id,
            accepted_head_fingerprint=state.head.fingerprint, source_request_ref=original_request_ref,
            declared_path_changes=changes, output_directory=output, read_context=context)
        if growth_ref is not None:
            from .task_coverage_demand import TaskFactSourceSnapshot
            surface_ref = _write_json(root, output, "observed-public-surface.json",
                {**public_surface, "growth_observation_ref": growth_ref})
            initial = replace(initial, source_snapshots=tuple(
                TaskFactSourceSnapshot("public_surface", surface_ref["path"], "sha256:" + surface_ref["sha256"],
                    reason="Original normal producer finite growth observation") if row.source_plane == "public_surface" else row
                for row in initial.source_snapshots), fact_observations=())
            facts = initial
            context.artifact_bytes(surface_ref["path"])
        phase = "native_material"
        leaf_refs = _selected_native_leaf_refs(root, state, tuple(selected.selected_model_ids), read_context=context)
        material = _finite_native_material(root, state, leaf_refs, context)
        growth = {"growth_gaps": ()}
        if growth_ref is not None:
            refs["growth"], growth = _write_growth_report(root=root, output=output, facts=facts,
                state=state, growth_ref=growth_ref, context=context)
        inventory = material["implementation_inventory"]
        paths = tuple(sorted({row.path for row in inventory.surfaces if row.surface_id in initial.affected_surface_ids}))
        if not paths or not set(initial.affected_surface_ids) <= set(inventory.required_surface_ids):
            raise ValueError("task affected surface has no independent current inventory member")
        from .existing_model_preflight import PREFLIGHT_INVENTORY_SELECTED, PREFLIGHT_MODE_FULL
        phase = "existing_model_scope"
        preflight = existing_model_preflight_from_project(root, initial.task_purpose,
            preflight_id="preflight:" + initial.task_id, changed_paths=selected.selected_model_paths,
            downstream_routes=("model_first_function_flow",), mode=PREFLIGHT_MODE_FULL, inventory_scope=PREFLIGHT_INVENTORY_SELECTED, read_context=context)
        preflight_report = review_existing_model_preflight(preflight)
        refs["preflight"] = _write_json(root, output, "existing-model-preflight.json", {"preflight": preflight.to_dict(), "report": preflight_report.to_dict()})
        if not preflight_report.ok:
            return _write_functional_diagnostic_context(root=root, output=output, facts=facts, state=state,
                refs=refs, context=context, request=request, command=command, leaf_refs=leaf_refs)
        preflight_proof = _proof(artifact_id="proof:" + preflight.preflight_id, route="existing_model_preflight", command=command,
            result_ref=refs["preflight"], root=root, started=started, finished=_now(), subject_id=preflight.preflight_id,
            subject_fingerprint=preflight_report.fingerprint,
            obligations=existing_model_preflight_projection_obligation_ids(preflight, preflight_report),
            fingerprints={"preflight_result": "sha256:" + refs["preflight"]["sha256"]})
        facts = project_existing_model_preflight_to_task_facts(initial, preflight, preflight_report, preflight_proof)
        refs["facts"] = _write_json(root, output, "task-facts.json", facts.to_dict())
        original = compile_task_coverage_demand(facts)
        refs["original_demand"] = _write_json(root, output, "original-coverage-demand.json", original.to_dict())
        outcomes = _outcomes(facts, selected, state.accepted_revision.current_effective_intent_view, material)
        phase = "functional_prerequisites"
        prerequisite = review_functional_task_prerequisites(state=state, facts=facts, selected_read=selected, subjects=subjects,
            results=results, details=details, material=material, outcome_refs=outcomes, preflight=preflight,
            preflight_report=preflight_report, growth_gaps=growth["growth_gaps"], read_context=context)
        refs["prerequisites"] = _write_json(root, output, "prerequisite-report.json", prerequisite)
        if not prerequisite["ok"]:
            return _write_functional_diagnostic_context(root=root, output=output, facts=facts, state=state,
                refs=refs, context=context, request=request, command=command, leaf_refs=leaf_refs)
        candidate = next(row.fingerprint for row in state.snapshot.model_instances if row.logical_model_id == request["primary_model_id"])
        contributions = [project_existing_model_preflight_maturation_contribution(facts, original, preflight, preflight_report,
            preflight_proof, candidate_model_fingerprint=candidate),
            _maturation_contribution(facts, original, prerequisite, refs["prerequisites"], root, command, started, _now(), candidate)]
        supplied = {row.owner_route for row in contributions}
        if set(original.required_owner_ids) - supplied:
            phase = "additional_triggered_route_requires_current_proof"
            raise ValueError(phase + ":" + ",".join(sorted(set(original.required_owner_ids) - supplied)))
        closed = original
        for contribution in sorted(contributions, key=lambda row: row.owner_route):
            closed = project_owner_resolution_to_demand(closed, contribution.owner_resolution)
        refs["demand"] = _write_json(root, output, "coverage-demand.json", closed.to_dict())
        refs["contributions"] = _write_json(root, output, "coverage-contributions.json", [row.to_dict() for row in contributions])
        from .model_authority_store import _read_content_addressed_payload
        from .model_authority import ModelSystemSnapshot
        previous_fp = state.head.previous_snapshot_fingerprint
        predecessor_path = root / ".flowguard/models/authority/snapshots" / (previous_fp.removeprefix("sha256:") + ".json")
        predecessor = ModelSystemSnapshot.from_dict(_read_material_json(root, predecessor_path, context))
        if predecessor.fingerprint != previous_fp:
            raise ValueError("actual predecessor snapshot fingerprint changed")
        bases = {row.logical_model_id:row.fingerprint for row in predecessor.model_instances}
        if request["primary_model_id"] not in bases:
            raise ValueError("functional task primary model has no actual predecessor instance")
        intake = ModelMaturationIntake("intake:" + facts.task_id, "plan:" + facts.task_id, facts.task_id,
            facts.task_purpose, request["primary_model_id"], "risk:" + facts.task_id, bases[request["primary_model_id"]], candidate,
            closed, task_facts=facts, contributions=tuple(contributions), required_path_quality_model_ids=selected.selected_model_ids,
            path_quality_subjects=subjects, path_quality_results=results, iteration=0)
        plan = compile_model_maturation_plan(intake)
        refs["plan"] = _write_json(root, output, "maturation-plan.json", plan.to_dict())
        report = review_model_maturation_loop(plan)
        refs["report"] = _write_json(root, output, "maturation-report.json", report.to_dict())
        if not (report.ok and report.decision == report.terminal_reason == "model_maturation_closed_for_task" and report.confidence == "full" and not report.open_gap_fingerprints and closed.closed):
            return _write_functional_diagnostic_context(root=root, output=output, facts=facts, state=state,
                refs=refs, context=context, request=request, command=command, leaf_refs=leaf_refs)
        request_ref = _write_json(root, output, "producer-request.json", request)
        environment = capture_environment_fingerprint(flowguard_version=_version())
        input_paths = set(context.payloads) | {row["path"] for row in refs.values()} | {request_ref["path"]}
        input_paths.discard(refs["report"]["path"])
        # Source authoring code is frozen even when the target is a different consumer root.
        producer_sources = {name: _producer_source_fingerprint(root, name, context) for name in ("functional_task_context.py", "functional_read.py", "model_maturation.py", "model_maturation_receipt.py")}
        input_paths.update(context.payloads)
        input_paths.discard(refs["report"]["path"])
        input_refs = [{"path":path, "sha256":context.raw_fingerprint(path, artifact=True).removeprefix("sha256:")} for path in sorted(input_paths)]
        obligations = tuple(sorted({item for row in closed.rows if row.triggered for item in row.coverage_ids} | {"functional-prerequisite:" + check for check in CHECK_IDS}))
        freeze = {"schema": "flowguard.functional_task_publication_freeze.v1", "producer_id": PRODUCER_ID,
            "producer_version": _version(), "command": command, "started_at": started, "finished_at": _now(),
            "environment": environment.to_dict(), "accepted_head_fingerprint": state.head.fingerprint,
            "request_ref": request_ref, "input_refs": input_refs, "covered_obligation_ids": list(obligations),
            "producer_source_sha256": producer_sources, "artifact_refs": refs}
        freeze_ref = _write_json(root, output, "producer-freeze.json", freeze)
        input_refs = [*input_refs, freeze_ref]
        guard = verify_selected_read_observation(freeze_selected_read_observation(context), accounting=context.accounting)
        if not guard.ok:
            raise ValueError("functional task inputs changed during prerequisites")
        verification_context, snapshots, environment = _verification_context(root, report, freeze, input_refs, request, context)
        publication = ModelMaturationReceiptPublication(PRODUCER_ID, _version(), (command,), started, freeze["finished_at"],
            environment.metadata, verification_context.receipt_context.contract_hash,
            verification_context.receipt_context.check_manifest_hash, verification_context.receipt_context.suite_map_hash,
            snapshots, obligations)
        receipt_ref = publish_model_maturation_receipt(report, publication, root, output_directory=root / MATURATION_ROOT)
        verification = verify_model_maturation_receipt(receipt_ref, verification_context, root, output_directory=root / MATURATION_ROOT)
        if not verification.ok or verification.verified_maturation is None:
            raise ValueError("new canonical maturation receipt failed independent verification")
        doc = {"schema": "flowguard.functional_read_context.v1", "task_id": facts.task_id,
            "context_kind": "verified_maturation", "diagnostic_ref": None,
            "task_facts_ref": refs["facts"], "coverage_demand_ref": refs["demand"], "maturation_report_ref": refs["report"],
            "maturation_receipt_ref": receipt_ref.to_dict(), "outcome_refs": outcomes, "native_owner_receipt_refs": leaf_refs}
        from .model_maturation import derive_functional_understanding
        understanding = derive_functional_understanding(task_facts=facts, coverage_demand=closed, maturation_report=report,
            verified_maturation=verification.verified_maturation, selected_read=selected,
            current_effective_intent_view=state.accepted_revision.current_effective_intent_view,
            binding_report=material["binding_report"], implementation_inventory=inventory, outcome_refs=outcomes, native_materials=_native_subset(material))
        if understanding["stopping_disposition"] != "model_maturation_closed_for_task":
            return {"status": "blocked", "functional_understanding": understanding, "verification": verification.to_dict(), "report_refs": refs}
        task_context_ref = _write_json(root, output, "task-context.json", doc)
        return {"status": "pass", "task_context_ref": task_context_ref,
            "verification": verification.to_dict(), "functional_understanding": understanding, "report_refs": refs}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        if authenticated and phase != "diagnostic_publication":
            try:
                if growth_ref is not None and "growth" not in refs:
                    refs["growth"], _ = _write_growth_report(root=root, output=output, facts=facts,
                        state=state, growth_ref=growth_ref, context=context)
                refs["prerequisites"] = _write_json(root, output, "original-exception-report.json", {
                    "schema": "flowguard.functional_task_prerequisites.v1", "task_id": facts.task_id,
                    "task_fingerprint": facts.fingerprint, "accepted_head_fingerprint": state.head.fingerprint,
                    "checks": [{"check_id": phase, "ok": False, "gap_ids": [phase]}],
                    "ok": False, "native_execution_count": 0, "final_maturation_dependency_count": 0,
                    "outcome_binding": {"reason": str(exc)}})
                return _write_functional_diagnostic_context(root=root, output=output, facts=facts, state=state,
                    refs=refs, context=context, request=request, command=command, leaf_refs=leaf_refs)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                pass
        return {"status": "blocked", "functional_understanding": functional_gap("functional_task_producer_input_invalid", reference=str(output), reason=str(exc)), "report_refs": refs}


def verify_functional_task_context(*, root, doc, facts, demand, report, selected_read, read_context):
    """The readonly adapter's finite independent verification, never publication."""
    from .model_maturation import ModelMaturationPlan, review_model_maturation_loop, derive_functional_understanding
    from .model_maturation_receipt import ModelMaturationReceiptRef, verify_model_maturation_receipt
    from .evidence_receipts import receipt_path
    directory = (root / doc["maturation_report_ref"]["path"]).parent
    freeze = exact_record(_read_material_json(root, directory / "producer-freeze.json", read_context),
        ("schema", "producer_id", "producer_version", "command", "started_at", "finished_at", "environment",
         "accepted_head_fingerprint", "request_ref", "input_refs", "covered_obligation_ids", "producer_source_sha256", "artifact_refs"),
        "functional publication freeze")
    if freeze["schema"] != "flowguard.functional_task_publication_freeze.v1":
        raise ValueError("missing normal task publication freeze")
    if set(freeze["producer_source_sha256"]) != {"functional_task_context.py", "functional_read.py", "model_maturation.py", "model_maturation_receipt.py"}:
        raise ValueError("functional producer source inventory is incomplete")
    for name, expected in freeze["producer_source_sha256"].items():
        if name not in {"functional_task_context.py", "functional_read.py", "model_maturation.py", "model_maturation_receipt.py"} or _producer_source_fingerprint(root, name, read_context) != expected:
            raise ValueError("functional producer source changed")
    request = read_root_reference(root, freeze["request_ref"], read_context)
    exact_record(request, REQUEST_FIELDS, "original functional producer request")
    state, selected, subjects, results, details = _current_selected_state(root, request["primary_model_id"], read_context, selected_read)
    if state.head.fingerprint != freeze["accepted_head_fingerprint"] or state.head.fingerprint != request["accepted_head_fingerprint"]:
        raise ValueError("functional task accepted head is stale")
    plan = ModelMaturationPlan.from_dict(read_root_reference(root, freeze["artifact_refs"]["plan"], read_context))
    if plan.coverage_task_facts != facts.to_dict() or plan.coverage_closed_demand != demand.to_dict() or review_model_maturation_loop(plan).to_dict() != report.to_dict():
        raise ValueError("task report differs from its actual facts/demand and replayed domain review")
    from .task_coverage_demand import compile_task_coverage_demand
    original = parse_task_coverage_demand(read_root_reference(root, freeze["artifact_refs"]["original_demand"], read_context))
    if compile_task_coverage_demand(facts).to_dict() != original.to_dict():
        raise ValueError("task original demand was not compiled from current facts")
    if report.path_quality_subjects != subjects or report.path_quality_results != results:
        raise ValueError("task accepted path-quality denominator differs from selected current material")
    if {ref.get("owner_id") for ref in doc["native_owner_receipt_refs"] if isinstance(ref,Mapping)} != {"model:" + model for model in selected.selected_model_ids}:
        raise ValueError("native receipt denominator differs from selected task closure")
    leaf_refs = _selected_native_leaf_refs(root, state, tuple(selected.selected_model_ids), read_context=read_context)
    if tuple(doc["native_owner_receipt_refs"]) != leaf_refs:
        raise ValueError("task original native leaf refs differ from selected current index")
    material = _finite_native_material(root, state, leaf_refs, read_context)
    expected_outcomes = _outcomes(facts, selected, state.accepted_revision.current_effective_intent_view, material)
    if doc["outcome_refs"] != expected_outcomes:
        raise ValueError("task outcome references differ from current target/binding/native material")
    freeze_path = (directory / "producer-freeze.json").relative_to(root).as_posix()
    refs = [*freeze["input_refs"], {"path":freeze_path, "sha256":hashlib.sha256(read_context.artifact_bytes(freeze_path)).hexdigest()}]
    context, _, _ = _verification_context(root, report, freeze, refs, request, read_context)
    reference = ModelMaturationReceiptRef(**exact_record(doc["maturation_receipt_ref"], ("receipt_id", "receipt_fingerprint"), "maturation receipt reference"))
    _read_material_json(root, receipt_path(reference.receipt_id, root, output_directory=root / MATURATION_ROOT), read_context)
    verification = verify_model_maturation_receipt(reference, context, root, output_directory=root / MATURATION_ROOT, read_context=read_context)
    if not verification.ok or verification.verified_maturation is None:
        raise ValueError("current canonical maturation receipt verification failed")
    result = derive_functional_understanding(task_facts=facts, coverage_demand=demand, maturation_report=report,
        verified_maturation=verification.verified_maturation, selected_read=selected,
        current_effective_intent_view=state.accepted_revision.current_effective_intent_view,
        binding_report=material["binding_report"], implementation_inventory=material["implementation_inventory"],
        outcome_refs=doc["outcome_refs"], native_materials=_native_subset(material), read_context=read_context)
    result.update(maturation_decision=report.decision, maturation_terminal_reason=report.terminal_reason,
        maturation_confidence=report.confidence, evidence_refs=[doc["maturation_receipt_ref"]], detail_refs=[doc["maturation_report_ref"]])
    if result["gap_ids"]:
        result["first_gap"] = {"gap_id": result["gap_ids"][0], "input_ref": doc["maturation_report_ref"]["path"], "next_owner_id": "task-model-maturation"}
    return result


def prepare_finite_functional_authority(*, repository_root, parent, current_design_contributions):
    """Explicit finite test-owner setup using executed leaves and official acceptance.

    It is separate from both normal task production and readonly consumption.
    It cannot run against this maintained source or a SkillGuard author root.
    Native execution must already have happened exactly once in the caller's
    temporary two-model root.  No receipt, path-quality pass, or Verified is made
    up by this helper.
    """
    import shutil
    from .model_regressions import ModelRegressionManifest, prepare_model_regression_plan
    from .model_authority_store import (prepare_initial_model_authority_staging,
        activate_model_revision_set, rebuild_model_authority, load_current_model_authority_state)
    from .model_revision_owner_evidence import produce_model_revision_owner_evidence
    from .model_intent_authority import build_current_intent_bootstrap_receipt, bootstrap_current_effective_intent_view, verify_model_intent_sources
    from .model_intent import derive_architecture_objective_projection
    from .model_revision_builder import build_current_model_revision
    from .model_revision_set import ModelRevisionSet
    from .model_authority import ModelSystemSnapshot, canonical_fingerprint
    from .model_regressions import resolve_current_full_model_regression_parent
    from .project_manifest import manifest_text_fingerprint
    from .__main__ import _native_path_quality_material
    root = Path(repository_root).resolve()
    if root == Path(__file__).resolve().parents[1] or (root / ".skillguard").exists():
        raise ValueError("finite setup cannot mutate the maintained author source")
    manifest = ModelRegressionManifest.load(root)
    if {row.model_id for row in manifest.entries} != {"alpha", "beta"} or parent.status != "pass":
        raise ValueError("finite setup requires the actually executed alpha/beta parent")
    staging = root / ".flowguard/work/bootstrap/functional-fixture"
    if staging.exists():
        raise ValueError("finite fixture authority setup is an initial single transaction")
    staging.mkdir(parents=True)
    # Only this explicitly controlled temporary fixture is copied.  The normal
    # producer never clones a software repository or changes its model head.
    for entry in root.iterdir():
        if entry.name in {"work", ".pytest_cache", "__pycache__"}:
            continue
        if entry.name == ".flowguard":
            for child in entry.iterdir():
                if child.name in {"work", "evidence"}:
                    continue
                destination = staging / ".flowguard" / child.name
                if child.is_dir():
                    shutil.copytree(child, destination)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(child, destination)
        elif entry.is_dir():
            shutil.copytree(entry, staging / entry.name)
        else:
            shutil.copy2(entry, staging / entry.name)
    snapshot_id = "finite-functional-current"
    seed = canonical_fingerprint({"original_parent": parent.parent_receipt_fingerprint, "fixture": "alpha-beta"})
    candidate, _, _ = prepare_initial_model_authority_staging(root, staging_root=staging,
        snapshot_id=snapshot_id, bootstrap_evidence_fingerprint=seed, system_id="flowguard")
    contributions = tuple(current_design_contributions)
    intent_receipt = build_current_intent_bootstrap_receipt(staging, receipt_id="intent:finite-functional",
        candidate_snapshot=candidate, current_design_contributions=contributions,
        rationale="Independent finite current design sources for functional consumer acceptance.")
    view = bootstrap_current_effective_intent_view(candidate, contributions,
        verify_model_intent_sources(staging, contributions), intent_receipt)
    source_bytes = {row.contribution_id:(root / row.source_ref).read_bytes() for row in contributions}
    objectives = derive_architecture_objective_projection(view, source_bytes_by_contribution_id=source_bytes)
    candidate_model_ids = {instance.logical_model_id for instance in candidate.model_instances}
    for bound in objectives:
        if not candidate_model_ids.intersection(bound.objective.model_ids):
            raise ValueError("architecture_objective_scope_unassigned:" + bound.objective.objective_id)
    receipt_root = root / MODEL_ROOT
    original_parent = resolve_current_full_model_regression_parent(root, receipt_dir=receipt_root)
    from types import SimpleNamespace
    from .model_authority_store import _SelectedReadContext
    subjects, results, details = [], [], []
    for instance in candidate.model_instances:
        model = instance.logical_model_id
        leaf = original_parent.child_evidence_by_model_id[model]
        evidence = _finite_native_material(root, SimpleNamespace(snapshot=candidate),
            [{"owner_id": "model:" + model, "receipt_id": leaf.receipt_id, "receipt_fingerprint": leaf.receipt_fingerprint}], _SelectedReadContext(root))
        local_objectives = tuple(bound for bound in objectives if model in bound.objective.model_ids)
        current_sources = dict(evidence["current_source_fingerprints"])
        identities = {row.contribution_id: row for row in view.verified_source_identities}
        for bound in local_objectives:
            from .source_identity import source_file_fingerprint
            identity = identities[bound.contribution_id]
            if (identity.fingerprint != bound.source_identity_fingerprint
                    or identity.source_ref != bound.source_ref
                    or source_file_fingerprint(root / bound.source_ref) != bound.source_fingerprint):
                raise ValueError("finite architecture objective Source identity is not current")
            if bound.source_ref in current_sources and current_sources[bound.source_ref] != bound.source_fingerprint:
                raise ValueError("finite objective/native Source identity conflict")
            current_sources[bound.source_ref] = bound.source_fingerprint
        evidence = {**evidence, "current_source_fingerprints": current_sources}
        # Each independent finite declaration retains its own actual scope.
        local = _native_path_quality_material(parent, candidate, required_model_ids=(model,),
            currentness_id=candidate.fingerprint, effective_intent_view=view,
            objective_projection=local_objectives, intent_source_bytes_by_contribution_id=source_bytes,
            semantic_evidence={"root": root, **{key:value for key,value in evidence.items() if key != "owner_materials"}})
        subjects.extend(local[0]); results.extend(local[1]); details.extend(local[2])
    owner_report = produce_model_revision_owner_evidence(staging, model_parent_receipt=parent.parent_receipt_path,
        snapshot_id=snapshot_id, receipt_root=receipt_root, output_path=staging / "work/native-owner-evidence.json")
    built = build_current_model_revision(staging, model_parent_receipt=parent.parent_receipt_path,
        revision_set_id="revision:finite-functional", task_id="task:finite-functional-bootstrap", snapshot_id=snapshot_id,
        receipt_root=receipt_root, current_design_intent_contributions=contributions,
        effective_intent_bootstrap_receipt=intent_receipt, native_owner_contracts=owner_report.bundle.contracts,
        native_owner_receipts=owner_report.bundle.receipts, native_owner_verification_results=owner_report.bundle.verification_results,
        path_quality_subjects=subjects, path_quality_results=results)
    if built.status != "pass":
        raise ValueError("finite fixture actual revision build did not pass")
    accepted = ModelSystemSnapshot.from_dict(strict_json_bytes(Path(built.candidate_snapshot_path).read_bytes()))
    revision = ModelRevisionSet.from_dict(strict_json_bytes(Path(built.revision_set_path).read_bytes()))
    activate_model_revision_set(staging, accepted, revision, path_quality_details=details)
    rebuild_model_authority(root, staging_root=staging,
        expected_absent_manifest_fingerprint=manifest_text_fingerprint((root / ".flowguard/project.toml").read_text("utf-8")),
        target_system_id="flowguard", target_generation=2)
    return load_current_model_authority_state(root)


def finite_current_design_contributions(repository_root):
    """Author independent desired behavior for the explicit two-function fixture."""
    from .model_intent import ModelIntentContribution
    from dataclasses import replace
    from .source_identity import source_file_fingerprint
    root = Path(repository_root).resolve()
    if root == Path(__file__).resolve().parents[1] or (root / ".skillguard").exists():
        raise ValueError("finite design authoring cannot target the maintained source")
    project = root / ".flowguard/project.toml"
    if not project.exists():
        project.write_text('[flowguard]\nrepository = "finite:alpha-beta"\nadopted_package_version = "' + _version() + '"\nschema_version = "1.0"\n', encoding="utf-8")
    declaration = root / ".flowguard/structure/owner-bindings.json"
    if not declaration.exists():
        from .model_system_inventory import build_manifest_model_system_snapshot
        from .model_revision_owner_evidence import _candidate_native_owner_route_universe, NATIVE_OWNER_BINDINGS_SCHEMA
        actual = build_manifest_model_system_snapshot(root, snapshot_id="finite-initial-owner-declaration", system_id="flowguard")
        models = sorted(row.logical_model_id for row in actual.model_instances)
        declaration.parent.mkdir(parents=True, exist_ok=True)
        declaration.write_text(json.dumps({"schema":NATIVE_OWNER_BINDINGS_SCHEMA, "system_id":actual.system_id,
            "candidate_model_ids":models, "bindings":[{"owner_route":route, "model_ids":models,
                "protected_failure_ids":["r8-finite:invalid"]} for route in _candidate_native_owner_route_universe(actual)],
            "claim_boundary":"Only the independent finite alpha/beta current model system and its actual classification failure."}, sort_keys=True), encoding="utf-8")
    result = []
    for model in ("alpha", "beta"):
        path = root / "docs" / ("current-design-" + model + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("The independent src/" + model + ".py classify function must map strictly typed integers to positive or nonpositive, reject every other type with TypeError, and preserve current independent input/native evidence. Its classification obligation is obligation:r8-finite:classification:" + model + "; its required external functional outcome is outcome:r8:finite_classification:" + model + ".\n", encoding="utf-8")
        result.append(ModelIntentContribution("intent:current-design:" + model, "design", path.relative_to(root).as_posix(), source_file_fingerprint(path),
            "normative_target", "design", "candidate", "accepted", "model:" + model, "", (), (),
            ("obligation:r8-finite:classification:" + model,), (), (), (),
            ("relation:model-realizes-purpose:" + model,), (), (), (), "finite-current-design",
            "Independent desired function behavior; executed samples are separate conformance evidence."))
        result[-1] = replace(result[-1], target_output_ids=("outcome:r8:finite_classification:" + model,))
    return tuple(result)


def prepare_functional_task_request(*, repository_root, task_id, primary_model_id,
                                  task_purpose, requested_outcome_ids, affected_surface_ids,
                                  related_model_ids=(), caller_requested_owner_ids=(), observed_path_changes=()):
    """Freeze an honest postaccept readonly task and six finite check declarations.

    This explicit preparation is separate from public read.  It observes the
    four source planes independently and never runs a native owner or accepts
    a model.  Caller-supplied surface IDs remain demands; production checks
    must subsequently resolve every one against the independent inventory.
    """
    from .model_authority_store import load_current_model_authority_state
    from .task_coverage_demand import TaskFacts, TaskFactSourceSnapshot
    from .evidence_receipts import capture_environment_fingerprint
    root = Path(repository_root).resolve()
    state = load_current_model_authority_state(root)
    changes = normalize_observed_path_changes(observed_path_changes)
    output = root / ".flowguard/evidence/task-contexts" / task_id
    from .functional_read import normalize_functional_artifact_path
    normalize_functional_artifact_path(output.relative_to(root).as_posix())
    planes = {
        "request": {"task_id": task_id, "purpose": task_purpose, "requested_outcome_ids": list(requested_outcome_ids), "read_only": True, "implementation_requested": False, "release_requested": False, "declared_path_changes": changes},
        "current_model": {"accepted_head": state.head.to_dict(), "accepted_revision_fingerprint": state.accepted_revision.fingerprint},
        "public_surface": {"affected_surface_ids": list(affected_surface_ids), "source": "caller demand, independently checked against accepted original native inventory", "growth_observation_ref": None},
        "lifecycle": {"snapshot_fingerprint": state.snapshot.fingerprint, "lifecycle": state.snapshot.lifecycle, "subject_lane": state.snapshot.subject_lane},
    }
    snapshots = []
    plane_refs = []
    for plane, value in planes.items():
        ref = _write_json(root, output, "inputs/" + plane + ".json", value)
        plane_refs.append(ref)
        snapshots.append(TaskFactSourceSnapshot(plane, ref["path"], "sha256:" + ref["sha256"], reason="Actual independent readonly task source observation"))
    facts = TaskFacts(task_id, task_purpose, requested_outcome_ids=tuple(requested_outcome_ids),
        affected_surface_ids=tuple(affected_surface_ids), related_model_ids=tuple(related_model_ids),
        caller_requested_owner_ids=tuple(caller_requested_owner_ids), change_kinds=(), source_snapshots=tuple(snapshots),
        implementation_requested=False, release_requested=False, read_only=True, non_trivial=True)
    facts_ref = _write_json(root, output, "initial-task-facts.json", facts.to_dict())
    contract = root / "openspec/specs/model-maturation-receipt/spec.md"
    if not contract.exists():
        raise ValueError("normal target lacks its canonical maturation contract")
    contract_ref = _raw_reference(root, contract)
    environment = capture_environment_fingerprint(flowguard_version=_version()).to_dict()
    check_ref = _write_json(root, output, "check-manifest.json", {"schema": "flowguard.functional_task_checks.v1", "check_ids": list(CHECK_IDS),
        "input_refs": [facts_ref, *plane_refs], "accepted_head_fingerprint": state.head.fingerprint,
        "producer_contract_ref": contract_ref, "environment": environment})
    suite_ref = _write_json(root, output, "suite-map.json", {"schema": "flowguard.functional_task_suite.v1",
        "owners": {"existing-model-owner": [CHECK_IDS[0]], "task-model-maturation": list(CHECK_IDS[1:])}})
    request = {"schema": "flowguard.functional_task_context_request.v1", "task_facts_ref": facts_ref,
        "primary_model_id": primary_model_id, "accepted_head_fingerprint": state.head.fingerprint,
        "producer_contract_ref": contract_ref, "check_manifest_ref": check_ref, "suite_map_ref": suite_ref}
    _write_json(root, output, "producer-request.json", request)
    return request, output
