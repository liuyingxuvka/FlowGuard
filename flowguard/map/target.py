"""Manage one target and check its merged tree against real code and bound tests."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import re
import subprocess
from dataclasses import dataclass, field, replace

from .common import matches_any, content_digest, atomic_write_text
from .inventory import build_inventory
from .mapfile import MapError, component_graph, ignore_patterns, load_map, model_registry, read_model_contract, save_map, validate_map
from .targetfile import (TARGET_RELDIR, TARGET_SCHEMA, build_target_view, load_target, target_is_noop, target_node_changes,
                         validate_target)
from .tree import build_tree
from .proof import DEFAULT_JOBS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m flowguard target")
    parser.add_argument("--root", default=".")
    commands = parser.add_subparsers(dest="command")
    start = commands.add_parser("start", help="start one target draft")
    start.add_argument("goal")
    add = commands.add_parser("add", help="copy a current node into the target")
    add.add_argument("node")
    drop = commands.add_parser("drop", help="preview or delete the target")
    drop.add_argument("--yes", action="store_true")
    check = commands.add_parser("check", help="check actual code against the current tree with the target applied")
    promote = commands.add_parser("promote", help="replace the current tree with a clean target")
    for command in (check, promote):
        command.add_argument("--jobs", type=int, choices=range(1, 33), default=DEFAULT_JOBS, metavar="N", help="run 1-32 model subprocesses concurrently (default: min(4, CPUs))")
    for command in (start, add, drop, check, promote):
        command.add_argument("--root", default=argparse.SUPPRESS)
    return parser


def _save(root: Path, data: dict) -> None:
    (root / TARGET_RELDIR / "map.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _remove_readonly(function, path, info):
    if not isinstance(info[1], PermissionError):
        raise info[1]
    os.chmod(path, stat.S_IWRITE)
    function(path)


TODO_CODES = {"test_file_not_split","anchor_broken", "component_empty", "pattern_dead", "model_anchor_broken",
              "model_missing", "flow_step_broken", "file_unmapped", "dep_undeclared",
              "dep_unused", "layer_violation", "dependency_cycle"}
ERROR_CODES = {"port_changed_consumer_unhandled", "file_multi_owner", "dep_unknown", "flow_step_unknown", "model_contract", "model_unreadable",
               "model_id_duplicate", "model_component_unknown", "model_anchor_missing", "model_conformance_missing",
               "model_path_unsupported", "parent_unknown", "parent_cycle", "parent_import_mismatch",
               "anchor_outside_home", "duplicate_child_owner", "duplicate_owner", "flow_handoff_invalid", "owner_dropped", "entrypoint_owner", "component_parent_unknown", "component_parent_cycle",
               "component_parent_layer", "target_noop", "target_goal_untied", "port_changed_parent_missing"}


@dataclass(frozen=True)
class TargetFinding:
    node: str
    code: str
    message: str


@dataclass
class TargetReport:
    goal: str = ""
    changes: dict = field(default_factory=lambda: {"+": [], "~": [], "-": []})
    errors: list[TargetFinding] = field(default_factory=list)
    todos: list[TargetFinding] = field(default_factory=list)
    warnings: list[TargetFinding] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    bound_tests: bool = False
    goal_rules: str = ""
    old: int = 0               # problems of unchanged models over unchanged code (warnings, never blocking)
    port_lines: list[str] = field(default_factory=list)
    promise_lines: list[str] = field(default_factory=list)
    deleting: list = field(default_factory=list)   # file_unmapped TO-DOs of files a removed/re-filed component owned


def target_model_paths(root, data, target):
    """Current logical files replaced or explicitly removed by this target."""
    paths = {f".flowguard/models/{filename}" for filename in target.models}
    paths.update(entry.path for entry in model_registry(root, data).entries
                 if entry.id in target.remove["model"])
    return paths


def target_owns_file(path, target):
    return any(matches_any(path, component.get("files", []))
               for component in target.data.get("components", []))


_FIELD_CODES = {"pattern_dead": ("files",), "component_empty": ("files",), "test_missing": ("tests",),
                "dep_undeclared": ("depends_on", "layer"), "dep_unused": ("depends_on", "layer"),
                "layer_violation": ("depends_on", "layer"), "dependency_cycle": ("depends_on", "layer")}
_VOLATILE = {"status", "fingerprint", "_hint"}


def _changed_fields(current, planned) -> set[str]:
    """Field names whose values differ between a current component and its target entry."""
    keys = (set(current) | set(planned)) - _VOLATILE
    return {key for key in keys if current.get(key) != planned.get(key)}


def _subject_changed(finding, current, planned, layers_changed) -> bool:
    """Whether the target changes what this component finding is about (FG-317 table)."""
    changed = _changed_fields(current, planned)
    if finding.code in ("anchor_broken", "entrypoint_unmodeled"):
        anchors = [anchor for anchor in current.get("entrypoints", [])
                   if anchor in finding.message or (anchor.partition(":")[0] in finding.message
                                                    and repr(anchor.partition(":")[2]) in finding.message)
                   or finding.message == f"anchor file missing: {anchor.partition(':')[0]}"]
        if anchors:
            return any(anchor not in planned.get("entrypoints", []) for anchor in anchors)
        return "entrypoints" in changed
    if finding.code in _FIELD_CODES:
        return bool(changed & set(_FIELD_CODES[finding.code])) or (
            layers_changed and _FIELD_CODES[finding.code][-1] == "layer")
    return bool(changed)


def moving_to_target(findings, root, data, target):
    """Annotate only current breakage of what the target actually changes."""
    if target is None:
        return findings
    current_components = {c["id"]: c for c in data["components"]}
    planned_components = {c["id"]: c for c in target.data.get("components", [])}
    layers_changed = "layers" in target.data and target.data["layers"] != data.get("layers", [])
    flows = {f["id"] for f in target.data.get("flows", [])} | target.remove["flow"]
    models = target_model_paths(root, data, target)
    model_codes = {"model_anchor_broken", "model_test_broken", "model_anchor_missing",
                   "model_conformance_missing", "model_unreadable", "model_contract"}
    result = []
    for finding in findings:
        planned = False
        if finding.level in {"error", "warn"}:
            flow = re.match(r"flow ([^ :]+):", finding.message)
            model = re.match(r"(\.flowguard/models/[^:]+\.py):", finding.message)
            if flow:
                planned = (finding.code in {"flow_step_broken", "flow_step_unknown", "model_missing"}
                           and flow.group(1) in flows)
            elif model or finding.code in model_codes or (finding.code == "model_missing" and finding.message.startswith("model file ")):
                planned = bool(model and finding.code in model_codes and model.group(1) in models)
            elif finding.code == "file_unmapped":
                planned = target_owns_file(finding.message.split(" has no owning component", 1)[0], target)
            elif finding.component in target.remove["component"]:
                planned = True
            elif finding.component in planned_components:
                planned = _subject_changed(finding, current_components.get(finding.component, {}),
                                           planned_components[finding.component], layers_changed)
        result.append(replace(finding, level="info", message="moving to target: " + finding.message)
                      if planned else finding)
    return result


def _selected_models(root, current, target, view, inv, tree):
    """Select the target and its transitive importers in both tree snapshots."""
    old = build_tree(root, current, inv)
    links = {}
    for source_tree in (old, tree):
        for imports in (source_tree.imports, source_tree.local_imports):
            for source, destinations in imports.items():
                for destination in destinations:
                    links.setdefault(destination, set()).add(source)
    reached = {f".flowguard/models/{filename}" for filename in target.models}
    reached.update(node.path for node in old.nodes.values() if node.id in target.remove["model"])
    pending = list(reached)
    while pending:
        for adjacent in links.get(pending.pop(), set()) - reached:
            reached.add(adjacent)
            pending.append(adjacent)
    for _, _, chosen, _ in _target_ports(root, old, target, tree):
        reached.update(tree.nodes[mid].path for mid, _ in chosen)
    return sorted(node.id for node in tree.nodes.values() if node.path in reached)


def _target_ports(root, old, target, tree):
    from .port import port_selection
    ports = {mid: node.contract["port"] for mid, node in tree.nodes.items() if "port" in node.contract}
    paths = {f".flowguard/models/{filename}" for filename in target.models}
    for mid, node in sorted(tree.nodes.items()):
        if node.path not in paths or mid not in ports:
            continue
        previous = old.nodes.get(mid)
        before = previous.contract.get("port") if previous else None
        chosen, line, description = port_selection(mid, before, ports[mid], tree, ports, new_model=previous is None)
        yield mid, line, chosen, (before, ports[mid], description)


def _finding_node(finding, tree):
    flow = re.search(r"\bflow ([^ :]+):", finding.message)
    if flow:
        return "flow " + flow.group(1)
    model = re.match(r"(\.flowguard/models/[^:]+\.py):", finding.message)
    if model:
        node = next((n for n in tree.nodes.values() if n.path == model.group(1)), None)
        return "model " + (node.id if node else Path(model.group(1)).stem)
    return "component " + finding.component if finding.component else "target"


def _issue_key(node, code, message, tree):
    """A code/test reference, not just a model ID or a generic message prefix."""
    family = {"model_anchor_broken": "anchor", "implemented_by": "anchor", "placeholder_anchor": "anchor", "model_test_broken": "test",
              "tested_by_failed": "test", "tested_by_misses_anchor": "test"}.get(code, code)
    contract = tree.nodes[node[6:]].contract if node.startswith("model ") and node[6:] in tree.nodes else {}
    if family == "anchor":
        anchors = {**contract.get("IMPLEMENTED_BY", {}), **{f"USES {name}": anchor for name, anchor in contract.get("USES", {}).items()}}
        for block, anchor in anchors.items():
            if f"{block} ->" in message or anchor in message:
                return node, family, anchor
    if family == "test":
        for invariant, anchors in contract.get("TESTED_BY", {}).items():
            for anchor in anchors:
                path, _, symbol = anchor.partition(":")
                if anchor in message or (f"{invariant} ->" in message and path in message
                                        and ("symbol '" not in message or repr(symbol) in message)):
                    return node, family, anchor
    return node, family, message


def check_target(root: Path, *, models: bool = True, tests: bool = False, impact=None, jobs: int = 1) -> TargetReport:
    """Fresh native facts and proofs; all engine project-cache writes are disabled."""
    from .check import run_check
    from .lint import architecture_findings, architecture_variants, dropped_owner_findings

    root = root.resolve()
    current = load_map(root)
    report = TargetReport(bound_tests=tests)
    try:
        target = load_target(root)
    except MapError as exc:
        report.errors.append(TargetFinding("target", "target_invalid", str(exc)))
        return report
    if target is None:
        raise MapError('no target; start one with python -m flowguard target start "<goal>"')
    report.goal = target.goal if isinstance(target.goal, str) else ""
    problems = validate_target(root, current, target)
    if problems:
        report.errors.extend(TargetFinding("target", item.code, item.message) for item in problems)
        return report
    report.changes = target_node_changes(root, current, target)
    view = build_target_view(root, current, target)
    inv = build_inventory(root, ignore_patterns(view.data), write_cache=False, import_roots=tuple(view.data.get("import_roots", ())))
    tree = build_tree(root, view.data, inv, view=view)
    seen = set()

    def add(level, node, code, message):
        key = (level, *_issue_key(node, code, message, tree))
        if key not in seen:
            seen.add(key)
            getattr(report, level).append(TargetFinding(node, code, message))

    from .facets import goal_rules_line

    report.goal_rules, goal, promises = goal_rules_line(root, current, target, view)
    from .facets import target_promise_notes, promise_records
    records = (promise_records(root,current), promise_records(root,view.data,view))
    report.promise_lines, removed_promises = target_promise_notes(root,current,target,view,records=records)
    for finding in removed_promises:
        add('warnings','model '+finding['component'],finding['code'],finding['message'])
    if target_is_noop(root, current, target):
        report.errors.append(TargetFinding("target", "target_noop", "the target changes nothing yet: edit .flowguard/target/ "
                                           "(components, models or remove) or drop it with python -m flowguard target drop --yes"))
    elif promises and not goal:
        field_name, item = promises[0]
        report.errors.append(TargetFinding("target", "target_goal_untied", f"the target changes a promise ({field_name}: {item}) "
                                           "but adds or changes no model rule or known-bad; add the rule that holds the goal to a "
                                           "target model (python -m flowguard target add <model> or python -m flowguard template "
                                           "behaviour --write .)"))
    replaced = {c["id"] for c in target.data.get("components", [])}
    # run_check reports duplicate_owner (with accepted debts) once.
    for finding in [*run_check(root, view.data, inv, view=view), *dropped_owner_findings(current, view.data, target)]:
        if finding.code in {"draft", "stale", "fingerprint_migrate"} and finding.component in replaced:
            continue
        if finding.level == "info":
            continue
        if finding.code in {"test_missing", "model_test_broken"} and not tests:
            add("warnings", _finding_node(finding, tree), finding.code, finding.message)
            continue
        placeholder = "placeholder anchor " in finding.message
        level = "errors" if placeholder else "todos" if finding.code in TODO_CODES else "errors" if finding.level == "error" or finding.code in ERROR_CODES else "warnings"
        add(level, _finding_node(finding, tree), finding.code, finding.message)
        if finding.code == "file_unmapped" and level == "todos" and _left_by_target(finding, current, target, inv):
            report.deleting.append(report.todos[-1])
    if view.data.get("accepted_debts"):
        from .lint import run_lint

        before = {f.message for f in run_lint(root, current, inv, write_cache=False) if f.code == "debt_stale"}
        for finding in run_lint(root, view.data, inv, view=view):
            if finding.code == "debt_stale" and finding.message not in before:
                add("warnings", "component " + finding.component if finding.component else "target", "debt_stale",
                    finding.message + " (remove the debt in the target's accepted_debts)")
    graph = component_graph(view.data, inv)
    for name, changed, edges in architecture_variants(view.data, graph):
        if not any(f.level == "error" for f in architecture_findings(changed, edges)):
            add("errors", "target", "known_bad_passed", f"generated known-bad variant {name!r} passed: architecture rules do not catch it")
    from .port import escalation_set, port_delta
    old_tree = build_tree(root, current, inv)
    from .facets import moved_model_rules
    from .testtree import test_file_not_split_findings
    for finding in test_file_not_split_findings(root,current,inv,old_tree,tree,moved_model_rules(root,current,target,view,records=records)):
        add('todos','test '+finding.component,finding.code,finding.message)
    ports = {mid: node.contract["port"] for mid, node in tree.nodes.items() if "port" in node.contract}
    changed_paths = target_model_paths(root, current, target)
    target_ids = {mid for mid, node in tree.nodes.items() if node.path in changed_paths}
    escalated = {}
    for mid, line, chosen, (before, after, description) in _target_ports(root, old_tree, target, tree):
        for receiver, reason in chosen:
            if receiver not in target_ids:
                escalated.setdefault(receiver, {})[mid] = reason
        if '(no model consumer)' in line:
            from .discover import discover_inventory
            from .port import code_callers
            from .mapfile import component_files
            scope = {path for comp in view.data['components'] if comp['id'] in tree.nodes[mid].components for path in component_files(comp, inv)}
            callers = code_callers(discover_inventory(root, inv, data=view.data, write_cache=False), tree.nodes[mid], scope)
            line = line.replace('(no model consumer)', '(no model consumer; code callers: ' + (', '.join(callers) or '-') + ')')
        report.port_lines.append(line)
        if before is None or port_delta(before, after)['out']:
            for parent, reason in escalation_set(mid, tree, ports, state=False):
                if reason == "parent" and parent not in target_ids:
                    old_values = {v for values in (before.outputs or {}).values() for v in values} if before else set()
                    values = [v for items in (after.outputs or {}).values() for v in items if v not in old_values]
                    value = str(values[0]) if values else "the changed output"
                    add("errors", "model " + mid, "port_changed_parent_missing",
                        f"the target changes the port of {mid} ({description}) but not its parent {parent}; python -m flowguard target add {parent}, then make {parent} receive '{value}' (a CHECK step that takes it; with a full-form HANDOFF entry, also map it there)")
    if not models:
        return report
    from .proof import run_models

    selected = _selected_models(root, current, target, view, inv, tree)
    if impact is not None:
        selected = sorted(set(selected) | (set(impact.model_ids) & set(tree.nodes)))
    # [] means "all" to model execution; an empty target selection means none.
    results = run_models(root, selected, tests=tests, view=view, inv=inv, jobs=jobs) if selected else []
    untouched, old = _unchanged_models(root, current, target, inv, tree, selected, changed_paths=changed_paths)
    old -= set(escalated)
    for result in results:
        node = "model " + result.model
        problems = list(result.problems)
        if result.status != "pass" and not problems:
            problems.append(f"model ended with status {result.status}")
        for problem in problems:
            unmatched = re.match(r"^handoff_output_unhandled: (\S+) emits (\S+)='([^']*)'", problem)
            if unmatched and unmatched.group(1) in escalated.get(result.model, {}):
                producer, key, value = unmatched.groups()
                missing_parent = (escalated[result.model][producer] == "parent" and any(
                    finding.code == "port_changed_parent_missing" and finding.node == "model " + producer
                    for finding in report.errors))
                if not missing_parent:
                    add("errors", node, "port_changed_consumer_unhandled",
                        f"{producer} emits {key}='{value}'; {result.model} never receives it and is not in the target; "
                        f"python -m flowguard target add {result.model}, then make {result.model} receive '{value}'")
                continue
            code = ("placeholder_anchor" if problem.startswith("placeholder anchor ") else
                    "implemented_by" if problem.startswith(("IMPLEMENTED_BY ", "USES ")) else
                    "tested_by_misses_anchor" if problem.startswith("tested_by_misses_anchor ") else
                    "tested_by_failed" if problem.startswith("tested_by_failed ") else
                    "uncovered_invariant" if problem.startswith("uncovered_invariant: ") else "model_proof")
            if result.model in old:
                text = problem if code in ("uncovered_invariant", "tested_by_failed", "tested_by_misses_anchor") else f"{code}: {problem}"
                add("warnings", node, "old_finding", f"{text} {OLD_NOTE}")
                report.old += 1
                continue
            if result.model in untouched:
                problem += (f" (model unchanged by the target; if python -m flowguard map models {result.model} "
                            "failed before your edit too, fix it first)")
            add("todos" if problem.split(" (model unchanged by the target;")[0] in result.code_gaps else "errors",
                node, code, problem)
        for warning in result.warnings:
            add("warnings", node, "invariant_untested" if warning.startswith("invariant_untested: ") else "model_warning", warning)
    report.gaps = gap_lines(root, target, view, report, results, goal=goal)
    for line in report.gaps:
        if line.startswith("NO GAP "):
            report.warnings.append(TargetFinding("model " + line.split()[2].rstrip(":"), "no_gap", line))
    return report


def gap_lines(root, target, view, report, results, *, goal=None):
    """Describe each target model's rule delta against genuine native code gaps."""
    from .facets import target_goal_rules
    changes = {line.split(": ", 1)[0][6:]: line.split(": ", 1)[1]
               for line in (target_goal_rules(root, target, view) if goal is None else goal)}
    by_model = {result.model: list(result.code_gaps) for result in results}
    output = []
    for entry in model_registry(root, view.data, view=view).entries:
        if entry.kind != "contract" or Path(entry.path).name not in target.models:
            continue
        mid = entry.id
        from .mapfile import process_model_reason, read_model_contract, resolve_model_path
        contract = read_model_contract(resolve_model_path(root, entry.path, view=view))
        if process_model_reason(view.data, contract):
            output.append(f"process model: {mid} (no code yet; no gap expected)")
            continue
        delta = changes.get(mid, "")
        items = [item for item in delta.split(", ") if not item.endswith("(known-bad)")]
        rules = [item for item in items if item.startswith(("+", "~"))]
        moved = [item for item in items if item.startswith(">")]
        gaps = by_model.get(mid, [])[:]
        for finding in report.todos:
            if finding.node == "model " + mid and finding.code == "model_anchor_broken" and not gaps:
                gaps.append(finding.message)
        first = gaps[0].splitlines()[0] if gaps else ""
        if rules:
            names = " ".join(rules)
            if gaps:
                output.append(f"EXPECTED GAP {mid}: {len(gaps)} code gap(s) for {names}; first: {first}")
            else:
                output.append(f"NO GAP {mid}: the current code already satisfies {names}; if this rule records what the code already does, write no code for it and say so in the commit message; otherwise conformance() does not drive the real entry (check its call shape)")
        elif moved:
            donors = {}
            for item in moved:
                donor = item.partition("(from ")[2].rstrip(")")
                donors[donor] = donors.get(donor, 0) + 1
            detail = ", ".join(f"{count} from {donor}" for donor, count in sorted(donors.items()))
            output.append(f"moved rules only: {mid} ({detail}; no gap expected)")
        else:
            detail = f"{len(gaps)} code gap(s) are TO-DO; first: {first}" if gaps else "no gap expected"
            output.append(f"no rule change: {mid} (no new or changed rule; {detail})")
    return output


