"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models target-project FlowGuard adoption/version gating before changing the
FlowGuard prompts, templates, and CLI that future agents will use.

Guards against:
- claiming real target-project FlowGuard use without the real package;
- bypassing the target project's managed AGENTS.md FlowGuard block;
- silently upgrading a project manifest without rerunning affected checks;
- treating adoption logs as a replacement for executable validation.
- writing `.skillguard` into an ordinary FlowGuard target project.
- treating a source-layout-only verifier as portable project evidence.
- copying a FlowGuard skill suite into an ordinary target project.
- treating an editable checkout's author suite map as installed-consumer proof.
- treating a target-owned JSON schema marker as FlowGuard artifact ownership.
- treating a legacy-BCL required-field subset plus target-only fields as
  historical FlowGuard producer ownership.

Use before editing:
FlowGuard project-adoption prompts, AGENTS snippets, manifest templates,
adoption CLI commands, installed skill guidance, or release synchronization.

Run:
python .flowguard/project_adoption_version_gate/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ProjectAction:
    kind: str


@dataclass(frozen=True)
class Claim:
    status: str
    reason: str


@dataclass(frozen=True)
class State:
    real_package_verified: bool = False
    consumer_suite_authority: str = "none"
    artifact_upgrade_authority: str = "none"
    flowguard_owned_json_write_count: int = 0
    unsupported_registered_envelope_write_count: int = 0
    target_owned_json_write_count: int = 0
    agents_block_current: bool = False
    manifest_current: bool = False
    installed_version_relation: str = "same"
    validation_current: bool = False
    revalidation_authority: str = "none"
    adoption_log_recorded: bool = False
    skillguard_project_write_count: int = 0
    project_local_flowguard_skill_write_count: int = 0
    author_maintenance_dependency_count: int = 0
    currentness_validation_launch_count: int = 0


