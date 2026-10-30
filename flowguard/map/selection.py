"""Shared static call-graph reachability and model selection for map consumers."""
from __future__ import annotations
from collections import defaultdict

def reachable_functions(edges, start):
    """Operation-local transitive calls; no retained reachability index."""
    pending, found = [start], set()
    while pending:
        node = pending.pop()
        if node not in found:
            found.add(node)
            pending.extend(edges.get(node, ()))
    return found

def anchor_matches(anchor, function):
    """A primary function/class anchor includes its nested symbols."""
    path, _, symbol = anchor.partition(':')
    file, _, name = function.partition('#')
    return path == file and (name == symbol or name.startswith(symbol+'.'))

def select_model_functions(data, inv, tree, raw, functions, *, matches=None):
    """The shared body-edit selection used by change and relation views."""
    from .mapfile import component_files, component_scope, flow_step_parts

    selected = set()
    flow_lines = []
    reasons = defaultdict(list)
    own = {mid: node.contract.get("IMPLEMENTED_BY", {}) for mid, node in tree.nodes.items()}
    uses = {mid: node.contract.get("USES", {}) for mid, node in tree.nodes.items()}
    closures = {}

    def reaches(anchor, fn):
        if anchor not in closures:
            path, _, symbol = anchor.partition(":")
            starts = [
                path + "#" + name
                for name in raw.get("files", {}).get(path, {}).get("functions", {})
                if name == symbol or name.startswith(symbol + ".")
            ]
            closures[anchor] = (
                set().union(*(reachable_functions(raw["edges"], start) for start in starts))
                if starts
                else set()
            )
        return fn in closures[anchor]

    unreached = []
    for fn in sorted(functions):
        owners = {
            mid
            for mid, anchors in own.items()
            if any(anchor_matches(anchor, fn) for anchor in anchors.values())
        }
        hits = set()
        for mid in tree.nodes:
            for name, anchor in {**own[mid], **uses[mid]}.items():
                if anchor_matches(anchor, fn):
                    selected.add(mid)
                    hits.add(mid)
                    reasons[mid].append(name + " is " + fn.replace("#", ":", 1))
        reached = (
            {
                mid
                for mid, anchors in own.items()
                if any(reaches(anchor, fn) for anchor in anchors.values())
            }
            if not owners
            else set()
        )
        reached = {
            mid for mid in reached if not any(mid in tree.ancestors(other) for other in reached)
        }
        for mid in reached:
            selected.add(mid)
            hits.add(mid)
            name = next(name for name, anchor in own[mid].items() if reaches(anchor, fn))
            reasons[mid].append(name + " reaches " + fn.replace("#", ":", 1))
        for flow in data.get("flows", ()):
            mid = next(
                (mid for mid, node in tree.nodes.items() if node.path == flow.get("model")), None
            )
            if mid is None:
                continue
            for number, step in enumerate(flow.get("steps", ()), 1):
                cid, symbol, _ = flow_step_parts(step)
                comp = next((c for c in data["components"] if c["id"] == cid), None)
                if comp is None:
                    continue
                anchors = [
                    path + ":" + (symbol or fn.split("#", 1)[1])
                    for path in component_files(component_scope(data, comp), inv)
                ]
                direct_flow = any(anchor_matches(anchor, fn) for anchor in anchors)
                following = list(flow.get("steps", ()))[number:]
                continues = not following
                if following:
                    next_cid, next_symbol, reads = flow_step_parts(following[0])
                    next_component = next(
                        (c for c in data["components"] if c["id"] == next_cid), None
                    )
                    if reads is None and next_component is not None:
                        following_anchors = [
                            path + ":" + (next_symbol or fn.split("#", 1)[1])
                            for path in component_files(component_scope(data, next_component), inv)
                        ]
                        after = reachable_functions(raw["edges"], fn)
                        continues = any(
                            anchor_matches(anchor, candidate)
                            for anchor in following_anchors
                            for candidate in after
                        )
                via = (
                    not owners
                    and not any(mid in tree.ancestors(other) for other in selected)
                    and any(reaches(anchor, fn) for anchor in anchors)
                    and continues
                )
                if direct_flow or via:
                    selected.add(mid)
                    hits.add(mid)
                    flow_lines.append(f"flow {flow['id']}: step {number} changed; model {mid}")
        if not hits:
            unreached.append(fn.replace("#", ":", 1))
        if matches is not None:
            for mid in hits:
                matches.setdefault(mid, set()).add(fn)
    return selected, dict(reasons), flow_lines, unreached
