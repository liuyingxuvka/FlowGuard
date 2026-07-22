"""Compile and check one declared bounded system through the canonical checker."""

from __future__ import annotations

import itertools
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .portable_checker import PortableCheckReport, check_composition, check_portable_model
from .portable_model import PortableInvariant, PortableModel, PortableState, PortableTemporalObligation, PortableTransition, canonical_identity
from .portable_system import PortableSystemDefinition, PortableSystemSlice, SystemCompositionRequest, derive_system_slice, validate_system_components


SYSTEM_COMPOSITION_STATUSES = ("pass", "fail", "blocked", "invalid")


@dataclass(frozen=True)
class SystemTraceStep:
    system_step_id: str
    compiled_transition_id: str
    component_transition_ids: tuple[str, ...]
    before_component_states: tuple[tuple[str, str], ...]
    after_component_states: tuple[tuple[str, str], ...]
    relation_ids: tuple[str, ...] = ()
    code_targets: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"system_step_id": self.system_step_id, "compiled_transition_id": self.compiled_transition_id, "component_transition_ids": list(self.component_transition_ids), "before_component_states": [list(item) for item in self.before_component_states], "after_component_states": [list(item) for item in self.after_component_states], "relation_ids": list(self.relation_ids), "code_targets": list(self.code_targets)}


@dataclass(frozen=True)
class SystemCounterexample:
    initial_component_states: tuple[tuple[str, str], ...]
    steps: tuple[SystemTraceStep, ...]
    terminal_component_states: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {"initial_component_states": [list(item) for item in self.initial_component_states], "steps": [item.to_dict() for item in self.steps], "terminal_component_states": [list(item) for item in self.terminal_component_states]}


@dataclass(frozen=True)
class SystemCompositionReport:
    status: str
    system_id: str
    system_fingerprint: str
    request_fingerprint: str
    slice_fingerprint: str = ""
    compiled_model_fingerprint: str = ""
    stages: Mapping[str, str] = field(default_factory=dict, compare=False)
    component_reports: tuple[PortableCheckReport, ...] = ()
    contract_report: PortableCheckReport | None = None
    system_report: PortableCheckReport | None = None
    counterexamples: tuple[SystemCounterexample, ...] = ()
    blockers: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    explored_state_count: int = 0
    frontier_ids: tuple[str, ...] = ()
    involved_component_ids: tuple[str, ...] = ()
    affected_component_ids: tuple[str, ...] = ()
    residual_risk: tuple[str, ...] = ()
    claim_boundary: str = "Bounded system composition covers only the exact declared graph, selected finite slice, and supplied current portable models; undeclared production dependencies and domain truth require separate evidence."

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_system_composition_report", "status": self.status, "ok": self.ok,
            "system_id": self.system_id, "system_fingerprint": self.system_fingerprint, "request_fingerprint": self.request_fingerprint,
            "slice_fingerprint": self.slice_fingerprint, "compiled_model_fingerprint": self.compiled_model_fingerprint,
            "stages": dict(self.stages), "component_reports": [item.to_dict() for item in self.component_reports],
            "contract_report": self.contract_report.to_dict() if self.contract_report else None,
            "system_report": self.system_report.to_dict() if self.system_report else None,
            "counterexamples": [item.to_dict() for item in self.counterexamples], "blockers": list(self.blockers), "findings": list(self.findings),
            "explored_state_count": self.explored_state_count, "frontier_ids": list(self.frontier_ids),
            "involved_component_ids": list(self.involved_component_ids), "affected_component_ids": list(self.affected_component_ids),
            "residual_risk": list(self.residual_risk), "claim_boundary": self.claim_boundary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = ["=== flowguard portable system check ===", f"status: {self.status}", f"system: {self.system_id}", f"definition: {self.system_fingerprint}", f"request: {self.request_fingerprint}", f"slice: {self.slice_fingerprint or 'not_run'}", f"explored_states: {self.explored_state_count}"]
        lines.extend(f"stage:{name}: {status}" for name, status in sorted(self.stages.items()))
        lines.extend(f"blocker: {item}" for item in self.blockers)
        lines.extend(f"finding: {item}" for item in self.findings)
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _Compilation:
    model: PortableModel
    state_vectors: Mapping[str, tuple[tuple[str, str], ...]]
    transition_metadata: Mapping[str, SystemTraceStep]
    complete: bool
    frontier_ids: tuple[str, ...]


