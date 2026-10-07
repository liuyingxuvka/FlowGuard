"""Executable model for provider-neutral, read-only WorkContext.

Purpose:
Let any explicitly registered planning source contribute bounded,
content-addressed context while preserving native ownership and preventing
provider execution, validation, receipt, completion, or archive authority.

Run:
python .flowguard/verification/owners/work_context/run_checks.py
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
    peer_adapters_ok = bool(
        selected_declared.adapter_selected and selected_openspec.adapter_selected
    )
    if not peer_adapters_ok:
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
    current_context_projection_ok = bool(
        context_read.output != "context-read"
        or projected.output != "projected"
        or not projected.new_state.context_projected
        or not projected.new_state.intent_contributions_projected
        or projected.new_state.behavior_admitted
    ) is False
    if not current_context_projection_ok:
        findings.append("current_context_not_projected")

    admitted = _run(
        WorkContextInput(
            "project",
            behavior_source_surface_ids=("surface:explicit-requirement",),
        ),
        context_read.new_state,
        2,
    )
    explicit_behavior_source_admission_ok = bool(admitted.new_state.behavior_admitted)
    if not explicit_behavior_source_admission_ok:
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
    multiple_distinct_contexts_ok = bool(second_context.output == "context-read")
    if not multiple_distinct_contexts_ok:
        findings.append("multiple_distinct_contexts_not_supported")

    return {
        "artifact_type": "flowguard_work_context_model_review",
        "ok": not findings,
        "status": "pass" if not findings else "blocked",
        "findings": findings,
        "function_blocks": [block.name for block in BLOCKS],
        "generic_artifact_roles": list(GENERIC_ARTIFACT_ROLES),
        "known_bad": known_bad,
        "peer_adapter_selection_ok": peer_adapters_ok,
        "current_context_projection_ok": current_context_projection_ok,
        "explicit_behavior_source_admission_ok": explicit_behavior_source_admission_ok,
        "multiple_distinct_contexts_ok": multiple_distinct_contexts_ok,
        "claim_boundary": (
            "The model proves a provider-neutral read-only planning-context "
            "boundary. Native providers retain authoring, execution, validation, "
            "status, completion, receipt, and archive authority. Projection creates "
            "bounded intent contributions but cannot activate model authority."
        ),
    }



def export_path_quality_source(model_instance_fingerprint: str):
    """Declare explicit event components from fixed current apply source, never traces."""
    import ast
    import inspect
    import textwrap
    from dataclasses import fields
    from pathlib import Path
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint

    model_id = "work_context"
    source_path = f".flowguard/models/owners/{model_id}/model.py"
    source_ref = {"path": source_path, "source_fingerprint": functional_source_fingerprint(Path(__file__).resolve().parents[4], source_path)}
    # These exact classes and events are the declared ports, not discovered runners.
    components = (("select", SelectAdapter), ("read", ReadArtifacts), ("project", ProjectContext))
    facts = {name: [] for name in ("states", "transitions", "branches", "function_blocks", "fields", "effects", "outputs", "validations", "owners", "initial_state_ids", "terminal_state_ids", "input_classes")}
    facts.update({
        "state_schema": [field.name for field in fields(WorkContextState)],
        "input_schema": [field.name for field in fields(WorkContextInput)],
        "event_dispatch": True, "constants": {"GENERIC_ARTIFACT_ROLES": list(GENERIC_ARTIFACT_ROLES)},
        "dispatcher_rejection": {"event_guard": "input_obj.event not in declared event ids", "outcome": "no_result", "terminal": False, "source_symbols": ["SelectAdapter.apply", "ReadArtifacts.apply", "ProjectContext.apply"]},
    })
    groundings = {}
    field_uses = {}
    observable_state_outputs = {}
    def field_id(role, name):
        return f"field:{model_id}:{role}:{name}"
    for event, block_type in components:
        block = block_type()
        source = textwrap.dedent(inspect.getsource(block_type.apply))
        function = ast.parse(source).body[0]
        anchor = {"kind": "explicit_event_dispatch", "source_symbol": f"{block_type.__name__}.apply", "source_definition": source, "event": event}
        predicates = {}
        outcomes = []
        no_result_guards = []
        def branches(statements, guards):
            current = list(guards)
            for node in statements:
                if isinstance(node, ast.If):
                    test = ast.unparse(node.test)
                    branches(node.body, current + [test])
                    if node.orelse:
                        branches(node.orelse, current + [f"not ({test})"])
                    # Current fixed branch bodies terminate. Never guess a new shape.
                    if not any(isinstance(item, ast.Return) for item in node.body):
                        raise ValueError(f"unsupported nonterminal dispatcher guard:{event}")
                    current.append(f"not ({test})")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            predicates[target.id] = ast.unparse(node.value)
                elif isinstance(node, ast.Return):
                    calls = [item for item in ast.walk(node.value) if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "FunctionResult"]
                    if not calls:
                        if not isinstance(node.value, ast.Tuple) or node.value.elts:
                            raise ValueError(f"unsupported no-result dispatcher source:{event}")
                        no_result_guards.append(" and ".join(current))
                        return
                    if len(calls) != 1:
                        raise ValueError(f"ambiguous dispatcher outcome:{event}")
                    call = calls[0]
                    output = call.args[0]
                    value = output.value if isinstance(output, ast.Constant) and isinstance(output.value, str) else None
                    replacement = call.args[1]
                    if value is None or not isinstance(replacement, ast.Call) or not isinstance(replacement.func, ast.Name) or replacement.func.id != "replace" or len(replacement.args) != 1 or not isinstance(replacement.args[0], ast.Name) or replacement.args[0].id != "state":
                        raise ValueError(f"unsupported dispatcher outcome:{event}")
                    updates = {keyword.arg: ast.unparse(keyword.value) for keyword in replacement.keywords}
                    outcomes.append((value, " and ".join(current), updates))
                    return
        branches(function.body, [])
        before = f"state:{model_id}:{event}:input"
        facts["states"].append({"id": before, "initial": True, "terminal": False, "state_schema": facts["state_schema"], "component_id": event})
        facts["initial_state_ids"].append(before)
        groundings[before] = {**anchor, "role": "current immutable input state"}
        read_ids = sorted({field_id(node.value.id, node.attr) for node in ast.walk(function) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ("input_obj", "state")})
        written_ids = sorted({field_id("state", key) for _, _, updates in outcomes for key in updates})
        block_id = f"function-block:{model_id}:{event}"
        transition_ids = []
        output_ids = []
        for value, guard, updates in outcomes:
            transition_id = f"transition:{model_id}:{event}:{value}"
            output_id = f"output:{model_id}:{event}:{value}"
            state_output_id = output_id + ":new-state"
            after = f"state:{model_id}:{event}:{value}"
            update_ids = [field_id("state", key) for key in sorted(updates)]
            facts["states"].append({"id": after, "initial": False, "terminal": False, "component_id": event, "field_values": updates, "unchanged_fields": sorted(set(facts["state_schema"]) - set(updates)), "continuation": "shared immutable state supplied to next event"})
            facts["transitions"].append({"id": transition_id, "source": before, "target": after, "trigger": event, "guard": guard, "guard_bindings": predicates, "outputs": [output_id, state_output_id], "reads": read_ids, "writes": update_ids, "state_updates": update_ids, "field_updates": updates, "function_block_ids": [block_id], "effects": [], "errors": [], "component_id": event})
            facts["outputs"].append({"id": output_id, "symbol": value, "terminal": False, "producer_id": transition_id, "consumer_ids": ["caller:event-dispatch"]})
            # FunctionResult exposes this exact immutable replacement as new_state.
            # Its updated fields are returned data, even if later guards do not read them.
            facts["outputs"].append({"id": state_output_id, "symbol": "FunctionResult.new_state", "terminal": False, "producer_id": transition_id, "consumer_ids": ["caller:event-dispatch:new_state"], "observable_field_ids": update_ids})
            groundings[state_output_id] = {**anchor, "role": "returned immutable FunctionResult.new_state", "field_updates": updates}
            for element_id in update_ids:
                observable_state_outputs.setdefault(element_id, []).append(state_output_id)
            groundings[after] = {**anchor, "guard": guard, "field_updates": updates}
            groundings[transition_id] = {**anchor, "guard": guard, "guard_bindings": predicates, "field_updates": updates}
            transition_ids.append(transition_id)
            output_ids.extend((output_id, state_output_id))
            facts["input_classes"].append({"id": f"input-class:{model_id}:{event}:{value}", "event": event, "guard": guard, "guard_bindings": predicates})
        facts["function_blocks"].append({"id": block_id, "inputs": [f"external-input:{event}"], "outputs": output_ids, "reads": read_ids, "writes": written_ids, "component_id": event, "no_result_guards": no_result_guards})
        groundings[block_id] = anchor
        branch_id = f"branch:{model_id}:{event}"
        facts["branches"].append({"id": branch_id, "source": before, "trigger": event, "transition_ids": transition_ids, "no_result_guards": no_result_guards})
        groundings[branch_id] = anchor
        for element_id in set(read_ids + written_ids):
            role, name = element_id.rsplit(":", 2)[-2:]
            uses = field_uses.setdefault(element_id, {"reads": [], "writes": [], "groundings": []})
            if element_id in read_ids:
                uses["reads"].append(block_id)
            if element_id in written_ids:
                uses["writes"].append(block_id)
            uses["groundings"].append(f"{block_type.__name__}.apply")
            groundings[element_id] = {"kind": "explicit_dispatch_field", "source_symbol": f"{'WorkContextInput' if role == 'input_obj' else 'WorkContextState'}:{name}", "apply_anchors": uses["groundings"]}
    for element_id, uses in sorted(field_uses.items()):
        output_refs = sorted(set(observable_state_outputs.get(element_id, ())))
        facts["fields"].append({"id": element_id, "used_by": sorted(set(uses["reads"] + uses["writes"])), "reads_by": sorted(set(uses["reads"])), "writes_by": sorted(set(uses["writes"])), "observable": bool(output_refs), "observable_output_ids": output_refs})
        if output_refs:
            groundings[element_id]["observable_output_ids"] = output_refs
    for invariant in ():
        validation_id = f"validation:{model_id}:{invariant.name}"
        facts["validations"].append({"id": validation_id, "contract": invariant.description, "oracle_id": invariant.name})
        groundings[validation_id] = {"kind": "declared_invariant", "source_symbol": "INVARIANTS", "invariant_name": invariant.name}
    return compile_declared_path_quality_source(
        model_id=model_id, model_instance_fingerprint=model_instance_fingerprint,
        source_refs=(source_ref,), graph_scope="model_behavior",
        provider_kind="flowguard.explicit-event-dispatch.v1",
        model_facts=facts, element_groundings=groundings,
    )


__all__ = [
    "export_path_quality_source",
    "BLOCKS",
    "FLOWGUARD_MODEL_MARKER",
    "GENERIC_ARTIFACT_ROLES",
    "WorkContextInput",
    "WorkContextState",
    "run_model_checks",
]
