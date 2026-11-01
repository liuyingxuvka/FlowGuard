"""Read-only source views over the shared inventory and discovery facts."""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .common import normalize_newlines, read_source, render_advice
from .discover import discover_inventory, function_spans, literal_sites, reachable_functions
from .inventory import build_inventory, function_digests, syntax_tree
from .mapfile import MapError, ignore_patterns, load_map, map_path, model_registry, owner_index, read_model_contract
from .records import change_records
from .requests import owner_words


def _git(root, *args, input=None):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, input=input)


@contextmanager
def _source(root, at):
    if at is None:
        result = _git(root, "rev-parse", "HEAD")
        yield root, result.stdout.decode().strip() if result.returncode == 0 else None
        return
    result = _git(root, "rev-parse", "--verify", "--end-of-options", str(at) + "^{commit}")
    if result.returncode:
        raise ValueError("unknown Git source reference: " + str(at))
    revision = result.stdout.decode().strip()
    listing = _git(root, "ls-tree", "-rz", revision)
    if listing.returncode:
        raise ValueError("cannot read Git source reference: " + str(at))
    rows = []
    for row in listing.stdout.split(b"\0"):
        if row:
            description, path = row.split(b"\t", 1)
            mode, kind, oid = description.split()
            if kind == b"blob":
                rows.append((mode, oid, Path(os.fsdecode(path))))
    blobs = _git(root, "cat-file", "--batch", input=b"".join(oid + b"\n" for _, oid, _ in rows))
    if blobs.returncode:
        raise ValueError("cannot read Git source blobs: " + str(at))
    with tempfile.TemporaryDirectory(prefix="flowguard-static-ref-") as directory:
        destination, bodies, links = Path(directory), io.BytesIO(blobs.stdout), []
        for mode, oid, relative in rows:
            header = bodies.readline().split()
            if len(header) != 3 or header[:2] != [oid, b"blob"]:
                raise ValueError("Git source blob is unavailable: " + str(relative))
            body = bodies.read(int(header[2]))
            bodies.read(1)
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if mode == b"120000":
                links.append((path, os.fsdecode(body)))
            else:
                path.write_bytes(body)
        for path, target in links:
            if (path.parent / target).resolve().is_relative_to(destination):
                path.symlink_to(target)
        yield destination, revision


DISPLAY_ROWS = 10  # rows per list in the default where output; --all prints every row


def bound(rows, label, omitted, *, all_rows=False, limit=DISPLAY_ROWS):
    """The first ``limit`` rows; how many were left out is added to ``omitted[label]``."""
    rows = list(rows)
    if all_rows or len(rows) <= limit:
        return rows
    omitted[label] = omitted.get(label, 0) + len(rows) - limit
    return rows[:limit]


def omitted_line(omitted, order=None):
    """One line with the counts a bounded view left out, or None when it showed everything."""
    if not omitted:
        return None
    return "omitted: " + ", ".join(f"{count} {label}" for label, count in omitted.items()) + (" · shown first: " + order if order else "")


def _map(root):
    """No map.json is a normal project state; a map that cannot be read is reported."""
    if not map_path(root).is_file():
        return {"components": [], "flows": []}, []
    try:
        return load_map(root), []
    except MapError as exc:
        return {"components": [], "flows": []}, [str(exc)]


def _writes_cache(root, at):
    """Parse caches go only into an adopted project's own .flowguard/cache, never for a Git reference."""
    return at is None and (Path(root) / ".flowguard").is_dir()


def _legacy(root, data):
    bindings, names, unknown = defaultdict(list), set(), []
    for entry in model_registry(root, data).entries:
        names.update((entry.id, entry.path, Path(entry.path).stem))
        if entry.kind != "contract":
            continue
        try:
            contract = read_model_contract(root / entry.path)
        except (OSError, ValueError, SyntaxError, TypeError) as exc:
            unknown.append(entry.path + ": " + str(exc))
            continue
        for anchor, target in contract.get("IMPLEMENTED_BY", {}).items():
            path, separator, symbol = target.partition(":")
            if separator:
                bindings[path + "#" + symbol].append({"model": entry.id, "anchor": anchor, "path": entry.path,
                    "kind": "declared legacy model binding", "tests": contract.get("TESTED_BY", {}).get(anchor, [])})
    return bindings, names, unknown


