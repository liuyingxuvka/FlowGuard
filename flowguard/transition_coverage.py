"""Transition coverage matrix helpers.

The helpers in this module turn modeled transitions into explicit evidence
targets. They are intentionally small: Model-Test Alignment still decides
semantic coverage and TestMesh still decides parent/child evidence freshness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .model_test_alignment import CodeContract, ModelObligation, TEST_KIND_HAPPY_PATH

TRANSITION_COVERAGE_OBLIGATION_TYPE = "transition_coverage"
TRANSITION_COVERAGE_OBLIGATION_PREFIX = "transition"
TRANSITION_COVERAGE_SOURCE_MODEL = "model"
TRANSITION_COVERAGE_SOURCE_UI = "ui_flow_structure"
TRANSITION_COVERAGE_SOURCE_WORKFLOW = "workflow_step_contracts"
TRANSITION_COVERAGE_SOURCE_LEAF_BOUNDARY = "leaf_boundary_matrix"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def transition_obligation_id(cell_id: str, *, prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX) -> str:
    """Return the default Model-Test Alignment obligation id for a cell."""

    normalized = str(cell_id)
    normalized_prefix = str(prefix)
    return f"{normalized_prefix}:{normalized}" if normalized_prefix else normalized


@dataclass(frozen=True)
class TransitionCoverageCell:
    """One modeled transition that should be backed by test evidence."""

    cell_id: str
    source_state: str
    trigger: str
    target_state: str
    expected_output: str = ""
    function_block: str = ""
    code_contract_id: str = ""
    runtime_node_id: str = ""
    risk_class: str = "normal"
    required_test_kinds: tuple[str, ...] = (TEST_KIND_HAPPY_PATH,)
    side_effects: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_id", str(self.cell_id))
        object.__setattr__(self, "source_state", str(self.source_state))
        object.__setattr__(self, "trigger", str(self.trigger))
        object.__setattr__(self, "target_state", str(self.target_state))
        object.__setattr__(self, "expected_output", str(self.expected_output))
        object.__setattr__(self, "function_block", str(self.function_block))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "runtime_node_id", str(self.runtime_node_id))
        object.__setattr__(self, "risk_class", str(self.risk_class))
        object.__setattr__(self, "required_test_kinds", _as_tuple(self.required_test_kinds))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_model_obligation(
        self,
        *,
        prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX,
        required: bool = True,
        allow_shared_evidence: bool = False,
    ) -> ModelObligation:
        """Project this cell into a Model-Test Alignment obligation."""

        description = self.rationale or (
            f"{self.source_state} + {self.trigger} -> {self.target_state}"
        )
        external_outputs = (self.expected_output,) if self.expected_output else ()
        return ModelObligation(
            transition_obligation_id(self.cell_id, prefix=prefix),
            obligation_type=TRANSITION_COVERAGE_OBLIGATION_TYPE,
            description=description,
            required=required,
            required_test_kinds=self.required_test_kinds,
            risk_level=self.risk_class,
            allow_shared_evidence=allow_shared_evidence,
            external_inputs=(self.trigger,),
            external_outputs=external_outputs,
            state_reads=(self.source_state,),
            state_writes=(self.target_state,),
            side_effects=self.side_effects,
            required_runtime_node_ids=(self.runtime_node_id,) if self.runtime_node_id else (),
        )

    def to_code_contract(
        self,
        *,
        prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX,
    ) -> CodeContract | None:
        """Project this cell into its owner code contract when one is declared."""

        if not self.code_contract_id:
            return None
        external_outputs = (self.expected_output,) if self.expected_output else ()
        return CodeContract(
            self.code_contract_id,
            symbol=self.function_block,
            implements_obligations=(transition_obligation_id(self.cell_id, prefix=prefix),),
            external_inputs=(self.trigger,),
            external_outputs=external_outputs,
            state_reads=(self.source_state,),
            state_writes=(self.target_state,),
            side_effects=self.side_effects,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "source_state": self.source_state,
            "trigger": self.trigger,
            "target_state": self.target_state,
            "expected_output": self.expected_output,
            "function_block": self.function_block,
            "code_contract_id": self.code_contract_id,
            "runtime_node_id": self.runtime_node_id,
            "risk_class": self.risk_class,
            "required_test_kinds": list(self.required_test_kinds),
            "side_effects": list(self.side_effects),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class TransitionCoverageMatrix:
    """A finite set of transition coverage cells for one model boundary."""

    matrix_id: str
    model_id: str = ""
    source_route: str = TRANSITION_COVERAGE_SOURCE_MODEL
    cells: tuple[TransitionCoverageCell, ...] = ()
    scoped_out_cell_reasons: Mapping[str, str] = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix_id", str(self.matrix_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "cells", tuple(self.cells))
        object.__setattr__(
            self,
            "scoped_out_cell_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_out_cell_reasons).items()},
        )
        object.__setattr__(self, "rationale", str(self.rationale))

    def required_cells(self) -> tuple[TransitionCoverageCell, ...]:
        scoped_out = set(self.scoped_out_cell_reasons)
        return tuple(cell for cell in self.cells if cell.cell_id not in scoped_out)

    def required_cell_ids(self) -> tuple[str, ...]:
        return _unique([cell.cell_id for cell in self.required_cells()])

    def to_model_obligations(
        self,
        *,
        prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX,
        allow_shared_evidence: bool = False,
    ) -> tuple[ModelObligation, ...]:
        return tuple(
            cell.to_model_obligation(
                prefix=prefix,
                allow_shared_evidence=allow_shared_evidence,
            )
            for cell in self.required_cells()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "model_id": self.model_id,
            "source_route": self.source_route,
            "cells": [cell.to_dict() for cell in self.cells],
            "scoped_out_cell_reasons": to_jsonable(dict(self.scoped_out_cell_reasons)),
            "rationale": self.rationale,
        }


def transition_coverage_to_model_obligations(
    matrix: TransitionCoverageMatrix,
    *,
    prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX,
    allow_shared_evidence: bool = False,
) -> tuple[ModelObligation, ...]:
    """Project matrix cells into Model-Test Alignment obligations."""

    return matrix.to_model_obligations(prefix=prefix, allow_shared_evidence=allow_shared_evidence)


def transition_coverage_to_required_leaf_cell_ids(matrix: TransitionCoverageMatrix) -> tuple[str, ...]:
    """Project matrix cells into TestMesh required leaf-cell ids."""

    return matrix.required_cell_ids()


def transition_coverage_to_code_contracts(
    matrix: TransitionCoverageMatrix,
    *,
    prefix: str = TRANSITION_COVERAGE_OBLIGATION_PREFIX,
) -> tuple[CodeContract, ...]:
    """Project matrix cells with declared code ids into CodeContract rows."""

    contracts: list[CodeContract] = []
    for cell in matrix.required_cells():
        contract = cell.to_code_contract(prefix=prefix)
        if contract is not None:
            contracts.append(contract)
    return tuple(contracts)


def ui_interaction_model_to_transition_coverage(
    model: Any,
    *,
    matrix_id: str = "",
    required_test_kinds: Sequence[str] = (TEST_KIND_HAPPY_PATH,),
    risk_class: str = "normal",
) -> TransitionCoverageMatrix:
    """Project a UIInteractionModel-like object into a transition matrix."""

    cells: list[TransitionCoverageCell] = []
    for transition in getattr(model, "transitions", ()):
        event_id = str(getattr(transition, "event_id", ""))
        source_state = str(getattr(transition, "source_state_id", ""))
        target_state = str(getattr(transition, "target_state_id", ""))
        cell_id = f"{source_state}.{event_id}->{target_state}"
        cells.append(
            TransitionCoverageCell(
                cell_id=cell_id,
                source_state=source_state,
                trigger=event_id,
                target_state=target_state,
                expected_output=str(getattr(transition, "output", "")),
                function_block=str(getattr(transition, "function_block", "")),
                code_contract_id=str(getattr(transition, "code_contract_id", "")),
                runtime_node_id=str(getattr(transition, "runtime_node_id", "")),
                risk_class=risk_class,
                required_test_kinds=tuple(required_test_kinds),
                side_effects=tuple(getattr(transition, "side_effects", ())),
                rationale=str(getattr(transition, "rationale", "")),
            )
        )
    resolved_matrix_id = matrix_id or f"{getattr(model, 'model_id', 'ui')}:transition-coverage"
    return TransitionCoverageMatrix(
        resolved_matrix_id,
        model_id=str(getattr(model, "model_id", "")),
        source_route=TRANSITION_COVERAGE_SOURCE_UI,
        cells=tuple(cells),
    )


__all__ = [
    "TRANSITION_COVERAGE_OBLIGATION_PREFIX",
    "TRANSITION_COVERAGE_OBLIGATION_TYPE",
    "TRANSITION_COVERAGE_SOURCE_LEAF_BOUNDARY",
    "TRANSITION_COVERAGE_SOURCE_MODEL",
    "TRANSITION_COVERAGE_SOURCE_UI",
    "TRANSITION_COVERAGE_SOURCE_WORKFLOW",
    "TransitionCoverageCell",
    "TransitionCoverageMatrix",
    "transition_coverage_to_code_contracts",
    "transition_coverage_to_model_obligations",
    "transition_coverage_to_required_leaf_cell_ids",
    "transition_obligation_id",
    "ui_interaction_model_to_transition_coverage",
]
