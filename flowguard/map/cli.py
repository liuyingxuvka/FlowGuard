"""Command line: python -m flowguard.map <command> [--root PATH] ...

Daily commands (read-only unless stated):
  show      the map as compact text (start every session with this)
  find      which component already owns a responsibility
  check     map <-> code verification (exit 1 on errors)
  impact    changed files -> components -> tests and models to run
  models    run executable models (writes only .flowguard/cache/)
  confirm   [writes map] accept a component's description as current
Setup and review:
  scan      [writes map] create draft components for a project without a map
  digest    API outline (signatures and docstrings) of components, for writing descriptions
  deps      show real component dependencies; --write copies them into depends_on
  discover  behaviour found in the code per component: entrypoints, side effects, state writers
  lint      architecture review
  verify    release gate: strict check + lint errors + all models (forced)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .check import run_check
from .common import MAP_RELPATH, print_findings
from .impact import changed_files, compute_impact, render_impact
from .inventory import build_inventory
from .lint import Limits, run_lint
from .mapfile import MapError, component_files, component_graph, fingerprint, ignore_patterns, load_map, map_path, owner_index, save_map
from .proof import render_results, run_models
from .scan import new_map
from .views import find_owners, render_digest, render_show


def _context(root: Path):
    data = load_map(root)
    return data, build_inventory(root, ignore_patterns(data))


def cmd_scan(root: Path, a) -> int:
    if map_path(root).is_file():
        data, inv = _context(root)
        owner, _ = owner_index(data, inv)
        unmapped = [f for f in inv.source if f not in owner and f not in inv.tests]
        print(f"{MAP_RELPATH} exists; {len(unmapped)} unmapped source file(s)")
        for f in unmapped[: a.limit]:
            print(f"  unmapped: {f}")
        return 0
    inv = build_inventory(root, ignore_patterns(None))
    data = new_map(root, inv)
    save_map(root, data)
    print(f"created {MAP_RELPATH}: {len(data['components'])} draft components from "
          f"{len(inv.source) - len(inv.tests)} source files and {len(inv.tests)} test files")
    print("next: digest all -> merge/describe components -> deps --write -> check -> confirm")
    return 0


def cmd_discover(root: Path, a) -> int:
    from .discover import component_summary, discover_inventory

    data, inv = _context(root)
    raw = discover_inventory(root, inv)
    comps = [c for c in data["components"] if not a.component or c["id"] == a.component]
    if a.component and not comps:
        print(f"unknown component {a.component!r}", file=sys.stderr)
        return 2
    out = {c["id"]: component_summary(raw, component_files(c, inv)) for c in comps}
    if a.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0
    for cid, found in out.items():
        if not (found["entrypoints"] or found["effects"] or found["state_writers"]):
            continue
        print(f"{cid}:")
        for line in found["entrypoints"]:
            print(f"  entry   {line}")
        if found["effects"]:
            print("  effects " + ", ".join(f"{k} x{v}" for k, v in found["effects"].items()))
        for entry, kinds in found["entrypoint_effect_reach"].items():
            print(f"  reach   {entry} -> {', '.join(kinds)}")
        for attr, writers in found["state_writers"].items():
            print(f"  state   {attr} <- {', '.join(writers)}")
    return 0


def cmd_show(root: Path, a) -> int:
    data, inv = _context(root)
    print(render_show(root, data, inv, component=a.component, detail=a.detail, budget=a.budget))
    return 0


def cmd_find(root: Path, a) -> int:
    data, inv = _context(root)
    hits = find_owners(data, inv, a.words)
    if not hits:
        print("no existing owner found; decide which component should own this before writing code")
        return 1
    by_id = {c["id"]: c for c in data["components"]}
    for score, cid, owned in hits:
        print(f"{score:3}  {cid}" + (f"  owns: {'; '.join(owned)}" if owned else ""))
        print(f"     files: {', '.join(by_id[cid].get('files', []))}")
    return 0


def cmd_digest(root: Path, a) -> int:
    data, inv = _context(root)
    text = render_digest(root, data, inv, a.ids, a.max_lines)
    print(text)
    return 1 if text.startswith("unknown component") else 0


def cmd_check(root: Path, a) -> int:
    data, inv = _context(root)
    counts = print_findings(run_check(root, data, inv, strict=a.strict), "check", as_json=a.json, limit=a.limit)
    return 1 if counts["error"] else 0


def cmd_lint(root: Path, a) -> int:
    data, inv = _context(root)
    limits = Limits(a.max_component_loc, a.max_file_loc, a.max_responsibilities, a.max_fan_out)
    counts = print_findings(run_lint(root, data, inv, limits), "lint", as_json=a.json, limit=a.limit)
    return 1 if counts["error"] else 0


def cmd_impact(root: Path, a) -> int:
    data, inv = _context(root)
    imp = compute_impact(root, data, inv, a.files or changed_files(root, a.base), a.depth)
    print(json.dumps(imp.to_dict(), indent=1) if a.json else render_impact(imp))
    return 0


def cmd_deps(root: Path, a) -> int:
    data, inv = _context(root)
    graph = component_graph(data, inv)
    changed = 0
    for c in data["components"]:
        actual = sorted(graph.get(c["id"], ()))
        print(f"{c['id']}: {', '.join(actual) or '-'}")
        if a.write and c.get("depends_on") != actual:
            c["depends_on"], changed = actual, changed + 1
    if a.write:
        save_map(root, data)
        print(f"updated depends_on of {changed} component(s) from the real import graph")
    return 0


def cmd_confirm(root: Path, a) -> int:
    data, inv = _context(root)
    ids = [c["id"] for c in data["components"]] if a.ids == ["all"] else a.ids
    by_id = {c["id"]: c for c in data["components"]}
    missing = [i for i in ids if i not in by_id]
    if missing:
        print(f"unknown component(s): {missing}")
        return 1
    empty = [i for i in ids if not by_id[i].get("summary") or not by_id[i].get("responsibilities")]
    if empty:
        print(f"fill summary and responsibilities before confirming: {empty}")
        return 1
    for i in ids:
        c = by_id[i]
        c.pop("_hint", None)
        c["status"], c["fingerprint"] = "confirmed", fingerprint(root, component_files(c, inv))
    save_map(root, data)
    print(f"confirmed {len(ids)} component(s)")
    return 0


def cmd_models(root: Path, a) -> int:
    results = run_models(root, a.ids, force=a.force, timeout=a.timeout)
    print(render_results(results))
    return 1 if any(r.status != "pass" for r in results) else 0


def cmd_verify(root: Path, a) -> int:
    data, inv = _context(root)
    check = print_findings(run_check(root, data, inv, strict=True), "check --strict", as_json=False, limit=a.limit)
    lint = print_findings([f for f in run_lint(root, data, inv) if f.level == "error"], "lint (errors only)",
                          as_json=False, limit=a.limit)
    results = run_models(root, [], force=True)
    print(render_results(results))
    failed = check["error"] + lint["error"] + sum(r.status != "pass" for r in results)
    print(f"verify: {'PASS' if not failed else 'FAIL'}"
          f" (also run the full test suite: {data.get('test_command') or 'python -m pytest -q'})")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m flowguard.map", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("discover"); s.add_argument("--component"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("show"); s.add_argument("--component"); s.add_argument("--detail", action="store_true")
    s.add_argument("--budget", type=int, default=12000, help="max characters printed")
    s = sub.add_parser("find"); s.add_argument("words", nargs="+")
    s = sub.add_parser("digest"); s.add_argument("ids", nargs="+", help="component ids, or 'all'")
    s.add_argument("--max-lines", type=int, default=60, help="max outline lines per file")
    for name in ("check", "lint"):
        s = sub.add_parser(name); s.add_argument("--json", action="store_true"); s.add_argument("--limit", type=int, default=80)
    sub.choices["check"].add_argument("--strict", action="store_true", help="draft and stale are errors (release)")
    lint = sub.choices["lint"]
    lint.add_argument("--max-component-loc", type=int, default=3000)
    lint.add_argument("--max-file-loc", type=int, default=800)
    lint.add_argument("--max-responsibilities", type=int, default=7)
    lint.add_argument("--max-fan-out", type=int, default=8)
    s = sub.add_parser("impact"); s.add_argument("files", nargs="*"); s.add_argument("--base", default="HEAD")
    s.add_argument("--depth", type=int, default=1); s.add_argument("--json", action="store_true")
    s = sub.add_parser("deps"); s.add_argument("--write", action="store_true")
    s = sub.add_parser("confirm"); s.add_argument("ids", nargs="+", help="component ids, or 'all'")
    s = sub.add_parser("models"); s.add_argument("ids", nargs="*"); s.add_argument("--force", action="store_true")
    s.add_argument("--timeout", type=int, default=300, help="seconds per model")
    s = sub.add_parser("verify"); s.add_argument("--limit", type=int, default=80)
    for command in sub.choices.values():   # --root is accepted before or after the command
        command.add_argument("--root", default=argparse.SUPPRESS, help="project root (default: current directory)")
    return p


HANDLERS = {"discover": cmd_discover, "scan": cmd_scan, "show": cmd_show, "find": cmd_find, "digest": cmd_digest, "check": cmd_check,
            "lint": cmd_lint, "impact": cmd_impact, "deps": cmd_deps, "confirm": cmd_confirm,
            "models": cmd_models, "verify": cmd_verify}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        return HANDLERS[args.cmd](root, args)
    except (MapError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:                     # e.g. "... | head": stop quietly
        try:
            sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - avoid a second error at interpreter exit
        except OSError:
            pass
        return 0
