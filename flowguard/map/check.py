"""Map <-> code mutual verification.

Every finding is cheap and objective: ownership of every source file, anchors
that must exist, declared vs real dependencies, flows, model files and their
code anchors, and staleness of confirmed descriptions.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import Finding, glob_match, is_test_file, read_source, matches_any, parse_test_anchor
from .inventory import Inventory
from .debts import evaluate_debts
from .mapfile import MapError, load_map, component_files, component_graph, component_scope, component_state, dependency_evidence, flow_step_parts, is_stale, model_registry, owner_index, read_model_contract, resolve_model_path
from .tree import component_parent_findings

PLACEHOLDER_ANCHOR = "REPLACE_ME"          # templates ship anchors containing it; they fail until replaced


def symbol_defined(inv: Inventory, path: str, symbol: str) -> bool:
    """'name', 'Class.method', or a bare method name defined on any class in that file."""
    symbols = inv.py[path].symbols if path in inv.py else set()
    return symbol in symbols or any(s.endswith("." + symbol) for s in symbols)


def anchor_problem(root: Path, inv: Inventory, anchor: str) -> str | None:
    """None when 'path:Symbol' exists; otherwise a human-readable problem."""
    path, sep, symbol = anchor.partition(":")
    if PLACEHOLDER_ANCHOR in anchor:
        return f"placeholder anchor {anchor!r}: replace it with the real 'path:Symbol' this model is about"
    if not sep or not symbol:
        return f"anchor {anchor!r} must look like 'path/to/file.py:Symbol'"
    if not (root / path).is_file():
        return f"anchor file missing: {path}"
    if path in inv.py:
        if inv.py[path].parse_error:
            return f"cannot parse {path}: {inv.py[path].parse_error}"
        return None if symbol_defined(inv, path, symbol) else f"symbol {symbol!r} not found in {path}"
    text = read_source(root / path)
    last = symbol.split(".")[-1]
    return None if re.search(rf"\b{re.escape(last)}\b", text) else f"symbol {symbol!r} not found in {path}"


def anchor_problems(root: Path, anchors) -> dict[str, str]:
    """{anchor: problem} for each 'path:Symbol' that does not resolve; parses only the anchored files."""
    from .inventory import parse_python

    root, anchors = Path(root), list(anchors)
    paths = sorted({anchor.partition(":")[0] for anchor in anchors})
    parsed = {path: parse_python(root, path, path[:-3].replace("/", "."), collect_bodies=False)
              for path in paths if path.endswith(".py") and (root / path).is_file()}
    inv = Inventory(root, paths, paths, [], parsed, {}, {})
    return {anchor: problem for anchor in anchors if (problem := anchor_problem(root, inv, anchor))}


def run_check(root: Path, data: dict, inv: Inventory, *, strict: bool = False, view=None,
              evaluation=None, target_state=None) -> list[Finding]:
    from .targetfile import target_seam

    evaluation = evaluation if evaluation is not None else evaluate_debts(root, data)
    out: list[Finding] = evaluation.diagnostics(strict=strict)
    from .requests import request_findings
    out.extend(request_findings(root))
    target_state = target_state if target_state is not None else target_seam(root, load_map(root) if view is not None else data)
    level = "error" if strict else "warn"
    if target_state.missing_indexed:
        out.append(Finding(level, "target_deleted_not_staged", "",
                           "target_deleted_not_staged: .flowguard/target/ files are deleted on disk but still committed; "
                           "stage the deletion (git add -A .flowguard)"))
    elif target_state.already_promoted:
        out.append(Finding(level, "target_already_promoted", "",
                           "target_already_promoted: .flowguard/target/ is committed but changes nothing (already promoted); "
                           "delete it and commit the deletion"))
    elif not target_state.has_git and target_state.noop:
        out.append(Finding("warn", "target_noop", "", "target_noop: target changes nothing: drop it or add work"))
    out.extend(component_parent_findings(data))
    by_id = {c["id"]: c for c in data["components"]}
    children = {c.get("parent") for c in data["components"] if c.get("parent") in by_id}
    owner, owners_all = owner_index(data, inv)
    for f, ids in sorted(owners_all.items()):
        if len(ids) > 1:
            out.append(Finding("error", "file_multi_owner", ids[0], f"{f} is also matched by {ids[1:]}"))
    unmapped = [f for f in inv.source if not is_test_file(f) and f not in owner]
    near: dict[str, set[str]] = {}
    for path, cid in (owner.items() if unmapped else ()):
        near.setdefault(path.rpartition("/")[0], set()).add(cid)
    for f in unmapped:
        here = sorted(near.get(f.rpartition("/")[0], ()))   # point at existing owners before a new component
        hint = (f"; the files next to it belong to {here[0]}: add it there unless it is a new responsibility"
                if len(here) == 1 else
                f"; the files next to it belong to {', '.join(here)}: add it to the one that owns its responsibility"
                if 1 < len(here) <= 4 else "")
        out.append(Finding("error", "file_unmapped", "", f"{f} has no owning component{hint}"))

    for path, info in sorted(inv.py.items()):
        if path in inv.source and (path in owner or not is_test_file(path)) and info.parse_error:
            out.append(Finding("error", "source_parse_error", owner.get(path, ""),
                               f"cannot parse {path}: {info.parse_error}"))
    registry = model_registry(root, data, view=view)
    for issue in registry.issues:
        out.append(Finding("error", issue.code, "", f"{issue.path}: {issue.message}"))

    from .tree import build_tree
    tree = build_tree(root, data, inv, view=view)
    out.extend(tree.findings)

    for flow in data.get("flows", []):
        for position, step in enumerate(flow.get("steps", [])):
            comp_id, symbol, handoff = flow_step_parts(step)
            if handoff is not None and (position == 0 or not handoff or not symbol):
                reason = ("the first step reads no earlier file" if position == 0 else
                          "nothing follows 'reads'" if not handoff else "a 'reads' step names a command symbol")
                out.append(Finding("error", "flow_handoff_invalid", comp_id if comp_id in by_id else "",
                                   f"flow {flow['id']}: step {step!r}: {reason}; write '<component>:<Symbol> reads <file>'"))
            if comp_id not in by_id:
                out.append(Finding("error", "flow_step_unknown", "", f"flow {flow['id']}: step {step!r} names no component"))
            elif symbol:
                owned = component_files(component_scope(data, by_id[comp_id]), inv)
                python_only = all(f in inv.py for f in owned)
                if python_only and not any(symbol_defined(inv, f, symbol) for f in owned):
                    out.append(Finding("error", "flow_step_broken", comp_id,
                                       f"flow {flow['id']}: symbol {symbol!r} not found in component {comp_id}"))
        if flow.get("model"):
            model_path = resolve_model_path(root, flow["model"], view=view)
            if model_path is None or not model_path.is_file():
                out.append(Finding("error", "model_missing", "", f"flow {flow['id']}: model file {flow['model']} missing"))

    for entry in registry.entries:              # contract models share one binding rule
        rel = entry.path
        path = resolve_model_path(root, rel, view=view)
        if path is None:
            out.append(Finding("error", "model_missing", "", f"model file {rel} missing"))
            continue
        try:
            contract = read_model_contract(path)
        except (SyntaxError, ValueError) as exc:
            out.append(Finding("error", "model_unreadable", "", f"{rel}: {exc}"))
            continue
        if entry.kind == "contract":
            if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
                out.append(Finding("error", "model_contract", "", f"{rel}: needs MODEL_ID and def build_explorer()"))
        from .mapfile import process_model_reason
        process = process_model_reason(data, contract, root=root, evaluation=evaluation)
        if not contract.get("IMPLEMENTED_BY"):
            out.append(Finding("error", "model_anchor_missing", entry.id,
                               f"{rel}: declares no IMPLEMENTED_BY anchors; name the real code it checks "
                               "('path:Symbol'), or plan it as a target model (python -m flowguard target start)"))
        if entry.kind == "contract" and "conformance" not in contract["functions"] and not process:
            out.append(Finding("error", "model_conformance_missing", "",
                               f"{rel}: abstract boundary only: no conformance(); replay the real code or "
                               "compare it as code facts, or plan it as a target model (python -m flowguard target start)"))
        for comp_id in contract.get("COMPONENTS", []):
            if comp_id not in by_id:
                out.append(Finding("error", "model_component_unknown", "", f"{rel}: COMPONENTS names unknown {comp_id!r}"))
        node = tree.nodes.get(entry.id)
        if entry.kind == "contract" and node:
            for cid, comp in by_id.items():
                if rel in comp.get("models", []) and cid not in node.components:
                    out.append(Finding("warn", "model_listed_unrelated", cid,
                                       f"{rel} is listed here but its COMPONENTS, IMPLEMENTED_BY and PARENT "
                                       "do not place it here; remove it from models"))
        for invariant, anchors in contract.get("TESTED_BY", {}).items():
            for anchor in anchors:
                try:
                    _, _, suffix = parse_test_anchor(anchor)
                    problem = anchor_problem(root, inv, anchor.removesuffix(suffix) if suffix else anchor)
                    if suffix and problem:
                        problem = f"{anchor}: {problem}"
                except ValueError as exc:
                    problem = str(exc)
                if problem:
                    out.append(Finding("error", "model_test_broken", "", f"{rel}: {invariant} -> {problem}"))
        for kind in ("IMPLEMENTED_BY", "USES"):
            for block, anchor in contract.get(kind, {}).items():
                problem = anchor_problem(root, inv, anchor)
                if problem:
                    label = f"USES {block}" if kind == "USES" else block
                    out.append(Finding("error", "model_anchor_broken", "", f"{rel}: {label} -> {problem}"))

    bound_tests = [pat for comp in data["components"] for pat in comp.get("tests", [])]
    for test in inv.tests:
        if test not in owner and (Path(test).name.startswith("test_") or Path(test).name.endswith("_test.py")
                                   or ".test." in test or ".spec." in test) and not matches_any(test, bound_tests):
            out.append(Finding("warn", "test_unbound", "", f"{test}: no component lists this test in tests"))
    graph = component_graph(data, inv)
    from .discover import discover_inventory
    raw = discover_inventory(root, inv, write_cache=view is None, data=data)
    evidence_graph = dependency_evidence(data, inv, raw, evaluation=evaluation)
    from .lint import apply_accepted_debts, duplicate_owner_findings, normalized_debts, structural_findings
    out.extend(apply_accepted_debts(structural_findings(data, graph, root=root, inv=inv) + duplicate_owner_findings(data),
                                    normalized_debts(data), evaluation=evaluation)[0])
    declared_entries: dict[str, set[str]] = {}
    for component in data["components"]:
        for anchor in component.get("entrypoints", []):
            declared_entries.setdefault(anchor, set()).add(component["id"])
    for anchor, declaring in sorted(declared_entries.items()):
        if len(declaring) > 1:
            ids = sorted(declaring)
            out.append(Finding("error", "entrypoint_owner", ids[0],
                               f"{anchor} is listed by {' and '.join(ids)}; one promise has one owner"))
    stale_level = "error" if strict else "warn"
    for c in data["components"]:
        cid, files = c["id"], component_files(c, inv)
        if not files and not (cid in children and not c.get("files")):
            out.append(Finding("error", "component_empty", cid, f"files {c.get('files')} match no source file"))
        for pat in c.get("files", []):
            if not any(glob_match(f, pat) for f in inv.source):
                out.append(Finding("warn", "pattern_dead", cid, f"files pattern {pat!r} matches nothing"))
        for anchor in c.get("entrypoints", []):
            path = anchor.partition(":")[0]
            if not matches_any(path, c.get("files", [])):
                owners = sorted(other["id"] for other in data["components"]
                                if matches_any(path, other.get("files", [])))
                ownership = (f"belongs to {', '.join(owners)}" if owners
                             else "does not match this component's files")
                out.append(Finding("error", "entrypoint_owner", cid,
                                   f"{anchor} is listed by {cid} but {path} {ownership}; list it on its owner"))
            problem = anchor_problem(root, inv, anchor)
            if problem:
                out.append(Finding("error", "anchor_broken", cid, problem))
        for pat in c.get("tests", []):
            if not any(glob_match(f, pat) for f in inv.files):
                out.append(Finding("error", "test_missing", cid, f"tests pattern {pat!r} matches nothing"))
        for m in c.get("models", []):
            model_path = resolve_model_path(root, m, view=view)
            if model_path is None or not model_path.is_file():
                out.append(Finding("error", "model_missing", cid, f"model file {m} missing"))
        declared, actual = set(c.get("depends_on", [])), graph.get(cid, set())
        for d in sorted(declared - set(by_id)):
            out.append(Finding("error", "dep_unknown", cid, f"depends_on {d!r} is not a component"))
        for d in sorted(actual - declared):
            out.append(Finding("error", "dep_undeclared", cid, f"imports {d} but depends_on does not list it"))
        unverified = sorted((declared if not files and cid in children else
                             declared - evidence_graph.get(cid, set())) & set(by_id))
        if unverified:
            out.append(Finding("error", "dep_unused", cid,
                               f"no import, module literal, injected collaborator or accepted debt evidence for: {', '.join(unverified)}"))
        if c["status"] == "draft":
            out.append(Finding(stale_level, "draft", cid, "description not confirmed yet"))
        elif not c.get("summary") or not c.get("responsibilities"):
            out.append(Finding("error", "confirmed_but_empty", cid, "a confirmed component needs summary and responsibilities"))
        else:
            state = component_state(root, c, inv, data)
            if state == "migrate":
                out.append(Finding(stale_level, "fingerprint_migrate", cid,
                                   f"fingerprint formula changed (format 1 -> 2): confirm {cid} once"))
            elif state == "stale":
                out.append(Finding(stale_level, "stale", cid, "owned files changed since last confirm; re-read them, update the description if behavior changed, then confirm"))
    from .lint import apply_accepted_debts
    from .lint_models import entrypoint_coverage_findings, model_coverage, model_writer_findings
    covered, not_modeled = model_coverage(root, data, registry, view=view)
    entry_findings = entrypoint_coverage_findings(raw, data, inv, covered, not_modeled=not_modeled,
        models_by_component={c["id"]: [n.path for n in tree.models_for_component(c["id"])] for c in data["components"]})
    entry_findings.extend(model_writer_findings(raw, data, root, inv, registry, view=view))
    out.extend(apply_accepted_debts(entry_findings, data.get("accepted_debts", []), evaluation=evaluation)[0])
    for directory in data.get("import_roots", []):
        if not (root / directory).is_dir():
            out.append(Finding("warn", "import_root_missing", "", f"import root directory missing: {directory}"))
    from .lint_models import model_size_findings
    out.extend(apply_accepted_debts(model_size_findings(root, data, inv, view=view, tree=tree),
                                    data.get('accepted_debts', []), evaluation=evaluation)[0])
    from .testtree import test_file_findings
    out.extend(apply_accepted_debts(test_file_findings(root, data, inv, tree),
                                    data.get('accepted_debts', []), evaluation=evaluation)[0])
    out.extend(model_edit_findings(root, load_map(root) if view is not None else data, stale_level))
    for finding in out:
        if finding.code == "model_anchor_missing":
            apply_accepted_debts([finding], data.get("accepted_debts", []), evaluation=evaluation)
    return out


def model_edit_findings(root, data, level):
    from .common import content_digest
    from .targetfile import load_target, model_helper_digests, target_helper_baseline
    try:
        target = load_target(root)
    except MapError:
        target = None
    staged = set(target.models) if target is not None else set()
    saved = data.get("model_digests", {})
    current = {p.relative_to(root).as_posix() for p in (root / ".flowguard/models").glob("*.py")
               if p.is_file() and not p.name.startswith("_")} if "model_digests" in data else set()
    out = []
    for logical in sorted(current | set(saved)):
        path = root / logical
        if not path.is_file() or logical not in saved or content_digest(path) != saved[logical]:
            if Path(logical).name in staged:
                out.append(_staged_model_edit(root, logical, target))
                continue
            out.append(Finding(level, "model_edited_outside_target", "",
                f"model_edited_outside_target: {logical} changed since the last target promote; "
                "python -m flowguard target add " + Path(logical).stem +
                " moves the edit into the target (with git the current file is restored from HEAD; "
                "without git the old model is lost: write the change in the target and restore the old rules by hand)"))
    helpers = sorted(name for name in staged if name.startswith("_"))
    if helpers:
        baseline = target_helper_baseline(root)
        current_helpers = model_helper_digests(root)
        for name in helpers:
            logical = ".flowguard/models/" + name
            if baseline is None:
                unchanged = logical in current_helpers and current_helpers[logical] == content_digest(root / target.models[name])
            else:
                unchanged = baseline.get(logical) == current_helpers.get(logical)
            if not unchanged:
                out.append(_staged_model_edit(root, logical, target, unknown=baseline is None))
    return out


def _staged_model_edit(root, logical, target, *, unknown=False):
    import shlex
    absolute_root = Path(root).resolve()
    current_path = absolute_root / logical
    target_path = absolute_root / target.models[Path(logical).name]
    if unknown:
        message = (f"model_edited_outside_target: {current_path} has no captured helper baseline; "
                   f"the target copy ({target_path}) could overwrite an edit or recreate an intentional deletion. "
                   "Save both current and target intent, then drop and reopen the target to capture the current helper baseline")
    else:
        restore = shlex.join(['git', '-C', str(absolute_root), '--literal-pathspecs',
                              'checkout', '--', str(current_path)])
        message = (f"model_edited_outside_target: {current_path} was edited in place while the target holds a copy; "
                   f"promote would overwrite it. Move the edit into the target copy ({target_path}) "
                   f"and restore the current file (with Git: {restore}), or drop the edit")
    return Finding("error", "model_edited_outside_target", "", message)
