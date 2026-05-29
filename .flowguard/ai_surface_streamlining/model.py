"""FlowGuard model for route-first AI surface streamlining.

Risk purpose:
- keep Model Similarity Consolidation as the owner of similar workflow
  maintenance;
- make the default AI path lightweight without removing full schema capability;
- replace repeated downstream similarity fields with one handoff;
- require tests, install, shadow, and git evidence before local completion.

Function block shape: Input x State -> Set(Output x State)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class State:
    openspec_valid: bool = False
    route_first_docs: bool = False
    lightweight_profiles: bool = False
    full_schema_available: bool = True
    handoff_added: bool = False
    repeated_fields_removed: bool = False
    downstream_routes_updated: bool = False
    tests_updated: bool = False
    self_model_passed: bool = False
    full_regression_passed: bool = False
    install_verified: bool = False
    shadow_verified: bool = False
    local_git_synced: bool = False


@dataclass(frozen=True)
class Output:
    label: str
    ok: bool
    reason: str = ""


def transition(action: str, state: State) -> tuple[tuple[Output, State], ...]:
    """Input x State -> Set(Output x State)."""

    if action == "validate_openspec":
        return ((Output(action, True), replace(state, openspec_valid=True)),)
    if action == "add_route_first_docs":
        return ((Output(action, True), replace(state, route_first_docs=True)),)
    if action == "add_profiles":
        return ((Output(action, True), replace(state, lightweight_profiles=True, full_schema_available=True)),)
    if action == "add_handoff":
        return ((Output(action, True), replace(state, handoff_added=True)),)
    if action == "remove_repeated_fields":
        ok = state.handoff_added
        return ((Output(action, ok, "" if ok else "handoff first"), replace(state, repeated_fields_removed=ok)),)
    if action == "update_downstream_routes":
        ok = state.handoff_added and state.repeated_fields_removed
        return (
            (
                Output(action, ok, "" if ok else "routes need clean handoff"),
                replace(state, downstream_routes_updated=ok),
            ),
        )
    if action == "focused_tests":
        ok = (
            state.openspec_valid
            and state.route_first_docs
            and state.lightweight_profiles
            and state.full_schema_available
            and state.handoff_added
            and state.repeated_fields_removed
            and state.downstream_routes_updated
        )
        return ((Output(action, ok, "" if ok else "surface evidence incomplete"), replace(state, tests_updated=ok)),)
    if action == "self_model":
        ok = state.tests_updated
        return ((Output(action, ok, "" if ok else "focused tests first"), replace(state, self_model_passed=ok)),)
    if action == "full_regression":
        ok = state.self_model_passed
        return ((Output(action, ok, "" if ok else "self model first"), replace(state, full_regression_passed=ok)),)
    if action == "install_and_shadow":
        ok = state.full_regression_passed
        return (
            (
                Output(action, ok, "" if ok else "regression first"),
                replace(state, install_verified=ok, shadow_verified=ok),
            ),
        )
    if action == "commit":
        ok = state.install_verified and state.shadow_verified
        return ((Output(action, ok, "" if ok else "install and shadow first"), replace(state, local_git_synced=ok)),)
    if action == "broken_compatibility_wrapper":
        return ((Output(action, False, "old repeated fields remain"), replace(state, handoff_added=True)),)
    if action == "broken_drop_full_schema":
        return ((Output(action, False, "full schema removed"), replace(state, lightweight_profiles=True, full_schema_available=False)),)
    return ((Output(action, False, "unknown action"), state),)


def run(actions: Iterable[str], initial: State = State()) -> tuple[State, tuple[Output, ...]]:
    state = initial
    outputs: list[Output] = []
    for action in actions:
        ((output, state),) = transition(action, state)
        outputs.append(output)
    return state, tuple(outputs)


def invariant_done_requires_clean_surface(state: State) -> bool:
    if not state.local_git_synced:
        return True
    return (
        state.openspec_valid
        and state.route_first_docs
        and state.lightweight_profiles
        and state.full_schema_available
        and state.handoff_added
        and state.repeated_fields_removed
        and state.downstream_routes_updated
        and state.tests_updated
        and state.self_model_passed
        and state.full_regression_passed
        and state.install_verified
        and state.shadow_verified
    )


def scenario_ok() -> State:
    state, outputs = run(
        (
            "validate_openspec",
            "add_route_first_docs",
            "add_profiles",
            "add_handoff",
            "remove_repeated_fields",
            "update_downstream_routes",
            "focused_tests",
            "self_model",
            "full_regression",
            "install_and_shadow",
            "commit",
        )
    )
    assert all(output.ok for output in outputs), outputs
    assert invariant_done_requires_clean_surface(state)
    return state


def scenario_wrapper_bloat_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("validate_openspec", "add_route_first_docs", "add_profiles", "broken_compatibility_wrapper", "focused_tests"))
    assert not outputs[-1].ok
    assert not state.repeated_fields_removed
    return state, outputs


def scenario_dropping_full_schema_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("validate_openspec", "add_route_first_docs", "broken_drop_full_schema", "add_handoff", "remove_repeated_fields", "update_downstream_routes", "focused_tests"))
    assert not outputs[-1].ok
    assert not state.full_schema_available
    return state, outputs


def scenario_commit_without_shadow_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(
        (
            "validate_openspec",
            "add_route_first_docs",
            "add_profiles",
            "add_handoff",
            "remove_repeated_fields",
            "update_downstream_routes",
            "focused_tests",
            "self_model",
            "full_regression",
            "commit",
        )
    )
    assert not outputs[-1].ok
    assert not state.local_git_synced
    return state, outputs