OLD_NOTE = ("(already in the current tree; the target does not change this model or its code; "
            "fix it in its own change or target)")


def _unchanged_models(root, current, target, inv, tree, selected, *, changed_paths=None):
    """(models the target does not change, the subset whose anchored code is also unchanged).

    Unchanged: neither the model file nor a model file it imports is replaced, added or removed by the target.
    Old: additionally every IMPLEMENTED_BY anchor lies in a component that is not stale."""
    from .mapfile import is_stale, owner_index

    changed = target_model_paths(root, current, target) if changed_paths is None else changed_paths
    owner, _ = owner_index(current, inv)
    components = {c["id"]: c for c in current["components"]}
    current_tree = build_tree(root, current, inv)
    untouched, old = set(), set()
    for mid in selected:
        node = tree.nodes.get(mid)
        if node is None or node.path in changed or any(
                source.imports.get(node.path, set()) & changed or source.local_imports.get(node.path, set()) & changed
                for source in (tree, current_tree)):
            continue
        untouched.add(mid)
        anchors = node.contract.get("IMPLEMENTED_BY", {}).values()
        owners = [owner.get(anchor.partition(":")[0]) for anchor in anchors]
        if owners and all(cid in components and not is_stale(root, components[cid], inv) for cid in owners):
            old.add(mid)
    return untouched, old


