"""Command line: python -m flowguard.map <command> [--root PATH] ...

Daily commands (read-only unless stated):
  show      the map as compact text (start every session with this); --review ranks the architecture
  find      which component already owns a responsibility
  check     map <-> code verification (exit 1 on errors)
  impact    changed files -> components -> tests and models to run
  models    run executable models
  confirm   [writes map] accept a component's description as current
Setup and review:
  scan      [writes map] create draft components for a project without a map
  digest    API outline (signatures and docstrings) of components, for writing descriptions
  deps      show real component dependencies; --write copies them into depends_on
  discover  behaviour found in the code per component: entrypoints, side effects, state writers
  lint      architecture review
  verify    release gate: strict check + lint errors + all models
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from .check import run_check
from .common import MAP_RELPATH, print_findings, quiet_broken_pipe, safe_stdio
from .impact import run_commands, changed_files, compute_impact, render_impact
from .inventory import build_inventory
from .lint import Limits, run_lint
from .mapfile import FINGERPRINT_FORMAT, format_guard, MapError, component_files, component_graph, dependency_evidence, fingerprint, ignore_patterns, load_map, map_path, model_registry, owner_index, save_map
from .proof import DEFAULT_JOBS, render_results, run_models
from .scan import new_map
from .tree import build_tree
from .views import closest_owners, defined_symbols, find_owners, render_field, render_digest, render_mermaid, render_show
from .target import check_target, moving_to_target, target_model_paths, target_owns_file
from .targetfile import TARGET_RELDIR, load_target, validate_target


def _context(root: Path, with_bodies: bool = True):
    data = load_map(root)
    inv = build_inventory(root, ignore_patterns(data), with_bodies=with_bodies, import_roots=tuple(data.get("import_roots", ())))
    if hasattr(inv, "set_explicit_sources"):
        inv.set_explicit_sources([pattern for comp in data["components"] for pattern in comp.get("files", [])])
    return data, inv


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
    data = new_map(root, inv, max_components=a.max_components)
    save_map(root, data)
    print(f"created {MAP_RELPATH}: {len(data['components'])} draft components from "
          f"{len(inv.source) - len(inv.tests)} source files and {len(inv.tests)} test files")
    for component in data["components"]:
        files = component_files(component, inv)
        if len(files) >= 6 and len({Path(path).parent.as_posix() for path in files}) == 1:
            print(f"hint: draft {component['id']} holds {len(files)} files of one directory; split it by responsibility "
                  f"(python -m flowguard map digest {component['id']} lists each file's API)")
    print("next: digest all -> merge/describe components -> deps --write -> check -> confirm")
    return 0


def cmd_discover(root: Path, a) -> int:
    from .discover import component_summary, discover_inventory

    data, inv = _context(root)
    raw = discover_inventory(root, inv, data=data)
    comps = [c for c in data["components"] if not a.component or c["id"] == a.component]
    if a.component and not comps:
        print(f"unknown component {a.component!r}", file=sys.stderr)
        return 2
    out = {c["id"]: component_summary(raw, component_files(c, inv)) for c in comps}
    if a.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0
    printed = False
    for cid, found in out.items():
        if not (found["entrypoints"] or found["effects"] or found["state_writers"]):
            continue
        printed = True
        print(f"{cid}:")
        for line in found["entrypoints"]:
            print(f"  entry   {line}")
        if found["effects"]:
            print("  effects " + ", ".join(f"{k} x{v}" for k, v in found["effects"].items()))
        for entry, kinds in found["entrypoint_effect_reach"].items():
            print(f"  reach   {entry} -> {', '.join(kinds)}")
        for attr, writers in found["state_writers"].items():
            print(f"  state   {attr} <- {', '.join(writers)}")
    if not printed:
        print("no entrypoints, effects or state writers found (a library without commands is normal; "
              "list its public API in entrypoints by hand)")
    return 0


def cmd_show(root: Path, a) -> int:
    if getattr(a, "field", None):
        if a.component or a.mermaid or a.target or a.review:
            print("error: --field cannot be combined with another view", file=sys.stderr)
            return 2
        data, inv = _context(root, with_bodies=False)
        text = render_field(root, data, inv, a.field)
        print(text)
        return int(text.startswith("field " + a.field + ": no model, rule or code site"))
    if getattr(a, "review", False):
        clash = [
            flag
            for flag, on in (
                ("--component", a.component),
                ("--mermaid", getattr(a, "mermaid", False)),
                ("--target", getattr(a, "target", False)),
            )
            if on
        ]
        if clash:
            print(f"error: --review cannot be used with {', '.join(clash)}", file=sys.stderr)
            return 2
        from .review import render_review

        data, inv = _context(root, with_bodies=False)
        print(render_review(root, data, inv))
        return 0
    data, inv = _context(root, with_bodies=False)
    target = None
    if getattr(a, "target", False):
        try:
            target = load_target(root)
            if target is None:
                print('no target; start one with python -m flowguard target start "<goal>"')
                return 1
            if validate_target(root, data, target):
                raise MapError("invalid target")
        except (OSError, ValueError, TypeError, SyntaxError, MapError):
            print(
                "target: .flowguard/target/map.json is invalid; run python -m flowguard target check"
            )
            return 1
    options = {"target": target} if target is not None else {}
    text = (
        render_mermaid(root, data, inv, component=a.component, **options)
        if getattr(a, "mermaid", False)
        else render_show(root, data, inv, component=a.component, detail=False, **options)
    )
    print(text)
    return 1 if text.startswith("no component") else 0


def cmd_find(root: Path, a) -> int:
    data, inv = _context(root, with_bodies=False)
    from .common import norm, tokens
    from .views import render_locate

    if len(a.words) == 1:
        location = a.words[0]
        path = norm(location.split("::", 1)[0].split(":", 1)[0])
        if path in inv.py:
            text = render_locate(root, data, inv, location)
            print(text)
            return int(text.startswith("no symbol "))
    tree = build_tree(root, data, inv)
    hits = find_owners(data, inv, a.words)
    if not hits:
        print("no existing owner found; decide which component should own this before writing code")
        closest = closest_owners(data, a.words)
        if closest:
            print("closest owners (check these before creating a new component):")
            for cid, duty in closest:
                print(f"  {cid}: {duty}")
        return 1
    by_id = {c["id"]: c for c in data["components"]}
    for score, cid, owned in hits:
        print(f"{score:3}  {cid}" + (f"  owns: {'; '.join(owned)}" if owned else ""))
        for symbol, path in defined_symbols(by_id[cid], inv, a.words)[:3]:
            print(f"     defines: {symbol} ({path})")
        print(f"     files: {', '.join(by_id[cid].get('files', []))}")
        models = [node.id for node in tree.models_for_component(cid)]
        if models:
            print(f"     models: {', '.join(models)}")
        for label, key in (("state", "state"), ("effects", "side_effects")):
            if by_id[cid].get(key):
                print(f"     {label}: {'; '.join(by_id[cid][key])}")
    print(
        "next: extend the owner above that already holds this behavior; create a new component only when none does"
    )
    from .views import locate_words

    print("locate: " + locate_words(root, tree, by_id[hits[0][1]], inv, a.words))
    return 0


def cmd_digest(root: Path, a) -> int:
    data, inv = _context(root, with_bodies=False)
    text = render_digest(root, data, inv, a.ids, 60)
    print(text)
    return 1 if text.startswith("unknown component") else 0


def _active_target(root, data):
    """Malformed drafts never authorize weakening a current-tree finding."""
    try:
        target = load_target(root)
        return target if target is not None and not validate_target(root, data, target) else None
    except MapError:
        return None


def cmd_check(root: Path, a) -> int:
    data, inv = _context(root)
    findings = run_check(root, data, inv, strict=a.strict)
    if not a.strict:
        findings = moving_to_target(findings, root, data, _active_target(root, data))
    counts = print_findings(findings, "check", as_json=a.json, limit=a.limit)
    return 1 if counts["error"] else 0


def cmd_lint(root: Path, a) -> int:
    from .debts import evaluate_debts

    data, inv = _context(root)
    evaluation = evaluate_debts(root, data)
    limits = Limits()
    findings = run_lint(root, data, inv, limits, evaluation=evaluation)
    if getattr(a, "debts", False):
        from .review import declined_debts
        matched = declined_debts(root, data, inv)
        for state, debt in zip(evaluation.states, data.get("accepted_debts", [])):
            used = any(f.code == debt["code"] and f.component == debt.get("component", f.component)
                       and "(accepted debt:" in f.message for f in findings)
            if debt.get("code") in {"unmodeled_owner", "hub", "flow_without_model", "unbound_models"}:
                used = (debt["code"], debt.get("component", "")) in matched
            used = used and state.status == "active"
            print(f"{debt['code']} {debt.get('component', '*')}: {debt.get('reason', '')}"
                  f" (expires {debt.get('expires', '')})"
                  + (" (expired)" if state.status == "expired" else "")
                  + ("" if used else " (unused)"))
        deadlines = [finding for finding in findings if finding.code in {"debt_without_expiry", "debt_expired"}]
        if deadlines:
            print_findings(deadlines, "debt deadlines", as_json=False, limit=a.limit)
        return int(any(f.level == "error" for f in findings))
    counts = print_findings(findings, "lint", as_json=a.json, limit=a.limit)
    return 1 if counts["error"] else 0


def cmd_impact(root: Path, a) -> int:
    data, inv = _context(root)
    imp = compute_impact(root, data, inv, a.files or changed_files(root, a.base), None, base=a.base, broad=True)
    print(json.dumps(imp.to_dict(), indent=1) if a.json else render_impact(imp))
    return 1 if imp.blocked or imp.unmapped else 0



def cmd_change(root: Path, a) -> int:
    """Check and select in one context; show architecture only for changed owners."""
    from .lint import scoped_architecture_findings

    data, inv = _context(root)
    changes = a.files or changed_files(root, a.base, data=data, inv=inv)
    findings = run_check(root, data, inv)
    formula_path = "flowguard/map/mapfile.py"
    if formula_path in changes and formula_path in inv.source:
        from .common import Finding, read_source

        previous = subprocess.run(
            ["git", "show", a.base + ":" + formula_path], cwd=root, capture_output=True
        )
        if previous.returncode == 0:
            message = format_guard(
                previous.stdout.decode("utf-8"), read_source(root / formula_path)
            )
            if message:
                findings.append(
                    Finding(
                        "warn",
                        "fingerprint_format_unchanged",
                        "map-file",
                        message.removeprefix("fingerprint_format_unchanged: "),
                    )
                )
    imp = compute_impact(root, data, inv, changes, base=a.base, broad=getattr(a, "broad", False))
    architecture = scoped_architecture_findings(root, data, inv, imp.direct)
    target = _active_target(root, data)
    findings = moving_to_target(findings, root, data, target)
    architecture = moving_to_target(architecture, root, data, target)
    unmapped = [
        path for path in imp.unmapped if target is None or not target_owns_file(path, target)
    ]
    # Structural violations appear once, as ARCH lines with import paths.
    arch_rules = {
        (f.code, f.component)
        for f in architecture
        if f.code in {"layer_violation", "dependency_cycle"}
    }
    shown = [
        f
        for f in findings
        if (
            f.level != "info"
            or f.component in imp.direct
            or f.message.startswith("moving to target: ")
        )
        and (f.code, f.component) not in arch_rules
    ]
    counts = {level: sum(f.level == level for f in findings) for level in ("error", "warn", "info")}
    print_findings(shown, "check", as_json=False, limit=80)
    if len(shown) < len(findings):
        print(
            f"({len(findings) - len(shown)} more finding(s) not repeated here: python -m flowguard map check)"
        )
    print()
    print(
        render_impact(
            imp,
            moving_models=target_model_paths(root, data, target) if target is not None else None,
            verbose=getattr(a, "verbose", False),
            unmapped=unmapped,
        )
    )
    if (root / TARGET_RELDIR).exists():
        if target is None:
            print(
                "TARGET: .flowguard/target/map.json is invalid; run: python -m flowguard target check"
            )
        else:
            report = check_target(root, models=False)
            print(
                f'TARGET "{report.goal}": {len(report.errors)} design error(s), {len(report.todos)} to-do in the map; '
                "run: python -m flowguard target check (it also runs the target models)"
            )
    for finding in architecture:
        print(f"ARCH {finding.level.upper()} {finding.code} {finding.component}: {finding.message}")
    affected = set(imp.direct)
    debts = sum(debt.get("component") in affected for debt in data.get("accepted_debts", []))
    print(
        f"debts: {debts} accepted for the changed components (python -m flowguard map lint --debts)"
    )
    code = int(
        bool(
            counts["error"]
            or imp.blocked
            or unmapped
            or any(f.level == "error" for f in architecture)
        )
    )
    if not getattr(a, "run", False):
        return code
    if code:
        print("RAN: skipped (fix the errors above first)")
        return code
    result = _run_selected(
        root,
        run_commands(imp, moving_models=target_model_paths(root, data, target) if target else None),
    )
    from .mapfile import is_stale

    stale = sorted(c["id"] for c in data["components"] if is_stale(root, c, inv))
    if stale:
        print("next: python -m flowguard map confirm " + " ".join(stale))
    return result


def _run_selected(root: Path, commands: list[str]) -> int:
    """change --run: execute each run: command without a shell; one RAN line per command."""
    import shlex
    import time

    failed = False
    for command in commands:
        argv = shlex.split(command)
        if argv and argv[0] == "python":         # the run: lines name the interpreter running FlowGuard
            argv[0] = sys.executable
        started = time.monotonic()
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        shown = command[:120]
        if result.returncode == 0:
            print(f"RAN PASS {time.monotonic()-started:.2f}s {shown}")
            continue
        failed = True
        print(f"RAN FAIL (exit {result.returncode}) {time.monotonic()-started:.2f}s {shown}")
        for line in (result.stdout + result.stderr).splitlines()[-20:]:
            print("  " + line)
    return int(failed)


def cmd_deps(root: Path, a) -> int:
    from .discover import discover_inventory
    data, inv = _context(root)
    graph = dependency_evidence(data, inv, discover_inventory(root, inv, data=data))
    changed = 0
    for c in data["components"]:
        actual = sorted(graph.get(c["id"], ()))
        declared_only = sorted(set(c.get("depends_on", [])) - set(actual))
        print(f"{c['id']}: {', '.join(actual) or '-'}")
        if declared_only:
            print("  declared, unverified: " + ", ".join(declared_only))
        # Static import extraction cannot disprove lazy/alias dependencies.
        retained = actual
        removed = sorted(set(c.get("depends_on", [])) - set(retained))
        if a.write and removed:
            print("  removed without evidence: " + ", ".join(removed))
        if a.write and c.get("depends_on") != retained:
            c["depends_on"], changed = retained, changed + 1
    if a.write:
        save_map(root, data)
        print(f"updated depends_on of {changed} component(s); kept only dependencies supported by imports, import-like literals, injected collaborators or accepted debts")
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
    if all(c.get("status") != "confirmed" or c.get("fingerprint") == fingerprint(root, component_files(c, inv))
           for c in data["components"]):
        data["fingerprint_format"] = FINGERPRINT_FORMAT
    save_map(root, data)
    suffix = f"; map fingerprint_format {FINGERPRINT_FORMAT}" if data.get("fingerprint_format") == FINGERPRINT_FORMAT else ""
    print(f"confirmed {len(ids)} component(s){suffix}")
    return 0


def cmd_models(root: Path, a) -> int:
    results = run_models(root, a.ids, tests=a.tests, jobs=getattr(a, "jobs", DEFAULT_JOBS))
    print(render_results(results))
    return 1 if any(r.status != "pass" for r in results) else 0


def cmd_verify(root: Path, a) -> int:
    from .debts import evaluate_debts

    if (root / TARGET_RELDIR).exists():
        try:
            target = load_target(root)
            goal = target.goal if target is not None else "<invalid target>"
        except MapError:
            goal = "<invalid target>"
        print(f'warning: target "{goal}" exists: release checks only the current tree; promote or drop the target before releasing')
    data, inv = _context(root)
    evaluation = evaluate_debts(root, data)
    check = print_findings(run_check(root, data, inv, strict=True, evaluation=evaluation), "check --strict", as_json=False, limit=a.limit)
    findings = run_lint(root, data, inv, evaluation=evaluation)
    lint = {level: sum(f.level == level for f in findings) for level in ("error", "warn", "info")}
    print(f"lint: {lint['error']} error(s) gating; {lint['warn']} warning(s), {lint['info']} info not gating (run python -m flowguard map lint)")
    if lint["error"]:
        print_findings([finding for finding in findings if finding.level == "error"],
                       "lint errors", as_json=False, limit=a.limit)
    debts = data.get("accepted_debts", [])
    print(f"accepted debts: {len(debts)} (python -m flowguard map lint --debts)")
    registry = model_registry(root, data)
    results = run_models(root, [], tests=True, jobs=getattr(a, "jobs", DEFAULT_JOBS))
    if results:
        print(render_results(results))
    expected = {(entry.id, entry.path) for entry in registry.entries}
    expected.add(("system", ".flowguard/map.json"))
    executed = [(result.model, result.file) for result in results]
    complete = len(executed) == len(set(executed)) and set(executed) == expected
    print(f"models: {len(expected)} declared, {len(executed)} executed" +
          ("; no model proof" if not expected else ""))
    if not complete:
        print(f"model execution mismatch: missing={sorted(expected - set(executed))}, unexpected={sorted(set(executed) - expected)}")
    failed = check["error"] + lint["error"] + sum(r.status != "pass" for r in results) + int(not complete)
    if a.shards is not None:
        if failed:
            print("suite: not run (fix the failures above first)")
        else:
            suite = subprocess.run(
                [sys.executable, "-m", "flowguard.pytest_shards_cli", "--root", str(root),
                 "--shards", str(a.shards)], capture_output=True, text=True,
            )
            for line in suite.stdout.splitlines():
                print(f"suite: {line}")
            for line in suite.stderr.splitlines():
                print(f"suite: {line}", file=sys.stderr)
            failed += int(suite.returncode != 0)
        print(f"verify: {'PASS' if not failed else 'FAIL'}")
    else:
        print(f"verify: {'PASS' if not failed else 'FAIL'}"
              " (only TESTED_BY tests ran; run the whole suite with python -m flowguard release --shards 4, or in CI)")
    return 1 if failed else 0




def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m flowguard.map",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--max-components", type=int, default=40)
    s = sub.add_parser("discover")
    s.add_argument("--component")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("--component")
    s.add_argument("--field", metavar="NAME")
    s.add_argument("--mermaid", action="store_true", help="export the model tree as Mermaid")
    s.add_argument("--target", action="store_true", help="show the target's node-by-node changes")
    s.add_argument(
        "--review",
        action="store_true",
        help="architecture review: metrics, strengths, defects, optimise next",
    )
    s = sub.add_parser("find")
    s.add_argument("words", nargs="+")
    s = sub.add_parser("digest")
    s.add_argument("ids", nargs="+", help="component ids, or 'all'")
    for name in ("check", "lint"):
        s = sub.add_parser(name)
        s.add_argument("--json", action="store_true")
        s.add_argument("--limit", type=int, default=80)
    sub.choices["check"].add_argument(
        "--strict", action="store_true", help="draft and stale are errors (release)"
    )
    lint = sub.choices["lint"]
    lint.add_argument(
        "--debts", action="store_true", help="list accepted decisions and unused debts"
    )
    s = sub.add_parser("impact")
    s.add_argument("files", nargs="*")
    s.add_argument("--base", default="HEAD")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("deps")
    s.add_argument("--write", action="store_true")
    s = sub.add_parser("confirm")
    s.add_argument("ids", nargs="+", help="component ids, or 'all'")
    s = sub.add_parser("models")
    s.add_argument("ids", nargs="*")
    s.add_argument(
        "--jobs",
        type=int,
        choices=range(1, 33),
        default=DEFAULT_JOBS,
        metavar="N",
        help="run 1-32 model subprocesses concurrently (default: min(4, CPUs))",
    )
    s.add_argument(
        "--tests",
        action="store_true",
        help="run each model's bound tests and check actual anchor reach",
    )
    s = sub.add_parser("verify")
    s.add_argument("--limit", type=int, default=80)
    s.add_argument(
        "--jobs",
        type=int,
        choices=range(1, 33),
        default=DEFAULT_JOBS,
        metavar="N",
        help="run 1-32 model subprocesses concurrently (default: min(4, CPUs))",
    )
    s.add_argument(
        "--shards",
        type=int,
        choices=range(1, 33),
        metavar="N",
        help="after normal checks pass, run the whole suite in 1-32 parallel shards",
    )
    for command in sub.choices.values():  # --root is accepted before or after the command
        command.add_argument(
            "--root", default=argparse.SUPPRESS, help="project root (default: current directory)"
        )
    return p


HANDLERS = {"discover": cmd_discover, "scan": cmd_scan, "show": cmd_show, "find": cmd_find, "digest": cmd_digest, "check": cmd_check,
            "lint": cmd_lint, "impact": cmd_impact, "deps": cmd_deps, "confirm": cmd_confirm,
            "models": cmd_models, "verify": cmd_verify}


@quiet_broken_pipe
def main(argv: list[str] | None = None) -> int:
    safe_stdio()
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        return HANDLERS[args.cmd](root, args)
    except (MapError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