def _joint_state_id(vector: tuple[tuple[str, str], ...]) -> str:
    return "joint:" + canonical_identity([list(item) for item in vector]).split(":", 1)[1][:24]


def _matches(vector: tuple[tuple[str, str], ...], pattern: tuple[tuple[str, str], ...]) -> bool:
    current = dict(vector)
    return all(current.get(component_id) == state_id for component_id, state_id in pattern)


def _compile(
    system: PortableSystemDefinition,
    request: SystemCompositionRequest,
    slice_: PortableSystemSlice,
    models: Sequence[PortableModel],
) -> _Compilation:
    refs = {item.component_id: item for item in system.components if item.component_id in slice_.included_component_ids}
    by_model_id = {item.model_id: item for item in models}
    component_models = {component_id: by_model_id[ref.model_id] for component_id, ref in refs.items()}
    component_order = tuple(sorted(component_models))
    transition_lookup = {(component_id, item.transition_id): item for component_id, model in component_models.items() for item in model.transitions}
    selected_steps = tuple(step for step in system.steps if all(ref.component_id in component_models for ref in step.transition_refs))
    initial_vectors = tuple(tuple(zip(component_order, states)) for states in itertools.product(*(component_models[component_id].initial_state_ids for component_id in component_order)))
    if len(initial_vectors) > request.max_states:
        empty = PortableModel(model_id=f"system:{system.system_id}:empty", states=(PortableState("overflow", {}),), transitions=(), initial_state_ids=("overflow",))
        return _Compilation(empty, {"overflow": ()}, {}, False, ("initial-state-product-exceeds-bound",))
    vectors_by_id: dict[str, tuple[tuple[str, str], ...]] = {}
    queue: deque[tuple[tuple[str, str], ...]] = deque()
    for vector in initial_vectors:
        state_id = _joint_state_id(vector)
        vectors_by_id[state_id] = vector
        queue.append(vector)
    transitions: list[PortableTransition] = []
    transition_metadata: dict[str, SystemTraceStep] = {}
    frontier: set[str] = set()
    while queue:
        vector = queue.popleft()
        source_id = _joint_state_id(vector)
        current = dict(vector)
        for step in selected_steps:
            resolved = tuple((ref, transition_lookup[(ref.component_id, ref.transition_id)]) for ref in step.transition_refs)
            if any(current[ref.component_id] != transition.source_state for ref, transition in resolved):
                continue
            next_state = dict(current)
            for ref, transition in resolved:
                next_state[ref.component_id] = transition.target_state
            target_vector = tuple(sorted(next_state.items()))
            target_id = _joint_state_id(target_vector)
            if target_id not in vectors_by_id and len(vectors_by_id) >= request.max_states:
                frontier.add(canonical_identity({"source": source_id, "step": step.step_id, "target": [list(item) for item in target_vector]}))
                continue
            if target_id not in vectors_by_id:
                vectors_by_id[target_id] = target_vector
                queue.append(target_vector)
            transition_id = f"joint-step:{step.step_id}:{source_id[6:]}:{target_id[6:]}"
            transition = PortableTransition(transition_id, source_id, {"system_step_id": step.step_id}, {"component_transition_ids": [ref.transition_id for ref, _item in resolved]}, target_id, step.step_id)
            transitions.append(transition)
            transition_metadata[transition_id] = SystemTraceStep(step.step_id, transition_id, tuple(f"{ref.component_id}:{ref.transition_id}" for ref, _item in resolved), vector, target_vector, step.relation_ids, step.code_targets)
    patterns = {item.pattern_id: item.component_states for item in system.state_patterns}
    selected_properties = tuple(item for item in system.properties if item.property_id in slice_.selected_property_ids)
    invariants: list[PortableInvariant] = []
    obligations: list[PortableTemporalObligation] = []
    for prop in selected_properties:
        triggers = tuple(sorted(state_id for state_id, vector in vectors_by_id.items() if any(_matches(vector, patterns[pattern_id]) for pattern_id in prop.trigger_pattern_ids)))
        targets = tuple(sorted(state_id for state_id, vector in vectors_by_id.items() if any(_matches(vector, patterns[pattern_id]) for pattern_id in prop.target_pattern_ids)))
        if prop.kind == "safety":
            invariants.append(PortableInvariant(prop.property_id, targets, f"system property owner={prop.owner_id}"))
        elif not frontier:
            transition_ids = tuple(sorted(transition_id for transition_id, metadata in transition_metadata.items() if metadata.system_step_id in prop.step_ids))
            obligations.append(PortableTemporalObligation(prop.property_id, prop.kind, triggers, targets, transition_ids, prop.max_steps, f"system property owner={prop.owner_id}"))
    terminal_ids = tuple(sorted(state_id for state_id, vector in vectors_by_id.items() if all(state_id_local in component_models[component_id].terminal_state_ids for component_id, state_id_local in vector)))
    compiled = PortableModel(
        model_id=f"system:{system.system_id}:{slice_.fingerprint.split(':', 1)[1][:16]}",
        states=tuple(PortableState(state_id, {"components": [list(item) for item in vector]}) for state_id, vector in sorted(vectors_by_id.items())),
        transitions=tuple(sorted(transitions, key=lambda item: item.transition_id)),
        initial_state_ids=tuple(sorted(_joint_state_id(vector) for vector in initial_vectors)), terminal_state_ids=terminal_ids,
        invariants=tuple(invariants), temporal_obligations=tuple(obligations),
        metadata={"system_id": system.system_id, "scheduler_policy": system.scheduler_policy},
    )
    return _Compilation(compiled, vectors_by_id, transition_metadata, not frontier, tuple(sorted(frontier)))


