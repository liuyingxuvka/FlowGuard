"""Model public release adoption from a fresh user checkout.

This model does not clone GitHub itself. The real clone/install/check commands
are run outside the model, then summarized as a deterministic observation. The
model reviews whether those observations satisfy the public adoption contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from flowguard import FunctionResult, InvariantResult, Trace, Workflow
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class ReleaseObservation:
    release: str
    cloned_from_github: bool
    checked_out_release_ref: bool
    clean_venv_created: bool
    recommended_install_command: str
    recommended_install_succeeded: bool
    normal_editable_install_succeeded: bool
    import_preflight_succeeded: bool
    public_tests_succeeded: bool
    examples_succeeded: bool
    skill_assets_present: bool
    helper_install_from_outside_repo_succeeded: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdoptionState:
    release: str = ""
    cloned: bool = False
    release_ref_checked: bool = False
    clean_venv: bool = False
    recommended_install_succeeded: bool = False
    normal_install_succeeded: bool = False
    import_ok: bool = False
    public_tests_ok: bool = False
    examples_ok: bool = False
    skill_assets_ok: bool = False
    helper_install_ok: bool = False
    status: str = "new"
    findings: tuple[str, ...] = ()

    def add_finding(self, finding: str) -> "AdoptionState":
        return AdoptionState(
            release=self.release,
            cloned=self.cloned,
            release_ref_checked=self.release_ref_checked,
            clean_venv=self.clean_venv,
            recommended_install_succeeded=self.recommended_install_succeeded,
            normal_install_succeeded=self.normal_install_succeeded,
            import_ok=self.import_ok,
            public_tests_ok=self.public_tests_ok,
            examples_ok=self.examples_ok,
            skill_assets_ok=self.skill_assets_ok,
            helper_install_ok=self.helper_install_ok,
            status=self.status,
            findings=self.findings + (finding,),
        )


INITIAL_STATE = AdoptionState()


class CheckClone:
    name = "CheckClone"
    reads = ("github", "release_ref")
    writes = ("cloned", "release_ref_checked", "clean_venv")
    accepted_input_type = ReleaseObservation
    input_description = "observed public release checkout"
    output_description = "clone readiness"
    idempotency = "pure observation projection"

    def can_accept(self, input_obj: object) -> bool:
        return isinstance(input_obj, ReleaseObservation)

    def apply(self, input_obj: ReleaseObservation, state: AdoptionState):
        cloned = input_obj.cloned_from_github
        checked = input_obj.checked_out_release_ref
        clean = input_obj.clean_venv_created
        new_state = AdoptionState(
            release=input_obj.release,
            cloned=cloned,
            release_ref_checked=checked,
            clean_venv=clean,
            findings=tuple(input_obj.notes),
        )
        label = "fresh_clone_ready" if cloned and checked and clean else "fresh_clone_not_ready"
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label=label,
            reason="project was checked as a fresh public release clone",
        )


class CheckInstall:
    name = "CheckInstall"
    reads = ("install_observation",)
    writes = ("install_status",)
    accepted_input_type = ReleaseObservation
    input_description = "observed install commands"
    output_description = "install readiness"
    idempotency = "pure observation projection"

    def can_accept(self, input_obj: object) -> bool:
        return isinstance(input_obj, ReleaseObservation)

    def apply(self, input_obj: ReleaseObservation, state: AdoptionState):
        findings = state.findings
        if not input_obj.recommended_install_succeeded:
            findings = findings + (
                "recommended install command failed in a clean venv",
            )
        if input_obj.normal_editable_install_succeeded:
            findings = findings + ("normal editable install succeeded",)
        new_state = AdoptionState(
            release=state.release,
            cloned=state.cloned,
            release_ref_checked=state.release_ref_checked,
            clean_venv=state.clean_venv,
            recommended_install_succeeded=input_obj.recommended_install_succeeded,
            normal_install_succeeded=input_obj.normal_editable_install_succeeded,
            import_ok=input_obj.import_preflight_succeeded,
            public_tests_ok=state.public_tests_ok,
            examples_ok=state.examples_ok,
            skill_assets_ok=state.skill_assets_ok,
            helper_install_ok=state.helper_install_ok,
            status=state.status,
            findings=findings,
        )
        label = (
            "recommended_install_ok"
            if input_obj.recommended_install_succeeded
            else "recommended_install_failed"
        )
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label=label,
            reason="checked whether the documented install command works in a clean venv",
        )


class CheckPublicCommands:
    name = "CheckPublicCommands"
    reads = ("public_tests", "examples")
    writes = ("public_command_status",)
    accepted_input_type = ReleaseObservation
    input_description = "observed public checks"
    output_description = "public check readiness"
    idempotency = "pure observation projection"

    def can_accept(self, input_obj: object) -> bool:
        return isinstance(input_obj, ReleaseObservation)

    def apply(self, input_obj: ReleaseObservation, state: AdoptionState):
        commands_ok = input_obj.public_tests_succeeded and input_obj.examples_succeeded
        new_state = AdoptionState(
            release=state.release,
            cloned=state.cloned,
            release_ref_checked=state.release_ref_checked,
            clean_venv=state.clean_venv,
            recommended_install_succeeded=state.recommended_install_succeeded,
            normal_install_succeeded=state.normal_install_succeeded,
            import_ok=state.import_ok,
            public_tests_ok=input_obj.public_tests_succeeded,
            examples_ok=input_obj.examples_succeeded,
            skill_assets_ok=state.skill_assets_ok,
            helper_install_ok=state.helper_install_ok,
            status=state.status,
            findings=state.findings,
        )
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label="public_commands_ok" if commands_ok else "public_commands_failed",
            reason="public tests and examples were executed from the release checkout",
        )


class CheckSkillAssets:
    name = "CheckSkillAssets"
    reads = ("skill_assets", "toolchain_helper")
    writes = ("skill_asset_status",)
    accepted_input_type = ReleaseObservation
    input_description = "observed Skill assets"
    output_description = "Skill readiness"
    idempotency = "pure observation projection"

    def can_accept(self, input_obj: object) -> bool:
        return isinstance(input_obj, ReleaseObservation)

    def apply(self, input_obj: ReleaseObservation, state: AdoptionState):
        findings = state.findings
        if not input_obj.helper_install_from_outside_repo_succeeded:
            findings = findings + (
                "toolchain helper did not install from outside the source tree",
            )
        new_state = AdoptionState(
            release=state.release,
            cloned=state.cloned,
            release_ref_checked=state.release_ref_checked,
            clean_venv=state.clean_venv,
            recommended_install_succeeded=state.recommended_install_succeeded,
            normal_install_succeeded=state.normal_install_succeeded,
            import_ok=state.import_ok,
            public_tests_ok=state.public_tests_ok,
            examples_ok=state.examples_ok,
            skill_assets_ok=input_obj.skill_assets_present,
            helper_install_ok=input_obj.helper_install_from_outside_repo_succeeded,
            status=state.status,
            findings=findings,
        )
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label="skill_assets_ok" if input_obj.skill_assets_present else "skill_assets_missing",
            reason="checked public Codex Skill and toolchain helper assets",
        )


class ClassifyAdoption:
    name = "ClassifyAdoption"
    reads = ("adoption_state",)
    writes = ("status",)
    accepted_input_type = ReleaseObservation
    input_description = "observed release adoption"
    output_description = "adoption status"
    idempotency = "pure classification"

    def can_accept(self, input_obj: object) -> bool:
        return isinstance(input_obj, ReleaseObservation)

    def apply(self, input_obj: ReleaseObservation, state: AdoptionState):
        ready = all(
            (
                state.cloned,
                state.release_ref_checked,
                state.clean_venv,
                state.recommended_install_succeeded,
                state.normal_install_succeeded,
                state.import_ok,
                state.public_tests_ok,
                state.examples_ok,
                state.skill_assets_ok,
                state.helper_install_ok,
            )
        )
        status = "ready_for_public_adoption" if ready else "needs_release_patch"
        new_state = AdoptionState(
            release=state.release,
            cloned=state.cloned,
            release_ref_checked=state.release_ref_checked,
            clean_venv=state.clean_venv,
            recommended_install_succeeded=state.recommended_install_succeeded,
            normal_install_succeeded=state.normal_install_succeeded,
            import_ok=state.import_ok,
            public_tests_ok=state.public_tests_ok,
            examples_ok=state.examples_ok,
            skill_assets_ok=state.skill_assets_ok,
            helper_install_ok=state.helper_install_ok,
            status=status,
            findings=state.findings,
        )
        yield FunctionResult(
            output=status,
            new_state=new_state,
            label=status,
            reason="classified whether the public release is ready for fresh-user adoption",
        )


class PublicReleaseInstallInvariant:
    name = "public_release_documented_install_works"
    description = "The documented install command must work in a clean virtual environment."

    def check(self, state: AdoptionState, trace: Trace) -> InvariantResult:
        if not state.release:
            return InvariantResult.pass_()
        if state.recommended_install_succeeded:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            "documented install command failed in clean venv",
            metadata=(("release", state.release),),
        )


class PublicChecksPassInvariant:
    name = "public_release_checks_pass"
    description = "Public tests and examples must pass from the release checkout."

    def check(self, state: AdoptionState, trace: Trace) -> InvariantResult:
        if not state.release:
            return InvariantResult.pass_()
        if state.import_ok and state.public_tests_ok and state.examples_ok:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            "public import/tests/examples did not all pass",
            metadata=(("release", state.release),),
        )


class SkillHelperInstallInvariant:
    name = "skill_helper_install_from_outside_repo_works"
    description = "The Skill toolchain helper must install from outside the source tree."

    def check(self, state: AdoptionState, trace: Trace) -> InvariantResult:
        if not state.release:
            return InvariantResult.pass_()
        if state.skill_assets_ok and state.helper_install_ok:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            "Skill helper did not prove install from outside source tree",
            metadata=(("release", state.release),),
        )


INVARIANTS = (
    PublicReleaseInstallInvariant(),
    PublicChecksPassInvariant(),
    SkillHelperInstallInvariant(),
)


def build_workflow() -> Workflow:
    return Workflow(
        [
            CheckClone(),
            CheckInstall(),
            CheckPublicCommands(),
            CheckSkillAssets(),
            ClassifyAdoption(),
        ]
    )


def observations() -> tuple[ReleaseObservation, ReleaseObservation]:
    return (
        ReleaseObservation(
            release="v0.1.0",
            cloned_from_github=True,
            checked_out_release_ref=True,
            clean_venv_created=True,
            recommended_install_command=(
                "python -m pip install -e . --no-deps --no-build-isolation"
            ),
            recommended_install_succeeded=False,
            normal_editable_install_succeeded=True,
            import_preflight_succeeded=True,
            public_tests_succeeded=True,
            examples_succeeded=True,
            skill_assets_present=True,
            helper_install_from_outside_repo_succeeded=False,
            notes=(
                "fresh clone from GitHub succeeded",
                "normal editable install worked after the narrow command failed",
            ),
        ),
        ReleaseObservation(
            release="v0.1.1",
            cloned_from_github=True,
            checked_out_release_ref=True,
            clean_venv_created=True,
            recommended_install_command="python -m pip install -e .",
            recommended_install_succeeded=True,
            normal_editable_install_succeeded=True,
            import_preflight_succeeded=True,
            public_tests_succeeded=True,
            examples_succeeded=True,
            skill_assets_present=True,
            helper_install_from_outside_repo_succeeded=True,
            notes=(
                "fresh clone release workflow uses normal editable install",
                "toolchain helper installs successfully from outside the source tree",
            ),
        ),
    )


def scenarios() -> tuple[Scenario, ...]:
    old_release, patched_release = observations()
    workflow = build_workflow()
    return (
        Scenario(
            name="PRA01_v0_1_0_fresh_user_adoption_finds_install_gap",
            description="v0.1.0 release works after manual recovery but documents a fragile install command.",
            initial_state=INITIAL_STATE,
            external_input_sequence=(old_release,),
            workflow=workflow,
            invariants=INVARIANTS,
            expected=ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=(
                    "public_release_documented_install_works",
                    "skill_helper_install_from_outside_repo_works",
                ),
                summary="VIOLATION; fresh clone exposed documented install/helper gap",
            ),
            tags=("public-release", "fresh-clone", "install"),
        ),
        Scenario(
            name="PRA02_v0_1_1_fresh_user_adoption_ready",
            description="Patched release uses normal editable install and helper install succeeds.",
            initial_state=INITIAL_STATE,
            external_input_sequence=(patched_release,),
            workflow=workflow,
            invariants=INVARIANTS,
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("ready_for_public_adoption",),
                summary="OK; fresh clone, install, tests, examples, and Skill helper all pass",
            ),
            tags=("public-release", "fresh-clone", "install"),
        ),
    )


__all__ = [
    "AdoptionState",
    "ReleaseObservation",
    "INITIAL_STATE",
    "INVARIANTS",
    "build_workflow",
    "observations",
    "scenarios",
]