class ProjectAdoptionGate:
    name = "ProjectAdoptionGate"
    reads = (
        "real_package_verified",
        "consumer_suite_authority",
        "artifact_upgrade_authority",
        "flowguard_owned_json_write_count",
        "unsupported_registered_envelope_write_count",
        "target_owned_json_write_count",
        "agents_block_current",
        "manifest_current",
        "installed_version_relation",
        "validation_current",
        "revalidation_authority",
        "adoption_log_recorded",
        "skillguard_project_write_count",
        "project_local_flowguard_skill_write_count",
        "author_maintenance_dependency_count",
        "currentness_validation_launch_count",
    )
    writes = (
        "real_package_verified",
        "consumer_suite_authority",
        "artifact_upgrade_authority",
        "flowguard_owned_json_write_count",
        "unsupported_registered_envelope_write_count",
        "target_owned_json_write_count",
        "agents_block_current",
        "manifest_current",
        "installed_version_relation",
        "validation_current",
        "revalidation_authority",
        "adoption_log_recorded",
        "skillguard_project_write_count",
        "project_local_flowguard_skill_write_count",
        "author_maintenance_dependency_count",
        "currentness_validation_launch_count",
    )
    accepted_input_type = ProjectAction
    input_description = "target-project adoption or upgrade action"
    output_description = "ProjectAction or Claim"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        kind = input_obj.kind
        if kind == "verify_real_package":
            yield FunctionResult(input_obj, replace(state, real_package_verified=True), label="real_package_verified")
            return
        if kind == "verify_packaged_global_consumer" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    consumer_suite_authority="package-global-exact",
                ),
                label="global_consumer_suite_verified",
            )
            return
        if kind == "verify_registered_artifact_scan" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    artifact_upgrade_authority=(
                        "current-envelope-registry+exact-56083c1e-bcl-migrator"
                    ),
                ),
                label="registered_artifact_scan_verified",
            )
            return
        if (
            kind == "migrate_typed_behavior_ledger"
            and state.artifact_upgrade_authority
            == "current-envelope-registry+exact-56083c1e-bcl-migrator"
        ):
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    flowguard_owned_json_write_count=(
                        state.flowguard_owned_json_write_count + 1
                    ),
                ),
                label="typed_behavior_ledger_migrated",
            )
            return
        if kind == "attempt_unsupported_registered_envelope_migration":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "registered report and trace envelopes are current-only without an evidence-bound migrator",
                ),
                state,
                label="unsupported_registered_envelope_migration_blocked",
            )
            return
        if kind == "attempt_target_owned_json_migration":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "numeric schema syntax does not grant FlowGuard artifact ownership",
                ),
                state,
                label="target_owned_json_migration_blocked",
            )
            return
        if kind == "attempt_legacy_lookalike_json_migration":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "target-only extra fields exclude the exact historical BCL producer shape",
                ),
                state,
                label="legacy_lookalike_json_migration_blocked",
            )
            return
        if kind == "installed_newer":
            yield FunctionResult(
                input_obj,
                replace(state, installed_version_relation="newer", validation_current=False),
                label="installed_version_newer",
            )
            return
        if kind == "installed_older":
            yield FunctionResult(
                input_obj,
                replace(state, installed_version_relation="older", validation_current=False),
                label="installed_version_older",
            )
            return
        if (
            kind == "write_agents_block"
            and state.real_package_verified
            and state.consumer_suite_authority == "package-global-exact"
        ):
            yield FunctionResult(input_obj, replace(state, agents_block_current=True), label="agents_block_written")
            return
        if kind == "write_manifest" and state.real_package_verified and state.agents_block_current:
            yield FunctionResult(input_obj, replace(state, manifest_current=True), label="manifest_written")
            return
        if kind == "rerun_validation" and state.manifest_current and state.installed_version_relation != "older":
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    validation_current=True,
                    revalidation_authority="package-module",
                ),
                label="validation_rerun",
            )
            return
        if kind == "record_adoption_log":
            yield FunctionResult(input_obj, replace(state, adoption_log_recorded=True), label="adoption_log_recorded")
            return
        if kind == "attempt_skillguard_project_write":
            yield FunctionResult(
                Claim("blocked", "ordinary FlowGuard projects permit only FlowGuard adoption state"),
                state,
                label="skillguard_project_write_blocked",
            )
            return
        if kind == "attempt_project_local_flowguard_skill_write":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "ordinary projects consume the global Codex skill projection",
                ),
                state,
                label="project_local_flowguard_skill_write_blocked",
            )
            return
        if kind == "attempt_author_maintenance_dependency":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "ordinary adoption ignores author checkout and SkillGuard state",
                ),
                state,
                label="author_maintenance_dependency_blocked",
            )
            return
        if kind == "attempt_currentness_validation_launch":
            yield FunctionResult(
                Claim(
                    "blocked",
                    "installed currentness is an identity read and launches no validator",
                ),
                state,
                label="currentness_validation_launch_blocked",
            )
            return
        if kind == "claim_done":
            complete = (
                state.real_package_verified
                and state.consumer_suite_authority == "package-global-exact"
                and state.artifact_upgrade_authority
                == "current-envelope-registry+exact-56083c1e-bcl-migrator"
                and state.unsupported_registered_envelope_write_count == 0
                and state.target_owned_json_write_count == 0
                and state.agents_block_current
                and state.manifest_current
                and state.installed_version_relation != "older"
                and state.validation_current
                and state.revalidation_authority == "package-module"
                and state.skillguard_project_write_count == 0
                and state.project_local_flowguard_skill_write_count == 0
                and state.author_maintenance_dependency_count == 0
                and state.currentness_validation_launch_count == 0
            )
            status = "complete" if complete else "blocked"
            yield FunctionResult(Claim(status, "checked project adoption gate"), state, label=f"claim_{status}")
            return
        yield FunctionResult(input_obj, state, label=f"ignored_{kind}")


class BrokenClaimWithoutAgents(ProjectAdoptionGate):
    name = "BrokenClaimWithoutAgents"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "claim_done":
            yield FunctionResult(Claim("complete", "ignored AGENTS block"), state, label="broken_claim_complete")
            return
        yield from super().apply(input_obj, state)


