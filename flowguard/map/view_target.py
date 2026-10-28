"""Compare and render a target overlay with its current model tree."""

from __future__ import annotations
from .discover import discover_inventory
from .facets import (
    component_facets,
    goal_rules_line,
    model_facets,
    system_facets,
    used_by_lines,
)
from .mapfile import component_files, component_graph, component_subtree, owner_index
from .targetfile import build_target_view, target_node_changes
from .tree import build_tree
from .view_format import (
    _read_facts,
    _relied_lines,
    _flow_lines,
    _show_header,
    _facet_lines_with_was,
    _model_lines,
    _layer_order,
    _component_block,
    _node_delta,
    _tidy,
    _dependency_lines,
)


def _target_comparison(root, data, inv, target):
    view = build_target_view(root, data, target)
    # A target can turn an exact source into a test, or the reverse. Keep facts
    # for both real source sets, while each snapshot retains its own test scope.
    source_paths = set()
    for mapping in (data, view.data):
        owner_index(mapping, inv)
        source_paths.update(
            path
            for component in mapping["components"]
            for path in component_files(component, inv)
            if path in inv.py
        )
    raw = discover_inventory(
        root, inv, write_cache=False, data=view.data, extra_sources=source_paths
    )
    source_cache = {}

    def snapshot(mapping, selected_view=None):
        tree = build_tree(root, mapping, inv, view=selected_view)
        graph = component_graph(mapping, inv)
        _, functions, coverage = _read_facts(
            root,
            mapping,
            inv,
            tree,
            raw=raw,
            source_cache=source_cache,
            view=selected_view,
        )
        records = {
            ("component", c["id"]): (
                c,
                component_facets(
                    root,
                    mapping,
                    inv,
                    c,
                    tree,
                    graph,
                    functions,
                    coverage=coverage[c["id"]],
                ),
            )
            for c in mapping["components"]
        }
        records.update(
            {
                ("model", mid): (node, model_facets(root, node, view=selected_view))
                for mid, node in tree.nodes.items()
            }
        )
        return (
            tree,
            graph,
            records,
            system_facets(mapping, inv, tree, graph, functions, coverage=coverage),
        )

    old_tree, _, old, old_system = snapshot(data)
    tree, graph, new, new_system = snapshot(view.data, view)
    changes = {
        key: "+" if key not in old else "-" if key not in new else "~"
        for key in old.keys() | new.keys()
        if key not in old or key not in new or _node_delta(key[0], old[key], new[key])
    }
    old_flows = {f["id"]: f for f in data.get("flows", [])}
    new_flows = {f["id"]: f for f in view.data.get("flows", [])}
    changes.update(
        {
            ("flow", fid): (
                "+" if fid not in old_flows else "-" if fid not in new_flows else "~"
            )
            for fid in old_flows.keys() | new_flows.keys()
            if old_flows.get(fid) != new_flows.get(fid)
        }
    )
    # Draft presence is visible even when all five facets still match today.
    # Added/removed identities still come from the actual two trees, not filenames.
    for entries in target_node_changes(root, data, target).values():
        for entry in entries:
            kind, identity = entry.split(":", 1)
            key = (kind, identity)
            if (
                key in old
                and key in new
                or kind == "flow"
                and identity in old_flows
                and identity in new_flows
            ):
                changes.setdefault(key, "~")
    return view, old_tree, tree, old, new, changes, graph, old_system, new_system, raw


