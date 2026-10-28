"""Model binding, implementation coverage and executable model size diagnostics."""

from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from .common import Finding, read_source
from .discover import anchor_state_writes, reachable_effects
from .inventory import Inventory
from .tree import build_tree
from .mapfile import (
    model_registry,
    owner_index,
    read_model_contract,
    resolve_model_path,
)

SIZE_LIMITS = {"rules": (8, 12), "sequences": (2000, 10000)}
PRECISE_ENTRY_KINDS = {"http_route", "cli_command", "console_script", "handler"}


def model_binding_notes(
    root: Path, data: dict, inv: Inventory | None = None, *, view=None, tree=None
) -> list[Finding]:
    """Non-gating binding notes: design-only models still to bind; models whose guarding tests are not named."""
    out: list[Finding] = []
    if inv is None:
        from .inventory import build_inventory
        from .mapfile import ignore_patterns

        inv = build_inventory(
            root,
            ignore_patterns(data),
            write_cache=view is None,
            import_roots=tuple(data.get("import_roots", ())),
        )
    if tree is None:
        tree = build_tree(root, data, inv, view=view)
    from .mapfile import process_model_reason

    unbound = [
        node
        for node in tree.nodes.values()
        if not any(node.contract.get("TESTED_BY", {}).values())
        and not process_model_reason(data, node.contract)
    ]
    if not unbound:
        return out
    from .testtree import test_calls

    calls = {}
    for test in inv.tests:
        if test.endswith(".py"):
            try:
                calls[test] = test_calls(test, read_source(root / test), inv)
            except OSError:
                continue
    for node in unbound:
        contract = node.contract
        anchors = set(contract.get("IMPLEMENTED_BY", {}).values())
        calling = [
            f"{path}::{name}"
            for path, functions in calls.items()
            for name, values in functions.items()
            if values & anchors
        ]
        if calling:
            detail = (
                f"{len(calling)} test functions call its code ({calling[0]}"
                + (f", +{len(calling)-1}" if len(calling) > 1 else "")
                + ")"
            )
        else:
            detail = "no tests call its code; 0 bound tests"
        out.append(Finding("warn", "unbound_models", node.id, detail))
    return out


def model_coverage(
    root: Path, data: dict, registry=None, *, view=None
) -> tuple[dict[str, set[str]], set[str]]:
    """Read declared implementation anchors and explicit negative scope once."""
    covered = {}
    not_modeled = set()
    for entry in (registry or model_registry(root, data, view=view)).entries:
        path = resolve_model_path(root, entry.path, view=view)
        if path is None:
            continue
        try:
            contract = read_model_contract(path)
        except (OSError, SyntaxError, ValueError):
            continue
        covered[entry.path] = set(contract.get("IMPLEMENTED_BY", {}).values())
        not_modeled.update(contract.get("NOT_MODELED", {}))
    return covered, not_modeled


def explained_by(anchor, covered, not_modeled=(), *, tests=""):
    """One static explanation: "model" (an IMPLEMENTED_BY anchor), "reason" (NOT_MODELED), "test"
    (its name is a whole word in the component's tests) or None. Lint leaves the test text empty.
    """
    if anchor in covered:
        return "model"
    if anchor in not_modeled:
        return "reason"
    return "test" if not isinstance(tests, str) and anchor in tests else None


def model_writer_findings(
    raw: dict, data: dict, root: Path, inv: Inventory, registry=None, *, view=None
) -> list[Finding]:
    """Other exact functions in an anchor's own file that write its modeled state."""
    contracts = []
    excluded = set()
    for entry in (registry or model_registry(root, data, view=view)).entries:
        path = resolve_model_path(root, entry.path, view=view)
        if path is None:
            continue
        try:
            contract = read_model_contract(path)
        except (OSError, SyntaxError, ValueError):
            continue
        contracts.append((entry, contract))
        excluded.update(contract.get("IMPLEMENTED_BY", {}).values())
        excluded.update(contract.get("NOT_MODELED", {}))
    owner, _ = owner_index(data, inv)
    out = []
    for entry, contract in contracts:
        by_file = defaultdict(list)
        for anchor in sorted(contract.get("IMPLEMENTED_BY", {}).values()):
            writes = anchor_state_writes(raw, anchor)
            if writes:
                by_file[anchor.split(":", 1)[0]].append((anchor, writes))
        for path, anchors in sorted(by_file.items()):
            for symbol, function in sorted(
                raw["files"][path].get("functions", {}).items()
            ):
                writer = f"{path}:{symbol}"
                if symbol.rsplit(".", 1)[-1] == "__init__" or explained_by(
                    writer, excluded
                ):
                    continue
                overlap = sorted(
                    (state, anchor)
                    for anchor, writes in anchors
                    for state in writes.intersection(function.get("writes", []))
                )
                if overlap:
                    state, anchor = overlap[0]
                    out.append(
                        Finding(
                            "warn",
                            "model_writer_unbound",
                            owner.get(path, ""),
                            f"{writer} writes {state}, which model {entry.id} covers through {anchor}; "
                            "add it to IMPLEMENTED_BY, or to NOT_MODELED with a reason",
                        )
                    )
    return out