class BrokenUpgradeWithoutValidation(ProjectAdoptionGate):
    name = "BrokenUpgradeWithoutValidation"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "write_manifest" and state.real_package_verified and state.agents_block_current:
            yield FunctionResult(
                Claim("complete", "manifest update treated as validation"),
                replace(state, manifest_current=True),
                label="broken_upgrade_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenLogAsCompletion(ProjectAdoptionGate):
    name = "BrokenLogAsCompletion"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "record_adoption_log":
            yield FunctionResult(
                Claim("complete", "log treated as proof"),
                replace(state, adoption_log_recorded=True),
                label="broken_log_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkillGuardProjectPollution(ProjectAdoptionGate):
    name = "BrokenSkillGuardProjectPollution"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "attempt_skillguard_project_write":
            yield FunctionResult(
                Claim("complete", "incorrectly wrote SkillGuard author state into a project"),
                replace(state, skillguard_project_write_count=1),
                label="broken_skillguard_project_pollution",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSourceLayoutRevalidation(ProjectAdoptionGate):
    name = "BrokenSourceLayoutRevalidation"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if (
            input_obj.kind == "rerun_validation"
            and state.manifest_current
            and state.installed_version_relation != "older"
        ):
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    validation_current=True,
                    revalidation_authority="source-script",
                ),
                label="source_layout_revalidation_treated_current",
            )
            return
        if input_obj.kind == "claim_done" and state.validation_current:
            yield FunctionResult(
                Claim("complete", "source-layout-only command treated as portable proof"),
                state,
                label="broken_source_layout_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenProjectLocalFlowGuardSuite(ProjectAdoptionGate):
    name = "BrokenProjectLocalFlowGuardSuite"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "attempt_project_local_flowguard_skill_write":
            yield FunctionResult(
                Claim("complete", "project-local FlowGuard suite treated as current authority"),
                replace(state, project_local_flowguard_skill_write_count=1),
                label="broken_project_local_flowguard_skill_write",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenEditableAuthorSuiteAuthority(ProjectAdoptionGate):
    name = "BrokenEditableAuthorSuiteAuthority"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "verify_packaged_global_consumer" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    consumer_suite_authority="editable-author-suite-map",
                ),
                label="editable_author_suite_treated_current",
            )
            return
        if (
            input_obj.kind == "write_agents_block"
            and state.real_package_verified
            and state.consumer_suite_authority == "editable-author-suite-map"
        ):
            yield FunctionResult(
                input_obj,
                replace(state, agents_block_current=True),
                label="agents_block_written_from_editable_author_suite",
            )
            return
        if input_obj.kind == "claim_done" and state.validation_current:
            yield FunctionResult(
                Claim(
                    "complete",
                    "editable author suite map treated as portable consumer authority",
                ),
                state,
                label="broken_editable_author_suite_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenAuthorMaintenanceDependency(ProjectAdoptionGate):
    name = "BrokenAuthorMaintenanceDependency"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "attempt_author_maintenance_dependency":
            yield FunctionResult(
                Claim(
                    "complete",
                    "ordinary project currentness consulted author maintenance state",
                ),
                replace(
                    state,
                    author_maintenance_dependency_count=1,
                ),
                label="broken_author_maintenance_dependency",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenCurrentnessValidationLaunch(ProjectAdoptionGate):
    name = "BrokenCurrentnessValidationLaunch"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "attempt_currentness_validation_launch":
            yield FunctionResult(
                Claim(
                    "complete",
                    "read-only installed currentness launched semantic validation",
                ),
                replace(
                    state,
                    currentness_validation_launch_count=1,
                ),
                label="broken_currentness_validation_launch",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNumericSchemaArtifactAuthority(ProjectAdoptionGate):
    name = "BrokenNumericSchemaArtifactAuthority"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "verify_registered_artifact_scan" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    artifact_upgrade_authority="numeric-schema-inference",
                ),
                label="numeric_schema_inference_treated_as_authority",
            )
            return
        if (
            input_obj.kind == "attempt_target_owned_json_migration"
            and state.artifact_upgrade_authority == "numeric-schema-inference"
        ):
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    target_owned_json_write_count=state.target_owned_json_write_count + 1,
                ),
                label="broken_target_owned_json_written",
            )
            return
        if input_obj.kind == "claim_done" and state.target_owned_json_write_count:
            yield FunctionResult(
                Claim("complete", "numeric schema marker treated as FlowGuard ownership"),
                state,
                label="broken_numeric_schema_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenUnsupportedRegisteredEnvelopeMigration(ProjectAdoptionGate):
    name = "BrokenUnsupportedRegisteredEnvelopeMigration"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "verify_registered_artifact_scan" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    artifact_upgrade_authority="open-version-envelope-registry",
                ),
                label="open_version_envelope_registry_treated_as_authority",
            )
            return
        if input_obj.kind == "attempt_unsupported_registered_envelope_migration":
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    unsupported_registered_envelope_write_count=(
                        state.unsupported_registered_envelope_write_count + 1
                    ),
                ),
                label="broken_unsupported_registered_envelope_written",
            )
            return
        if input_obj.kind == "claim_done" and state.unsupported_registered_envelope_write_count:
            yield FunctionResult(
                Claim(
                    "complete",
                    "unsupported registered envelope version rewritten without a proven migrator",
                ),
                state,
                label="broken_unsupported_registered_envelope_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenLegacyLookalikeArtifactAuthority(ProjectAdoptionGate):
    name = "BrokenLegacyLookalikeArtifactAuthority"

    def apply(self, input_obj: ProjectAction, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "verify_registered_artifact_scan" and state.real_package_verified:
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    artifact_upgrade_authority="legacy-required-subset-inference",
                ),
                label="legacy_required_subset_treated_as_authority",
            )
            return
        if (
            input_obj.kind == "attempt_legacy_lookalike_json_migration"
            and state.artifact_upgrade_authority == "legacy-required-subset-inference"
        ):
            yield FunctionResult(
                input_obj,
                replace(
                    state,
                    target_owned_json_write_count=state.target_owned_json_write_count + 1,
                ),
                label="broken_legacy_lookalike_json_written",
            )
            return
        if input_obj.kind == "claim_done" and state.target_owned_json_write_count:
            yield FunctionResult(
                Claim(
                    "complete",
                    "legacy required-field subset plus target-only fields treated as FlowGuard ownership",
                ),
                state,
                label="broken_legacy_lookalike_claim_complete",
            )
            return
        yield from super().apply(input_obj, state)


