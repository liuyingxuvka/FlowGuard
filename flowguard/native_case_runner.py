"""Small producer-side bridge for native model case evidence.

The verification owner scripts predate the strict native-case envelope and
therefore expose their results in a few different, already-existing report
shapes.  This module does not run another check and does not invent a verdict:
it captures the result returned by the owner, preserves its machine-readable
artifacts or terminal transcript as raw evidence, and projects each observed
case into the common envelope consumed by the model-regression verifier.

It is intentionally a producer helper.  Readers still verify the envelope,
raw bytes, owner identity, marker, and (when supplied) the exact frozen case
contracts.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from contextvars import ContextVar
from dataclasses import dataclass, replace
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any, Callable, Mapping, Sequence


_DECLARED_SOURCE: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "flowguard_native_declared_source", default=None
)
_ARCHITECTURE_MATERIAL: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "flowguard_native_architecture_material", default=None
)


@dataclass(frozen=True)
class NativeArchitectureDeclaration:
    """One exporter result; the material precedes any episode receipt."""
    source: Any
    architecture_material: Mapping[str, Any]



_R8_CASES = (
    ("public-functional-read", "authoritative_model_system", "r8_public_task_context_read", "flowguard/__main__.py", "_read_operation", "openspec/specs/task-aware-functional-map/spec.md", "public_read_consumes_verified_task_context", ("task:selected_current",)),
    ("contextual-architecture-comparison", "model_maturation_loop", "r8_context_indexed_comparison", "flowguard/model_path_quality.py", "derive_architecture_relation_candidates", "openspec/specs/context-indexed-architecture-direction/spec.md", "compare_only_context_related_responsibilities", ("comparison:related_overlap", "comparison:distinct_context")),
    ("affected-native-selection", "authoritative_model_system", "r8_affected_owner_selection", "flowguard/model_regressions.py", "prepare_model_regression_plan", "openspec/specs/task-aware-functional-map/spec.md", "preserve_unaffected_owner_reuse", ("planner:one_changed_owner",)),
)




_R9_CASES = (
    ("normal-task-context", "model_maturation_loop", "r9_normal_task_context", "flowguard/functional_task_context.py", "produce_functional_task_context", "openspec/specs/context-indexed-architecture-direction/spec.md", "publish_current_task_or_original_gap", ("normal:current_verified", "normal:original_diagnostic")),
    ("finite-growth-observation", "authoritative_model_system", "r9_finite_growth_observation", "flowguard/model_authority_store.py", "_observe_growth_paths", "openspec/specs/task-aware-functional-map/spec.md", "preserve_finite_growth_and_unknowns", ("growth:finite_present_and_missing", "growth:unknown_admission")),
    ("pointer-detail-navigation", "authoritative_model_system", "r9_pointer_detail_navigation", "flowguard/model_authority_store.py", "resolve_architecture_improvement_pointer", "openspec/specs/task-aware-functional-map/spec.md", "resolve_current_action_location", ("pointer:accepted_current", "pointer:wrong_hash_or_head")),
)


def r9_functional_code_contracts():
    """The sole typed definitions consumed by the normal-use native exporter."""
    from .model_test_alignment import CodeContract
    outcomes = {
        "normal-task-context": "outcome:r9:normal_task_current_or_gap_visible",
        "finite-growth-observation": "outcome:r9:finite_growth_gap_visible",
        "pointer-detail-navigation": "outcome:r9:current_pointer_resolution_state_visible",
    }
    return tuple(CodeContract(code_contract_id="code-contract:r9:" + name, path=path, symbol=symbol,
        implements_obligations=("obligation:r9:" + obligation,),
        relation_code_obligation_ids=("obligation:r9:" + obligation,),
        external_inputs=("current independently bound " + name + " inputs",),
        external_outputs=(outcomes[name],),
        state_reads=("selected current task and exact independent finite evidence",),
        state_writes=("owned immutable task and maturation evidence",) if name == "normal-task-context" else (),
        side_effects=("publish owned current-or-original-gap task evidence",) if name == "normal-task-context" else (),
        error_paths=("malformed, foreign, stale and missing evidence remain rejected or original needs_evidence",),
        required=True) for name, _, _, path, symbol, _, obligation, _ in _R9_CASES)


def _r9_functional_inventory(root):
    """Observe exactly six named real Source surfaces; retain every AST neighbor."""
    import ast
    from .implementation_inventory import SoftwareBoundary, ImplementationFileDisposition, build_implementation_surface_inventory, implementation_surface_key
    from .implementation_inventory_python import discover_python_implementation_surfaces, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID, _collect_node_specs
    from .source_identity import functional_source_fingerprint
    root = Path(root).resolve()
    cases = _R8_CASES + _R9_CASES
    paths = sorted({row[3] for row in cases})
    manifest = [{"path": path, "sha256": functional_source_fingerprint(root, path)} for path in paths]
    files = tuple(ImplementationFileDisposition(row["path"], "production", row["sha256"], "model_implementation", "Finite real Source AST denominator for six explicitly required production functions", True, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID) for row in manifest)
    targets = {implementation_surface_key(row[3], row[4]) for row in cases}
    discoveries = {}
    for file in files:
        dispositions = {implementation_surface_key(file.path, row.symbol): "model_implementation" if implementation_surface_key(file.path, row.symbol) in targets else "scoped_out" for row in _collect_node_specs(ast.parse((root / file.path).read_text(encoding="utf-8")))}
        discoveries[file.path] = discover_python_implementation_surfaces(root=root, file_disposition=file, surface_dispositions=dispositions)
    inventory = build_implementation_surface_inventory(root, SoftwareBoundary("boundary:r9:six-production-functions", "source:r9:current-functional", production_patterns=tuple(paths)), inventory_id="inventory:r9:six-production-functions", file_dispositions=files, discovery_results=discoveries, resolved_manifest=manifest, claim_boundary="Complete observed AST denominator of five frozen modules; only six named functions are required; other members and unresolved dynamic diagnostics remain explicitly outside the finite functional claim")
    actual = {(row.path, row.symbol) for row in inventory.surfaces if row.disposition == "model_implementation"}
    if actual != {(row[3], row[4]) for row in cases}:
        raise NativeCaseProtocolError("six actual production functions missing from the finite Source boundary")
    return inventory, manifest


def observe_r9_unmodeled_normal_surfaces(root, *, original_source, original_architecture_material):
    """Consume prior original declarations and current AST into diagnostic gaps.

    Original leaf material remains unchanged. Its old source identities may be
    stale after Source edits; that is an explicit diagnostic, never acceptance.
    The caller retains the original raw/native/receipt references independently.
    """
    from .native_case_protocol import parse_native_architecture_material
    from .model_path_quality import parse_architecture_binding_report, derive_architecture_model_gaps, derive_architecture_improvement_pointers
    from .implementation_blueprint import review_model_implementation_bindings
    material = parse_native_architecture_material(original_architecture_material)
    original = parse_architecture_binding_report(material["binding_report"])
    old_ids = {"binding:r8:" + row[0] for row in _R8_CASES}
    if not old_ids <= {row.binding_id for row in original.bindings} or any(row.binding_id.startswith("binding:r9:") for row in original.bindings):
        raise NativeCaseProtocolError("diagnostic requires the preserved original three-function binding material")
    inventory, manifest = _r9_functional_inventory(root)
    report = review_model_implementation_bindings(inventory,
        required_model_element_ids=original.required_model_element_ids,
        bindings=original.bindings, semantic_specs=original.semantic_specs, oracles=original.oracles)
    gaps = derive_architecture_model_gaps(original_source, implementation_inventory=inventory, binding_report=report, root=root)
    required = {(row[3], row[4]) for row in _R9_CASES}
    new_surfaces = {row.surface_id for row in inventory.surfaces if (row.path, row.symbol) in required}
    actual = {row["surface_id"] for row in gaps if row["gap_id"].startswith("model_surface_unbound:")}
    if not new_surfaces <= actual:
        raise NativeCaseProtocolError("original model did not expose every actual normal-use model coverage gap")
    pointers = derive_architecture_improvement_pointers(model_gaps=gaps,
        implementation_inventory=inventory,
        current_source_fingerprints={row["path"]: row["sha256"] for row in manifest})
    return {"schema": "flowguard.r9.source_model_gap_observation.v1",
        "claim_boundary": "source_only_finite_model_coverage_diagnostic_not_accepted_pointer",
        "source_defect_claim": False,
        "original_source_fingerprint": original_source.fingerprint,
        "original_architecture_material_fingerprint": fingerprint_payload(material),
        "implementation_inventory": inventory.to_dict(), "binding_report": report.to_dict(),
        "resolved_manifest_rows": manifest, "model_gaps": list(gaps),
        "action_targets": [target.to_dict() for pointer in pointers for target in pointer.action_targets],
        "original_binding_ids": sorted(row.binding_id for row in original.bindings),
        "required_normal_surface_ids": sorted(new_surfaces)}


def build_r8_finite_architecture_declaration(root, source):
    """Actual finite alpha/beta evidence for exercising production consumers."""
    from .implementation_inventory import SoftwareBoundary, ImplementationFileDisposition, build_implementation_surface_inventory
    from .implementation_inventory_python import discover_python_implementation_surfaces, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID, _collect_node_specs
    from .implementation_blueprint import ModelImplementationBinding, SemanticSpecReference, OracleReference, review_model_implementation_bindings
    from .model_test_alignment import CodeContract
    from .model_path_quality import ArchitectureResponsibilityFact, HARD_SEMANTIC_DIMENSIONS, ARCHITECTURE_HARD_DIMENSION_PROJECTION, derive_retained_elements
    from .native_case_protocol import NativeModelCaseContract, ARCHITECTURE_MATERIAL_SCHEMA, parse_native_architecture_material
    from .source_identity import functional_source_fingerprint
    root = Path(root)
    model = source.model_id
    path = "src/" + model + ".py"
    spec_path = "docs/finite-semantics.json"
    semantics = json.loads((root / spec_path).read_text(encoding="utf-8"))
    fp = functional_source_fingerprint(root, path)
    spec_fp = functional_source_fingerprint(root, spec_path)
    manifest = [{"path": path, "sha256": fp}]
    file = ImplementationFileDisposition(path, "production", fp, "model_implementation", "Actual independently bounded finite integer function", True, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID)
    import ast
    dispositions = {file.path + "#" + row.symbol: "model_implementation" if row.symbol == "classify" else "scoped_out" for row in _collect_node_specs(ast.parse((root / file.path).read_text(encoding="utf-8")))}
    discovered = discover_python_implementation_surfaces(root=root, file_disposition=file, surface_dispositions=dispositions)
    inventory = build_implementation_surface_inventory(root, SoftwareBoundary("boundary:r8-finite:" + model, "finite:current", production_patterns=(path,)), inventory_id="inventory:r8-finite:" + model, file_dispositions=(file,), discovery_results={path: discovered}, resolved_manifest=manifest)
    surface = next(row for row in inventory.surfaces if row.symbol == "classify")
    code = CodeContract("code-contract:r8-finite:" + model, path=path, symbol="classify", implements_obligations=("obligation:r8-finite:classification:" + model,), external_inputs=("integer",), external_outputs=("outcome:r8:finite_classification:" + model,), error_paths=("TypeError for non-integer",))
    element = "function-block:r8-finite:" + model
    specs, oracles, contracts, facts, rows = [], [], [], [], []
    for case, inputs in (("overlap", ("ordinary", model + "-only")), ("distinct", (model + "-distinct",))):
        case_id = "case:" + model + ":" + case
        spec_id = "semantic-spec:r8-finite:" + model + ":" + case
        oracle_id = "model:" + model + ":" + case_id + ":input"
        groups = tuple((dimension, json.dumps({"schema": "flowguard.architecture_hard_semantics.v1", "dimension": dimension, "input_class_ids": list(inputs), "hard_dimensions": {hard: semantics[hard] for hard in names}}, sort_keys=True, separators=(",", ":"))) for dimension, names in ARCHITECTURE_HARD_DIMENSION_PROJECTION.items())
        spec = SemanticSpecReference(spec_id, "spec-owner:r8-finite", spec_path, spec_fp, spec_path, "spec-owner:r8-finite", spec_fp, (element,), tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), groups, provenance_fingerprints=((spec_path, spec_fp),))
        contract = NativeModelCaseContract("model:" + model, case_id, "good", callable_ref=path + "#classify", result_selector="scenario:" + case, expected_status="pass", expected_observed_status="ok", covered_dimensions=GOOD_DIMENSIONS, oracle_member_ids=tuple("model:" + model + ":" + case_id + ":" + dimension for dimension in sorted(GOOD_DIMENSIONS)), evidence_scope="implementation_boundary", input_contract_fingerprint=os.environ.get("FLOWGUARD_INPUT_FINGERPRINT", ""), oracle_content_fingerprint="")
        oracle = OracleReference(oracle_id, "model:" + model, "native-input-contract:" + case_id, source.source_refs[0]["source_fingerprint"], source.source_refs[0]["path"], "model:" + model, source.source_refs[0]["source_fingerprint"], (element,), tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), groups)
        specs.append(spec); oracles.append(oracle); contracts.append(contract)
        facts.append((case, inputs, spec, oracle))
    binding = ModelImplementationBinding("binding:r8-finite:" + model, element, ("obligation:r8-finite:classification:" + model,), surface.surface_id, "implements", code.code_contract_id, path, "model:" + model, fp, tuple(row.semantic_spec_id for row in specs), tuple(row.oracle_id for row in oracles), required_dimensions=tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), owner_contract_fingerprint=fingerprint_payload(code.to_dict()), test_evidence_ids=("test:r8-finite:" + model,), test_evidence_fingerprints=(("test:r8-finite:" + model, source.source_refs[0]["source_fingerprint"]),))
    report = review_model_implementation_bindings(inventory, required_model_element_ids=(element,), bindings=(binding,), semantic_specs=tuple(specs), oracles=tuple(oracles))
    if not report.ok:
        raise NativeCaseProtocolError("finite function bindings are incomplete: " + str(report.to_dict()["findings"]))
    responsibilities = []
    for case, inputs, spec, oracle in facts:
        responsibility = "responsibility:r8-finite:" + model + ":" + case
        fact = ArchitectureResponsibilityFact(responsibility, model, (element,), "model:" + model, "boundary:r8-finite:classification", "layer:finite:classification", inputs, semantics, surface.surface_id, surface.structure_fingerprint, code.code_contract_id, fingerprint_payload(code.to_dict()), (spec.semantic_spec_id,), (spec.fingerprint,), (oracle.oracle_id,), binding.fingerprint, ({"path": path, "source_fingerprint": fp}, {"path": spec_path, "source_fingerprint": spec_fp}))
        responsibilities.append(fact)
        rows.extend({"responsibility_id": responsibility, "hard_dimension_id": hard, "input_class_id": context, "code_contract_id": code.code_contract_id, "semantic_spec_id": spec.semantic_spec_id, "oracle_id": oracle.oracle_id, "source_case_ids": ["case:" + model + ":" + case]} for context in inputs for hard in HARD_SEMANTIC_DIMENSIONS)
    model_facts = dict(source.model_facts)
    model_facts["function_blocks"] = list(model_facts["function_blocks"]) + [{"id": element, "name": "classify"}]
    model_facts["responsibilities"] = [row.to_dict() for row in responsibilities]
    refs = {row["path"]: row["source_fingerprint"] for row in source.source_refs}; refs.update({path: fp, spec_path: spec_fp})
    source_refs = tuple({"path": path, "source_fingerprint": value} for path, value in sorted(refs.items()))
    groundings = {**source.element_groundings, element: {"kind": "actual_finite_function", "source_ref": path, "source_fingerprint": fp}}
    declared = replace(source, source_refs=source_refs, model_facts=model_facts, element_groundings=groundings, declared_element_ids=tuple(row for row, _ in derive_retained_elements(model_facts)))
    material = {"schema": ARCHITECTURE_MATERIAL_SCHEMA, "model_id": model, "source_refs": list(source_refs), "observed_source_inputs": [{"path": row["path"], "sha256": row["source_fingerprint"]} for row in source_refs], "resolved_manifest_rows": manifest, "implementation_inventory": inventory.to_dict(), "binding_report": report.to_dict(), "code_contracts": [code.to_dict()], "native_case_contracts": [row.to_dict() for row in contracts], "responsibility_context_rows": rows}
    return NativeArchitectureDeclaration(declared, parse_native_architecture_material(material))


def r8_finite_classification_checks(model, case, value, actual, error, function):
    """Measure the finite function once; preserve its positive and invalid probes."""
    declaration = _DECLARED_SOURCE.get()
    if case == "bad":
        return []
    if declaration is None:
        raise NativeCaseProtocolError("finite function lacks declared independent source")
    fact = next(row for row in declaration["model_facts"]["responsibilities"] if row["responsibility_id"] == "responsibility:r8-finite:" + model + ":" + case)
    samples = {str(sample): actual if sample == value else function(sample) for sample in (-1, 0, 1)}
    valid = samples == {"-1": "nonpositive", "0": "nonpositive", "1": "positive"} and error == "TypeError"
    observed = {"actual_input": value, "actual_output": actual, "actual_sample_outputs": samples, "actual_invalid_input_error": error, "function_boundary": "classify(integer)->positive/nonpositive; rejects other input"}
    return [{"check_id": "semantic-check:" + fact["responsibility_id"] + ":" + hard + ":" + context,
             "responsibility_id": fact["responsibility_id"], "hard_dimension_id": hard, "input_class_id": context,
             "args": {"value": value, "invalid_probe": "invalid"}, "observed": observed,
             "expected": expected, "status": "pass" if valid else "blocked"}
            for context in fact["applicable_input_class_ids"] for hard, expected in fact["hard_semantics"].items()]

def write_r8_finite_native_fixture(root):
    """Build an independent two-owner actual function fixture, not a receipt stub."""
    from .model_regressions import MANIFEST_SCHEMA
    from .model_purpose import build_model_purpose_closure, file_fingerprint
    from .native_case_protocol import NativeCaseBinding, BAD_DIMENSIONS, BOUNDARY_DIMENSIONS
    from .native_case_mapping import compute_native_case_mapping_fingerprint, NATIVE_CASE_MAPPING_SCHEMA
    from .source_identity import source_file_fingerprint
    root = Path(root).resolve()
    source_root = Path(__file__).resolve().parents[1]
    if root.exists() and any(root.iterdir()):
        raise NativeCaseProtocolError("finite native fixture requires an empty private root")
    root.mkdir(parents=True, exist_ok=True)
    canonical_spec = root / "openspec/specs/model-maturation-receipt/spec.md"
    canonical_spec.parent.mkdir(parents=True)
    canonical_spec.write_bytes((source_root / "openspec/specs/model-maturation-receipt/spec.md").read_bytes())
    rows, mapping = [], []
    from .model_path_quality import HARD_SEMANTIC_DIMENSIONS
    spec = root / "docs/finite-semantics.json"
    spec.parent.mkdir(parents=True, exist_ok=True)
    finite_semantics = {hard: {"not_applicable": "This finite synchronous integer classification function has no " + hard.replace("_", " ") + " state or execution-owner boundary"} for hard in HARD_SEMANTIC_DIMENSIONS}
    finite_semantics.update({"accepted_inputs": {"types": ["integer"], "samples": [-1, 0, 1]}, "rejected_inputs": {"types": ["noninteger"], "samples": ["invalid"]}, "outputs": {"samples": {"-1": "nonpositive", "0": "nonpositive", "1": "positive"}}, "terminal_states": {"returns": ["positive", "nonpositive"], "raises": ["TypeError"]}, "protected_errors": {"error_type": "TypeError"}, "intent": {"classification": "integer sign"}, "behavior_commitments": {"negative_and_zero": "nonpositive", "positive": "positive"}, "oracles": {"positive_samples": [-1, 0, 1], "invalid_sample": "invalid"}, "evidence_obligations": {"native_input_oracle": "actual finite classification samples"}})
    spec.write_text(json.dumps(finite_semantics, sort_keys=True), encoding="utf-8")
    for model_id in ("alpha", "beta"):
        model_path = root / ".flowguard/models/owners" / model_id / "model.py"
        runner_path = root / ".flowguard/verification/owners" / model_id / "run_checks.py"
        implementation_path = root / "src" / (model_id + ".py")
        for path in (model_path, runner_path, implementation_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        implementation_path.write_text("def classify(value):\n    if type(value) is not int:\n        raise TypeError('finite integer boundary')\n    return 'positive' if value > 0 else 'nonpositive'\n", encoding="utf-8")
        model_path.write_text(
            "from dataclasses import dataclass\n"
            "from flowguard import FunctionResult\n"
            "from flowguard.workflow import Workflow\n"
            "from flowguard import Invariant, InvariantResult\n"
            "from flowguard.scenario import Scenario, ScenarioExpectation\n"
            "from flowguard.review import review_scenarios\n"
            "from src." + model_id + " import classify\n"
            "@dataclass(frozen=True)\nclass State:\n    value: str = ''\n    semantic_checks: tuple = ()\n    def __hash__(self):\n        import json\n        return hash((self.value, json.dumps(self.semantic_checks, sort_keys=True)))\n    def to_dict(self):\n        return {'value': self.value, 'semantic_checks': list(self.semantic_checks)}\n"
            "class Classify:\n    def __init__(self, case):\n        self.case = case\n    name = 'Classify'\n    accepted_input_type = object\n    reads = ()\n    writes = ('value', 'semantic_checks')\n    def apply(self, value, state):\n        try:\n            actual = classify(value)\n        except TypeError:\n            actual = 'invalid'\n        error = ''\n        try:\n            classify('invalid')\n        except TypeError as exc:\n            error = type(exc).__name__\n        from flowguard.native_case_runner import r8_finite_classification_checks\n        checks = r8_finite_classification_checks(" + repr(model_id) + ", self.case, value, actual, error, classify)\n        return (FunctionResult(output=actual, new_state=State(actual, tuple(checks)), label='actual-classify'),)\n"
            "def valid(state, trace):\n    return InvariantResult.fail('invalid finite boundary') if state.value == 'invalid' else InvariantResult.pass_()\n"
            "INVARIANTS = (Invariant('r8-finite:invalid', 'Reject actual invalid typed input', valid),)\n"
            "SCENARIOS = tuple(Scenario(name=case, description='actual finite classify', workflow=Workflow((Classify(case),), name='finite-classify-' + case), initial_state=State(), external_input_sequence=(value,), invariants=INVARIANTS, expected=ScenarioExpectation(expected_status=expected, required_trace_labels=('actual-classify',) if expected == 'ok' else (), expected_violation_names=('r8-finite:invalid',) if expected == 'violation' else ())) for case, value, expected in (('overlap', 1, 'ok'), ('distinct', 0, 'ok'), ('bad', 'invalid', 'violation')))\n"
            "def run_review():\n    return review_scenarios(SCENARIOS)\n"
            "def export_path_quality_source(instance):\n    from pathlib import Path\n    from flowguard.model_path_quality import compile_declared_path_quality_source\n    from flowguard.source_identity import functional_source_fingerprint\n    root = Path(__file__).resolve().parents[4]\n    relative = Path(__file__).resolve().relative_to(root).as_posix()\n    from flowguard.native_case_runner import build_r8_finite_architecture_declaration\n    source = compile_declared_path_quality_source(model_id=" + repr(model_id) + ", model_instance_fingerprint=instance, source_refs=({'path': relative, 'source_fingerprint': functional_source_fingerprint(root, relative)},), workflows=tuple(s.workflow for s in SCENARIOS if s.expected.expected_status == 'ok'), invariants=INVARIANTS)\n    return build_r8_finite_architecture_declaration(root, source)\n",
            encoding="utf-8")
        runner_path.write_text(
            "import sys\nfrom pathlib import Path\nsys.path.insert(0, " + repr(str(source_root)) + ")\nsys.path.insert(0, str(Path(__file__).resolve().parents[4]))\nsys.path.insert(0, str(Path(__file__).resolve().parents[4] / '.flowguard/models/owners/" + model_id + "'))\n"
            "from model import run_review, export_path_quality_source\nfrom flowguard.native_case_runner import native_main\ndef main():\n    report = run_review()\n    print(report.format_text())\n    return 0 if report.ok else 1\nif __name__ == '__main__':\n    raise SystemExit(native_main('model:" + model_id + "', main, declared_source_exporter=export_path_quality_source))\n",
            encoding="utf-8")
        design_path = root / "docs" / ("current-design-" + model_id + ".md")
        design_path.write_text("The independent src/" + model_id + ".py classify function must map strictly typed integers to positive or nonpositive, reject every other type with TypeError, and preserve current independent input/native evidence. Its classification obligation is obligation:r8-finite:classification:" + model_id + ".\n", encoding="utf-8")
        owner = "model:" + model_id
        purpose = build_model_purpose_closure(model_instance_id="regression:" + model_id + ":current", reusable_model_type_id=model_id, task_intent_id="intent:r8-finite:" + model_id, guarded_purpose="Reject invalid typed inputs without accepting stale finite owner evidence", protected_failure_ids=("r8-finite:invalid",), known_good_case_id="case:" + model_id + ":overlap", failure_bindings=({"failure_id": "r8-finite:invalid", "known_bad_case_id": "case:" + model_id + ":bad", "oracle_id": "oracle:r8-finite:" + model_id},), claim_boundary="Only the actual finite integer function in this independent private fixture", evidence_check_ids=("check:model-regression:" + model_id,), model_sha256=file_fingerprint(model_path), runner_sha256=file_fingerprint(runner_path))
        inputs = [path.relative_to(root).as_posix() for path in (model_path, runner_path, implementation_path)] + ["docs/finite-semantics.json", design_path.relative_to(root).as_posix()]
        rows.append({"model_id": model_id, "model_path": inputs[0], "runner": ["{python}", inputs[1]], "tier": "full", "timeout_seconds": 60, "shard_safe": True, "mutation_policy": "none", "input_globs": inputs, "expected_artifacts": [], "exclusion_reason": "", "purpose_closure": purpose.to_dict(), "functional_obligation_ids": ["obligation:r8-finite:classification:" + model_id], "intent_source_inputs": [design_path.relative_to(root).as_posix()]})
        for name, kind, observed in (("overlap", "good", "ok"), ("distinct", "good", "ok"), ("bad", "bad", "violation")):
            mapping.append(NativeCaseBinding(owner, "r8-finite:" + model_id + ":" + name, name, ("case:" + model_id + ":" + name,), kind, "implementation_boundary", GOOD_DIMENSIONS if kind == "good" else BAD_DIMENSIONS, "pass", expected_observed_status=observed, protected_failure_ids=("r8-finite:invalid",) if kind == "bad" else (), expected_finding_codes=("r8-finite:invalid",) if kind == "bad" else ()))
        children = tuple(sorted(case for row in mapping if row.owner_id == owner for case in row.native_case_ids))
        mapping.append(NativeCaseBinding(owner, "r8-finite:" + model_id + ":boundary", "r8-finite:" + model_id + ":boundary", ("case:" + model_id + ":boundary",), "boundary", "implementation_boundary", BOUNDARY_DIMENSIONS, "pass", expected_observed_status="ok", required_child_case_ids=children))
    manifest_path = root / ".flowguard/models/regression-manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": MANIFEST_SCHEMA, "governed_input_globs": [".flowguard/models/owners/**/*.py", ".flowguard/verification/owners/**/*.py", "src/**/*.py"], "snapshot_only_input_globs": [], "shared_input_groups": [], "models": rows}, sort_keys=True), encoding="utf-8")
    relative = manifest_path.relative_to(root).as_posix()
    manifest_fp = source_file_fingerprint(manifest_path)
    mapping_fp = compute_native_case_mapping_fingerprint(source_manifest_fingerprint=manifest_fp, source_paths=(relative,), bindings=mapping)
    (root / ".flowguard/models/native-case-mapping.json").write_text(json.dumps({"schema_version": NATIVE_CASE_MAPPING_SCHEMA, "mapping_fingerprint": mapping_fp, "source_manifest_fingerprint": manifest_fp, "source_paths": [relative], "diagnostic_native_case_ids": [], "bindings": [replace(row, mapping_fingerprint=mapping_fp).to_dict() for row in sorted(mapping, key=lambda row: row.blueprint_case_id)]}, sort_keys=True), encoding="utf-8")
    return root


@dataclass(frozen=True)
class R8FunctionalCaseInput:
    case_name: str


@dataclass(frozen=True)
class R8FunctionalCaseState:
    case_name: str = ""
    semantic_checks: tuple[Mapping[str, Any], ...] = ()

    def __hash__(self):
        return hash((self.case_name, json.dumps(self.semantic_checks, sort_keys=True)))

    def to_dict(self):
        return {"case_name": self.case_name, "semantic_checks": list(self.semantic_checks)}


class EvaluateR8FunctionalCase:
    accepted_input_type = R8FunctionalCaseInput
    reads = ()
    writes = ("case_name", "semantic_checks")
    input_description = "One independent finite production-function context"
    output_description = "Actual named semantic observations for this finite context"

    def __init__(self, case_name, repository_root):
        self.case_name = case_name
        self.repository_root = Path(repository_root).resolve()
        self.name = case_name

    def apply(self, input_obj, state):
        from . import FunctionResult
        if input_obj.case_name != self.case_name:
            raise NativeCaseProtocolError("foreign R8 functional case input")
        checks = run_r8_functional_case(self.repository_root, self.case_name)
        return (FunctionResult(output=self.case_name, new_state=R8FunctionalCaseState(self.case_name, tuple(checks)), label=self.case_name, reason="Actual finite calls preserve named hard checks"),)


def r8_functional_case_scenario(root, case_name):
    from . import Invariant, InvariantResult, Workflow, Scenario, ScenarioExpectation
    def actual_checks_pass(state, trace):
        if state.case_name and (not state.semantic_checks or any(row["status"] != "pass" for row in state.semantic_checks)):
            return InvariantResult.fail("Actual R8 production-function semantic check failed")
        return InvariantResult.pass_()
    invariant = Invariant("r8-functional-actual-checks:" + case_name, "Only actual complete semantic checks pass", actual_checks_pass)
    return Scenario(name=case_name, description="R8 actual bounded production function behavior", workflow=Workflow((EvaluateR8FunctionalCase(case_name, root),), name=case_name), initial_state=R8FunctionalCaseState(), external_input_sequence=(R8FunctionalCaseInput(case_name),), invariants=(invariant,), expected=ScenarioExpectation(expected_status="ok", required_trace_labels=(case_name,)))


def _r8_finite_tree(root):
    return {path.relative_to(root).as_posix(): _sha256_bytes(path.read_bytes())
            for path in Path(root).rglob("*") if path.is_file() and "__pycache__" not in path.parts}


def _r8_affected_owner_observations(root):
    import tempfile
    from .model_regressions import run_manifest_regressions, prepare_model_regression_plan
    from .validation_ownership import OWNER_REUSE_CURRENT, OWNER_EXECUTE
    directory = tempfile.mkdtemp(prefix="r8-plan-")
    fixture = write_r8_finite_native_fixture(Path(directory))
    receipts = fixture / ".flowguard/evidence/model-owner-receipts"
    produced = run_manifest_regressions(fixture, tier="full", jobs=1, output_dir=fixture / ".flowguard/work/r8-original", receipt_dir=receipts, require_executed_case_ids=True, command="r8-finite:original-current-native-evidence")
    if not produced.ok:
        raise NativeCaseProtocolError("finite actual native fixture failed; preserved private root=" + str(fixture) + "; findings=" + str(produced.findings))
    original = prepare_model_regression_plan(fixture, receipt_dir=receipts, require_executed_case_ids=True)
    before = {row.owner_id: row.disposition for row in original.rows}
    implementation = fixture / "src/alpha.py"
    implementation.write_text(implementation.read_text(encoding="utf-8") + "\n# actual changed declared alpha input\n", encoding="utf-8")
    frozen_before = _r8_finite_tree(fixture)
    invalid_error = ""
    try:
        prepare_model_regression_plan(fixture / "missing", receipt_dir=receipts, require_executed_case_ids=True)
    except (OSError, ValueError) as exc:
        invalid_error = type(exc).__name__
    changed = prepare_model_regression_plan(fixture, affected_ids=("model:alpha",), receipt_dir=receipts, require_executed_case_ids=True)
    frozen_after = _r8_finite_tree(fixture)
    decisions = {row.owner_id: row.disposition for row in changed.rows}
    valid = before == {"model:alpha": OWNER_REUSE_CURRENT, "model:beta": OWNER_REUSE_CURRENT} and decisions == {"model:alpha": OWNER_EXECUTE, "model:beta": OWNER_REUSE_CURRENT}
    return {"args": {"affected_ids": ["model:alpha"], "complete_owner_denominator": list(changed.model_denominator)},
            "result": {"before_dispositions": before, "changed_dispositions": decisions, "rows": [row.to_dict() for row in changed.rows], "native_fixture_parent": produced.parent_receipt_fingerprint},
            "valid": valid, "rejected": bool(invalid_error), "rejection": invalid_error,
            "read_only": frozen_before == frozen_after, "recovered": valid,
            "authority": bool(next((row.reuse_receipt_ref for row in changed.rows if row.owner_id == "model:beta"), "")),
            "counts": {"execute": len([row for row in changed.rows if row.disposition == OWNER_EXECUTE]), "reuse": len([row for row in changed.rows if row.disposition == OWNER_REUSE_CURRENT])}}



def _r8_verified_finite_responsibilities(fixture, parent=None):
    """Authenticate each independent denominator against its original typed leaf."""
    from .model_regressions import resolve_current_full_model_regression_parent, prepare_model_regression_plan
    from .validation_ownership import build_owner_receipt_context
    from .native_case_protocol import parse_native_architecture_material, NativeModelCaseContract
    from .implementation_inventory import ImplementationSurfaceInventory
    from .model_test_alignment import CodeContract
    from .model_path_quality import (ArchitectureResponsibilityFact, ResponsibilitySemanticEvidenceBinding,
        parse_architecture_binding_report, verify_responsibility_semantic_evidence)
    current = resolve_current_full_model_regression_parent(fixture, receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts")
    if parent is not None and Path(current.parent_artifact_path).resolve() != Path(parent.parent_receipt_path).resolve():
        raise NativeCaseProtocolError("finite evidence parent differs from original current composition")
    observation = prepare_model_regression_plan(fixture, receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts").current_observation
    from .native_case_mapping import load_native_case_mapping
    mapping = load_native_case_mapping(fixture)
    facts, reviews = {}, {}
    for model, leaf in sorted(current.child_evidence_by_model_id.items()):
        raw = json.loads(Path(leaf.native_case_result_artifact_path).with_name("native-source.json").read_text(encoding="utf-8"))
        material = parse_native_architecture_material(raw["architecture_material"])
        leaf = current.child_evidence_by_model_id[model]
        if leaf.receipt is None or leaf.verification is None or not leaf.verification.ok:
            raise NativeCaseProtocolError("finite leaf is not current and authenticated")
        context = build_owner_receipt_context(observation.current_by_owner["model:" + model], leaf.receipt, fixture / ".flowguard/evidence/model-owner-receipts")
        context = replace(context, receipt_store_repository_root=str(fixture), receipt_store_output_directory=str(fixture / ".flowguard/evidence/model-owner-receipts"))
        report = parse_architecture_binding_report(material["binding_report"])
        inventory = ImplementationSurfaceInventory.from_dict(material["implementation_inventory"])
        code = tuple(CodeContract(**row) for row in material["code_contracts"])
        contracts = tuple(NativeModelCaseContract.from_dict(row) for row in material["native_case_contracts"])
        native_bindings = tuple(row for row in mapping.bindings if row.owner_id == "model:" + model)
        identities = {(row.owner_id, row.source_case_id): {name: getattr(row, name) for name in
            ("input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint")} for row in leaf.native_case_results}
        inputs = {}
        for row in material["responsibility_context_rows"]:
            for case in row["source_case_ids"]:
                inputs.setdefault(("model:" + model, case), set()).add(row["input_class_id"])
        declaration = raw["declared_path_quality_source"]
        for wire in declaration["model_facts"]["responsibilities"]:
            fact = ArchitectureResponsibilityFact.from_dict(wire)
            evidence = []
            for row in material["responsibility_context_rows"]:
                if row["responsibility_id"] != fact.responsibility_id:
                    continue
                matched = [binding for binding in native_bindings if binding.owner_id == fact.owner_id and
                    tuple(binding.native_case_ids) == tuple(row["source_case_ids"]) and binding.evidence_scope == "implementation_boundary"]
                if len(matched) != 1:
                    raise NativeCaseProtocolError("finite hard context lacks exact original native binding")
                evidence.append(ResponsibilitySemanticEvidenceBinding(row["hard_dimension_id"], row["input_class_id"], row["semantic_spec_id"], row["oracle_id"], matched[0].fingerprint, leaf.receipt.receipt_id, leaf.receipt.fingerprint, fact.owner_id, tuple(row["source_case_ids"]), "implementation_boundary"))
            fact = replace(fact, semantic_evidence_bindings=tuple(evidence))
            review = verify_responsibility_semantic_evidence(fact, binding_report=report, implementation_inventory=inventory,
                code_contracts=code, native_contracts=contracts, native_bindings=native_bindings,
                native_results=leaf.native_case_results, receipts=(leaf.receipt,), receipt_contexts={leaf.receipt.receipt_id: context},
                raw_artifact_root=fixture, current_source_fingerprints={row["path"]: row["sha256"] for row in material["observed_source_inputs"]},
                current_native_identities=identities, native_input_class_ids={key: tuple(sorted(value)) for key, value in inputs.items()},
                observed_source_inputs=tuple(material["observed_source_inputs"]))
            if not review.ready:
                raise NativeCaseProtocolError("finite responsibility lacks actual semantic evidence: " + str(review))
            facts[fact.responsibility_id] = fact
            reviews[fact.responsibility_id] = review
    return facts, reviews


def _r8_comparison_observations(root):
    import tempfile
    from .model_regressions import run_manifest_regressions
    from .model_path_quality import derive_architecture_relation_candidates
    fixture = write_r8_finite_native_fixture(Path(tempfile.mkdtemp(prefix="r8-compare-")))
    parent = run_manifest_regressions(fixture, tier="full", jobs=1, output_dir=fixture / ".flowguard/work/original", receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts", require_executed_case_ids=True, command="r8-finite:context-indexed-comparison")
    if not parent.ok:
        raise NativeCaseProtocolError("comparison finite producer failed; private root=" + str(fixture))
    facts, reviews = _r8_verified_finite_responsibilities(fixture, parent)
    frozen = _r8_finite_tree(fixture)
    output = {}
    for context, case in (("comparison:related_overlap", "overlap"), ("comparison:distinct_context", "distinct")):
        selected = tuple(facts["responsibility:r8-finite:" + model + ":" + case] for model in ("alpha", "beta"))
        semantic_reviews = tuple(reviews[row.responsibility_id] for row in selected)
        input_before = [row.to_dict() for row in selected]
        result = derive_architecture_relation_candidates(selected, semantic_reviews=semantic_reviews)
        unknown = derive_architecture_relation_candidates(selected)
        missing_rejected = not unknown["relations"] and not unknown["rewrite_candidates"] and len(unknown["observation_gap_ids"]) == len(selected)
        error = ""
        try:
            derive_architecture_relation_candidates(selected, semantic_reviews=semantic_reviews, licensed_adapter_pairs=((selected[0].responsibility_id, selected[1].responsibility_id),))
        except ValueError as exc:
            error = str(exc)
        if case == "overlap":
            matching = [row for row in result["relations"] if row["kind"] == "duplicate_boundary"]
            valid = (len(matching) == 1 and matching[0]["input_class_ids"] == ["ordinary"] and
                {row["responsibility_id"]: row["input_class_ids"] for row in matching[0]["remaining_contexts"]} == {selected[0].responsibility_id: ["alpha-only"], selected[1].responsibility_id: ["beta-only"]} and len(result["rewrite_candidates"]) == 1)
        else:
            valid = not result["relations"] and not result["rewrite_candidates"]
        valid = valid and not result["observation_gap_ids"]
        recovered = derive_architecture_relation_candidates(selected, semantic_reviews=semantic_reviews) == result
        output[context] = {"args": {"responsibility_ids": [row.responsibility_id for row in selected], "input_class_ids": [list(row.applicable_input_class_ids) for row in selected]},
            "result": {**result, "original_parent_receipt": parent.parent_receipt_path, "unverified_observation": unknown, "independent_semantic_reviews": [{"responsibility_fingerprint": row.responsibility_fingerprint, "ready": row.ready, "gap_ids": list(row.gap_ids), "semantic_content_fingerprint": row.semantic_content_fingerprint} for row in semantic_reviews]},
            "valid": valid, "rejected": missing_rejected and "architecture_handoff_evidence_unknown" in error, "rejection": error,
            "read_only": frozen == _r8_finite_tree(fixture) and input_before == [row.to_dict() for row in selected], "recovered": recovered, "authority": all(row.ready for row in semantic_reviews)}
    return output


def _r8_public_read_observations(root):
    import tempfile
    from .model_regressions import run_manifest_regressions, resolve_current_full_model_regression_parent
    from .functional_task_context import (finite_current_design_contributions, prepare_finite_functional_authority,
        prepare_functional_task_request, produce_functional_task_context)
    from .__main__ import _read_operation
    fixture = write_r8_finite_native_fixture(Path(tempfile.mkdtemp(prefix="r8-read-")))
    # Distinct actual file bytes ensure the foreign fixture has a real different head.
    alpha_path = fixture / "src/alpha.py"
    with alpha_path.open("a", encoding="utf-8") as stream:
        stream.write("\n# R9 finite fixture identity: " + fixture.name + "\n")
    contributions = finite_current_design_contributions(fixture)
    parent = run_manifest_regressions(fixture, tier="full", jobs=1, output_dir=fixture / ".flowguard/work/original", receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts", require_executed_case_ids=True, command="r8-finite:public-functional-read")
    if not parent.ok:
        raise NativeCaseProtocolError("public read finite producer failed; root=" + str(fixture))
    state = prepare_finite_functional_authority(repository_root=fixture, parent=parent, current_design_contributions=contributions)
    current = resolve_current_full_model_regression_parent(fixture, receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts")
    raw = json.loads(Path(current.child_evidence_by_model_id["alpha"].native_case_result_artifact_path).with_name("native-source.json").read_text(encoding="utf-8"))
    materials = [raw["architecture_material"]]
    beta_raw = json.loads(Path(current.child_evidence_by_model_id["beta"].native_case_result_artifact_path).with_name("native-source.json").read_text(encoding="utf-8"))
    materials.append(beta_raw["architecture_material"])
    request, output = prepare_functional_task_request(repository_root=fixture, task_id="r8-public-read", primary_model_id="alpha",
        task_purpose="Understand both actual finite integer classification outcomes from independent current evidence",
        requested_outcome_ids=tuple(dict.fromkeys(value for material in materials for contract in material["code_contracts"] for value in contract["implements_obligations"])),
        affected_surface_ids=tuple(row["implementation_surface_id"] for material in materials for row in material["binding_report"]["bindings"]),
        related_model_ids=("beta",))
    produced = produce_functional_task_context(repository_root=fixture, request=request, output_directory=output, command="r8-finite:produce-public-task-context")
    if produced["status"] != "pass":
        raise NativeCaseProtocolError("actual functional producer blocked; root=" + str(fixture) + "; result=" + str(produced))
    read_request = {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"], "task_context": produced["task_context_ref"]}
    frozen = _r8_finite_tree(fixture)
    input_before = json.dumps(read_request, sort_keys=True)
    observed = _read_operation(fixture, read_request, {})
    unknown_error = ""
    try:
        _read_operation(fixture, {**read_request, "unknown_request_key": True}, {})
    except ValueError as exc:
        unknown_error = str(exc)
    unauthenticated_error = ""
    unauthenticated = {}
    try:
        unauthenticated = _read_operation(fixture, {**read_request, "task_context": {**produced["task_context_ref"], "sha256": "0" * 64}}, {})
    except ValueError as exc:
        unauthenticated_error = str(exc)
    narrowed = _read_operation(fixture, {**read_request, "scope": ["alpha"]}, {})
    narrowed_functional = narrowed.get("functional_understanding", {})
    recovered = _read_operation(fixture, read_request, {})
    functional = observed.get("functional_understanding", {})
    valid = observed["status"] == "pass" and functional.get("stopping_disposition") == "model_maturation_closed_for_task" and not functional.get("gap_ids")
    result = {"public_read": observed, "narrowed_read": narrowed, "unauthenticated_rejection": {"exception_type": "ValueError" if unauthenticated_error else "", "message": unauthenticated_error, "original_public_result": unauthenticated}, "original_task_context_ref": produced["task_context_ref"], "original_producer_verification": produced["verification"], "actual_accepted_head": state.head.fingerprint, "original_parent_path": parent.parent_receipt_path}
    return {"task:selected_current": {"args": read_request, "result": result,
        "valid": valid, "rejected": bool(unknown_error) and ("functional_task_context_invalid" in unauthenticated.get("functional_understanding", {}).get("gap_ids", ())) and narrowed_functional.get("stopping_disposition") == "needs_evidence" and bool(narrowed_functional.get("gap_ids")),
        "rejection": unknown_error, "read_only": frozen == _r8_finite_tree(fixture) and input_before == json.dumps(read_request, sort_keys=True),
        "recovered": recovered == observed, "authority": produced["verification"].get("ok") is True and observed.get("authority_integrity") in {"pass", "pass_with_gaps"} and observed.get("as_of", {}).get("authority_head_fingerprint") == state.head.fingerprint}}

def _r9_current_finite_fixture(prefix, *, pointer_goal=False):
    """Create genuine two-owner native and accepted evidence in a private fixture."""
    import tempfile
    from .model_regressions import run_manifest_regressions, resolve_current_full_model_regression_parent
    from .functional_task_context import finite_current_design_contributions, prepare_finite_functional_authority, _finite_native_material
    from .model_authority_store import _SelectedReadContext
    fixture = write_r8_finite_native_fixture(Path(tempfile.mkdtemp(prefix=prefix)))
    # The foreign fixture must have a different observed Source identity, not
    # merely a different directory containing identical accepted inputs.
    alpha_path = fixture / "src/alpha.py"
    with alpha_path.open("a", encoding="utf-8") as stream:
        stream.write("\n# R9 finite fixture identity: " + fixture.name + "\n")
    contributions = finite_current_design_contributions(fixture)
    if pointer_goal:
        from .model_intent import ArchitectureObjective, ArchitectureObjectiveSource
        from .source_identity import source_file_fingerprint
        objective = ArchitectureObjective("objective:r9-fixture:alpha-shared-service", True,
            ("alpha",), ("responsibility:r8-finite:alpha:overlap",), ("ordinary", "alpha-only"),
            "allowed_layers", {"layer_ids": ["layer:fixture:shared-service"]},
            "model:alpha", ("r8-finite:invalid",))
        goal_path = fixture / "docs/current-design-alpha.md"
        with goal_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\nThis independent fixture requests a shared-service layer while preserving its classification outcome and invalid-input error. It does not prescribe a universal software architecture.\n```flowguard-architecture-objectives\n"
                + json.dumps(ArchitectureObjectiveSource((objective,)).to_dict(), sort_keys=True)
                + "\n```\n")
        contributions = tuple(replace(row, source_fingerprint=source_file_fingerprint(goal_path),
            target_invariant_ids=tuple(sorted(set(row.target_invariant_ids) | {objective.objective_id})))
            if row.contribution_id == "intent:current-design:alpha" else row for row in contributions)
    parent = run_manifest_regressions(fixture, tier="full", jobs=1,
        output_dir=fixture / ".flowguard/work/original",
        receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts",
        require_executed_case_ids=True, command="r9-finite:" + prefix)
    if not parent.ok:
        raise NativeCaseProtocolError("R9 finite original native producer failed; preserved root=" + str(fixture))
    state = prepare_finite_functional_authority(repository_root=fixture, parent=parent, current_design_contributions=contributions)
    current = resolve_current_full_model_regression_parent(fixture, receipt_dir=fixture / ".flowguard/evidence/model-owner-receipts")
    context = _SelectedReadContext(fixture)
    leaves = [{"owner_id": "model:" + model, "receipt_id": leaf.receipt_id, "receipt_fingerprint": leaf.receipt_fingerprint}
              for model, leaf in current.child_evidence_by_model_id.items()]
    material = _finite_native_material(fixture, state, leaves, context)
    if pointer_goal:
        from .model_intent import derive_architecture_objective_projection
        view = state.accepted_revision.current_effective_intent_view
        identities = {row.contribution_id: row for row in view.verified_source_identities}
        source_bytes = {row.contribution_id: (fixture / row.source_ref).read_bytes()
                        for row in view.active_contributions}
        goals = derive_architecture_objective_projection(view, source_bytes_by_contribution_id=source_bytes)
        current = dict(material["current_source_fingerprints"])
        for goal in goals:
            identity = identities[goal.contribution_id]
            if (identity.fingerprint != goal.source_identity_fingerprint
                    or identity.source_ref != goal.source_ref
                    or source_file_fingerprint(fixture / goal.source_ref) != goal.source_fingerprint):
                raise NativeCaseProtocolError("accepted finite goal Source identity is not current")
            if goal.source_ref in current and current[goal.source_ref] != goal.source_fingerprint:
                raise NativeCaseProtocolError("finite goal/native Source identity conflict")
            current[goal.source_ref] = goal.source_fingerprint
        material = {**material, "current_source_fingerprints": current}
    return fixture, state, parent, material, context


def _r9_normal_task_context_observations(root):
    """Execute the normal CLI against genuine current and insufficient tasks."""
    import subprocess
    from .functional_task_context import prepare_functional_task_request, MATURATION_ROOT
    from .__main__ import _read_operation
    from .model_authority_store import load_observed_model_head
    fixture, state, parent, material, _ = _r9_current_finite_fixture("r9-normal-")
    source = Path(root).resolve()
    outcomes = tuple(sorted({outcome for code in material["code_contracts"] for outcome in code.external_outputs}))
    observations = {}
    for context, requested in (("normal:current_verified", outcomes),
                               ("normal:original_diagnostic", ("outcome:finite:unadmitted-normal-use",))):
        request, output = prepare_functional_task_request(repository_root=fixture,
            task_id="r9-native-" + context.replace(":", "-"), primary_model_id="alpha",
            task_purpose="Use the actual normal producer and retain its original current-or-gap result",
            requested_outcome_ids=requested, affected_surface_ids=material["implementation_inventory"].required_surface_ids,
            related_model_ids=("beta",))
        request_path = output / "producer-request.json"
        argv = [sys.executable, "-B", str(source / "scripts/produce_flowguard_task_context.py"),
                "--root", str(fixture), "--request", str(request_path), "--output-dir", str(output), "--json"]
        before = _r8_finite_tree(fixture)
        result = subprocess.run(argv, cwd=fixture, capture_output=True, text=True, encoding="utf-8", check=False)
        invocation = {"argv": argv, "cwd": str(fixture), "returncode": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr}
        invocation_path = output / "native-normal-cli-invocation.json"
        with invocation_path.open("x", encoding="utf-8") as stream:
            json.dump(invocation, stream, ensure_ascii=False, sort_keys=True)
        produced = json.loads(result.stdout)
        reference = produced.get("task_context_ref")
        if not isinstance(reference, Mapping):
            raise NativeCaseProtocolError("normal CLI did not preserve an authentic current-or-gap context; root=" + str(fixture))
        document_raw = (fixture / reference["path"]).read_bytes()
        if _sha256_bytes(document_raw).removeprefix("sha256:") != reference["sha256"]:
            raise NativeCaseProtocolError("normal task context raw reference differs")
        document = json.loads(document_raw)
        read_request = {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"], "task_context": reference}
        read_before = _r8_finite_tree(fixture)
        public = _read_operation(fixture, read_request, {})
        actual = public.get("functional_understanding", {})
        reread = _read_operation(fixture, read_request, {})
        bad_error = ""
        rejected_public = {}
        try:
            rejected_public = _read_operation(fixture, {**read_request, "task_context": {**reference, "sha256": "0" * 64}}, {})
        except ValueError as exc:
            bad_error = str(exc)
        diagnostic = context == "normal:original_diagnostic"
        if diagnostic:
            valid = (result.returncode == 2 and produced.get("status") == "blocked"
                and document["context_kind"] == "diagnostic" and document["maturation_receipt_ref"] is None
                and actual.get("stopping_disposition") != "model_maturation_closed_for_task"
                and bool(actual.get("gap_ids")) and isinstance(actual.get("first_gap"), Mapping)
                and actual.get("gap_report_ref") == document["diagnostic_ref"])
        else:
            valid = (result.returncode == 0 and produced.get("status") == "pass"
                and produced.get("verification", {}).get("ok") is True
                and document["context_kind"] == "verified_maturation" and document["diagnostic_ref"] is None
                and actual.get("stopping_disposition") == "model_maturation_closed_for_task" and not actual.get("gap_ids"))
        after = _r8_finite_tree(fixture)
        new_paths = sorted(set(after) - set(before))
        allowed = (output.relative_to(fixture).as_posix() + "/", MATURATION_ROOT + "/")
        effects_valid = (all(after.get(path) == fingerprint for path, fingerprint in before.items())
            and bool(new_paths) and all(path.startswith(allowed) for path in new_paths)
            and read_before == after and load_observed_model_head(fixture).fingerprint == state.head.fingerprint)
        observations[context] = {"args": {"argv": argv, "requested_outcome_ids": list(requested)},
            "result": {"producer": produced, "public_read": public,
                "context_document": document, "rejected_public_read": rejected_public, "normal_cli_invocation_ref": {"path": str(invocation_path), "sha256": _sha256_bytes(invocation_path.read_bytes()).removeprefix("sha256:")},
                "created_evidence_paths": new_paths, "original_parent_path": parent.parent_receipt_path,
                "normal_task_producer_invocation_count": 1},
            "valid": valid, "rejected": "functional_task_context_invalid" in rejected_public.get("functional_understanding", {}).get("gap_ids", ()), "rejection": json.dumps(rejected_public, sort_keys=True) if rejected_public else bad_error,
            "read_only": False, "effects_valid": effects_valid, "recovered": reread == public,
            "authority": (load_observed_model_head(fixture).fingerprint == state.head.fingerprint and public.get("authority_integrity") in {"pass", "pass_with_gaps"})}
    return observations


def _r9_growth_observations(root):
    """Measure real finite add/delete/rename/neighbor states and unknown admission."""
    from .model_authority_store import _observe_growth_paths
    fixture, state, parent, material, context = _r9_current_finite_fixture("r9-growth-")
    inventory, report = material["implementation_inventory"], material["binding_report"]
    # The fixture's verified original leaves already registered these typed
    # declared/authenticated scopes through _finite_native_material.
    new = fixture / "src/new-neighbor.py"
    new.write_text("def neighbor(value):\n    return value\n", encoding="utf-8")
    deleted = fixture / "src/deleted.py"
    deleted.write_text("def deleted():\n    return None\n", encoding="utf-8")
    deleted.unlink()
    old = fixture / "src/rename-old.py"
    old.write_text("def renamed(value):\n    return value\n", encoding="utf-8")
    renamed = fixture / "src/rename-new.py"
    old.rename(renamed)
    paths = ("src/alpha.py", "src/deleted.py", "src/new-neighbor.py", "src/rename-old.py", "src/rename-new.py")
    before = _r8_finite_tree(fixture)
    observed = _observe_growth_paths(context, paths)
    empty = _observe_growth_paths(context, ())
    error = ""
    try:
        _observe_growth_paths(context, ("../outside",))
    except ValueError as exc:
        error = str(exc)
    gaps = {row["path"]: row for row in observed["growth_gaps"]}
    expected_states = {"src/deleted.py": "missing", "src/new-neighbor.py": "present",
                       "src/rename-old.py": "missing", "src/rename-new.py": "present"}
    valid = (observed["checked_observed_paths"] == tuple(sorted(paths))
        and observed["live_unregistered_file_detection"] == "FINITE_OBSERVATION"
        and all(gaps.get(path, {}).get("observed_state") == value for path, value in expected_states.items())
        and "src/alpha.py" not in gaps and {"src/deleted.py", "src/rename-old.py"} <= context.missing_paths)
    unknown = all(not gaps[path]["next_owner_id"] and gaps[path]["next_action"] == "boundary_admission_required:" + path for path in expected_states)
    after = _r8_finite_tree(fixture)
    common = {"args": {"changed_paths": list(paths), "actual_rename_old": "src/rename-old.py", "actual_rename_new": "src/rename-new.py"},
        "result": {"growth": observed, "unobserved": empty, "original_parent_path": parent.parent_receipt_path,
                   "actual_missing_paths": sorted(context.missing_paths),
                   "current_accepted_head_fingerprint": state.head.fingerprint},
        "rejected": bool(error), "rejection": error, "read_only": before == after,
        "recovered": _observe_growth_paths(context, paths) == observed,
        "authority": material["binding_report"].ok and bool(material["receipts"])}
    return {"growth:finite_present_and_missing": {**common, "valid": valid},
            "growth:unknown_admission": {**common, "valid": unknown and empty["live_unregistered_file_detection"] == "NOT_OBSERVED" and not empty["growth_gaps"]}}


def _r9_pointer_detail_observations(root):
    """Direct production resolver calls use this fixture's genuine accepted detail."""
    from .model_authority_store import resolve_architecture_improvement_pointer
    from .__main__ import _read_operation
    fixture, state, parent, material, _ = _r9_current_finite_fixture("r9-pointer-", pointer_goal=True)
    public = _read_operation(fixture, {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"], "read_batch": True}, {})
    pointers = [row for page in public.get("pages", ()) for row in page.get("architecture", {}).get("improvement_pointers", ())]
    if not pointers:
        raise NativeCaseProtocolError("finite accepted original native material has no actual pointer; preserved root=" + str(fixture))
    reference = pointers[0]
    before = _r8_finite_tree(fixture)
    resolved = resolve_architecture_improvement_pointer(fixture, reference)
    recovered = resolve_architecture_improvement_pointer(fixture, reference)
    errors = {}
    try:
        resolve_architecture_improvement_pointer(fixture, {**reference,
            "detail_ref": {**reference["detail_ref"], "sha256": "0" * 64}})
    except ValueError as exc:
        errors["wrong_hash"] = str(exc)
    foreign, foreign_state, _, _, _ = _r9_current_finite_fixture("r9-pointer-foreign-", pointer_goal=True)
    try:
        resolve_architecture_improvement_pointer(foreign, reference)
    except ValueError as exc:
        errors["foreign_head"] = str(exc)
    detail_path = fixture / reference["detail_ref"]["path"]
    detail_bytes = detail_path.read_bytes()
    try:
        detail_path.unlink()
        try:
            resolve_architecture_improvement_pointer(fixture, reference)
        except ValueError as exc:
            errors["missing_detail"] = str(exc)
    finally:
        with detail_path.open("xb") as stream:
            stream.write(detail_bytes)
    after = _r8_finite_tree(fixture)
    valid = (public.get("status") == "pass" and bool(resolved.get("action_targets"))
        and resolved["pointer_id"] == reference["pointer_id"]
        and all(row["path"] in material["current_source_fingerprints"] and row["source_fingerprint"] == material["current_source_fingerprints"][row["path"]] for row in resolved["action_targets"]))
    common = {"args": {"root": str(fixture), "pointer_ref": reference},
        "result": {"public_batch": public, "resolved_original_pointer": resolved,
                   "original_parent_path": parent.parent_receipt_path, "negative_observations": errors,
                   "actual_accepted_head_fingerprint": state.head.fingerprint,
                   "actual_foreign_head_fingerprint": foreign_state.head.fingerprint},
        "rejected": set(errors) == {"wrong_hash", "foreign_head", "missing_detail"},
        "rejection": json.dumps(errors, sort_keys=True), "read_only": before == after,
        "recovered": recovered == resolved and resolve_architecture_improvement_pointer(fixture, reference) == resolved,
        "authority": bool(material["receipts"]) and state.head.fingerprint != foreign_state.head.fingerprint}
    return {"pointer:accepted_current": {**common, "valid": valid},
            "pointer:wrong_hash_or_head": {**common, "valid": valid and set(errors) == {"wrong_hash", "foreign_head", "missing_detail"}}}


def run_r8_functional_case(root, case_name):
    """Execute once per actual context and derive checks from measured behavior."""
    record = next((row for row in _R8_CASES + _R9_CASES if row[2] == case_name), None)
    if record is None:
        raise NativeCaseProtocolError("unknown R8 production functional case")
    name, _, _, path, symbol, spec_path, _, contexts = record
    responsibility = "responsibility:" + ("r9" if record in _R9_CASES else "r8") + ":" + name
    semantics = load_r8_hard_semantics(root, responsibility, spec_path)
    if name == "normal-task-context":
        observations = _r9_normal_task_context_observations(root)
    elif name == "finite-growth-observation":
        observations = _r9_growth_observations(root)
    elif name == "pointer-detail-navigation":
        observations = _r9_pointer_detail_observations(root)
    elif name == "affected-native-selection":
        observations = {contexts[0]: _r8_affected_owner_observations(root)}
    elif name == "public-functional-read":
        observations = _r8_public_read_observations(root)
    else:
        observations = _r8_comparison_observations(root)
    if set(observations) != set(contexts):
        raise NativeCaseProtocolError("actual functional input contexts differ from contract")
    checks = []
    for context in contexts:
        actual = observations[context]
        effects_valid = actual.get("effects_valid", actual["read_only"])
        conditions = {
            "accepted_inputs": actual["valid"], "rejected_inputs": actual["rejected"],
            "outputs": actual["valid"], "terminal_states": actual["valid"],
            "state_transitions": effects_valid, "field_transitions": effects_valid,
            "protected_errors": actual["rejected"], "recovery": actual["recovered"],
            "side_effects": effects_valid, "order": actual["valid"] and actual["rejected"],
            "retry": effects_valid, "timeout": effects_valid, "cancellation": effects_valid,
            "progress": actual["valid"], "fairness": effects_valid, "permissions": actual["authority"],
            "authority": actual["authority"], "parent_interfaces": actual["valid"],
            "child_interfaces": actual["valid"], "intent": actual["valid"],
            "behavior_commitments": actual["valid"], "oracles": actual["valid"] and actual["rejected"],
            "evidence_obligations": actual["authority"],
        }
        for hard, expected in semantics.items():
            observed = {"actual_production_result": actual["result"], "condition_met": conditions[hard],
                        "actual_rejected_input_error": actual["rejection"], "owned_tree_unchanged": actual["read_only"], "bounded_effects_valid": effects_valid}
            if expected.get("mode") == "not_applicable":
                observed["not_applicable"] = expected["reason"]
                observed["bounded_function"] = path + "#" + symbol
            checks.append({"check_id": "semantic-check:" + responsibility + ":" + hard + ":" + context,
                "responsibility_id": responsibility, "hard_dimension_id": hard, "input_class_id": context,
                "args": actual["args"], "observed": observed, "expected": expected,
                "status": "pass" if conditions[hard] else "blocked"})
    return checks

def load_r8_hard_semantics(root, responsibility_id, spec_path):
    """Read independent normative content, never substitute model constants."""
    from .model_path_quality import HARD_SEMANTIC_DIMENSIONS
    from .native_case_protocol import _reject_duplicate_json_keys
    blocks = re.findall(r"```flowguard-r8-hard-semantics\s*\n(.*?)\n```", (Path(root) / spec_path).read_text(encoding="utf-8"), re.S)
    found = []
    for block in blocks:
        payload = json.loads(block, object_pairs_hook=_reject_duplicate_json_keys)
        if not isinstance(payload, dict):
            raise NativeCaseProtocolError("normative hard semantics must be an object")
        if responsibility_id in payload:
            found.append(payload[responsibility_id])
    if len(found) != 1 or not isinstance(found[0], dict) or set(found[0]) != set(HARD_SEMANTIC_DIMENSIONS):
        raise NativeCaseProtocolError("independent normative semantics missing/ambiguous: " + responsibility_id)
    return found[0]


def build_r8_architecture_declaration(root, source):
    """Export shared finite Source inventory and owner-specific original cases once."""
    from .implementation_inventory import SoftwareBoundary, ImplementationFileDisposition, build_implementation_surface_inventory, implementation_surface_key
    from .implementation_inventory_python import discover_python_implementation_surfaces, PYTHON_AST_IMPLEMENTATION_ADAPTER_ID, _collect_node_specs
    from .implementation_blueprint import ModelImplementationBinding, SemanticSpecReference, OracleReference, review_model_implementation_bindings
    from .model_path_quality import HARD_SEMANTIC_DIMENSIONS, ARCHITECTURE_HARD_DIMENSION_PROJECTION, ArchitectureResponsibilityFact, derive_retained_elements
    from .model_test_alignment import CodeContract
    from .native_case_protocol import NativeModelCaseContract, ARCHITECTURE_MATERIAL_SCHEMA, parse_native_architecture_material
    from .source_identity import functional_source_fingerprint
    root = Path(root).resolve()
    inventory, manifest = _r9_functional_inventory(root)
    r9_codes = {row.code_contract_id: row for row in r9_functional_code_contracts()}
    surfaces = {(surface.path, surface.symbol): surface for surface in inventory.surfaces}
    bindings, specs, oracles, codes, own_contracts, own_facts, contexts = [], [], [], [], [], [], []
    all_refs = {row["path"]: row["source_fingerprint"] for row in source.source_refs}
    all_refs.update({row["path"]: row["sha256"] for row in manifest})
    facts = dict(source.model_facts)
    blocks = list(facts["function_blocks"])
    groundings = dict(source.element_groundings)
    for record in _R8_CASES + _R9_CASES:
        name, model, case_name, path, symbol, spec_path, obligation, inputs = record
        namespace = "r9" if record in _R9_CASES else "r8"
        responsibility_id = "responsibility:" + namespace + ":" + name
        semantics = load_r8_hard_semantics(root, responsibility_id, spec_path)
        element = "function-block:" + namespace + ":" + name
        surface = surfaces.get((path, symbol))
        if surface is None or surface.disposition != "model_implementation":
            raise NativeCaseProtocolError("required actual production function absent: " + path + "#" + symbol)
        spec_fp = functional_source_fingerprint(root, spec_path)
        model_path = ".flowguard/models/owners/" + model + "/model.py"
        runner_path = ".flowguard/verification/owners/" + model + "/run_checks.py"
        model_source_fp = functional_source_fingerprint(root, model_path)
        runner_fp = functional_source_fingerprint(root, runner_path)
        all_refs.update({spec_path: spec_fp, model_path: model_source_fp, runner_path: runner_fp})
        obligation_id = "obligation:" + namespace + ":" + obligation
        code = r9_codes["code-contract:r9:" + name] if namespace == "r9" else CodeContract(code_contract_id="code-contract:r8:" + name, path=path, symbol=symbol, implements_obligations=(obligation_id,), relation_code_obligation_ids=(obligation_id,), external_inputs=("current independently bound " + name + " inputs",), external_outputs=({"public-functional-read": "outcome:r8:task_functional_state_visible", "contextual-architecture-comparison": "outcome:r8:related_overlap_and_gap_visible", "affected-native-selection": "outcome:r8:only_affected_native_execution_required"}[name],), state_reads=("selected current model inputs and exact independent evidence",), state_writes=(), side_effects=(), error_paths=("malformed, unknown or unauthenticated inputs remain rejected",), required=True)
        codes.append(code)
        case_id = ("native-scenario:" if model == "authoritative_model_system" else "case:") + model + ":" + case_name
        contract = NativeModelCaseContract(owner_id="model:" + model, source_case_id=case_id, case_kind="good", callable_ref=path + "#" + symbol, result_selector="scenario:" + case_name, expected_status="pass", expected_observed_status="ok", covered_dimensions=GOOD_DIMENSIONS, oracle_member_ids=tuple("model:" + model + ":" + case_id + ":" + dimension for dimension in sorted(GOOD_DIMENSIONS)), evidence_scope="implementation_boundary", input_contract_fingerprint=os.environ.get("FLOWGUARD_INPUT_FINGERPRINT", "") if model == source.model_id else "", oracle_content_fingerprint="")
        groups = tuple((dimension, json.dumps({"schema": "flowguard.architecture_hard_semantics.v1", "dimension": dimension, "hard_dimensions": {hard: semantics[hard] for hard in dimensions}, "input_class_ids": list(inputs)}, sort_keys=True, separators=(",", ":"))) for dimension, dimensions in ARCHITECTURE_HARD_DIMENSION_PROJECTION.items())
        spec_id = "semantic-spec:" + namespace + ":" + name
        oracle_id = "model:" + model + ":" + case_id + ":input"
        spec = SemanticSpecReference(spec_id, "spec-owner:" + namespace + ":" + name, spec_path, spec_fp, spec_path, "spec-owner:" + namespace + ":" + name, spec_fp, (element,), tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), groups, provenance_fingerprints=((spec_path, spec_fp),))
        oracle = OracleReference(oracle_id, "model:" + model, runner_path, runner_fp, runner_path, "model:" + model, runner_fp, (element,), tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), groups)
        binding = ModelImplementationBinding("binding:" + namespace + ":" + name, element, (obligation_id,), surface.surface_id, "implements", code.code_contract_id, path, "model:" + model, surface.content_fingerprint, (spec_id,), (oracle_id,), required_dimensions=tuple(ARCHITECTURE_HARD_DIMENSION_PROJECTION), owner_contract_fingerprint=fingerprint_payload(code.to_dict()), test_evidence_ids=("test:" + namespace + ":" + case_id,), test_evidence_fingerprints=(("test:" + namespace + ":" + case_id, runner_fp),))
        specs.append(spec); oracles.append(oracle); bindings.append(binding)
        blocks.append({"id": element, "name": symbol, "implementation_path": path})
        groundings[element] = {"kind": "actual_production_function", "symbol": symbol, "source_ref": path, "source_fingerprint": surface.content_fingerprint}
        if model == source.model_id:
            own_contracts.append(contract)
            refs = tuple({"path": ref, "source_fingerprint": fp} for ref, fp in sorted({path: surface.content_fingerprint, spec_path: spec_fp, model_path: model_source_fp, runner_path: runner_fp}.items()))
            own_facts.append(ArchitectureResponsibilityFact(responsibility_id, model, (element,), "model:" + model, inventory.boundary.boundary_id, "layer:" + namespace + ":bounded-functional-consumer", tuple(inputs), semantics, surface.surface_id, surface.structure_fingerprint, code.code_contract_id, fingerprint_payload(code.to_dict()), (spec_id,), (spec.fingerprint,), (oracle_id,), binding.fingerprint, refs))
            contexts.extend({"responsibility_id": responsibility_id, "hard_dimension_id": hard, "input_class_id": context, "code_contract_id": code.code_contract_id, "semantic_spec_id": spec_id, "oracle_id": oracle_id, "source_case_ids": [case_id]} for context in inputs for hard in HARD_SEMANTIC_DIMENSIONS)
    facts["function_blocks"] = blocks
    facts["responsibilities"] = [fact.to_dict() for fact in own_facts]
    report = review_model_implementation_bindings(inventory, required_model_element_ids=tuple(binding.model_element_id for binding in bindings), bindings=tuple(bindings), semantic_specs=tuple(specs), oracles=tuple(oracles))
    if not report.ok:
        raise NativeCaseProtocolError("six-function implementation bindings are incomplete: " + str(report.to_dict()["findings"]))
    refs = tuple({"path": path, "source_fingerprint": fp} for path, fp in sorted(all_refs.items()))
    declared = replace(source, source_refs=refs, model_facts=facts, element_groundings=groundings, declared_element_ids=tuple(item for item, _ in derive_retained_elements(facts)))
    material = {"schema": ARCHITECTURE_MATERIAL_SCHEMA, "model_id": source.model_id,
        "source_refs": list(refs), "observed_source_inputs": [{"path": row["path"], "sha256": row["source_fingerprint"]} for row in refs],
        "resolved_manifest_rows": manifest, "implementation_inventory": inventory.to_dict(), "binding_report": report.to_dict(),
        "code_contracts": [code.to_dict() for code in codes], "native_case_contracts": [contract.to_dict() for contract in own_contracts],
        "responsibility_context_rows": contexts}
    material = parse_native_architecture_material(material)
    _verify_architecture_declaration(declared, material)
    return NativeArchitectureDeclaration(declared, material)