def _safety_only(model: PortableModel) -> PortableModel:
    return PortableModel(model_id=model.model_id + ":safety-witness", states=model.states, transitions=model.transitions, initial_state_ids=model.initial_state_ids, terminal_state_ids=model.terminal_state_ids, invariants=model.invariants, metadata=model.metadata)


def _map_counterexamples(report: PortableCheckReport, compilation: _Compilation) -> tuple[SystemCounterexample, ...]:
    mapped: list[SystemCounterexample] = []
    for trace in report.counterexamples:
        steps = tuple(compilation.transition_metadata[item.transition_id] for item in trace.steps if item.transition_id in compilation.transition_metadata)
        mapped.append(SystemCounterexample(compilation.state_vectors.get(trace.initial_state, ()), steps, compilation.state_vectors.get(trace.terminal_state, ())))
    return tuple(mapped)


def _early_report(status: str, system: PortableSystemDefinition, request: SystemCompositionRequest, *, stages: Mapping[str, str], slice_: PortableSystemSlice | None = None, blockers: Sequence[str] = (), findings: Sequence[str] = (), component_reports: Sequence[PortableCheckReport] = (), contract_report: PortableCheckReport | None = None) -> SystemCompositionReport:
    return SystemCompositionReport(status, system.system_id, system.fingerprint, request.fingerprint, slice_.fingerprint if slice_ else "", stages=dict(stages), component_reports=tuple(component_reports), contract_report=contract_report, blockers=tuple(blockers), findings=tuple(findings), affected_component_ids=slice_.included_component_ids if slice_ else ())