def complete_claim_requires_real_package(_state: State, trace) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if isinstance(output, Claim) and output.status == "complete" and not step.old_state.real_package_verified:
            return InvariantResult.fail("complete claim before real FlowGuard package verification")
    return InvariantResult.pass_()


def complete_claim_requires_agents_block(_state: State, trace) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if isinstance(output, Claim) and output.status == "complete" and not step.old_state.agents_block_current:
            return InvariantResult.fail("complete claim without target-project AGENTS FlowGuard block")
    return InvariantResult.pass_()


def complete_claim_requires_manifest(_state: State, trace) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if isinstance(output, Claim) and output.status == "complete" and not step.old_state.manifest_current:
            return InvariantResult.fail("complete claim without .flowguard/project.toml")
    return InvariantResult.pass_()


def complete_claim_requires_current_validation(_state: State, trace) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if isinstance(output, Claim) and output.status == "complete" and not step.old_state.validation_current:
            return InvariantResult.fail("complete claim without current validation after adoption/version change")
    return InvariantResult.pass_()


def older_local_tool_blocks_completion(_state: State, trace) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if isinstance(output, Claim) and output.status == "complete" and step.old_state.installed_version_relation == "older":
            return InvariantResult.fail("complete claim with installed FlowGuard older than project record")
    return InvariantResult.pass_()


def complete_claim_requires_package_owned_revalidation(
    _state: State, trace
) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if (
            isinstance(output, Claim)
            and output.status == "complete"
            and step.old_state.revalidation_authority != "package-module"
        ):
            return InvariantResult.fail(
                "complete claim without package-owned target-project revalidation"
            )
    return InvariantResult.pass_()


def complete_claim_requires_packaged_global_consumer_authority(
    _state: State, trace
) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if (
            isinstance(output, Claim)
            and output.status == "complete"
            and step.old_state.consumer_suite_authority != "package-global-exact"
        ):
            return InvariantResult.fail(
                "complete claim without exact packaged-authority/global-consumer parity"
            )
    return InvariantResult.pass_()


def complete_claim_requires_registered_artifact_upgrade_authority(
    _state: State, trace
) -> InvariantResult:
    for step in trace.steps:
        output = step.function_output
        if (
            isinstance(output, Claim)
            and output.status == "complete"
            and step.old_state.artifact_upgrade_authority
            != "current-envelope-registry+exact-56083c1e-bcl-migrator"
        ):
            return InvariantResult.fail(
                "complete claim without exact FlowGuard artifact type/field registry"
            )
    return InvariantResult.pass_()


