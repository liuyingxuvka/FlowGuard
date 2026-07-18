"""FlowGuard self-maintenance mesh model.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: make FlowGuard's own route graph, field layering, AI entry profiles,
child route evidence, exact change-contract checks, install sync, shadow sync,
and repository boundary visible before claiming self-maintenance completion.
Guards against: adding more helpers while leaving routes unconnected, hiding
required field/evidence expansion, or claiming completion before validation and
sync evidence is current; unrelated local-green receipts, progress-only
background runs, and wrong-plane completion authority cannot stand in for the
declared plane-upgrade checks.
Use before editing: public route API, AI entry guidance, installed skills,
field lifecycle prompts, structure split plans, and release/sync records.
Run: python .flowguard/self_maintenance_mesh/run_checks.py
Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class SelfMaintenanceAction:
    action_type: str
    behavior_plane: str = "development_process"
    verified_child_receipt_ids: tuple[str, ...] = ()
    verification_set_fingerprint: str = ""
    verified_plane_upgrade_receipt_ids: tuple[str, ...] = ()
    terminal_plane_upgrade_receipt_ids: tuple[str, ...] = ()
    progress_only_plane_upgrade_receipt_ids: tuple[str, ...] = ()
    verification_contract_fingerprint: str = ""
    spec_context_ids: tuple[str, ...] = ()
    spec_context_provider: str = "openspec"
    spec_context_artifacts_current: bool = True
    spec_context_read_only: bool = True
    spec_receipt_bridge_present: bool = False


@dataclass(frozen=True)
class SelfMaintenanceOutput:
    status: str


@dataclass(frozen=True)
class SelfMaintenanceState:
    route_graph_connected: bool = False
    route_handoffs_typed: bool = False
    route_owners_unique: bool = False
    route_cycles_bounded: bool = False
    ai_profiles_declared: bool = False
    field_layers_declared: bool = False
    child_reports_current: bool = False
    plane_upgrade_reports_current: bool = False
    behavior_ledger_current: bool = False
    dcar_coverage_current: bool = False
    test_mesh_shards_current: bool = False
    model_miss_backfeed_current: bool = False
    route_api_tested: bool = False
    focused_validation_passed: bool = False
    install_sync_verified: bool = False
    shadow_sync_checked: bool = False
    git_status_checked: bool = False
    spec_context_current: bool = False
    consumed_spec_context_ids: tuple[str, ...] = ()
    consumed_child_receipt_ids: tuple[str, ...] = ()
    receipt_set_fingerprint: str = ""
    consumed_plane_upgrade_receipt_ids: tuple[str, ...] = ()
    terminal_plane_upgrade_receipt_ids: tuple[str, ...] = ()
    verification_contract_fingerprint: str = ""
    completion_authority_plane: str = ""
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.route_graph_connected
            and self.route_handoffs_typed
            and self.route_owners_unique
            and self.route_cycles_bounded
            and self.ai_profiles_declared
            and self.field_layers_declared
            and self.child_reports_current
            and self.plane_upgrade_reports_current
            and self.behavior_ledger_current
            and self.dcar_coverage_current
            and self.test_mesh_shards_current
            and self.model_miss_backfeed_current
            and self.route_api_tested
            and self.focused_validation_passed
            and self.install_sync_verified
            and self.shadow_sync_checked
            and self.git_status_checked
            and self.spec_context_current
        )


def _receipt_sets_current(input_obj: SelfMaintenanceAction) -> tuple[bool, bool, bool]:
    skill_receipt_ids = tuple(input_obj.verified_child_receipt_ids)
    skill_set_current = (
        len(skill_receipt_ids) == len(REQUIRED_SKILL_RECEIPT_IDS)
        and set(skill_receipt_ids) == set(REQUIRED_SKILL_RECEIPT_IDS)
        and bool(input_obj.verification_set_fingerprint)
    )

    plane_receipt_ids = tuple(input_obj.verified_plane_upgrade_receipt_ids)
    terminal_receipt_ids = tuple(input_obj.terminal_plane_upgrade_receipt_ids)
    plane_set_current = (
        len(plane_receipt_ids) == len(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and set(plane_receipt_ids) == set(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and len(terminal_receipt_ids) == len(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and set(terminal_receipt_ids) == set(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and not input_obj.progress_only_plane_upgrade_receipt_ids
        and input_obj.verification_contract_fingerprint
        == PLANE_UPGRADE_VERIFICATION_CONTRACT_FINGERPRINT
    )
    spec_set_current = (
        set(input_obj.spec_context_ids) == set(REQUIRED_SPEC_CONTEXT_IDS)
        and input_obj.spec_context_provider == "openspec"
        and input_obj.spec_context_artifacts_current
        and input_obj.spec_context_read_only
        and not input_obj.spec_receipt_bridge_present
    )
    return skill_set_current, plane_set_current, spec_set_current


class CorrectSelfMaintenance:
    name = "CorrectSelfMaintenance"
    reads = (
        "route_graph_connected",
        "route_handoffs_typed",
        "route_owners_unique",
        "route_cycles_bounded",
        "ai_profiles_declared",
        "field_layers_declared",
        "child_reports_current",
        "plane_upgrade_reports_current",
        "behavior_ledger_current",
        "dcar_coverage_current",
        "test_mesh_shards_current",
        "model_miss_backfeed_current",
        "route_api_tested",
        "focused_validation_passed",
        "install_sync_verified",
        "shadow_sync_checked",
        "git_status_checked",
        "spec_context_current",
        "consumed_spec_context_ids",
        "consumed_child_receipt_ids",
        "receipt_set_fingerprint",
        "consumed_plane_upgrade_receipt_ids",
        "terminal_plane_upgrade_receipt_ids",
        "verification_contract_fingerprint",
        "completion_authority_plane",
        "done_claim",
    )
    writes = reads
    accepted_input_type = SelfMaintenanceAction
    input_description = "self-maintenance lifecycle action"
    output_description = "self-maintenance state or claim decision"
    idempotency = (
        "Done claims require route graph, profiles, behavior ledger, DCAR, TestMesh, "
        "model-miss backfeed, exact plane-upgrade receipts, validation, install, shadow, and repository gates."
    )

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.behavior_plane != "development_process":
            yield FunctionResult(
                SelfMaintenanceOutput("wrong_plane_action_blocked"),
                state,
                label="wrong_plane_action_blocked",
            )
            return
        action = input_obj.action_type
        if action == "advance_receipt_bound_workflow":
            if not state.route_graph_connected:
                yield FunctionResult(
                    SelfMaintenanceOutput("route_graph_connected"),
                    replace(
                        state,
                        route_graph_connected=True,
                        route_handoffs_typed=True,
                        route_owners_unique=True,
                        route_cycles_bounded=True,
                        ai_profiles_declared=True,
                    ),
                    label="route_graph_connected",
                )
            elif not state.field_layers_declared:
                yield FunctionResult(
                    SelfMaintenanceOutput("field_layers_declared"),
                    replace(state, field_layers_declared=True),
                    label="field_layers_declared",
                )
            elif not (
                state.child_reports_current
                and state.plane_upgrade_reports_current
                and state.spec_context_current
            ):
                receipt_ids = tuple(input_obj.verified_child_receipt_ids)
                plane_receipt_ids = tuple(input_obj.verified_plane_upgrade_receipt_ids)
                terminal_receipt_ids = tuple(input_obj.terminal_plane_upgrade_receipt_ids)
                exact_set, plane_exact_set, spec_exact_set = _receipt_sets_current(input_obj)
                all_current = exact_set and plane_exact_set and spec_exact_set
                yield FunctionResult(
                    SelfMaintenanceOutput("receipt_set_consumed" if all_current else "receipt_set_rejected"),
                    replace(
                        state,
                        child_reports_current=exact_set,
                        plane_upgrade_reports_current=plane_exact_set,
                        behavior_ledger_current=plane_exact_set,
                        dcar_coverage_current=plane_exact_set,
                        test_mesh_shards_current=plane_exact_set,
                        model_miss_backfeed_current=plane_exact_set,
                        route_api_tested=plane_exact_set,
                        consumed_child_receipt_ids=receipt_ids if exact_set else (),
                        receipt_set_fingerprint=input_obj.verification_set_fingerprint if exact_set else "",
                        consumed_plane_upgrade_receipt_ids=plane_receipt_ids if plane_exact_set else (),
                        terminal_plane_upgrade_receipt_ids=terminal_receipt_ids if plane_exact_set else (),
                        verification_contract_fingerprint=(
                            input_obj.verification_contract_fingerprint if plane_exact_set else ""
                        ),
                        spec_context_current=spec_exact_set,
                        consumed_spec_context_ids=(
                            tuple(input_obj.spec_context_ids) if spec_exact_set else ()
                        ),
                    ),
                    label="receipt_set_consumed" if all_current else "receipt_set_rejected",
                )
            elif not state.focused_validation_passed:
                yield FunctionResult(
                    SelfMaintenanceOutput("focused_validation_passed"),
                    replace(state, focused_validation_passed=True),
                    label="focused_validation_passed",
                )
            elif not (state.install_sync_verified and state.shadow_sync_checked and state.git_status_checked):
                yield FunctionResult(
                    SelfMaintenanceOutput("local_surfaces_synced"),
                    replace(
                        state,
                        install_sync_verified=True,
                        shadow_sync_checked=True,
                        git_status_checked=True,
                    ),
                    label="local_surfaces_synced",
                )
            else:
                yield FunctionResult(
                    SelfMaintenanceOutput("done_accepted"),
                    replace(
                        state,
                        done_claim="accepted",
                        completion_authority_plane=input_obj.behavior_plane,
                    ),
                    label="done_accepted",
                )
        elif action == "connect_route_graph":
            yield FunctionResult(
                SelfMaintenanceOutput("route_graph_connected"),
                replace(
                    state,
                    route_graph_connected=True,
                    route_handoffs_typed=True,
                    route_owners_unique=True,
                    route_cycles_bounded=True,
                    ai_profiles_declared=True,
                ),
                label="route_graph_connected",
            )
        elif action == "declare_field_layers":
            yield FunctionResult(
                SelfMaintenanceOutput("field_layers_declared"),
                replace(state, field_layers_declared=True),
                label="field_layers_declared",
            )
        elif action == "consume_verified_receipt_set":
            receipt_ids = tuple(input_obj.verified_child_receipt_ids)
            plane_receipt_ids = tuple(input_obj.verified_plane_upgrade_receipt_ids)
            terminal_receipt_ids = tuple(input_obj.terminal_plane_upgrade_receipt_ids)
            exact_set, plane_exact_set, spec_exact_set = _receipt_sets_current(input_obj)
            all_current = exact_set and plane_exact_set and spec_exact_set
            yield FunctionResult(
                SelfMaintenanceOutput("receipt_set_consumed" if all_current else "receipt_set_rejected"),
                replace(
                    state,
                    child_reports_current=exact_set,
                    plane_upgrade_reports_current=plane_exact_set,
                    behavior_ledger_current=plane_exact_set,
                    dcar_coverage_current=plane_exact_set,
                    test_mesh_shards_current=plane_exact_set,
                    model_miss_backfeed_current=plane_exact_set,
                    route_api_tested=plane_exact_set,
                    consumed_child_receipt_ids=receipt_ids if exact_set else (),
                    receipt_set_fingerprint=input_obj.verification_set_fingerprint if exact_set else "",
                    consumed_plane_upgrade_receipt_ids=plane_receipt_ids if plane_exact_set else (),
                    terminal_plane_upgrade_receipt_ids=terminal_receipt_ids if plane_exact_set else (),
                    verification_contract_fingerprint=(
                        input_obj.verification_contract_fingerprint if plane_exact_set else ""
                    ),
                    spec_context_current=spec_exact_set,
                    consumed_spec_context_ids=(
                        tuple(input_obj.spec_context_ids) if spec_exact_set else ()
                    ),
                ),
                label="receipt_set_consumed" if all_current else "receipt_set_rejected",
            )
        elif action == "run_focused_validation":
            yield FunctionResult(
                SelfMaintenanceOutput("focused_validation_passed"),
                replace(state, focused_validation_passed=True),
                label="focused_validation_passed",
            )
        elif action == "sync_local_surfaces":
            yield FunctionResult(
                SelfMaintenanceOutput("local_surfaces_synced"),
                replace(
                    state,
                    install_sync_verified=True,
                    shadow_sync_checked=True,
                    git_status_checked=True,
                ),
                label="local_surfaces_synced",
            )
        elif action == "claim_done":
            claim = "accepted" if state.ready_for_done() else "rejected"
            yield FunctionResult(
                SelfMaintenanceOutput(f"done_{claim}"),
                replace(
                    state,
                    done_claim=claim,
                    completion_authority_plane=input_obj.behavior_plane if claim == "accepted" else "",
                ),
                label=f"done_{claim}",
            )


class BrokenRouteGraphOnly(CorrectSelfMaintenance):
    name = "BrokenRouteGraphOnly"
    idempotency = "Broken variant accepts completion once route graph and profiles exist."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            claim = "accepted" if state.route_graph_connected and state.ai_profiles_declared else "rejected"
            yield FunctionResult(
                SelfMaintenanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingSync(CorrectSelfMaintenance):
    name = "BrokenMissingSync"
    idempotency = "Broken variant accepts completion before install, shadow, and git evidence."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            claim = (
                "accepted"
                if state.route_graph_connected
                and state.ai_profiles_declared
                and state.field_layers_declared
                and state.child_reports_current
                and state.route_api_tested
                and state.focused_validation_passed
                else "rejected"
            )
            yield FunctionResult(
                SelfMaintenanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSyntheticAllFlags(CorrectSelfMaintenance):
    name = "BrokenSyntheticAllFlags"
    idempotency = "Broken variant manufactures current evidence flags without consuming receipts."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "declare_field_layers":
            yield FunctionResult(
                SelfMaintenanceOutput("field_layers_declared"),
                replace(
                    state,
                    field_layers_declared=True,
                    child_reports_current=True,
                    plane_upgrade_reports_current=True,
                    behavior_ledger_current=True,
                    dcar_coverage_current=True,
                    test_mesh_shards_current=True,
                    model_miss_backfeed_current=True,
                    route_api_tested=True,
                ),
                label="synthetic_all_flags",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenAcceptsUnverifiedPlaneReceipts(CorrectSelfMaintenance):
    name = "BrokenAcceptsUnverifiedPlaneReceipts"
    idempotency = "Broken variant trusts caller-supplied receipt identities, progress, and fingerprints."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "consume_verified_receipt_set":
            yield FunctionResult(
                SelfMaintenanceOutput("receipt_set_consumed"),
                replace(
                    state,
                    child_reports_current=True,
                    plane_upgrade_reports_current=True,
                    behavior_ledger_current=True,
                    dcar_coverage_current=True,
                    test_mesh_shards_current=True,
                    model_miss_backfeed_current=True,
                    route_api_tested=True,
                    consumed_child_receipt_ids=tuple(input_obj.verified_child_receipt_ids),
                    receipt_set_fingerprint=input_obj.verification_set_fingerprint,
                    consumed_plane_upgrade_receipt_ids=tuple(
                        input_obj.verified_plane_upgrade_receipt_ids
                    ),
                    terminal_plane_upgrade_receipt_ids=tuple(
                        input_obj.terminal_plane_upgrade_receipt_ids
                    ),
                    verification_contract_fingerprint=input_obj.verification_contract_fingerprint,
                ),
                label="unverified_receipts_consumed",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingCoverageGate(CorrectSelfMaintenance):
    name = "BrokenMissingCoverageGate"
    omitted_gate = ""
    idempotency = "Broken variant accepts completion while one self-coverage gate is still missing."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "declare_field_layers":
            updates = {
                "field_layers_declared": True,
                "child_reports_current": True,
                "plane_upgrade_reports_current": True,
                "behavior_ledger_current": True,
                "dcar_coverage_current": True,
                "test_mesh_shards_current": True,
                "model_miss_backfeed_current": True,
                "route_api_tested": True,
            }
            if self.omitted_gate:
                updates[self.omitted_gate] = False
            yield FunctionResult(
                SelfMaintenanceOutput("field_layers_declared"),
                replace(state, **updates),
                label="field_layers_declared",
            )
            return
        if input_obj.action_type == "claim_done":
            checks = {
                "route_graph_connected": state.route_graph_connected,
                "route_handoffs_typed": state.route_handoffs_typed,
                "route_owners_unique": state.route_owners_unique,
                "route_cycles_bounded": state.route_cycles_bounded,
                "ai_profiles_declared": state.ai_profiles_declared,
                "field_layers_declared": state.field_layers_declared,
                "child_reports_current": state.child_reports_current,
                "plane_upgrade_reports_current": state.plane_upgrade_reports_current,
                "behavior_ledger_current": state.behavior_ledger_current,
                "dcar_coverage_current": state.dcar_coverage_current,
                "test_mesh_shards_current": state.test_mesh_shards_current,
                "model_miss_backfeed_current": state.model_miss_backfeed_current,
                "route_api_tested": state.route_api_tested,
                "focused_validation_passed": state.focused_validation_passed,
                "install_sync_verified": state.install_sync_verified,
                "shadow_sync_checked": state.shadow_sync_checked,
                "git_status_checked": state.git_status_checked,
            }
            if self.omitted_gate:
                checks[self.omitted_gate] = True
            claim = "accepted" if all(checks.values()) else "rejected"
            yield FunctionResult(
                SelfMaintenanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingBehaviorLedger(BrokenMissingCoverageGate):
    name = "BrokenMissingBehaviorLedger"
    omitted_gate = "behavior_ledger_current"


class BrokenMissingDcarCoverage(BrokenMissingCoverageGate):
    name = "BrokenMissingDcarCoverage"
    omitted_gate = "dcar_coverage_current"


class BrokenMissingTestMeshShards(BrokenMissingCoverageGate):
    name = "BrokenMissingTestMeshShards"
    omitted_gate = "test_mesh_shards_current"


class BrokenMissingModelMissBackfeed(BrokenMissingCoverageGate):
    name = "BrokenMissingModelMissBackfeed"
    omitted_gate = "model_miss_backfeed_current"


class BrokenMissingPlaneUpgradeReports(BrokenMissingCoverageGate):
    name = "BrokenMissingPlaneUpgradeReports"
    omitted_gate = "plane_upgrade_reports_current"


class BrokenWrongPlaneCompletionAuthority(CorrectSelfMaintenance):
    name = "BrokenWrongPlaneCompletionAuthority"
    idempotency = "Broken variant lets an agent-operation action own development-process completion."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done" and input_obj.behavior_plane != "development_process":
            yield FunctionResult(
                SelfMaintenanceOutput("done_accepted"),
                replace(
                    state,
                    done_claim="accepted",
                    completion_authority_plane=input_obj.behavior_plane,
                ),
                label="wrong_plane_done_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingSpecContext(CorrectSelfMaintenance):
    name = "BrokenMissingSpecContext"
    idempotency = "Broken variant accepts done after ordinary checks pass without current read-only requirements context."

    def apply(self, input_obj: SelfMaintenanceAction, state: SelfMaintenanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            ordinary_ready = replace(state, spec_context_current=True).ready_for_done()
            claim = "accepted" if ordinary_ready else "rejected"
            yield FunctionResult(
                SelfMaintenanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim, completion_authority_plane="development_process"),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, SelfMaintenanceOutput) and current_output.status.startswith("done_")


def no_done_without_full_route_and_sync(state: SelfMaintenanceState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "self-maintenance done accepted before typed route handoffs, unique owners, bounded cycles, profiles, field layers, exact skill and plane-upgrade child reports, behavior ledger, DCAR, TestMesh, model-miss backfeed, tests, install, shadow, and repository gates"
        )
    return InvariantResult.pass_()


def no_evidence_flags_without_exact_receipt_set(state: SelfMaintenanceState, trace) -> InvariantResult:
    del trace
    if state.child_reports_current and not (
        len(state.consumed_child_receipt_ids) == len(REQUIRED_SKILL_RECEIPT_IDS)
        and set(state.consumed_child_receipt_ids) == set(REQUIRED_SKILL_RECEIPT_IDS)
        and bool(state.receipt_set_fingerprint)
    ):
        return InvariantResult.fail(
            "skill-suite evidence became current without the exact required child identities"
        )

    plane_evidence_flags = (
        state.plane_upgrade_reports_current,
        state.behavior_ledger_current,
        state.dcar_coverage_current,
        state.test_mesh_shards_current,
        state.model_miss_backfeed_current,
        state.route_api_tested,
    )
    if any(plane_evidence_flags) and not (
        len(state.consumed_plane_upgrade_receipt_ids)
        == len(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and set(state.consumed_plane_upgrade_receipt_ids)
        == set(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and len(state.terminal_plane_upgrade_receipt_ids)
        == len(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and set(state.terminal_plane_upgrade_receipt_ids)
        == set(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS)
        and state.verification_contract_fingerprint
        == PLANE_UPGRADE_VERIFICATION_CONTRACT_FINGERPRINT
    ):
        return InvariantResult.fail(
            "plane-upgrade evidence became current without exact terminal check identities and the current verification-contract fingerprint"
        )
    if state.spec_context_current and not (
        set(state.consumed_spec_context_ids) == set(REQUIRED_SPEC_CONTEXT_IDS)
    ):
        return InvariantResult.fail(
            "spec context became current without the required read-only change identity"
        )
    return InvariantResult.pass_()


def route_graph_does_not_replace_field_layers(state: SelfMaintenanceState, trace) -> InvariantResult:
    del trace
    if state.route_graph_connected and state.done_claim == "accepted" and not state.field_layers_declared:
        return InvariantResult.fail("route graph completion replaced field layer evidence")
    return InvariantResult.pass_()


def completion_authority_stays_in_development_process(state: SelfMaintenanceState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and state.completion_authority_plane != "development_process":
        return InvariantResult.fail(
            "self-maintenance completion was owned by a product-runtime or agent-operation action"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_full_route_and_sync",
        "Self-maintenance done claims require typed route handoffs, unique owners, bounded cycles, AI profiles, field layers, child reports, behavior ledger, DCAR, TestMesh, model-miss backfeed, validation, install, shadow, and git gates.",
        no_done_without_full_route_and_sync,
    ),
    Invariant(
        "route_graph_does_not_replace_field_layers",
        "Route graph completion cannot replace field layer evidence.",
        route_graph_does_not_replace_field_layers,
    ),
    Invariant(
        "no_evidence_flags_without_exact_receipt_set",
        "Evidence views require exact receipt identities and an aggregate verifier fingerprint.",
        no_evidence_flags_without_exact_receipt_set,
    ),
    Invariant(
        "completion_authority_stays_in_development_process",
        "Self-maintenance completion remains owned by the development-process plane; other planes are typed targets or evidence sources.",
        completion_authority_stays_in_development_process,
    ),
)

REQUIRED_SKILL_RECEIPT_IDS = (
    "flowguard",
    "flowguard-architecture-reduction",
    "flowguard-behavior-commitment-ledger",
    "flowguard-code-structure-recommendation",
    "flowguard-contract-exhaustion-mesh",
    "flowguard-development-process-flow",
    "flowguard-existing-model-preflight",
    "flowguard-field-lifecycle-mesh",
    "flowguard-model-mesh",
    "flowguard-model-miss-review",
    "flowguard-model-test-alignment",
    "flowguard-model-topology-hazard-review",
    "flowguard-structure-mesh",
    "flowguard-test-mesh",
    "flowguard-ui-flow-structure",
)
REQUIRED_RECEIPT_COUNT = len(REQUIRED_SKILL_RECEIPT_IDS)
ABSTRACT_RECEIPT_IDS = REQUIRED_SKILL_RECEIPT_IDS
REQUIRED_PLANE_UPGRADE_RECEIPT_IDS = (
    "check.lookup.focused",
    "check.behavior.focused",
    "check.contracts.focused",
    "check.api.templates",
    "check.skills.focused",
    "check.skills.static",
    "check.skills.install",
    "check.project.models",
    "check.models.full",
    "check.tests.full",
    "check.flowguard.audit",
)
PLANE_UPGRADE_VERIFICATION_CONTRACT_FINGERPRINT = (
    "sha256:"
    + hashlib.sha256(
        "\n".join(REQUIRED_PLANE_UPGRADE_RECEIPT_IDS).encode("utf-8")
    ).hexdigest().upper()
)
# Exact source identity for the OpenSpec verification contract that declares
# the current plane-upgrade checks. This is intentionally separate from the
# normalized check-id fingerprint above.
PLANE_UPGRADE_VERIFICATION_CONTRACT_SOURCE_SHA256 = (
    "sha256:01BC478660999AE0B19A3DF6EFFC2A55368E54D28B5B9043B447E3BC25C7A86A"
)
REQUIRED_SPEC_CONTEXT_IDS = (
    "openspec:separate-flowguard-consumer-skills-from-skillguard-maintenance",
)
EXTERNAL_INPUTS = (
    SelfMaintenanceAction(
        "advance_receipt_bound_workflow",
        verified_child_receipt_ids=ABSTRACT_RECEIPT_IDS,
        verification_set_fingerprint="sha256:abstract-current-receipt-set",
        verified_plane_upgrade_receipt_ids=REQUIRED_PLANE_UPGRADE_RECEIPT_IDS,
        terminal_plane_upgrade_receipt_ids=REQUIRED_PLANE_UPGRADE_RECEIPT_IDS,
        verification_contract_fingerprint=PLANE_UPGRADE_VERIFICATION_CONTRACT_FINGERPRINT,
        spec_context_ids=REQUIRED_SPEC_CONTEXT_IDS,
        spec_context_provider="openspec",
        spec_context_artifacts_current=True,
        spec_context_read_only=True,
        spec_receipt_bridge_present=False,
    ),
)

MAX_SEQUENCE_LENGTH = 6


def initial_state() -> SelfMaintenanceState:
    return SelfMaintenanceState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectSelfMaintenance(),), name="self_maintenance_correct")


def build_broken_route_graph_only_workflow() -> Workflow:
    return Workflow((BrokenRouteGraphOnly(),), name="self_maintenance_broken_route_graph_only")


def build_broken_missing_sync_workflow() -> Workflow:
    return Workflow((BrokenMissingSync(),), name="self_maintenance_broken_missing_sync")


def build_broken_synthetic_all_flags_workflow() -> Workflow:
    return Workflow((BrokenSyntheticAllFlags(),), name="self_maintenance_broken_synthetic_all_flags")


def build_broken_unverified_plane_receipts_workflow() -> Workflow:
    return Workflow(
        (BrokenAcceptsUnverifiedPlaneReceipts(),),
        name="self_maintenance_broken_unverified_plane_receipts",
    )


def build_broken_missing_behavior_ledger_workflow() -> Workflow:
    return Workflow((BrokenMissingBehaviorLedger(),), name="self_maintenance_broken_missing_behavior_ledger")


def build_broken_missing_dcar_coverage_workflow() -> Workflow:
    return Workflow((BrokenMissingDcarCoverage(),), name="self_maintenance_broken_missing_dcar_coverage")


def build_broken_missing_test_mesh_shards_workflow() -> Workflow:
    return Workflow((BrokenMissingTestMeshShards(),), name="self_maintenance_broken_missing_test_mesh_shards")


def build_broken_missing_model_miss_backfeed_workflow() -> Workflow:
    return Workflow((BrokenMissingModelMissBackfeed(),), name="self_maintenance_broken_missing_model_miss_backfeed")


def build_broken_missing_plane_upgrade_reports_workflow() -> Workflow:
    return Workflow((BrokenMissingPlaneUpgradeReports(),), name="self_maintenance_broken_missing_plane_upgrade_reports")


def build_broken_wrong_plane_completion_workflow() -> Workflow:
    return Workflow((BrokenWrongPlaneCompletionAuthority(),), name="self_maintenance_broken_wrong_plane_completion")


def build_broken_missing_spec_context_workflow() -> Workflow:
    return Workflow((BrokenMissingSpecContext(),), name="self_maintenance_broken_missing_spec_context")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "SelfMaintenanceAction",
    "SelfMaintenanceOutput",
    "SelfMaintenanceState",
    "build_broken_missing_behavior_ledger_workflow",
    "build_broken_missing_dcar_coverage_workflow",
    "build_broken_missing_model_miss_backfeed_workflow",
    "build_broken_missing_plane_upgrade_reports_workflow",
    "build_broken_missing_spec_context_workflow",
    "build_broken_missing_sync_workflow",
    "build_broken_synthetic_all_flags_workflow",
    "build_broken_unverified_plane_receipts_workflow",
    "build_broken_missing_test_mesh_shards_workflow",
    "build_broken_route_graph_only_workflow",
    "build_broken_wrong_plane_completion_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
