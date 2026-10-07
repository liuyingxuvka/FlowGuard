"""Executable evidence owner for the Emergent Integration Benchmark."""

from examples.bounded_system_composition.benchmark import run_bounded_system_benchmark


def validate_benchmark() -> bool:
    return run_bounded_system_benchmark().ok


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_path_quality_source(model_instance_fingerprint: str):
    """Declare repaired component graphs and exact protected system variants."""
    from pathlib import Path
    from examples.bounded_system_composition.benchmark import FAMILIES, build_case_inputs
    from flowguard.model_path_quality import compile_declared_path_quality_source, derive_retained_elements
    from flowguard.portable_path_quality import compile_portable_path_quality_facts
    from flowguard.source_identity import functional_source_fingerprint

    model_id = "bounded_system_composition_benchmark"
    root = Path(__file__).resolve().parents[4]
    source_path = "examples/bounded_system_composition/benchmark.py"
    refs = (
        {"path": f".flowguard/models/owners/{model_id}/model.py", "source_fingerprint": functional_source_fingerprint(root, f".flowguard/models/owners/{model_id}/model.py")},
        {"path": source_path, "source_fingerprint": functional_source_fingerprint(root, source_path)},
    )
    facts = {name: [] for name in ("states", "transitions", "branches", "function_blocks", "fields", "effects", "outputs", "validations", "owners", "initial_state_ids", "terminal_state_ids", "components", "system_definitions", "variant_declarations")}
    groundings = {}
    for family_id, component_ids in FAMILIES.items():
        models, definition, request, expected = build_case_inputs(family_id, component_ids, "repaired")
        facts["system_definitions"].append({"family_id": family_id, "definition": definition.to_dict(), "request": request.to_dict(), "expected_status": expected})
        for component_id, model in zip(component_ids, models):
            projected = compile_portable_path_quality_facts(model)
            namespace = f"{family_id}/{component_id}"
            id_map = {row["id"]: f"{namespace}/{row['id']}" for name in ("states", "transitions", "branches", "outputs", "validations") for row in projected[name]}
            def namespaced(value):
                if isinstance(value, str):
                    return id_map.get(value, value)
                if isinstance(value, list):
                    return [namespaced(item) for item in value]
                if isinstance(value, dict):
                    return {key: namespaced(item) for key, item in value.items()}
                return value
            for name in ("states", "transitions", "branches", "function_blocks", "fields", "effects", "outputs", "validations", "owners", "initial_state_ids", "terminal_state_ids"):
                facts[name].extend(namespaced(projected[name]))
            facts["components"].append({"id": namespace, "family_id": family_id, "component_id": component_id, "model_fingerprint": model.fingerprint, "model": model.to_dict()})
            for element_id, _ in derive_retained_elements(projected):
                groundings[id_map.get(element_id, element_id)] = {"source_ref": source_path, "source_fingerprint": refs[1]["source_fingerprint"], "source_symbol": "_component", "component_id": component_id, "family_id": family_id, "portable_element_id": element_id, "portable_model_fingerprint": model.fingerprint}
        for variant in ("bad", "missing-semantics", "truncated"):
            _, variant_definition, variant_request, variant_expected = build_case_inputs(family_id, component_ids, variant)
            facts["variant_declarations"].append({"family_id": family_id, "variant": variant, "definition": variant_definition.to_dict(), "request": variant_request.to_dict(), "expected_status": variant_expected, "source_symbol": "build_case_inputs", "coverage": "not_run"})
    return compile_declared_path_quality_source(
        model_id=model_id, model_instance_fingerprint=model_instance_fingerprint,
        source_refs=refs, graph_scope="model_behavior",
        provider_kind="flowguard.portable-system-benchmark-declaration.v1",
        model_facts=facts, element_groundings=groundings,
    )