def ordinary_project_has_zero_target_owned_json_writes(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.target_owned_json_write_count:
        return InvariantResult.fail(
            "FlowGuard project upgrade modified a target-owned JSON artifact"
        )
    return InvariantResult.pass_()


def unsupported_registered_envelopes_have_zero_writes(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.unsupported_registered_envelope_write_count:
        return InvariantResult.fail(
            "project upgrade rewrote an unsupported report/trace envelope version"
        )
    return InvariantResult.pass_()


def ordinary_project_has_zero_skillguard_writes(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.skillguard_project_write_count:
        return InvariantResult.fail(
            "ordinary FlowGuard project received SkillGuard author-control files"
        )
    return InvariantResult.pass_()


def ordinary_project_has_zero_local_flowguard_skill_writes(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.project_local_flowguard_skill_write_count:
        return InvariantResult.fail(
            "ordinary project received a second project-local FlowGuard skill suite"
        )
    return InvariantResult.pass_()


def ordinary_project_has_zero_author_maintenance_dependencies(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.author_maintenance_dependency_count:
        return InvariantResult.fail(
            "ordinary project adoption consumed author or SkillGuard maintenance state"
        )
    return InvariantResult.pass_()


def currentness_read_launches_zero_validation(
    state: State, trace
) -> InvariantResult:
    del trace
    if state.currentness_validation_launch_count:
        return InvariantResult.fail(
            "read-only installed currentness launched a semantic validation owner"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("complete_claim_requires_real_package", "complete claims require real FlowGuard import evidence", complete_claim_requires_real_package),
    Invariant("complete_claim_requires_agents_block", "complete claims require the target-project AGENTS block", complete_claim_requires_agents_block),
    Invariant("complete_claim_requires_manifest", "complete claims require the project FlowGuard manifest", complete_claim_requires_manifest),
    Invariant("complete_claim_requires_current_validation", "manifest/log writes do not replace validation", complete_claim_requires_current_validation),
    Invariant(
        "complete_claim_requires_package_owned_revalidation",
        "target-project revalidation uses the installed FlowGuard package entrypoint",
        complete_claim_requires_package_owned_revalidation,
    ),
    Invariant(
        "complete_claim_requires_packaged_global_consumer_authority",
        "ordinary project writes require exact package/global consumer parity",
        complete_claim_requires_packaged_global_consumer_authority,
    ),
    Invariant(
        "complete_claim_requires_registered_artifact_upgrade_authority",
        "artifact writes require the exact current-envelope registry plus exact historical BCL owner",
        complete_claim_requires_registered_artifact_upgrade_authority,
    ),
    Invariant(
        "ordinary_project_has_zero_target_owned_json_writes",
        "unknown and target-owned JSON artifacts remain byte-identical.",
        ordinary_project_has_zero_target_owned_json_writes,
    ),
    Invariant(
        "unsupported_registered_envelopes_have_zero_writes",
        "registered report and trace envelopes are current-only.",
        unsupported_registered_envelopes_have_zero_writes,
    ),
    Invariant("older_local_tool_blocks_completion", "older local FlowGuard cannot maintain a newer project record", older_local_tool_blocks_completion),
    Invariant(
        "ordinary_project_has_zero_skillguard_writes",
        "FlowGuard project adoption writes only FlowGuard-owned project state.",
        ordinary_project_has_zero_skillguard_writes,
    ),
    Invariant(
        "ordinary_project_has_zero_local_flowguard_skill_writes",
        "ordinary projects consume the global FlowGuard skill projection.",
        ordinary_project_has_zero_local_flowguard_skill_writes,
    ),
    Invariant(
        "ordinary_project_has_zero_author_maintenance_dependencies",
        "ordinary project adoption depends only on package and consumer projection identities.",
        ordinary_project_has_zero_author_maintenance_dependencies,
    ),
    Invariant(
        "currentness_read_launches_zero_validation",
        "read-only installed currentness launches no semantic validation owner.",
        currentness_read_launches_zero_validation,
    ),
)


EXTERNAL_INPUTS = (
    ProjectAction("verify_real_package"),
    ProjectAction("verify_packaged_global_consumer"),
    ProjectAction("verify_registered_artifact_scan"),
    ProjectAction("migrate_typed_behavior_ledger"),
    ProjectAction("attempt_unsupported_registered_envelope_migration"),
    ProjectAction("attempt_target_owned_json_migration"),
    ProjectAction("attempt_legacy_lookalike_json_migration"),
    ProjectAction("installed_newer"),
    ProjectAction("installed_older"),
    ProjectAction("write_agents_block"),
    ProjectAction("write_manifest"),
    ProjectAction("rerun_validation"),
    ProjectAction("record_adoption_log"),
    ProjectAction("attempt_author_maintenance_dependency"),
    ProjectAction("attempt_currentness_validation_launch"),
    ProjectAction("claim_done"),
)


def initial_state() -> State:
    return State()


def build_workflow(block=None) -> Workflow:
    return Workflow((block or ProjectAdoptionGate(),), name="project_adoption_version_gate")