def _verify_architecture_declaration(source, material):
    """Keep independently exported materials and graph responsibilities joined."""
    from .model_path_quality import ArchitectureResponsibilityFact
    if source.model_id != material["model_id"]:
        raise NativeCaseProtocolError("architecture material belongs to a foreign model")
    facts = {row["responsibility_id"]: ArchitectureResponsibilityFact.from_dict(row)
             for row in source.model_facts.get("responsibilities", ())}
    rows = material["responsibility_context_rows"]
    if {row["responsibility_id"] for row in rows} != set(facts):
        raise NativeCaseProtocolError("architecture material responsibility denominator mismatch")
    for row in rows:
        fact = facts[row["responsibility_id"]]
        if (row["input_class_id"] not in fact.applicable_input_class_ids
                or row["code_contract_id"] != fact.owner_code_contract_id
                or row["semantic_spec_id"] not in fact.semantic_spec_ids
                or row["oracle_id"] not in fact.oracle_ids):
            raise NativeCaseProtocolError("architecture context differs from declared responsibility")
    from .model_path_quality import HARD_SEMANTIC_DIMENSIONS
    expected = {(fact.responsibility_id, context, dimension)
                for fact in facts.values() for context in fact.applicable_input_class_ids
                for dimension in HARD_SEMANTIC_DIMENSIONS}
    actual = {(row["responsibility_id"], row["input_class_id"], row["hard_dimension_id"]) for row in rows}
    if expected != actual:
        raise NativeCaseProtocolError("architecture context does not cover declared responsibility")


