"""FlowGuard Risk Purpose Header.

Purpose:
Models the skill-architecture upgrade from one FlowGuard kernel skill with
internal sub-protocols to one kernel plus the current public owner and
delegated mode satellite skills.

Guards against:
- publishing while any satellite skill is missing;
- publishing while public owner and delegated mode skill counts are collapsed;
- treating helper APIs or CLI templates as Codex skills;
- allowing satellite skills to bypass kernel hard gates;
- claiming complete FlowGuard use while the closure contract is absent;
- claiming release readiness before installed skills, shadow workspace, tests,
  and version/tag/release surfaces are aligned.
- shipping SkillGuard author-control material inside any FlowGuard consumer
  skill or making consumer use depend on SkillGuard.

Run:
python .flowguard/codex_skill_satellites/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


SATELLITE_COUNT = 16
CONSUMER_SKILL_COUNT = 17
PUBLIC_OWNER_SKILL_COUNT = 14
DELEGATED_MODE_SKILL_COUNT = 2


@dataclass(frozen=True)
class UpgradeAction:
    action_type: str


@dataclass(frozen=True)
class UpgradeOutput:
    status: str


@dataclass(frozen=True)
class UpgradeState:
    kernel_preserved: bool = False
    satellite_count: int = 0
    public_owner_skill_count: int = 0
    delegated_mode_skill_count: int = 0
    helper_api_misclassified: bool = False
    global_prompt_synced: bool = False
    installed_skills_synced: bool = False
    shadow_workspace_synced: bool = False
    validations_passed: bool = False
    version_surfaces_aligned: bool = False
    closure_contract_documented: bool = False
    clean_consumer_skill_count: int = 0
    consumer_skillguard_residual_count: int = 0
    consumer_independence_validated: bool = False
    author_maintenance_state_private: bool = False
    release_claim: str = "none"

    def ready_for_release(self) -> bool:
        return (
            self.kernel_preserved
            and self.satellite_count == SATELLITE_COUNT
            and self.public_owner_skill_count == PUBLIC_OWNER_SKILL_COUNT
            and self.delegated_mode_skill_count == DELEGATED_MODE_SKILL_COUNT
            and not self.helper_api_misclassified
            and self.global_prompt_synced
            and self.installed_skills_synced
            and self.shadow_workspace_synced
            and self.validations_passed
            and self.version_surfaces_aligned
            and self.closure_contract_documented
            and self.clean_consumer_skill_count == CONSUMER_SKILL_COUNT
            and self.consumer_skillguard_residual_count == 0
            and self.consumer_independence_validated
            and self.author_maintenance_state_private
        )


class SkillSatelliteUpgrade:
    name = "SkillSatelliteUpgrade"
    reads = (
        "kernel_preserved",
        "satellite_count",
        "public_owner_skill_count",
        "delegated_mode_skill_count",
        "helper_api_misclassified",
        "global_prompt_synced",
        "installed_skills_synced",
        "shadow_workspace_synced",
        "validations_passed",
        "version_surfaces_aligned",
        "closure_contract_documented",
        "clean_consumer_skill_count",
        "consumer_skillguard_residual_count",
        "consumer_independence_validated",
        "author_maintenance_state_private",
    )
    writes = reads + ("release_claim",)
    accepted_input_type = UpgradeAction
    input_description = "skill architecture upgrade action"
    output_description = "skill topology and release readiness state"
    idempotency = "Release can only be accepted after every topology and sync gate is true."

    def apply(self, input_obj: UpgradeAction, state: UpgradeState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "prepare_topology":
            yield FunctionResult(
                UpgradeOutput("topology_prepared"),
                replace(
                    state,
                    kernel_preserved=True,
                    satellite_count=SATELLITE_COUNT,
                    public_owner_skill_count=PUBLIC_OWNER_SKILL_COUNT,
                    delegated_mode_skill_count=DELEGATED_MODE_SKILL_COUNT,
                ),
                label="topology_prepared",
            )
        elif action == "misclassify_helper_api":
            yield FunctionResult(
                UpgradeOutput("helper_api_misclassified"),
                replace(state, helper_api_misclassified=True),
                label="helper_api_misclassified",
            )
        elif action == "fix_helper_boundary":
            yield FunctionResult(
                UpgradeOutput("helper_boundary_fixed"),
                replace(state, helper_api_misclassified=False),
                label="helper_boundary_fixed",
            )
        elif action == "sync_runtime_surfaces":
            yield FunctionResult(
                UpgradeOutput("runtime_surfaces_synced"),
                replace(
                    state,
                    global_prompt_synced=True,
                    installed_skills_synced=True,
                    shadow_workspace_synced=True,
                ),
                label="runtime_surfaces_synced",
            )
        elif action == "pass_validations":
            yield FunctionResult(
                UpgradeOutput("validations_passed"),
                replace(state, validations_passed=True),
                label="validations_passed",
            )
        elif action == "align_version_surfaces":
            yield FunctionResult(
                UpgradeOutput("version_surfaces_aligned"),
                replace(state, version_surfaces_aligned=True, closure_contract_documented=True),
                label="version_surfaces_aligned",
            )
        elif action == "build_clean_consumer_distribution":
            yield FunctionResult(
                UpgradeOutput("clean_consumer_distribution_built"),
                replace(
                    state,
                    clean_consumer_skill_count=CONSUMER_SKILL_COUNT,
                    consumer_skillguard_residual_count=0,
                    consumer_independence_validated=True,
                    author_maintenance_state_private=True,
                ),
                label="clean_consumer_distribution_built",
            )
        elif action == "pollute_consumer_with_skillguard":
            yield FunctionResult(
                UpgradeOutput("consumer_polluted"),
                replace(
                    state,
                    consumer_skillguard_residual_count=1,
                    consumer_independence_validated=False,
                ),
                label="consumer_polluted",
            )
        elif action == "claim_release":
            claim = "accepted" if state.ready_for_release() else "rejected"
            yield FunctionResult(
                UpgradeOutput(f"release_{claim}"),
                replace(state, release_claim=claim),
                label=f"release_{claim}",
            )


class BrokenEarlyRelease(SkillSatelliteUpgrade):
    name = "BrokenEarlyRelease"
    idempotency = "Broken variant accepts a release once the kernel and some satellites exist."

    def apply(self, input_obj: UpgradeAction, state: UpgradeState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_release":
            claim = "accepted" if state.kernel_preserved and state.satellite_count > 0 else "rejected"
            yield FunctionResult(
                UpgradeOutput(f"release_{claim}"),
                replace(state, release_claim=claim),
                label=f"release_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, UpgradeOutput) and current_output.status.startswith("release_")


def no_release_without_full_topology_and_sync(state: UpgradeState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.ready_for_release():
        return InvariantResult.fail("release accepted before full skill topology and sync gates")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_release_without_full_topology_and_sync",
        "Release claims require kernel, current public owner/delegated satellite topology, prompt/install/shadow/test/version alignment, and no helper API misclassification.",
        no_release_without_full_topology_and_sync,
    ),
)

EXTERNAL_INPUTS = (
    UpgradeAction("prepare_topology"),
    UpgradeAction("misclassify_helper_api"),
    UpgradeAction("fix_helper_boundary"),
    UpgradeAction("sync_runtime_surfaces"),
    UpgradeAction("pass_validations"),
    UpgradeAction("align_version_surfaces"),
    UpgradeAction("build_clean_consumer_distribution"),
    UpgradeAction("claim_release"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> UpgradeState:
    return UpgradeState()


def build_correct_workflow() -> Workflow:
    return Workflow((SkillSatelliteUpgrade(),), name="codex_skill_satellites_correct")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenEarlyRelease(),), name="codex_skill_satellites_broken")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "PUBLIC_OWNER_SKILL_COUNT",
    "DELEGATED_MODE_SKILL_COUNT",
    "CONSUMER_SKILL_COUNT",
    "SATELLITE_COUNT",
    "UpgradeAction",
    "UpgradeOutput",
    "UpgradeState",
    "build_broken_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
