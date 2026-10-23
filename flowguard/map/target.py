"""Start, extend and drop one target draft without running a model or code check."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import stat
import sys

from .inventory import build_inventory
from .mapfile import MapError, ignore_patterns, load_map, model_registry, read_model_contract
from .targetfile import TARGET_RELDIR, TARGET_SCHEMA, load_target, validate_target
from .tree import build_tree


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
    for command in (start, add, drop):
        command.add_argument("--root", default=argparse.SUPPRESS)
    return parser


def _save(root: Path, data: dict) -> None:
    (root / TARGET_RELDIR / "map.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _remove_readonly(function, path, info):
    if not isinstance(info[1], PermissionError):
        raise info[1]
    os.chmod(path, stat.S_IWRITE)
    function(path)


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
        contract = read_model_contract(root / entry.path)
        for helper in contract["imports"]:
            if helper.startswith("_") and (root / ".flowguard/models" / f"{helper}.py").is_file():
                print(f"note: it imports {helper}; copy .flowguard/models/{helper}.py into "
                      ".flowguard/target/models/ only if the target changes it")
        tree = build_tree(root, data, build_inventory(root, ignore_patterns(data)))
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    root = Path(args.root).resolve()
    try:
        data = load_map(root)
        target = load_target(root)
        if args.command == "start":
            if target is not None:
                raise MapError(f'a target already exists: "{target.goal}"; promote it (python -m flowguard target promote) '
                               'or drop it (python -m flowguard target drop --yes)')
            if not args.goal.strip():
                raise MapError("the goal must be a nonempty sentence")
            directory = root / TARGET_RELDIR
            directory.mkdir(parents=True)
            (directory / "models").mkdir()
            _save(root, dict(schema=TARGET_SCHEMA, goal=args.goal, components=[], flows=[], remove=[]))
            print(f'target started: "{args.goal}"')
            print("next: python -m flowguard target add <component-or-model-id>, edit the files under "
                  ".flowguard/target/, then python -m flowguard target check")
            return 0
        if target is None:
            raise MapError('no target; start one with python -m flowguard target start "<goal>"')
        if args.command == "drop":
            directory = root / TARGET_RELDIR
            if not args.yes:
                count = sum(path.is_file() for path in directory.rglob("*"))
                print(f'would delete .flowguard/target/ ("{target.goal}", {count} file(s)); re-run with --yes')
                return 1
            shutil.rmtree(directory, onerror=_remove_readonly)
            print(f'dropped target "{target.goal}"')
            return 0
        problems = validate_target(root, data, target)
        if problems:
            raise MapError("; ".join(f"{issue.code}: {issue.message}" for issue in problems))
        _add(root, data, target, args.node)
        return 0
    except (MapError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
