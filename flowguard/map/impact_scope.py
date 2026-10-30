"""Impact report data and the component-wide caller closure."""

from __future__ import annotations
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from .common import (
    DEFAULT_TEST_COMMAND,
    SOURCE_EXTS,
    glob_match,
    is_collectable_test,
    is_product_file,
    matches_any,
    normalize_newlines,
    read_source,
)
from .inventory import Inventory
from .mapfile import (
    component_files,
    component_scope,
    component_subtree,
    component_graph,
    dependency_evidence,
    flow_step_parts,
    ignore_patterns,
    is_stale,
    model_registry,
    read_model_contract,
)
from .tree import build_tree
from .impact_history import (
    _anchor_changed,
    _binding_indexes,
    _commands_for_tests,
    _comment_only,
    _owner_model_paths,
    _previous_map,
    _removed_model_context,
    _tests_reaching,
    project_relative,
)

VERIFICATION_FIELDS = (
    "files",
    "entrypoints",
    "depends_on",
    "tests",
    "models",
    "state",
    "side_effects",
    "parent",
)


@dataclass
class Impact:
    changed: list[str]
    direct: list[str]
    dependents: list[str]
    unmapped: list[str]
    tests: list[str]
    models: list[str]
    needs_review: list[str]
    test_command: str = DEFAULT_TEST_COMMAND
    total_tests: int = 0
    selected_test_functions: int = 0
    total_test_functions: int = 0
    map_changed: bool = False
    depth: int | None = None
    uncertainty: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    map_review: list[str] = field(default_factory=list)
    model_ids: list[str] = field(default_factory=list)
    test_commands: dict[str, str] = field(default_factory=dict)
    no_checks: list[str] = field(default_factory=list)
    comment_only: list[str] = field(default_factory=list)
    review_models: dict[str, list[str]] = field(default_factory=dict)
    relied_models: list[str] = field(
        default_factory=list
    )  # "<model> via <owner>:<anchor symbol>"
    flow_models: list[str] = field(
        default_factory=list
    )  # "flow <id>: step <n> changed; model <M>"
    port_lines: list[str] = field(default_factory=list)
    unexplained: list[str] = field(
        default_factory=list
    )  # "<component>: <path:symbol> (<entrypoint|state writer>)"

    changed_functions: list[str] = field(default_factory=list)
    uncertain_files: dict[str, str] = field(default_factory=dict)
    unreached: list[str] = field(default_factory=list)
    test_functions: dict[str, list[str]] = field(default_factory=dict)
    whole_test_files: list[str] = field(default_factory=list)
    model_reasons: dict[str, list[str]] = field(default_factory=dict)
    bound_test_count: int = 0
    calling_test_count: int = 0
    also_reached: list[str] = field(default_factory=list)
    no_git: str = ""
    consumer_lines: list[str] = field(default_factory=list)
    promise_lines: list[str] = field(default_factory=list)
    promise_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            key: value
            for key, value in self.__dict__.items()
            if key not in ("_test_function_counts", "model_source_causes")
        }