def _executed_architecture_checks(case_id, raw):
    """Consume actual case observations; absence never creates passing checks."""
    material = _ARCHITECTURE_MATERIAL.get()
    if material is None:
        return []
    contexts = [row for row in material["responsibility_context_rows"] if case_id in row["source_case_ids"]]
    if not contexts:
        return []
    found = []
    def visit(value):
        if isinstance(value, Mapping):
            if "semantic_checks" in value:
                if value["semantic_checks"]:
                    found.append(value["semantic_checks"])
            for key, item in value.items():
                if key != "semantic_checks":
                    visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
    visit(raw)
    if not found or not isinstance(found[0], list) or any(row != found[0] for row in found):
        raise NativeCaseProtocolError("required actual architecture checks missing/inconsistent: " + case_id)
    rows = found[0]
    expected = {(row["responsibility_id"], row["hard_dimension_id"], row["input_class_id"]) for row in contexts}
    from .model_path_quality import ArchitectureResponsibilityFact
    declaration = _DECLARED_SOURCE.get()
    facts = {row["responsibility_id"]: ArchitectureResponsibilityFact.from_dict(row)
             for row in declaration["model_facts"]["responsibilities"]}
    actual = set()
    fields = {"check_id", "responsibility_id", "hard_dimension_id", "input_class_id",
              "args", "observed", "expected", "status"}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != fields:
            raise NativeCaseProtocolError("semantic check fields must be exact")
        key = row["responsibility_id"], row["hard_dimension_id"], row["input_class_id"]
        if key not in expected or key in actual:
            raise NativeCaseProtocolError("semantic check foreign/duplicate hard context")
        actual.add(key)
        if row["check_id"] != "semantic-check:" + ":".join(key):
            raise NativeCaseProtocolError("semantic check identity mismatch")
        if row["expected"] != facts[key[0]].hard_semantics[key[1]]:
            raise NativeCaseProtocolError("semantic check differs from independent declared semantics")
        if row["status"] not in {"pass", "blocked"} or any(
                not isinstance(row[name], Mapping) or not row[name] for name in ("args", "observed")):
            raise NativeCaseProtocolError("semantic check lacks actual args/observation/status")
    if expected != actual:
        raise NativeCaseProtocolError("semantic checks do not cover exact hard contexts")
    return rows