def _render_target_show(root, data, inv, target, *, component, detail):
    view, old_tree, tree, old, new, changes, graph, old_system, new_system, raw = (
        _target_comparison(root, data, inv, target)
    )
    merged = view.data
    component_ids = {
        cid for kind, cid in old.keys() | new.keys() if kind == "component"
    }
    ordered = [c["id"] for c in merged["components"]] + [
        c["id"] for c in data["components"]
    ]
    display_data = {
        **merged,
        "components": [
            (new.get(("component", cid)) or old[("component", cid)])[0]
            for cid in dict.fromkeys(ordered)
            if cid in component_ids
        ],
    }
    if component and component != "system":
        descendants = {
            c["id"]
            for mapping in (data, merged)
            for c in component_subtree(mapping, component)
        }
        component_ids = {
            cid
            for cid in component_ids
            if cid in descendants or cid.startswith(component + ".")
        }
        if not component_ids:
            return f"no component {component!r}; run 'python -m flowguard read' to list components"
    elif component == "system":
        component_ids = set()
    counts = {mark: sum(value == mark for value in changes.values()) for mark in "+~-"}
    lines = [
        _show_header(merged, graph, inv),
        f'target: "{target.goal}" (+{counts["+"]} ~{counts["~"]} -{counts["-"]} nodes)',
        goal_rules_line(root, data, target, view)[0],
        next(line for line in new_system.code if line.startswith("coverage:")),
    ]
    if not component:
        flows = {f["id"]: f for f in [*data.get("flows", []), *merged.get("flows", [])]}
        for kind, fid in sorted(changes):
            if kind == "flow":
                flow = flows[fid]
                lines.append(
                    f'> {changes[(kind, fid)]} flow {fid}: {flow.get("summary", "")} :: '
                    + " -> ".join(flow.get("steps", []))
                    + (
                        f" model: {flow['model']}"
                        if flow.get("model")
                        else " (no model)"
                    )
                    + (
                        " (removed by the target)"
                        if changes[(kind, fid)] == "-"
                        else ""
                    )
                )
    model_data = {
        mid: record[1] for (kind, mid), record in new.items() if kind == "model"
    }
    old_model_data = {
        mid: record[1] for (kind, mid), record in old.items() if kind == "model"
    }
    if component is None or component == "system":
        if component == "system":
            lines.extend(_facet_lines_with_was(new_system, old_system, "  "))
        for snapshot, facts, removed in (
            (tree, model_data, False),
            (old_tree, old_model_data, True),
        ):
            roots = {
                mid
                for mid, node in snapshot.nodes.items()
                if node.home_kind == "system"
                and (
                    (changes.get(("model", mid)) == "-")
                    if removed
                    else ("model", mid) in changes
                )
            }
            lines.extend(
                _model_lines(
                    snapshot,
                    roots,
                    facts,
                    bindings=bool(component or detail),
                    changes=changes,
                    previous=old,
                    fold=not bool(component or detail),
                )
            )
    if component == "system":
        return _tidy("\n".join(lines))
    related = (
        {node.id for cid in component_ids for node in tree.models_for_component(cid)}
        if component
        else set()
    )
    foreign = {
        mid
        for mid in related
        if tree.nodes[mid].home_kind != "component"
        or tree.nodes[mid].home not in component_ids
    }
    old_related = (
        {
            node.id
            for cid in component_ids
            for node in old_tree.models_for_component(cid)
        }
        if component
        else set()
    )
    old_foreign = {
        mid
        for mid in old_related
        if changes.get(("model", mid)) == "-"
        and (
            old_tree.nodes[mid].home_kind != "component"
            or old_tree.nodes[mid].home not in component_ids
        )
    }
    relevant = {cid for kind, cid in changes if kind == "component"}
    relevant.update(
        node.home
        for snapshot in (old_tree, tree)
        for node in snapshot.nodes.values()
        if node.home_kind == "component" and ("model", node.id) in changes
    )
    for display_comp, depth in _layer_order(display_data, component_ids):
        cid = display_comp["id"]
        key = ("component", cid)
        before, after = old.get(key), new.get(key)
        own = {
            mid
            for mid, node in tree.nodes.items()
            if node.home_kind == "component" and node.home == cid
        }
        ids = (
            own
            if component or detail
            else {mid for mid in own if ("model", mid) in changes}
        )
        removed = {
            mid
            for mid, node in old_tree.nodes.items()
            if node.home_kind == "component"
            and node.home == cid
            and changes.get(("model", mid)) == "-"
        }
        if (
            not component
            and key not in changes
            and not ids
            and not removed
            and not any(
                child["id"] in relevant
                for child in component_subtree(display_data, cid)
            )
        ):
            continue
        comp, fact = after or before
        mark = changes.get(key, "")
        heading = f"\n## {mark + ' ' if mark else ''}{cid} [{comp.get('layer') or '-'}] {fact.code[0]}, {fact.rule_count} rules"
        full = bool(detail or cid == component)
        body = [heading + (" (removed by the target)" if mark == "-" else "")]
        if mark != "-":
            if full:
                body.extend(
                    _facet_lines_with_was(fact, before[1] if before else None, "  ")
                )
                body.extend(used_by_lines(merged, inv, tree, cid))
                body.extend(_dependency_lines(merged, inv, cid, graph, raw))
                body.extend(_relied_lines(merged, inv, raw, tree, model_data, cid))
                body.extend(_flow_lines(merged, tree, model_data, cid))
            else:
                body.append("  " + fact.purpose)
                delta = _node_delta("component", before, after)
                if delta:
                    body.append("  changes: " + "; ".join(delta))
            body.extend(
                _model_lines(
                    tree,
                    ids,
                    model_data,
                    component=cid if full else None,
                    bindings=full,
                    changes=changes,
                    previous=old,
                    fold=not full,
                )
            )
        body.extend(
            _model_lines(
                old_tree,
                removed,
                old_model_data,
                changes=changes,
                previous=old,
                fold=not full,
            )
        )
        if cid == component:
            for snapshot, facts, mids in (
                (tree, model_data, foreign),
                (old_tree, old_model_data, old_foreign),
            ):
                for mid in sorted(mids):
                    row = _model_lines(
                        snapshot, {mid}, facts, changes=changes, previous=old
                    )[0]
                    body.append(row + f" (home {snapshot.nodes[mid].home})")
        lines.append(_component_block(body, depth))
    if component is None:
        unchanged = sum(
            ("component", c["id"]) not in changes for c in data["components"]
        )
        lines.append(
            f"unchanged: {unchanged} component(s); python -m flowguard read shows them"
        )
    return _tidy("\n".join(lines))
