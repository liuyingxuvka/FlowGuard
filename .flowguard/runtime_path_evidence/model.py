"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the Runtime Path Evidence upgrade before production helper changes.

Guards against:
- claiming real-code or parent-model confidence without leaf runtime node
  observations;
- parent meshes consuming stale child path evidence;
- closure contract promoting scoped or missing runtime path alignment to full
  confidence;
- treating ad hoc logs as structured runtime path evidence.

Use before editing:
runtime path evidence helpers, model-test alignment runtime rows, layered
boundary proof leaf evidence, hierarchical mesh reattachment, runtime gateway
bindings, closure contract, templates, docs, or skill prompts.

Run:
python .flowguard/runtime_path_evidence/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class State:
    contract_declared: bool = False
    expected_inventory_declared: bool = False
    stable_authority_bound: bool = False
    leaf_node_observed: bool = False
    path_aligned: bool = False
    expected_inventory_covered: bool = False
    facade_delegates_only: bool = False
    child_evidence_current: bool = True
    parent_consumed_child: bool = False
    runtime_gateway_bound: bool = False
    closure_full: bool = False
    scoped_runtime_path: bool = False
    ad_hoc_log_only: bool = False


class RuntimePathUpgrade:
    name = "RuntimePathUpgrade"
    reads = (
        "contract_declared",
        "leaf_node_observed",
        "path_aligned",
        "child_evidence_current",
        "parent_consumed_child",
        "runtime_gateway_bound",
        "scoped_runtime_path",
    )
    writes = tuple(field for field in State.__dataclass_fields__)
    accepted_input_type = Event
    input_description = "runtime path evidence rollout event"
    output_description = "accepted rollout event or blocked transition"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        kind = input_obj.kind
        if kind == "declare_contract":
            yield FunctionResult(input_obj, replace(state, contract_declared=True), label="contract_declared")
            return
        if kind == "declare_expected_inventory":
            yield FunctionResult(
                input_obj,
                replace(state, expected_inventory_declared=True),
                label="expected_runtime_inventory_declared",
            )
            return
        if kind == "bind_stable_authority":
            if not state.contract_declared:
                yield FunctionResult(input_obj, state, label="blocked_authority_without_contract")
                return
            yield FunctionResult(
                input_obj,
                replace(state, stable_authority_bound=True),
                label="stable_runtime_authority_bound",
            )
            return
        if kind == "emit_leaf_node":
            if not state.contract_declared:
                yield FunctionResult(input_obj, state, label="blocked_leaf_without_contract")
                return
            yield FunctionResult(input_obj, replace(state, leaf_node_observed=True), label="leaf_node_observed")
            return
        if kind == "align_path":
            if (
                not state.leaf_node_observed
                or not state.child_evidence_current
                or not state.stable_authority_bound
            ):
                yield FunctionResult(input_obj, state, label="blocked_alignment_without_current_leaf")
                return
            yield FunctionResult(input_obj, replace(state, path_aligned=True), label="runtime_path_aligned")
            return
        if kind == "cover_expected_inventory":
            if not state.expected_inventory_declared or not state.path_aligned:
                yield FunctionResult(input_obj, state, label="blocked_inventory_without_declared_path")
                return
            yield FunctionResult(
                input_obj,
                replace(state, expected_inventory_covered=True),
                label="expected_runtime_inventory_covered",
            )
            return
        if kind == "prove_facade_delegation":
            if not state.path_aligned:
                yield FunctionResult(input_obj, state, label="blocked_facade_without_primary_path")
                return
            yield FunctionResult(
                input_obj,
                replace(state, facade_delegates_only=True),
                label="facade_delegation_only_proved",
            )
            return
        if kind == "mark_child_stale":
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    child_evidence_current=False,
                    path_aligned=False,
                    expected_inventory_covered=False,
                    facade_delegates_only=False,
                    parent_consumed_child=False,
                    runtime_gateway_bound=False,
                    closure_full=False,
                ),
                label="child_path_evidence_stale",
            )
            return
        if kind == "consume_parent":
            if not state.path_aligned or not state.child_evidence_current:
                yield FunctionResult(input_obj, state, label="blocked_parent_without_current_path")
                return
            yield FunctionResult(input_obj, replace(state, parent_consumed_child=True), label="parent_consumed_child_path")
            return
        if kind == "bind_gateway":
            if not state.path_aligned:
                yield FunctionResult(input_obj, state, label="blocked_gateway_without_path")
                return
            yield FunctionResult(input_obj, replace(state, runtime_gateway_bound=True), label="runtime_gateway_bound")
            return
        if kind == "scope_runtime_path":
            yield FunctionResult(input_obj, replace(state, scoped_runtime_path=True), label="runtime_path_scoped")
            return
        if kind == "ad_hoc_log":
            yield FunctionResult(input_obj, replace(state, ad_hoc_log_only=True), label="ad_hoc_log_recorded")
            return
        if kind == "claim_full":
            if (
                not state.path_aligned
                or not state.expected_inventory_declared
                or not state.expected_inventory_covered
                or not state.stable_authority_bound
                or not state.facade_delegates_only
                or not state.parent_consumed_child
                or not state.runtime_gateway_bound
                or state.scoped_runtime_path
            ):
                yield FunctionResult(input_obj, state, label="blocked_full_claim_without_path_evidence")
                return
            yield FunctionResult(input_obj, replace(state, closure_full=True), label="closure_full_confidence")
            return
        yield FunctionResult(input_obj, state, label="unknown_event")