def _entries(raw):
    rows = []
    for path, file in raw["files"].items():
        for item in file.get("entrypoints", []):
            roots = item.get("handlers")
            if roots is None:
                roots = [] if item.get("via") == "argparse" else [path + "#" + item["symbol"]]
            roots = [value for value in roots if value.partition("#")[2] in raw["files"].get(value.partition("#")[0], {}).get("functions", {})]
            rows.append({**item, "path": path, "id": path + "#" + item["symbol"] + "@" + str(item.get("line", 0)) + ":" + item["kind"] + ":" + item["name"], "roots": roots,
                         "reach_state": "resolved static routes" if roots else "handler binding unknown"})
    return sorted(rows, key=lambda row: (row["path"], row.get("line", 0), row["kind"], row["name"]))


def _match(name, value):
    if name == value:
        return True
    return value.endswith(("#" + name, ":" + name, "." + name))


def _anchor(name):
    return name.replace(".py:", ".py#", 1)


def _runtime(execution, identifier):
    if not execution or execution.get("state") != "recorded":
        return {"state": (execution or {}).get("state", "not_recorded"), "tests": "not recorded in this clone"}
    coverage = execution.get("coverage")
    hit = coverage.get("hit_functions") if isinstance(coverage, dict) else None
    test_reach = execution.get("test_reach", {})
    tests = test_reach.get(identifier)
    return {"state": "recorded", "shipped_observed": identifier in hit if isinstance(hit, list) else None,
            "tests": tests if tests is not None else "not recorded for this function",
            "scope": execution.get("test_reach_scope", "supplied validated execution facts")}


def _changed_since(root, receipt, function, memo):
    key = (receipt, function["path"])
    if key not in memo:
        commit = _git(root, "log", "--diff-filter=A", "--format=%H", "--", ".flowguard/changes/" + receipt + ".json")
        revision = commit.stdout.splitlines()[-1].decode() if commit.returncode == 0 and commit.stdout.splitlines() else None
        blob = _git(root, "show", revision + ":" + function["path"]) if revision else None
        try:
            previous = function_digests(normalize_newlines(blob.stdout).decode("utf-8"))["functions"] if blob and blob.returncode == 0 else None
        except (UnicodeError, SyntaxError, ValueError):
            previous = None
        memo[key] = revision, previous
    revision, previous = memo[key]
    if previous is None:
        return {"state": "unknown", "reason": "receipt has no committed source before-image in this clone"}
    if function["path"] not in memo:
        memo[function["path"]] = function_digests(read_source(root / function["path"]))["functions"]
    current = memo[function["path"]]
    return {"state": "recorded", "commit": revision,
            "changed": previous.get(function["function"]) != current.get(function["function"]),
            "scope": "compared with the commit that introduced this receipt in this clone"}


def source_names(inv, raw, extra_names=()):
    """The same static spellings serve one-file and whole-project text views."""
    names = set(extra_names)
    names.update(inv.files)
    for file, facts in raw["files"].items():
        names.update((file, facts["module"]))
        names.update(facts.get("imports", {}))
        names.update(facts.get("classes", []))
        for symbol in facts.get("functions", {}):
            names.update((symbol, symbol.rsplit(".", 1)[-1], file + "#" + symbol, file + ":" + symbol, facts["module"] + "." + symbol))
        names.update(facts.get("all_state", facts.get("state", {})))
        names.update(facts.get("source_constants", {}))
        names.update(info["name"] for info in facts.get("references", []))
        names.update(inv.py[file].symbols)
        names.update(inv.py[file].string_literals)
    return names


