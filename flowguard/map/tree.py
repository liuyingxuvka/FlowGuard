"""One model tree derived from model literals, sibling imports and code ownership."""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import Finding, matches_any, read_source
from .inventory import Inventory
from .mapfile import component_ancestors, component_scope, component_subtree, component_files, local_imports, model_registry, owner_index, read_model_contract, resolve_model_path, top_level_imports


@dataclass
class ModelNode:
    id: str
    path: str
    kind: str
    parent: str
    parent_kind: str
    source: str
    home: str = "system"
    import_files: set[str] = field(default_factory=set)
    local_import_files: set[str] = field(default_factory=set)     # imports inside functions or blocks
    contract: dict = field(default_factory=dict)
    components: set[str] = field(default_factory=set)
    home_kind: str = "system"
    nonnested_tests: set[str] = field(default_factory=set)


@dataclass
class ModelTree:
    nodes: dict[str, ModelNode]
    imports: dict[str, set[str]]
    findings: list[Finding] = field(default_factory=list)
    local_imports: dict[str, set[str]] = field(default_factory=dict)

    def ancestors(self, model: str) -> list[str]:
        result, seen = [], {model}
        node = self.nodes.get(model)
        while node and node.parent_kind == "model" and node.parent not in seen:
            result.append(node.parent)
            seen.add(node.parent)
            node = self.nodes.get(node.parent)
        return result

    def children(self, parent: str, kind: str) -> list[ModelNode]:
        return sorted((n for n in self.nodes.values() if (n.parent, n.parent_kind) == (parent, kind)),
                      key=lambda n: n.id)

    def models_for_component(self, component: str) -> list[ModelNode]:
        return sorted((n for n in self.nodes.values() if component in n.components), key=lambda n: n.id)

    def importers(self, path: str) -> set[str]:
        reverse: dict[str, set[str]] = defaultdict(set)
        for edges in (self.imports, self.local_imports):        # an import anywhere in the file counts
            for source, targets in edges.items():
                for target in targets:
                    reverse[target].add(source)
        pending, reached = [path], set()
        while pending:
            for source in reverse.get(pending.pop(), ()):
                if source not in reached:
                    reached.add(source)
                    pending.append(source)
        return {n.id for n in self.nodes.values() if n.path in reached}


def component_parent_findings(data: dict) -> list[Finding]:
    """Component parents must exist, stay in one layer and never loop (errors)."""
    out: list[Finding] = []
    by_id = {c["id"]: c for c in data["components"]}
    for cid, comp in by_id.items():
        parent = comp.get("parent")
        if parent is None:
            continue
        if parent not in by_id:
            out.append(Finding("error", "component_parent_unknown", cid,
                               f"component {cid}: parent {parent!r} is not a component"))
        elif (comp.get("layer") or "") != (by_id[parent].get("layer") or ""):
            out.append(Finding("error", "component_parent_layer", cid,
                               f"component {cid} is in layer {comp.get('layer')} but its parent {parent} "
                               f"is in layer {by_id[parent].get('layer')}; a sub-system stays in one layer"))
    finished = set()
    for start in by_id:
        chain, current = [], start
        while current in by_id and current not in finished:
            if current in chain:
                loop = chain[chain.index(current):] + [current]
                out.append(Finding("error", "component_parent_cycle", current,
                                   "component parent loop: " + " -> ".join(loop)))
                break
            chain.append(current)
            current = by_id[current].get("parent")
        finished.update(chain)
    return out


