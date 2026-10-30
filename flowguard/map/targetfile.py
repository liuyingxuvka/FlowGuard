"""Pure static target storage and map overlay, separate from proof execution."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import content_digest, git_paths, read_source, tokens
from .mapfile import COMPONENT_KEYS, ID_RE, MapError, model_registry, read_model_contract, validate_map

TARGET_RELDIR = ".flowguard/target"
TARGET_SCHEMA = "flowguard.target.v1"
TARGET_KEYS = {"schema", "goal", "components", "flows", "layers", "accepted_debts", "remove"}


@dataclass(frozen=True)
class Target:
    goal: str
    data: dict
    models: dict[str, str]
    remove: dict[str, set[str]]


@dataclass(frozen=True)
class TargetIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ModelView:
    """One operation's complete model namespace; logical paths keep their identity."""
    root: Path
    data: dict
    model_sources: dict[str, str]
    model_names: set[str]

    def resolve(self, logical: str) -> Path | None:
        if Path(logical).parts[:2] == (".flowguard", "models"):
            physical = self.model_sources.get(logical)
            return self.root / physical if physical is not None else None
        return self.root / logical

    def to_payload(self) -> dict:
        return {"root": str(self.root), "data": self.data, "model_sources": self.model_sources,
                "model_names": sorted(self.model_names)}

    @classmethod
    def from_payload(cls, payload: dict) -> ModelView:
        return cls(Path(payload["root"]).resolve(), payload["data"], dict(payload["model_sources"]),
                   set(payload["model_names"]))


def build_target_view(root: Path, current_data: dict, target: Target) -> ModelView:
    root = root.resolve()
    files = {p.name: p.relative_to(root).as_posix() for p in (root / ".flowguard/models").glob("*.py") if p.is_file()}
    names = {Path(filename).stem for filename in files.keys() | target.models.keys()}
    removed = {entry.path for entry in model_registry(root, current_data).entries
               if entry.id in target.remove["model"]}
    sources = {f".flowguard/models/{name}": physical for name, physical in files.items() if physical not in removed}
    # Applying replacements last also permits removing an old ID and supplying a
    # different ID in that same filename; the new source is not a tombstone.
    sources.update({f".flowguard/models/{name}": physical for name, physical in target.models.items()})
    view = ModelView(root, merge_target_map(current_data, target), sources, names)
    from .mapfile import model_digests
    view.data["model_digests"] = model_digests(root, view=view)
    return view


def load_target(root: Path) -> Target | None:
    directory = root / TARGET_RELDIR
    if not directory.exists():
        return None
    path = directory / "map.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise MapError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MapError(f"{path} must contain a JSON object")
    removed = {kind: set() for kind in ("component", "flow", "model", "entrypoint", "state", "side_effect", "responsibility")}
    for value in data.get("remove", []) if isinstance(data.get("remove", []), list) else []:
        if isinstance(value, str):
            kind, _, name = value.partition(":")
            if kind in removed and name:
                removed[kind].add(name)
    models = {p.name: p.relative_to(root).as_posix() for p in sorted((directory / "models").glob("*.py")) if p.is_file()}
    return Target(data.get("goal", ""), data, models, removed)


def model_helper_digests(root: Path) -> dict[str, str]:
    """Complete current helper source identities; missing keys record absence."""
    return {path.relative_to(root).as_posix(): content_digest(path)
            for path in sorted((root / ".flowguard/models").glob("_*.py")) if path.is_file()}