class BrokenRuntimePathUpgrade(RuntimePathUpgrade):
    name = "BrokenRuntimePathUpgrade"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        kind = input_obj.kind
        if kind == "align_path":
            yield FunctionResult(input_obj, replace(state, path_aligned=True), label="broken_align_without_leaf")
            return
        if kind == "consume_parent":
            yield FunctionResult(input_obj, replace(state, parent_consumed_child=True), label="broken_parent_consumes_stale")
            return
        if kind == "bind_gateway":
            yield FunctionResult(input_obj, replace(state, runtime_gateway_bound=True), label="broken_gateway_without_node")
            return
        if kind == "claim_full":
            yield FunctionResult(input_obj, replace(state, closure_full=True), label="broken_full_claim")
            return
        yield from super().apply(input_obj, state)


EVENTS = (
    Event("declare_contract"),
    Event("declare_expected_inventory"),
    Event("bind_stable_authority"),
    Event("emit_leaf_node"),
    Event("align_path"),
    Event("cover_expected_inventory"),
    Event("prove_facade_delegation"),
    Event("mark_child_stale"),
    Event("consume_parent"),
    Event("bind_gateway"),
    Event("scope_runtime_path"),
    Event("ad_hoc_log"),
    Event("claim_full"),
)

GOOD_EVENTS = (
    Event("declare_contract"),
    Event("declare_expected_inventory"),
    Event("bind_stable_authority"),
    Event("emit_leaf_node"),
    Event("align_path"),
    Event("cover_expected_inventory"),
    Event("prove_facade_delegation"),
    Event("consume_parent"),
    Event("bind_gateway"),
    Event("claim_full"),
)


def closure_requires_runtime_path(state: State, trace) -> InvariantResult:
    del trace
    if state.closure_full and not state.path_aligned:
        return InvariantResult.fail("full closure requires runtime path alignment")
    if state.closure_full and not state.stable_authority_bound:
        return InvariantResult.fail("full closure requires stable intent, commitment, and selected-path identity")
    if state.closure_full and not state.expected_inventory_declared:
        return InvariantResult.fail("full closure requires an independently declared expected runtime inventory")
    if state.closure_full and not state.expected_inventory_covered:
        return InvariantResult.fail("full closure requires every expected runtime surface and candidate to be covered")
    if state.closure_full and not state.facade_delegates_only:
        return InvariantResult.fail("full closure requires retained facades to delegate without independent success")
    if state.closure_full and not state.leaf_node_observed:
        return InvariantResult.fail("full closure requires leaf runtime node observation")
    if state.closure_full and not state.parent_consumed_child:
        return InvariantResult.fail("full closure requires parent to consume child path evidence")
    if state.closure_full and not state.runtime_gateway_bound:
        return InvariantResult.fail("full closure requires runtime gateway node binding")
    if state.closure_full and state.scoped_runtime_path:
        return InvariantResult.fail("scoped runtime path evidence cannot support full closure")
    if state.closure_full and state.ad_hoc_log_only:
        return InvariantResult.fail("ad hoc logs cannot substitute for structured path evidence")
    return InvariantResult.pass_()


def parent_consumes_current_child(state: State, trace) -> InvariantResult:
    del trace
    if state.parent_consumed_child and not state.child_evidence_current:
        return InvariantResult.fail("parent consumed stale child path evidence")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="closure_requires_runtime_path",
        description="full closure needs current structured runtime path evidence",
        predicate=closure_requires_runtime_path,
    ),
    Invariant(
        name="parent_consumes_current_child",
        description="parent reattachment consumes only current child path evidence",
        predicate=parent_consumes_current_child,
    ),
)


def build_workflow(*, broken: bool = False) -> Workflow:
    block = BrokenRuntimePathUpgrade() if broken else RuntimePathUpgrade()
    return Workflow((block,), name="runtime_path_evidence_upgrade")


def initial_state() -> State:
    return State()


__all__ = [
    "EVENTS",
    "GOOD_EVENTS",
    "INVARIANTS",
    "Event",
    "State",
    "build_workflow",
    "initial_state",
]
