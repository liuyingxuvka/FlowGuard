"""The map file (.flowguard/map.json): load, validate, save, and derived views.

The map is the project's DNA: components with plain-language responsibilities,
owned files, entrypoints, state, side effects, dependencies, tests and models.
Git is its history.  Each component's ``fingerprint`` (hash of the files it
owns, written by ``confirm``) is the "current pointer": when it no longer
matches, the description is stale and must be re-read and re-confirmed.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_IGNORE, MAP_RELPATH, SCHEMA, SOURCE_EXTS, content_digest, normalize_newlines, is_test_file, matches_any, read_source
from .inventory import Inventory

FINGERPRINT_FORMAT = 2

TOP_KEYS = {"large_test_seconds", "large_model_seconds", "import_roots", "schema", "project", "layers", "ignore", "test_command", "test_commands", "components", "flows", "accepted_debts", "fingerprint_format", "model_digests"}
COMPONENT_KEYS = {"id", "layer", "summary", "responsibilities", "files", "entrypoints", "state",
                  "side_effects", "depends_on", "tests", "models", "status", "fingerprint", "_hint", "parent"}
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
    fmt = data.get("fingerprint_format", 1)
    if type(fmt) is not int or fmt not in (1, FINGERPRINT_FORMAT):
        errors.append(f"fingerprint_format {fmt} is newer than this FlowGuard ({FINGERPRINT_FORMAT}); install a newer FlowGuard"
                      if type(fmt) is int and fmt > FINGERPRINT_FORMAT else f"fingerprint_format must be 1 or {FINGERPRINT_FORMAT}")
    digests = data.get("model_digests", {})
    if not isinstance(digests, dict) or not all(isinstance(k, str) and k.startswith(".flowguard/models/")
            and k.count("/") == 2 and "\\" not in k and k.endswith(".py") and not Path(k).name.startswith("_")
            and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for k, v in digests.items()):
        errors.append("model_digests must map model paths to sha256 strings")
    import math
    limit=data.get('large_model_seconds',10)
    if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<=0:
        errors.append('large_model_seconds must be a positive number')
    limit=data.get('large_test_seconds',60)
    if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<=0:
        errors.append('large_test_seconds must be a positive number')
    roots = data.get("import_roots", [])
    if not isinstance(roots, list) or not all(isinstance(value, str) and value and not value.startswith("/")
            and ".." not in value.split("/") and "\\" not in value for value in roots):
        errors.append("import_roots must be a list of nonempty relative POSIX paths without '..'")
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
        if "parent" in c and (not isinstance(c["parent"], str) or not ID_RE.fullmatch(c["parent"])):
            errors.append(f"{where}.parent must name a component id")
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
        if isinstance(debt, dict) and "members" in debt and (
                not isinstance(debt["members"], list) or not all(isinstance(x, str) for x in debt["members"])):
            errors.append(f"accepted_debts[{i}].members must be a list of strings")
    return errors


def load_map(root: Path) -> dict:
    path = map_path(root)
    if not path.is_file():
        raise MapError(f"no map at {path}; run python -m flowguard map scan first "
                       "(references/first_map.md in the FlowGuard skill explains the first map)")
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
    normalized = {**data, "components": [
        {**c, "depends_on": sorted(set(c["depends_on"]))} if "depends_on" in c else c
        for c in data["components"]]}
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ignore_patterns(data: dict | None) -> list[str]:
    return DEFAULT_IGNORE + list((data or {}).get("ignore", []))


def inventory_memo(inv: Inventory, name: str, depends_on=()) -> dict:
    """Content-dependent working data for this inventory only; never persisted."""
    memos = inv.__dict__.setdefault('_flowguard_memo', {})
    dependencies = inv.__dict__.setdefault('_flowguard_memo_dependencies', {})
    current = tuple(depends_on)
    previous = dependencies.get(name)
    if previous is None or not (len(previous) == len(current) and
            all(left is right for left, right in zip(previous, current))):
        if previous is None or previous != current:
            memos[name] = {}
        dependencies[name] = current
    return memos.setdefault(name, {})


def component_files(comp: dict, inv: Inventory) -> list[str]:
    """Return a fresh file list, computing one immutable result per component pattern."""
    memo = inventory_memo(inv, 'component_files', (inv.source, inv.files))
    key = tuple(comp.get('files', ()))
    if key not in memo:
        memo[key] = tuple(_component_files(comp, inv))
    return list(memo[key])


def _component_files(comp: dict, inv: Inventory) -> list[str]:
    """Code matched by globs, plus exact registered non-ignored resource files."""
    pats = comp.get("files", [])
    exact = {p for p in pats if not any(char in p for char in "*?[")}
    candidates = sorted(set(inv.source) | (exact & set(inv.files)))
    return [f for f in candidates if matches_any(f, pats)
            and (Path(f).suffix in SOURCE_EXTS or f in exact)
            and (f in exact or not is_test_file(f))]


def component_subtree(data: dict, component: str) -> list[dict]:
    """Derived containment only; never add descendant files to direct ownership."""
    by_id = {c["id"]: c for c in data["components"]}
    children = defaultdict(list)
    for comp in data["components"]:
        children[comp.get("parent")].append(comp["id"])
    pending, seen, result = [component], set(), []
    while pending:
        cid = pending.pop()
        if cid not in by_id or cid in seen:
            continue
        seen.add(cid)
        result.append(by_id[cid])
        pending.extend(reversed(children.get(cid, [])))
    return result


def component_ancestors(data: dict, component: str) -> list[str]:
    """Component containment is distinct from a model's PARENT relationship."""
    by_id = {c["id"]: c for c in data["components"]}
    result, seen = [], {component}
    while component in by_id and (parent := by_id[component].get("parent")) in by_id and parent not in seen:
        result.append(parent)
        seen.add(parent)
        component = parent
    return result


