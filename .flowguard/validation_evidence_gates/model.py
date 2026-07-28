"""FlowGuard model for validation evidence gate rollout.

Risk purpose:
- require UI click-through evidence for reachable actionable controls/events;
- require artifact payload packs when file/work-package behavior is claimed;
- require structured manual evidence only when automation cannot inspect a
  boundary;
- require installed skill prompt sync before local installed behavior is
  claimed.

Function block shape: Input x State -> Set(Output x State)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class State:
    openspec_valid: bool = False
    ui_gate_documented: bool = False
    payload_gate_documented: bool = False
    manual_gate_documented: bool = False
    payload_helper_added: bool = False
    ui_guidance_updated: bool = False
    templates_updated: bool = False
    risk_ledger_updated: bool = False
    tests_updated: bool = False
    installed_skills_synced: bool = False
    package_import_verified: bool = False
    local_source_synced: bool = False
    done_claim: str = "none"


@dataclass(frozen=True)
class Output:
    action: str
    ok: bool
    reason: str = ""


def transition(action: str, state: State) -> tuple[tuple[Output, State], ...]:
    """Input x State -> Set(Output x State)."""

    if action == "validate_openspec":
        return ((Output(action, True), replace(state, openspec_valid=True)),)
    if action == "document_ui_gate":
        return ((Output(action, True), replace(state, ui_gate_documented=True)),)
    if action == "document_payload_gate":
        return ((Output(action, True), replace(state, payload_gate_documented=True)),)
    if action == "document_manual_gate":
        return ((Output(action, True), replace(state, manual_gate_documented=True)),)
    if action == "add_payload_helper":
        ok = state.payload_gate_documented
        return (
            (
                Output(action, ok, "" if ok else "payload gate must be documented first"),
                replace(state, payload_helper_added=ok),
            ),
        )
    if action == "update_ui_guidance":
        ok = state.ui_gate_documented and state.manual_gate_documented
        return (
            (
                Output(action, ok, "" if ok else "UI and manual gates must be documented"),
                replace(state, ui_guidance_updated=ok),
            ),
        )
    if action == "update_templates":
        ok = state.payload_helper_added and state.ui_guidance_updated
        return (
            (
                Output(action, ok, "" if ok else "helpers and UI guidance first"),
                replace(state, templates_updated=ok),
            ),
        )
    if action == "update_risk_ledger":
        ok = state.payload_gate_documented and state.ui_gate_documented
        return (
            (
                Output(action, ok, "" if ok else "risk gates need UI and payload boundaries"),
                replace(state, risk_ledger_updated=ok),
            ),
        )
    if action == "focused_tests":
        ok = (
            state.openspec_valid
            and state.ui_gate_documented
            and state.payload_gate_documented
            and state.manual_gate_documented
            and state.payload_helper_added
            and state.ui_guidance_updated
            and state.templates_updated
            and state.risk_ledger_updated
        )
        return (
            (
                Output(action, ok, "" if ok else "validation gate implementation incomplete"),
                replace(state, tests_updated=ok),
            ),
        )
    if action == "sync_installed_skills":
        ok = state.tests_updated
        return (
            (
                Output(action, ok, "" if ok else "tests must pass before installed sync"),
                replace(state, installed_skills_synced=ok),
            ),
        )
    if action == "verify_package_import":
        ok = state.tests_updated
        return (
            (
                Output(action, ok, "" if ok else "tests must pass before package verification"),
                replace(state, package_import_verified=ok),
            ),
        )
    if action == "sync_local_source":
        ok = state.installed_skills_synced and state.package_import_verified
        return (
            (
                Output(action, ok, "" if ok else "install and package evidence first"),
                replace(state, local_source_synced=ok),
            ),
        )
    if action == "claim_done":
        accepted = (
            state.openspec_valid
            and state.ui_gate_documented
            and state.payload_gate_documented
            and state.manual_gate_documented
            and state.payload_helper_added
            and state.ui_guidance_updated
            and state.templates_updated
            and state.risk_ledger_updated
            and state.tests_updated
            and state.installed_skills_synced
            and state.package_import_verified
            and state.local_source_synced
        )
        return (
            (
                Output(action, accepted, "" if accepted else "done evidence incomplete"),
                replace(state, done_claim="accepted" if accepted else "rejected"),
            ),
        )
    if action == "broken_claim_without_payload_pack":
        return (
            (
                Output(action, True, "broken accepted without payload helper"),
                replace(
                    state,
                    openspec_valid=True,
                    ui_gate_documented=True,
                    manual_gate_documented=True,
                    ui_guidance_updated=True,
                    tests_updated=True,
                    installed_skills_synced=True,
                    package_import_verified=True,
                    local_source_synced=True,
                    done_claim="accepted",
                ),
            ),
        )
    if action == "broken_claim_without_clickthrough":
        return (
            (
                Output(action, True, "broken accepted without UI guidance"),
                replace(
                    state,
                    openspec_valid=True,
                    payload_gate_documented=True,
                    manual_gate_documented=True,
                    payload_helper_added=True,
                    templates_updated=True,
                    risk_ledger_updated=True,
                    tests_updated=True,
                    installed_skills_synced=True,
                    package_import_verified=True,
                    local_source_synced=True,
                    done_claim="accepted",
                ),
            ),
        )
    if action == "broken_claim_with_prose_manual_check":
        return (
            (
                Output(action, True, "broken accepted with prose-only manual gate"),
                replace(
                    state,
                    openspec_valid=True,
                    ui_gate_documented=True,
                    payload_gate_documented=True,
                    payload_helper_added=True,
                    ui_guidance_updated=True,
                    templates_updated=True,
                    risk_ledger_updated=True,
                    tests_updated=True,
                    installed_skills_synced=True,
                    package_import_verified=True,
                    local_source_synced=True,
                    done_claim="accepted",
                ),
            ),
        )
    if action == "broken_claim_without_installed_sync":
        return (
            (
                Output(action, True, "broken accepted without installed skill sync"),
                replace(
                    state,
                    openspec_valid=True,
                    ui_gate_documented=True,
                    payload_gate_documented=True,
                    manual_gate_documented=True,
                    payload_helper_added=True,
                    ui_guidance_updated=True,
                    templates_updated=True,
                    risk_ledger_updated=True,
                    tests_updated=True,
                    package_import_verified=True,
                    local_source_synced=True,
                    done_claim="accepted",
                ),
            ),
        )
    return ((Output(action, False, "unknown action"), state),)


def run(actions: Iterable[str], initial: State = State()) -> tuple[State, tuple[Output, ...]]:
    state = initial
    outputs: list[Output] = []
    for action in actions:
        ((output, state),) = transition(action, state)
        outputs.append(output)
    return state, tuple(outputs)


def invariant_done_has_ui_payload_manual_and_sync(state: State) -> bool:
    if state.done_claim != "accepted":
        return True
    return (
        state.openspec_valid
        and state.ui_gate_documented
        and state.payload_gate_documented
        and state.manual_gate_documented
        and state.payload_helper_added
        and state.ui_guidance_updated
        and state.templates_updated
        and state.risk_ledger_updated
        and state.tests_updated
        and state.installed_skills_synced
        and state.package_import_verified
        and state.local_source_synced
    )


def scenario_ok() -> State:
    state, outputs = run(
        (
            "validate_openspec",
            "document_ui_gate",
            "document_payload_gate",
            "document_manual_gate",
            "add_payload_helper",
            "update_ui_guidance",
            "update_templates",
            "update_risk_ledger",
            "focused_tests",
            "sync_installed_skills",
            "verify_package_import",
            "sync_local_source",
            "claim_done",
        )
    )
    assert all(output.ok for output in outputs), outputs
    assert invariant_done_has_ui_payload_manual_and_sync(state)
    return state


def scenario_missing_payload_pack_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("broken_claim_without_payload_pack",))
    assert state.done_claim == "accepted"
    assert not invariant_done_has_ui_payload_manual_and_sync(state)
    return state, outputs


def scenario_missing_clickthrough_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("broken_claim_without_clickthrough",))
    assert state.done_claim == "accepted"
    assert not invariant_done_has_ui_payload_manual_and_sync(state)
    return state, outputs


def scenario_prose_manual_check_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("broken_claim_with_prose_manual_check",))
    assert state.done_claim == "accepted"
    assert not invariant_done_has_ui_payload_manual_and_sync(state)
    return state, outputs


def scenario_missing_installed_sync_blocks() -> tuple[State, tuple[Output, ...]]:
    state, outputs = run(("broken_claim_without_installed_sync",))
    assert state.done_claim == "accepted"
    assert not invariant_done_has_ui_payload_manual_and_sync(state)
    return state, outputs
