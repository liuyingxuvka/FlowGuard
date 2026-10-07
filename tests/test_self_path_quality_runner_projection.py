from __future__ import annotations

from pathlib import Path

import ast
import importlib.util
import json
import sys
from contextlib import ExitStack
from unittest.mock import patch

from flowguard.model_path_quality import PathQualityResult
from flowguard.model_path_quality import DeclaredPathQualitySource, derive_retained_elements
from flowguard.self_path_quality import (
    _augment_provider_gaps,
    _runner_called_owner_symbols,
)


def test_module_level_main_guard_is_projected_as_native_entrypoint(tmp_path: Path) -> None:
    runner = tmp_path / "run_checks.py"
    runner.write_text(
        "\n".join(
            (
                "from package import emit_runner",
                "import package.runtime as runtime",
                "",
                "def run_owner():",
                "    return runtime.execute()",
                "",
                "if __name__ == \"__main__\":",
                "    raise SystemExit(emit_runner(\"owner\", run_owner()))",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert _runner_called_owner_symbols(runner) == (
        "package.runtime:execute",
        "package:emit_runner",
    )


def test_provider_gap_promotes_triggered_result_to_deep_required() -> None:
    fingerprint = "sha256:" + ("a" * 64)
    result = PathQualityResult(
        result_id="path-quality:fixture",
        subject_fingerprint=fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=fingerprint,
        detail_evidence_fingerprint=fingerprint,
        producer_id="fixture",
        currentness_id="fixture-current",
    )

    augmented = _augment_provider_gaps(result, ("provider_gap",))

    assert augmented.conclusion == "unresolved"
    assert augmented.trigger_ids == ("missing_necessity_witness",)
    assert augmented.optimization_depth == "deep_required"
    assert augmented.unresolved_ids == ("provider_gap:provider_gap",)


ROOT = Path(__file__).resolve().parents[1]
INSTANCE_FINGERPRINT = "sha256:" + "a" * 64
CURRENT_ADDED_OWNER_IDS = frozenset({
    "python_function_state_verification", "problem_corpus_coverage", "evidence_storage_lifecycle",
})


def _current_declared_owners():
    return json.loads((ROOT / ".flowguard/models/regression-manifest.json").read_text(encoding="utf-8"))["models"]


def _load_declared_owner(owner):
    name = "r6_declared_provider_" + owner["model_id"]
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / owner["model_path"])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def _export_without_checks(module, model_instance_fingerprint=INSTANCE_FINGERPRINT):
    with ExitStack() as stack:
        for name in ("run_model_checks", "run_checks", "validate_benchmark", "validate_kernel", "validate_contract", "apply_event", "_run"):
            if callable(getattr(module, name, None)):
                stack.enter_context(patch.object(module, name, side_effect=AssertionError("export attempted native check: " + name)))
        for block in getattr(module, "BLOCKS", ()):
            # Source introspection reads the original apply definition. Replacing
            # the method would remove its real anchor, so guard checker entrypoints.
            assert callable(getattr(block, "apply", None))
        stack.enter_context(patch("flowguard.system_composition.check_system_composition", side_effect=AssertionError("export executed system checker")))
        stack.enter_context(patch("examples.bounded_system_composition.benchmark.check_system_composition", side_effect=AssertionError("export executed benchmark checker")))
        stack.enter_context(patch("examples.bounded_system_composition.benchmark.run_bounded_system_benchmark", side_effect=AssertionError("export executed benchmark owner")))
        declaration = module.export_path_quality_source(model_instance_fingerprint)
        # Consume the current native exporter contract exactly as native_main
        # does: two architecture owners carry their declared graph and their
        # independent receipt-free material together. Other current ports
        # remain genuine DeclaredPathQualitySource values.
        from flowguard.native_case_runner import (
            NativeArchitectureDeclaration, _verify_architecture_declaration,
        )
        from flowguard.native_case_protocol import parse_native_architecture_material
        if isinstance(declaration, NativeArchitectureDeclaration):
            material = parse_native_architecture_material(declaration.architecture_material)
            source = declaration.source
            assert isinstance(source, DeclaredPathQualitySource)
            assert source.model_id in {"authoritative_model_system", "model_maturation_loop"}
            _verify_architecture_declaration(source, material)
            assert material["model_id"] == source.model_id
        else:
            assert isinstance(declaration, DeclaredPathQualitySource)
            source = declaration
            assert source.model_id not in {"authoritative_model_system", "model_maturation_loop"}
        return source


def test_all_51_owners_have_exact_declared_source_port():
    # The selector preserves historical evidence identity; its current scope is
    # the frozen 54-owner manifest, including these three independent domains.
    owners = _current_declared_owners()
    assert len(owners) == 54
    owner_ids = {owner["model_id"] for owner in owners}
    assert len(owner_ids) == 54
    assert CURRENT_ADDED_OWNER_IDS <= owner_ids
    for owner in owners:
        module = _load_declared_owner(owner)
        source = _export_without_checks(module)
        assert isinstance(source, DeclaredPathQualitySource), owner["model_id"]
        assert source.model_id == owner["model_id"]
        assert source.model_instance_fingerprint == INSTANCE_FINGERPRINT
        assert source.declared_element_ids == tuple(row[0] for row in derive_retained_elements(source.model_facts))
        assert source.declared_element_ids
        assert set(source.element_groundings) == set(source.declared_element_ids)
        assert owner["model_path"] in {row["path"] for row in source.source_refs}
        assert DeclaredPathQualitySource.from_dict(source.to_dict()).fingerprint == source.fingerprint
        runner = ast.parse((ROOT / owner["runner"][1]).read_text(encoding="utf-8"))
        native_calls = [node for node in ast.walk(runner) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "native_main"]
        assert len(native_calls) == 1, owner["model_id"]
        exporters = [keyword.value for keyword in native_calls[0].keywords if keyword.arg == "declared_source_exporter"]
        assert len(exporters) == 1
        exporter = exporters[0]
        direct_exporter = isinstance(exporter, ast.Name) and exporter.id == "export_path_quality_source"
        imported_model_exporter = (
            isinstance(exporter, ast.Attribute) and exporter.attr == "export_path_quality_source"
            and isinstance(exporter.value, ast.Call) and isinstance(exporter.value.func, ast.Name)
            and exporter.value.func.id == "__import__" and len(exporter.value.args) == 1
            and isinstance(exporter.value.args[0], ast.Constant) and exporter.value.args[0].value == "model"
            and not exporter.value.keywords
        )
        model_attribute_exporter = (
            isinstance(exporter, ast.Attribute) and exporter.attr == "export_path_quality_source"
            and isinstance(exporter.value, ast.Name) and exporter.value.id == "model"
            and any(isinstance(node, ast.Import) and any(alias.name == "model" and alias.asname is None for alias in node.names) for node in runner.body)
        )
        assert direct_exporter or imported_model_exporter or model_attribute_exporter, owner["model_id"]


def test_provider_scope_remains_honest_for_native_contract_models():
    owners = {owner["model_id"]: owner for owner in _current_declared_owners()}
    for owner_id in ("code_boundary_conformance", "contract_source_audit", "harden_ui_content_visibility_validation", "primary_path_authority", "runtime_gateway_adoption"):
        source = _export_without_checks(_load_declared_owner(owners[owner_id]))
        assert source.graph_scope == "native_check_contract", owner_id
        assert source.scope_coverage["claim_scope"] == "declared_model"
        assert source.scope_coverage["implementation_inventory_fingerprint"] == ""
        assert source.scope_coverage["binding_report_fingerprint"] == ""


def test_all_51_declared_ports_pass_actual_path_quality_consumer():
    # Historical selector name; this consumer reads all current 54 owners.
    from flowguard.model_regressions import (
        ModelRegressionManifest, resolve_entry_input_inventory, build_regression_model_instance,
    )
    from flowguard.model_path_quality import (
        PathQualitySubject, PathQualityArchitectureDetail, canonical_fingerprint,
        normalized_model_facts_fingerprint, verify_declared_path_quality_source,
        find_lightweight_findings, collect_deep_review_triggers, lightweight_path_review,
    )
    owners = {row["model_id"]: row for row in _current_declared_owners()}
    manifest = ModelRegressionManifest.load(ROOT)
    failures = []
    # These identities label a finite consumer test episode, not accepted intent
    # or terminal native evidence. Actual model/input identities come from ROOT.
    intent = canonical_fingerprint({"fixture": "all-declared-port-consumers"})
    for entry in manifest.entries:
        try:
            inventory = resolve_entry_input_inventory(ROOT, entry,
                additional_patterns=manifest.owner_patterns_for(entry.model_id))
            instance = build_regression_model_instance(ROOT, entry, inventory)
            source = _export_without_checks(_load_declared_owner(owners[entry.model_id]), instance.fingerprint)
            source = DeclaredPathQualitySource.from_dict(source.to_dict())
            assert not verify_declared_path_quality_source(source, instance)
            facts = source.model_facts
            subject = PathQualitySubject(
                model_id=entry.model_id, boundary_id="fixture:declared-port-consumer",
                model_fingerprint=instance.fingerprint,
                normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts),
                retained_element_inventory_fingerprint=canonical_fingerprint(dict(derive_retained_elements(facts))),
                purpose_fingerprint=instance.purpose_closure_fingerprint, intent_fingerprint=intent,
                obligation_fingerprint=canonical_fingerprint([row.get("obligation_id") for row in facts.get("validations", ())]),
                provider_fingerprint=source.fingerprint, dependency_fingerprint=instance.input_inventory_fingerprint,
                code_fingerprint=canonical_fingerprint({row.path: row.sha256 for row in instance.inputs}),
                test_fingerprint=instance.runner_sha256, oracle_fingerprint=canonical_fingerprint([row.get("oracle_id") for row in facts.get("validations", ())]),
                evidence_fingerprint=canonical_fingerprint({"fixture_declaration": source.fingerprint}),
                currentness_id="fixture:declared-port-consumer")
            subject = PathQualitySubject.from_dict(subject.to_dict())
            triggers = collect_deep_review_triggers(find_lightweight_findings(facts))
            details = []
            result = lightweight_path_review(subject, facts,
                trigger_evidence={trigger: source.fingerprint for trigger in triggers},
                trigger_currentness_id=subject.currentness_id, detail_collector=details)
            assert not result.observation_gap_ids, result.observation_gap_ids
            assert result.current
            assert len(details) == 1 and details[0].fingerprint == result.detail_evidence_fingerprint
            assert not details[0].binding_errors(subject, result)
            assert PathQualityResult.from_dict(result.to_dict()) == result
            assert PathQualityArchitectureDetail.from_dict(details[0].to_dict()) == details[0]
        except (AssertionError, TypeError, ValueError) as exc:
            failures.append(f"{entry.model_id}: {type(exc).__name__}: {exc}")
    assert len(manifest.entries) == 54
    assert CURRENT_ADDED_OWNER_IDS <= {entry.model_id for entry in manifest.entries}
    assert not failures, "\n".join(failures)


def test_exporter_does_not_execute_native_checks():
    owners = {owner["model_id"]: owner for owner in _current_declared_owners()}
    sources = {}
    for owner_id in ("development_process_strategy", "work_context", "bounded_system_composition_benchmark"):
        module = _load_declared_owner(owners[owner_id])
        source = _export_without_checks(module)
        assert source.fingerprint == _export_without_checks(module).fingerprint
        assert source.graph_scope == "model_behavior"
        sources[owner_id] = source
    strategy = sources["development_process_strategy"].model_facts
    assert {row["component_id"] for row in strategy["function_blocks"]} == {"route", "equivalence", "diagnostic", "repair", "select", "material_change"}
    assert len(strategy["transitions"]) == 13
    assert strategy["dispatcher_rejection"]["outcome"].startswith("AssertionError")
    assert any(row["field_updates"].get("selected") == "False" and row["field_updates"].get("material_revision") == "revision" for row in strategy["transitions"])
    for row in strategy["transitions"]:
        assert row["guard"] and row["function_block_ids"]
        assert row["guard_bindings"] is not None
    context = sources["work_context"].model_facts
    assert len(context["transitions"]) == 6
    assert context["dispatcher_rejection"]["outcome"] == "no_result"
    assert context["dispatcher_rejection"]["terminal"] is False
    assert any(row["field_updates"].get("behavior_admitted") == "bool(input_obj.behavior_source_surface_ids)" for row in context["transitions"])
    benchmark = sources["bounded_system_composition_benchmark"].model_facts
    assert len(benchmark["components"]) == 7
    assert len(benchmark["system_definitions"]) == 3
    assert len(benchmark["variant_declarations"]) == 9
    assert len({row["id"] for row in benchmark["states"]}) == 14
    assert all(row["definition"]["dependencies"] and row["definition"]["steps"] and row["definition"]["properties"] for row in benchmark["system_definitions"])
    from examples.bounded_system_composition import benchmark as benchmark_module
    family_id, component_ids = next(iter(benchmark_module.FAMILIES.items()))
    with patch.object(benchmark_module, "check_system_composition") as checker:
        inputs = benchmark_module.build_case_inputs(family_id, component_ids, "repaired")
        checker.assert_not_called()
        assert len(inputs) == 4
        benchmark_module._case(family_id, component_ids, "repaired")
        checker.assert_called_once_with(inputs[1], inputs[2], inputs[0])