def component_scope(data: dict, component: dict) -> dict:
    """View/model scope: ordered unions, without modifying the map or fingerprints."""
    members = component_subtree(data, component["id"]) or [component]
    return {**component, **{key: list(dict.fromkeys(value for member in members for value in member.get(key, [])))
                            for key in LIST_KEYS}}


def flow_step_parts(step: str) -> tuple[str, str, str | None]:
    """``component``, ``component:Symbol`` or ``component:Symbol reads <file>`` -> (component, symbol, file).

    ``file`` is None for a call-chain step; a ``reads`` step is a separate command that reads a file an
    earlier step wrote (an empty string when nothing follows ``reads``).
    """
    head, separator, file = step.partition(" reads ")
    component, _, symbol = head.partition(":")
    return component, symbol, (file.strip() if separator else None)


def component_order(data: dict, identities: set[str] | None = None) -> list[tuple[dict, int]]:
    """Parent-before-child view order, finite even for an invalid parent cycle."""
    visible = {c["id"] for c in data["components"]} if identities is None else identities
    by_id = {c["id"]: c for c in data["components"] if c["id"] in visible}
    children = defaultdict(list)
    for comp in by_id.values():
        children[comp.get("parent")].append(comp["id"])
    roots = [cid for cid, comp in by_id.items() if comp.get("parent") not in by_id]
    result, seen = [], set()
    for root in [*roots, *by_id]:
        pending = [(root, 0)]
        while pending:
            cid, depth = pending.pop()
            if cid in seen:
                continue
            seen.add(cid)
            result.append((by_id[cid], depth))
            pending.extend((child, depth + 1) for child in reversed(children.get(cid, [])))
    return result


def owner_index(data: dict, inv: Inventory) -> tuple[dict[str, str], dict[str, list[str]]]:
    """(file -> first owning component id, file -> all owning ids)."""
    inv.set_explicit_sources([p for comp in data["components"] for p in comp.get("files", [])])
    owners: dict[str, list[str]] = defaultdict(list)
    for comp in data["components"]:
        for f in component_files(comp, inv):
            owners[f].append(comp["id"])
    return {f: ids[0] for f, ids in owners.items()}, dict(owners)


def _release_neutral(path: Path, content: bytes) -> bytes:
    """Mask only release declarations, preserving every other normalized byte."""
    if path.name == "VERSION":
        return b"<version>\n"
    if path.suffix == ".py" and b"__version__" in content:
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError, UnicodeError):
            return content
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
                continue
            value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if value.lineno != value.end_lineno:
                return content
            lines = content.splitlines(keepends=True)
            offset = 3 if value.lineno == 1 and content.startswith(b"\xef\xbb\xbf") else 0
            line = lines[value.lineno - 1]
            lines[value.lineno - 1] = line[:value.col_offset + offset] + b'"<version>"' + line[value.end_col_offset + offset:]
            return b"".join(lines)
    if path.name == "pyproject.toml":
        lines, table = [], ""
        for line in content.splitlines(keepends=True):
            stripped = line.split(b"#", 1)[0].strip()
            if stripped.startswith(b"["):
                table = stripped.strip(b"[]").strip()
            if table == b"project":
                match = re.match(rb"^(\s*version\s*=\s*)(['\"])[^'\"\n]*\2", line)
                if match:
                    line = match[1] + b'"<version>"' + line[match.end():]
            lines.append(line)
        return b"".join(lines)
    return content


