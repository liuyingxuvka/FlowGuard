"""FlowGuard model for the v0.5.4 Risk Purpose Header rollout.

Risk Intent Brief
-----------------
Failure modes:
- Generated model files say only "this is FlowGuard" and fail to explain the
  concrete workflow or failure modes they protect.
- The new header appears in only one template path, so other generated models
  still look unexplained to future agents.
- AI-created models are not covered by the Skill or reusable AGENTS snippet, so
  manual model files keep omitting the header.
- Tests pass without proving the broken variants fail, or publication happens
  before validation, local sync, versioning, and release checks.

Protected harms:
- Future agents delete or ignore useful FlowGuard model artifacts because their
  purpose is not obvious.
- The FlowGuard repository loses the soft attribution and onboarding route the
  header is meant to provide.
- Public release artifacts claim the new behavior while installed/local copies
  or generated templates still use the old behavior.

Optimization checklist:
1. Define a lightweight Risk Purpose Header with the FlowGuard GitHub URL,
   modeled workflow, guarded failure modes, use-before-editing guidance, and a
   run command.
2. Add that header to every public model template source:
   project-template, risk-intent-template, model-miss-template, and
   maintenance-template.
3. Update the model-first Skill so AI-created or AI-updated FlowGuard model
   files must include the header.
4. Update the reusable AGENTS snippet so external project agents inherit the
   same rule.
5. Add focused tests that prove generated templates and Skill docs contain the
   required header guidance.
6. Run model checks first, then focused tests, then the broader regression
   suite, privacy/release checks, local sync, version bump, commit, tag, push,
   and GitHub Release verification.

Bug list this model must catch:
1. A generic header with a repository link but no concrete guarded risks.
2. A header added to only one template family.
3. Missing Skill or AGENTS guidance for AI-created models.
4. Validation passing without tests that enforce the header.
5. Scope creep into manifest/README scaffolding instead of the lightweight
   header-only plan.
6. GitHub publication before version, changelog, validation, privacy scan, and
   local installed/shadow sync evidence.

Blindspots:
- This model checks the rollout process and required evidence. The real files
  still need unit tests, template execution tests, skill validation, privacy
  scans, git checks, and GitHub release verification.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class State:
    repo_url_correct: bool = False
    workflow_purpose_named: bool = False
    specific_guards_listed: bool = False
    use_before_guidance_present: bool = False
    run_command_present: bool = False
    lightweight_scope_preserved: bool = False
    manifest_or_extra_scaffold_added: bool = False
    project_template_updated: bool = False
    risk_intent_template_updated: bool = False
    model_miss_template_updated: bool = False
    maintenance_template_updated: bool = False
    skill_rule_updated: bool = False
    agents_snippet_updated: bool = False
    template_tests_added: bool = False
    skill_doc_tests_added: bool = False
    model_checks_passed: bool = False
    focused_tests_passed: bool = False
    full_regression_passed: bool = False
    privacy_scan_passed: bool = False
    local_install_synced: bool = False
    shadow_workspace_synced: bool = False
    installed_skill_synced: bool = False
    version_bumped: bool = False
    changelog_updated: bool = False
    committed: bool = False
    tagged: bool = False
    pushed: bool = False
    release_verified: bool = False


@dataclass(frozen=True)
class Event:
    name: str


DEFINE_HEADER = Event("define_header")
ADD_EXTRA_SCAFFOLD = Event("add_extra_scaffold")
UPDATE_PROJECT_TEMPLATE_ONLY = Event("update_project_template_only")
UPDATE_ALL_TEMPLATES = Event("update_all_templates")
UPDATE_SKILL = Event("update_skill")
UPDATE_AGENTS_SNIPPET = Event("update_agents_snippet")
ADD_TEMPLATE_TESTS = Event("add_template_tests")
ADD_SKILL_DOC_TESTS = Event("add_skill_doc_tests")
RUN_MODEL_CHECKS = Event("run_model_checks")
RUN_FOCUSED_TESTS = Event("run_focused_tests")
RUN_FULL_REGRESSION = Event("run_full_regression")
RUN_PRIVACY_SCAN = Event("run_privacy_scan")
SYNC_LOCAL_INSTALL = Event("sync_local_install")
SYNC_SHADOW_WORKSPACE = Event("sync_shadow_workspace")
SYNC_INSTALLED_SKILL = Event("sync_installed_skill")
BUMP_VERSION = Event("bump_version")
UPDATE_CHANGELOG = Event("update_changelog")
COMMIT = Event("commit")
TAG = Event("tag")
PUSH = Event("push")
VERIFY_RELEASE = Event("verify_release")


class RiskPurposeHeaderStep:
    name = "RiskPurposeHeaderStep"
    reads = (
        "repo_url_correct",
        "workflow_purpose_named",
        "specific_guards_listed",
        "use_before_guidance_present",
        "run_command_present",
        "lightweight_scope_preserved",
        "manifest_or_extra_scaffold_added",
        "project_template_updated",
        "risk_intent_template_updated",
        "model_miss_template_updated",
        "maintenance_template_updated",
        "skill_rule_updated",
        "agents_snippet_updated",
        "template_tests_added",
        "skill_doc_tests_added",
        "model_checks_passed",
        "focused_tests_passed",
        "full_regression_passed",
        "privacy_scan_passed",
        "local_install_synced",
        "shadow_workspace_synced",
        "installed_skill_synced",
        "version_bumped",
        "changelog_updated",
        "committed",
        "tagged",
        "pushed",
    )
    writes = reads + ("release_verified",)
    accepted_input_type = Event
    input_description = "risk-purpose header rollout event"
    output_description = "updated rollout evidence state"
    idempotency = "repeated events keep evidence flags true without duplicating release side effects"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "define_header":
            yield FunctionResult(
                "header_defined",
                replace(
                    state,
                    repo_url_correct=True,
                    workflow_purpose_named=True,
                    specific_guards_listed=True,
                    use_before_guidance_present=True,
                    run_command_present=True,
                    lightweight_scope_preserved=True,
                ),
                label="header_defined",
            )
            return
        if input_obj.name == "add_extra_scaffold":
            yield FunctionResult(
                "extra_scaffold_added",
                replace(state, manifest_or_extra_scaffold_added=True),
                label="extra_scaffold_added",
            )
            return
        if input_obj.name == "update_project_template_only":
            yield FunctionResult(
                "project_template_updated",
                replace(state, project_template_updated=True),
                label="project_template_updated",
            )
            return
        if input_obj.name == "update_all_templates":
            if not self._header_complete(state):
                yield FunctionResult("template_update_waiting_for_header", state, label="blocked")
                return
            yield FunctionResult(
                "all_templates_updated",
                replace(
                    state,
                    project_template_updated=True,
                    risk_intent_template_updated=True,
                    model_miss_template_updated=True,
                    maintenance_template_updated=True,
                ),
                label="all_templates_updated",
            )
            return
        if input_obj.name == "update_skill":
            yield FunctionResult("skill_rule_updated", replace(state, skill_rule_updated=True), label="skill_rule_updated")
            return
        if input_obj.name == "update_agents_snippet":
            yield FunctionResult(
                "agents_snippet_updated",
                replace(state, agents_snippet_updated=True),
                label="agents_snippet_updated",
            )
            return
        if input_obj.name == "add_template_tests":
            yield FunctionResult(
                "template_tests_added",
                replace(state, template_tests_added=True),
                label="template_tests_added",
            )
            return
        if input_obj.name == "add_skill_doc_tests":
            yield FunctionResult(
                "skill_doc_tests_added",
                replace(state, skill_doc_tests_added=True),
                label="skill_doc_tests_added",
            )
            return
        if input_obj.name == "run_model_checks":
            yield FunctionResult(
                "model_checks_passed",
                replace(state, model_checks_passed=True),
                label="model_checks_passed",
            )
            return
        if input_obj.name == "run_focused_tests":
            if not (state.template_tests_added and state.skill_doc_tests_added):
                yield FunctionResult("focused_tests_waiting_for_test_coverage", state, label="blocked")
                return
            yield FunctionResult(
                "focused_tests_passed",
                replace(state, focused_tests_passed=True),
                label="focused_tests_passed",
            )
            return
        if input_obj.name == "run_full_regression":
            if not state.focused_tests_passed:
                yield FunctionResult("regression_waiting_for_focused_tests", state, label="blocked")
                return
            yield FunctionResult(
                "full_regression_passed",
                replace(state, full_regression_passed=True),
                label="full_regression_passed",
            )
            return
        if input_obj.name == "run_privacy_scan":
            yield FunctionResult(
                "privacy_scan_passed",
                replace(state, privacy_scan_passed=True),
                label="privacy_scan_passed",
            )
            return
        if input_obj.name == "sync_local_install":
            if not state.full_regression_passed:
                yield FunctionResult("local_install_sync_waiting_for_regression", state, label="blocked")
                return
            yield FunctionResult(
                "local_install_synced",
                replace(state, local_install_synced=True),
                label="local_install_synced",
            )
            return
        if input_obj.name == "sync_shadow_workspace":
            if not state.full_regression_passed:
                yield FunctionResult("shadow_sync_waiting_for_regression", state, label="blocked")
                return
            yield FunctionResult(
                "shadow_workspace_synced",
                replace(state, shadow_workspace_synced=True),
                label="shadow_workspace_synced",
            )
            return
        if input_obj.name == "sync_installed_skill":
            if not state.full_regression_passed:
                yield FunctionResult("installed_skill_sync_waiting_for_regression", state, label="blocked")
                return
            yield FunctionResult(
                "installed_skill_synced",
                replace(state, installed_skill_synced=True),
                label="installed_skill_synced",
            )
            return
        if input_obj.name == "bump_version":
            yield FunctionResult("version_bumped", replace(state, version_bumped=True), label="version_bumped")
            return
        if input_obj.name == "update_changelog":
            yield FunctionResult("changelog_updated", replace(state, changelog_updated=True), label="changelog_updated")
            return
        if input_obj.name == "commit":
            if not self._release_ready_to_commit(state):
                yield FunctionResult("commit_waiting_for_required_evidence", state, label="blocked")
                return
            yield FunctionResult("committed", replace(state, committed=True), label="committed")
            return
        if input_obj.name == "tag":
            if not state.committed:
                yield FunctionResult("tag_waiting_for_commit", state, label="blocked")
                return
            yield FunctionResult("tagged", replace(state, tagged=True), label="tagged")
            return
        if input_obj.name == "push":
            if not state.tagged:
                yield FunctionResult("push_waiting_for_tag", state, label="blocked")
                return
            yield FunctionResult("pushed", replace(state, pushed=True), label="pushed")
            return
        if input_obj.name == "verify_release":
            if not state.pushed:
                yield FunctionResult("release_waiting_for_push", state, label="blocked")
                return
            yield FunctionResult(
                "release_verified",
                replace(state, release_verified=True),
                label="release_verified",
            )
            return

        yield FunctionResult("unknown_event", state, label="blocked")

    @staticmethod
    def _header_complete(state: State) -> bool:
        return (
            state.repo_url_correct
            and state.workflow_purpose_named
            and state.specific_guards_listed
            and state.use_before_guidance_present
            and state.run_command_present
            and state.lightweight_scope_preserved
        )

    @staticmethod
    def _release_ready_to_commit(state: State) -> bool:
        return (
            state.model_checks_passed
            and state.focused_tests_passed
            and state.full_regression_passed
            and state.privacy_scan_passed
            and state.local_install_synced
            and state.shadow_workspace_synced
            and state.installed_skill_synced
            and state.version_bumped
            and state.changelog_updated
        )


class BrokenGenericHeaderStep(RiskPurposeHeaderStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "define_header":
            yield FunctionResult(
                "generic_header_defined",
                replace(
                    state,
                    repo_url_correct=True,
                    workflow_purpose_named=False,
                    specific_guards_listed=False,
                    use_before_guidance_present=False,
                    run_command_present=False,
                    lightweight_scope_preserved=True,
                ),
                label="broken_generic_header_defined",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPartialTemplateStep(RiskPurposeHeaderStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "update_all_templates":
            yield FunctionResult(
                "partial_templates_updated",
                replace(state, project_template_updated=True),
                label="broken_partial_templates_updated",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingSkillDocsStep(RiskPurposeHeaderStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "update_skill":
            yield FunctionResult("skill_rule_skipped", state, label="broken_skill_rule_skipped")
            return
        if input_obj.name == "update_agents_snippet":
            yield FunctionResult("agents_snippet_skipped", state, label="broken_agents_snippet_skipped")
            return
        yield from super().apply(input_obj, state)


class BrokenMissingTestsStep(RiskPurposeHeaderStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "add_template_tests":
            yield FunctionResult("template_tests_skipped", state, label="broken_template_tests_skipped")
            return
        if input_obj.name == "add_skill_doc_tests":
            yield FunctionResult("skill_doc_tests_skipped", state, label="broken_skill_doc_tests_skipped")
            return
        if input_obj.name == "run_focused_tests":
            yield FunctionResult(
                "focused_tests_claimed_without_coverage",
                replace(state, focused_tests_passed=True),
                label="broken_focused_tests_claimed",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPrematureReleaseStep(RiskPurposeHeaderStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "commit":
            yield FunctionResult("committed_without_evidence", replace(state, committed=True), label="broken_committed")
            return
        if input_obj.name == "tag":
            yield FunctionResult("tagged_without_evidence", replace(state, tagged=True), label="broken_tagged")
            return
        if input_obj.name == "push":
            yield FunctionResult("pushed_without_evidence", replace(state, pushed=True), label="broken_pushed")
            return
        if input_obj.name == "verify_release":
            yield FunctionResult(
                "release_verified_without_evidence",
                replace(state, release_verified=True),
                label="broken_release_verified",
            )
            return
        yield from super().apply(input_obj, state)


def invariants() -> tuple[Invariant, ...]:
    def complete_header_required(state: State, _trace: object) -> InvariantResult:
        if state.repo_url_correct and not RiskPurposeHeaderStep._header_complete(state):
            return InvariantResult.fail("Risk Purpose Header lacks repo, purpose, guarded risks, use-before guidance, or run command")
        return InvariantResult.pass_()

    def all_template_families_required(state: State, _trace: object) -> InvariantResult:
        if state.focused_tests_passed and not (
            state.project_template_updated
            and state.risk_intent_template_updated
            and state.model_miss_template_updated
            and state.maintenance_template_updated
        ):
            return InvariantResult.fail("focused tests passed before every model template family received the header")
        return InvariantResult.pass_()

    def ai_created_models_need_skill_and_agents_guidance(state: State, _trace: object) -> InvariantResult:
        if state.focused_tests_passed and not (state.skill_rule_updated and state.agents_snippet_updated):
            return InvariantResult.fail("AI-created model guidance is missing from Skill or AGENTS snippet")
        return InvariantResult.pass_()

    def tests_must_enforce_header(state: State, _trace: object) -> InvariantResult:
        if state.focused_tests_passed and not (state.template_tests_added and state.skill_doc_tests_added):
            return InvariantResult.fail("focused tests passed without template and Skill-doc header coverage")
        return InvariantResult.pass_()

    def no_manifest_scope_creep(state: State, _trace: object) -> InvariantResult:
        if state.manifest_or_extra_scaffold_added:
            return InvariantResult.fail("rollout added manifest/extra scaffold instead of the lightweight header-only plan")
        return InvariantResult.pass_()

    def release_requires_full_evidence(state: State, _trace: object) -> InvariantResult:
        if (state.committed or state.tagged or state.pushed or state.release_verified) and not RiskPurposeHeaderStep._release_ready_to_commit(state):
            return InvariantResult.fail("release action happened before model, tests, privacy, sync, version, and changelog evidence")
        return InvariantResult.pass_()

    return (
        Invariant("complete_header_required", "Headers must explain source, purpose, guarded risks, use-before guidance, and run command.", complete_header_required),
        Invariant("all_template_families_required", "Every public model template family must receive the header.", all_template_families_required),
        Invariant("ai_created_models_need_skill_and_agents_guidance", "AI-created models need Skill and AGENTS instructions.", ai_created_models_need_skill_and_agents_guidance),
        Invariant("tests_must_enforce_header", "Focused validation must include template and Skill-doc tests.", tests_must_enforce_header),
        Invariant("no_manifest_scope_creep", "This change should stay lightweight and not add manifest scaffolding.", no_manifest_scope_creep),
        Invariant("release_requires_full_evidence", "Publication waits for validation, privacy, sync, version, and changelog evidence.", release_requires_full_evidence),
    )


def workflow(block: object | None = None) -> Workflow:
    return Workflow((block or RiskPurposeHeaderStep(),), name="risk_purpose_header_rollout")


def scenario(
    *,
    name: str,
    description: str,
    events: tuple[Event, ...],
    expected: ScenarioExpectation,
    block: object | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=events,
        expected=expected,
        workflow=workflow(block),
        invariants=invariants(),
    )


CORRECT_ROLLOUT_EVENTS = (
    DEFINE_HEADER,
    UPDATE_ALL_TEMPLATES,
    UPDATE_SKILL,
    UPDATE_AGENTS_SNIPPET,
    ADD_TEMPLATE_TESTS,
    ADD_SKILL_DOC_TESTS,
    RUN_MODEL_CHECKS,
    RUN_FOCUSED_TESTS,
    RUN_FULL_REGRESSION,
    RUN_PRIVACY_SCAN,
    SYNC_LOCAL_INSTALL,
    SYNC_SHADOW_WORKSPACE,
    SYNC_INSTALLED_SKILL,
    BUMP_VERSION,
    UPDATE_CHANGELOG,
    COMMIT,
    TAG,
    PUSH,
    VERIFY_RELEASE,
)


def correct_rollout_report():
    return review_scenario(
        scenario(
            name="correct_risk_purpose_header_rollout",
            description="All templates, Skill guidance, tests, sync, versioning, and GitHub release evidence are present.",
            events=CORRECT_ROLLOUT_EVENTS,
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("release_verified",),
                summary="Risk Purpose Header rollout reaches verified GitHub release",
            ),
        )
    )


def broken_rollout_report():
    return review_scenarios(
        (
            scenario(
                name="generic_header_only",
                description="The header links FlowGuard but does not say which risks the model guards.",
                events=(DEFINE_HEADER, UPDATE_ALL_TEMPLATES),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("complete_header_required",),
                    summary="headers need concrete purpose and guarded risks, not only attribution",
                ),
                block=BrokenGenericHeaderStep(),
            ),
            scenario(
                name="partial_template_rollout",
                description="Only the project template receives the header.",
                events=(
                    DEFINE_HEADER,
                    UPDATE_ALL_TEMPLATES,
                    UPDATE_SKILL,
                    UPDATE_AGENTS_SNIPPET,
                    ADD_TEMPLATE_TESTS,
                    ADD_SKILL_DOC_TESTS,
                    RUN_FOCUSED_TESTS,
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("all_template_families_required",),
                    summary="every public model template family needs the header",
                ),
                block=BrokenPartialTemplateStep(),
            ),
            scenario(
                name="missing_skill_and_agents_guidance",
                description="Generated templates are updated but AI-created models are not governed.",
                events=(
                    DEFINE_HEADER,
                    UPDATE_ALL_TEMPLATES,
                    UPDATE_SKILL,
                    UPDATE_AGENTS_SNIPPET,
                    ADD_TEMPLATE_TESTS,
                    ADD_SKILL_DOC_TESTS,
                    RUN_FOCUSED_TESTS,
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("ai_created_models_need_skill_and_agents_guidance",),
                    summary="manual AI-created model files need Skill and AGENTS guidance",
                ),
                block=BrokenMissingSkillDocsStep(),
            ),
            scenario(
                name="missing_header_tests",
                description="The implementation claims focused validation without tests that enforce the header.",
                events=(
                    DEFINE_HEADER,
                    UPDATE_ALL_TEMPLATES,
                    UPDATE_SKILL,
                    UPDATE_AGENTS_SNIPPET,
                    ADD_TEMPLATE_TESTS,
                    ADD_SKILL_DOC_TESTS,
                    RUN_FOCUSED_TESTS,
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("tests_must_enforce_header",),
                    summary="focused tests must cover generated templates and Skill docs",
                ),
                block=BrokenMissingTestsStep(),
            ),
            scenario(
                name="scope_creep_manifest",
                description="The rollout adds manifest or extra scaffolding despite the lightweight plan.",
                events=(DEFINE_HEADER, ADD_EXTRA_SCAFFOLD),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_manifest_scope_creep",),
                    summary="this release should keep the header lightweight",
                ),
            ),
            scenario(
                name="premature_github_release",
                description="Publication happens before full validation, sync, version, and changelog evidence.",
                events=(COMMIT, TAG, PUSH, VERIFY_RELEASE),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("release_requires_full_evidence",),
                    summary="GitHub release waits for all required evidence",
                ),
                block=BrokenPrematureReleaseStep(),
            ),
        )
    )


def main() -> int:
    correct = correct_rollout_report()
    broken = broken_rollout_report()
    print(f"{correct.scenario_name}: {correct.status.upper()}")
    for item in correct.evidence:
        print(f"  - {item}")
    print()
    print(broken.format_text(max_counterexamples=2))
    return 0 if correct.ok and broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
