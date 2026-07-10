"""FlowGuard model for a verified public release and distribution refresh.

Risk Intent Brief
-----------------
Failure modes:
- The public template update copies private project-control artifacts instead
  of distilling neutral, reusable FlowGuard patterns.
- A new template is published without runnable checks, docs, or export wiring.
- GitHub publication happens before tests, privacy scans, and local runtime
  sync have passed.

Protected harms:
- Local project details, private workflows, or user-specific paths leak into
  a public source release.
- New users receive templates that look complete but cannot be executed.
- Local installed and shadow workspace copies drift from the GitHub release.

Model-critical state and side effects:
- Candidate template sources and their privacy classification.
- Template implementation, docs, tests, export wiring, and CLI exposure.
- Validation, privacy scan, local sync, commit, tag, push, release, and
  post-release verification evidence.

Adversarial inputs:
- A private project template is selected directly.
- A template is implemented without tests or docs.
- A release is pushed before validation or local sync.

Hard invariants:
- Published templates must be public-safe and neutral.
- Release requires tests, privacy scan, and local sync.
- Public template changes must have tests and documentation.

Blindspots:
- This model checks the release process boundary. The real code still needs
  unit tests, template execution tests, privacy scans, Git checks, and GitHub
  release verification.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class State:
    selected_public_safe: bool = False
    selected_private_direct: bool = False
    implemented: bool = False
    docs_updated: bool = False
    tests_added: bool = False
    exports_wired: bool = False
    validations_passed: bool = False
    privacy_scanned: bool = False
    local_runtime_synced: bool = False
    committed: bool = False
    tagged: bool = False
    pushed: bool = False
    release_verified: bool = False


@dataclass(frozen=True)
class Event:
    name: str


SELECT_PUBLIC_PATTERNS = Event("select_public_patterns")
SELECT_PRIVATE_DIRECT = Event("select_private_direct")
IMPLEMENT_TEMPLATES = Event("implement_templates")
UPDATE_DOCS = Event("update_docs")
ADD_TESTS = Event("add_tests")
WIRE_EXPORTS = Event("wire_exports")
RUN_VALIDATION = Event("run_validation")
RUN_PRIVACY_SCAN = Event("run_privacy_scan")
SYNC_LOCAL_RUNTIME = Event("sync_local_runtime")
COMMIT = Event("commit")
TAG = Event("tag")
PUSH = Event("push")
VERIFY_RELEASE = Event("verify_release")


class TemplateReleaseStep:
    name = "TemplateReleaseStep"
    reads = (
        "selected_public_safe",
        "selected_private_direct",
        "implemented",
        "docs_updated",
        "tests_added",
        "exports_wired",
        "validations_passed",
        "privacy_scanned",
        "local_runtime_synced",
        "committed",
        "tagged",
        "pushed",
    )
    writes = (
        "selected_public_safe",
        "selected_private_direct",
        "implemented",
        "docs_updated",
        "tests_added",
        "exports_wired",
        "validations_passed",
        "privacy_scanned",
        "local_runtime_synced",
        "committed",
        "tagged",
        "pushed",
        "release_verified",
    )
    accepted_input_type = Event
    input_description = "release process event"
    output_description = "updated public template release state"
    idempotency = "repeated events keep the same evidence flags instead of duplicating release side effects"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "select_public_patterns":
            yield FunctionResult(
                "public_patterns_selected",
                replace(state, selected_public_safe=True),
                label="public_patterns_selected",
            )
            return

        if input_obj.name == "select_private_direct":
            yield FunctionResult(
                "private_template_selected_directly",
                replace(state, selected_private_direct=True),
                label="private_template_selected_directly",
            )
            return

        if input_obj.name == "implement_templates":
            if not state.selected_public_safe or state.selected_private_direct:
                yield FunctionResult("implementation_blocked", state, label="blocked")
                return
            yield FunctionResult("templates_implemented", replace(state, implemented=True), label="implemented")
            return

        if input_obj.name == "update_docs":
            if not state.implemented:
                yield FunctionResult("docs_waiting_for_templates", state, label="blocked")
                return
            yield FunctionResult("docs_updated", replace(state, docs_updated=True), label="docs_updated")
            return

        if input_obj.name == "add_tests":
            if not state.implemented:
                yield FunctionResult("tests_waiting_for_templates", state, label="blocked")
                return
            yield FunctionResult("tests_added", replace(state, tests_added=True), label="tests_added")
            return

        if input_obj.name == "wire_exports":
            if not state.implemented:
                yield FunctionResult("exports_waiting_for_templates", state, label="blocked")
                return
            yield FunctionResult("exports_wired", replace(state, exports_wired=True), label="exports_wired")
            return

        if input_obj.name == "run_validation":
            if not (state.implemented and state.tests_added and state.exports_wired):
                yield FunctionResult("validation_waiting_for_complete_templates", state, label="blocked")
                return
            yield FunctionResult("validations_passed", replace(state, validations_passed=True), label="validated")
            return

        if input_obj.name == "run_privacy_scan":
            if not state.implemented:
                yield FunctionResult("privacy_scan_waiting_for_templates", state, label="blocked")
                return
            yield FunctionResult("privacy_scan_passed", replace(state, privacy_scanned=True), label="privacy_scanned")
            return

        if input_obj.name == "sync_local_runtime":
            if not state.validations_passed:
                yield FunctionResult("local_sync_waiting_for_validation", state, label="blocked")
                return
            yield FunctionResult(
                "local_runtime_synced",
                replace(state, local_runtime_synced=True),
                label="local_runtime_synced",
            )
            return

        if input_obj.name == "commit":
            if not (state.validations_passed and state.privacy_scanned):
                yield FunctionResult("commit_blocked_until_checks_pass", state, label="blocked")
                return
            yield FunctionResult("committed", replace(state, committed=True), label="committed")
            return

        if input_obj.name == "tag":
            if not state.committed:
                yield FunctionResult("tag_blocked_until_commit", state, label="blocked")
                return
            yield FunctionResult("tagged", replace(state, tagged=True), label="tagged")
            return

        if input_obj.name == "push":
            if not (state.tagged and state.local_runtime_synced):
                yield FunctionResult("push_blocked_until_tag_and_sync", state, label="blocked")
                return
            yield FunctionResult("pushed", replace(state, pushed=True), label="pushed")
            return

        if input_obj.name == "verify_release":
            if not state.pushed:
                yield FunctionResult("release_verify_waiting_for_push", state, label="blocked")
                return
            yield FunctionResult(
                "release_verified",
                replace(state, release_verified=True),
                label="release_verified",
            )
            return

        yield FunctionResult("unknown_event", state, label="blocked")


class BrokenPrivateTemplateStep(TemplateReleaseStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "implement_templates":
            yield FunctionResult(
                "implemented_private_template",
                replace(state, implemented=True, selected_private_direct=True),
                label="broken_private_template_implemented",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenReleaseBeforeValidationStep(TemplateReleaseStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "push":
            yield FunctionResult(
                "pushed_without_required_evidence",
                replace(state, pushed=True),
                label="broken_pushed_without_required_evidence",
            )
            return
        yield from super().apply(input_obj, state)


def public_release_invariants() -> tuple[Invariant, ...]:
    def no_private_public_template(state: State, _trace: object) -> InvariantResult:
        if state.implemented and state.selected_private_direct:
            return InvariantResult.fail("private project template selected directly for public release")
        return InvariantResult.pass_()

    def templates_require_docs_tests_and_exports(state: State, _trace: object) -> InvariantResult:
        if state.validations_passed and not (state.docs_updated and state.tests_added and state.exports_wired):
            return InvariantResult.fail("template validation passed without docs, tests, and export wiring")
        return InvariantResult.pass_()

    def release_requires_checks_and_sync(state: State, _trace: object) -> InvariantResult:
        if state.pushed and not (state.validations_passed and state.privacy_scanned and state.local_runtime_synced):
            return InvariantResult.fail("release pushed before validation, privacy scan, or local runtime sync")
        return InvariantResult.pass_()

    return (
        Invariant("no_private_public_template", "Public templates must be neutral and privacy-safe.", no_private_public_template),
        Invariant(
            "templates_require_docs_tests_and_exports",
            "Template checks require docs, tests, and export wiring.",
            templates_require_docs_tests_and_exports,
        ),
        Invariant(
            "release_requires_checks_and_sync",
            "Publication requires validation, privacy scan, and local runtime sync.",
            release_requires_checks_and_sync,
        ),
    )


def workflow(block: object | None = None) -> Workflow:
    return Workflow((block or TemplateReleaseStep(),), name="template_public_release")


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
        invariants=public_release_invariants(),
    )


def main() -> int:
    reviews = (
        review_scenario(
            scenario(
                name="correct_template_release",
                description="Public-safe template patterns are implemented, checked, synced, and released.",
                events=(
                    SELECT_PUBLIC_PATTERNS,
                    IMPLEMENT_TEMPLATES,
                    UPDATE_DOCS,
                    ADD_TESTS,
                    WIRE_EXPORTS,
                    RUN_VALIDATION,
                    RUN_PRIVACY_SCAN,
                    SYNC_LOCAL_RUNTIME,
                    COMMIT,
                    TAG,
                    PUSH,
                    VERIFY_RELEASE,
                ),
                expected=ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("release_verified",),
                    summary="safe public template release reaches verified release",
                ),
            )
        ),
    )
    broken_report = review_scenarios(
        (
            scenario(
                name="private_template_leak",
                description="A broken implementation publishes a private project template directly.",
                events=(SELECT_PRIVATE_DIRECT, IMPLEMENT_TEMPLATES),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_private_public_template",),
                    summary="private project templates must not become public templates",
                ),
                block=BrokenPrivateTemplateStep(),
            ),
            scenario(
                name="release_before_checks",
                description="A broken implementation pushes before checks and local sync.",
                events=(PUSH,),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("release_requires_checks_and_sync",),
                    summary="release push requires validation, privacy scan, and local sync",
                ),
                block=BrokenReleaseBeforeValidationStep(),
            ),
        )
    )

    for result in reviews:
        print(f"{result.scenario_name}: {result.status.upper()}")
        for item in result.evidence:
            print(f"  - {item}")
    print()
    print(broken_report.format_text(max_counterexamples=2))

    return 0 if all(result.ok for result in reviews) and broken_report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
