"""Three finite families that separate local/token green from system evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from flowguard.portable_model import PortableModel, PortableState, PortableTransition
from flowguard.portable_system import PortableSystemDefinition, SystemComponentRef, SystemCompositionRequest, SystemDependency, SystemProperty, SystemStatePattern, SystemStep, SystemTransitionRef
from flowguard.system_composition import SystemCompositionReport, check_system_composition


@dataclass(frozen=True)
class BenchmarkCaseResult:
    family_id: str
    case_id: str
    expected_status: str
    report: SystemCompositionReport

    @property
    def ok(self) -> bool:
        return self.report.status == self.expected_status

    def to_dict(self) -> dict[str, Any]:
        return {"family_id": self.family_id, "case_id": self.case_id, "expected_status": self.expected_status, "observed_status": self.report.status, "ok": self.ok, "local_status": self.report.stages.get("component_local", "not_run"), "contract_status": self.report.stages.get("contract_composition", "not_run"), "trace_length": len(self.report.counterexamples[0].steps) if self.report.counterexamples else 0, "affected_component_count": len(self.report.affected_component_ids), "involved_component_count": len(self.report.involved_component_ids), "explored_state_count": self.report.explored_state_count}


@dataclass(frozen=True)
class BoundedSystemBenchmarkReport:
    cases: tuple[BenchmarkCaseResult, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "flowguard.bounded_system_benchmark.v1", "status": "pass" if self.ok else "fail", "ok": self.ok,
            "family_count": len({item.family_id for item in self.cases}), "case_count": len(self.cases),
            "local_green_case_count": sum(item.report.stages.get("component_local") == "pass" for item in self.cases),
            "executable_failure_count": sum(item.report.status == "fail" for item in self.cases),
            "false_finding_count": sum(item.report.status != item.expected_status for item in self.cases),
            "cases": [item.to_dict() for item in self.cases],
            "claim_boundary": "The benchmark covers twelve declared finite variants across three representative interaction families; it does not establish arbitrary future or production correctness.",
        }

    def to_json_text(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def format_text(self) -> str:
        payload = self.to_dict()
        return f"bounded_system_benchmark: {payload['status']} families={payload['family_count']} cases={payload['case_count']} false_findings={payload['false_finding_count']}"


FAMILIES = {
    "payment-order-retry-identity": ("payment", "order"),
    "permission-revocation-cache": ("permission", "cache"),
    "deletion-index-export": ("deletion", "index", "export"),
}


def _component(component_id: str, first: bool) -> PortableModel:
    source = "ready" if first else "pending"
    transition_id = f"{component_id}-advance"
    return PortableModel(component_id + "-model", (PortableState(source), PortableState("done")), (PortableTransition(transition_id, source, transition_id, transition_id, "done"),), (source,), ("done",))


def _case(family_id: str, component_ids: tuple[str, ...], variant: str) -> BenchmarkCaseResult:
    models = tuple(_component(component_id, index == 0) for index, component_id in enumerate(component_ids))
    refs = tuple(SystemComponentRef(component_id, model.model_id, model.fingerprint) for component_id, model in zip(component_ids, models))
    if variant == "repaired":
        steps = (SystemStep("atomic-repair", tuple(SystemTransitionRef(component_id, f"{component_id}-advance") for component_id in component_ids)),)
    else:
        steps = tuple(SystemStep(f"step-{component_id}", (SystemTransitionRef(component_id, f"{component_id}-advance"),)) for component_id in component_ids)
    initial = tuple((component_id, "ready" if index == 0 else "pending") for index, component_id in enumerate(component_ids))
    unsafe = ((component_ids[0], "done"),) + tuple((component_id, "pending") for component_id in component_ids[1:])
    definition = PortableSystemDefinition(
        family_id, refs,
        tuple(SystemDependency(f"dep-{component_ids[index]}-{component_ids[index + 1]}", component_ids[index], component_ids[index + 1], family_id) for index in range(len(component_ids) - 1)),
        (), (), (), steps,
        (SystemStatePattern("initial", initial), SystemStatePattern("unsafe", unsafe)),
        (SystemProperty("system-safety", f"owner:{component_ids[0]}", "safety", target_pattern_ids=("unsafe",)),),
        unresolved_dependency_ids=("missing-semantics",) if variant == "missing-semantics" else (),
        discovery_evidence_id=f"benchmark:{family_id}",
    )
    bound = 1 if variant == "truncated" else 100
    request = SystemCompositionRequest(f"{family_id}:{variant}", definition.system_id, definition.fingerprint, (component_ids[0],), max_states=bound)
    expected = {"bad": "fail", "repaired": "pass", "missing-semantics": "blocked", "truncated": "blocked"}[variant]
    return BenchmarkCaseResult(family_id, variant, expected, check_system_composition(definition, request, models))


def run_bounded_system_benchmark() -> BoundedSystemBenchmarkReport:
    return BoundedSystemBenchmarkReport(tuple(_case(family_id, component_ids, variant) for family_id, component_ids in FAMILIES.items() for variant in ("bad", "repaired", "missing-semantics", "truncated")))


__all__ = ["BenchmarkCaseResult", "BoundedSystemBenchmarkReport", "FAMILIES", "run_bounded_system_benchmark"]