def text_reference_hint(root, path, spelling, names, *, basenames=None):
    """Classify a spelling; filename candidates never establish a symbol or owner."""
    query = _anchor(spelling.split("(", 1)[0])
    candidate = Path(spelling)
    if ('.' in spelling or '/' in spelling or basenames and spelling in basenames) and not any(char.isspace() for char in spelling) and not candidate.is_absolute():
        for relative in (Path(path).parent / candidate, candidate):
            selected = root / relative
            resolved = selected.resolve()
            if resolved.is_relative_to(root.resolve()) and selected.is_file():
                return {"state": "file exists in selected tree", "kind": "file candidate",
                        "files": [resolved.relative_to(root.resolve()).as_posix()]}
        if spelling not in names and query not in names and candidate.name == spelling and basenames and spelling in basenames:
            files = sorted(basenames[spelling])
            return {"state": "file candidate; " + ("unique basename" if len(files) == 1 else "ambiguous basename") + " in selected tree",
                    "kind": "file candidate", "files": files}
    if spelling in names or query in names:
        return {"state": "found in static source", "kind": "source spelling"}
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+", spelling):
        return {"state": "prose candidate; code binding unknown", "kind": "prose candidate"}
    if re.fullmatch(r"[A-Za-z_][\w.:-]*", query):
        return {"state": "not found in static source; dynamic binding unknown", "kind": "unresolved code"}
    if "/" in spelling and not any(char.isspace() for char in spelling):
        return {"state": "path not found in selected tree", "kind": "unresolved path"}
    return {"state": "not a single static code name", "kind": "unclassified text"}


def text_references(root, path, inv, raw, extra_names=(), *, names=None):
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("text path must be relative to the selected source tree")
    source = root / candidate
    if not source.is_file():
        raise ValueError("text is absent from the selected source tree: " + str(path))
    names = source_names(inv, raw, extra_names) if names is None else names
    basenames = defaultdict(list)
    for file in inv.files:
        basenames[Path(file).name].append(file)
    references = []
    fenced = False
    for line, text in enumerate(read_source(source).splitlines(), 1):
        if text.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        for value in re.findall(r"(?<!`)`([^`\n]+)`(?!`)", text):
            spelling = value.strip()
            hint = text_reference_hint(root, path, spelling, names, basenames=basenames)
            references.append({"path": str(candidate), "line": line, "name": spelling, **hint})
    return references


def _predicate_sites(raw):
    """Exact pure Boolean shapes from discovery's per-file facts; no body-similarity or behavioral claim."""
    rows = {kind: [{"path": path, **row} for path, file in raw["files"].items() for row in file["predicates"][kind]]
            for kind in ("helpers", "sites")}
    return rows["helpers"], rows["sites"]


COHESION_UNKNOWN = (
    "normative predicate bindings, passed normative text and per-rule ownership are unknown; "
    "model/test names and TESTED_BY do not license them"
)


def cohesion_facts(inv, raw, data):
    """Candidate helper boundaries from the existing static graph, without reparsing.

    The graph includes conservative may-call edges (including passed functions).
    Locations identify the actual caller/callee definitions, not inferred call sites.
    """
    _, declared = owner_index(data, inv)
    files = raw.get("files", {})
    entries = {path for path, file in files.items() if file.get("entrypoints")}
    entries.update(anchor.partition(":")[0] for component in data["components"]
                   for anchor in component.get("entrypoints", []))

    def owner(path):
        ids = set(declared.get(path, ()))
        return (next(iter(ids)), "declared component") if len(ids) == 1 else (
            (path, "module") if not ids else (None, "ambiguous declared owners"))

    incoming = defaultdict(list)
    ambiguous = set()
    for caller, targets in sorted(raw.get("edges", {}).items()):
        source, _, symbol = caller.partition("#")
        function = files.get(source, {}).get("functions", {}).get(symbol)
        if function is None or inv.is_test(source):
            continue
        source_owner, source_basis = owner(source)
        for target in targets:
            path, _, name = target.partition("#")
            callee = files.get(path, {}).get("functions", {}).get(name)
            if source == path or callee is None or inv.is_test(path):
                continue
            target_owner, target_basis = owner(path)
            if source_owner is None or target_owner is None:
                ambiguous.add(path)
                continue
            if source_owner != target_owner:
                incoming[path].append({"caller": caller, "caller_line": function["line"],
                                       "callee": target, "callee_line": callee["line"],
                                       "caller_owner": source_owner, "caller_owner_basis": source_basis,
                                       "callee_owner": target_owner, "callee_owner_basis": target_basis})
    out = []
    for path, edges in sorted(incoming.items()):
        external = {edge["caller_owner"] for edge in edges}
        if (len(external) != 1 or path in ambiguous or path in entries
                or Path(path).name == "__init__.py" or "examples" in Path(path).parts):
            continue
        target_owner, basis = owner(path)
        out.append({"class": 5, "kind": "module_without_boundary", "source": path,
                    "line": min(edge["callee_line"] for edge in edges),
                    "owner": target_owner, "owner_basis": basis,
                    "external_owner": next(iter(external)),
                    "callers": sorted({edge["caller"].partition("#")[0] for edge in edges}),
                    "call_edges": edges,
                    "fact": "resolved external may-call edges have one owner; no declared or indexed independent entry",
                    "scope": "static helper-boundary candidate, not a semantic cohesion verdict; dynamic uses remain unknown"})
    return out


