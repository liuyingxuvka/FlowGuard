"""Executable model for provider-neutral, read-only WorkContext.

Purpose:
Let any explicitly registered planning source contribute bounded,
content-addressed context while preserving native ownership and preventing
provider execution, validation, receipt, completion, or archive authority.

Run:
python .flowguard/work_context/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
GENERIC_ARTIFACT_ROLES = (
    "scope",
    "requirement",
    "acceptance",
    "design",
    "plan",
    "task",
    "status",
    "history",
    "other",
)


@dataclass(frozen=True)
class WorkContextInput:
    event: str
    adapter_id: str = "declared-files"
    registered_adapter_ids: tuple[str, ...] = ("declared-files", "openspec")
    provider_root_bounded: bool = True
    artifact_roles: tuple[str, ...] = ("requirement", "design", "plan")
    required_artifact_roles: tuple[str, ...] = ("requirement", "design", "plan")
    artifact_fingerprints_current: bool = True
    context_id: str = "context:one"
    existing_context_ids: tuple[str, ...] = ()
    write_requested: bool = False
    execute_requested: bool = False
    validation_requested: bool = False
    authority_bridge_requested: bool = False
    behavior_source_surface_ids: tuple[str, ...] = ()
    intent_provenance_current: bool = True
    intent_dispositions_terminal: bool = True
    intent_conflict: bool = False


@dataclass(frozen=True)
class WorkContextState:
    adapter_selected: bool = False
    artifacts_read: bool = False
    context_projected: bool = False
    blocked: bool = False
    provider_write_count: int = 0
    provider_execution_count: int = 0
    provider_validation_count: int = 0
    authority_bridge_count: int = 0
    behavior_admitted: bool = False
    intent_contributions_projected: bool = False


class SelectAdapter:
    name = "select_registered_work_context_adapter"
    reads = ("adapter_id", "registered_adapter_ids", "provider_root")
    writes = ("adapter_selected", "blocked")
    input_description = "Explicit adapter id and bounded project root"
    output_description = "Selected peer adapter or visible blocker"
    idempotency = "idempotent"

    def apply(self, input_obj: WorkContextInput, state: WorkContextState):
        if input_obj.event != "select":
            return ()
        if (
            input_obj.adapter_id not in input_obj.registered_adapter_ids
            or not input_obj.provider_root_bounded
        ):
            return (
                FunctionResult(
                    "blocked",
                    replace(state, blocked=True),
                    "adapter_or_boundary_blocked",
                ),
            )
        return (
            FunctionResult(
                "selected",
                replace(state, adapter_selected=True),
                "explicit_peer_adapter_selected",
            ),
        )


class ReadArtifacts:
    name = "read_work_context"
    reads = ("adapter_selected", "native_artifacts", "required_roles")
    writes = ("artifacts_read", "blocked")
    input_description = "Current bounded native artifacts with generic roles"
    output_description = "Content-addressed read-only WorkContext or blocker"
    idempotency = "idempotent-by-context-fingerprint"

    def apply(self, input_obj: WorkContextInput, state: WorkContextState):
        if input_obj.event != "read":
            return ()
        roles = set(input_obj.artifact_roles)
        required = set(input_obj.required_artifact_roles)
        invalid_roles = roles - set(GENERIC_ARTIFACT_ROLES)
        duplicate_identity = input_obj.context_id in input_obj.existing_context_ids
        forbidden = (
            input_obj.write_requested
            or input_obj.execute_requested
            or input_obj.validation_requested
            or input_obj.authority_bridge_requested
        )
        if (
            not state.adapter_selected
            or invalid_roles
            or not required.issubset(roles)
            or not input_obj.artifact_fingerprints_current
            or duplicate_identity
            or forbidden
        ):
            return (
                FunctionResult(
                    "blocked",
                    replace(
                        state,
                        blocked=True,
                        provider_write_count=int(input_obj.write_requested),
                        provider_execution_count=int(input_obj.execute_requested),
                        provider_validation_count=int(input_obj.validation_requested),
                        authority_bridge_count=int(input_obj.authority_bridge_requested),
                    ),
                    "work_context_read_blocked",
                ),
            )
        return (
            FunctionResult(
                "context-read",
                replace(state, artifacts_read=True),
                "work_context_read",
            ),
        )


class ProjectContext:
    name = "project_work_context"
    reads = ("artifacts_read",)
    writes = (
        "context_projected",
        "behavior_admitted",
        "intent_contributions_projected",
        "blocked",
    )
    input_description = "Read-only current WorkContext"
    output_description = "Planning-context projection without native authority"
    idempotency = "idempotent"

    def apply(self, input_obj: WorkContextInput, state: WorkContextState):
        if input_obj.event != "project":
            return ()
        if (
            not state.artifacts_read
            or state.provider_write_count
            or state.provider_execution_count
            or state.provider_validation_count
            or state.authority_bridge_count
            or not input_obj.intent_provenance_current
            or not input_obj.intent_dispositions_terminal
            or input_obj.intent_conflict
        ):
            return (
                FunctionResult(
                    "blocked",
                    replace(state, blocked=True),
                    "context_projection_blocked",
                ),
            )
        return (
            FunctionResult(
                "projected",
                replace(
                    state,
                    context_projected=True,
                    behavior_admitted=bool(input_obj.behavior_source_surface_ids),
                    intent_contributions_projected=True,
                ),
                "read_only_context_projected",
            ),
        )


BLOCKS = (SelectAdapter(), ReadArtifacts(), ProjectContext())


def _run(input_obj: WorkContextInput, state: WorkContextState, index: int):
    return tuple(BLOCKS[index].apply(input_obj, state))[0]


def run_model_checks() -> dict[str, object]:
    findings: list[str] = []
    known_bad: dict[str, str] = {}

    for name, case in {
        "unregistered_adapter": WorkContextInput(
            "select",
            adapter_id="unknown",
        ),
        "unbounded_root": WorkContextInput(
            "select",
            provider_root_bounded=False,
        ),
    }.items():
        result = _run(case, WorkContextState(), 0)
        known_bad[name] = str(result.output)
        if result.output != "blocked":
            findings.append(f"{name}_not_blocked")

    selected_declared = _run(
        WorkContextInput("select", adapter_id="declared-files"),
        WorkContextState(),
        0,
    ).new_state
    selected_openspec = _run(
        WorkContextInput("select", adapter_id="openspec"),
        WorkContextState(),
        0,
    ).new_state
    if not (selected_declared.adapter_selected and selected_openspec.adapter_selected):
        findings.append("peer_adapters_not_equivalent")

    bad_reads = {
        "missing_required_role": WorkContextInput(
            "read",
            artifact_roles=("requirement",),
        ),
        "stale_fingerprint": WorkContextInput(
            "read",
            artifact_fingerprints_current=False,
        ),
        "duplicate_context": WorkContextInput(
            "read",
            existing_context_ids=("context:one",),
        ),
        "provider_write": WorkContextInput("read", write_requested=True),
        "provider_execution": WorkContextInput("read", execute_requested=True),
        "provider_validation": WorkContextInput("read", validation_requested=True),
        "authority_bridge": WorkContextInput(
            "read",
            authority_bridge_requested=True,
        ),
    }
    for name, case in bad_reads.items():
        result = _run(case, selected_declared, 1)
        known_bad[name] = str(result.output)
        if result.output != "blocked":
            findings.append(f"{name}_not_blocked")

    context_read = _run(
        WorkContextInput("read"),
        selected_declared,
        1,
    )
    projected = _run(
        WorkContextInput("project"),
        context_read.new_state,
        2,
    )
    if (
        context_read.output != "context-read"
        or projected.output != "projected"
        or not projected.new_state.context_projected
        or not projected.new_state.intent_contributions_projected
        or projected.new_state.behavior_admitted
    ):
        findings.append("current_context_not_projected")

    admitted = _run(
        WorkContextInput(
            "project",
            behavior_source_surface_ids=("surface:explicit-requirement",),
        ),
        context_read.new_state,
        2,
    )
    if not admitted.new_state.behavior_admitted:
        findings.append("explicit_behavior_source_not_admitted")

    for name, case in {
        "stale_intent_provenance": WorkContextInput(
            "project", intent_provenance_current=False
        ),
        "unresolved_intent_disposition": WorkContextInput(
            "project", intent_dispositions_terminal=False
        ),
        "conflicting_intent": WorkContextInput("project", intent_conflict=True),
    }.items():
        result = _run(case, context_read.new_state, 2)
        known_bad[name] = str(result.output)
        if result.output != "blocked":
            findings.append(f"{name}_not_blocked")

    second_context = _run(
        WorkContextInput(
            "read",
            context_id="context:two",
            existing_context_ids=("context:one",),
        ),
        selected_openspec,
        1,
    )
    if second_context.output != "context-read":
        findings.append("multiple_distinct_contexts_not_supported")

    return {
        "artifact_type": "flowguard_work_context_model_review",
        "ok": not findings,
        "status": "pass" if not findings else "blocked",
        "findings": findings,
        "function_blocks": [block.name for block in BLOCKS],
        "generic_artifact_roles": list(GENERIC_ARTIFACT_ROLES),
        "known_bad": known_bad,
        "claim_boundary": (
            "The model proves a provider-neutral read-only planning-context "
            "boundary. Native providers retain authoring, execution, validation, "
            "status, completion, receipt, and archive authority. Projection creates "
            "bounded intent contributions but cannot activate model authority."
        ),
    }


__all__ = [
    "BLOCKS",
    "FLOWGUARD_MODEL_MARKER",
    "GENERIC_ARTIFACT_ROLES",
    "WorkContextInput",
    "WorkContextState",
    "run_model_checks",
]