def format_guard(before: str, after: str) -> str | None:
    """Name changes to the stored-fingerprint formula when its format is unchanged.

    Changes in dependencies such as normalize_newlines remain covered by the
    executable release-neutral model; this guard compares only these two owners.
    """
    from .inventory import function_digests, syntax_tree

    def format_value(text):
        for node in syntax_tree(text).body:
            value = None
            if isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id == "FINGERPRINT_FORMAT" for item in node.targets):
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "FINGERPRINT_FORMAT":
                value = node.value
            if isinstance(value, ast.Constant) and type(value.value) is int:
                return value.value
        return None

    try:
        old_format, new_format = format_value(before), format_value(after)
        if old_format is None or old_format != new_format:
            return None
        old = function_digests(before)["functions"]
        new = function_digests(after)["functions"]
    except (SyntaxError, ValueError, TypeError):
        return None
    changed = [name for name in ("fingerprint", "_release_neutral") if old.get(name) != new.get(name)]
    if not changed:
        return None
    return ("fingerprint_format_unchanged: the target changes flowguard/map/mapfile.py:" + ", ".join(changed)
            + f", which computes stored fingerprints, but FINGERPRINT_FORMAT stays {new_format}; "
            "if a stored fingerprint changes value, bump FINGERPRINT_FORMAT and give component_state a migrate path "
            "for the old format; otherwise say in the commit message that stored fingerprints keep their value")


