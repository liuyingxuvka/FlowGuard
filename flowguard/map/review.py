"""Architecture review view (``read --review``): per-component metrics, strengths, defects and a
ranked list of what to optimise next, each step with its recipe.

Static and read-only: it re-arranges what ``map lint``, the dependency graph, the coverage
counts and the static five facets already compute; it imports and runs no model.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .facets import component_facets, model_facets
from .inventory import Inventory
from .lint import run_lint
from .mapfile import component_files, component_graph
from .tree import build_tree
from .views import _layer_order, _read_facts

ARCHITECTURE = "references/architecture_review.md ({code})"
TEMPLATE = "python -m flowguard template behaviour --write ."
# code (or candidate kind) -> (weight, action word, recipe or command)
REVIEW_ACTIONS = {
    "error": (1000, "fix", ARCHITECTURE),
    "hub": (500, "split", "references/tree_operations.md#Add or split a component, as a target"),
    "entrypoint_unmodeled": (300, "model", TEMPLATE),
    "model_writer_unbound": (300, "model", TEMPLATE),
    "foreign_state_write": (300, "move", ARCHITECTURE),
    "private_cross_component_use": (300, "move", ARCHITECTURE),
    "unexplained": (200, "explain", "python -m flowguard read --component {component}"),
    "unmodeled_owner": (150, "model", TEMPLATE),
    "warn": (100, "{code}", ARCHITECTURE),
    "flow_without_model": (80, "model flow", "references/map_format.md"),
    "unbound_models": (60, "bind tests", "references/model_recipes.md#Run the bound tests"),
    "never_imported": (50, "delete or list", "references/tree_operations.md#Remove or merge a node"),
}
HUB_USERS, HUB_USES, HUB_LOC, HUB_DUTIES = 3, 3, 1500, 7
SHOWN_STEPS = 5


def _accepted(finding) -> bool:
    return "(accepted debt:" in finding.message


def _size(message: str) -> int:
    numbers = [int(value) for value in re.findall(r"\b(\d+)\b", message)]
    return max(numbers, default=1)


def _step(kind, component, detail, size, *, code=""):
    weight, verb, recipe = REVIEW_ACTIONS[kind]
    verb, recipe = verb.format(code=code), recipe.format(code=code, component=component)
    subject = f"{verb} {code} {component}" if kind == "error" else f"{verb} {component}"
    return weight, size, component, f"{subject}: {detail}; {recipe}"


def _strengths(findings, data, coverage_total, model_data) -> list[str]:
    codes = {finding.code for finding in findings}
    flows = data.get("flows", [])
    entries, writers = coverage_total
    claims = [
        ("no dependency cycles", "dependency_cycle" not in codes),
        ("no layer violations", "layer_violation" not in codes),
        ("one owner per responsibility, state and side effect", "duplicate_owner" not in codes),
        ("every flow has a model", bool(flows) and all(flow.get("model") for flow in flows)),
        ("every entrypoint explained", entries[1] > 0 and entries[0] == entries[1]),
        ("every state writer explained", writers[1] > 0 and writers[0] == writers[1]),
        ("every model shows its known-bad variants",
         bool(model_data) and all(facets.known_bad_count is not None for facets in model_data.values())),
        ("no accepted debts", not data.get("accepted_debts")),
    ]
    return [text for text, holds in claims if holds]


def _defect_lines(findings) -> list[str]:
    grouped = defaultdict(list)
    for finding in findings:
        if finding.level in ("error", "warn"):
            grouped[(finding.level, finding.code)].append(finding)
    lines = []
    for (level, code), items in sorted(grouped.items(), key=lambda pair: (pair[0][0] != "error", -len(pair[1]), pair[0][1])):
        first = items[0]
        message = first.message if len(first.message) <= 100 else first.message[:99] + "…"
        lines.append(f"  {'ERROR' if level == 'error' else 'WARN '} {code} x{len(items)}: {first.component}: {message}")
    notes = sum(finding.level == "info" for finding in findings)
    if notes:
        lines.append(f"  info: {notes} notes (python -m flowguard map lint)")
    return lines or ["  none"]


def _candidates(findings, data, inv, graph, tree, coverage, rows):
    steps = []
    for finding in findings:
        if _accepted(finding):
            continue
        detail = finding.message if len(finding.message) <= 100 else finding.message[:99] + "…"
        if finding.level == "error":
            steps.append(_step("error", finding.component, detail, 1, code=finding.code))
        elif finding.level == "warn" and finding.code in REVIEW_ACTIONS:
            steps.append(_step(finding.code, finding.component, f"{finding.code}: {detail}", 1, code=finding.code))
        elif finding.level == "warn":
            steps.append(_step("warn", finding.component, detail, _size(finding.message), code=finding.code))
        elif finding.code == "never_imported":
            steps.append(_step("never_imported", finding.component, detail, 1))
    for component in data["components"]:
        cid = component["id"]
        row = rows[cid]
        if row["used_by"] >= HUB_USERS and row["uses"] >= HUB_USES and (row["loc"] >= HUB_LOC or row["duties"] >= HUB_DUTIES):
            steps.append(_step("hub", cid, f"hub (used by {row['used_by']}, uses {row['uses']}, {row['duties']} duties, "
                                            f"{row['loc']} loc)", row["loc"]))
        own_files = set(component_files(component, inv))
        own = [anchor for anchor in coverage[cid]["unexplained"] if anchor.partition(":")[0] in own_files
               or anchor in component.get("entrypoints", [])]
        if own:
            steps.append(_step("unexplained", cid, f"{len(own)} unexplained entrypoints and state writers", 200 + len(own)))
        models = tree.models_for_component(cid)
        if (component.get("state") or component.get("side_effects")) and not models:
            steps.append(_step("unmodeled_owner", cid, "owns state or side effects but has no model", 1))
        if models and row["bound"] == 0:
            steps.append(_step("unbound_models", cid, f"{len(models)} models, 0 bound tests", len(models)))
    for flow in data.get("flows", []):
        if not flow.get("model"):
            steps.append(_step("flow_without_model", flow["id"], "no model", 1))
    steps.sort(key=lambda step: (-step[0], -step[1], step[2]))
    return [text for *_, text in steps]


def render_review(root: Path, data: dict, inv: Inventory, *, budget: int = 8000) -> str:
    graph = component_graph(data, inv)
    tree = build_tree(root, data, inv)
    model_data = {mid: model_facets(root, node) for mid, node in tree.nodes.items()}
    raw, functions, coverage = _read_facts(root, data, inv, tree)
    findings = run_lint(root, data, inv)
    used_by = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            used_by[target].add(source)
    rows, table = {}, []
    for component, _ in _layer_order(data, {c["id"] for c in data["components"]}):
        cid = component["id"]
        files = component_files(component, inv)
        facets = component_facets(root, data, inv, component, tree, graph, functions, coverage=coverage[cid])
        functions_bound = next((re.match(r"(\d+) functions, (\d+) bound", item) for item in facets.tests
                                if re.match(r"\d+ functions, \d+ bound", item)), None)
        total, bound = (int(functions_bound.group(1)), int(functions_bound.group(2))) if functions_bound else (0, 0)
        models = tree.models_for_component(cid)
        rules = [model_data[node.id].rule_count for node in models]
        bads = [model_data[node.id].known_bad_count for node in models]
        rule_text = "?" if None in rules else str(sum(rules))
        bad_text = "?" if None in bads else str(sum(bads))
        row = dict(loc=sum(inv.loc.get(path, 0) for path in files), files=len(files),
                   duties=len(component.get("responsibilities", [])), uses=len(graph.get(cid, ())),
                   used_by=len(used_by[cid]), bound=bound)
        rows[cid] = row
        unexplained = len(coverage[cid]["unexplained"])
        table.append(f"  {cid} {component.get('layer') or '-'} {row['files']}/{row['loc']} {row['duties']} "
                     f"{row['uses']}/{row['used_by']} {len(models)}({rule_text}/{bad_text}) {bound}/{total} {unexplained}")
    entries = [sum(coverage[c["id"]]["entrypoints"][i] for c in data["components"] if not c.get("parent")) for i in (0, 1)]
    writers = [sum(coverage[c["id"]]["state_writers"][i] for c in data["components"] if not c.get("parent")) for i in (0, 1)]
    errors = sum(finding.level == "error" for finding in findings)
    warnings = sum(finding.level == "warn" for finding in findings)
    debts = data.get("accepted_debts", [])
    head = (f"# {data.get('project', '')} review: {len(data['components'])} components, {len(tree.nodes) + 1} models (with system), "
            f"{len(data.get('flows', []))} flows; architecture: {errors} error(s), {warnings} warning(s), "
            f"{len(debts)} accepted debt(s)")
    strengths = _strengths(findings, data, (entries, writers), model_data)
    steps = _candidates(findings, data, inv, graph, tree, coverage, rows)
    ranked = [f"  {index}. {text}" for index, text in enumerate(steps[:SHOWN_STEPS], 1)]
    if len(steps) > SHOWN_STEPS:
        ranked.append(f"  +{len(steps) - SHOWN_STEPS} more (python -m flowguard map lint)")
    before = [head, "strengths: " + ("; ".join(strengths) or "none yet"), "defects:", *_defect_lines(findings),
              "components: id layer files/loc duties uses/used-by models(rules/known-bad) tests(bound/functions) unexplained"]
    after = ["optimise next:" + ("" if ranked else " nothing to rank"), *ranked]
    if debts:
        after += ["debts:", *(f"  {debt.get('code', '')} {debt.get('component', '')}: {debt.get('reason', '')}" for debt in debts)]
    shown = list(table)
    while True:
        hidden = len(table) - len(shown)
        middle = shown + ([f"  ... {hidden} more components (python -m flowguard read)"] if hidden else [])
        text = "\n".join(before + middle + after)
        if len(text) <= budget or not shown:
            return text
        shown.pop()