def _left_by_target(finding, current, target, inv):
    """The unowned file belonged to a component the target removes or whose files the target changes."""
    from .mapfile import owner_index

    path = finding.message.split(" has no owning component", 1)[0]
    owner = owner_index(current, inv)[0].get(path)
    planned = {c["id"]: c for c in target.data.get("components", [])}
    before = {c["id"]: c for c in current["components"]}
    return owner in target.remove["component"] or (
        owner in planned and planned[owner].get("files") != before.get(owner, {}).get("files"))


def _todo_next(code, deleting=False):
    if code in {"model_test_broken", "tested_by_failed", "tested_by_misses_anchor", "test_missing"}:
        return "write the test the target binds"
    if code == "file_unmapped" and deleting:
        return "delete the file, or give it an owner in the target"
    if code in {"component_empty", "pattern_dead", "file_unmapped", "model_missing"}:
        return "create the file, or change the target's files"
    if code in {"dep_undeclared", "dep_unused", "layer_violation", "dependency_cycle"}:
        return "make the imports match the target's depends_on"
    if code in {"anchor_broken", "model_anchor_broken", "implemented_by", "flow_step_broken"}:
        return "write the code the target names"
    return "change the code until it replays the target model"


def render_target_report(report: TargetReport) -> str:
    changes = report.changes
    lines = [f'target: "{report.goal}" (+{len(changes["+"])} ~{len(changes["~"])} -{len(changes["-"])} nodes)']
    if report.goal_rules:
        lines.append(report.goal_rules)
    lines.extend(report.gaps)
    lines.extend(report.promise_lines)
    lines.extend(report.port_lines)
    for label, findings in (("ERROR", report.errors), ("TO-DO", report.todos), ("WARN ", report.warnings)):
        for finding in findings:
            if finding.code == "no_gap":
                continue
            suffix = f" ({_todo_next(finding.code, finding in report.deleting)})" if label == "TO-DO" else ""
            message = finding.message.replace("\n", "\n  ")
            lines.append(f"{label} {finding.node}: {finding.code}: {message}{suffix}")
    lines.append(f"target check: {len(report.errors)} error(s), {len(report.todos)} to-do, {len(report.warnings)} warning(s)"
                 + (f" ({report.old} old)" if report.old else ""))
    lines.append("next: " + ("fix the target design (ERROR lines) in .flowguard/target/ first" if report.errors else
                            "write the code and tests until no TO-DO remains, then python -m flowguard target promote" if report.todos else
                            "python -m flowguard target promote"))
    if not report.bound_tests:
        lines.append("bound tests: not run here; target promote runs them once")
    return "\n".join(lines)


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _promotion_inputs(root, data):
    """Operation-local byte identities, never stored as a check result or cache."""
    inv = build_inventory(root, ignore_patterns(data), with_bodies=False, write_cache=False, import_roots=tuple(data.get("import_roots", ())))
    paths = set(inv.files) | {".flowguard/map.json"}
    paths.update(p.relative_to(root).as_posix() for p in (root / ".flowguard/models").glob("*.py") if p.is_file())
    paths.update(p.relative_to(root).as_posix() for p in (root / TARGET_RELDIR).rglob("*") if p.is_file())
    return {path: _file_hash(root / path) for path in sorted(paths)}