def _architecture(root, inv, raw, data, functions, entries):
    drift = []
    owners, _ = owner_index(data, inv)
    helpers, sites = _predicate_sites(raw)
    for site in sites:
        for helper in helpers:
            caller, target = site["path"] + "#" + site["function"], helper["path"] + "#" + helper["function"]
            if caller == target or site["shape"] != helper["shape"] or len(site["parameters"]) != len(helper["parameters"]):
                continue
            imported = raw["files"][site["path"]].get("imports", {})
            module = raw["files"][helper["path"]]["module"]
            callable_here = site["path"] == helper["path"] or module + ":" + helper["function"] in imported.values() or module in imported.values()
            if not callable_here or target in reachable_functions(raw["edges"], caller):
                continue
            drift.append({"class": 1, "kind": "reimplemented", "source": caller, "line": site["line"], "helper": target,
                          "fact": "same pure boolean expression over matching public arguments; named helper is available here",
                          "scope": "exact static shape and callable binding; behavior outside that expression is not inferred"})
    for row in raw.get("foreign_writes", []):
        drift.append({"class": 4, "kind": "foreign_write", "source": row["source"], "line": row["line"],
                      "target": row["class_path"] + "#" + row["class"] + "." + row["attr"],
                      "owner": owners.get(row["class_path"], row["class_path"]), "owner_basis": "declared component or writing module"})
    drift.extend(cohesion_facts(inv, raw, data))
    return sorted(drift, key=lambda row: (row["class"], "/" not in row.get("helper", ""), row["source"], row["line"], row.get("helper", "")))


def _by_size(modules):
    return sorted(modules, key=lambda row: (-row["functions"], row["path"]))


def _enclosing(spans, line):
    inside = [span for span in spans if span[0] <= line <= span[1]]
    return min(inside, key=lambda span: span[1] - span[0])[2] if inside else "<module>"


