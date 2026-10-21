"""The map file (.flowguard/map.json): load, validate, save, and derived views.

The map is the project's DNA: components with plain-language responsibilities,
owned files, entrypoints, state, side effects, dependencies, tests and models.
Git is its history.  Each component's ``fingerprint`` (hash of the files it
owns, written by ``confirm``) is the "current pointer": when it no longer
matches, the description is stale and must be re-read and re-confirmed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_IGNORE, MAP_RELPATH, SCHEMA, SOURCE_EXTS, content_digest, is_test_file, matches_any, read_source
from .inventory import Inventory

TOP_KEYS = {"schema", "project", "layers", "ignore", "test_command", "test_commands", "components", "flows", "accepted_debts"}
COMPONENT_KEYS = {"id", "layer", "summary", "responsibilities", "files", "entrypoints", "state",
                  "side_effects", "depends_on", "tests", "models", "status", "fingerprint", "_hint"}
LIST_KEYS = ("responsibilities", "files", "entrypoints", "state", "side_effects", "depends_on", "tests", "models")
ID_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")


class MapError(Exception):
    """The map file is missing or invalid; the message says what to fix."""


def map_path(root: Path) -> Path:
    return root / MAP_RELPATH


def validate_map(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["map.json must contain a JSON object"]
    errors = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    errors += [f"unknown top-level key {k!r}" for k in sorted(set(data) - TOP_KEYS)]
    test_commands = data.get("test_commands", {})
    if not isinstance(test_commands, dict) or not all(isinstance(p, str) and isinstance(cmd, str) and cmd.strip()
                                                      for p, cmd in test_commands.items()):
        errors.append("test_commands must map test file patterns to nonempty command strings")
    comps = data.get("components")
    if not isinstance(comps, list):
        return errors + ["components must be a list"]
    layers = data.get("layers", [])
    if not isinstance(layers, list) or len(set(layers)) != len(layers):
        errors.append("layers must be a list of unique names (first = top, last = bottom)")
        layers = []
    seen: set[str] = set()
    for i, c in enumerate(comps):
        where = f"components[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{where} must be an object")
            continue
        errors += [f"{where}: unknown key {k!r}" for k in sorted(set(c) - COMPONENT_KEYS)]
        cid = c.get("id")
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
            errors.append(f"{where}.id must match [a-z0-9][a-z0-9_.-]*")
        elif cid in seen:
            errors.append(f"duplicate component id {cid!r}")
        else:
            seen.add(cid)
        if c.get("status") not in {"draft", "confirmed"}:
            errors.append(f"{where}.status must be 'draft' or 'confirmed'")
        errors += [f"{where}.{k} must be a list of strings" for k in LIST_KEYS
                   if not isinstance(c.get(k, []), list) or not all(isinstance(x, str) for x in c.get(k, []))]
        if c.get("layer") and layers and c["layer"] not in layers:
            errors.append(f"{where}.layer {c['layer']!r} is not one of layers {layers}")
    for i, flow in enumerate(data.get("flows", [])):
        if not isinstance(flow, dict) or not isinstance(flow.get("id"), str) or not isinstance(flow.get("steps", []), list):
            errors.append(f"flows[{i}] needs a string id and a list of steps 'component' or 'component:symbol'")
    for i, debt in enumerate(data.get("accepted_debts", [])):
        if not isinstance(debt, dict) or not debt.get("code") or not debt.get("reason"):
            errors.append(f"accepted_debts[{i}] needs at least 'code' and 'reason'")
    return errors


def load_map(root: Path) -> dict:
    path = map_path(root)
    if not path.is_file():
        raise MapError(f"no map at {path}; run 'python -m flowguard.map scan' first")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))   # editors on Windows may add a BOM
    except ValueError as exc:
        raise MapError(f"{path} is not valid JSON: {exc}") from exc
    errors = validate_map(data)
    if errors:
        raise MapError(f"invalid {path}:\n  " + "\n  ".join(errors))
    return data


def save_map(root: Path, data: dict) -> None:
    errors = validate_map(data)
    if errors:
        raise MapError("refusing to save an invalid map:\n  " + "\n  ".join(errors))
    path = map_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ignore_patterns(data: dict | None) -> list[str]:
    return DEFAULT_IGNORE + list((data or {}).get("ignore", []))


def component_files(comp: dict, inv: Inventory) -> list[str]:
    """Code matched by globs, plus exact registered non-ignored resource files."""
    pats = comp.get("files", [])
    exact = {p for p in pats if not any(char in p for char in "*?[")}
    candidates = sorted(set(inv.source) | (exact & set(inv.files)))
    return [f for f in candidates if matches_any(f, pats)
            and (Path(f).suffix in SOURCE_EXTS or f in exact)
            and (f in exact or not is_test_file(f))]


def owner_index(data: dict, inv: Inventory) -> tuple[dict[str, str], dict[str, list[str]]]:
    """(file -> first owning component id, file -> all owning ids)."""
    inv.set_explicit_sources([p for comp in data["components"] for p in comp.get("files", [])])
    owners: dict[str, list[str]] = defaultdict(list)
    for comp in data["components"]:
        for f in component_files(comp, inv):
            owners[f].append(comp["id"])
    return {f: ids[0] for f, ids in owners.items()}, dict(owners)


def fingerprint(root: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        try:
            h.update(f"{f}\0{content_digest(root / f)}\n".encode())
        except OSError:
            h.update(f"{f}\0missing\n".encode())
    return "sha256:" + h.hexdigest()


def is_stale(root: Path, comp: dict, inv: Inventory) -> bool:
    return comp.get("status") == "confirmed" and comp.get("fingerprint") != fingerprint(root, component_files(comp, inv))


def component_graph(data: dict, inv: Inventory) -> dict[str, set[str]]:
    """Component -> components it imports (from the real import graph)."""
    owner, _ = owner_index(data, inv)
    graph: dict[str, set[str]] = {c["id"]: set() for c in data["components"]}
    for f, targets in inv.file_deps.items():
        src = owner.get(f)
        if src:
            graph[src].update(owner[t] for t in targets if t in owner and owner[t] != src)
    return graph


def read_model_contract(path: Path) -> dict:
    """MODEL_ID / COMPONENTS / IMPLEMENTED_BY literals and defined hooks of a model file, without importing it."""
    tree = ast.parse(read_source(path))
    found: dict = {"functions": []}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in {"MODEL_ID", "COMPONENTS", "IMPLEMENTED_BY", "TESTED_BY", "NOT_MODELED"}:
            found[node.targets[0].id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name in {"build_explorer", "broken_variants", "conformance"}:
            found["functions"].append(node.name)
    for key in ("IMPLEMENTED_BY", "NOT_MODELED"):
        value = found.get(key, {})
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip()
                                                 for k, v in value.items()):
            raise ValueError(f"{key} must map anchors/names to nonempty strings")
    tested_by = found.get("TESTED_BY", {})
    if not isinstance(tested_by, dict) or not all(isinstance(k, str) and isinstance(v, (list, tuple))
            and all(isinstance(anchor, str) for anchor in v) for k, v in tested_by.items()):
        raise ValueError("TESTED_BY must map invariant names to lists of test anchors")
    return found


def dependency_evidence(data: dict, inv: Inventory) -> dict[str, set[str]]:
    """Actual imports plus named module literals and explicitly justified debts.

    Literal evidence validates declarations; it is not itself a caller edge.
    """
    graph = component_graph(data, inv)
    owner, _ = owner_index(data, inv)
    modules = {info.module: owner[path] for path, info in inv.py.items() if path in owner}
    symbols = {info.module: info.symbols for info in inv.py.values()}
    for path, info in inv.py.items():
        cid = owner.get(path)
        if cid is None:
            continue
        for literal in getattr(info, "string_literals", set()):
            # Exact module ("pkg.mod" or "pkg.mod:name") or "pkg.mod.symbol"; never truncate further.
            target = modules.get(literal.split(":", 1)[0])
            if target is None and ":" not in literal:
                base, _, name = literal.rpartition(".")
                if name in symbols.get(base, ()):
                    target = modules.get(base)
            if target is not None and target != cid:
                graph[cid].add(target)
    for debt in data.get("accepted_debts", []):
        if debt.get("code") == "dep_unused" and debt.get("component") in graph and debt.get("reason"):
            cid = debt["component"]
            for target in graph:
                if debt.get("contains") == target:
                    graph[cid].add(target)
    return graph


@dataclass(frozen=True)
class ModelEntry:
    id: str
    path: str
    kind: str                         # contract | runner


@dataclass(frozen=True)
class RegistryIssue:
    code: str
    path: str
    message: str


@dataclass
class ModelRegistry:
    entries: list[ModelEntry] = field(default_factory=list)
    issues: list[RegistryIssue] = field(default_factory=list)


def model_registry(root: Path, data: dict | None = None) -> ModelRegistry:
    """The single executable inventory: top-level contracts and declared runners.

    Paths outside these conventions are not silently counted as proof. Discovery
    only reads literals; importing and executing belongs to the proof runner.
    """
    if data is None:
        try:
            data = load_map(root)
        except MapError:
            data = {}
    referenced = {m for c in data.get("components", []) for m in c.get("models", [])}
    referenced |= {f["model"] for f in data.get("flows", []) if f.get("model")}
    base = root / ".flowguard/models"
    paths = {p.relative_to(root).as_posix() for p in base.glob("*.py") if not p.name.startswith("_")}
    registry = ModelRegistry()
    runners = {p.relative_to(root).as_posix()
               for p in (root / ".flowguard/verification/owners").glob("*/run_checks.py")}
    for rel in sorted(runners - referenced):
        registry.issues.append(RegistryIssue("model_unbound", rel,
                              "unregistered runner: add it to its owning component's models or remove it"))
    for directory in sorted((root / ".flowguard/models/owners").glob("*")):
        if directory.is_dir() and any(directory.glob("*.py")):
            runner = f".flowguard/verification/owners/{directory.name}/run_checks.py"
            if runner not in referenced:
                registry.issues.append(RegistryIssue("model_unbound", directory.relative_to(root).as_posix(),
                                      "unregistered owner model: add its runner to the owning component's models or remove it"))
    for rel in sorted(paths | referenced):
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            registry.issues.append(RegistryIssue("model_path_unsupported", rel,
                                  f"{rel}: model paths must stay inside the project"))
            continue
        path = root / rel
        if not path.is_file():
            registry.issues.append(RegistryIssue("model_missing", rel, f"model file {rel} missing"))
            continue
        if path.name == "run_checks.py" and rel in referenced:
            entry = ModelEntry(path.parent.name, rel, "runner")
        elif rel in paths:
            try:
                contract = read_model_contract(path)
                mid = contract.get("MODEL_ID")
                if not isinstance(mid, str) or not mid or "build_explorer" not in contract["functions"]:
                    raise ValueError("needs a nonempty string MODEL_ID and def build_explorer()")
                if not isinstance(contract.get("COMPONENTS", []), list) or not all(
                        isinstance(c, str) for c in contract.get("COMPONENTS", [])):
                    raise ValueError("COMPONENTS must be a list of component ids")
                anchors = contract.get("IMPLEMENTED_BY", {})
                if not isinstance(anchors, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                           for k, v in anchors.items()):
                    raise ValueError("IMPLEMENTED_BY must map block names to string anchors")
                entry = ModelEntry(mid, rel, "contract")
            except (OSError, SyntaxError, ValueError, TypeError) as exc:
                registry.issues.append(RegistryIssue("model_contract", rel, f"{rel}: {exc}"))
                continue
        else:
            registry.issues.append(RegistryIssue("model_path_unsupported", rel,
                                  f"{rel}: expected a top-level .flowguard/models/*.py contract or declared run_checks.py"))
            continue
        registry.entries.append(entry)
    by_id: dict[str, list[str]] = defaultdict(list)
    for entry in registry.entries:
        by_id[entry.id].append(entry.path)
    for mid, rels in sorted(by_id.items()):
        if len(rels) > 1:
            registry.issues.append(RegistryIssue("model_id_duplicate", rels[0],
                                  f"model id {mid!r} is shared by {', '.join(rels)}"))
    return registry
