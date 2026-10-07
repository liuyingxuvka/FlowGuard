"""Authenticate original native architecture inputs without executing owners."""
from dataclasses import replace
from pathlib import Path
import json


def collect_architecture_native_evidence(*, root, candidate, parent,
                                        planning_observation, receipt_root,
                                        read_context=None):
    from .native_case_protocol import parse_native_architecture_material, _reject_duplicate_json_keys
    from .model_path_quality import (
        parse_architecture_binding_report, ResponsibilitySemanticEvidenceBinding,
    )
    from .implementation_inventory import ImplementationSurfaceInventory
    from .model_test_alignment import CodeContract
    from .model_regressions import resolve_current_full_model_regression_parent
    from .native_case_mapping import load_native_case_mapping
    from .validation_ownership import build_owner_receipt_context
    from .model_authority import functional_source_fingerprint
    root, receipt_root = Path(root).resolve(), Path(receipt_root).resolve()
    materials = []
    for run in parent.results:
        path = Path(run.native_case_result_artifact_path).with_name('native-source.json')
        source_bytes = (read_context.artifact_bytes(path.resolve().relative_to(root).as_posix())
                        if read_context is not None else path.read_bytes())
        raw = json.loads(source_bytes.decode('utf-8'), object_pairs_hook=_reject_duplicate_json_keys,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if 'architecture_material' in raw:
            material = parse_native_architecture_material(raw['architecture_material'])
            if material['model_id'] != run.model_id:
                raise ValueError('native architecture material owner mismatch')
            for row in (*material['source_refs'], *material['observed_source_inputs']):
                expected = row.get('sha256', row.get('source_fingerprint'))
                if functional_source_fingerprint(root, row['path']) != expected:
                    raise ValueError('native architecture source observation is stale: '+row['path'])
            materials.append(material)
    if not materials:
        return {}
    first = materials[0]
    for material in materials[1:]:
        for name in ('implementation_inventory', 'binding_report', 'code_contracts',
                     'resolved_manifest_rows', 'observed_source_inputs'):
            if material[name] != first[name]:
                raise ValueError('native architecture shared denominator differs: '+name)
    resolved = resolve_current_full_model_regression_parent(root, receipt_dir=receipt_root)
    if Path(resolved.parent_artifact_path).resolve() != Path(parent.parent_receipt_path).resolve():
        raise ValueError('native architecture parent is not the original current composition')
    leaves = resolved.child_evidence_by_model_id
    mapping = load_native_case_mapping(root / '.flowguard/models/native-case-mapping.json')
    contracts = []
    receipts, contexts, bindings, results = [], {}, [], []
    proofs, input_classes, identities = {}, {}, {}
    from .native_case_protocol import NativeModelCaseContract
    for material in materials:
        model = material['model_id']
        leaf = leaves[model]
        receipt = leaf.receipt
        if receipt is None or leaf.verification is None or not leaf.verification.ok:
            raise ValueError('architecture native leaf is not independently current')
        receipts.append(receipt)
        context = build_owner_receipt_context(
            planning_observation.current_by_owner['model:'+model], receipt, receipt_root)
        if context is None:
            raise ValueError('architecture native leaf has no original proof context')
        contexts[receipt.receipt_id] = replace(context,
            receipt_store_repository_root=str(root),
            receipt_store_output_directory=str(receipt_root))
        contracts.extend(NativeModelCaseContract.from_dict(row) for row in material['native_case_contracts'])
        original_bindings = tuple(row for row in mapping.bindings
                                  if row.owner_id == 'model:'+model)
        bindings.extend(original_bindings)
        results.extend(leaf.native_case_results)
        for row in leaf.native_case_results:
            identities[(row.owner_id, row.source_case_id)] = {
                name: getattr(row, name) for name in (
                    'input_fingerprint', 'model_fingerprint', 'code_fingerprint',
                    'test_fingerprint', 'oracle_fingerprint', 'toolchain_fingerprint',
                    'environment_fingerprint')}
        for row in material['responsibility_context_rows']:
            matches = [b for b in original_bindings
                       if b.owner_id == 'model:'+model
                       and tuple(b.native_case_ids) == tuple(row['source_case_ids'])
                       and b.evidence_scope == 'implementation_boundary']
            if len(matches) != 1:
                raise ValueError('architecture responsibility has no exact original native binding')
            proof = ResponsibilitySemanticEvidenceBinding(
                row['hard_dimension_id'], row['input_class_id'], row['semantic_spec_id'],
                row['oracle_id'], matches[0].fingerprint, receipt.receipt_id,
                receipt.fingerprint, 'model:'+model, tuple(row['source_case_ids']),
                'implementation_boundary')
            proofs.setdefault(row['responsibility_id'], []).append(proof)
            for case in row['source_case_ids']:
                input_classes.setdefault(('model:'+model, case), set()).add(row['input_class_id'])
    return {
        'implementation_inventory': ImplementationSurfaceInventory.from_dict(first['implementation_inventory']),
        'binding_report': parse_architecture_binding_report(first['binding_report']),
        'code_contracts': tuple(CodeContract(**row) for row in first['code_contracts']),
        'native_contracts': tuple(contracts), 'native_bindings': tuple(bindings),
        'native_results': tuple(results), 'receipts': tuple(receipts),
        'receipt_contexts': contexts, 'raw_artifact_root': root,
        'current_native_identities': identities,
        'native_input_class_ids': {key: tuple(sorted(value)) for key,value in input_classes.items()},
        'observed_source_inputs': tuple(first['observed_source_inputs']),
        'current_source_fingerprints': {row['path']: row['sha256'] for row in first['observed_source_inputs']},
        'responsibility_evidence_bindings': {key: tuple(value) for key,value in proofs.items()},
        'root': root,
    }