def where(root, name=None, *, view="tree", at=None, execution=None, inv=None, raw=None):
    """Compute a source view; optional execution must already be validated by its owner."""
    if view not in {"tree", "name", "flow", "arch", "text", "keyflows"}:
        raise ValueError("unknown where view: " + str(view))
    original = Path(root).resolve()
    cache = _writes_cache(original, at)
    with _source(original, at) as (source, revision):
        data, unknown = _map(source)
        if at is not None:
            inv = raw = execution = None
        inv = inv or build_inventory(source, ignore_patterns(data), with_bodies=False, write_cache=cache, import_roots=data.get("import_roots", ()))
        raw = raw or discover_inventory(source, inv, write_cache=cache, data=data)
        parse_errors = [path + ": " + file["parse_error"] for path, file in raw["files"].items() if file.get("parse_error")]
        unknown.extend("source not parsed: " + error for error in parse_errors)
        raw = {**raw, "files": {path: file for path, file in raw["files"].items() if not file.get("parse_error") and "module" in file}}
        bindings, model_names, model_unknown = _legacy(source, data)
        unknown.extend(model_unknown)
        owners, _ = owner_index(data, inv)
        functions = {path + "#" + symbol: {"id": path + "#" + symbol, "path": path, "function": symbol,
                     "line": fn["line"], "owner": owners.get(path, path), "calls": raw["edges"].get(path + "#" + symbol, []),
                     "reads": fn.get("reads", []), "writes": fn.get("all_writes", fn["writes"]),
                     "model_bindings": bindings.get(path + "#" + symbol, []), "execution": _runtime(execution, path + "#" + symbol)}
                     for path, facts in raw["files"].items() for symbol, fn in facts.get("functions", {}).items()}
        entries = _entries(raw)
        reached = {entry["id"]: set().union(*(reachable_functions(raw["edges"], start) for start in entry["roots"])) if entry["roots"] else set() for entry in entries}
        result = {"view": "name" if view == "tree" and name else view, "name": name, "root": str(original), "revision": revision,
                  "source": str(at) if at is not None else "working tree", "unknown": unknown,
                  "execution_state": (execution or {}).get("state", "not_recorded")}
        if view == "text":
            names = source_names(inv, raw, model_names)
            if name:
                result["references"] = text_references(source, name, inv, raw, names=names)
            else:
                groups = {}
                for path in inv.files:
                    if Path(path).suffix.lower() not in {".md", ".rst", ".txt"}:
                        continue
                    refs = text_references(source, path, inv, raw, names=names)
                    parent = "/".join(Path(path).parts[:2]) if len(Path(path).parts) > 2 else str(Path(path).parent)
                    group = groups.setdefault(parent, {"source": parent, "files": 0, "references": 0, "unresolved": 0})
                    group["files"] += 1
                    group["references"] += len(refs)
                    group["unresolved"] += sum("not found" in row["state"] for row in refs)
                result["text_groups"] = list(groups.values())
                result["unexpanded_texts"] = sum(row["files"] for row in groups.values())
            return result
        if view == "arch":
            result.update(modules=_by_size({"path": path, "owner": owners.get(path, path), "functions": len(file.get("functions", {})),
                                            "imports": sorted(inv.file_deps.get(path, [])), "entrypoints": [entry["name"] for entry in entries if entry["path"] == path]} for path, file in raw["files"].items()),
                          drift=_architecture(source, inv, raw, data, functions, entries))
            if name:
                paths = {row["path"] for row in result["modules"] if name in {row["path"], row["owner"], raw["files"][row["path"]]["module"]}
                         or row["path"].startswith(name.rstrip("/") + "/")}
                paths.update(fn["path"] for identifier, fn in functions.items() if _match(_anchor(name), identifier))
                result["modules"] = [row for row in result["modules"] if row["path"] in paths]
                result["drift"] = [row for row in result["drift"] if row["source"].partition("#")[0] in paths or _match(name, row.get("helper", ""))]
            return result
        state = []
        for path, file in raw["files"].items():
            for term, writers in file.get("all_state", file.get("state", {})).items():
                writer_ids = {path + "#" + writer for writer in writers}
                routes = [entry["id"] for entry in entries if reached[entry["id"]] & writer_ids]
                state.append({"path": path, "term": term, "writers": sorted(writer_ids), "entries": routes,
                              "readers": sorted(identifier for identifier, fn in functions.items() if fn["path"] == path and term in fn["reads"]),
                              "owner": owners.get(path, path)})
        if view == "keyflows":
            result["shared_state"] = sorted((row for row in state if len(row["entries"]) > 1 and len(row["writers"]) > 1 and (not name or _match(name, row["term"]))),
                                            key=lambda row: (-len(row["entries"]) * len(row["writers"]), row["path"], row["term"]))
            result["stores"] = [{"path": path, **row} for path, file in raw["files"].items() for row in file.get("file_targets", [])
                                if not name or name in {path, row.get("last_component"), row.get("symbol")} or name in row.get("constants", [])]
            return result
        records = change_records(source) if at is None else []
        for identifier, fn in functions.items():
            changes = [(key, record) for key, record in records if identifier.replace("#", ":", 1) in record.get("implemented_by", [])]
            fn["last_change"] = changes[-1][0] if changes else None
            fn["last_requests"] = [item["id"] for item in changes[-1][1].get("requests", [])] if changes else []
        selected = [identifier for identifier in functions if name is None or _match(_anchor(name), identifier)
                    or name in {functions[identifier]["path"], functions[identifier]["owner"], raw["files"][functions[identifier]["path"]]["module"]}
                    or functions[identifier]["path"].startswith(str(name).rstrip("/") + "/")]
        if name:
            selected = sorted(set(selected) | {identifier for entry in entries if name in {entry["name"], entry["id"]} for identifier in entry["roots"]})
        if view == "flow":
            selected = sorted(set(selected) | {identifier for row in state if name and _match(name, row["term"]) for identifier in row["writers"]})
            # Call depth from the selected functions orders every flow row: nearest calls first.
            depth, pending = {identifier: 0 for identifier in (selected if name is not None else functions)}, deque(selected if name is not None else functions)
            while pending:
                caller = pending.popleft()
                for callee in raw["edges"].get(caller, ()):
                    if callee not in depth:
                        depth[callee] = depth[caller] + 1
                        pending.append(callee)
            included = set(depth)
            edges = sorted(([caller, callee] for caller, targets in raw["edges"].items() for callee in targets if caller in included and callee in included),
                           key=lambda edge: (depth[edge[0]], edge[0], edge[1]))
            module_edges = defaultdict(int)
            for caller, callee in edges:
                module_edges[(caller.partition("#")[0], callee.partition("#")[0])] += 1
            result["module_edges"] = [{"source": caller, "target": callee, "calls": count} for (caller, callee), count in sorted(module_edges.items(), key=lambda item: (-item[1], item[0]))]
            result["resolved_edges"] = len(edges)
            if name is not None:
                result["functions"] = [functions[identifier] for identifier in sorted(included, key=lambda item: (depth[item], item)) if identifier in functions]
                result["edges"] = edges
            else:
                modules = defaultdict(int)
                for identifier in included:
                    if identifier in functions:
                        modules[functions[identifier]["path"]] += 1
                result["modules"] = _by_size({"path": path, "functions": count} for path, count in modules.items())
                result["unexpanded_functions"], result["unexpanded_edges"] = len(included), len(edges)
            if name is not None:
                result["state"] = [row for row in state if _match(name, row["term"]) or set(row["writers"]) & included]
            else:
                state_counts = defaultdict(int)
                for row in state:
                    state_counts[row["path"]] += 1
                result["state_summary"] = dict(sorted(state_counts.items()))
            if execution and "transitions" in execution:
                result["behavior"] = execution["transitions"]
            result["unresolved"] = [{"function": path + "#" + symbol, "calls": fn["dynamic"]} for path, file in raw["files"].items() for symbol, fn in file.get("functions", {}).items() if fn["dynamic"] and path + "#" + symbol in included]
            return result
        if name is None:
            modules = {}
            for fn in functions.values():
                row = modules.setdefault(fn["path"], {"path": fn["path"], "owner": fn["owner"], "functions": 0,
                    "entrypoints": [entry["name"] for entry in entries if entry["path"] == fn["path"]], "without_declared_model_binding": 0})
                row["functions"] += 1
                row["without_declared_model_binding"] += bool(fn["writes"] and not fn["model_bindings"])
            result["modules"] = _by_size(modules.values())
            result["unexpanded_functions"] = len(functions)
            return result
        result["functions"] = []
        history = {}
        for identifier in selected:
            row = dict(functions[identifier])
            if row["last_change"]:
                row["changed_since"] = _changed_since(source, row["last_change"], row, history)
            row["callers"] = sorted(caller for caller, targets in raw["edges"].items() if identifier in targets)
            row["reaching_entries"] = [entry["id"] for entry in entries if identifier in reached[entry["id"]]]
            row["no_resolved_route"] = [entry["id"] for entry in entries if entry["roots"] and identifier not in reached[entry["id"]]]
            result["functions"].append(row)
        if result["functions"]:
            # One project-wide list, not repeated per function: entries whose handlers are not resolved.
            result["unresolved_entries"] = [entry["id"] for entry in entries if not entry["roots"]]
        result["references"] = [{"path": path, **row} for path, file in raw["files"].items() for row in file.get("references", []) if _match(name, row["name"]) or _match(name, row.get("raw", ""))]
        result["literals"] = []
        for path in raw["files"]:
            if name not in inv.py[path].string_literals:
                continue  # the inventory holds every string constant outside `if TYPE_CHECKING:` blocks
            text = read_source(source / path)
            spans = function_spans(syntax_tree(text))
            result["literals"].extend({"path": path, "line": line, "function": _enclosing(spans, line), "role": role, "value": value}
                                      for value, line, role in literal_sites(text) if value == name)
        result["state"] = [row for row in state if _match(name, row["term"])]
        result["entries"] = [entry for entry in entries if _match(name, entry["name"])]
        result["changes"] = [{"id": identifier, "goal": record["goal"], "requests": record["requests"], "implemented_by": record["implemented_by"]}
                             for identifier, record in records if name == identifier or any(item["id"] == name for item in record["requests"])]
        result["requests"] = [row for row in owner_words(source, records=records)["rows"] if row["id"] == name] if at is None else []
        result["constants"] = [{"path": path, "name": key, **value} for path, file in raw["files"].items() for key, value in file.get("source_constants", {}).items() if _match(name, key)]
        if not any(result.get(key) for key in ("functions", "references", "literals", "state", "entries", "changes", "requests", "constants")):
            result["unknown"].append("name not resolved in the static source index: " + name)
        return result


