"""Informational hazards inferred from a model's existing structure.

These are prompts for an invariant or a known-bad variant, never verdicts.
No exploration, user action, usage description or model import is needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Mapping, Sequence

from ._normalization import nonempty_string_sequence as _as_tuple, unique_strings as _unique
from .export import to_jsonable

TOPOLOGY_NODE_WORKFLOW = "workflow"
TOPOLOGY_NODE_STATE = "state"
TOPOLOGY_NODE_BLOCK = "block"
TOPOLOGY_NODE_INPUT = "input"
TOPOLOGY_NODE_OUTPUT = "output"
TOPOLOGY_EDGE_WORKFLOW = "workflow_edge"
TOPOLOGY_EDGE_SIDE_EFFECT = "side_effect"
TOPOLOGY_LANDMARK_SHARED_WRITER = "shared_writer"
TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT = "side_effect_repeat"
TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION = "external_confirmation_boundary"
TOPOLOGY_LANDMARK_COARSE_TERMINAL = "coarse_terminal_state"
TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY = "legacy_or_compatibility_path"
TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION = "parent_child_compression"


def _normalize(record, strings=(), sequences=()):
    for name in strings:
        object.__setattr__(record, name, str(getattr(record, name)))
    for name in sequences:
        object.__setattr__(record, name, _as_tuple(getattr(record, name)))
    if hasattr(record, "metadata"):
        object.__setattr__(record, "metadata", dict(record.metadata))


def _record_dict(record):
    return to_jsonable({item.name: getattr(record, item.name) for item in fields(record)})


@dataclass(frozen=True)
class TopologyNode:
    node_id: str
    node_kind: str
    label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("node_id", "node_kind", "label"))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class TopologyEdge:
    edge_id: str
    edge_kind: str
    source_id: str
    target_id: str
    label: str = ""
    block_name: str = ""
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    repeatable: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("edge_id", "edge_kind", "source_id", "target_id", "label", "block_name"),
                   ("reads", "writes", "side_effects"))
        object.__setattr__(self, "repeatable", bool(self.repeatable))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class TopologyLandmark:
    landmark_id: str
    landmark_type: str
    anchor_ids: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("landmark_id", "landmark_type", "description"), ("anchor_ids",))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class TopologyDigest:
    digest_id: str
    workflow_name: str = ""
    nodes: tuple[TopologyNode, ...] = ()
    edges: tuple[TopologyEdge, ...] = ()
    landmarks: tuple[TopologyLandmark, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("digest_id", "workflow_name"))
        for name in ("nodes", "edges", "landmarks"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def anchor_ids(self) -> tuple[str, ...]:
        return _unique(tuple(node.node_id for node in self.nodes) + tuple(edge.edge_id for edge in self.edges)
                       + tuple(landmark.landmark_id for landmark in self.landmarks))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class HazardCandidate:
    hazard_id: str
    summary: str
    rationale: str = ""
    future_failure_mode: str = ""
    topology_anchor_ids: tuple[str, ...] = ()
    source_landmark_ids: tuple[str, ...] = ()
    landmark_type: str = ""

    def __post_init__(self):
        _normalize(self, ("hazard_id", "summary", "rationale", "future_failure_mode", "landmark_type"),
                   ("topology_anchor_ids", "source_landmark_ids"))

    def to_dict(self):
        return _record_dict(self)


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _field_names(value: Any) -> tuple[str, ...]:
    if is_dataclass(value):
        return tuple(item.name for item in fields(value))
    if hasattr(value, "__dict__"):
        return tuple(str(name) for name in vars(value))
    return ()


def _contains_any(text, keywords):
    return any(keyword in text.lower() for keyword in keywords)


def _block_name(block, index):
    return str(getattr(block, "name", "") or type(block).__name__ or f"block_{index}")


def _block_tuple(block, name):
    return _as_tuple(getattr(block, name, ()) or ())


def _block_side_effects(block):
    explicit = _block_tuple(block, "side_effects")
    if explicit:
        return explicit
    keywords = ("api", "cache", "database", "db", "email", "file", "network", "payment",
                "persist", "publish", "release", "save", "write")
    return tuple(item for item in _block_tuple(block, "writes") if _contains_any(item, keywords))


def infer_topology_digest(*, workflow: Any, initial_states: Sequence[Any] = (),
                          external_inputs: Sequence[Any] = (), digest_id: str = "") -> TopologyDigest:
    """Read blocks, fields and declared effects without running the workflow."""
    blocks = tuple(getattr(workflow, "blocks", ()) or ())
    name = str(getattr(workflow, "name", "") or type(workflow).__name__)
    root = "workflow:root"
    nodes = [TopologyNode(root, TOPOLOGY_NODE_WORKFLOW, name)]
    for index, block in enumerate(blocks):
        nodes.append(TopologyNode(f"block:{index}:{_block_name(block, index)}", TOPOLOGY_NODE_BLOCK,
                                  _block_name(block, index),
                                  {"reads": _block_tuple(block, "reads"), "writes": _block_tuple(block, "writes")}))
    for kind, values in ((TOPOLOGY_NODE_STATE, initial_states), (TOPOLOGY_NODE_INPUT, external_inputs)):
        for index, value in enumerate(values):
            nodes.append(TopologyNode(f"{kind}:{index}:{_type_name(value)}", kind, _type_name(value),
                                      {"fields": _field_names(value)}))
    edges = []
    for index, block in enumerate(blocks):
        block_name = _block_name(block, index)
        source = root
        if index and getattr(workflow, "mode", "sequence") != "choice":
            source = f"block:{index - 1}:{_block_name(blocks[index - 1], index - 1)}"
        target = f"block:{index}:{block_name}"
        reads, writes = _block_tuple(block, "reads"), _block_tuple(block, "writes")
        effects = _block_side_effects(block)
        edges.append(TopologyEdge(f"edge:{index}:{block_name}", TOPOLOGY_EDGE_WORKFLOW, source, target,
                                  block_name, block_name, reads, writes, effects, bool(external_inputs)))
        if effects:
            output = f"output:{index}:{block_name}"
            nodes.append(TopologyNode(output, TOPOLOGY_NODE_OUTPUT, block_name, {"effects": effects}))
            edges.append(TopologyEdge(f"effect:{index}:{block_name}", TOPOLOGY_EDGE_SIDE_EFFECT, target, output,
                                      "observable side effect", block_name, reads, writes, effects, bool(external_inputs)))
    return TopologyDigest(digest_id or f"topology:{name}", name, tuple(nodes), tuple(edges),
                          _infer_landmarks(nodes, edges))


def _infer_landmarks(nodes, edges) -> tuple[TopologyLandmark, ...]:
    landmarks = []
    write_owners = {}
    for edge in edges:
        if edge.edge_kind == TOPOLOGY_EDGE_SIDE_EFFECT:
            continue  # A block's effect edge repeats its workflow edge's writes.
        for write in set(edge.writes):
            write_owners.setdefault(write, []).append(edge.edge_id)
    for write, owners in sorted(write_owners.items()):
        if len(owners) > 1:
            landmarks.append(TopologyLandmark(f"landmark:shared-writer:{write}", TOPOLOGY_LANDMARK_SHARED_WRITER,
                                              tuple(owners), f"multiple topology edges write {write!r}"))
    for edge in edges:
        if edge.side_effects and edge.repeatable and edge.edge_kind != TOPOLOGY_EDGE_SIDE_EFFECT:
            landmarks.append(TopologyLandmark(f"landmark:side-effect-repeat:{edge.edge_id}",
                                              TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT, (edge.edge_id,),
                                              "repeatable edge owns observable side effects"))
        text = " ".join((edge.edge_id, edge.label, edge.block_name, *edge.reads, *edge.writes, *edge.side_effects))
        if _contains_any(text, ("confirm", "external", "callback", "remote", "deploy", "publish")):
            landmarks.append(TopologyLandmark(f"landmark:external-confirmation:{edge.edge_id}",
                                              TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION, (edge.edge_id,),
                                              "edge appears to cross an external confirmation boundary"))
        if _contains_any(text, ("legacy", "old", "compat", "schema", "migration", "upgrade")):
            landmarks.append(TopologyLandmark(f"landmark:legacy:{edge.edge_id}",
                                              TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY, (edge.edge_id,),
                                              "edge appears to involve old-shape or compatibility topology"))
    for node in nodes:
        # Field names are structural; arbitrary example values are deliberately excluded.
        text = " ".join((node.node_id, node.label, *node.metadata.get("fields", ())))
        if _contains_any(text, ("done", "complete", "success", "final")):
            landmarks.append(TopologyLandmark(f"landmark:coarse-terminal:{node.node_id}",
                                              TOPOLOGY_LANDMARK_COARSE_TERMINAL, (node.node_id,),
                                              "node suggests a broad terminal/success state"))
        if _contains_any(text, ("parent", "child", "mesh")):
            landmarks.append(TopologyLandmark(f"landmark:parent-child:{node.node_id}",
                                              TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION, (node.node_id,),
                                              "node suggests parent/child model compression"))
    return tuple(landmarks)


_DESCRIPTIONS = {
    TOPOLOGY_LANDMARK_SHARED_WRITER: (
        "Multiple model edges write the same state surface.",
        "add an invariant over it or a known-bad variant where the writers disagree",
        "A later path overwrites state without preserving the earlier proof."),
    TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT: (
        "A repeatable edge owns observable side effects.",
        "add an invariant or a known-bad variant for repeated activation",
        "Repeated use produces duplicate or stale side effects."),
    TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION: (
        "A model edge crosses an external confirmation boundary.",
        "add an invariant or a known-bad variant where confirmation has not arrived",
        "Local success is reported before an external environment confirms it."),
    TOPOLOGY_LANDMARK_COARSE_TERMINAL: (
        "A broad terminal or success node may compress hidden states.",
        "add an invariant or a known-bad variant for partial success or recovery",
        "A hidden failure appears after the modeled success state."),
    TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY: (
        "An old-shape or compatibility edge may need an explicit model path.",
        "add an invariant or a known-bad variant for the old shape",
        "Old data, configuration or artifacts reach an unmodeled path."),
    TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION: (
        "A node may compress parent and child behavior.",
        "add an invariant or a known-bad variant for the handoff",
        "A child passes while its parent handoff remains incomplete."),
}


def derive_topology_hazard_candidates(digest: TopologyDigest) -> tuple[HazardCandidate, ...]:
    """Turn the six structural landmarks into anchored informational candidates."""
    anchors = {node.node_id for node in digest.nodes} | {edge.edge_id for edge in digest.edges}
    edges = {edge.edge_id: edge for edge in digest.edges}
    candidates = []
    for landmark in digest.landmarks:
        if landmark.landmark_type not in _DESCRIPTIONS or not landmark.anchor_ids:
            continue
        if any(anchor not in anchors for anchor in landmark.anchor_ids):
            continue
        summary, advice, failure = _DESCRIPTIONS[landmark.landmark_type]
        if landmark.landmark_type == TOPOLOGY_LANDMARK_SHARED_WRITER:
            writers = [edges[anchor] for anchor in landmark.anchor_ids if anchor in edges]
            if writers:
                common = set(writers[0].writes).intersection(*(set(edge.writes) for edge in writers[1:]))
                names = ", ".join(edge.block_name for edge in writers)
                summary = f"state {', '.join(repr(name) for name in sorted(common))} is written by blocks {names}"
        candidates.append(HazardCandidate(f"hazard:{landmark.landmark_type}:{landmark.landmark_id}", summary,
                                          advice, failure, landmark.anchor_ids, (landmark.landmark_id,),
                                          landmark.landmark_type))
    return tuple(candidates)


def model_hazards(explorer) -> list[str]:
    """Compute messages from an already-built Explorer, without exploring it again."""
    digest = infer_topology_digest(workflow=explorer.workflow, initial_states=explorer.initial_states,
                                   external_inputs=explorer.external_inputs)
    return [f"{candidate.landmark_type}: {candidate.summary} [{', '.join(candidate.topology_anchor_ids)}]; "
            f"{candidate.rationale}" for candidate in derive_topology_hazard_candidates(digest)]
