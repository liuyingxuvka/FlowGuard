"""FlowGuard model for explicit template reuse plus verified public release.

Risk Intent Brief
-----------------
Failure modes:
- Ordinary minimum-model work triggers template-library search even though no
  caller requested template reuse.
- Search, reuse, merge, or harvest proceeds without its explicit request,
  source identities, conflict/duplicate disposition, complete reusable
  contract, or current code/test binding.
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
- Explicit template-lifecycle request identity; search sources and matches;
  reused, merged, harvested, or duplicate-linked template identities; and the
  exact code/test bindings that protect each operation.
- Candidate template sources and their privacy classification.
- Template implementation, docs, tests, export wiring, and CLI exposure.
- Validation, privacy scan, local sync, commit, tag, push, release, and
  post-release verification evidence.

Adversarial inputs:
- An ordinary minimum-model request silently triggers a template search.
- Merge or harvest is attempted without authorization, sources, duplicate or
  conflict disposition, or a complete protected-error contract.
- A private project template is selected directly.
- A template is implemented without tests or docs.
- A release is pushed before validation or local sync.

Hard invariants:
- Template-library work is on-demand: only an explicit request may enter the
  search/reuse/merge/harvest lifecycle.
- Merge and harvest require explicit authorization, complete provenance,
  duplicate/conflict handling, a complete reusable contract, and current
  production/test bindings.
- Published templates must be public-safe and neutral.
- Release requires tests, privacy scan, and local sync.
- Public template changes must have tests and documentation.

Blindspots:
- This model checks the release process boundary. The real code still needs
  unit tests, template execution tests, privacy scans, Git checks, and GitHub
  release verification.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


TEMPLATE_OPERATION_KINDS = ("search", "reuse", "merge", "harvest")
TEMPLATE_HARVEST_DISPOSITIONS = (
    "written",
    "merged",
    "duplicate_linked",
    "not_harvestable",
)

CURRENT_CODE_BINDINGS = {
    "search": (
        "flowguard/risk_templates.py::search_risk_templates",
    ),
    "reuse": (
        "flowguard/risk_templates.py::review_template_reuse",
    ),
    "merge": (
        "flowguard/risk_templates.py::merge_risk_templates",
    ),
    "harvest": (
        "flowguard/risk_templates.py::harvest_risk_template_candidate",
        "flowguard/risk_templates.py::review_template_harvest_closure",
        "flowguard/risk_templates.py::write_local_risk_template",
    ),
}

CURRENT_TEST_BINDINGS = {
    "search": (
        "tests/test_risk_templates.py::RiskTemplateTests::test_search_uses_public_and_local_layers",
        "tests/test_risk_templates.py::RiskTemplateTests::test_minimum_model_review_does_not_search_templates",
    ),
    "reuse": (
        "tests/test_risk_templates.py::RiskTemplateTests::test_explicit_template_reuse_review_remains_strict",
    ),
    "merge": (
        "tests/test_risk_templates.py::RiskTemplateTests::test_merge_keeps_known_bad_cases_and_sources",
        "tests/test_risk_templates.py::RiskTemplateTests::test_merge_rejects_missing_source_templates",
        "tests/test_risk_templates.py::RiskTemplateTests::test_merge_rejects_conflicting_source_templates_without_rationale",
    ),
    "harvest": (
        "tests/test_risk_templates.py::RiskTemplateTests::test_harvest_candidate_requires_minimum_fields",
        "tests/test_risk_templates.py::RiskTemplateTests::test_harvest_candidate_writes_and_loads_local_card",
        "tests/test_risk_templates.py::RiskTemplateTests::test_harvest_duplicate_write_is_blocked",
    ),
}


@dataclass(frozen=True)
class TemplateOperation:
    """One explicit on-demand template-library operation request."""

    operation_id: str
    kind: str
    request_id: str
    explicitly_requested: bool = False
    authorized: bool = False
    query: str = ""
    searched_layers: tuple[str, ...] = ()
    match_template_ids: tuple[str, ...] = ()
    used_template_ids: tuple[str, ...] = ()
    no_match_reason: str = ""
    source_ids: tuple[str, ...] = ()
    result_template_ids: tuple[str, ...] = ()
    preserved_source_ids: tuple[str, ...] = ()
    duplicate_template_ids: tuple[str, ...] = ()
    conflict_template_ids: tuple[str, ...] = ()
    false_friend_rationale: str = ""
    protected_error_classes: tuple[str, ...] = ()
    modeled_state: tuple[str, ...] = ()
    modeled_side_effects: tuple[str, ...] = ()
    completion_evidence_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    harvest_disposition: str = ""
    not_harvestable_reason: str = ""
    code_binding_ids: tuple[str, ...] = ()
    test_binding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateLifecycleOutput:
    operation_id: str
    kind: str
    status: str
    result_template_ids: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class State:
    explicit_template_request_ids: tuple[str, ...] = ()
    template_operations: tuple[TemplateOperation, ...] = ()
    reused_template_ids: tuple[str, ...] = ()
    merged_template_ids: tuple[str, ...] = ()
    harvested_template_ids: tuple[str, ...] = ()
    template_effects: tuple[str, ...] = ()
    ordinary_minimum_model_observed: bool = False
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
    request_id: str = ""
    operation: TemplateOperation | None = None


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
ORDINARY_MINIMUM_MODEL = Event("ordinary_minimum_model")
EXPLICIT_TEMPLATE_REQUEST_ID = "request:explicit-template-reuse"
OPEN_TEMPLATE_LIFECYCLE = Event(
    "open_template_lifecycle",
    request_id=EXPLICIT_TEMPLATE_REQUEST_ID,
)


def _append_unique(values: tuple[str, ...], items: Iterable[str]) -> tuple[str, ...]:
    result = list(values)
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _record_operation(
    values: tuple[TemplateOperation, ...],
    operation: TemplateOperation,
) -> tuple[TemplateOperation, ...]:
    if any(item.operation_id == operation.operation_id for item in values):
        return tuple(
            operation if item.operation_id == operation.operation_id else item
            for item in values
        )
    return values + (operation,)


def _search_matches(state: State, request_id: str) -> tuple[str, ...] | None:
    for operation in reversed(state.template_operations):
        if operation.request_id == request_id and operation.kind == "search":
            return operation.match_template_ids
    return None


def _contract_complete(operation: TemplateOperation) -> bool:
    return bool(
        operation.protected_error_classes
        and (operation.modeled_state or operation.modeled_side_effects)
        and operation.completion_evidence_ids
        and operation.known_bad_case_ids
    )


def _operation_effects(operation: TemplateOperation) -> tuple[str, ...]:
    if operation.kind == "search":
        return tuple(f"read:template-library:{layer}" for layer in operation.searched_layers)
    if operation.kind == "reuse":
        return tuple(f"consume:template-contract:{item}" for item in operation.used_template_ids)
    if operation.kind == "merge":
        return tuple(
            f"write:merged-template-candidate:{item}"
            for item in operation.result_template_ids
        )
    if operation.kind == "harvest":
        prefix = "link:existing-template" if operation.harvest_disposition == "duplicate_linked" else "write:local-template-candidate"
        return tuple(f"{prefix}:{item}" for item in operation.result_template_ids)
    return ()


def _operation_findings(operation: TemplateOperation, state: State) -> tuple[str, ...]:
    findings: list[str] = []
    if operation.kind not in TEMPLATE_OPERATION_KINDS:
        return ("unknown_template_operation",)
    if not operation.explicitly_requested or operation.request_id not in state.explicit_template_request_ids:
        findings.append("template_operation_not_explicitly_requested")

    required_code = set(CURRENT_CODE_BINDINGS[operation.kind])
    required_tests = set(CURRENT_TEST_BINDINGS[operation.kind])
    if not required_code.issubset(operation.code_binding_ids):
        findings.append("current_code_binding_missing")
    if not required_tests.issubset(operation.test_binding_ids):
        findings.append("current_test_binding_missing")

    if operation.kind == "search":
        if not operation.searched_layers:
            findings.append("template_search_source_missing")
        if len(set(operation.searched_layers)) != len(operation.searched_layers):
            findings.append("template_search_source_duplicated")
    else:
        matches = _search_matches(state, operation.request_id)
        if matches is None:
            findings.append("template_search_not_completed")

    if operation.kind == "reuse":
        matches = _search_matches(state, operation.request_id) or ()
        if not operation.used_template_ids and not operation.no_match_reason.strip():
            findings.append("template_use_or_no_match_reason_missing")
        if not set(operation.used_template_ids).issubset(matches):
            findings.append("reused_template_not_in_search_results")

    if operation.kind in {"merge", "harvest"} and not operation.authorized:
        findings.append("template_mutation_not_authorized")

    if operation.kind == "merge":
        if not operation.source_ids:
            findings.append("merge_source_missing")
        elif len(set(operation.source_ids)) != len(operation.source_ids):
            findings.append("merge_source_duplicated")
        if not set(operation.source_ids).issubset(operation.preserved_source_ids):
            findings.append("merge_source_provenance_not_preserved")
        if operation.duplicate_template_ids:
            findings.append("duplicate_template_should_reuse_or_link")
        if operation.conflict_template_ids and not operation.false_friend_rationale.strip():
            findings.append("merge_conflict_without_rationale")
        if not operation.result_template_ids:
            findings.append("merge_result_missing")
        if not _contract_complete(operation):
            findings.append("reusable_template_contract_incomplete")

    if operation.kind == "harvest":
        if not operation.source_ids:
            findings.append("harvest_source_missing")
        if operation.harvest_disposition not in TEMPLATE_HARVEST_DISPOSITIONS:
            findings.append("harvest_disposition_invalid")
        elif operation.harvest_disposition == "not_harvestable":
            if not operation.not_harvestable_reason.strip():
                findings.append("not_harvestable_reason_missing")
        elif not operation.result_template_ids:
            findings.append("harvest_result_missing")
        if operation.duplicate_template_ids and operation.harvest_disposition != "duplicate_linked":
            findings.append("duplicate_template_not_linked")
        if operation.harvest_disposition in {"written", "merged"} and not _contract_complete(operation):
            findings.append("reusable_template_contract_incomplete")

    return tuple(dict.fromkeys(findings))


def _apply_operation(state: State, operation: TemplateOperation) -> State:
    effects = _operation_effects(operation)
    updates: dict[str, object] = {
        "template_operations": _record_operation(state.template_operations, operation),
        "template_effects": _append_unique(state.template_effects, effects),
    }
    if operation.kind == "reuse":
        updates["reused_template_ids"] = _append_unique(
            state.reused_template_ids,
            operation.used_template_ids,
        )
    elif operation.kind == "merge":
        updates["merged_template_ids"] = _append_unique(
            state.merged_template_ids,
            operation.result_template_ids,
        )
    elif operation.kind == "harvest":
        updates["harvested_template_ids"] = _append_unique(
            state.harvested_template_ids,
            operation.result_template_ids,
        )
    return replace(state, **updates)


class TemplateReleaseStep:
    name = "TemplateReleaseStep"
    reads = (
        "explicit_template_request_ids",
        "template_operations",
        "reused_template_ids",
        "merged_template_ids",
        "harvested_template_ids",
        "template_effects",
        "ordinary_minimum_model_observed",
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
        "explicit_template_request_ids",
        "template_operations",
        "reused_template_ids",
        "merged_template_ids",
        "harvested_template_ids",
        "template_effects",
        "ordinary_minimum_model_observed",
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
    input_description = "explicit template lifecycle or public release process event"
    output_description = "typed template operation result and updated public template release state"
    idempotency = "operation ids and evidence flags are recorded once; repeated inputs do not duplicate effects"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "ordinary_minimum_model":
            yield FunctionResult(
                "ordinary_minimum_model_without_template_work",
                replace(
                    state,
                    ordinary_minimum_model_observed=True,
                ),
                label="ordinary_path_no_template_operation",
            )
            return

        if input_obj.name == "open_template_lifecycle":
            if not input_obj.request_id.strip():
                yield FunctionResult("template_request_missing_identity", state, label="blocked")
                return
            yield FunctionResult(
                "explicit_template_lifecycle_opened",
                replace(
                    state,
                    explicit_template_request_ids=_append_unique(
                        state.explicit_template_request_ids,
                        (input_obj.request_id,),
                    ),
                ),
                label="template_lifecycle_explicitly_requested",
            )
            return

        if input_obj.name == "template_operation":
            if input_obj.operation is None:
                yield FunctionResult("template_operation_missing", state, label="blocked")
                return
            operation = input_obj.operation
            findings = _operation_findings(operation, state)
            if findings:
                yield FunctionResult(
                    TemplateLifecycleOutput(
                        operation.operation_id,
                        operation.kind,
                        "blocked",
                        findings=findings,
                    ),
                    state,
                    label="template_operation_blocked",
                )
                return
            effects = _operation_effects(operation)
            yield FunctionResult(
                TemplateLifecycleOutput(
                    operation.operation_id,
                    operation.kind,
                    "completed",
                    result_template_ids=operation.result_template_ids,
                    effects=effects,
                ),
                _apply_operation(state, operation),
                label=f"template_{operation.kind}_completed",
            )
            return

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


class BrokenTemplateLifecycleStep(TemplateReleaseStep):
    """Known-bad implementation that records selected invalid operations."""

    def __init__(self, *bypass_operation_ids: str) -> None:
        self.bypass_operation_ids = tuple(bypass_operation_ids)

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        operation = input_obj.operation
        if (
            input_obj.name == "template_operation"
            and operation is not None
            and operation.operation_id in self.bypass_operation_ids
        ):
            yield FunctionResult(
                TemplateLifecycleOutput(
                    operation.operation_id,
                    operation.kind,
                    "completed",
                    result_template_ids=operation.result_template_ids,
                    effects=_operation_effects(operation),
                ),
                _apply_operation(state, operation),
                label=f"broken_template_{operation.kind}_completed",
            )
            return
        yield from super().apply(input_obj, state)


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
    def invalid_operations(state: State, finding_codes: set[str]) -> tuple[str, ...]:
        return tuple(
            f"{operation.operation_id}:{finding}"
            for operation in state.template_operations
            for finding in _operation_findings(operation, state)
            if finding in finding_codes
        )

    def template_operations_require_explicit_request(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {"template_operation_not_explicitly_requested"},
        )
        if invalid:
            return InvariantResult.fail(
                "ordinary or unrequested path performed template work: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_operations_bind_current_code_and_tests(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {"current_code_binding_missing", "current_test_binding_missing"},
        )
        if invalid:
            return InvariantResult.fail(
                "template operation missing current code/test binding: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_mutations_require_authorization(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {"template_mutation_not_authorized"},
        )
        if invalid:
            return InvariantResult.fail(
                "template merge or harvest was not authorized: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_operation_sources_are_complete_and_unique(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {
                "template_search_source_missing",
                "template_search_source_duplicated",
                "merge_source_missing",
                "merge_source_duplicated",
                "merge_source_provenance_not_preserved",
                "harvest_source_missing",
            },
        )
        if invalid:
            return InvariantResult.fail(
                "template operation source identity is missing, duplicated, or unpreserved: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_reuse_requires_search_result_disposition(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {
                "template_search_not_completed",
                "template_use_or_no_match_reason_missing",
                "reused_template_not_in_search_results",
            },
        )
        if invalid:
            return InvariantResult.fail(
                "template reuse lifecycle lacks its search/result disposition: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_duplicates_and_conflicts_are_resolved(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {
                "duplicate_template_should_reuse_or_link",
                "merge_conflict_without_rationale",
                "duplicate_template_not_linked",
            },
        )
        if invalid:
            return InvariantResult.fail(
                "template duplicate or conflict was not explicitly resolved: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def reusable_template_contract_is_complete(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {"reusable_template_contract_incomplete"},
        )
        if invalid:
            return InvariantResult.fail(
                "reusable template lacks protected errors, state/effects, evidence, or known-bad cases: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

    def template_harvest_has_terminal_disposition(state: State, _trace: object) -> InvariantResult:
        invalid = invalid_operations(
            state,
            {
                "harvest_disposition_invalid",
                "not_harvestable_reason_missing",
                "harvest_result_missing",
            },
        )
        if invalid:
            return InvariantResult.fail(
                "template harvest lacks an exact terminal disposition: "
                f"{invalid!r}"
            )
        return InvariantResult.pass_()

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
        Invariant(
            "template_operations_require_explicit_request",
            "Ordinary minimum-model work performs no template-library operation.",
            template_operations_require_explicit_request,
        ),
        Invariant(
            "template_operations_bind_current_code_and_tests",
            "Every template operation binds its current production and regression owner.",
            template_operations_bind_current_code_and_tests,
        ),
        Invariant(
            "template_mutations_require_authorization",
            "Template merge and harvest are explicit authorized mutations.",
            template_mutations_require_authorization,
        ),
        Invariant(
            "template_operation_sources_are_complete_and_unique",
            "Search, merge, and harvest preserve complete unique source identities.",
            template_operation_sources_are_complete_and_unique,
        ),
        Invariant(
            "template_reuse_requires_search_result_disposition",
            "Reuse, merge, and harvest consume a completed explicit search decision.",
            template_reuse_requires_search_result_disposition,
        ),
        Invariant(
            "template_duplicates_and_conflicts_are_resolved",
            "Duplicates are reused or linked and conflicts carry an explicit rationale.",
            template_duplicates_and_conflicts_are_resolved,
        ),
        Invariant(
            "reusable_template_contract_is_complete",
            "Merged or harvested templates carry a complete reusable risk contract.",
            reusable_template_contract_is_complete,
        ),
        Invariant(
            "template_harvest_has_terminal_disposition",
            "Harvest terminates as written, merged, duplicate-linked, or exactly not-harvestable.",
            template_harvest_has_terminal_disposition,
        ),
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


def _bound_operation(kind: str, **overrides: object) -> TemplateOperation:
    values: dict[str, object] = {
        "operation_id": f"operation:{kind}",
        "kind": kind,
        "request_id": EXPLICIT_TEMPLATE_REQUEST_ID,
        "explicitly_requested": True,
        "code_binding_ids": CURRENT_CODE_BINDINGS[kind],
        "test_binding_ids": CURRENT_TEST_BINDINGS[kind],
    }
    values.update(overrides)
    return TemplateOperation(**values)


SEARCH_OPERATION = _bound_operation(
    "search",
    operation_id="operation:search-public-and-local",
    query="completion evidence",
    searched_layers=("public", "local"),
    match_template_ids=("completion_requires_evidence", "local-completion-proof"),
)
REUSE_OPERATION = _bound_operation(
    "reuse",
    operation_id="operation:reuse-completion-contract",
    used_template_ids=("completion_requires_evidence",),
)
MERGE_OPERATION = _bound_operation(
    "merge",
    operation_id="operation:merge-completion-contracts",
    authorized=True,
    source_ids=("completion_requires_evidence", "local-completion-proof"),
    preserved_source_ids=("completion_requires_evidence", "local-completion-proof"),
    result_template_ids=("merged-completion-proof",),
    protected_error_classes=("premature_completion",),
    modeled_state=("completed",),
    modeled_side_effects=("publish_completion",),
    completion_evidence_ids=("receipt",),
    known_bad_case_ids=("ack_without_receipt",),
)
HARVEST_OPERATION = _bound_operation(
    "harvest",
    operation_id="operation:harvest-current-proof",
    authorized=True,
    source_ids=("model:completion-proof", "evidence:ack-without-receipt"),
    result_template_ids=("local-completion-proof-v2",),
    protected_error_classes=("premature_completion",),
    modeled_state=("completed",),
    modeled_side_effects=("publish_completion",),
    completion_evidence_ids=("receipt",),
    known_bad_case_ids=("ack_without_receipt",),
    harvest_disposition="written",
)


def operation_event(operation: TemplateOperation) -> Event:
    return Event("template_operation", operation=operation)


def _ast_has_binding(path: Path, symbol_parts: tuple[str, ...]) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return False
    if len(symbol_parts) == 1:
        name = symbol_parts[0]
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == name
            for node in tree.body
        )
    if len(symbol_parts) == 2:
        class_name, member_name = symbol_parts
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return any(
                    isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and member.name == member_name
                    for member in node.body
                )
    return False


def binding_integrity_findings(root: Path | None = None) -> tuple[str, ...]:
    """Verify every declared code/test binding resolves in the current tree."""

    repository_root = root or Path(__file__).resolve().parents[2]
    bindings = tuple(
        dict.fromkeys(
            binding
            for table in (CURRENT_CODE_BINDINGS, CURRENT_TEST_BINDINGS)
            for values in table.values()
            for binding in values
        )
    )
    findings: list[str] = []
    for binding in bindings:
        relative_path, *symbols = binding.split("::")
        path = repository_root / relative_path
        if not path.is_file():
            findings.append(f"binding_path_missing:{binding}")
        elif not symbols or not _ast_has_binding(path, tuple(symbols)):
            findings.append(f"binding_symbol_missing:{binding}")
    return tuple(findings)


def main() -> int:
    reviews = (
        review_scenario(
            scenario(
                name="ordinary_minimum_model_stays_lightweight",
                description="Ordinary minimum-model admission does not touch template libraries.",
                events=(ORDINARY_MINIMUM_MODEL,),
                expected=ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("ordinary_path_no_template_operation",),
                    summary="ordinary minimum-model work has no template search ceremony",
                ),
            )
        ),
        review_scenario(
            scenario(
                name="explicit_template_reuse_lifecycle",
                description="An explicit request searches, reuses, merges, and harvests with current bindings.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(REUSE_OPERATION),
                    operation_event(MERGE_OPERATION),
                    operation_event(HARVEST_OPERATION),
                ),
                expected=ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=(
                        "template_lifecycle_explicitly_requested",
                        "template_search_completed",
                        "template_reuse_completed",
                        "template_merge_completed",
                        "template_harvest_completed",
                    ),
                    summary="explicit template work preserves sources, contracts, effects, and bindings",
                ),
            )
        ),
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
                name="ordinary_path_accidentally_searches_templates",
                description="A broken ordinary path searches templates without an explicit request.",
                events=(
                    operation_event(
                        replace(
                            SEARCH_OPERATION,
                            operation_id="broken:ordinary-template-search",
                            request_id="request:ordinary-minimum-model",
                            explicitly_requested=False,
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_operations_require_explicit_request",),
                    summary="ordinary modeling must not silently invoke template search",
                ),
                block=BrokenTemplateLifecycleStep("broken:ordinary-template-search"),
            ),
            scenario(
                name="merge_without_authorization",
                description="A broken lifecycle merges searched templates without mutation authorization.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            MERGE_OPERATION,
                            operation_id="broken:unauthorized-merge",
                            authorized=False,
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_mutations_require_authorization",),
                    summary="template merge requires explicit authorization",
                ),
                block=BrokenTemplateLifecycleStep("broken:unauthorized-merge"),
            ),
            scenario(
                name="harvest_without_authorization",
                description="A broken lifecycle harvests a template without mutation authorization.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            HARVEST_OPERATION,
                            operation_id="broken:unauthorized-harvest",
                            authorized=False,
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_mutations_require_authorization",),
                    summary="template harvest requires explicit authorization",
                ),
                block=BrokenTemplateLifecycleStep("broken:unauthorized-harvest"),
            ),
            scenario(
                name="merge_without_source",
                description="A broken merge emits a result without source template identities.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            MERGE_OPERATION,
                            operation_id="broken:merge-source-missing",
                            source_ids=(),
                            preserved_source_ids=(),
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_operation_sources_are_complete_and_unique",),
                    summary="merged templates preserve exact source identities",
                ),
                block=BrokenTemplateLifecycleStep("broken:merge-source-missing"),
            ),
            scenario(
                name="merge_repeats_source",
                description="A broken merge repeats one source as though it were two inputs.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            MERGE_OPERATION,
                            operation_id="broken:merge-source-duplicated",
                            source_ids=("completion_requires_evidence", "completion_requires_evidence"),
                            preserved_source_ids=("completion_requires_evidence",),
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_operation_sources_are_complete_and_unique",),
                    summary="duplicate source inputs cannot manufacture a merge",
                ),
                block=BrokenTemplateLifecycleStep("broken:merge-source-duplicated"),
            ),
            scenario(
                name="merge_conflict_without_rationale",
                description="A broken merge hides incompatible template contracts.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            MERGE_OPERATION,
                            operation_id="broken:merge-conflict",
                            conflict_template_ids=("local-completion-proof",),
                            false_friend_rationale="",
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_duplicates_and_conflicts_are_resolved",),
                    summary="conflicting templates need an explicit rationale instead of silent merge",
                ),
                block=BrokenTemplateLifecycleStep("broken:merge-conflict"),
            ),
            scenario(
                name="harvest_duplicate_as_new_template",
                description="A broken harvest writes a known duplicate instead of linking it.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            HARVEST_OPERATION,
                            operation_id="broken:harvest-duplicate-write",
                            duplicate_template_ids=("completion_requires_evidence",),
                            harvest_disposition="written",
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_duplicates_and_conflicts_are_resolved",),
                    summary="duplicate harvest links the existing template rather than writing another",
                ),
                block=BrokenTemplateLifecycleStep("broken:harvest-duplicate-write"),
            ),
            scenario(
                name="harvest_incomplete_contract",
                description="A broken harvest writes a template without completion evidence.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(SEARCH_OPERATION),
                    operation_event(
                        replace(
                            HARVEST_OPERATION,
                            operation_id="broken:harvest-incomplete-contract",
                            completion_evidence_ids=(),
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("reusable_template_contract_is_complete",),
                    summary="harvested templates retain executable completion and known-bad protection",
                ),
                block=BrokenTemplateLifecycleStep("broken:harvest-incomplete-contract"),
            ),
            scenario(
                name="reuse_without_search",
                description="A broken lifecycle claims reuse without a completed search result.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(
                        replace(
                            REUSE_OPERATION,
                            operation_id="broken:reuse-without-search",
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_reuse_requires_search_result_disposition",),
                    summary="reuse consumes a search result or exact no-match disposition",
                ),
                block=BrokenTemplateLifecycleStep("broken:reuse-without-search"),
            ),
            scenario(
                name="search_without_current_test_binding",
                description="A broken search record omits its current regression owner.",
                events=(
                    OPEN_TEMPLATE_LIFECYCLE,
                    operation_event(
                        replace(
                            SEARCH_OPERATION,
                            operation_id="broken:search-test-binding-missing",
                            test_binding_ids=(),
                        )
                    ),
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("template_operations_bind_current_code_and_tests",),
                    summary="template lifecycle claims bind exact current production and test owners",
                ),
                block=BrokenTemplateLifecycleStep("broken:search-test-binding-missing"),
            ),
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

    binding_findings = binding_integrity_findings()
    print()
    print("owner: template_public_release")
    print("protection transfer: risk_templates search/reuse/merge/harvest -> template_public_release")
    print(f"current code bindings: {sum(len(items) for items in CURRENT_CODE_BINDINGS.values())}")
    print(f"current test bindings: {sum(len(items) for items in CURRENT_TEST_BINDINGS.values())}")
    for finding in binding_findings:
        print(f"binding finding: {finding}")

    return 0 if all(result.ok for result in reviews) and broken_report.ok and not binding_findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