def check_system_composition(system: PortableSystemDefinition, request: SystemCompositionRequest, models: Sequence[PortableModel]) -> SystemCompositionReport:
    stages = {"component_local": "not_run", "contract_composition": "not_run", "affected_slice": "not_run", "system_composition": "not_run"}
    component_errors = validate_system_components(system, models)
    stale = tuple(item for item in component_errors if "fingerprint is stale" in item)
    invalid = tuple(item for item in component_errors if item not in stale)
    if invalid:
        return _early_report("invalid", system, request, stages=stages, findings=invalid, blockers=stale)
    if stale:
        return _early_report("blocked", system, request, stages=stages, blockers=stale)
    slice_ = derive_system_slice(system, request)
    stages["affected_slice"] = "pass" if slice_.complete else "blocked"
    if not slice_.complete:
        return _early_report("blocked", system, request, stages=stages, slice_=slice_, blockers=slice_.blockers)
    selected_model_ids = {item.model_id for item in system.components if item.component_id in slice_.included_component_ids}
    selected_models = tuple(item for item in models if item.model_id in selected_model_ids)
    component_reports = tuple(check_portable_model(item) for item in selected_models)
    component_status = "pass"
    for candidate in ("invalid", "blocked", "fail"):
        if any(item.status == candidate for item in component_reports):
            component_status = candidate
            break
    stages["component_local"] = component_status
    if component_status != "pass":
        return _early_report(component_status, system, request, stages=stages, slice_=slice_, component_reports=component_reports, findings=("one or more component-local checks did not pass",))
    contract_report = check_composition(selected_models, environment_guarantees=request.environment_guarantees)
    stages["contract_composition"] = contract_report.status
    if contract_report.status != "pass":
        return _early_report(contract_report.status, system, request, stages=stages, slice_=slice_, component_reports=component_reports, contract_report=contract_report, findings=("assumption/provider or declared-conflict composition did not pass",))
    compilation = _compile(system, request, slice_, selected_models)
    if not compilation.complete:
        safety_model = _safety_only(compilation.model)
        reachable_forbidden = any(invariant.forbidden_state_ids for invariant in safety_model.invariants)
        if not reachable_forbidden:
            stages["system_composition"] = "blocked"
            return SystemCompositionReport("blocked", system.system_id, system.fingerprint, request.fingerprint, slice_.fingerprint, compilation.model.fingerprint, stages, component_reports, contract_report, None, blockers=("joint exploration reached max_states with an unexplored frontier",), explored_state_count=len(compilation.model.states), frontier_ids=compilation.frontier_ids, affected_component_ids=slice_.included_component_ids, residual_risk=("Temporal and clean results are unavailable because the joint graph is incomplete.",))
        final_report = check_portable_model(safety_model, max_states=max(1, len(safety_model.states) + 1))
        if final_report.status != "fail":
            stages["system_composition"] = "blocked"
            return SystemCompositionReport("blocked", system.system_id, system.fingerprint, request.fingerprint, slice_.fingerprint, compilation.model.fingerprint, stages, component_reports, contract_report, final_report, blockers=("truncated safety candidate was not confirmed by the canonical checker",), explored_state_count=len(compilation.model.states), frontier_ids=compilation.frontier_ids, affected_component_ids=slice_.included_component_ids)
        stages["system_composition"] = "fail"
        mapped = _map_counterexamples(final_report, compilation)
        involved = tuple(sorted({step.component_transition_ids[index].split(":", 1)[0] for item in mapped for step in item.steps for index in range(len(step.component_transition_ids))}))
        return SystemCompositionReport("fail", system.system_id, system.fingerprint, request.fingerprint, slice_.fingerprint, compilation.model.fingerprint, stages, component_reports, contract_report, final_report, mapped, findings=("canonical checker confirmed a reachable safety violation before truncation",), explored_state_count=len(compilation.model.states), frontier_ids=compilation.frontier_ids, involved_component_ids=involved, affected_component_ids=slice_.included_component_ids, residual_risk=("The safety witness is valid; other unexplored behavior remains residual risk.",))
    final_report = check_portable_model(compilation.model, max_states=max(1, len(compilation.model.states) + 1))
    stages["system_composition"] = final_report.status
    mapped = _map_counterexamples(final_report, compilation)
    involved = tuple(sorted({transition.split(":", 1)[0] for item in mapped for step in item.steps for transition in step.component_transition_ids}))
    return SystemCompositionReport(final_report.status, system.system_id, system.fingerprint, request.fingerprint, slice_.fingerprint, compilation.model.fingerprint, stages, component_reports, contract_report, final_report, mapped, findings=tuple(item.message for item in final_report.findings), explored_state_count=len(compilation.model.states), involved_component_ids=involved, affected_component_ids=slice_.included_component_ids, residual_risk=("Passing evidence is bounded to the complete declared finite joint graph.",) if final_report.status == "pass" else ())


__all__ = ["SYSTEM_COMPOSITION_STATUSES", "SystemCompositionReport", "SystemCounterexample", "SystemTraceStep", "check_system_composition"]