def promote_target(root: Path, *, jobs: int = 1) -> int:
    """Check once, revalidate the checked bytes, then apply a prepared write plan."""
    root = root.resolve()
    try:
        if not (root / TARGET_RELDIR).exists():
            raise MapError('no target; start one with python -m flowguard target start "<goal>"')
        current = load_map(root)
        inputs = _promotion_inputs(root, current)
        current = load_map(root)
        try:
            target = load_target(root)
        except MapError:
            target = None
        prepared = target is not None and not validate_target(root, current, target)
        if prepared:
            view = build_target_view(root, current, target)
            merged = view.data
            model_bytes = {name: (root / path).read_bytes() for name, path in target.models.items()}
            staged_matches = all(hashlib.sha256(content).hexdigest() == inputs.get(target.models[name])
                                 for name, content in model_bytes.items())
            deleted = [entry.path for entry in model_registry(root, current).entries
                       if entry.id in target.remove["model"] and view.resolve(entry.path) is None]
            changes = target_node_changes(root, current, target)
            drafts = sorted(c["id"] for c in target.data.get("components", []))
            reread = _re_read(root, current, target, view)
        # The same full proof and TESTED_BY path as `target check`, exactly once.
        from .impact import changed_files, compute_impact, test_groups
        inventory = build_inventory(root, ignore_patterns(current), write_cache=False, import_roots=tuple(current.get('import_roots', ())))
        impact = compute_impact(root, current, inventory, changed_files(root, 'HEAD', data=current, inv=inventory), base='HEAD')
        report = check_target(root, tests=True, impact=impact, jobs=jobs)
        if not report.errors and not report.todos:
            # Bound nodes were already checked, with anchor reach, by run_models.
            # Run the additional selected test nodes once without rerunning those bindings.
            tested = set()
            if prepared:
                from .testtree import resolve_test_anchor
                merged_tree = build_tree(root, merged, inventory, view=view)
                combined = set(_selected_models(root,current,target,view,inventory,merged_tree)) | set(impact.model_ids)
                for mid in combined & set(merged_tree.nodes):
                    for anchors in merged_tree.nodes[mid].contract.get('TESTED_BY', {}).values():
                        for anchor in anchors:
                            path, _, symbol = anchor.partition(':')
                            found = resolve_test_anchor(root/path,symbol)
                            if found:
                                suffix = '['+symbol.split('[',1)[1] if '[' in symbol else ''
                                tested.add(path+'::'+found.replace('.', '::')+suffix)
            groups, missing = test_groups(impact)
            import shlex
            for command, nodes in groups.items():
                remaining = []
                for node in nodes:
                    if '::' in node:
                        if node not in tested and node.split('[',1)[0] not in tested: remaining.append(node)
                    elif node.endswith('.py'):
                        from .testtree import test_functions
                        remaining.extend(node+'::'+name.replace('.', '::') for name in test_functions((root/node).read_text(encoding='utf-8'))
                                         if node+'::'+name.replace('.', '::') not in tested)
                    else: remaining.append(node)
                if not remaining: continue
                argv=shlex.split(command)
                if argv and argv[0]=='python': argv[0]=sys.executable
                if 'pytest' in argv: argv += ['-p','no:cacheprovider']
                for offset in range(0,len(remaining),50):
                    result=subprocess.run(argv+remaining[offset:offset+50],cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'))
                    if result.returncode:
                        report.errors.append(TargetFinding('target','selected_tests_failed','function-selected tests failed: '+' '.join(remaining[offset:offset+50])+'\n'+(result.stdout+result.stderr)[-5000:]))
            if missing:
                report.errors.append(TargetFinding('target','selected_tests_unavailable',', '.join(missing)))
        if report.errors or report.todos:
            print(render_target_report(report))
            print(f"promote refused: {len(report.errors)} error(s), {len(report.todos)} to-do")
            return 1
        if not prepared or not staged_matches or _promotion_inputs(root, current) != inputs:
            print("promote refused: checked inputs changed; run python -m flowguard target check")
            return 1
        problems = validate_map(merged)
        if problems:
            print("promote refused: " + "; ".join(problems))
            return 1
        backup = root / TARGET_RELDIR / ".replaced"
        for rel in [".flowguard/map.json", *[".flowguard/models/" + name for name in model_bytes], *deleted]:
            source = root / rel
            if source.is_file():
                destination = backup / Path(rel).relative_to(".flowguard")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        if model_bytes:
            (root / ".flowguard/models").mkdir(parents=True, exist_ok=True)
        for name, content in model_bytes.items():
            destination = root / ".flowguard/models" / name
            temporary = destination.with_name(destination.name + ".tmp")
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        for path in deleted:
            (root / path).unlink()
        temporary = root / ".flowguard/map.json.tmp"
        temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, root / ".flowguard/map.json")
        directory = root / TARGET_RELDIR
        for child in directory.iterdir():
            if child == backup:
                continue
            if child.is_dir():
                shutil.rmtree(child, onerror=_remove_readonly)
            else:
                child.unlink()
        if backup.exists():
            shutil.rmtree(backup, onerror=_remove_readonly)
        directory.rmdir()
        from .mapfile import is_stale
        inv = build_inventory(root, ignore_patterns(merged), write_cache=False, import_roots=tuple(merged.get("import_roots", ())))
        drafts = sorted(set(drafts) | {c["id"] for c in merged["components"] if is_stale(root, c, inv)})
        summaries = []
        for kind, label in (("component", "components"), ("model", "models"), ("flow", "flows")):
            items = [symbol + entry.split(":", 1)[1] for symbol in ("+", "~", "-")
                     for entry in changes[symbol] if entry.startswith(kind + ":")]
            summaries.append(label + " " + (" ".join(items) or "-"))
        print(f'promoted "{target.goal}": ' + "; ".join(summaries))
        for line in reread:
            print(line)
        if drafts:
            print("next: python -m flowguard map confirm " + " ".join(drafts))
        print("next: commit (the code, .flowguard/models/ and .flowguard/map.json together)")
        return 0
    except OSError as exc:
        print(f"promote stopped: {exc}; the target is intact in .flowguard/target/ and the replaced files are in .flowguard/target/.replaced/; copy them back into .flowguard/ to restore, then run python -m flowguard target promote again", file=sys.stderr)
        if _git_head(root):
            print("restore with: git checkout -- .flowguard && git clean -fd .flowguard", file=sys.stderr)
        return 2
    except MapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _re_read(root, current, target, view, limit=5):
    """Drift hints for promotion: re-parented models, flows crossing changed components, tests losing their binding."""
    from .mapfile import flow_step_parts

    inv = build_inventory(root, ignore_patterns(view.data), with_bodies=False, write_cache=False, import_roots=tuple(view.data.get("import_roots", ())))
    old, new = build_tree(root, current, inv), build_tree(root, view.data, inv, view=view)
    groups = [[f"re-read: model {mid}: its parent changed from {old.nodes[mid].parent} to {node.parent}; check its purpose"
               for mid, node in sorted(new.nodes.items()) if mid in old.nodes and old.nodes[mid].parent != node.parent]]
    changed = {c["id"] for c in target.data.get("components", [])} | target.remove["component"]
    flows = []
    for flow in view.data.get("flows", []):
        crossed = [part for part in dict.fromkeys(flow_step_parts(step)[0] for step in flow.get("steps", [])) if part in changed]
        if crossed:
            flows.append(f"re-read: flow {flow['id']}: it crosses changed component {crossed[0]}; check its steps and model")
    groups.append(flows)

    def bound(tree):
        return {anchor for node in tree.nodes.values() for anchors in node.contract.get("TESTED_BY", {}).values()
                for anchor in anchors}
    groups.append([f"re-read: test {anchor}: no longer bound by any TESTED_BY; bind it or delete it"
                   for anchor in sorted(bound(old) - bound(new))])
    lines = []
    for group in groups:
        lines += group[:limit] + ([f"re-read: +{len(group) - limit} more"] if len(group) > limit else [])
    return lines


