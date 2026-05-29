"""FlowGuard model for structure-surface simplification.

Risk purpose:
- Template body splits must preserve public facade and CLI parity.
- Grouped API discovery must not drop existing flat exports.
- Lightweight evidence objects must not hide skipped, stale, or progress-only
  states.

Function block shape: Input x State -> Set(Output x State)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class State:
    templates_split: bool = False
    template_facade_parity: bool = False
    template_cli_parity: bool = False
    api_registry_added: bool = False
    flat_api_compatible: bool = False
    evidence_helpers_added: bool = False
    evidence_hidden_non_pass: bool = False
    focused_tests_passed: bool = False
    full_regression_passed: bool = False
    editable_install_verified: bool = False
    shadow_verified: bool = False
    local_git_synced: bool = False


@dataclass(frozen=True)
class Output:
    label: str
    ok: bool
    reason: str = ""


def transition(action: str, state: State) -> tuple[tuple[Output, State], ...]:
    """Input x State -> Set(Output x State)."""
    if action == "split_templates":
        return ((Output(action, True), replace(state, templates_split=True)),)
    if action == "prove_template_parity":
        ok = state.templates_split
        return ((Output(action, ok, "" if ok else "split first"), replace(state, template_facade_parity=ok, template_cli_parity=ok)),)
    if action == "add_api_registry":
        return ((Output(action, True), replace(state, api_registry_added=True, flat_api_compatible=True)),)
    if action == "add_evidence_helpers":
        return ((Output(action, True), replace(state, evidence_helpers_added=True, evidence_hidden_non_pass=False)),)
    if action == "broken_hide_non_pass_evidence":
        return ((Output(action, False, "non-pass evidence hidden"), replace(state, evidence_helpers_added=True, evidence_hidden_non_pass=True)),)
    if action == "focused_tests":
        ok = state.template_facade_parity and state.api_registry_added and state.evidence_helpers_added and not state.evidence_hidden_non_pass
        return ((Output(action, ok, "" if ok else "focused surface evidence missing"), replace(state, focused_tests_passed=ok)),)
    if action == "full_regression":
        ok = state.focused_tests_passed
        return ((Output(action, ok, "" if ok else "focused tests first"), replace(state, full_regression_passed=ok)),)
    if action == "install_and_shadow":
        ok = state.full_regression_passed
        return ((Output(action, ok, "" if ok else "regression evidence first"), replace(state, editable_install_verified=ok, shadow_verified=ok)),)
    if action == "commit":
        ok = state.editable_install_verified and state.shadow_verified
        return ((Output(action, ok, "" if ok else "install and shadow first"), replace(state, local_git_synced=ok)),)
    return ((Output(action, False, "unknown action"), state),)


def run(actions: Iterable[str], initial: State = State()) -> tuple[State, tuple[Output, ...]]:
    state = initial
    outputs: list[Output] = []
    for action in actions:
        ((output, state),) = transition(action, state)
        outputs.append(output)
    return state, tuple(outputs)


def invariant_done_requires_current_evidence(state: State) -> bool:
    if not state.local_git_synced:
        return True
    return (
        state.templates_split
        and state.template_facade_parity
        and state.template_cli_parity
        and state.api_registry_added
        and state.flat_api_compatible
        and state.evidence_helpers_added
        and not state.evidence_hidden_non_pass
        and state.focused_tests_passed
        and state.full_regression_passed
        and state.editable_install_verified
        and state.shadow_verified
    )


def scenario_ok() -> State:
    state, outputs = run(
        (
            "split_templates",
            "prove_template_parity",
            "add_api_registry",
            "add_evidence_helpers",
            "focused_tests",
            "full_regression",
            "install_and_shadow",
            "commit",
        )
    )
    assert all(output.ok for output in outputs), outputs
    assert invariant_done_requires_current_evidence(state)
    return state


def scenario_missing_template_parity_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("split_templates", "add_api_registry", "add_evidence_helpers", "focused_tests"))
    assert not outputs[-1].ok
    assert not state.focused_tests_passed
    return state, outputs


def scenario_hidden_non_pass_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("split_templates", "prove_template_parity", "add_api_registry", "broken_hide_non_pass_evidence", "focused_tests"))
    assert not outputs[-1].ok
    assert not invariant_done_requires_current_evidence(replace(state, local_git_synced=True))
    return state, outputs


def scenario_commit_without_shadow_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("split_templates", "prove_template_parity", "add_api_registry", "add_evidence_helpers", "focused_tests", "full_regression", "commit"))
    assert not outputs[-1].ok
    assert not state.local_git_synced
    return state, outputs