def build_tree(root: Path, data: dict, inv: Inventory, *,
               historical_imports: dict[str, list[str]] | None = None, view=None) -> ModelTree:
    """Resolve each model's parent once; report invalid nesting and fall back finitely."""
    registry = model_registry(root, data, view=view)
    components = {c["id"]: c for c in data.get("components", [])}
    owner, _ = owner_index(data, inv)
    files = ({Path(path).stem: path for path in view.model_sources}
             if view is not None else
             {p.stem: p.relative_to(root).as_posix() for p in (root / ".flowguard/models").glob("*.py")})
    for path in historical_imports or {}:
        files.setdefault(Path(path).stem, path)
    contracts, imports, nested = {}, {}, {}
    registered_paths = {entry.path for entry in registry.entries}
    for path in sorted(set(files.values()) | {e.path for e in registry.entries}):
        try:
            physical = resolve_model_path(root, path, view=view)
            inner = []
            if path in (historical_imports or {}) and (physical is None or not physical.exists()):
                contract, names = {}, historical_imports[path]
            elif physical is None:
                contract, names = {}, []
            elif path in registered_paths:
                contract = read_model_contract(physical)
                names, inner = contract["imports"], contract["local_imports"]
            else:
                contract = {}
                syntax = ast.parse(read_source(physical))
                names, inner = top_level_imports(syntax), local_imports(syntax)
        except (OSError, SyntaxError, ValueError, TypeError):
            contract, names, inner = {}, [], []      # the registry/check owner reports malformed contracts
        contracts[path] = contract
        imports[path] = {files[name] for name in names if name in files}
        nested[path] = {files[name] for name in inner if name in files} - imports[path] - {path}
    nodes = {}
    for entry in registry.entries:
        nodes.setdefault(entry.id, ModelNode(entry.id, entry.path, entry.kind, "system", "system", "default",
                                            import_files=imports.get(entry.path, set()),
                                            local_import_files=nested.get(entry.path, set()), contract=contracts[entry.path]))
    tree = ModelTree(nodes, imports, local_imports=nested)
    pending_findings: list[tuple[str, str, str]] = []

    def parent_importers(node: ModelNode) -> list[str]:
        # A child may import its explicit model parent's state/blocks. Keep the real
        # imports graph for impact, but do not invert that declared tree relation.
        return [n.id for n in nodes.values() if n.kind == "contract" and n.id != node.id
                and node.path in n.import_files
                and not (n.contract.get("PARENT") == node.id and node.id not in components and node.id != "system")]

    def default_parent(node: ModelNode, *, allow_model: bool = True) -> tuple[str, str, str]:
        importers = parent_importers(node)
        if allow_model and len(importers) == 1:
            return importers[0], "model", "import"
        if node.contract.get("COMPONENTS"):
            return node.contract["COMPONENTS"][0], "component", "COMPONENTS"
        anchors = list(node.contract.get("IMPLEMENTED_BY", {}).values())
        if anchors and (cid := owner.get(anchors[0].split(":", 1)[0])):
            return cid, "component", "anchor"
        return "system", "system", "default"

    for node in nodes.values():
        parent = node.contract.get("PARENT")
        node.parent, node.parent_kind, node.source = default_parent(node)
        if parent is not None:
            if parent == "system" or parent in components or parent in nodes:
                node.parent = parent
                node.parent_kind = "system" if parent == "system" else "component" if parent in components else "model"
                node.source = "PARENT"
            else:
                pending_findings.append((node.id, "parent_unknown",
                    f"{node.path}: PARENT {parent!r} names no component, model id or 'system'"))
            importers = parent_importers(node)
            if len(importers) == 1 and parent != importers[0]:
                pending_findings.append((node.id, "parent_import_mismatch",
                    f"{node.path}: imported only by model {importers[0]!r} but PARENT is {parent!r}"))

    cycles: dict[str, str] = {}
    for start in nodes:
        chain, current = [], start
        while current in nodes and nodes[current].parent_kind == "model":
            if current in chain:
                cycle = chain[chain.index(current):]
                message = " -> ".join([*cycle, current])
                for mid in cycle:
                    cycles.setdefault(mid, message)
                break
            chain.append(current)
            current = nodes[current].parent
    for mid, chain in cycles.items():
        node = nodes[mid]
        pending_findings.append((mid, "parent_cycle", f"{node.path}: PARENT chain loops: {chain}"))
        node.parent, node.parent_kind, node.source = default_parent(node, allow_model=False)
    for node in nodes.values():
        top = nodes[tree.ancestors(node.id)[-1]] if tree.ancestors(node.id) else node
        node.home_kind = "component" if top.parent_kind == "component" and top.parent in components else "system"
        node.home = top.parent if node.home_kind == "component" else "system"
        explicit_components = set(node.contract.get("COMPONENTS", []))
        node.components = explicit_components | {
            member["id"] for cid in explicit_components for member in component_subtree(data, cid)
        }
        node.components.update(owner[a.split(":", 1)[0]] for a in node.contract.get("IMPLEMENTED_BY", {}).values()
                               if a.split(":", 1)[0] in owner)
        if node.home_kind == "component":
            node.components.add(node.home)
        node.components.update(parent for cid in list(node.components) for parent in component_ancestors(data, cid))
        cids = sorted(cid for cid in node.components if cid in components)
        tests = {anchor.split(":", 1)[0] for anchors in node.contract.get("TESTED_BY", {}).values() for anchor in anchors}
        for path in sorted(tests):
            if not any(matches_any(path, component_scope(data, components[cid]).get("tests", [])) for cid in cids):
                node.nonnested_tests.add(path)
                tree.findings.append(Finding("warn", "test_not_nested", node.home if node.home_kind == "component" else "",
                    f"{node.id} binds {path}, which is not in the tests of {', '.join(cids) or '(no components)'}; "
                    "list it there or bind a test that belongs to them"))
    for mid, code, message in pending_findings:
        level = "error" if code in {"parent_unknown", "parent_cycle", "parent_import_mismatch"} else "warn"
        tree.findings.append(Finding(level, code, nodes[mid].home if nodes[mid].home_kind == "component" else "", message))

    sibling_anchors: dict[tuple[str, str], list[ModelNode]] = defaultdict(list)
    for node in nodes.values():
        if node.source not in {"PARENT", "import"} or node.parent_kind == "system":
            continue
        if node.parent_kind == "component":
            allowed = set(component_files(component_scope(data, components[node.parent]), inv))
        else:
            parent = nodes[node.parent]
            cids = set(parent.contract.get("COMPONENTS", []))
            cids.update(owner.get(a.split(":", 1)[0]) for a in parent.contract.get("IMPLEMENTED_BY", {}).values())
            allowed = {path for cid in cids if cid in components for path in component_files(component_scope(data, components[cid]), inv)}
        for anchor in node.contract.get("IMPLEMENTED_BY", {}).values():
            anchor_path = anchor.split(":", 1)[0]
            planned_component_anchor = (
                view is not None and node.parent_kind == "component"
                and not (root / anchor_path).exists()
                and matches_any(anchor_path, component_scope(data, components[node.parent]).get("files", []))
            )
            if anchor_path not in allowed and not planned_component_anchor:
                tree.findings.append(Finding("error", "child_outside_parent", node.home if node.home_kind == "component" else "",
                    f"{node.path}: IMPLEMENTED_BY {anchor!r} is outside parent {node.parent!r}'s code"))
            if node.parent_kind == "model":
                sibling_anchors[(node.parent, anchor)].append(node)
    for (parent, anchor), siblings in sorted(sibling_anchors.items()):
        unique = {n.id: n for n in siblings}
        if len(unique) > 1:
            node = next(iter(unique.values()))
            tree.findings.append(Finding("error", "duplicate_child_owner", node.home if node.home_kind == "component" else "",
                f"model {parent!r}: children {', '.join(sorted(unique))} anchor the same IMPLEMENTED_BY {anchor!r}"))
    return tree