def _git(root, *arguments):
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], capture_output=True)
    except OSError:
        return None


def _git_head(root):
    result = _git(root, "rev-parse", "--verify", "HEAD")
    return result is not None and result.returncode == 0


def _add(root: Path, data: dict, target, requested: str) -> None:
    registry = model_registry(root, data)
    components = {c["id"]: c for c in data["components"]}
    models = {entry.id: entry for entry in registry.entries if entry.kind == "contract"}
    flows = {flow["id"]: flow for flow in data.get("flows", [])}
    kind, separator, name = requested.partition(":")
    if not separator:
        name = requested
        if name in components and name in models:
            raise MapError(f"{name!r} is both a component and a model; use component:{name} or model:{name}")
        kind = "component" if name in components else "model" if name in models else ""
    choices = {"component": components, "model": models, "flow": flows}
    if kind not in choices or name not in choices[kind]:
        raise MapError(f"unknown node {requested!r}; components: {', '.join(sorted(components)[:10])}; "
                       f"models: {', '.join(sorted(models)[:10])}")
    if kind == "model":
        entry = models[name]
        destination = root / TARGET_RELDIR / "models" / Path(entry.path).name
        if destination.exists():
            raise MapError(f"model {name} is already in the target")
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(root / entry.path, destination)
        print(f"added model {name}: {destination.relative_to(root).as_posix()}")
        contract = read_model_contract(destination)
        if _git_head(root):
            tracked = _git(root, "ls-files", "--error-unmatch", entry.path)
            if tracked.returncode:
                print(f"note: {entry.path} is not tracked by git; it stays the current model until target promote (commit .flowguard/ so git also holds it)")
            else:
                dirty = _git(root, "diff", "--quiet", "HEAD", "--", entry.path).returncode == 1
                digest = content_digest(root / entry.path)
                if dirty and digest != data.get("model_digests", {}).get(entry.path):
                    original = _git(root, "show", "HEAD:" + entry.path)
                    if original.returncode:
                        raise MapError(f"cannot read HEAD model {entry.path}")
                    (root / entry.path).write_bytes(original.stdout)
                    print(f"moved uncommitted edits of {entry.path} into the target; the current model is HEAD again")
        for helper in contract["imports"]:
            if helper.startswith("_") and (root / ".flowguard/models" / f"{helper}.py").is_file():
                print(f"note: it imports {helper}; copy .flowguard/models/{helper}.py into "
                      ".flowguard/target/models/ only if the target changes it")
        tree = build_tree(root, data, build_inventory(root, ignore_patterns(data), import_roots=tuple(data.get("import_roots", ()))))
        importers = sorted(tree.importers(entry.path) - {name})
        if importers:
            print("note: target check also runs these models against the target version: " + ", ".join(importers))
    else:
        plural = "components" if kind == "component" else "flows"
        if any(item["id"] == name for item in target.data.get(plural, [])):
            raise MapError(f"{kind} {name} is already in the target")
        item = copy.deepcopy(choices[kind][name])
        if kind == "component":
            for key in ("status", "fingerprint", "_hint"):
                item.pop(key, None)
        target.data.setdefault(plural, []).append(item)
        _save(root, target.data)
        print(f"added {kind} {name} to .flowguard/target/map.json")


