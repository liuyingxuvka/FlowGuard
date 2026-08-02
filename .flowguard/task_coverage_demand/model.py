"""Executable model for task-derived, non-reducible coverage demand.

Run before editing the TaskCoverageDemand runtime or model-maturation intake:
python .flowguard/task_coverage_demand/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    compiler_owner_ids: tuple[str, ...]
    caller_owner_ids: tuple[str, ...] = ()
    unknown_fact_ids: tuple[str, ...] = ()
    satisfied_owner_ids: tuple[str, ...] = ()
    not_triggered_owner_ids: tuple[str, ...] = ()
    blocked_owner_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskFactsFrozen:
    task_id: str
    compiler_owner_ids: tuple[str, ...]
    caller_owner_ids: tuple[str, ...]
    unknown_fact_ids: tuple[str, ...]
    satisfied_owner_ids: tuple[str, ...]
    not_triggered_owner_ids: tuple[str, ...]
    blocked_owner_ids: tuple[str, ...]


@dataclass(frozen=True)
class DemandCompiled:
    task_id: str
    demanded_owner_ids: tuple[str, ...]
    unknown_fact_ids: tuple[str, ...]
    satisfied_owner_ids: tuple[str, ...] = ()
    not_triggered_owner_ids: tuple[str, ...] = ()
    blocked_owner_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DemandResolved:
    task_id: str
    decision: str
    unresolved_owner_ids: tuple[str, ...]


@dataclass(frozen=True)
class Rejected:
    task_id: str
    reason: str


@dataclass(frozen=True)
class State:
    frozen_task_ids: tuple[str, ...] = ()
    compiler_minimums: tuple[tuple[str, tuple[str, ...]], ...] = ()
    demanded_owners: tuple[tuple[str, tuple[str, ...]], ...] = ()
    resolved_task_ids: tuple[str, ...] = ()
    unresolved_by_task: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _lookup(rows: tuple[tuple[str, tuple[str, ...]], ...], task_id: str) -> tuple[str, ...]:
    return next((values for key, values in rows if key == task_id), ())


class FreezeTaskFacts:
    name = "FreezeTaskFacts"
    reads = ()
    writes = ("frozen_task_ids", "compiler_minimums")
    accepted_input_type = TaskRequest
    input_description = "Exact task request and independently derived owner candidates"
    output_description = "Frozen task facts"

    def apply(self, input_obj: TaskRequest, state: State) -> Iterable[FunctionResult]:
        compiler = tuple(sorted(set(input_obj.compiler_owner_ids)))
        if not input_obj.task_id or not compiler:
            yield FunctionResult(Rejected(input_obj.task_id, "task_facts_incomplete"), state, label="facts_rejected")
            return
        yield FunctionResult(
            TaskFactsFrozen(
                input_obj.task_id,
                compiler,
                tuple(sorted(set(input_obj.caller_owner_ids))),
                tuple(sorted(set(input_obj.unknown_fact_ids))),
                tuple(sorted(set(input_obj.satisfied_owner_ids))),
                tuple(sorted(set(input_obj.not_triggered_owner_ids))),
                tuple(sorted(set(input_obj.blocked_owner_ids))),
            ),
            replace(
                state,
                frozen_task_ids=state.frozen_task_ids + (input_obj.task_id,),
                compiler_minimums=state.compiler_minimums + ((input_obj.task_id, compiler),),
            ),
            label="task_facts_frozen",
        )


class CompileCoverageDemand:
    name = "CompileCoverageDemand"
    reads = ("frozen_task_ids", "compiler_minimums")
    writes = ("demanded_owners",)
    accepted_input_type = TaskFactsFrozen
    input_description = "Frozen task facts"
    output_description = "Non-reducible coverage demand"

    def apply(self, input_obj: TaskFactsFrozen, state: State) -> Iterable[FunctionResult]:
        if input_obj.task_id not in state.frozen_task_ids:
            yield FunctionResult(Rejected(input_obj.task_id, "task_not_frozen"), state, label="demand_rejected")
            return
        demanded = tuple(sorted(set(input_obj.compiler_owner_ids) | set(input_obj.caller_owner_ids)))
        yield FunctionResult(
            DemandCompiled(
                input_obj.task_id,
                demanded,
                input_obj.unknown_fact_ids,
                input_obj.satisfied_owner_ids,
                input_obj.not_triggered_owner_ids,
                input_obj.blocked_owner_ids,
            ),
            replace(state, demanded_owners=state.demanded_owners + ((input_obj.task_id, demanded),)),
            label="coverage_demand_compiled",
        )


class ResolveCoverageDemand:
    name = "ResolveCoverageDemand"
    reads = ("demanded_owners",)
    writes = ("resolved_task_ids", "unresolved_by_task")
    accepted_input_type = DemandCompiled
    input_description = "Compiled demand and exact owner evidence"
    output_description = "Closed or blocked demand disposition"

    def apply(self, input_obj: DemandCompiled, state: State) -> Iterable[FunctionResult]:
        demand = input_obj
        demanded = set(_lookup(state.demanded_owners, demand.task_id))
        satisfied = set(demand.satisfied_owner_ids)
        not_triggered = set(demand.not_triggered_owner_ids)
        blocked = set(demand.blocked_owner_ids)
        dispositions = satisfied | not_triggered | blocked
        overlap = (satisfied & not_triggered) | (satisfied & blocked) | (not_triggered & blocked)
        if overlap or not dispositions.issubset(demanded):
            yield FunctionResult(Rejected(demand.task_id, "invalid_owner_disposition"), state, label="resolution_rejected")
            return
        unresolved = tuple(sorted(demanded - dispositions))
        if demand.unknown_fact_ids:
            unresolved = tuple(sorted(set(unresolved) | {"coverage-demand-owner"}))
        decision = "closed" if not unresolved and not blocked else "blocked"
        next_state = replace(
            state,
            unresolved_by_task=state.unresolved_by_task + ((demand.task_id, unresolved),),
            resolved_task_ids=(
                state.resolved_task_ids + (demand.task_id,)
                if decision == "closed"
                else state.resolved_task_ids
            ),
        )
        yield FunctionResult(
            DemandResolved(demand.task_id, decision, unresolved),
            next_state,
            label="coverage_demand_closed" if decision == "closed" else "coverage_demand_blocked",
        )


class BrokenCallerOnlyCompiler(CompileCoverageDemand):
    name = "BrokenCallerOnlyCompiler"

    def apply(self, input_obj: TaskFactsFrozen, state: State) -> Iterable[FunctionResult]:
        demanded = tuple(sorted(set(input_obj.caller_owner_ids)))
        yield FunctionResult(
            DemandCompiled(
                input_obj.task_id,
                demanded,
                input_obj.unknown_fact_ids,
                input_obj.satisfied_owner_ids,
                input_obj.not_triggered_owner_ids,
                input_obj.blocked_owner_ids,
            ),
            replace(state, demanded_owners=state.demanded_owners + ((input_obj.task_id, demanded),)),
            label="caller_reduced_coverage",
        )


def demand_preserves_compiler_minimum(state: State, _trace) -> InvariantResult:
    for task_id, minimum in state.compiler_minimums:
        demanded = set(_lookup(state.demanded_owners, task_id))
        missing = set(minimum) - demanded
        if missing:
            return InvariantResult.fail(f"compiler minimum removed for {task_id}: {sorted(missing)!r}")
    return InvariantResult.pass_()


def closed_tasks_have_no_unresolved_owners(state: State, _trace) -> InvariantResult:
    for task_id in state.resolved_task_ids:
        if _lookup(state.unresolved_by_task, task_id):
            return InvariantResult.fail(f"closed task has unresolved owners: {task_id}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("demand_preserves_compiler_minimum", "callers cannot reduce compiler-derived coverage", demand_preserves_compiler_minimum),
    Invariant("closed_tasks_have_no_unresolved_owners", "closure requires every demanded owner disposition", closed_tasks_have_no_unresolved_owners),
)

REQUEST = TaskRequest(
    "task:upgrade-understanding",
    ("existing-model-preflight", "model-maturation", "development-process-flow"),
    ("model-maturation",),
    satisfied_owner_ids=("existing-model-preflight", "model-maturation", "development-process-flow"),
)
EXTERNAL_INPUTS = (REQUEST,)
MAX_SEQUENCE_LENGTH = 3


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow((FreezeTaskFacts(), CompileCoverageDemand(), ResolveCoverageDemand()), name="task_coverage_demand")


def broken_caller_only_workflow() -> Workflow:
    return Workflow((FreezeTaskFacts(), BrokenCallerOnlyCompiler(), ResolveCoverageDemand()), name="broken_caller_only_demand")


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (DemandResolved, Rejected))


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