def target_helper_baseline(root: Path) -> dict[str, str] | None:
    """A captured complete helper set, or unknown for older/damaged target bases."""
    try:
        data = json.loads((root / TARGET_RELDIR / "base.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    helpers = (data.get("helpers") if isinstance(data, dict)
               and data.get("schema") == "flowguard.target-base.v1" else None)
    if not isinstance(helpers, dict):
        return None
    if any(not isinstance(path, str) or not path.startswith(".flowguard/models/_")
           or path.count("/") != 2 or not path.endswith(".py") or "\\" in path
           or not isinstance(digest, str) or len(digest) != 64
           or any(character not in "0123456789abcdef" for character in digest)
           for path, digest in helpers.items()):
        return None
    return helpers


def merge_target_map(current_data: dict, target: Target) -> dict:
    """Return an independent map; neither current nor target metadata is changed."""
    merged = copy.deepcopy(current_data)
    for plural, kind in (("components", "component"), ("flows", "flow")):
        replacements = {item["id"]: copy.deepcopy(item) for item in target.data.get(plural, [])}
        if kind == "component":
            for item in replacements.values():
                item["status"] = "draft"
                item.pop("fingerprint", None)
                item.pop("_hint", None)
        items = []
        for item in merged.get(plural, []):
            if item["id"] not in target.remove[kind]:
                items.append(replacements.pop(item["id"], item))
        merged[plural] = items + list(replacements.values())
    for key in ("layers", "accepted_debts"):
        if key in target.data:
            merged[key] = copy.deepcopy(target.data[key])
    return merged


def _removal_subjects(data, registry):
    subjects = {"component": {c["id"] for c in data["components"]},
                "flow": {f["id"] for f in data.get("flows", [])},
                "model": {entry.id for entry in registry.entries}}
    for kind, field in (("entrypoint", "entrypoints"), ("state", "state"), ("side_effect", "side_effects"),
                        ("responsibility", "responsibilities")):
        subjects[kind] = {value for component in data["components"] for value in component.get(field, [])}
    return subjects


def validate_target(root: Path, current_data: dict, target: Target, *,
                    allow_applied_removals: bool = False) -> list[TargetIssue]:
    """Strict target syntax/identities; missing removals are allowed only for artifact inspection.

    The inspection allowance keeps all syntax/duplicate/overlay checks and is
    never used to authorize an open target or promotion.
    """
    data, issues = target.data, []

    def invalid(message):
        issues.append(TargetIssue("target_invalid", message))

    if data.get("schema") != TARGET_SCHEMA:
        invalid(f"schema must be {TARGET_SCHEMA!r}")
    if not isinstance(target.goal, str) or not target.goal.strip():
        invalid("goal must be a nonempty sentence")
    for key in sorted(set(data) - TARGET_KEYS):
        invalid(f"unknown target key {key!r}")
    for plural, kind, keys in (("components", "component", COMPONENT_KEYS - {"status", "fingerprint", "_hint"}),
                               ("flows", "flow", {"id", "summary", "steps", "model"})):
        values = data.get(plural, [])
        if not isinstance(values, list):
            invalid(f"{plural} must be a list")
            continue
        seen = set()
        for index, item in enumerate(values):
            where = f"{plural}[{index}]"
            if not isinstance(item, dict):
                invalid(f"{where} must be an object")
                continue
            name = item.get("id")
            if not isinstance(name, str) or not ID_RE.fullmatch(name):
                invalid(f"{where}.id must match [a-z0-9][a-z0-9_.-]*")
            elif name in seen:
                invalid(f"duplicate {kind} id {name!r}")
            else:
                seen.add(name)
            for key in sorted(set(item) - keys):
                invalid(f"{where}: target entries cannot contain {key!r}")
            if isinstance(name, str) and name in target.remove[kind]:
                invalid(f"{kind}:{name} is both replaced and removed")
            if kind == "component" and (not isinstance(item.get("summary"), str) or not item["summary"].strip()
                    or not isinstance(item.get("responsibilities"), list) or not item["responsibilities"]
                    or not all(isinstance(rule, str) and rule.strip() for rule in item["responsibilities"])):
                issues.append(TargetIssue("target_component_incomplete", f"{where} needs summary and responsibilities"))
            if kind == "flow" and "model" in item and not isinstance(item["model"], str):
                invalid(f"{where}.model must be a string path")
            if kind == "flow" and (not isinstance(item.get("steps", []), list)
                    or not all(isinstance(step, str) for step in item.get("steps", []))):
                invalid(f"{where}.steps must be a list of strings")
            paths = item.get("models", []) if kind == "component" else [item["model"]] if item.get("model") else []
            if isinstance(paths, list):
                for path in paths:
                    if not isinstance(path, str) or not (path.startswith(".flowguard/models/")
                            and path.count("/") == 2 and path.endswith(".py") and "\\" not in path):
                        invalid(f"{where}: model paths must name the merged .flowguard/models/ location")
    for key in ("layers", "accepted_debts"):
        if key in data and not isinstance(data[key], list):
            invalid(f"{key} must be a list")
    if "layers" in data and isinstance(data["layers"], list) and not all(isinstance(v, str) for v in data["layers"]):
        invalid("layers must contain strings")
    registry = model_registry(root, current_data)
    current = _removal_subjects(current_data, registry)
    removed = data.get("remove", [])
    if not isinstance(removed, list):
        invalid("remove must be a list")
    else:
        seen = set()
        for value in removed:
            if not isinstance(value, str):
                invalid("remove entries must be kind:id strings")
                continue
            kind, separator, name = value.partition(":")
            if (not separator or kind not in current or not name
                    or name not in current[kind] and not allow_applied_removals):
                invalid(f"remove names no current node: {value!r}")
            elif value in seen:
                invalid(f"duplicate remove entry {value!r}")
            seen.add(value)
    target_ids = {}
    for filename, rel in target.models.items():
        if filename.startswith("_"):
            continue
        try:
            contract = read_model_contract(root / rel)
        except (OSError, SyntaxError, ValueError, TypeError) as exc:
            invalid(f"{rel}: {exc}")
            continue
        mid = contract.get("MODEL_ID")
        if isinstance(mid, str):
            if mid in target_ids:
                invalid(f"target model id {mid!r} is shared by {target_ids[mid]} and {filename}")
            target_ids[mid] = filename
            if any(entry.id == mid and Path(entry.path).name != filename and mid not in target.remove["model"]
                   for entry in registry.entries):
                issues.append(TargetIssue("target_model_id_clash", f"{rel}: model id {mid!r} belongs to another filename; "
                                          f"use the same filename, or add model:{mid} to remove"))
    if not issues:
        merged = merge_target_map(current_data, target)
        for error in validate_map(merged):
            invalid(error)
        for component in merged["components"]:
            if component.get("parent") in target.remove["component"]:
                invalid(f"cannot remove component {component['parent']!r} while child {component['id']!r} "
                        "still names it; remove or reparent the child")
    return issues


def target_node_changes(root: Path, current_data: dict, target: Target) -> dict[str, list[str]]:
    """Presence in the overlay means changed, even if its bytes still match today."""
    changes = {symbol: [] for symbol in ("+", "~", "-")}
    for plural, kind in (("components", "component"), ("flows", "flow")):
        current = {item["id"] for item in current_data.get(plural, [])}
        for item in target.data.get(plural, []):
            changes["~" if item["id"] in current else "+"].append(f"{kind}:{item['id']}")
    for filename, rel in target.models.items():
        if not filename.startswith("_"):
            contract = read_model_contract(root / rel)
            changes["~" if (root / ".flowguard/models" / filename).is_file() else "+"].append(
                "model:" + str(contract.get("MODEL_ID", Path(filename).stem)))
    for kind in ("component", "flow", "model"):
        names = target.remove[kind]
        changes["-"].extend(f"{kind}:{name}" for name in sorted(names))
    return {symbol: sorted(values) for symbol, values in changes.items()}


_VOLATILE = ("status", "fingerprint", "_hint")


def _comparable(data: dict) -> dict:
    out = copy.deepcopy({key: data.get(key, []) for key in ("components", "flows", "layers", "accepted_debts")})
    for component in out["components"]:
        for key in _VOLATILE:
            component.pop(key, None)
    return out


def target_is_noop(root: Path, current_data: dict, target: Target) -> bool:
    """The merged map equals the current one (ignoring status, fingerprint, _hint), nothing is removed,
    and every target model file has the same AST as the current file of that name (comments do not count)."""
    if any(target.remove.values()) or _comparable(merge_target_map(current_data, target)) != _comparable(current_data):
        return False
    for filename, physical in target.models.items():
        current = root / ".flowguard/models" / filename
        try:
            if not current.is_file() or ast.dump(ast.parse(read_source(root / physical))) != \
                    ast.dump(ast.parse(read_source(current))):
                return False
        except (OSError, SyntaxError, ValueError):
            return False
    return True


@dataclass(frozen=True)
class TargetSeam:
    target: Target | None
    has_git: bool
    noop: bool
    committed: bool
    missing_indexed: tuple[str, ...]
    removals_fulfilled: bool = False

    @property
    def already_promoted(self) -> bool:
        return self.committed and (self.noop or self.removals_fulfilled)


def target_seam(root: Path, current_data: dict) -> TargetSeam:
    """Inspect actual current/target and read-only index/HEAD facts, never a merged view."""
    prefix = TARGET_RELDIR + "/"
    has_git, indexed, committed = False, set(), set()
    try:
        indexed = set(git_paths(root, "ls-files", "--cached", "-z", "--", TARGET_RELDIR))
        has_git = True
    except (OSError, subprocess.CalledProcessError):
        pass
    if has_git:
        try:
            committed = set(git_paths(root, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", TARGET_RELDIR))
        except (OSError, subprocess.CalledProcessError):
            pass  # An unborn repository still has a real index.
    missing = tuple(sorted(path for path in indexed if path.startswith(prefix)
                           and not (root / path).exists() and not (root / path).is_symlink()))
    target, noop, fulfilled = None, False, False
    try:
        target = load_target(root)
        if target is not None and not validate_target(root, current_data, target):
            noop = target_is_noop(root, current_data, target)
        elif target is not None and indexed & committed and any(target.remove.values()):
            subjects = _removal_subjects(current_data, model_registry(root, current_data))
            absent = all(not values & subjects[kind] for kind, values in target.remove.items())
            if absent and not validate_target(root, current_data, target, allow_applied_removals=True):
                cleared = Target(target.goal, {**target.data, "remove": []}, target.models,
                                 {kind: set() for kind in target.remove})
                fulfilled = target_is_noop(root, current_data, cleared)
    except MapError:
        pass  # Existing invalid-target diagnostics retain their owner.
    return TargetSeam(target, has_git, noop, bool(indexed & committed), missing, fulfilled)


def target_promise_changes(current_data: dict, merged_data: dict, target: Target) -> list[tuple[str, str]]:
    """(field, first item) for each of entrypoints, state and side effects whose project-wide set the
    target changes, apart from items explicitly retired in remove (owner_dropped governs those)."""
    out = []
    for kind, field in (("entrypoint", "entrypoints"), ("state", "state"), ("side_effect", "side_effects")):
        def identity(value):
            return value if kind == "entrypoint" else frozenset(tokens(value))

        before = {identity(v): v for c in current_data["components"] for v in c.get(field, [])}
        after = {identity(v): v for c in merged_data["components"] for v in c.get(field, [])}
        retired = {identity(v) for v in target.remove.get(kind, set())}
        differ = sorted({**before, **after}[key] for key in (before.keys() ^ after.keys()) - retired)
        if differ:
            out.append((field, differ[0]))
    return out