def _order(result):
    """The relevance order of the bounded rows, stated next to what was omitted."""
    if result["view"] == "flow":
        return ("functions by call depth from the name; " if result.get("name") else "modules by function count; ") + "module edges by calls"
    return {"arch": "drift findings, then modules by function count", "keyflows": "state by entries × writers",
            "tree": "modules by function count"}.get(result["view"])


def project(result, *, all_rows=False):
    """The one projection human and JSON output print: every list bounded unless all_rows.

    Per function, the routes it is not on are shown only with all_rows, and so is the
    project-wide list of entries whose handlers are unresolved. Projecting twice changes nothing.
    """
    omitted, shown = dict(result.get("omitted", {})), dict(result)
    keep = dict(all_rows=all_rows)
    if "functions" in result:
        shown["functions"] = []
        for row in bound(result["functions"], "functions", omitted, **keep):
            shown["functions"].append({**row, **{field: bound(row[field], label, omitted, **keep, limit=limit)
                                                 for field, label, limit in (("callers", "callers", DISPLAY_ROWS),
                                                                             ("reaching_entries", "entry routes", DISPLAY_ROWS),
                                                                             ("no_resolved_route", "entries without a route here", 0))
                                                 if field in row}})
    for field, label, limit in (("unresolved_entries", "unknown entry bindings", 0), ("edges", "function edges", DISPLAY_ROWS),
                                ("modules", "modules", DISPLAY_ROWS), ("module_edges", "module edges", DISPLAY_ROWS),
                                ("drift", "drift findings", DISPLAY_ROWS), ("references", "references", DISPLAY_ROWS),
                                ("literals", "literals", DISPLAY_ROWS), ("constants", "constants", DISPLAY_ROWS),
                                ("entries", "entries", DISPLAY_ROWS), ("changes", "changes", DISPLAY_ROWS),
                                ("requests", "requests", DISPLAY_ROWS), ("stores", "stores", DISPLAY_ROWS),
                                ("unresolved", "unresolved calls", DISPLAY_ROWS), ("text_groups", "text groups", DISPLAY_ROWS)):
        if field in result:
            shown[field] = bound(result[field], label, omitted, **keep, limit=limit)
    for field in ("state", "shared_state"):
        if field in result:
            shown[field] = [{**row, "writers": bound(row["writers"], "state writers", omitted, **keep),
                             "entries": bound(row["entries"], "state entry routes", omitted, **keep)}
                            for row in bound(result[field], "state rows", omitted, **keep)]
    if not all_rows:
        shown["omitted"] = omitted
    return shown