from .native_case_protocol import (
    CASE_DIMENSIONS,
    GOOD_DIMENSIONS,
    NATIVE_CASE_RESULT_SCHEMA,
    NativeModelCaseResult,
    NativeCaseProtocolError,
    fingerprint_payload,
)
from .native_case_mapping import (
    NativeCaseMappingError,
    NativeCaseMappingRegistry,
    load_native_case_mapping,
)
from .review import OracleReviewResult, ScenarioReviewReport
from .scenario import ScenarioRun


_CASE_KEYS = ("scenario_name", "source_case_id", "case_id", "case", "name", "id")
_STATUS_KEYS = ("status", "observed_status", "decision", "outcome")
_OK_KEYS = ("ok", "passed", "match", "observed_ok")
_CASE_CONTAINERS = {
    "results",
    "case_results",
    "cases",
    "known_bad_proofs",
    "checks",
    "reviews",
    "evidence_runs",
}

# These are the only owners whose native leaf identity has a distinct wire
# namespace.  The distinction is part of the checked-in case mapping: it is
# not inferred from a report count or a similar-looking case name.
_SCENARIO_OWNERS = frozenset(
    {
        "authoritative_model_system",
        "adversarial_scenario_synthesis",
        "architecture_reduction",
        "hierarchical_model_mesh",
        "mesh_target_split_derivation",
        "skill_kernel_modularization",
        "structure_refactor_mesh",
        "test_evidence_mesh",
        "validation_evidence_gates",
    }
)
_BENCHMARK_OWNER = "bounded_system_composition_benchmark"
# These five owners are the finite scenario producers whose report is now
# converted to the typed native tuple by the owner itself.  They deliberately
# bypass the historical capture bridge below: stdout, globals, and an
# existing JSON file are never evidence for these owners.
_STRICT_NATIVE_OWNER_IDS = frozenset(
    {
        "architecture_reduction",
        "hierarchical_model_mesh",
        "mesh_target_split_derivation",
        "structure_refactor_mesh",
        "test_evidence_mesh",
    }
)
_SUMMARY_CASE_NAMES = frozenset(
    {
        "status", "result", "decision", "outcome", "observed", "expected", "evidence",
        # Wrapper-only projections.  These labels are emitted by a report
        # formatter or by the generic model serializer, not by a registered
        # native leaf.  Keeping them out of the leaf inventory prevents a
        # summary line from becoming a foreign case while preserving the raw
        # transcript in ``native-source.json``.
        "anonymous",
        "model_report",
        "scenario_review",
        "model-miss diagnostic projection",
        # Public benchmark runner summary; the twelve family/variant rows are
        # the executable leaves and this aggregate label has no registry
        # binding of its own.
        "bounded_system_benchmark",
    }
)

# Primary Path Authority calls the same typed reviewer once for the complete
# plan and once for each named counterexample.  The plan id is the stable
# producer selector; keeping this finite table here lets the native bridge
# project the outer assertion without treating a report's finding list as a
# set of guessed leaves.
_PRIMARY_PATH_PLAN_CASES = {
    "complete-primary-path-authority": ("complete_plan", True),
    "broken-a-failed-b-success": ("broken_a_failed_b_success", False),
    "broken-old-field-fallback": ("broken_old_field_fallback", False),
    "broken-manual-recovery-auto-invoked": ("broken_manual_recovery_auto_invoked", False),
    "broken-two-paths-same-exact-intent": ("broken_two_paths_same_exact_intent", False),
    "broken-missing-candidate-inventory": ("broken_missing_candidate_inventory", False),
    "broken-stale-material-evidence": ("broken_stale_material_evidence", False),
}