def start_target(root: Path, goal: str) -> int:
    """Create the one target draft; refuse a second target or an empty goal."""
    target = load_target(root)
    if target is not None:
        raise MapError(f'a target already exists: "{target.goal}"; promote it (python -m flowguard target promote) '
                       'or drop it (python -m flowguard target drop --yes)')
    if not goal.strip():
        raise MapError("the goal must be a nonempty sentence")
    directory = root / TARGET_RELDIR
    directory.mkdir(parents=True)
    (directory / "models").mkdir()
    _save(root, dict(schema=TARGET_SCHEMA, goal=goal, components=[], flows=[], remove=[]))
    print(f'target started: "{goal}"')
    if not _git_head(root):
        print("note: no git here; the current model stays in .flowguard/models/ until target promote")
    print("next: python -m flowguard target add <component-or-model-id>, edit the files under "
          ".flowguard/target/, then python -m flowguard target check")
    return 0


def _require_target(root: Path):
    target = load_target(root)
    if target is None:
        raise MapError('no target; start one with python -m flowguard target start "<goal>"')
    return target


def add_to_target(root: Path, node_id: str) -> int:
    """Copy one current component or model into a valid target."""
    data = load_map(root)
    target = _require_target(root)
    problems = validate_target(root, data, target)
    if problems:
        raise MapError("; ".join(f"{issue.code}: {issue.message}" for issue in problems))
    _add(root, data, target, node_id)
    from .check import model_edit_findings
    for finding in model_edit_findings(root, data, "warn"):
        print("WARN " + finding.message)
    return 0


def drop_target(root: Path, *, yes: bool) -> int:
    """Preview the target deletion, or delete .flowguard/target/ with yes."""
    target = _require_target(root)
    directory = root / TARGET_RELDIR
    if not yes:
        count = sum(path.is_file() for path in directory.rglob("*"))
        print(f'would delete .flowguard/target/ ("{target.goal}", {count} file(s)); re-run with --yes')
        return 1
    shutil.rmtree(directory, onerror=_remove_readonly)
    print(f'dropped target "{target.goal}"')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    root = Path(args.root).resolve()
    try:
        if args.command == "promote":
            return promote_target(root, jobs=args.jobs)
        if args.command == "check":
            report = check_target(root, jobs=args.jobs)
            print(render_target_report(report))
            return 1 if report.errors else 3 if report.todos else 0
        load_map(root)
        if args.command == "start":
            return start_target(root, args.goal)
        if args.command == "drop":
            return drop_target(root, yes=args.yes)
        return add_to_target(root, args.node)
    except (MapError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