def render(result, *, as_json=False, all_rows=False):
    """Render facts on demand; no success verdict or remembered judgment is written."""
    result = project(result, all_rows=all_rows)
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    lines = ["where " + result["view"] + (" " + str(result["name"]) if result.get("name") else "") + " · " + result["source"] + (" " + result["revision"][:12] if result.get("revision") else "")]
    if result["view"] == "text":
        lines.extend(f"{row['path']}:{row['line']} `{row['name']}`: {row['state']}" for row in result.get("references", []))
        for group in result.get("text_groups", []):
            lines.append(group["source"] + " · " + str(group["files"]) + " texts · " + str(group["references"]) + " code references · " + str(group["unresolved"]) + " unresolved")
    else:
        function_rows = result.get("functions", [])
        for row in function_rows:
            text = row["id"] + ":" + str(row["line"]) + " · owner " + row["owner"]
            if row["last_change"]:
                text += " · change " + row["last_change"] + (" · requests " + ",".join(row["last_requests"]) if row["last_requests"] else "")
            lines.append(text)
            if row.get("callers"):
                lines.append("  callers: " + ", ".join(row["callers"]))
            if "reaching_entries" in row:
                lines.append("  entry routes: " + (", ".join(row["reaching_entries"]) or "none resolved"))
            if row.get("no_resolved_route"):
                lines.append("  no resolved route: " + ", ".join(row["no_resolved_route"]))
            if row["execution"]["state"] == "recorded":
                lines.append("  tests: " + (", ".join(row["execution"]["tests"]) if isinstance(row["execution"]["tests"], list) else row["execution"]["tests"]))
            if row["model_bindings"]:
                lines.append("  declared model anchors: " + ", ".join(item["model"] + "." + item["anchor"] for item in row["model_bindings"]))
        if result.get("unresolved_entries"):
            lines.append("unknown entry bindings: " + ", ".join(result["unresolved_entries"]))
        if result["view"] == "flow":
            lines.append("static call graph by module (" + str(result["resolved_edges"]) + " resolved function edges):")
            lines.extend("  " + edge["source"] + " -> " + edge["target"] + " · " + str(edge["calls"]) + " calls" for edge in result["module_edges"])
            if "behavior" in result:
                lines.append("behavior: " + str(result["behavior"]))
        for row in result.get("references", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row.get("symbol", "<module>") + " reads " + row["raw"])
        for row in result.get("constants", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row["name"] + " = " + repr(row.get("value")))
        for row in result.get("literals", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row["function"] + " " + row["role"] + " " + repr(row["value"]))
        for row in result.get("state", result.get("shared_state", [])):
            lines.append(row["path"] + " " + row["term"] + " <- " + ", ".join(row["writers"]))
            if row["entries"]:
                lines.append("  entries: " + ", ".join(row["entries"]))
        for row in result.get("entries", []):
            lines.append(row["path"] + ":" + str(row.get("line", 0)) + " command " + row["name"] + " -> " + (", ".join(row["roots"]) or "handler binding unknown"))
        for row in result.get("changes", []):
            lines.append("change " + row["id"] + ": " + row["goal"] + " · " + ", ".join(row["implemented_by"]))
        for row in result.get("requests", []):
            state = ("retired: not the owner's words" if row["retired"] else
                     "superseded by " + ", ".join(row["superseded_by"]) if row["superseded_by"] else "owner words")
            lines.append("request " + row["id"] + ": " + state + " · " + row["first_line"]
                         + (" · cited by " + ", ".join(row["cited_by"]) if row["cited_by"] else ""))
        for row in result.get("drift", []):
            lines.append("drift class " + str(row["class"]) + " " + row["kind"] + " " + row["source"] + ":" + str(row["line"]) + " · " + row.get("fact", row.get("target", "")))
        for row in result.get("modules", []):
            lines.append(row["path"] + " · " + str(row["functions"]) + " functions" + (" · owner " + row["owner"] if "owner" in row else "")
                         + (" · imports " + ", ".join(row["imports"]) if "imports" in row else ""))
        for row in result.get("stores", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " store " + str(row.get("last_component") or "unknown") + " · " + row["expression"])
    if "unexpanded_functions" in result:
        lines.append(str(result["unexpanded_functions"]) + " function details unexpanded")
    if "unexpanded_texts" in result:
        lines.append(str(result["unexpanded_texts"]) + " text details unexpanded")
    if result.get("next"):
        lines.append(render_advice(result["next"]))
    if (line := omitted_line(result.get("omitted"), _order(result))):
        lines.append(line)
    lines.extend("unknown: " + item for item in result["unknown"])
    return "\n".join(lines)