# Existing named producer callbacks used by the verification owners.  This is
# an allow-list, not reflective discovery: native_main wraps only callbacks
# that are explicitly part of the owner contract and captures each call once.
_OWNER_CAPTURE_FUNCTIONS: Mapping[str, tuple[str, ...]] = {
    "code_boundary_conformance": ("run_rollout_review",),
    "contract_source_audit": ("run_rollout_review",),
    "runtime_gateway_adoption": ("run_inventory_review",),
    "model_test_code_alignment": (
        "run_rollout_review",
        "run_evidence_projection_review",
        "run_delegated_helper_graph_review",
        "run_native_pytest_contract",
    ),
    "ai_entry_surface_reduction": ("run_case",),
    "harden_ui_real_surface_validation": ("run_case",),
    "ui_human_operability_gate": ("run_case",),
    "ui_flow_structure_skill": ("run_sequence", "run_rejected_release_sequence"),
    "user_facing_model_diagrams": ("run_case", "print_case"),
    "codex_skill_satellites": (
        "_run",
        "_accepted",
        "_rejected_with",
        "_stale_rejected",
        "_print_case",
    ),
    "work_context": ("run_model_checks",),
    "model_maturation_loop": ("run_r6_architecture_review", "run_r8_architecture_review", "run_r9_architecture_review"),
    # The strategy surface was contracted to one canonical optimization
    # review.  Its child reports are invoked through the owner module (and
    # emitted as the explicit structured ``native_cases`` rows), not through
    # globals in this bridge.  Keeping the retired callback names here would
    # make the current runtime advertise a removed public vocabulary while
    # adding no capture coverage.
    "development_process_strategy": (),
    "maintenance_obligation_memory": ("run_workflow_suite",),
    "model_topology_hazard_review": ("run_workflow_suite",),
    "state_closure_gate": ("run_workflow_suite",),
    "primary_path_authority": ("review_primary_path_authority",),
    "behavior_commitment_ledger": (
        "review_behavior_commitment_ledger",
        "audit_flowguard_behavior_commitment_source_inventory",
    ),
    "model_miss_review": (
        "run_checks",
        "_check_diagnostic_projection",
        "_native_case_projection",
    ),
    "plan_detailing_compiler": ("run_plan_detailing_review",),
    "template_public_release": ("run_checks",),
    "harden_ui_content_visibility_validation": (
        "review_model_test_alignment",
        "review_test_mesh",
        "review_risk_evidence_ledger",
        "contract_exhaustion_report",
    ),
    "development_process_flow": (
        "review_scenarios",
        "run_author_shadow_sync_model",
        "run_implementation_admission_model",
        "run_release_identity_model",
        "run_path_quality_lifecycle_model",
    ),
    "default_replacement_field_lifecycle": (
        "review_field_lifecycle",
        "ui_reader_handoff_contract",
        "product_language_authority_field_contract",
    ),
    "existing_model_preflight": (
        "review_existing_model_preflight",
        "run_exact_owner_identity_review",
    ),
    "minimum_valuable_model_entry": (
        "run_narrow_entry_projection_review",
        "run_ordinary_entry_review",
        "run_rejection_examples",
    ),
    "guidance_compression": (
        "review_prompt_bundles",
        "run_real_load_graph_budget_review",
        "architecture_reduction_report",
        "development_process_report",
    ),
    "maintenance_obligation_memory": (
        "build_maintenance_obligation_report",
        "review_risk_evidence_ledger",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "model_topology_hazard_review": (
        "review_topology_hazards",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "state_closure_gate": (
        "review_state_closure",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "self_maintenance_mesh": (
        "review_flowguard_self_maintenance",
        "review_route_admission",
        "run_narrow_route_admission_review",
        "run_plane_upgrade_contract_binding",
        "run_receipt_parent_review",
        "run_route_profile_review",
        "run_route_topology_review",
        "run_semantic_mesh_verification_review",
        "run_skill_self_governance",
        "run_workflow_suite",
    ),
}


@dataclass(frozen=True)
class _CapturedCall:
    """One exact callback return plus callbacks nested inside it."""

    function_name: str
    args: tuple[Any, ...]
    kwargs: Mapping[str, Any]
    result: Any
    nested: tuple[Any, ...] = ()
    parent_function: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            # Keep the immutable call receipt bounded.  The typed result is
            # projected into ``cases`` separately; serialising a full model
            # trace here used to duplicate every transition and could create
            # hundreds of megabytes for one owner.  The summary retains
            # enough shape/fingerprint information to audit the producer
            # without becoming a second result authority.
            "args": _bounded_source_summary(self.args),
            "kwargs": _bounded_source_summary(dict(self.kwargs)),
            "result": _bounded_source_summary(self.result),
            "nested": [_bounded_source_summary(item) for item in self.nested],
            "parent_function": self.parent_function,
        }


_SOURCE_SEQUENCE_FIELDS = (
    "results",
    "case_results",
    "cases",
    "known_bad_proofs",
    "checks",
    "reviews",
    "evidence_runs",
    "traces",
    "final_states",
    "violations",
    "evidence",
)
_SOURCE_SCALAR_FIELDS = (
    "scenario_name",
    "name",
    "status",
    "decision",
    "diagnostic_status",
    "owner_decision",
    "observed_status",
    "ok",
    "expected_ok",
    "observed_ok",
    "closure_licensed",
)


def _bounded_source_summary(value: Any, *, depth: int = 0) -> Any:
    """Return a deterministic, small summary for a captured call receipt.

    This function is used only for ``structured_reports`` in
    ``native-source.json``.  Behavioural leaf projection continues to inspect
    the live typed return object through the explicit projectors above.  A
    bounded summary avoids duplicating large traces while retaining the
    producer name, scalar verdicts, collection sizes, and a short sample of
    mapping/sequence keys for diagnosis.
    """

    if depth > 3:
        return {"type": type(value).__name__}
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 256:
            return value[:256] + "…"
        return value
    if isinstance(value, Mapping):
        keys = sorted(str(key) for key in value)[:24]
        return {
            "type": "mapping",
            "keys": keys,
            "size": len(value),
            "scalars": {
                str(key): _bounded_source_summary(value[key], depth=depth + 1)
                for key in keys
                if key in value and isinstance(value[key], (str, int, float, bool))
            },
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        return {
            "type": type(value).__name__,
            "size": len(items),
            "sample": [
                _bounded_source_summary(item, depth=depth + 1)
                for item in items[:4]
            ],
        }
    summary: dict[str, Any] = {"type": type(value).__name__}
    for field_name in _SOURCE_SCALAR_FIELDS:
        try:
            field_value = getattr(value, field_name)
        except AttributeError:
            continue
        if isinstance(field_value, (str, int, float, bool)) or field_value is None:
            summary[field_name] = _bounded_source_summary(field_value, depth=depth + 1)
    for field_name in _SOURCE_SEQUENCE_FIELDS:
        try:
            field_value = getattr(value, field_name)
        except AttributeError:
            continue
        if isinstance(field_value, (str, bytes, Mapping)):
            continue
        try:
            size = len(field_value)
        except (TypeError, AttributeError):
            continue
        summary[f"{field_name}_count"] = size
    return summary


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _valid_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _case_id(raw: Mapping[str, Any]) -> str:
    for key in _CASE_KEYS:
        value = _valid_text(raw.get(key))
        if value:
            return value
    return ""


def _status(raw: Mapping[str, Any], *, ok: bool) -> str:
    # ``observed_status`` is the model's actual result (for example
    # ``violation``), while ``status`` may be the wrapper's oracle verdict
    # (for example ``expected_violation_observed``).  Keep the two distinct.
    for key in ("observed_status", "status", "decision", "outcome"):
        value = _valid_text(raw.get(key))
        if value:
            return value
    if raw.get("observed_ok") is False:
        return "violation"
    return "pass" if ok else "fail"


def _observed_ok(raw: Mapping[str, Any]) -> bool:
    for key in _OK_KEYS:
        value = raw.get(key)
        if isinstance(value, bool):
            return value
        if key == "match" and isinstance(value, str):
            return value.strip().casefold() in {"yes", "true", "pass", "ok"}
    return False


def _finding_codes(raw: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    # Scenario owners expose invariant labels as ``observed_violation_names``
    # on the typed ScenarioRun.  They are findings for the *model* oracle even
    # when the enclosing check passes because the violation was expected.  Do
    # not drop them while projecting the report into the native envelope.
    for key in (
        "finding_codes",
        "expected_finding_codes",
        "violations",
        "observed_finding_codes",
        "observed_violation_names",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            value = (value,)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                text = _valid_text(item)
                if text and text not in values:
                    values.append(text)
    return tuple(values)


def _is_case_mapping(raw: Mapping[str, Any]) -> bool:
    identifier = _case_id(raw)
    if not identifier:
        return False
    return any(key in raw for key in (*_OK_KEYS, *_STATUS_KEYS, "expected_ok"))


def _collect_json_cases(value: Any, found: list[dict[str, Any]], *, parent_key: str = "") -> None:
    if isinstance(value, Mapping):
        if _is_case_mapping(value):
            row = dict(value)
            row.setdefault("projection_source", "json")
            row.setdefault("projection_priority", 20)
            found.append(row)
        elif parent_key and isinstance(value.get("ok"), bool):
            # Some composite owner reports intentionally keep their child
            # reports under a named section rather than repeating a case id.
            # The section itself is an observed aggregate result; its raw
            # payload remains linked by fingerprint and is never treated as a
            # leaf contract by the strict verifier.
            found.append({
                "name": parent_key,
                "ok": value.get("ok"),
                "status": value.get("status", "pass" if value.get("ok") else "fail"),
                "finding_codes": value.get("finding_codes", value.get("findings", ())),
                "projection_source": "json",
                "projection_priority": 20,
            })
        for key, child in value.items():
            if isinstance(child, (Mapping, list, tuple)):
                _collect_json_cases(child, found, parent_key=str(key))
            elif parent_key in {"known_bad", "known_bad_proofs"} and isinstance(child, str):
                found.append({
                    "name": f"{parent_key}:{key}",
                    "status": child,
                    "ok": child.casefold() in {"blocked", "pass", "passed", "ok"},
                    "projection_source": "json",
                    "projection_priority": 20,
                })
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_json_cases(child, found, parent_key=parent_key)


def _structured_to_payload(value: Any) -> Any:
    """Serialize one captured native return without reducing it to a marker.

    Native owners historically print a human report and return only an exit
    code.  ``native_main`` now captures the structured object at the same call
    site, but keeps the conversion deliberately small: a typed ``to_dict``
    method is authoritative, mappings/sequences are copied recursively, and
    other values are retained only as a scalar representation.  This helper
    never invokes a second producer or reconstructs an oracle from text.
    """

    # Access the typed projection directly.  Keeping this as a fixed protocol
    # lookup (rather than a caller-selected attribute name) is important for
    # the self-model: the runner may project only the four registered report
    # families and must not become a reflective case extractor.
    try:
        to_dict = value.to_dict
    except AttributeError:
        to_dict = None
    if callable(to_dict):
        try:
            return _structured_to_payload(to_dict())
        except (TypeError, ValueError, MemoryError, RecursionError):
            # A malformed or oversized optional projection must not make the
            # owner look like it produced a passing case.  Do not call repr()
            # here: dataclass reprs can recursively walk a full self-model and
            # exhaust the producer process before the immutable source
            # envelope is written.  The bounded structural summary remains
            # linked in that envelope for diagnosis.
            return _bounded_source_summary(value)
    if isinstance(value, Mapping):
        return {
            str(key): _structured_to_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_structured_to_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Unknown objects are kept as a bounded shape summary.  A raw repr is not
    # a stable evidence surface and can expand without limit for nested model
    # graphs.
    return _bounded_source_summary(value)


def _path_quality_report_payload(candidate: Any) -> Mapping[str, Any] | None:
    """Project only a possible executed scenario report, preserving its graph."""

    # Exact types have known projection contracts. Subclasses and compatible
    # custom reports still use the existing projection and payload checks.
    if candidate is None or type(candidate) in (
        bool, int, float, str, ScenarioRun, OracleReviewResult,
    ):
        return None
    if type(candidate) is dict and "results" not in candidate:
        return None
    # The outer dataclass does not enforce its annotated inner types. Only
    # inspect a known graph directly; compatible objects and malformed
    # containers retain the serializer's original fallback/error boundary.
    if (
        type(candidate) is ScenarioReviewReport
        and type(candidate.results) in (list, tuple)
        and all(
            type(row) is OracleReviewResult
            and (
                row.scenario_run is None
                or (
                    type(row.scenario_run) is ScenarioRun
                    and type(row.scenario_run.traces) in (list, tuple)
                    and type(row.scenario_run.final_states) in (list, tuple)
                )
            )
            for row in candidate.results
        )
    ):
        if not candidate.results or not all(
            isinstance(row.scenario_name, str)
            and bool(row.scenario_name.strip())
            and row.scenario_run is not None
            and bool(row.scenario_run.traces)
            and bool(row.scenario_run.final_states)
            for row in candidate.results
        ):
            return None

    payload = _structured_to_payload(candidate)
    if not isinstance(payload, Mapping):
        return None
    report_rows = payload.get("results")
    if not isinstance(report_rows, list) or not report_rows:
        return None
    if not all(
        isinstance(row, Mapping)
        and isinstance(row.get("scenario_name"), str)
        and bool(row.get("scenario_name", "").strip())
        and isinstance(row.get("scenario_run"), Mapping)
        and isinstance(row["scenario_run"].get("traces"), list)
        and bool(row["scenario_run"].get("traces"))
        and isinstance(row["scenario_run"].get("final_states"), list)
        and bool(row["scenario_run"].get("final_states"))
        for row in report_rows
    ):
        return None
    return payload


def _model_run_projection(
    run: Any,
    *,
    name: str,
    wrapper_ok: bool | None = None,
    case_kind: str = "",
    projection_priority: int = 40,
) -> dict[str, Any] | None:
    """Project one already-executed sequence run for an outer oracle.

    ``run_exact_sequence`` returns a rich ``ScenarioRun``.  The outer owner
    helper (``run_sequence``/``print_case``) is the source of the case name and
    expected oracle; the inner run is only the observed model evidence.  This
    keeps an expected violation as a passing *check* while retaining the
    model's actual violation status and names.
    """

    try:
        report = run.model_report
    except AttributeError:
        return None
    if not name:
        try:
            name = _valid_text(run.scenario.name)
        except AttributeError:
            name = ""
    if not name:
        return None
    try:
        report_ok = bool(report.ok)
    except AttributeError:
        report_ok = False
    try:
        violations = tuple(report.violations)
    except AttributeError:
        violations = ()
    finding_codes: list[str] = []
    for violation in violations:
        try:
            value = _valid_text(violation.invariant_name)
        except AttributeError:
            value = ""
        if not value:
            try:
                value = _valid_text(violation.name)
            except AttributeError:
                value = ""
        if value and value not in finding_codes:
            finding_codes.append(value)
    try:
        observed_status = _valid_text(run.observed_status).lower()
    except AttributeError:
        observed_status = "ok" if report_ok else "violation"
    if not observed_status:
        observed_status = "ok" if report_ok else "violation"
    try:
        traces = tuple(run.traces)
    except AttributeError:
        traces = ()
    trace_labels: list[str] = []
    for trace in traces:
        try:
            steps = tuple(trace.steps)
        except AttributeError:
            steps = ()
        for step in steps:
            try:
                label = _valid_text(step.label)
            except AttributeError:
                label = ""
            if label and label not in trace_labels:
                trace_labels.append(label)
    result: dict[str, Any] = {
        "name": name,
        # The outer helper's bool is the declared oracle result.  If it is not
        # available, the inner model report is the only honest fallback.
        "ok": report_ok if wrapper_ok is None else bool(wrapper_ok),
        "observed_status": observed_status,
        "observed_finding_codes": finding_codes,
        "trace_labels": trace_labels,
        "case_kind": case_kind if case_kind in {"good", "bad", "boundary"} else (
            "bad" if not report_ok else "good"
        ),
        "projection_priority": projection_priority,
    }
    return result


def _captured_call_cases(
    call: _CapturedCall,
    *,
    owner_id: str,
) -> list[dict[str, Any]]:
    """Adapt the small set of explicit owner callback return shapes."""

    owner = owner_id.removeprefix("model:")
    name = call.function_name
    result = call.result
    rows: list[dict[str, Any]] = []

    # Preserve the richer typed object before serializing it through the
    # generic JSON collector.  In particular ScenarioRun keeps
    # observed_violation_names on its nested object; flattening first would
    # lose the model finding codes while retaining only the wrapper ``ok``.
    if any(
        hasattr(result, attribute)
        for attribute in ("results", "case_results", "cases")
    ):
        rows = _captured_structured_cases((result,), owner_id=owner_id)
        for row in rows:
            row.setdefault("projection_source", "structured")
            row.setdefault("projection_priority", 50)
        return rows

    # The two rollout-review owners intentionally expose tuple rows.  The
    # tuple shape itself is fixed by their model contract: (name, matched,
    # finding_codes).  Kind/status/dimensions are supplied later by the exact
    # checked-in mapping registry; no name heuristic is used here.
    if isinstance(result, (list, tuple)) and result and all(
        isinstance(item, (list, tuple)) and len(item) == 3 for item in result
    ):
        for item in result:
            case_name = _valid_text(item[0])
            if not case_name or not isinstance(item[1], bool):
                continue
            codes = item[2]
            if isinstance(codes, str):
                codes = (codes,)
            if not isinstance(codes, Sequence) or isinstance(codes, (str, bytes)):
                continue
            normalized_codes = [
                value for value in (_valid_text(code) for code in codes) if value
            ]
            rows.append(
                {
                    "name": case_name,
                    "ok": bool(item[1]),
                    "status": "pass" if item[1] else "fail",
                    # Tuple-based reviewers return the wrapper's oracle match
                    # plus the underlying report finding codes.  The wrapper
                    # bool is therefore not the model status: a matched bad
                    # case is an observed violation, while a matched good
                    # case has no violation codes.  Preserve both layers so a
                    # bad case cannot be flattened into an apparently normal
                    # ``pass`` observation.
                    "observed_status": "violation" if normalized_codes else "ok",
                    "finding_codes": normalized_codes,
                    "projection_priority": 38,
                    "projection_source": "structured",
                }
            )
        return rows

    if name == "review_primary_path_authority" and call.args:
        plan_id = _valid_text(getattr(call.args[0], "plan_id", ""))
        selector = _PRIMARY_PATH_PLAN_CASES.get(plan_id)
        if selector is not None and hasattr(result, "ok"):
            case_name, expected_ok = selector
            observed_ok = bool(getattr(result, "ok", False))
            findings = []
            for finding in tuple(getattr(result, "findings", ()) or ()):
                code = _valid_text(getattr(finding, "code", ""))
                if code and code not in findings:
                    findings.append(code)
            rows.append(
                {
                    "name": case_name,
                    # The owner checks intentionally expect every broken plan
                    # to be rejected.  ``ok`` is therefore the assertion
                    # result, while ``observed_status`` retains the model's
                    # actual authority decision.
                    "ok": observed_ok is expected_ok,
                    "status": "pass" if observed_ok is expected_ok else "fail",
                    "observed_status": "ok" if observed_ok else "violation",
                    "finding_codes": findings,
                    "case_kind": "good" if expected_ok else "bad",
                    "projection_priority": 46,
                    "projection_source": "structured",
                }
            )
        return rows

    # The outer UI flow helper owns the final expected-oracle bool.  Its nested
    # exact sequence report is the model observation and must be consumed once.
    if name in {"run_sequence", "run_rejected_release_sequence"}:
        case_name = _valid_text(call.args[0]) if call.args else ""
        expected_ok = call.kwargs.get("expect_ok")
        kind = "bad" if name == "run_rejected_release_sequence" else (
            "bad" if expected_ok is False else "good"
        )
        for child in call.nested:
            if isinstance(child, _CapturedCall) and child.function_name in {
                "run_exact_sequence",
                "run_exact_workflow_case",
            }:
                row = _model_run_projection(
                    child.result,
                    name=case_name,
                    wrapper_ok=bool(result) if isinstance(result, bool) else None,
                    case_kind=kind,
                    projection_priority=45,
                )
                if row is not None:
                    row.setdefault("projection_source", "structured")
                    if name == "run_rejected_release_sequence":
                        # The inner workflow is allowed to remain invariant
                        # clean while the release claim is rejected.  For
                        # this explicitly named bad boundary, the outer
                        # rejection is the observed violation consumed by
                        # the mapping; do not flatten it into a green model
                        # status merely because no lower invariant fired.
                        row["observed_status"] = "violation" if bool(result) else "ok"
                    rows.append(row)
                break
        return rows

    # Three formal owners expose one named positive workflow check together
    # with a finite suite of deliberately broken workflows.  The outer
    # ``run_workflow_suite`` boolean is an aggregate (and is false whenever a
    # broken workflow is correctly rejected), so it cannot stand in for the
    # positive leaf.  Project the exact positive sequence from its nested
    # typed result and leave the formal suite's bad leaves to the structured
    # report projector below.
    if name == "run_workflow_suite" and owner in {
        "maintenance_obligation_memory",
        "model_topology_hazard_review",
        "state_closure_gate",
    }:
        positive_names = {
            "maintenance_obligation_memory": "correct_maintenance_obligation_memory",
            "model_topology_hazard_review": "correct_topology_hazard_review",
            "state_closure_gate": "correct_state_closure_gate",
        }
        positive_name = positive_names[owner]
        for child in call.nested:
            if not isinstance(child, _CapturedCall) or child.function_name != "run_exact_sequence":
                continue
            exact = child.result
            report = getattr(exact, "model_report", None)
            observed_ok = bool(getattr(report, "ok", False))
            final_states = tuple(getattr(exact, "final_states", ()) or ())
            final_ok = len(final_states) == 1
            if final_ok:
                final_state = final_states[0]
                if owner == "maintenance_obligation_memory":
                    final_ok = getattr(final_state, "broad_claim", None) == "full_accepted"
                elif owner == "model_topology_hazard_review":
                    final_ok = getattr(final_state, "final_claim", None) == "full"
                else:
                    final_ok = getattr(final_state, "final_claim", None) == "full"
            exact_ok = observed_ok and final_ok
            rows.append(
                {
                    "name": positive_name,
                    "ok": exact_ok,
                    "status": "pass" if exact_ok else "fail",
                    "observed_status": "ok" if observed_ok else "violation",
                    "finding_codes": [
                        _valid_text(getattr(item, "code", ""))
                        for item in tuple(getattr(report, "findings", ()) or ())
                        if _valid_text(getattr(item, "code", ""))
                    ],
                    "case_kind": "good",
                    "projection_priority": 60,
                    "projection_source": "structured",
                }
            )
            break
        return rows

    # A few model-only owners invoke the exact sequence helper directly (no
    # named outer wrapper).  ``run_exact_workflow_case`` is slightly
    # different: its first argument is the stable native case name while the
    # nested ``run_exact_sequence`` carries only the model workflow name.
    # Keep that caller-provided name (and remove the one explicit blueprint
    # display prefix) so an aggregate's children cannot collapse into one
    # anonymous ScenarioRun row.
    if name in {"run_exact_sequence", "run_exact_workflow_case"}:
        case_name = ""
        wrapper_ok: bool | None = None
        case_kind = ""
        if name == "run_exact_workflow_case":
            case_name = _valid_text(call.args[0]) if call.args else ""
            if case_name.startswith("bounded blueprint path qualified: "):
                case_name = case_name.removeprefix("bounded blueprint path qualified: ").strip()
            if isinstance(result, bool):
                wrapper_ok = result
            case_kind = "good"
            # ``run_exact_workflow_case`` is the named native producer for a
            # bounded positive case.  Its contract intentionally returns the
            # final oracle as a plain bool, so there is no typed model report
            # for ``_model_run_projection`` to unwrap.  Preserve the exact
            # caller-provided case name as a native leaf instead of silently
            # dropping the evidence.  This is deliberately limited to this
            # explicit helper and does not infer cases from arbitrary bools.
            if case_name and isinstance(result, bool):
                rows.append(
                    {
                        "name": case_name,
                        "ok": result,
                        "status": "pass" if result else "fail",
                        "observed_status": "ok" if result else "violation",
                        "case_kind": "good",
                        "projection_priority": 44,
                        "projection_source": "structured",
                    }
                )
                return rows
        row = _model_run_projection(
            result,
            name=case_name,
            wrapper_ok=wrapper_ok,
            case_kind=case_kind,
            projection_priority=44,
        )
        if row is not None:
            row.setdefault("projection_source", "structured")
            rows.append(row)
        return rows

    # User-facing diagrams use print_case(name, run, expected_ok) as the named
    # oracle while run_case itself has no name.  The report is already present
    # in the call arguments and is never re-executed.
    if name == "print_case" and call.args:
        case_name = _valid_text(call.args[0])
        run = call.args[1] if len(call.args) > 1 else None
        expected_ok = call.args[2] if len(call.args) > 2 else None
        observed_ok = bool(
            run.model_report.ok
            if run is not None and hasattr(run, "model_report")
            else False
        )
        # ``print_case`` is an assertion helper rather than the model report
        # itself: a deliberately broken diagram is a passing *check* when
        # ``expected_ok`` is False.  Preserve the model violation status but
        # project the outer oracle match into ``ok`` so grouped bad leaves and
        # their finite boundary can close without treating rejection as a
        # failed producer.
        oracle_ok = (
            observed_ok is bool(expected_ok)
            if isinstance(expected_ok, bool)
            else observed_ok
        )
        row = _model_run_projection(
            run,
            name=case_name,
            wrapper_ok=oracle_ok,
            case_kind="good" if expected_ok is True else "bad" if expected_ok is False else "",
            projection_priority=45,
        )
        if row is not None:
            row.setdefault("projection_source", "structured")
            rows.append(row)
        return rows

    # AI-entry and the two UI hardening owners return either a bool or a typed
    # per-case dictionary.  The function's first argument is its exact case
    # name; any richer fields are retained as raw observed payload.
    if name == "run_case":
        if isinstance(result, Mapping):
            case_name = _valid_text(result.get("case") or result.get("name"))
            if case_name:
                row = dict(result)
                row["name"] = case_name
                row["ok"] = bool(result.get("ok"))
                row["projection_priority"] = 42
                row["projection_source"] = "structured"
                rows.append(row)
                return rows
        case_name = _valid_text(call.args[0]) if call.args else ""
        if case_name and isinstance(result, bool):
            rows.append(
                {
                    "name": case_name,
                    "ok": result,
                    "status": "pass" if result else "fail",
                    "observed_status": "ok" if result else "violation",
                    "projection_priority": 42,
                    "projection_source": "structured",
                }
            )
        return rows

    # A custom owner returning a mapping with a concrete case/result section
    # is projected through the same exact JSON case collector.  Aggregate
    # wrapper metadata remains raw and cannot satisfy a leaf binding by itself.
    payload = _structured_to_payload(result)
    if isinstance(payload, (Mapping, list, tuple)):
        _collect_json_cases(payload, rows)
        for row in rows:
            row.setdefault("projection_priority", 35)
            row.setdefault("projection_source", "structured")
    return rows


def _captured_structured_cases(
    captured: Sequence[Any],
    *,
    owner_id: str = "",
) -> list[dict[str, Any]]:
    """Project captured typed reports into explicit native case dictionaries.

    The projectors intentionally recognise the four existing report families.
    An aggregate report is retained as metadata, while only its concrete
    ``results``/``case_results``/``cases`` members become executable leaves.
    Unknown return shapes are not guessed into cases.
    """

    projected: list[dict[str, Any]] = []
    for report in captured:
        if isinstance(report, _CapturedCall):
            # A nested exact sequence is evidence for its named outer oracle;
            # projecting it as an anonymous extra leaf would create a foreign
            # case and could mask the outer expected-violation verdict.
            if report.parent_function:
                if report.function_name not in {"run_exact_sequence", "run_exact_workflow_case"}:
                    rows = _captured_call_cases(report, owner_id=owner_id)
                    projected.extend(rows)
                continue
            rows = _captured_call_cases(report, owner_id=owner_id)
            projected.extend(rows)
            # The four canonical typed report producers are captured as call
            # envelopes too.  Their report object is projected by the exact
            # attribute branches below; do not reduce it to repr merely
            # because it has no generic ``to_dict`` method.
            if not rows and report.result is not None:
                projected.extend(
                    _captured_structured_cases((report.result,), owner_id=owner_id)
                )
            continue
        # ScenarioReviewReport / compatible typed report.
        try:
            results = report.results
        except AttributeError:
            results = None
        if isinstance(results, (list, tuple)):
            for item in results:
                try:
                    name = _valid_text(item.scenario_name)
                except AttributeError:
                    name = ""
                if not name:
                    continue
                row = _structured_to_payload(item)
                if not isinstance(row, Mapping):
                    continue
                result = dict(row)
                try:
                    run = item.scenario_run
                except AttributeError:
                    run = None
                if run is not None:
                    # OracleReviewResult.to_dict already includes this exact
                    # run projection. Keep custom report fallback unchanged.
                    if not (
                        type(item) is OracleReviewResult
                        and isinstance(row.get("scenario_run"), Mapping)
                    ):
                        result["scenario_run"] = _structured_to_payload(run)
                    try:
                        observed_status = run.observed_status
                    except AttributeError:
                        observed_status = ""
                    result["observed_status"] = _valid_text(observed_status)
                    try:
                        violation_names = run.observed_violation_names
                    except AttributeError:
                        violation_names = ()
                    result["observed_violation_names"] = list(violation_names or ())
                result["scenario_name"] = name
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                # A scenario's wrapper ``ok`` is the oracle verdict, so an
                # expected violation is a passing *check* whose model leaf is
                # nevertheless a bad-case observation.  Classify from the
                # observed model status first and only then fall back to the
                # wrapper status/ok bit.
                observed = _valid_text(result.get("observed_status")).lower()
                wrapper_status = _valid_text(result.get("status")).lower()
                if observed in {"violation", "rejected", "fail", "failed", "blocked"} or "violation" in wrapper_status:
                    result.setdefault("case_kind", "bad")
                else:
                    try:
                        item_ok = item.ok
                    except AttributeError:
                        item_ok = False
                    result.setdefault("case_kind", "good" if bool(item_ok) else "bad")
                projected.append(result)
            # A formal report also exposes ``results`` only for custom
            # wrappers; continue so its explicit case_results branch below can
            # add the richer expected/observed fields.
        try:
            case_results = report.case_results
        except AttributeError:
            case_results = None
        if isinstance(case_results, (list, tuple)):
            for item in case_results:
                try:
                    name = _valid_text(item.name)
                except AttributeError:
                    name = ""
                if not name:
                    continue
                result = _structured_to_payload(item)
                if not isinstance(result, Mapping):
                    continue
                result = dict(result)
                try:
                    expected_ok = item.expected_ok
                except AttributeError:
                    expected_ok = None
                try:
                    observed_ok = item.observed_ok
                except AttributeError:
                    observed_ok = None
                if isinstance(expected_ok, bool):
                    result["expected_ok"] = expected_ok
                    result["case_kind"] = "good" if expected_ok else "bad"
                if isinstance(observed_ok, bool):
                    result["observed_ok"] = observed_ok
                    result["observed_status"] = "ok" if observed_ok else "violation"
                result["name"] = name
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                try:
                    item_ok = item.ok
                except AttributeError:
                    item_ok = False
                result.setdefault("ok", bool(item_ok))
                projected.append(result)
        try:
            cases = report.cases
        except AttributeError:
            cases = None
        if isinstance(cases, (list, tuple)):
            for item in cases:
                try:
                    family = _valid_text(item.family_id)
                except AttributeError:
                    family = ""
                try:
                    case = _valid_text(item.case_id)
                except AttributeError:
                    case = ""
                if not family or not case:
                    continue
                result = _structured_to_payload(item)
                if not isinstance(result, Mapping):
                    continue
                result = dict(result)
                result["family_id"] = family
                result["case_id"] = case
                result["name"] = case
                result["variant"] = case
                result["case_kind"] = (
                    "bad" if case == "bad" else
                    "boundary" if case in {"missing-semantics", "truncated"}
                    else "good"
                )
                try:
                    item_report = item.report
                except AttributeError:
                    item_report = None
                try:
                    item_status = item_report.status
                except AttributeError:
                    item_status = ""
                result["observed_status"] = _valid_text(item_status) or _valid_text(
                    result.get("observed_status")
                )
                try:
                    item_ok = item.ok
                except AttributeError:
                    item_ok = False
                result["ok"] = bool(item_ok)
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                projected.append(result)
    return projected


_FORMAL_LINE = re.compile(
    # Both current formal runners are intentionally supported: some print a
    # Markdown-style ``- name: ...`` row while others print the same exact
    # row without the bullet.  The name/verdict fields are unchanged; the
    # optional prefix is not a fuzzy case selector.
    r"^(?:-\s+)?(?P<name>[^:]+):\s+observed=(?P<observed>OK|VIOLATION)\s+"
    # Formal producers may append bounded receipt annotations after the
    # verdict (for example ``exact=yes``).  The verdict fields remain the
    # authoritative parser contract; rejecting a valid line merely because
    # a producer added that explicit trailing annotation silently drops the
    # positive native leaf and can make its boundary appear incomplete.
    r"expected=(?P<expected>OK|VIOLATION)\s+match=(?P<match>yes|no)\s+formal=(?P<formal>\w+)(?:\s+.*)?$",
    re.IGNORECASE,
)
_SCENARIO_NAME = re.compile(r"^Scenario:\s*(?P<name>.+?)\s*$")
_SCENARIO_STATUS = re.compile(r"^Status:\s*(?P<status>\S+)")
_STATUS_LINE = re.compile(r"^status:(?P<name>[^:]+):\s*(?P<status>\S+)", re.IGNORECASE)
# Formal owners that still use ``run_exact_sequence`` print a compact positive
# receipt instead of a ``FormalWorkflowCaseResult`` row.  This line is an
# explicit producer contract (the name and exact marker are fixed), not a
# fuzzy interpretation of arbitrary prose.
_EXACT_PASS_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.:/-][A-Za-z0-9_.:/ -]*):\s*exact\s+model\s+pass\s*$",
    re.IGNORECASE,
)
# Keep the lowercase aggregate summary distinct from ``Status: ...`` inside a
# Scenario block.  The latter must be consumed by ``_SCENARIO_STATUS`` while a
# scenario is pending; treating both spellings as the same line silently left
# every good scenario at its default ``fail`` status.
_SIMPLE_STATUS = re.compile(r"^status:\s*(?P<status>PASS|PASSED|FAIL|FAILED|OK|BLOCKED)\s*$")
_NAMED_STATUS = re.compile(
    r"^(?:-\s*)?(?P<name>[A-Za-z0-9_.:/-][A-Za-z0-9_.:/ -]*?):\s*"
    r"(?P<status>PASS|PASSED|FAIL|FAILED|OK|VIOLATION|BLOCKED)\b",
    re.IGNORECASE,
)


def _collect_text_cases(
    stdout: str,
    *,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """Project the bounded legacy transcript grammar.

    The public helper historically returned only the case fields.  Keep that
    small API stable for callers that use it as a parser, while the native
    execution path opts into provenance metadata so the strict writer can
    prefer a typed report over a duplicate transcript line.  Metadata is
    therefore an execution-envelope concern, not part of the legacy parser's
    semantic result.
    """
    found: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for line in stdout.splitlines():
        match = _SIMPLE_STATUS.match(line.strip())
        if match:
            status = match.group("status").strip().lower()
            found.append({
                "name": "status",
                "status": status,
                "ok": status in {"pass", "passed", "ok"},
                "projection_source": "text",
                "projection_priority": 5,
            })
            continue
        match = _EXACT_PASS_LINE.match(line.strip())
        if match:
            found.append(
                {
                    "name": match.group("name").strip(),
                    "status": "pass",
                    "observed_status": "ok",
                    "ok": True,
                    "case_kind": "good",
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _SCENARIO_NAME.match(line.strip())
        if match:
            pending = {
                "scenario_name": match.group("name"),
                "ok": False,
                "status": "fail",
                "projection_source": "text",
                "projection_priority": 10,
            }
            found.append(pending)
            continue
        if pending is not None:
            observed = re.match(r"^Observed:\s*(?P<status>[^;]+)", line.strip())
            if observed:
                pending["observed_status"] = observed.group("status").strip().lower()
                continue
            match = _SCENARIO_STATUS.match(line.strip())
            if match:
                status = match.group("status").strip().lower()
                pending["status"] = status
                pending["ok"] = status in {"pass", "ok", "expected_violation_observed"}
                continue
            violation_names = re.match(
                r"^-?\s*violation_names=\s*(?P<codes>.+?)\s*$",
                line.strip(),
                re.IGNORECASE,
            )
            if violation_names:
                codes = tuple(
                    item.strip()
                    for item in violation_names.group("codes").split(",")
                    if item.strip()
                )
                if codes:
                    pending["finding_codes"] = list(codes)
                continue
        match = _FORMAL_LINE.match(line.strip())
        if match:
            found.append(
                {
                    "name": match.group("name").strip(),
                    "observed_status": match.group("observed").lower(),
                    "expected_ok": match.group("expected").upper() == "OK",
                    "match": match.group("match"),
                    "ok": match.group("match").lower() == "yes",
                    "formal": match.group("formal"),
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _STATUS_LINE.match(line.strip())
        if match:
            status = match.group("status").strip().lower()
            found.append(
                {
                    "name": match.group("name").strip(),
                    "status": status,
                    "ok": status in {"pass", "ok", "passed"},
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _NAMED_STATUS.match(line.strip())
        if match:
            name = match.group("name").strip()
            # Avoid turning aggregate summary labels into duplicate cases.
            if name.casefold() not in {
                "status",
                "result",
                "decision",
                "outcome",
                "observed",
                "expected",
                "evidence",
                "counterexample",
            }:
                status = match.group("status").strip().lower()
                row = {
                    "name": name,
                    "status": status,
                    "ok": status in {"pass", "passed", "ok"},
                    "projection_source": "text",
                    "projection_priority": 15,
                }
                # Several legacy custom owners display their typed oracle
                # codes on the same line (``name: PASS codes=[...]``).  Keep
                # that finite diagnostic payload; dropping it would make a
                # known-bad model row indistinguishable from a good row.
                codes_match = re.search(r"\bcodes\s*=\s*\[(?P<codes>[^\]]*)\]", line, re.IGNORECASE)
                if codes_match:
                    encoded = codes_match.group("codes")
                    codes = tuple(
                        item
                        for item in re.findall(r"['\"]([^'\"]+)['\"]", encoded)
                        if item.strip()
                    )
                    if codes:
                        row["finding_codes"] = list(dict.fromkeys(codes))
                found.append(row)
    if not include_metadata:
        for row in found:
            row.pop("projection_source", None)
            row.pop("projection_priority", None)
    return found


_NON_CASE_JSON_NAMES = frozenset(
    {
        # These are FlowGuard envelopes/heads, not producer-owned case
        # sources.  In particular, an older native result must never be
        # re-projected as a case for a later invocation.
        "native-case-results.json",
        "native-source.json",
        "evidence-run.json",
        "CURRENT.json",
    }
)


def _json_file_state(output_dir: Path) -> dict[Path, tuple[int, int, int]]:
    """Return the invocation-boundary state of regular JSON files.

    The native bridge historically walked the complete output tree after the
    owner returned.  That made a previous invocation's case envelope look
    indistinguishable from a file emitted by the current owner.  A small
    stat-based snapshot is sufficient here: files that are created or
    replaced during the owner call are explicitly admitted below, while
    untouched history is not an input to the current case projection.
    """

    state: dict[Path, tuple[int, int, int]] = {}
    if not output_dir.is_dir():
        return state
    for path in sorted(output_dir.rglob("*.json")):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        state[path.resolve()] = (
            int(stat.st_size),
            int(getattr(stat, "st_mtime_ns", 0)),
            int(getattr(stat, "st_ctime_ns", 0)),
        )
    return state


def _load_existing_json(
    output_dir: Path,
    *,
    paths: Sequence[Path] = (),
) -> list[dict[str, Any]]:
    """Load only JSON files explicitly changed by this owner invocation.

    ``paths`` is deliberately required at the call site (an empty default
    yields no rows), so this helper cannot silently fall back to a historical
    recursive scan.  The caller owns the invocation-boundary snapshot and
    passes only newly-created or replaced files.
    """

    found: list[dict[str, Any]] = []
    if not paths or not output_dir.is_dir():
        return found
    root = output_dir.resolve()
    candidates: set[Path] = set()
    for candidate in paths:
        try:
            path = Path(candidate).resolve()
        except (OSError, RuntimeError, TypeError):
            continue
        if root not in path.parents or path.name in _NON_CASE_JSON_NAMES:
            continue
        candidates.add(path)
    for path in sorted(candidates):
        try:
            if path.is_symlink() or not path.is_file():
                continue
        except OSError:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        _collect_json_cases(payload, found)
    return found


def _deduplicate_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    owner_id: str = "",
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for raw in cases:
        identifier = _case_id(raw)
        # Benchmark leaves are keyed by the ordered pair (family_id, case_id)
        # on the wire.  Deduplicating on the short variant alone would retain
        # only the first family and silently shrink the finite denominator.
        family = _valid_text(raw.get("family_id")) if isinstance(raw, Mapping) else ""
        if family and identifier:
            identifier = f"benchmark:{family}:{identifier}"
        if (
            not identifier
            or identifier.casefold() in _SUMMARY_CASE_NAMES
        ):
            continue
        candidate = dict(raw)
        position = positions.get(identifier)
        if position is None:
            positions[identifier] = len(result)
            result.append(candidate)
            continue
        # Prefer the outer, named oracle over an inner report projection and
        # prefer structured data over legacy transcript parsing.  Equal
        # priority keeps first-observed order deterministic.
        old = result[position]
        old_priority = int(old.get("projection_priority", 0) or 0)
        new_priority = int(candidate.get("projection_priority", 0) or 0)
        if new_priority > old_priority:
            result[position] = candidate
    return result


def _qualified_case_id(owner_id: str, raw: Mapping[str, Any]) -> str:
    """Apply the frozen native leaf namespace for one owner.

    This is an explicit owner-class dispatch, not a best-effort alias.  A
    benchmark row must carry both family and case identities; otherwise it is
    left unqualified and the strict binding verifier reports it as foreign.
    """

    owner = _valid_text(owner_id).removeprefix("model:")
    raw_id = _case_id(raw)
    if not owner or not raw_id:
        return ""
    if raw_id.startswith(("native-scenario:", "case:", "benchmark:")):
        return raw_id
    if owner in _SCENARIO_OWNERS:
        return f"native-scenario:{owner}:{raw_id}"
    if owner == _BENCHMARK_OWNER:
        family = _valid_text(raw.get("family_id"))
        case = _valid_text(raw.get("case_id")) or raw_id
        if family and case:
            return f"benchmark:{family}:{case}"
        return raw_id
    return f"case:{owner}:{raw_id}"


def _env_fingerprint(name: str, fallback: Any) -> str:
    value = _valid_text(os.environ.get(name))
    if value.startswith("sha256:") and len(value) == 71:
        return value
    return fingerprint_payload(fallback)


def _case_kind(raw: Mapping[str, Any], qualified_case_id: str) -> str:
    """Return an explicit leaf kind when the producer supplied one."""

    declared = _valid_text(raw.get("case_kind")).lower()
    if declared in {"good", "boundary", "bad"}:
        return declared
    expected_ok = raw.get("expected_ok")
    if isinstance(expected_ok, bool):
        return "good" if expected_ok else "bad"
    variant = _valid_text(raw.get("variant")).lower()
    if variant in {"missing-semantics", "truncated"}:
        return "boundary"
    if variant == "bad":
        return "bad"
    status = _status(raw, ok=_observed_ok(raw)).casefold()
    if "boundary" in qualified_case_id.casefold():
        return "boundary"
    if any(token in status for token in ("violation", "reject", "fail", "error")):
        return "bad"
    return "good"


def _expected_observed_status(raw: Mapping[str, Any], *, fallback: str) -> str:
    """Prefer a producer's observed/model status over wrapper outcome text."""

    for key in ("observed_status", "model_observed_status", "observed"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    scenario_run = raw.get("scenario_run")
    if isinstance(scenario_run, Mapping):
        value = scenario_run.get("observed_status")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return fallback


def _runtime_case_mapping(
    owner_id: str,
) -> tuple[NativeCaseMappingRegistry | None, dict[str, Any], str]:
    """Load the one explicit project mapping, when a project root supplied it.

    Native runners are also used as small standalone tests, so the registry is
    optional for those callers.  Once ``FLOWGUARD_PROJECT_ROOT`` is present,
    however, a missing, stale, or malformed registry is a hard producer input
    error.  No output-directory parent walk or name-based fallback is allowed.
    The returned index is keyed by the exact ``(owner, native_case_id)`` pair
    and contains the binding's declared kind/dimensions/oracle expectations.
    """

    root_text = _valid_text(os.environ.get("FLOWGUARD_PROJECT_ROOT"))
    if not root_text:
        return None, {}, ""
    root = Path(root_text).expanduser().resolve()
    try:
        registry = load_native_case_mapping(root)
        registry.assert_current_manifest(root)
    except (NativeCaseMappingError, OSError, UnicodeError, ValueError) as exc:
        return None, {}, f"native_case_mapping_invalid:{exc}"
    index: dict[str, Any] = {}
    owner = _valid_text(owner_id) or "model:unknown"
    for binding in registry.bindings_by_owner.get(owner, ()):
        for native_id in binding.native_case_ids:
            key = f"{owner}\x00{native_id}"
            # Reuse is legal when the registry proved the projections have an
            # identical observable contract.  Keep one deterministic binding
            # for producer row shaping; the downstream binding verifier still
            # evaluates every blueprint obligation against that one receipt.
            if key in index:
                previous = index[key]
                signature = (
                    previous.expected_status,
                    previous.expected_observed_status or previous.expected_status,
                    previous.evidence_scope,
                    previous.covered_dimensions,
                    previous.protected_failure_ids,
                    previous.expected_finding_codes,
                )
                current = binding
                current_signature = (
                    current.expected_status,
                    current.expected_observed_status or current.expected_status,
                    current.evidence_scope,
                    current.covered_dimensions,
                    current.protected_failure_ids,
                    current.expected_finding_codes,
                )
                if signature != current_signature:
                    return None, {}, f"native_case_mapping_incompatible_reuse:{owner}:{native_id}"
                continue
            index[key] = binding
    return registry, index, ""


def _required_environment_fingerprint(name: str) -> str:
    """Read one producer identity without manufacturing a fallback hash.

    The model-regression launcher supplies all six values from its frozen
    owner observation.  A strict producer invoked outside that launcher must
    fail closed instead of turning the current process, stdout, or a guessed
    model name into an input identity.
    """

    value = _valid_text(os.environ.get(name))
    if not value.startswith("sha256:") or len(value) != 71:
        raise NativeCaseProtocolError(
            f"strict native producer requires canonical {name}"
        )
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise NativeCaseProtocolError(
            f"strict native producer requires canonical {name}"
        ) from exc
    return value


def _scenario_result_status(result: Any) -> tuple[str, bool]:
    """Convert the report's oracle status to native outcome semantics.

    ``expected_violation_observed`` is a passing *oracle* result: the model
    intentionally observed a violation.  The native row therefore has
    ``outcome=pass`` while retaining ``observed_status=violation``.  Any
    unresolved or mismatched report status is blocked and cannot be promoted
    by an exit code or a transcript.
    """

    status = _valid_text(getattr(result, "status", "")).lower()
    if status in {"pass", "expected_violation_observed"}:
        return "pass", True
    return "blocked", False


def _scenario_trace_labels(result: Any) -> tuple[str, ...]:
    run = getattr(result, "scenario_run", None)
    traces = getattr(run, "traces", ()) if run is not None else ()
    labels: list[str] = []
    for trace in traces or ():
        for label in getattr(trace, "labels", ()) or ():
            text = _valid_text(label)
            if text and text not in labels:
                labels.append(text)
    return tuple(labels)


def _scenario_observed_findings(result: Any) -> tuple[str, ...]:
    run = getattr(result, "scenario_run", None)
    values = getattr(run, "observed_violation_names", ()) if run is not None else ()
    findings: list[str] = []
    for value in values or ():
        text = _valid_text(value)
        if text and text not in findings:
            findings.append(text)
    return tuple(findings)


def native_results_from_scenario_report(
    owner_id: str,
    report: Any,
) -> tuple[NativeModelCaseResult, ...]:
    """Convert one real ``ScenarioReviewReport`` to the strict native tuple.

    The conversion is intentionally producer-side and one-shot.  It requires
    the current checked-in mapping, uses the exact scenario names as native
    IDs, preserves the model's observed status/finding/trace data, and emits
    the boundary aggregate only after every declared child was returned by
    this same report.  No stdout, global callback, directory scan, or count
    inference participates in the result.
    """

    owner = _valid_text(owner_id)
    if not owner.startswith("model:"):
        owner = "model:" + owner
    owner_key = owner.removeprefix("model:")
    if owner_key not in _STRICT_NATIVE_OWNER_IDS:
        raise NativeCaseProtocolError(
            f"scenario report producer is not registered for {owner}"
        )
    report_rows = getattr(report, "results", None)
    if not isinstance(report_rows, tuple):
        raise NativeCaseProtocolError(
            "strict scenario producer must return one ScenarioReviewReport tuple"
        )
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    if mapping is None or mapping_error:
        raise NativeCaseProtocolError(
            mapping_error or "strict native producer requires current native mapping"
        )
    input_fp = _required_environment_fingerprint("FLOWGUARD_INPUT_FINGERPRINT")
    model_fp = _required_environment_fingerprint("FLOWGUARD_MODEL_FINGERPRINT")
    code_fp = _required_environment_fingerprint("FLOWGUARD_CODE_FINGERPRINT")
    test_fp = _required_environment_fingerprint("FLOWGUARD_TEST_FINGERPRINT")
    tool_fp = _required_environment_fingerprint("FLOWGUARD_TOOLCHAIN_FINGERPRINT")
    env_fp = _required_environment_fingerprint("FLOWGUARD_ENVIRONMENT_FINGERPRINT")
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", "")).resolve()
    if not str(output_dir) or str(output_dir) == str(Path.cwd().resolve()):
        raise NativeCaseProtocolError(
            "strict native producer requires an explicit FLOWGUARD_OUTPUT_DIR"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "native-source.json"

    # The report itself is the raw immutable producer artifact.  It is written
    # before rows are constructed so every row can bind to its exact bytes.
    report_payload = _structured_to_payload(report)
    source_payload = {
        "schema_version": NATIVE_CASE_RESULT_SCHEMA,
        "owner_id": owner,
        "producer": "scenario_review_report",
        "mapping_fingerprint": mapping.mapping_fingerprint,
        "report": report_payload,
    }
    declaration = _DECLARED_SOURCE.get()
    if declaration is not None:
        source_payload["declared_path_quality_source"] = declaration
    material = _ARCHITECTURE_MATERIAL.get()
    if material is not None:
        source_payload["architecture_material"] = material
    source_bytes = _json_bytes(source_payload) + b"\n"
    source_path.write_bytes(source_bytes)
    source_fp = _sha256_bytes(source_bytes)

    expected_leaf_ids = {
        key.split("\x00", 1)[1]
        for key, binding in mapping_index.items()
        if key.startswith(owner + "\x00") and not binding.required_child_case_ids
    }
    rows_by_id: dict[str, NativeModelCaseResult] = {}
    for report_row in report_rows:
        scenario_name = _valid_text(getattr(report_row, "scenario_name", ""))
        if not scenario_name:
            raise NativeCaseProtocolError("scenario report has an unnamed result")
        native_id = f"native-scenario:{owner_key}:{scenario_name}"
        if native_id in rows_by_id:
            raise NativeCaseProtocolError(f"duplicate strict native scenario: {native_id}")
        binding = mapping_index.get(f"{owner}\x00{native_id}")
        if binding is None or binding.required_child_case_ids:
            raise NativeCaseProtocolError(f"unmapped strict native scenario: {native_id}")
        run = getattr(report_row, "scenario_run", None)
        observed_status = _valid_text(getattr(run, "observed_status", ""))
        if not observed_status:
            raise NativeCaseProtocolError(f"scenario has no observed status: {native_id}")
        outcome, oracle_ok = _scenario_result_status(report_row)
        semantic_checks = _executed_architecture_checks(native_id, _structured_to_payload(report_row))
        if semantic_checks and not all(x["status"] == "pass" for x in semantic_checks):
            oracle_ok, outcome = False, "fail"
        findings = _scenario_observed_findings(report_row)
        trace_labels = _scenario_trace_labels(report_row)
        dimensions = tuple(binding.covered_dimensions)
        oracle_fp = fingerprint_payload(
            {
                "scenario_name": scenario_name,
                "expected_status": binding.expected_status,
                "expected_observed_status": binding.expected_observed_status,
                "expected_finding_codes": list(binding.expected_finding_codes),
                "observed_status": observed_status,
                "observed_finding_codes": list(findings),
                "trace_labels": list(trace_labels),
            }
        )
        rows_by_id[native_id] = NativeModelCaseResult(
            owner_id=owner,
            source_case_id=native_id,
            outcome=outcome,
            observed_status=observed_status,
            observed_finding_codes=findings,
            executed_dimensions=dimensions,
            oracle_results=tuple(
                {
                    "dimension": dimension,
                    "oracle_member_id": f"{owner}:{native_id}:{dimension}",
                    "status": observed_status,
                    "ok": oracle_ok,
                    "finding_codes": list(findings),
                    "observed": {"trace_labels": list(trace_labels), **(
                        {"semantic_checks": semantic_checks} if dimension == "input" and semantic_checks else {}
                    )},
                }
                for dimension in dimensions
            ),
            result_artifact_fingerprint=source_fp,
            input_fingerprint=input_fp,
            model_fingerprint=model_fp,
            code_fingerprint=code_fp,
            test_fingerprint=test_fp,
            oracle_fingerprint=oracle_fp,
            toolchain_fingerprint=tool_fp,
            environment_fingerprint=env_fp,
            raw_artifact_path=str(source_path.resolve()) if _ARCHITECTURE_MATERIAL.get() is not None else "native-source.json",
        )
    actual_leaf_ids = set(rows_by_id)
    if actual_leaf_ids != expected_leaf_ids:
        missing = sorted(expected_leaf_ids - actual_leaf_ids)
        extra = sorted(actual_leaf_ids - expected_leaf_ids)
        raise NativeCaseProtocolError(
            f"strict native denominator mismatch: missing={missing}, extra={extra}"
        )

    boundary_bindings = {
        binding.native_case_ids[0]: binding
        for key, binding in mapping_index.items()
        if key.startswith(owner + "\x00")
        and binding.case_kind == "boundary" and binding.required_child_case_ids
    }
    if len(boundary_bindings) != 1:
        raise NativeCaseProtocolError("native owner requires exactly one boundary aggregate")
    for boundary_id, binding in sorted(boundary_bindings.items()):
        child_ids = tuple(binding.required_child_case_ids)
        missing = tuple(child for child in child_ids if child not in rows_by_id)
        failed = tuple(
            child
            for child in child_ids
            if child in rows_by_id and rows_by_id[child].outcome != "pass"
        )
        boundary_ok = bool(child_ids) and not missing and not failed
        status = "ok" if boundary_ok else "blocked"
        findings = tuple(
            item
            for item in (
                "boundary_child_result_missing" if missing else "",
                "boundary_child_result_failed" if failed else "",
            )
            if item
        )
        rows_by_id[boundary_id] = NativeModelCaseResult(
            owner_id=owner,
            source_case_id=boundary_id,
            outcome="pass" if boundary_ok else "blocked",
            observed_status=status,
            observed_finding_codes=findings,
            executed_dimensions=tuple(binding.covered_dimensions),
            oracle_results=tuple(
                {
                    "dimension": dimension,
                    "oracle_member_id": f"{owner}:{boundary_id}:{dimension}",
                    "status": status,
                    "ok": boundary_ok,
                    "finding_codes": list(findings),
                    "observed": {"child_case_ids": list(child_ids)},
                }
                for dimension in binding.covered_dimensions
            ),
            result_artifact_fingerprint=source_fp,
            input_fingerprint=input_fp,
            model_fingerprint=model_fp,
            code_fingerprint=code_fp,
            test_fingerprint=test_fp,
            oracle_fingerprint=fingerprint_payload(
                {"boundary": boundary_id, "children": list(child_ids), "status": status}
            ),
            toolchain_fingerprint=tool_fp,
            environment_fingerprint=env_fp,
            raw_artifact_path="native-source.json",
            child_case_ids=child_ids,
        )
    return tuple(rows_by_id[key] for key in sorted(rows_by_id))


def _write_strict_native_results(
    owner_id: str,
    results: tuple[NativeModelCaseResult, ...],
    output_dir: Path,
) -> Path:
    """Persist a typed producer tuple after exact mapping validation."""

    owner = _valid_text(owner_id)
    if not owner.startswith("model:"):
        owner = "model:" + owner
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    if mapping is None or mapping_error:
        raise NativeCaseProtocolError(
            mapping_error or "strict native result requires current native mapping"
        )
    if not results or any(not isinstance(row, NativeModelCaseResult) for row in results):
        raise NativeCaseProtocolError(
            "strict native producer must return tuple[NativeModelCaseResult, ...]"
        )
    keys = [(row.owner_id, row.source_case_id) for row in results]
    if len(keys) != len(set(keys)):
        raise NativeCaseProtocolError("strict native producer returned duplicate rows")
    if any(row.owner_id != owner for row in results):
        raise NativeCaseProtocolError("strict native producer returned a foreign owner")
    declared_keys = {
        (key.split("\x00", 1)[0], key.split("\x00", 1)[1])
        for key in mapping_index
    }
    actual_keys = set(keys)
    if actual_keys != declared_keys:
        missing = sorted(declared_keys - actual_keys)
        extra = sorted(actual_keys - declared_keys)
        raise NativeCaseProtocolError(
            f"strict native result mapping mismatch: missing={missing}, extra={extra}"
        )
    source_path = output_dir / "native-source.json"
    if source_path.is_symlink() or not source_path.is_file():
        raise NativeCaseProtocolError("strict native producer did not write native-source.json")
    source_fp = _sha256_bytes(source_path.read_bytes())
    for row in results:
        raw_path = Path(row.raw_artifact_path)
        if raw_path.is_absolute() or raw_path.parts != ("native-source.json",):
            raise NativeCaseProtocolError("strict native row raw artifact path is not current")
        if row.result_artifact_fingerprint != source_fp:
            raise NativeCaseProtocolError(
                f"strict native row artifact fingerprint mismatch: {row.source_case_id}"
            )
    target = output_dir / "native-case-results.json"
    target.write_bytes(
        _json_bytes(
            {
                "schema_version": NATIVE_CASE_RESULT_SCHEMA,
                "results": [row.to_dict() for row in results],
            }
        )
        + b"\n"
    )
    return target


def _write_results(
    owner_id: str,
    cases: Sequence[Mapping[str, Any]],
    stdout: str,
    exit_code: int,
    output_dir: Path,
    *,
    structured_reports: Sequence[Any] = (),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "native-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    owner = _valid_text(owner_id) or "model:unknown"
    base_input = _env_fingerprint("FLOWGUARD_INPUT_FINGERPRINT", {"owner": owner, "stdout": stdout})
    model_fp = _env_fingerprint("FLOWGUARD_MODEL_FINGERPRINT", {"owner": owner, "model": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    code_fp = _env_fingerprint("FLOWGUARD_CODE_FINGERPRINT", {"owner": owner, "code": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    test_fp = _env_fingerprint("FLOWGUARD_TEST_FINGERPRINT", {"owner": owner, "test": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    tool_fp = _env_fingerprint("FLOWGUARD_TOOLCHAIN_FINGERPRINT", {"python": sys.version, "executable": sys.executable})
    env_fp = _env_fingerprint("FLOWGUARD_ENVIRONMENT_FINGERPRINT", {"platform": sys.platform, "cwd": str(Path.cwd())})
    stdout_fingerprint = _sha256_bytes(stdout.encode("utf-8"))
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    diagnostic_case_ids = (
        frozenset(mapping.diagnostic_native_case_ids)
        if mapping is not None
        else frozenset()
    )

    # Preserve the original executed report for coverage and conformance.
    # Complete graph authority comes only from the independent explicit source
    # exporter below; passing traces never fill an absent declaration.
    report_payload: Mapping[str, Any] | None = None
    for captured in structured_reports:
        candidate = (
            captured.result
            if isinstance(captured, _CapturedCall)
            else captured
        )
        payload = _path_quality_report_payload(candidate)
        if payload is None:
            continue
        report_payload = payload
        break
    normalized_cases: list[tuple[str, Mapping[str, Any]]] = []
    for raw in cases:
        qualified = _qualified_case_id(owner, raw)
        if not qualified:
            continue
        normalized_cases.append((qualified, raw))
    compact_cases: list[dict[str, Any]] = []
    for qualified, raw in normalized_cases:
        compact: dict[str, Any] = {}
        for key in (
            *_CASE_KEYS,
            *_STATUS_KEYS,
            *_OK_KEYS,
            "finding_codes",
            "observed_finding_codes",
            # Execution provenance is intentionally kept in the raw source
            # envelope.  It lets a reviewer see why a transcript duplicate
            # was not promoted to an authoritative leaf without making the
            # native result verifier depend on display text.
            "projection_source",
            "projection_priority",
        ):
            if key in raw and not isinstance(raw[key], (Mapping, list, tuple)):
                compact[key] = raw[key]
            elif key in raw and isinstance(raw[key], (list, tuple)):
                compact[key] = [item for item in raw[key] if isinstance(item, (str, int, float, bool))]
        compact["source_fingerprint"] = fingerprint_payload(raw)
        compact["qualified_case_id"] = qualified
        # Preserve the actual named checks before the source artifact is
        # hashed. Diagnostic report summaries do not retain these records.
        semantic_checks = _executed_architecture_checks(qualified, raw)
        if semantic_checks:
            compact["semantic_checks"] = semantic_checks
        compact_cases.append(compact)
    unmapped_cases: list[dict[str, Any]] = []
    if mapping is not None:
        for qualified, raw in normalized_cases:
            if f"{owner}\x00{qualified}" in mapping_index:
                continue
            unmapped_cases.append(
                {
                    "qualified_case_id": qualified,
                    "source_fingerprint": fingerprint_payload(raw),
                    "disposition": (
                        "diagnostic"
                        if qualified in diagnostic_case_ids
                        else "supporting_native_observation"
                    ),
                }
            )
    # A boundary is a distinct finite aggregate receipt, not a copied good or
    # bad aggregate.  The mapping compiler freezes its exact child set.  Keep
    # the accounting visible in the raw source envelope and emit the boundary
    # result below only after all child rows have been projected from this one
    # producer invocation. Every selected current owner has exactly one such
    # aggregate; boundary leaves keep their own independent native results.
    boundary_binding = None
    boundary_case_id = ""
    boundary_children: tuple[str, ...] = ()
    boundary_present_children: tuple[str, ...] = ()
    boundary_missing_children: tuple[str, ...] = ()
    if mapping is not None and not mapping_error:
        aggregates = {
            candidate.blueprint_case_id: candidate
            for candidate in mapping_index.values()
            if candidate.owner_id == owner
            and candidate.case_kind == "boundary"
            and candidate.required_child_case_ids
        }
        if len(aggregates) != 1:
            raise NativeCaseProtocolError("native owner requires exactly one boundary aggregate")
        boundary_binding = next(iter(aggregates.values()))
        if boundary_binding is not None:
            boundary_case_id = boundary_binding.native_case_ids[0]
            boundary_children = tuple(boundary_binding.required_child_case_ids)
            observed_ids = {
                qualified
                for qualified, _raw in normalized_cases
                if f"{owner}\x00{qualified}" in mapping_index
                and qualified != boundary_case_id
            }
            boundary_present_children = tuple(
                child for child in boundary_children if child in observed_ids
            )
            boundary_missing_children = tuple(
                child for child in boundary_children if child not in observed_ids
            )
    source_payload = {
        "schema_version": NATIVE_CASE_RESULT_SCHEMA,
        "owner_id": owner,
        "exit_code": exit_code,
        "stdout_fingerprint": stdout_fingerprint,
        "native_case_mapping": {
            "status": (
                "not_configured"
                if mapping is None and not mapping_error
                else "current"
                if mapping is not None
                else "invalid"
            ),
            "mapping_fingerprint": mapping.mapping_fingerprint if mapping is not None else "",
            "error": mapping_error,
            # Current native producers may expose more observations than the
            # small set of rows that this owner declares as blueprint
            # obligations.  Keep those exact rows visible without allowing
            # them to become an implicit leaf or a producer-wide failure.
            # Missing rows that *are* declared remain a hard error in the
            # binding verifier below.
            "unmapped_cases": unmapped_cases,
            "boundary": {
                "native_case_id": boundary_case_id,
                "required_child_case_ids": list(boundary_children),
                "present_child_case_ids": list(boundary_present_children),
                "missing_child_case_ids": list(boundary_missing_children),
                "status": (
                    "not_configured"
                    if mapping is None and not mapping_error
                    else "invalid"
                    if mapping_error
                    else "ready"
                    if not boundary_missing_children
                    else "incomplete"
                ),
            },
            "diagnostic_cases_present": [
                {
                    "qualified_case_id": qualified,
                    "source_fingerprint": fingerprint_payload(raw),
                }
                for qualified, raw in normalized_cases
                if qualified in diagnostic_case_ids
            ],
        },
        "cases": compact_cases,
        "structured_reports": [
            _structured_to_payload(item) for item in structured_reports
        ],
    }
    if report_payload is not None:
        source_payload["report"] = report_payload
    declaration = _DECLARED_SOURCE.get()
    if declaration is not None:
        source_payload["declared_path_quality_source"] = declaration
    material = _ARCHITECTURE_MATERIAL.get()
    if material is not None:
        source_payload["architecture_material"] = material
    source_path = output_dir / "native-source.json"
    source_bytes = _json_bytes(source_payload) + b"\n"
    source_path.write_bytes(source_bytes)
    source_fp = _sha256_bytes(source_bytes)
    rows: list[dict[str, Any]] = []
    for case, raw in normalized_cases:
        binding = None
        if mapping is not None:
            binding = mapping_index.get(f"{owner}\x00{case}")
            if binding is None:
                if case in diagnostic_case_ids:
                    # This row is a current, explicitly named helper or
                    # transcript projection.  Preserve it in the immutable
                    # source envelope, but never let it satisfy a blueprint
                    # leaf or turn an unknown row into a pass.
                    continue
                # A current registry is authoritative.  Preserve the raw
                # observation above for diagnosis, but do not infer a kind,
                # dimensions, or expected status for an unmapped row.  It is
                # deliberately omitted from authoritative result rows.
                continue
        ok = _observed_ok(raw)
        status = _status(raw, ok=ok)
        outcome = "pass" if ok else ("rejected" if "violation" in status.casefold() or "reject" in status.casefold() else "fail")
        findings = _finding_codes(raw)
        compact = next(
            (item for item in compact_cases if item.get("qualified_case_id") == case),
            {"source_case_id": case, "source_fingerprint": fingerprint_payload(raw)},
        )
        oracle_fp = fingerprint_payload({"case": dict(raw), "status": status, "outcome": outcome})
        kind = binding.case_kind if binding is not None else _case_kind(raw, case)
        dimensions = {
            "boundary": ("input", "error", "decision", "retry", "timeout", "completion"),
            "bad": ("input", "state", "effect", "error", "decision", "completion"),
            "good": GOOD_DIMENSIONS,
        }[kind]
        observed_status = _expected_observed_status(raw, fallback=status)
        semantic_checks = _executed_architecture_checks(case, raw)
        # An explicitly captured oracle result is a passed *check* even when
        # the model intentionally observed a violation.  Keep that distinction
        # in the row instead of deriving it from the wrapper's exit status.
        declared_kind = raw.get("case_kind")
        if (isinstance(declared_kind, str) and declared_kind in {"good", "boundary", "bad"}) or "expected_ok" in raw:
            outcome = "pass" if bool(raw.get("ok", ok)) else outcome
        if semantic_checks and not all(x["status"] == "pass" for x in semantic_checks):
            ok, outcome = False, "fail"
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=case,
                outcome=outcome,
                observed_status=observed_status,
                observed_finding_codes=findings,
                executed_dimensions=dimensions,
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:{case}:{dimension}",
                        "status": observed_status,
                        "ok": bool(ok),
                        "finding_codes": list(findings),
                        "observed": {**{key: value for key, value in compact.items()
                                       if key != "semantic_checks"}, **(
                            {"semantic_checks": semantic_checks} if dimension == "input" and semantic_checks else {}
                        )},
                    }
                    for dimension in dimensions
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=oracle_fp,
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.resolve()) if _ARCHITECTURE_MATERIAL.get() is not None else str(source_path.relative_to(output_dir)),
            ).to_dict()
        )
    if boundary_binding is not None and not mapping_error:
        # Child rows are already produced above; do not call any owner
        # callback again.  A complete boundary requires every frozen child to
        # be present and to have a passing producer outcome.  Bad-model cases
        # intentionally have ``observed_status=violation`` but their wrapper
        # oracle is still ``outcome=pass`` and therefore count as valid
        # children here.
        by_source_case = {
            str(row.get("source_case_id", "")): row
            for row in rows
            if isinstance(row, Mapping)
        }
        missing_children = tuple(
            child
            for child in boundary_children
            if child not in by_source_case
        )
        failed_children = tuple(
            child
            for child in boundary_children
            if child in by_source_case
            and by_source_case[child].get("outcome") != "pass"
        )
        boundary_ok = bool(boundary_children) and not missing_children and not failed_children
        boundary_status = "ok" if boundary_ok else "blocked"
        boundary_findings = tuple(
            ["boundary_child_result_missing"] if missing_children else []
        ) + tuple(
            ["boundary_child_result_failed"] if failed_children else []
        )
        boundary_observed = {
            "native_case_id": boundary_case_id,
            "required_child_case_ids": list(boundary_children),
            "present_child_case_ids": [
                child for child in boundary_children if child in by_source_case
            ],
            "missing_child_case_ids": list(missing_children),
            "failed_child_case_ids": list(failed_children),
            "status": boundary_status,
        }
        boundary_oracle_fp = fingerprint_payload(boundary_observed)
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=boundary_case_id,
                outcome="pass" if boundary_ok else "blocked",
                observed_status=boundary_status,
                observed_finding_codes=boundary_findings,
                executed_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:{boundary_case_id}:{dimension}",
                        "status": boundary_status,
                        "ok": boundary_ok,
                        "finding_codes": list(boundary_findings),
                        "observed": boundary_observed,
                    }
                    for dimension in ("input", "error", "decision", "retry", "timeout", "completion")
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=boundary_oracle_fp,
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.relative_to(output_dir)),
                child_case_ids=boundary_children,
            ).to_dict()
        )
    mapping_findings = tuple(
        dict.fromkeys(mapping_error.splitlines() if mapping_error else ())
    )
    if mapping_findings:
        # A registry failure is represented as a terminal blocked producer
        # result, never as a guessed set of leaf rows.  The complete raw
        # observations remain in native-source.json with the exact error.
        rows = []
    if not rows:
        # A runner with no case-shaped report is still recorded as a blocked
        # producer.  This keeps the strict gate honest instead of turning an
        # exit code into a fabricated behavioural pass.
        raw_payload = {
            "schema_version": NATIVE_CASE_RESULT_SCHEMA,
            "owner_id": owner,
            "source_case_id": "terminal",
            "observed_status": "no_case_projection",
            "outcome": "blocked",
            "stdout_fingerprint": stdout_fingerprint,
            "exit_code": exit_code,
            "mapping_findings": list(mapping_findings),
        }
        finding_code = (
            mapping_findings[0]
            if mapping_findings
            else "native_case_projection_missing"
        )
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id="terminal",
                outcome="blocked",
                observed_status="no_case_projection",
                observed_finding_codes=(finding_code,),
                executed_dimensions=GOOD_DIMENSIONS,
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:terminal:{dimension}",
                        "status": "no_case_projection",
                        "ok": False,
                        "finding_codes": [finding_code],
                        "observed": raw_payload,
                    }
                    for dimension in GOOD_DIMENSIONS
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=fingerprint_payload(raw_payload),
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.relative_to(output_dir)),
            ).to_dict()
        )
    target = output_dir / "native-case-results.json"
    target.write_bytes(_json_bytes({"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": rows}) + b"\n")
    return target


def native_main(
    owner_id: str,
    main: Callable[[], Any],
    *,
    declared_source_exporter: Callable[[str], Any] | None = None,
) -> int:
    """Export declaration once before the same owner's immutable raw episode.

    The exporter constructs source data only.  Receipt admission happens in
    the later consumer; no current-episode receipt can precede its own bytes.
    """
    declaration = None
    architecture_material = None
    if declared_source_exporter is not None:
        try:
            from .model_path_quality import DeclaredPathQualitySource

            model_fp = _required_environment_fingerprint("FLOWGUARD_MODEL_INSTANCE_FINGERPRINT")
            source = declared_source_exporter(model_fp)
            if isinstance(source, NativeArchitectureDeclaration):
                from .native_case_protocol import parse_native_architecture_material
                architecture_material = parse_native_architecture_material(source.architecture_material)
                source = source.source
            if isinstance(source, Mapping):
                source = DeclaredPathQualitySource.from_dict(source)
            if not isinstance(source, DeclaredPathQualitySource):
                raise NativeCaseProtocolError("exporter did not return a declared source")
            if source.model_id != owner_id.removeprefix("model:"):
                raise NativeCaseProtocolError("declared source belongs to a foreign model")
            if source.model_instance_fingerprint != model_fp:
                raise NativeCaseProtocolError("declared source model identity mismatch")
            if architecture_material is not None:
                _verify_architecture_declaration(source, architecture_material)
            declaration = source.to_dict()
        except (OSError, TypeError, ValueError) as exc:
            print("declared native source rejected: " + str(exc), file=sys.stderr)
            return 1
    token = _DECLARED_SOURCE.set(declaration)
    material_token = _ARCHITECTURE_MATERIAL.set(architecture_material)
    try:
        return _native_main(owner_id, main)
    finally:
        _DECLARED_SOURCE.reset(token)
        _ARCHITECTURE_MATERIAL.reset(material_token)


def _native_main(owner_id: str, main: Callable[[], Any]) -> int:
    """Run one existing owner entrypoint and emit its producer evidence."""

    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path.cwd())).resolve()
    owner_key = _valid_text(owner_id).removeprefix("model:")
    if owner_key in _STRICT_NATIVE_OWNER_IDS:
        # Strict scenario owners return the typed tuple directly.  No wrapper
        # globals, stdout parser, existing JSON scan, or exit-code inference
        # is entered for this path.
        try:
            value = main()
            if type(value) is not tuple:
                raise NativeCaseProtocolError(
                    "strict native owner must return an exact tuple"
                )
            typed_results = tuple(value)
            result_path = _write_strict_native_results(
                owner_id,
                typed_results,
                output_dir,
            )
            marker_ids = [row.source_case_id for row in typed_results]
            print(
                "FLOWGUARD_EXECUTED_CASE_IDS="
                + json.dumps(marker_ids, ensure_ascii=False)
            )
            return 0 if all(row.outcome == "pass" for row in typed_results) else 1
        except (OSError, TypeError, ValueError, NativeCaseProtocolError) as exc:
            print(
                "strict native producer rejected: " + str(exc),
                file=sys.stderr,
            )
            return 1
    # Establish the file boundary before entering the owner.  Only files
    # created/replaced by this invocation may contribute JSON case rows;
    # retained output from an earlier invocation is evidence history, not a
    # current native case source.
    output_dir.mkdir(parents=True, exist_ok=True)
    before_json = _json_file_state(output_dir)
    captured = io.StringIO()
    structured_reports: list[Any] = []
    # Existing owner entrypoints return only an integer but call one of the
    # typed report producers below.  Wrap that call for this invocation so the
    # exact returned object is captured without executing the producer twice.
    # The original globals are restored in ``finally`` even when a runner
    # raises, so a long-lived interpreter cannot retain a stale wrapper.
    global_namespace = main.__globals__
    wrapped_globals: list[tuple[str, Any]] = []
    call_stack: list[str] = []
    capture_names = tuple(
        dict.fromkeys(
            (
                "run_review",
                "run_formal_workflow_suite",
                "run_bounded_system_benchmark",
                "run_exact_sequence",
                "run_exact_workflow_case",
            )
            + _OWNER_CAPTURE_FUNCTIONS.get(owner_key, ())
        )
    )
    for name in capture_names:
        original = global_namespace.get(name)
        if not callable(original):
            continue

        def _capture(
            *args: Any,
            __name: str = name,
            __original: Callable[..., Any] = original,
            **kwargs: Any,
        ) -> Any:
            parent = call_stack[-1] if call_stack else ""
            start = len(structured_reports)
            call_stack.append(__name)
            try:
                result = __original(*args, **kwargs)
            finally:
                call_stack.pop()
            nested = tuple(structured_reports[start:])
            structured_reports.append(
                _CapturedCall(
                    function_name=__name,
                    args=tuple(args),
                    kwargs=dict(kwargs),
                    result=result,
                    nested=nested,
                    parent_function=parent,
                )
            )
            return result

        wrapped_globals.append((name, original))
        global_namespace[name] = _capture
    # ``main`` is commonly passed as a function object looked up by the
    # owner's module before this bridge enters ``native_main`` (for example,
    # ``native_main("model:alpha", run_review)``).  Replacing the module
    # global alone therefore does not change that already-resolved object;
    # calling it directly would silently bypass the capture wrapper and lose
    # the producer's structured report graph.  Re-resolve the entrypoint by
    # its registered global name after installing wrappers.  An entrypoint
    # that is not a captured global keeps its original callable identity.
    entrypoint_name = _valid_text(getattr(main, "__name__", ""))
    entrypoint = global_namespace.get(entrypoint_name)
    if not callable(entrypoint):
        entrypoint = main
    exit_code = 1
    try:
        with redirect_stdout(captured):
            try:
                value = entrypoint()
                if isinstance(value, int):
                    exit_code = int(value)
                elif isinstance(value, Mapping) and type(value.get("exit_code")) is int:
                    exit_code = int(value["exit_code"])
                else:
                    exit_code = 0
            except SystemExit as exc:
                value = exc.code
                exit_code = int(value) if isinstance(value, int) else (0 if value in (None, "") else 1)
            except BaseException:
                traceback.print_exc()
                exit_code = 1
    finally:
        for name, original in wrapped_globals:
            global_namespace[name] = original
    stdout = captured.getvalue()
    after_json = _json_file_state(output_dir)
    changed_json = tuple(
        path
        for path, state in after_json.items()
        if before_json.get(path) != state
    )
    cases = _captured_structured_cases(structured_reports, owner_id=owner_id)
    cases += _load_existing_json(output_dir, paths=changed_json) + _collect_text_cases(
        stdout,
        include_metadata=True,
    )
    try:
        stdout_payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        stdout_payload = None
    if isinstance(stdout_payload, (Mapping, list, tuple)):
        _collect_json_cases(stdout_payload, cases)
    else:
        # A few established owner runners deliberately keep their readable
        # transcript and append one compact JSON envelope on its own line.
        # Consume only complete line-shaped JSON values; never attempt to
        # parse arbitrary transcript fragments or infer a case from text.
        for line in stdout.splitlines():
            candidate = line.strip()
            if not candidate or candidate[0] not in "[{":
                continue
            try:
                line_payload = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(line_payload, (Mapping, list, tuple)):
                _collect_json_cases(line_payload, cases)
    cases = _deduplicate_cases(cases, owner_id=owner_id)
    result_path = _write_results(
        owner_id,
        cases,
        stdout,
        exit_code,
        output_dir,
        structured_reports=structured_reports,
    )
    print(stdout, end="")
    # The liveness marker names only rows that were actually written to the
    # authoritative native-result envelope.  In particular, a producer may
    # expose supporting/diagnostic observations that are intentionally kept in
    # ``native-source.json`` but are not blueprint leaves.  Seeding the marker
    # from every captured observation would make the parent demand result rows
    # that the mapping explicitly excludes, turning a visible support record
    # into a false ``native_result_missing`` failure.
    marker_ids: list[str] = []
    # ``_write_results`` may add one explicit finite boundary aggregate after
    # projecting the producer's atomic cases.  Include the exact rows written
    # to the current result envelope in the liveness marker so the parent
    # orchestrator cannot mistake a successfully emitted boundary receipt for
    # a missing execution.  The marker is derived from this invocation's
    # immutable output; it does not discover or invent additional selectors.
    try:
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        result_payload = None
    if isinstance(result_payload, Mapping):
        raw_results = result_payload.get("results")
        if isinstance(raw_results, list):
            for row in raw_results:
                if not isinstance(row, Mapping):
                    continue
                source_case_id = _valid_text(row.get("source_case_id"))
                if source_case_id and source_case_id not in marker_ids:
                    marker_ids.append(source_case_id)
    if not marker_ids:
        marker_ids = ["terminal"]
    print(
        "FLOWGUARD_EXECUTED_CASE_IDS="
        + json.dumps(marker_ids, ensure_ascii=False)
    )
    return exit_code


__all__ = ["native_main"]