def entrypoint_coverage_findings(
    raw: dict,
    data: dict,
    inv: Inventory,
    covered_by_model: dict[str, set[str]],
    *,
    not_modeled: set[str] | None = None,
    models_by_component: dict[str, list[str]] | None = None,
) -> list[Finding]:
    """Check external or dangerous declared entries against model anchors or explicit reasons."""
    out = []
    dangerous = {"db", "network", "fs_write", "fs_delete"}
    for comp in data["components"]:
        paths = (
            models_by_component.get(comp["id"], [])
            if models_by_component is not None
            else comp.get("models", [])
        )
        covered = set().union(*(covered_by_model.get(model, set()) for model in paths))
        for anchor in comp.get("entrypoints", []):
            if explained_by(anchor, covered, not_modeled or set()):
                continue
            path, sep, symbol = anchor.partition(":")
            if not sep:
                continue
            file = raw["files"].get(path, {})
            functions = file.get("functions", {})
            names = (
                [symbol]
                if symbol in functions
                else [name for name in functions if name.endswith("." + symbol)]
            )
            precise = sorted(
                {
                    entry["kind"]
                    for entry in file.get("entrypoints", [])
                    if entry["symbol"] in names
                    and entry["kind"] in PRECISE_ENTRY_KINDS
                    and entry.get("via") != "argparse"
                }
            )
            if precise:
                out.append(
                    Finding(
                        "warn",
                        "entrypoint_unmodeled",
                        comp["id"],
                        f"external promise {anchor} ({', '.join(precise)}) has no model anchor; "
                        "model it, or declare NOT_MODELED with a reason",
                    )
                )
                continue
            effects = set().union(
                *(set(reachable_effects(raw, f"{path}#{name}")) for name in names)
            )
            if effects & dangerous:
                out.append(
                    Finding(
                        "warn",
                        "entrypoint_unmodeled",
                        comp["id"],
                        f"{anchor} reaches {', '.join(sorted(effects & dangerous))} without a model anchor; "
                        "model it, or declare NOT_MODELED with a reason",
                    )
                )
    return out


def split_recipe(model):
    return (
        "a staged model becomes a coarse parent plus one child per stage, a model of alternatives a dispatch parent plus one child per branch "
        f'(PARENT = "{model}"; DISPATCH); different aspects, and parts other models also use, become independent models; '
        "a test file that tests only this model is split with it (references/routes.md#Split a model)"
    )


def size_finding(model, kind, count):
    soft, hard = SIZE_LIMITS[kind]
    if count is None or count <= soft:
        return None
    unit = "rules" if kind == "rules" else "explored sequences"
    quantity = str(count) if kind == "rules" else f"{count:,}"
    limit = (
        (lambda number: str(number))
        if kind == "rules"
        else (lambda number: f"{number:,}")
    )
    detail = (
        f"{quantity} {unit}, over the hard limit {limit(hard)}; split it in a target"
        if count > hard
        else f"{quantity} {unit} (soft limit {limit(soft)}; split before {limit(hard)})"
    )
    return Finding(
        "error" if count > hard else "warn",
        "large_model",
        model,
        detail + ": " + split_recipe(model),
    )


def model_size_findings(root, data, inv, *, view=None, tree=None):
    from .modelstatic import rule_count

    if tree is None:
        tree = build_tree(root, data, inv, view=view)
    return [
        finding
        for mid, node in tree.nodes.items()
        if (
            finding := size_finding(
                mid, "rules", rule_count(root, node.path, view=view)
            )
        )
        is not None
    ]