def fingerprint(root: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        try:
            content = _release_neutral(root / f, normalize_newlines((root / f).read_bytes()))
            digest = hashlib.sha256(content).hexdigest()
            h.update(f"{f}\0{digest}\n".encode())
        except OSError:
            h.update(f"{f}\0missing\n".encode())
    return "sha256:" + h.hexdigest()


def component_state(root: Path, comp: dict, inv: Inventory, data: dict) -> str:
    """Distinguish a one-time formula migration from an actual source edit."""
    files = component_files(comp, inv)
    if comp.get("fingerprint") == fingerprint(root, files):
        return "current"
    if data.get("fingerprint_format", 1) < FINGERPRINT_FORMAT:
        legacy = hashlib.sha256()
        for path in sorted(files):
            try:
                legacy.update(f"{path}\0{content_digest(root / path)}\n".encode())
            except OSError:
                legacy.update(f"{path}\0missing\n".encode())
        if comp.get("fingerprint") == "sha256:" + legacy.hexdigest():
            return "migrate"
    return "stale"


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


def top_level_imports(tree: ast.Module) -> list[str]:
    """First module segments of ordinary, absolute imports at module scope."""
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return sorted(set(names))


def local_imports(tree: ast.Module) -> list[str]:
    """First module segments of absolute imports anywhere below module scope (functions, if blocks)."""
    top = {id(node) for node in tree.body}
    names = []
    for node in ast.walk(tree):
        if id(node) in top:
            continue
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return sorted(set(names))


_MODEL_CONTRACT_CACHE: dict[tuple[str, str], tuple[dict, ast.Module]] = {}


def read_model_contract(path: Path) -> dict:
    """MODEL_ID / COMPONENTS / IMPLEMENTED_BY literals and defined hooks of a model file, without importing it."""
    raw = path.read_bytes()
    cache_key = (str(path.resolve()), hashlib.sha256(raw).hexdigest())
    if cache_key in _MODEL_CONTRACT_CACHE:
        return copy.deepcopy(_MODEL_CONTRACT_CACHE[cache_key][0])
    tree = ast.parse(read_source(path, data=raw))
    found: dict = {"functions": [], "imports": top_level_imports(tree), "local_imports": local_imports(tree)}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in {"MODEL_ID", "COMPONENTS", "IMPLEMENTED_BY", "USES", "TESTED_BY", "NOT_MODELED",
                                           "PARENT", "OUTPUTS", "HANDOFF", "READS_PARENT", "KEEPS", "DISPATCH"}:
            found[node.targets[0].id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name in {"build_explorer", "broken_variants", "conformance",
                                                               "project_parent_state"}:
            found["functions"].append(node.name)
    if "PARENT" in found and not (isinstance(found["PARENT"], str) and found["PARENT"].strip()):
        raise ValueError("PARENT must be a nonempty string")
    for key in ("IMPLEMENTED_BY", "NOT_MODELED"):
        value = found.get(key, {})
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip()
                                                 for k, v in value.items()):
            raise ValueError(f"{key} must map anchors/names to nonempty strings")
    uses = found.get("USES", {})
    if not isinstance(uses, dict) or not all(isinstance(name, str) and name.strip()
            and isinstance(anchor, str) and anchor.partition(":")[0].strip() and anchor.partition(":")[1]
            and anchor.partition(":")[2].strip() for name, anchor in uses.items()):
        raise ValueError("USES must map names to nonempty 'path:Symbol' strings")
    tested_by = found.get("TESTED_BY", {})
    if not isinstance(tested_by, dict) or not all(isinstance(k, str) and isinstance(v, (list, tuple))
            and all(isinstance(anchor, str) for anchor in v) for k, v in tested_by.items()):
        raise ValueError("TESTED_BY must map invariant names to lists of test anchors")
    scalar = lambda value: type(value) in (str, int, bool)
    outputs = found.get("OUTPUTS")
    if "OUTPUTS" in found and (not isinstance(outputs, dict) or not all(isinstance(k, str) and isinstance(v, tuple)
            and bool(v) and all(scalar(item) for item in v) for k, v in outputs.items())):
        raise ValueError("OUTPUTS must map State field names to nonempty tuples of str, int or bool values")
    handoff = found.get("HANDOFF")
    if "HANDOFF" in found:
        if not isinstance(handoff, dict) or not all(isinstance(k, str) and isinstance(v, dict) for k, v in handoff.items()):
            raise ValueError("HANDOFF must map producer ids to {output key: field name or (field or None, {value: value or None})}")
        for producer, keys in handoff.items():
            for key, item in keys.items():
                valid = isinstance(key, str) and (isinstance(item, str) or isinstance(item, tuple) and len(item) == 2
                    and (item[0] is None or isinstance(item[0], str)) and isinstance(item[1], dict)
                    and all(scalar(k) and (v is None or scalar(v)) for k, v in item[1].items()))
                if not valid:
                    raise ValueError(f"HANDOFF['{producer}']['{key}'] must be a field name or a 2-tuple (field or None, value map)")
    for key, wording in (("READS_PARENT", "parent State field names"), ("KEEPS", "State field names")):
        if key in found and not (isinstance(found[key], tuple) and all(isinstance(n, str) for n in found[key])):
            raise ValueError(f"{key} must be a tuple of {wording}")
    dispatch = found.get("DISPATCH")
    if "DISPATCH" in found:
        if not isinstance(dispatch, dict) or len(dispatch) != 1 or not all(isinstance(k, str) for k in dispatch):
            raise ValueError("DISPATCH must map one State field name to {alternative: child model id}")
        for selector, alternatives in dispatch.items():
            if not isinstance(alternatives, dict) or not all(scalar(k) and isinstance(v, str) and v for k, v in alternatives.items()):
                raise ValueError(f"DISPATCH['{selector}'] must map alternatives to model ids")
    from .port import model_port
    found["port"] = model_port(tree)
    _MODEL_CONTRACT_CACHE[cache_key] = (copy.deepcopy(found), tree)
    return found


def read_model_syntax(path: Path, *, copy_tree=True):
    """Reuse parsed source; callers get an independent tree unless borrowing it read-only."""
    raw=path.read_bytes()
    key=(str(path.resolve()),hashlib.sha256(raw).hexdigest())
    if key not in _MODEL_CONTRACT_CACHE:
        read_model_contract(path)
    return copy.deepcopy(_MODEL_CONTRACT_CACHE[key][1]) if copy_tree else _MODEL_CONTRACT_CACHE[key][1]


def dependency_evidence(data: dict, inv: Inventory, raw: dict | None = None) -> dict[str, set[str]]:
    """Actual imports plus import-like literals, injected collaborators and explicitly justified debts.

    Literal evidence validates declarations; it is not itself a caller edge. ``raw`` (discovery) adds
    calls through constructor-injected attributes; they never enter the import graph.
    """
    graph = component_graph(data, inv)
    owner, _ = owner_index(data, inv)
    modules = {info.module: owner[path] for path, info in inv.py.items() if path in owner}
    symbols = {info.module: info.symbols for info in inv.py.values()}
    for path, info in inv.py.items():
        cid = owner.get(path)
        if cid is None:
            continue
        import_literals = getattr(info, "import_literals", set()) | set(info.lazy_exports.values())
        for literal in import_literals | getattr(info, "string_literals", set()):
            # Bare module names count only in import calls or a lazy export table.
            target = modules.get(literal.split(":", 1)[0]) if literal in import_literals or ":" in literal else None
            if target is None and ":" not in literal:
                base, _, name = literal.rpartition(".")
                if name in symbols.get(base, ()):
                    target = modules.get(base)
            if target is not None and target != cid:
                graph[cid].add(target)
    for source, targets in (raw or {}).get("injected_edges", {}).items():
        cid = owner.get(source.partition("#")[0])
        for target in targets:
            other = owner.get(target.partition("#")[0])
            if cid is not None and other is not None and other != cid:
                graph[cid].add(other)
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
    kind: str = field(default="contract", init=False)


@dataclass(frozen=True)
class RegistryIssue:
    code: str
    path: str
    message: str


@dataclass
class ModelRegistry:
    entries: list[ModelEntry] = field(default_factory=list)
    issues: list[RegistryIssue] = field(default_factory=list)


def resolve_model_path(root: Path, logical: str, *, view=None) -> Path | None:
    """Resolve a canonical model path without falling back outside a supplied view."""
    return root / logical if view is None else view.resolve(logical)


def model_registry(root: Path, data: dict | None = None, *, view=None) -> ModelRegistry:
    """The single executable inventory of contract models.

    Paths outside these conventions are not silently counted as proof. Discovery
    only reads literals; importing and executing belongs to the proof runner.
    """
    if data is None:
        if view is not None:
            data = view.data
        else:
            try:
                data = load_map(root)
            except MapError:
                data = {}
    referenced = {m for c in data.get("components", []) for m in c.get("models", [])}
    referenced |= {f["model"] for f in data.get("flows", []) if f.get("model")}
    base = root / ".flowguard/models"
    paths = ({rel for rel in view.model_sources
              if Path(rel).parent.as_posix() == ".flowguard/models" and Path(rel).suffix == ".py"
              and not Path(rel).name.startswith("_")}
             if view is not None else
             {p.relative_to(root).as_posix() for p in base.glob("*.py") if not p.name.startswith("_")})
    registry = ModelRegistry()
    for rel in sorted(paths | referenced):
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            registry.issues.append(RegistryIssue("model_path_unsupported", rel,
                                  f"{rel}: model paths must stay inside the project"))
            continue
        path = resolve_model_path(root, rel, view=view)
        if path is None or not path.is_file():
            registry.issues.append(RegistryIssue("model_missing", rel, f"model file {rel} missing"))
            continue
        if rel in paths:
            try:
                contract = read_model_contract(path)
                mid = contract.get("MODEL_ID")
                if not isinstance(mid, str) or not mid or "build_explorer" not in contract["functions"]:
                    raise ValueError("needs a nonempty string MODEL_ID and def build_explorer()")
                if mid == "system":
                    raise ValueError("MODEL_ID 'system' is reserved for the root node")
                if not isinstance(contract.get("COMPONENTS", []), list) or not all(
                        isinstance(c, str) for c in contract.get("COMPONENTS", [])):
                    raise ValueError("COMPONENTS must be a list of component ids")
                anchors = contract.get("IMPLEMENTED_BY", {})
                if not isinstance(anchors, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                           for k, v in anchors.items()):
                    raise ValueError("IMPLEMENTED_BY must map block names to string anchors")
                entry = ModelEntry(mid, rel)
            except (OSError, SyntaxError, ValueError, TypeError) as exc:
                registry.issues.append(RegistryIssue("model_contract", rel, f"{rel}: {exc}"))
                continue
        else:
            registry.issues.append(RegistryIssue("model_path_unsupported", rel,
                                  f"{rel}: expected a top-level .flowguard/models/*.py contract"))
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


def model_digests(root: Path, *, view=None) -> dict[str, str]:
    """Canonical source byte identities; helpers and execution verdicts are excluded."""
    sources = (view.model_sources if view is not None else
               {p.relative_to(root).as_posix(): p.relative_to(root).as_posix()
                for p in (root / ".flowguard/models").glob("*.py") if p.is_file()})
    result = {}
    for logical in sorted(sources):
        if Path(logical).name.startswith("_") or not logical.endswith(".py"):
            continue
        path = view.resolve(logical) if view is not None else root / logical
        if path is not None and path.is_file():
            result[logical] = content_digest(path)
    return result


def process_model_reason(data, contract):
    """An explicit no-code debt applies only until implementation anchors exist."""
    if contract.get("IMPLEMENTED_BY"):
        return ""
    return next((debt.get("reason", "") for debt in data.get("accepted_debts", [])
                 if debt.get("code") == "model_anchor_missing" and
                 debt.get("component") == contract.get("MODEL_ID")), "")