def _broad_impact(
    root: Path,
    data: dict,
    inv: Inventory,
    changed: list[str],
    depth: int | None = None,
    *,
    base: str | None = None,
    broad: bool = False,
    package_init: bool = True,
) -> Impact:
    """Select source caller closure; test/model edits retain only their explicit links."""
    if depth is not None and depth < 0:
        raise ValueError("impact depth must be nonnegative")
    changed = sorted(
        {
            project_relative(root, f)
            for f in changed
            if "__pycache__" not in Path(project_relative(root, f)).parts
            and not f.endswith((".pyc", ".pyo"))
            and not project_relative(root, f).startswith(
                (".flowguard/cache/", ".flowguard/target/")
            )
        }
    )
    previous = _previous_map(root, base) if ".flowguard/map.json" in changed else None
    # A comment-only edit keeps its owner in REVIEW but selects no callers, tests or models.
    comment_only = sorted(f for f in changed if _comment_only(root, base, f))
    source_paths = {f for f in changed if f not in comment_only and not inv.is_test(f)
                    and not f.startswith(".flowguard/")
                    and (f in inv.source or Path(f).suffix in SOURCE_EXTS)}
    source_causes = defaultdict(set)
    source_seeds = defaultdict(set)
    by_id = {c["id"]: c for c in data["components"]}
    old_by_id = {c["id"]: c for c in (previous or {}).get("components", [])}
    inv.set_explicit_sources(
        [p for comp in data["components"] for p in comp.get("files", [])]
    )
    actual = component_graph(data, inv)
    evidence = dependency_evidence(data, inv)
    facades = {
        c["id"]
        for c in data["components"]
        if any(inv.py[f].lazy_exports for f in component_files(c, inv) if f in inv.py)
    }
    terminal = {
        (src, dst)
        for src in facades
        for dst in evidence.get(src, ()) - actual.get(src, set())
    }
    graph = {cid: set(edges) for cid, edges in actual.items()}
    declared_only = set()
    for comp in data["components"]:
        for dst in comp.get("depends_on", []):
            if dst in by_id:
                if dst not in evidence.get(comp["id"], ()):
                    declared_only.add((comp["id"], dst))
                if (comp["id"], dst) not in terminal:
                    graph.setdefault(comp["id"], set()).add(dst)
    for comp in old_by_id.values():
        for dst in comp.get("depends_on", []):
            if comp["id"] in by_id and (comp["id"], dst) not in terminal:
                graph.setdefault(comp["id"], set()).add(dst)
    reverse: dict[str, set[str]] = defaultdict(set)
    reverse_terminal: dict[str, set[str]] = defaultdict(set)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse[dst].add(src)
    for src, dst in terminal:
        reverse_terminal[dst].add(src)
    removed, prior_contracts, historical_imports = _removed_model_context(
        root, base, changed
    )
    tree = build_tree(root, data, inv, historical_imports=historical_imports)
    test_bindings, model_bindings = _binding_indexes(data, tree)
    old_tests, old_models = _binding_indexes(previous or {})
    registry = model_registry(root, data)
    registered = {entry.path: entry for entry in registry.entries}
    contract_inputs: dict[str, set[str]] = defaultdict(set)
    contract_tests: dict[str, set[str]] = defaultdict(set)
    readonly_unchanged = set()
    uses_diffs = {}
    for entry in registry.entries:  # contract models bind code and tests in one way
        try:
            contract = read_model_contract(root / entry.path)
        except (OSError, SyntaxError, ValueError, TypeError):
            continue  # registry/check reports the invalid contract
        for anchor in contract.get("IMPLEMENTED_BY", {}).values():
            contract_inputs[anchor.split(":", 1)[0]].add(entry.path)
        uses = [
            anchor
            for anchor in contract.get("USES", {}).values()
            if anchor.partition(":")[0] in changed
            and anchor.partition(":")[0] not in comment_only
        ]
        hits = []
        for anchor in uses:
            path, _, symbol = anchor.partition(":")
            key = (path, symbol)
            if key not in uses_diffs:
                uses_diffs[key] = _anchor_changed(root, base, path, symbol)
            if uses_diffs[key]:
                contract_inputs[path].add(entry.path)
                hits.append(anchor)
        own_changed = any(
            anchor.partition(":")[0] in changed
            for anchor in contract.get("IMPLEMENTED_BY", {}).values()
        )
        if uses and not hits and not own_changed:
            readonly_unchanged.add(entry.path)
        for anchors in contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                contract_tests[entry.path].add(anchor.split(":", 1)[0])
    direct, blocked, map_review = set(), [], []
    selected_model_paths, matched, seeds = set(), set(), set()
    retired = set()
    matched_owners: dict[str, set[str]] = defaultdict(set)
    tests = {
        f
        for f in changed
        if f in inv.tests and is_collectable_test(f) and f not in comment_only
    }
    for f in changed:
        for comp in list(by_id.values()) + list(old_by_id.values()):
            if is_product_file(f, comp.get("files", [])):
                direct.add(comp["id"])
                matched.add(f)
                matched_owners[f].add(comp["id"])
                if f not in comment_only:
                    seeds.add(comp["id"])
                if f in source_paths:
                    source_seeds[comp["id"]].add(f)
        if f in comment_only:
            if _owner_model_paths(f, model_bindings) or any(
                glob_match(f, pat) for pat in test_bindings
            ):
                matched.add(f)
            continue
        selected_model_paths.update(contract_inputs.get(f, ()))
        if f in source_paths:
            for model in contract_inputs.get(f, ()):
                source_causes[model].add(f)
        for model in contract_inputs.get(
            f, ()
        ):  # anchored code changed: the model's named tests too
            tests.update(contract_tests.get(model, ()))
        bound_models = _owner_model_paths(f, model_bindings)
        old_bound_models = _owner_model_paths(f, old_models)
        selected_model_paths.update(bound_models)
        if bound_models or old_bound_models:
            matched.add(f)
        # Changing a test does not imply changing its owning production component.
        # Select only this test and explicitly linked owner models.
        for pat, cids in test_bindings.items():
            if glob_match(f, pat) and inv.is_test(f):
                matched.add(f)
        for model, linked_tests in contract_tests.items():
            if f in linked_tests:
                selected_model_paths.add(model)
            if f == model or model in bound_models:
                tests.update(linked_tests)
        if (
            f.startswith((".flowguard/models/", ".flowguard/verification/"))
            and f.endswith(".py")
            and not bound_models
            and not old_bound_models
        ):
            if Path(f).parent.as_posix() == ".flowguard/models":
                if not Path(f).name.startswith("_"):
                    selected_model_paths.add(f)
            else:
                blocked.append(
                    f"{f}: no registered executable model binding; declare a contract model or remove this file"
                )
        if (
            f not in inv.source
            and not f.startswith(".flowguard/models/")
            and f != ".flowguard/map.json"
        ):
            referenced = set()
            for t in inv.tests:
                if not is_collectable_test(t):
                    continue
                try:
                    text = read_source(root / t)
                except OSError:
                    continue
                if f in text or Path(f).name in text:
                    referenced.add(t)
            tests.update(referenced)
    referenced_models = {
        p for comp in data["components"] for p in comp.get("models", [])
    }
    referenced_models.update(
        flow["model"] for flow in data.get("flows", []) if flow.get("model")
    )
    current_ids = {entry.id for entry in registry.entries}
    prior_by_id = {
        contract["MODEL_ID"]: contract for contract in prior_contracts.values()
    }
    for path in sorted(removed.intersection(changed)):
        if Path(path).name.startswith("_"):
            continue
        selected_model_paths.add(path)
        contract = prior_contracts.get(path)
        if contract is None:
            continue  # unknown/malformed/ambiguous old contracts still fail
        mid = contract["MODEL_ID"]
        importers = tree.importers(path)
        dangling_children = {
            n.id
            for n in tree.nodes.values()
            if n.contract.get("PARENT") == mid
            and mid not in current_ids
            and mid not in by_id
            and mid != "system"
        }
        linked = importers | dangling_children
        linked.update(entry.id for entry in registry.entries if entry.id == mid)
        parent, seen = contract.get("PARENT"), set()
        while (
            parent and parent not in by_id and parent != "system" and parent not in seen
        ):
            seen.add(parent)
            if parent in tree.nodes:
                linked.add(parent)
                break
            parent = prior_by_id.get(parent, {}).get("PARENT")
        for linked_id in linked:
            node = tree.nodes[linked_id]
            selected_model_paths.add(node.path)
            tests.update(contract_tests.get(node.path, ()))
        prior_tests = {
            anchor.split(":", 1)[0]
            for anchors in contract.get("TESTED_BY", {}).values()
            for anchor in anchors
        }
        tests.update(prior_tests & set(inv.tests))
        if (
            path not in referenced_models
            and not importers
            and not dangling_children
            and not contract_inputs.get(path)
        ):
            retired.add(path)
            matched.add(path)
        else:
            blocked.append(
                f"{path}: removed model is still referenced by the current map, model tree or code anchors"
            )
    # Rules travel along direct calls: an edit that calls another component's anchored code selects its model.
    relied, unexplained = [], []
    edited_sources = [
        f
        for f in changed
        if f in inv.py and f not in comment_only and not inv.is_test(f)
    ]
    if edited_sources:
        from .discover import discover_inventory, relied_models
        from .lint import coverage_facts

        raw = discover_inventory(root, inv, data=data, write_cache=False)
        # Functions of the edited files that no model anchor, test or NOT_MODELED reason explains.
        for cid, record in sorted(coverage_facts(root, data, inv, tree, raw).items()):
            entries = set(record.get("unexplained_entries", ()))
            unexplained.extend(
                f"{cid}: {anchor} ({'entrypoint' if anchor in entries else 'state writer'})"
                for anchor in record["unexplained"]
                if anchor.partition(":")[0] in edited_sources
            )
        anchors = {
            mid: list(node.contract.get("IMPLEMENTED_BY", {}).values())
            for mid, node in tree.nodes.items()
        }
        relied_sources = {}
        for mid, sites in sorted(
            relied_models(raw, data, inv, anchors, files=edited_sources, source_files=relied_sources).items()
        ):
            node = tree.nodes[mid]
            selected_model_paths.add(node.path)
            source_causes[node.path].update(relied_sources.get(mid, set()) & source_paths)
            tests.update(contract_tests.get(node.path, ()))
            relied.extend(
                f"{mid} via {owner}:{symbol}" for owner, symbol in sorted(sites)
            )
    # A flow's model protects every step: a real edit to a step's code selects it.
    flow_lines = []
    registered_ids = {entry.path: entry.id for entry in registry.entries}
    for flow in data.get("flows", []):
        if not flow.get("model"):
            continue
        for number, step in enumerate(flow.get("steps", []), 1):
            cid, symbol, _ = flow_step_parts(step)
            if cid not in by_id:
                continue
            owned = set(component_files(component_scope(data, by_id[cid]), inv))
            hit = [
                f
                for f in changed
                if f in owned
                and f not in comment_only
                and (not symbol or f in inv.py and symbol in inv.py[f].symbols)
            ]
            if hit:
                selected_model_paths.add(flow["model"])
                source_causes[flow["model"]].update(set(hit) & source_paths)
                tests.update(contract_tests.get(flow["model"], ()))
                flow_lines.append(
                    f"flow {flow['id']}: step {number} changed; model "
                    f"{registered_ids.get(flow['model'], flow['model'])}"
                )
    top_model_files = [
        f
        for f in changed
        if Path(f).parent.as_posix() == ".flowguard/models" and f.endswith(".py")
    ]
    importers = {f: tree.importers(f) for f in top_model_files}
    for f in top_model_files:
        if f not in comment_only:
            selected_model_paths.update(tree.nodes[mid].path for mid in importers[f])
            if f in registered:
                selected_model_paths.add(f)
            if importers[f] or f in registered:
                matched.add(f)
    if ".flowguard/map.json" in changed:
        if previous is None:
            if (
                base is not None
                and subprocess.run(
                    [
                        "git",
                        "-C",
                        str(root),
                        "ls-files",
                        "--error-unmatch",
                        ".flowguard/map.json",
                    ],
                    capture_output=True,
                ).returncode
                == 0
            ):
                blocked.append(
                    ".flowguard/map.json: previous map unavailable; verification scope cannot be compared"
                )
        else:
            for cid in set(by_id) | set(old_by_id):
                now, old = by_id.get(cid), old_by_id.get(cid)
                if now is not None:
                    now = {**now, "depends_on": sorted(set(now.get("depends_on", [])))}
                if old is not None:
                    old = {**old, "depends_on": sorted(set(old.get("depends_on", [])))}
                if (
                    now is None
                    or old is None
                    or any(
                        now.get(k, []) != old.get(k, []) for k in VERIFICATION_FIELDS
                    )
                ):
                    direct.add(cid)
                    seeds.add(cid)
                elif {
                    k: v for k, v in now.items() if k not in {"status", "fingerprint"}
                } != {
                    k: v for k, v in old.items() if k not in {"status", "fingerprint"}
                }:
                    map_review.append(cid)
                if (
                    now is not None
                    and old is not None
                    and now.get("parent") != old.get("parent")
                ):
                    # Keep a still-registered model whose explicitly protected old
                    # subsystem lost this member. Placement alone does not claim siblings.
                    for node in tree.nodes.values():
                        if any(
                            cid
                            in {
                                member["id"]
                                for member in component_subtree(previous, protected)
                            }
                            for protected in node.contract.get("COMPONENTS", [])
                        ):
                            selected_model_paths.add(node.path)
    affected, traversed = set(seeds), set(seeds)
    component_sources = defaultdict(set, {cid: set(paths) for cid, paths in source_seeds.items()})
    terminal_sources = defaultdict(set)
    queue = deque((cid, 0, frozenset(source_seeds[cid])) for cid in sorted(seeds))
    propagated_sources = defaultdict(set)
    processed = set()
    while queue:
        cid, distance, origins = queue.popleft()
        if depth is not None and distance >= depth:
            continue
        new_sources = origins - propagated_sources[cid]
        if cid in processed and not new_sources:
            continue
        processed.add(cid)
        propagated_sources[cid].update(new_sources)
        terminal_callers = reverse_terminal.get(cid, ())
        affected.update(terminal_callers)
        for caller in terminal_callers:
            terminal_sources[caller].update(new_sources)
        for caller in sorted(reverse.get(cid, ())):
            component_sources[caller].update(new_sources)
            added_sources = new_sources - propagated_sources[caller]
            if caller not in traversed:
                affected.add(caller)
                traversed.add(caller)
                queue.append((caller, distance + 1, frozenset(added_sources)))
            elif added_sources:
                # Selection still visits each component once; only newly arriving
                # source origins continue through the existing graph.
                queue.append((caller, distance + 1, frozenset(added_sources)))
    tests.update(
        _tests_reaching(
            inv,
            [f for f in changed if f not in comment_only],
            package_init=package_init,
        )
    )
    owner_tests: dict[str, set[str]] = defaultdict(set)
    owner_models: dict[str, set[str]] = defaultdict(set)
    for cid in affected:
        for comp in (by_id.get(cid), old_by_id.get(cid)):
            if comp is None:
                continue
            owner_tests[cid].update(
                f
                for f in inv.tests
                if any(glob_match(f, pat) for pat in comp.get("tests", []))
            )
            if comp is by_id.get(cid):
                owner_models[cid].update(n.path for n in tree.models_for_component(cid))
            else:
                owner_models[cid].update(
                    path for path in comp.get("models", []) if (root / path).is_file()
                )
        if cid not in seeds:
            owner_models[cid].difference_update(readonly_unchanged)
        tests.update(owner_tests[cid])
        selected_model_paths.update(owner_models[cid])
        for model in owner_models[cid]:
            source_causes[model].update(component_sources[cid] | terminal_sources[cid])
    for model in selected_model_paths:
        if model in changed:
            tests.update(contract_tests.get(model, ()))
    from .port import model_port, port_selection, code_callers

    ports = {
        mid: node.contract["port"]
        for mid, node in tree.nodes.items()
        if "port" in node.contract
    }
    port_lines = []
    for path in top_model_files:
        if path in comment_only or path in removed or path not in registered:
            continue
        mid = registered[path].id
        if mid not in ports:
            continue
        blob = (
            subprocess.run(
                ["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True
            )
            if base
            else None
        )
        available = blob is not None and blob.returncode == 0
        missing = False
        if blob is not None and not available:
            # Distinguish an actual new file from an unavailable revision/repository.
            missing = (
                subprocess.run(
                    ["git", "-C", str(root), "rev-parse", "--verify", base],
                    capture_output=True,
                ).returncode
                == 0
            )
        try:
            previous_port = (
                model_port(normalize_newlines(blob.stdout)) if available else None
            )
        except (SyntaxError, ValueError, TypeError):
            previous_port, available, missing = None, False, False
        chosen, line, _ = port_selection(
            mid,
            previous_port,
            ports[mid],
            tree,
            ports,
            new_model=missing,
            unavailable=not available and not missing,
        )
        if "(no model consumer)" in line:
            from .discover import discover_inventory

            scope = {
                path
                for cid in tree.nodes[mid].components
                if cid in by_id
                for path in component_files(by_id[cid], inv)
            }
            callers = code_callers(
                discover_inventory(root, inv, data=data, write_cache=False),
                tree.nodes[mid],
                scope,
            )
            line = line.replace(
                "(no model consumer)",
                "(no model consumer; code callers: "
                + (", ".join(callers) or "-")
                + ")",
            )
        port_lines.append(line)
        selected_model_paths.update(
            tree.nodes[chosen_id].path for chosen_id, _ in chosen
        )
    if broad:
        while True:
            ancestors = {
                tree.nodes[mid].path
                for path in selected_model_paths
                if path in registered
                for mid in tree.ancestors(registered[path].id)
            }
            selected_ids = {
                registered[path].id
                for path in selected_model_paths
                if path in registered
            }
            review_children = {
                node.path
                for node in tree.nodes.values()
                if node.kind == "contract"
                and node.source == "PARENT"
                and node.parent_kind == "model"
                and node.parent in selected_ids
                and node.parent in tree.nodes
                and tree.nodes[node.parent].path
                in node.import_files | node.local_import_files
            }
            expanded = ancestors | review_children
            if expanded <= selected_model_paths:
                break
            selected_model_paths.update(expanded)
    models = []
    selected_model_paths.difference_update(retired)
    id_counts: dict[str, int] = defaultdict(int)
    for entry in registry.entries:
        id_counts[entry.id] += 1
    duplicate_ids = {mid for mid, count in id_counts.items() if count > 1}
    blocked.extend(
        f"executable model id {mid!r} is duplicated; resolve its binding"
        for mid in sorted(duplicate_ids)
    )
    for model in sorted(selected_model_paths):
        if model in registered and registered[model].id in duplicate_ids:
            continue
        elif model not in registered:
            details = [
                issue.message for issue in registry.issues if issue.path == model
            ]
            blocked.append(
                f"{model}: "
                + (
                    "; ".join(details)
                    or "selected model is missing or is not an executable registered model"
                )
            )
        else:
            models.append(model)
    uncertainty = [
        f"{src} -> {dst}: declared but unverified"
        for src, dst in sorted(declared_only)
        if src in affected or dst in affected
    ]
    owned_affected = {
        f for cid in affected if cid in by_id for f in component_files(by_id[cid], inv)
    }
    uncertainty.extend(
        f"{f}: dynamic imports may be unresolved; declare known component dependencies"
        for f in sorted(inv.dynamic_files & owned_affected)
    )
    tests = {t for t in tests if is_collectable_test(t) and inv.is_test(t)}
    test_commands, command_problems = _commands_for_tests(data, previous, tests)
    blocked.extend(command_problems)
    covered = {
        f
        for f, cids in matched_owners.items()
        if any(
            owner_tests[cid] & tests or owner_models[cid] & set(models) for cid in cids
        )
    }
    no_checks = [
        f
        for f in changed
        if f not in inv.source
        and f not in covered
        and f != ".flowguard/map.json"
        and (
            not f.startswith(".flowguard/")
            or f in importers
            and Path(f).name.startswith("_")
            and not importers[f]
        )
        and not any(
            f in read_source(root / t) or Path(f).name in read_source(root / t)
            for t in tests
            if (root / t).is_file()
        )
    ]
    needs_review = [
        cid
        for cid in sorted(direct)
        if cid in by_id and is_stale(root, by_id[cid], inv)
    ]
    from .testtree import test_functions

    function_counts = {}
    for path in inv.tests if tests else ():
        if path.endswith(".py"):
            try:
                function_counts[path] = len(test_functions(read_source(root / path)))
            except OSError:
                pass
    report = Impact(
        changed=changed,
        direct=sorted(direct),
        dependents=sorted(affected - direct),
        unmapped=[
            f
            for f in changed
            if f not in matched
            and not inv.is_test(f)
            and (f in inv.source or Path(f).suffix in SOURCE_EXTS)
            and not matches_any(f, ignore_patterns(data))
        ],
        tests=sorted(tests),
        models=models,
        needs_review=needs_review,
        review_models={
            cid: [n.id for n in tree.models_for_component(cid)] for cid in needs_review
        },
        test_command=data.get("test_command") or DEFAULT_TEST_COMMAND,
        total_tests=sum(is_collectable_test(t) for t in inv.tests),
        selected_test_functions=sum(function_counts.get(path, 0) for path in tests),
        total_test_functions=sum(function_counts.values()),
        map_changed=".flowguard/map.json" in changed,
        depth=depth,
        uncertainty=uncertainty,
        blocked=sorted(set(blocked)),
        map_review=sorted(map_review),
        model_ids=[registered[m].id for m in models],
        test_commands=test_commands,
        no_checks=no_checks,
        comment_only=comment_only,
        relied_models=relied,
        flow_models=flow_lines,
        unexplained=list(dict.fromkeys(unexplained)),
        port_lines=port_lines,
    )
    report._test_function_counts = function_counts
    # Operation-local source evidence is not part of Impact's serialized API.
    report.model_source_causes = {registered[model].id: {source: ["conservative"]
                                 for source in sorted(source_causes[model])}
                                 for model in models if source_causes[model]}
    return report
