"""Containers for low-friction model-first check orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable
from .risk import RiskProfile


@dataclass(frozen=True)
class ScenarioMatrixConfig:
    """Configuration for optional generated scenario scaffolding."""

    enabled: bool = True
    max_scenarios: int = 12
    max_sequence_length: int | None = None
    include_single_inputs: bool = True
    include_repeat_same: bool = True
    include_pairwise_orders: bool = True
    include_aba: bool = True
    name_prefix: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScenarioMatrixConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            max_scenarios=int(data.get("max_scenarios", 12)),
            max_sequence_length=data.get("max_sequence_length"),
            include_single_inputs=bool(data.get("include_single_inputs", True)),
            include_repeat_same=bool(data.get("include_repeat_same", True)),
            include_pairwise_orders=bool(data.get("include_pairwise_orders", True)),
            include_aba=bool(data.get("include_aba", True)),
            name_prefix=str(data.get("name_prefix", "")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_scenarios": self.max_scenarios,
            "max_sequence_length": self.max_sequence_length,
            "include_single_inputs": self.include_single_inputs,
            "include_repeat_same": self.include_repeat_same,
            "include_pairwise_orders": self.include_pairwise_orders,
            "include_aba": self.include_aba,
            "name_prefix": self.name_prefix,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class FlowGuardCheckPlan:
    """Data container for one optional model-first helper run."""

    workflow: Any
    initial_states: tuple[Any, ...]
    external_inputs: tuple[Any, ...]
    invariants: tuple[Any, ...] = ()
    max_sequence_length: int = 1
    risk_profile: RiskProfile | None = None
    scenarios: tuple[Any, ...] = ()
    contracts: tuple[Any, ...] = ()
    progress_config: Any = None
    conformance_status: str | None = None
    conformance_report: Any = None
    scenario_matrix_config: ScenarioMatrixConfig | None = None
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __init__(
        self,
        *,
        workflow: Any,
        initial_states: Iterable[Any],
        external_inputs: Sequence[Any],
        invariants: Sequence[Any] = (),
        max_sequence_length: int = 1,
        risk_profile: RiskProfile | Mapping[str, Any] | None = None,
        scenarios: Sequence[Any] = (),
        contracts: Sequence[Any] = (),
        progress_config: Any = None,
        conformance_status: str | None = None,
        conformance_report: Any = None,
        scenario_matrix_config: ScenarioMatrixConfig | Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> None:
        object.__setattr__(self, "workflow", workflow)
        object.__setattr__(self, "initial_states", tuple(initial_states))
        object.__setattr__(self, "external_inputs", tuple(external_inputs))
        object.__setattr__(self, "invariants", tuple(invariants))
        object.__setattr__(self, "max_sequence_length", int(max_sequence_length))
        object.__setattr__(self, "risk_profile", _coerce_risk_profile(risk_profile))
        object.__setattr__(self, "scenarios", tuple(scenarios))
        object.__setattr__(self, "contracts", tuple(contracts))
        object.__setattr__(self, "progress_config", progress_config)
        object.__setattr__(self, "conformance_status", conformance_status)
        object.__setattr__(self, "conformance_report", conformance_report)
        object.__setattr__(
            self,
            "scenario_matrix_config",
            _coerce_scenario_matrix_config(scenario_matrix_config),
        )
        object.__setattr__(self, "metadata", freeze_metadata(metadata))

    def format_text(self) -> str:
        lines = [
            "=== flowguard check plan ===",
            f"workflow: {getattr(self.workflow, 'name', type(self.workflow).__name__)}",
            f"initial_states: {len(self.initial_states)}",
            f"external_inputs: {len(self.external_inputs)}",
            f"invariants: {len(self.invariants)}",
            f"max_sequence_length: {self.max_sequence_length}",
            f"scenarios: {len(self.scenarios)}",
            f"contracts: {len(self.contracts)}",
            f"progress_config: {'provided' if self.progress_config is not None else 'not_provided'}",
            f"conformance_status: {self.conformance_status or 'not_provided'}",
        ]
        if self.risk_profile is not None:
            lines.append(f"risk_profile: {self.risk_profile.modeled_boundary}")
        if self.scenario_matrix_config is not None:
            lines.append(
                "scenario_matrix: "
                f"{'enabled' if self.scenario_matrix_config.enabled else 'disabled'}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": getattr(self.workflow, "name", type(self.workflow).__name__),
            "initial_states": to_jsonable(self.initial_states),
            "external_inputs": to_jsonable(self.external_inputs),
            "invariants": [
                {
                    "name": str(getattr(invariant, "name", type(invariant).__name__)),
                    "description": str(getattr(invariant, "description", "")),
                }
                for invariant in self.invariants
            ],
            "max_sequence_length": self.max_sequence_length,
            "risk_profile": self.risk_profile.to_dict() if self.risk_profile else None,
            "scenarios": [str(getattr(scenario, "name", repr(scenario))) for scenario in self.scenarios],
            "contracts": [str(getattr(contract, "function_name", repr(contract))) for contract in self.contracts],
            "progress_config": "provided" if self.progress_config is not None else None,
            "conformance_status": self.conformance_status,
            "conformance_report": to_jsonable(self.conformance_report),
            "scenario_matrix_config": (
                self.scenario_matrix_config.to_dict()
                if self.scenario_matrix_config is not None
                else None
            ),
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _coerce_risk_profile(value: RiskProfile | Mapping[str, Any] | None) -> RiskProfile | None:
    if value is None or isinstance(value, RiskProfile):
        return value
    if isinstance(value, Mapping):
        return RiskProfile.from_dict(value)
    raise TypeError("risk_profile must be a RiskProfile, mapping, or None")


def _coerce_scenario_matrix_config(
    value: ScenarioMatrixConfig | Mapping[str, Any] | None,
) -> ScenarioMatrixConfig | None:
    if value is None or isinstance(value, ScenarioMatrixConfig):
        return value
    if isinstance(value, Mapping):
        return ScenarioMatrixConfig.from_dict(value)
    raise TypeError("scenario_matrix_config must be a ScenarioMatrixConfig, mapping, or None")


__all__ = ["FlowGuardCheckPlan", "ScenarioMatrixConfig"]
