"""Long-lived model for deterministic user-facing Mermaid projections.

The capability projects one canonical model/route/evidence snapshot into an
optional explanation.  The projection is never checker authority and never
counts as validation evidence.  Source, specification, tests, prompts, model,
route, and evidence identities all participate in one freshness boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


ROUTE_EDGE_SEMANTICS = {
    "flowguard": (
        "state_transition",
        "evidence_supports",
        "gap_blocks",
        "handoff_to_owner",
    ),
    "flowguard-development-process-flow": (
        "order",
        "invalidation",
        "required_revalidation",
    ),
    "flowguard-ui-flow-structure": ("reachable_interaction_transition",),
    "flowguard-model-test-alignment": (
        "covers",
        "partially_covers",
        "does_not_cover",
    ),
    "flowguard-code-structure-recommendation": (
        "owns",
        "calls",
        "adapts",
        "exposes",
        "validates",
    ),
    "flowguard-model-mesh": (
        "delegates",
        "reattaches",
        "consumes_output",
        "realizes",
        "blocks",
    ),
}

_VALID_DIRECTIONS = {"TB", "TD", "BT", "RL", "LR"}
_VALID_EVIDENCE_STATUSES = {
    "pass",
    "fail",
    "blocked",
    "skipped",
    "not_run",
}
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _identity(label: str) -> str:
    return _canonical_fingerprint({"identity": label})


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("|", "&#124;")
        .replace("\n", "<br/>")
    )


def _comment(text: str) -> str:
    return " ".join(str(text).split())


def _mermaid_node_id(stable_node_id: str) -> str:
    digest = hashlib.sha256(stable_node_id.encode("utf-8")).hexdigest()[:16]
    return f"n_{digest}"


@dataclass(frozen=True)
class DiagramNode:
    node_id: str
    label: str
    state_kind: str


@dataclass(frozen=True)
class DiagramEdge:
    edge_id: str
    source_id: str
    target_id: str
    semantic: str
    label: str = ""


@dataclass(frozen=True)
class DiagramSource:
    """One canonical model/route/evidence state plus real freshness inputs."""

    model_id: str
    model_fingerprint: str
    route_id: str
    route_fingerprint: str
    evidence_status: str
    evidence_fingerprint: str
    implementation_fingerprint: str
    test_fingerprint: str
    specification_fingerprint: str
    prompt_fingerprint: str
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]
    direction: str = "TD"
    non_trivial: bool = True
    user_suppressed_progress: bool = False
    current_situation: str = ""
    applicable: bool = True
    not_applicable_reason: str = ""


@dataclass(frozen=True)
class DiagramAction:
    action_type: str
    source: DiagramSource | None = None
    reason: str = ""


@dataclass(frozen=True)
class DiagramOutput:
    """Compact projection; it never repeats the canonical source body."""

    status: str
    source_fingerprint: str
    projection_fingerprint: str
    checker_status: str
    evidence_role: str
    mermaid_text: str = ""


@dataclass(frozen=True)
class DiagramState:
    source: DiagramSource | None = None
    source_fingerprint: str = ""
    source_checker_status: str = "not_run"
    checker_status: str = "not_run"
    projection_status: str = "absent"
    projection_source_fingerprint: str = ""
    projection_fingerprint: str = ""
    mermaid_text: str = ""
    projected_edge_semantics: tuple[str, ...] = ()
    diagram_used_as_evidence: bool = False
    disposition_reason: str = ""
    projection_claim: str = "none"


def _node_payload(node: DiagramNode) -> dict[str, str]:
    return {
        "node_id": node.node_id,
        "label": node.label,
        "state_kind": node.state_kind,
    }


def _edge_payload(edge: DiagramEdge) -> dict[str, str]:
    return {
        "edge_id": edge.edge_id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "semantic": edge.semantic,
        "label": edge.label,
    }


def source_fingerprint(source: DiagramSource) -> str:
    """Bind model, route, evidence, and every real implementation input."""

    return _canonical_fingerprint(
        {
            "model_id": source.model_id,
            "model_fingerprint": source.model_fingerprint,
            "route_id": source.route_id,
            "route_fingerprint": source.route_fingerprint,
            "evidence_status": source.evidence_status,
            "evidence_fingerprint": source.evidence_fingerprint,
            "implementation_fingerprint": source.implementation_fingerprint,
            "test_fingerprint": source.test_fingerprint,
            "specification_fingerprint": source.specification_fingerprint,
            "prompt_fingerprint": source.prompt_fingerprint,
            "nodes": [
                _node_payload(node)
                for node in sorted(source.nodes, key=lambda item: item.node_id)
            ],
            "edges": [
                _edge_payload(edge)
                for edge in sorted(
                    source.edges,
                    key=lambda item: (
                        item.source_id,
                        item.target_id,
                        item.semantic,
                        item.edge_id,
                    ),
                )
            ],
            "direction": source.direction,
            "non_trivial": source.non_trivial,
            "user_suppressed_progress": source.user_suppressed_progress,
            "current_situation": source.current_situation,
            "applicable": source.applicable,
            "not_applicable_reason": source.not_applicable_reason,
        }
    )


def _source_gaps(source: DiagramSource) -> tuple[str, ...]:
    gaps: set[str] = set()
    for name in ("model_id", "route_id"):
        if not str(getattr(source, name)).strip():
            gaps.add(f"{name}_missing")
    for name in (
        "model_fingerprint",
        "route_fingerprint",
        "evidence_fingerprint",
        "implementation_fingerprint",
        "test_fingerprint",
        "specification_fingerprint",
        "prompt_fingerprint",
    ):
        if not _FINGERPRINT_RE.fullmatch(str(getattr(source, name))):
            gaps.add(f"{name}_invalid")
    if source.route_id not in ROUTE_EDGE_SEMANTICS:
        gaps.add("route_semantics_unknown")
    if source.direction not in _VALID_DIRECTIONS:
        gaps.add("direction_invalid")
    if source.evidence_status not in _VALID_EVIDENCE_STATUSES:
        gaps.add("evidence_status_invalid")
    node_ids = tuple(node.node_id for node in source.nodes)
    edge_ids = tuple(edge.edge_id for edge in source.edges)
    if any(not value for value in node_ids) or len(set(node_ids)) != len(node_ids):
        gaps.add("node_identity_invalid")
    if any(not value for value in edge_ids) or len(set(edge_ids)) != len(edge_ids):
        gaps.add("edge_identity_invalid")
    allowed_semantics = set(ROUTE_EDGE_SEMANTICS.get(source.route_id, ()))
    for edge in source.edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            gaps.add(f"edge_endpoint_missing:{edge.edge_id}")
        if edge.semantic not in allowed_semantics:
            gaps.add(f"route_edge_semantic_invalid:{edge.edge_id}")
    if (
        source.applicable
        and source.non_trivial
        and not source.user_suppressed_progress
        and not source.current_situation.strip()
    ):
        gaps.add("current_situation_missing")
    if not source.applicable and not source.not_applicable_reason.strip():
        gaps.add("not_applicable_reason_missing")
    return tuple(sorted(gaps))


def render_mermaid(source: DiagramSource, *, include_edge_semantics: bool = True) -> str:
    """Independent deterministic contract projection, not production evidence."""

    nodes = tuple(sorted(source.nodes, key=lambda item: item.node_id))
    edges = tuple(
        sorted(
            source.edges,
            key=lambda item: (
                item.source_id,
                item.target_id,
                item.semantic,
                item.edge_id,
            ),
        )
    )
    lines = [f"flowchart {source.direction}"]
    lines.append(f"  %% {_comment(source.model_id)} via {_comment(source.route_id)}")
    for node in nodes:
        node_id = _mermaid_node_id(node.node_id)
        label = _escape(f"{node.label} [{node.state_kind}]")
        lines.append(f'  {node_id}["{label}"]')
    for edge in edges:
        source_id = _mermaid_node_id(edge.source_id)
        target_id = _mermaid_node_id(edge.target_id)
        if include_edge_semantics:
            edge_text = edge.semantic
            if edge.label:
                edge_text += f": {edge.label}"
            lines.append(f"  {source_id} -->|{_escape(edge_text)}| {target_id}")
        else:
            lines.append(f"  {source_id} --> {target_id}")
    return "\n".join(lines)


def _compact_output(state: DiagramState, status: str) -> DiagramOutput:
    return DiagramOutput(
        status=status,
        source_fingerprint=state.source_fingerprint,
        projection_fingerprint=state.projection_fingerprint,
        checker_status=state.checker_status,
        evidence_role="explanation_only",
        mermaid_text=state.mermaid_text if state.projection_status == "current" else "",
    )


class DiagramProjectionFlow:
    name = "DiagramProjectionFlow"
    reads = tuple(DiagramState.__dataclass_fields__)
    writes = reads
    accepted_input_type = DiagramAction
    input_description = "canonical model/route/evidence snapshot or projection disposition"
    output_description = "compact optional explanation projection with no checker authority"
    idempotency = "The same canonical source produces byte-identical Mermaid and compact identities."

    def _load_source(self, source: DiagramSource, state: DiagramState) -> DiagramState:
        identity = source_fingerprint(source)
        gaps = _source_gaps(source)
        prior_disposition = state.projection_status in {"current", "skipped", "not_applicable"}
        changed = bool(state.source_fingerprint and state.source_fingerprint != identity)
        status = "blocked" if gaps else ("stale" if prior_disposition and changed else "absent")
        if state.projection_status == "current" and not changed and not gaps:
            status = "current"
        return replace(
            state,
            source=source,
            source_fingerprint=identity,
            source_checker_status=source.evidence_status,
            checker_status=source.evidence_status,
            projection_status=status,
            diagram_used_as_evidence=False,
            disposition_reason=",".join(gaps) if gaps else ("source_changed" if changed else ""),
            projection_claim="none",
        )

    def _project(self, state: DiagramState) -> DiagramState:
        source = state.source
        if source is None:
            return replace(
                state,
                projection_status="blocked",
                disposition_reason="canonical_source_missing",
                projection_claim="none",
            )
        gaps = _source_gaps(source)
        if gaps:
            return replace(
                state,
                projection_status="blocked",
                disposition_reason=",".join(gaps),
                projection_claim="none",
            )
        if not source.applicable:
            return replace(
                state,
                projection_status="blocked",
                disposition_reason="use_explicit_not_applicable_disposition",
                projection_claim="none",
            )
        mermaid = render_mermaid(source)
        return replace(
            state,
            projection_status="current",
            projection_source_fingerprint=state.source_fingerprint,
            projection_fingerprint=_canonical_fingerprint({"mermaid": mermaid}),
            mermaid_text=mermaid,
            projected_edge_semantics=tuple(sorted({edge.semantic for edge in source.edges})),
            diagram_used_as_evidence=False,
            disposition_reason="projected_from_canonical_source",
            projection_claim="none",
        )

    def _claimable(self, state: DiagramState) -> bool:
        source = state.source
        if source is None or state.checker_status != source.evidence_status:
            return False
        if state.diagram_used_as_evidence:
            return False
        if state.projection_status == "current":
            expected_mermaid = render_mermaid(source)
            return (
                source.applicable
                and state.projection_source_fingerprint == state.source_fingerprint
                and state.mermaid_text == expected_mermaid
                and state.projection_fingerprint
                == _canonical_fingerprint({"mermaid": expected_mermaid})
                and state.projected_edge_semantics
                == tuple(sorted({edge.semantic for edge in source.edges}))
            )
        if state.projection_status == "skipped":
            return bool(source.applicable and state.disposition_reason.strip())
        if state.projection_status == "not_applicable":
            return bool(not source.applicable and state.disposition_reason.strip())
        return False

    def apply(self, input_obj: DiagramAction, state: DiagramState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "load_source":
            if input_obj.source is None:
                next_state = replace(
                    state,
                    projection_status="blocked",
                    disposition_reason="canonical_source_missing",
                    projection_claim="none",
                )
            else:
                next_state = self._load_source(input_obj.source, state)
            yield FunctionResult(
                _compact_output(next_state, "source_loaded"),
                next_state,
                label="canonical_source_loaded",
                reason="one source binds model, route, evidence, implementation, test, spec, and prompt identities",
            )
            return
        if action == "project":
            next_state = self._project(state)
            yield FunctionResult(
                _compact_output(next_state, next_state.projection_status),
                next_state,
                label="diagram_projected" if next_state.projection_status == "current" else "projection_blocked",
                reason=next_state.disposition_reason,
            )
            return
        if action == "skip":
            allowed = state.source is not None and state.source.applicable and bool(input_obj.reason.strip())
            next_state = replace(
                state,
                projection_status="skipped" if allowed else "blocked",
                projection_source_fingerprint=state.source_fingerprint if allowed else "",
                projection_fingerprint="",
                mermaid_text="",
                projected_edge_semantics=(),
                diagram_used_as_evidence=False,
                disposition_reason=input_obj.reason if allowed else "explicit_skip_reason_missing",
                projection_claim="none",
            )
            yield FunctionResult(
                _compact_output(next_state, next_state.projection_status),
                next_state,
                label="diagram_skipped" if allowed else "skip_blocked",
                reason=next_state.disposition_reason,
            )
            return
        if action == "mark_not_applicable":
            allowed = (
                state.source is not None
                and not state.source.applicable
                and bool(state.source.not_applicable_reason.strip())
            )
            next_state = replace(
                state,
                projection_status="not_applicable" if allowed else "blocked",
                projection_source_fingerprint=state.source_fingerprint if allowed else "",
                projection_fingerprint="",
                mermaid_text="",
                projected_edge_semantics=(),
                diagram_used_as_evidence=False,
                disposition_reason=(
                    state.source.not_applicable_reason
                    if allowed and state.source is not None
                    else "not_applicable_boundary_missing"
                ),
                projection_claim="none",
            )
            yield FunctionResult(
                _compact_output(next_state, next_state.projection_status),
                next_state,
                label="diagram_not_applicable" if allowed else "not_applicable_blocked",
                reason=next_state.disposition_reason,
            )
            return
        if action == "claim_projection":
            accepted = self._claimable(state)
            next_state = replace(
                state,
                projection_claim="accepted" if accepted else "rejected",
            )
            yield FunctionResult(
                _compact_output(next_state, next_state.projection_claim),
                next_state,
                label="projection_claim_accepted" if accepted else "projection_claim_rejected",
                reason="diagram disposition is current explanation only" if accepted else "projection is stale, invalid, or unbounded",
            )


class BrokenDiagramModelMismatch(DiagramProjectionFlow):
    name = "BrokenDiagramModelMismatch"

    def _project(self, state: DiagramState) -> DiagramState:
        projected = super()._project(state)
        if projected.projection_status != "current":
            return projected
        return replace(projected, projection_source_fingerprint=_identity("foreign-model"))

    def _claimable(self, state: DiagramState) -> bool:
        return state.projection_status == "current"


class BrokenDiagramAsEvidence(DiagramProjectionFlow):
    name = "BrokenDiagramAsEvidence"

    def _project(self, state: DiagramState) -> DiagramState:
        projected = super()._project(state)
        if projected.projection_status != "current":
            return projected
        return replace(projected, checker_status="pass", diagram_used_as_evidence=True)

    def _claimable(self, state: DiagramState) -> bool:
        return state.projection_status == "current"


class BrokenEdgeSemanticsLost(DiagramProjectionFlow):
    name = "BrokenEdgeSemanticsLost"

    def _project(self, state: DiagramState) -> DiagramState:
        projected = super()._project(state)
        if projected.projection_status != "current" or projected.source is None:
            return projected
        mermaid = render_mermaid(projected.source, include_edge_semantics=False)
        return replace(
            projected,
            mermaid_text=mermaid,
            projection_fingerprint=_canonical_fingerprint({"mermaid": mermaid}),
            projected_edge_semantics=(),
        )

    def _claimable(self, state: DiagramState) -> bool:
        return state.projection_status == "current"


class BrokenStaleDiagramReuse(DiagramProjectionFlow):
    name = "BrokenStaleDiagramReuse"

    def _load_source(self, source: DiagramSource, state: DiagramState) -> DiagramState:
        loaded = super()._load_source(source, state)
        if state.projection_status == "current" and state.source_fingerprint != loaded.source_fingerprint:
            return replace(loaded, projection_status="current")
        return loaded

    def _claimable(self, state: DiagramState) -> bool:
        return state.projection_status == "current"


def accepted_projection_matches_canonical_source(
    state: DiagramState,
    trace,
) -> InvariantResult:
    del trace
    if state.projection_claim != "accepted" or state.projection_status != "current":
        return InvariantResult.pass_()
    if state.source is None:
        return InvariantResult.fail("accepted projection has no canonical source")
    expected = render_mermaid(state.source)
    if (
        state.projection_source_fingerprint != state.source_fingerprint
        or state.mermaid_text != expected
        or state.projection_fingerprint != _canonical_fingerprint({"mermaid": expected})
    ):
        return InvariantResult.fail("accepted diagram does not match its canonical model/route/evidence source")
    return InvariantResult.pass_()


def diagram_never_supplies_checker_evidence(state: DiagramState, trace) -> InvariantResult:
    del trace
    if state.projection_claim == "accepted" and (
        state.diagram_used_as_evidence
        or state.checker_status != state.source_checker_status
    ):
        return InvariantResult.fail("diagram changed checker semantics or substituted for validation evidence")
    return InvariantResult.pass_()


def accepted_projection_preserves_route_edge_semantics(
    state: DiagramState,
    trace,
) -> InvariantResult:
    del trace
    if state.projection_claim != "accepted" or state.projection_status != "current":
        return InvariantResult.pass_()
    if state.source is None:
        return InvariantResult.fail("accepted projection has no route semantics")
    expected = tuple(sorted({edge.semantic for edge in state.source.edges}))
    labels_present = all(f"|{_escape(semantic)}" in state.mermaid_text for semantic in expected)
    if state.projected_edge_semantics != expected or not labels_present:
        return InvariantResult.fail("accepted diagram flattened or lost route-owned edge semantics")
    return InvariantResult.pass_()


def accepted_disposition_is_current_and_explicit(
    state: DiagramState,
    trace,
) -> InvariantResult:
    del trace
    if state.projection_claim != "accepted":
        return InvariantResult.pass_()
    if state.source is None or state.projection_status not in {
        "current",
        "skipped",
        "not_applicable",
    }:
        return InvariantResult.fail("accepted diagram disposition is missing, stale, or blocked")
    if state.projection_source_fingerprint != state.source_fingerprint:
        return InvariantResult.fail("accepted diagram disposition belongs to an older source")
    if state.projection_status == "skipped" and not state.disposition_reason.strip():
        return InvariantResult.fail("skipped diagram has no explicit reason")
    if state.projection_status == "not_applicable" and (
        state.source.applicable or not state.disposition_reason.strip()
    ):
        return InvariantResult.fail("not-applicable diagram lacks an exact applicability boundary")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_projection_matches_canonical_source",
        "Accepted Mermaid is a deterministic projection of the exact current source.",
        accepted_projection_matches_canonical_source,
    ),
    Invariant(
        "diagram_never_supplies_checker_evidence",
        "A diagram explains checker state and never changes or proves it.",
        diagram_never_supplies_checker_evidence,
    ),
    Invariant(
        "accepted_projection_preserves_route_edge_semantics",
        "Every rendered edge retains the selected route's relationship meaning.",
        accepted_projection_preserves_route_edge_semantics,
    ),
    Invariant(
        "accepted_disposition_is_current_and_explicit",
        "Current, skipped, and not-applicable dispositions stay explicit and source-bound.",
        accepted_disposition_is_current_and_explicit,
    ),
)


SOURCE_V1 = DiagramSource(
    model_id="model_mesh.current_child_handoff",
    model_fingerprint=_identity("model-v1"),
    route_id="flowguard-model-mesh",
    route_fingerprint=_identity("model-mesh-route-v1"),
    evidence_status="not_run",
    evidence_fingerprint=_identity("evidence-not-run-v1"),
    implementation_fingerprint=_identity("flowguard/mermaid.py"),
    test_fingerprint=_identity("tests/test_mermaid_export.py"),
    specification_fingerprint=_identity("user-facing-model-diagrams-spec"),
    prompt_fingerprint=_identity("route-specific-diagram-prompts"),
    nodes=(
        DiagramNode("parent", 'Parent <model> | "current"', "parent"),
        DiagramNode("child", "Child model", "child"),
        DiagramNode("evidence", "Evidence not run", "evidence"),
    ),
    edges=(
        DiagramEdge("parent-child", "parent", "child", "delegates", "behavior boundary"),
        DiagramEdge("child-evidence", "child", "evidence", "consumes_output", "terminal receipt"),
    ),
    current_situation="The model relation is current; executable evidence is explicitly not run.",
)

SOURCE_V2 = replace(
    SOURCE_V1,
    model_fingerprint=_identity("model-v2"),
    evidence_status="blocked",
    evidence_fingerprint=_identity("evidence-blocked-v2"),
    current_situation="The changed model is blocked until its new child receipt is current.",
)

SOURCE_V1_REORDERED = replace(
    SOURCE_V1,
    nodes=tuple(reversed(SOURCE_V1.nodes)),
    edges=tuple(reversed(SOURCE_V1.edges)),
)

NOT_APPLICABLE_SOURCE = replace(
    SOURCE_V1,
    model_id="trivial.direct_status",
    model_fingerprint=_identity("trivial-model"),
    nodes=(),
    edges=(),
    non_trivial=False,
    current_situation="",
    applicable=False,
    not_applicable_reason="The tiny direct status has no material relationship that benefits from a diagram.",
)

GOOD_SEQUENCE = (
    DiagramAction("load_source", SOURCE_V1),
    DiagramAction("project"),
    DiagramAction("claim_projection"),
)

REORDERED_SEQUENCE = (
    DiagramAction("load_source", SOURCE_V1_REORDERED),
    DiagramAction("project"),
    DiagramAction("claim_projection"),
)

SKIP_SEQUENCE = (
    DiagramAction("load_source", SOURCE_V1),
    DiagramAction("skip", reason="The user suppressed visual progress detail for this explanation."),
    DiagramAction("claim_projection"),
)

NOT_APPLICABLE_SEQUENCE = (
    DiagramAction("load_source", NOT_APPLICABLE_SOURCE),
    DiagramAction("mark_not_applicable"),
    DiagramAction("claim_projection"),
)

STALE_SEQUENCE = (
    DiagramAction("load_source", SOURCE_V1),
    DiagramAction("project"),
    DiagramAction("load_source", SOURCE_V2),
    DiagramAction("claim_projection"),
)

EXTERNAL_INPUTS = (
    DiagramAction("load_source", SOURCE_V1),
    DiagramAction("load_source", SOURCE_V2),
    DiagramAction("project"),
    DiagramAction("skip", reason="explicit user-facing skip"),
    DiagramAction("mark_not_applicable"),
    DiagramAction("claim_projection"),
)

MAX_SEQUENCE_LENGTH = 4


def initial_state() -> DiagramState:
    return DiagramState()


def build_correct_workflow() -> Workflow:
    return Workflow((DiagramProjectionFlow(),), name="user_facing_diagram_projection")


def build_broken_model_mismatch_workflow() -> Workflow:
    return Workflow((BrokenDiagramModelMismatch(),), name="broken_diagram_model_mismatch")


def build_broken_evidence_substitution_workflow() -> Workflow:
    return Workflow((BrokenDiagramAsEvidence(),), name="broken_diagram_as_evidence")


def build_broken_edge_semantics_workflow() -> Workflow:
    return Workflow((BrokenEdgeSemanticsLost(),), name="broken_edge_semantics_lost")


def build_broken_stale_reuse_workflow() -> Workflow:
    return Workflow((BrokenStaleDiagramReuse(),), name="broken_stale_diagram_reuse")


__all__ = [
    "EXTERNAL_INPUTS",
    "GOOD_SEQUENCE",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "NOT_APPLICABLE_SEQUENCE",
    "REORDERED_SEQUENCE",
    "ROUTE_EDGE_SEMANTICS",
    "SKIP_SEQUENCE",
    "SOURCE_V1",
    "SOURCE_V1_REORDERED",
    "SOURCE_V2",
    "STALE_SEQUENCE",
    "DiagramAction",
    "DiagramEdge",
    "DiagramNode",
    "DiagramOutput",
    "DiagramSource",
    "DiagramState",
    "build_broken_edge_semantics_workflow",
    "build_broken_evidence_substitution_workflow",
    "build_broken_model_mismatch_workflow",
    "build_broken_stale_reuse_workflow",
    "build_correct_workflow",
    "initial_state",
    "render_mermaid",
    "source_fingerprint",
]
