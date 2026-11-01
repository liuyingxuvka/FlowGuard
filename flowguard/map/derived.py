"""Read-only source views over the shared inventory and discovery facts."""

from __future__ import annotations

import ast
from collections import defaultdict
from contextlib import contextmanager
import copy
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .common import normalize_newlines, read_source
from .discover import discover_inventory, function_spans, literal_sites, reachable_functions
from .inventory import build_inventory, function_digests, syntax_tree
from .mapfile import MapError, ignore_patterns, load_map, model_registry, owner_index, read_model_contract
from .records import change_records
from .requests import request_details


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


def _map(root):
    try:
        return load_map(root), []
    except MapError as exc:
        return {"components": [], "flows": []}, [str(exc)]


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
    current = function_digests(read_source(root / function["path"]))["functions"]
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


def text_references(root, path, inv, raw, extra_names=(), *, names=None):
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("text path must be relative to the selected source tree")
    source = root / candidate
    if not source.is_file():
        raise ValueError("text is absent from the selected source tree: " + str(path))
    names = source_names(inv, raw, extra_names) if names is None else names
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
            query = _anchor(spelling.split("(", 1)[0])
            if spelling in names or query in names:
                state = "found in static source"
            elif re.fullmatch(r"[A-Za-z_][\w.:-]*", query):
                state = "not found in static source; dynamic binding unknown"
            elif "/" in spelling and not any(char.isspace() for char in spelling):
                state = "path not found in selected tree" if not (root / spelling).exists() else "path exists"
            else:
                state = "not a single static code name"
            references.append({"path": str(candidate), "line": line, "name": spelling, "state": state})
    return references


def _predicate_sites(root, raw):
    """Exact pure boolean source shapes; no body-similarity or behavioral equivalence claim."""
    helpers, sites = [], []
    for path, file in raw["files"].items():
        try:
            tree = syntax_tree(read_source(root / path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        spans = {start: name for start, _, name in function_spans(tree)}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.lineno not in spans:
                continue
            symbol = spans[node.lineno]
            params = [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]]
            if file["functions"].get(symbol, {}).get("class") and params:
                params = params[1:]
            positions = {name: "argument_" + str(index) for index, name in enumerate(params)}
            local_names = {value.id for value in ast.walk(node) if isinstance(value, ast.Name) and isinstance(value.ctx, ast.Store)}
            imports = {**file.get("imports", {}), **file["functions"].get(symbol, {}).get("local_imports", {})}
            class Normalize(ast.NodeTransformer):
                def visit_Name(self, value):
                    imported = imports.get(value.id) if value.id not in local_names else None
                    identity = positions.get(value.id, imported.replace(":", ".") if imported else file["module"] + ("#" + symbol if value.id in local_names else "") + "." + value.id)
                    return ast.copy_location(ast.Name(id=identity, ctx=value.ctx), value)
                def visit_Attribute(self, value):
                    parts, base = [], value
                    while isinstance(base, ast.Attribute):
                        parts.append(base.attr)
                        base = base.value
                    if isinstance(base, ast.Name) and base.id in imports and base.id not in local_names:
                        identity = imports[base.id].replace(":", ".") + "." + ".".join(reversed(parts))
                        return ast.copy_location(ast.Name(id=identity, ctx=value.ctx), value)
                    return self.generic_visit(value)
            def shape(value):
                if not isinstance(value, (ast.Compare, ast.BoolOp, ast.UnaryOp)) or any(isinstance(x, (ast.Call, ast.NamedExpr, ast.Lambda, ast.Await)) for x in ast.walk(value)):
                    return None
                if isinstance(value, ast.UnaryOp) and not isinstance(value.op, ast.Not):
                    return None
                return ast.dump(Normalize().visit(copy.deepcopy(value)), include_attributes=False)
            body = [item for item in node.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
            def boolean(value):
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
                    return True
                if isinstance(value, ast.Compare):
                    return all(isinstance(op, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for op in value.ops)
                return isinstance(value, ast.BoolOp) and all(boolean(part) for part in value.values)
            if (len(body) == 1 and isinstance(body[0], ast.Return) and shape(body[0].value)
                    and boolean(body[0].value)
                    and not file["functions"][symbol].get("class") and "." not in symbol
                    and isinstance(node, ast.FunctionDef) and not node.decorator_list
                    and node in tree.body
                    and not node.args.vararg and not node.args.kwarg and not node.args.kwonlyargs):
                helpers.append({"path": path, "function": symbol, "line": node.lineno, "shape": shape(body[0].value), "parameters": params})
            pending = list(node.body)
            while pending:
                item = pending.pop()
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                value = item.test if isinstance(item, (ast.If, ast.While)) else item.value if isinstance(item, ast.Return) else None
                if value is not None and (key := shape(value)):
                    sites.append({"path": path, "function": symbol, "line": item.lineno, "shape": key, "parameters": params})
                pending.extend(ast.iter_child_nodes(item))
    return helpers, sites


def _architecture(root, inv, raw, data, functions, entries):
    drift = []
    owners, _ = owner_index(data, inv)
    helpers, sites = _predicate_sites(root, raw)
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
    entry_paths = {entry["path"] for entry in entries}
    for path in raw["files"]:
        callers = {source for source, dependencies in inv.file_deps.items() if path in dependencies and source != path}
        sources = {owners.get(source, source) for source in callers if owners.get(source, source) != owners.get(path, path)}
        if len(sources) == 1 and callers and path not in entry_paths and Path(path).name != "__init__.py" and "examples" not in Path(path).parts:
            drift.append({"class": 5, "kind": "module_without_boundary", "source": path, "line": 0,
                          "callers": sorted(callers), "fact": "resolved outside importers belong to one owner; no indexed public entry point",
                          "scope": "dynamic importers and runtime uses remain unknown"})
    return sorted(drift, key=lambda row: (row["class"], "/" not in row.get("helper", ""), row["source"], row["line"], row.get("helper", "")))


def where(root, name=None, *, view="tree", at=None, execution=None, inv=None, raw=None):
    """Compute a source view; optional execution must already be validated by its owner."""
    if view not in {"tree", "name", "flow", "arch", "text", "keyflows"}:
        raise ValueError("unknown where view: " + str(view))
    original = Path(root).resolve()
    with _source(original, at) as (source, revision):
        data, unknown = _map(source)
        if at is not None:
            inv = raw = execution = None
        inv = inv or build_inventory(source, ignore_patterns(data), with_bodies=False, write_cache=False, import_roots=data.get("import_roots", ()))
        raw = raw or discover_inventory(source, inv, write_cache=False, data=data)
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
                  "execution_state": (execution or {}).get("state", "not_recorded"),
                  "scope": "complete resolved static graph; unresolved calls are unknown; declared model bindings are not observed tests",
                  "rule_scope": "rule-test provenance is unavailable; declared legacy model anchors are shown separately"}
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
                result["next"] = "where --text <relative-text-path>"
            return result
        if view == "arch":
            result.update(modules=[{"path": path, "owner": owners.get(path, path), "functions": len(file.get("functions", {})),
                                    "imports": sorted(inv.file_deps.get(path, [])), "entrypoints": [entry["name"] for entry in entries if entry["path"] == path]} for path, file in sorted(raw["files"].items())],
                          drift=_architecture(source, inv, raw, data, functions, entries))
            result["drift_scope"] = "source-backed Boolean-helper reuse, foreign writes and resolved module boundaries; runtime adapter agreement and registered rule conventions are not judged"
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
                              "rule_reads": "unknown: no rule-test provenance index", "owner": owners.get(path, path)})
        if view == "keyflows":
            result["shared_state"] = [row for row in state if len(row["entries"]) > 1 and len(row["writers"]) > 1 and (not name or _match(name, row["term"]))]
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
            included = set(selected) if name is not None else set(functions)
            for identifier in tuple(included):
                included.update(reachable_functions(raw["edges"], identifier))
            edges = [[caller, callee] for caller, targets in sorted(raw["edges"].items()) for callee in targets if caller in included and callee in included]
            if name is not None:
                result["functions"] = [functions[identifier] for identifier in sorted(included) if identifier in functions]
                result["edges"] = edges
            else:
                modules = defaultdict(int)
                for identifier in included:
                    if identifier in functions:
                        modules[functions[identifier]["path"]] += 1
                module_edges = defaultdict(int)
                for caller, callee in edges:
                    module_edges[(caller.partition("#")[0], callee.partition("#")[0])] += 1
                result["modules"] = [{"path": path, "functions": count} for path, count in sorted(modules.items())]
                result["module_edges"] = [{"source": caller, "target": callee, "calls": count} for (caller, callee), count in sorted(module_edges.items())]
                result["unexpanded_functions"], result["unexpanded_edges"] = len(included), len(edges)
                result["next"] = "where <function-or-module> --flow"
            if name is not None:
                result["state"] = [row for row in state if _match(name, row["term"]) or set(row["writers"]) & included]
            else:
                state_counts = defaultdict(int)
                for row in state:
                    state_counts[row["path"]] += 1
                result["state_summary"] = dict(sorted(state_counts.items()))
            result["behavior"] = (execution or {}).get("transitions", "not recorded; these are static calls and writes")
            result["unresolved"] = [{"function": path + "#" + symbol, "calls": fn["dynamic"]} for path, file in raw["files"].items() for symbol, fn in file.get("functions", {}).items() if fn["dynamic"] and path + "#" + symbol in included]
            return result
        if name is None:
            modules = {}
            for fn in functions.values():
                row = modules.setdefault(fn["path"], {"path": fn["path"], "owner": fn["owner"], "functions": 0,
                    "entrypoints": [entry["name"] for entry in entries if entry["path"] == fn["path"]], "without_declared_model_binding": 0})
                row["functions"] += 1
                row["without_declared_model_binding"] += bool(fn["writes"] and not fn["model_bindings"])
            result["modules"] = list(modules.values())
            result["unexpanded_functions"] = len(functions)
            result["next"] = "where <function-or-module>"
            return result
        query = _anchor(name)
        result["functions"] = []
        history = {}
        for identifier in selected:
            row = dict(functions[identifier])
            if row["last_change"]:
                row["changed_since"] = _changed_since(source, row["last_change"], row, history)
            row["callers"] = sorted(caller for caller, targets in raw["edges"].items() if identifier in targets)
            row["reaching_entries"] = [entry["id"] for entry in entries if identifier in reached[entry["id"]]]
            row["no_resolved_route"] = [entry["id"] for entry in entries if entry["roots"] and identifier not in reached[entry["id"]]]
            row["unresolved_entries"] = [entry["id"] for entry in entries if not entry["roots"]]
            result["functions"].append(row)
        result["references"] = [{"path": path, **row} for path, file in raw["files"].items() for row in file.get("references", []) if _match(name, row["name"]) or _match(name, row.get("raw", ""))]
        result["literals"] = [{"path": path, "function": symbol, "line": line, "value": value}
                              for path in raw["files"] for symbol, line, value in literal_sites(read_source(source / path)) if name == value]
        result["state"] = [row for row in state if _match(name, row["term"])]
        result["entries"] = [entry for entry in entries if _match(name, entry["name"])]
        result["changes"] = [{"id": identifier, "goal": record["goal"], "requests": record["requests"], "implemented_by": record["implemented_by"]}
                             for identifier, record in records if name == identifier or any(item["id"] == name for item in record["requests"])]
        result["requests"] = [row for row in request_details(source, records=records, worktrees=[]) if row["id"] == name] if at is None else []
        result["constants"] = [{"path": path, "name": key, **value} for path, file in raw["files"].items() for key, value in file.get("source_constants", {}).items() if _match(name, key)]
        if not any(result.get(key) for key in ("functions", "references", "literals", "state", "entries", "changes", "requests", "constants")):
            result["unknown"].append("name not resolved in the static source index: " + name)
        return result


def render(result, *, as_json=False):
    """Render facts on demand; no success verdict or remembered judgment is written."""
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    lines = ["where " + result["view"] + (" " + str(result["name"]) if result.get("name") else "") + " · " + result["source"] + (" " + result["revision"][:12] if result.get("revision") else ""), result["scope"]]
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
            for field, label in (("callers", "callers"), ("reaching_entries", "entry routes"), ("no_resolved_route", "no resolved route"), ("unresolved_entries", "unknown entry bindings")):
                if row.get(field):
                    lines.append("  " + label + ": " + ", ".join(row[field]))
            if result["view"] == "name":
                lines.append("  tests: " + (", ".join(row["execution"]["tests"]) if isinstance(row["execution"]["tests"], list) else row["execution"]["tests"]))
                lines.append("  declared model anchors: " + (", ".join(item["model"] + "." + item["anchor"] for item in row["model_bindings"]) or "none recorded; rule judgment unknown"))
        if result["view"] == "flow":
            module_edges = defaultdict(int)
            for caller, callee in result.get("edges", []):
                module_edges[(caller.partition("#")[0], callee.partition("#")[0])] += 1
            for edge in result.get("module_edges", []):
                module_edges[(edge["source"], edge["target"])] += edge["calls"]
            count = len(result["edges"]) if "edges" in result else result["unexpanded_edges"]
            lines.append("static call graph by module (" + str(count) + " resolved function edges):")
            lines.extend("  " + caller + " -> " + callee + " · " + str(count) + " calls" for (caller, callee), count in sorted(module_edges.items()))
            lines.append("behavior: " + str(result["behavior"]))
        for row in result.get("references", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row.get("symbol", "<module>") + " reads " + row["raw"])
        for row in result.get("constants", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row["name"] + " = " + repr(row.get("value")))
        for row in result.get("literals", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " " + row["function"] + " contains " + repr(row["value"]))
        for row in result.get("state", result.get("shared_state", [])):
            lines.append(row["path"] + " " + row["term"] + " <- " + ", ".join(row["writers"]))
            lines.append("  entries: " + ", ".join(row["entries"]) + "; " + row["rule_reads"])
        for row in result.get("entries", []):
            lines.append(row["path"] + ":" + str(row.get("line", 0)) + " command " + row["name"] + " -> " + (", ".join(row["roots"]) or "handler binding unknown"))
        for row in result.get("changes", []):
            lines.append("change " + row["id"] + ": " + row["goal"] + " · " + ", ".join(row["implemented_by"]))
        for row in result.get("requests", []):
            lines.append("request " + row["id"] + ": " + row["state"] + " · " + row["first_line"])
        for row in result.get("modules", []):
            lines.append(row["path"] + " · " + str(row["functions"]) + " functions" + (" · owner " + row["owner"] if "owner" in row else "")
                         + (" · imports " + ", ".join(row["imports"]) if "imports" in row else ""))
        for row in result.get("drift", []):
            lines.append("drift class " + str(row["class"]) + " " + row["kind"] + " " + row["source"] + ":" + str(row["line"]) + " · " + row.get("fact", row.get("target", "")))
        for row in result.get("stores", []):
            lines.append(row["path"] + ":" + str(row["line"]) + " store " + str(row.get("last_component") or "unknown") + " · " + row["expression"])
    if "unexpanded_functions" in result:
        lines.append(str(result["unexpanded_functions"]) + " function details unexpanded · next: " + result["next"])
    if "unexpanded_texts" in result:
        lines.append(str(result["unexpanded_texts"]) + " text details unexpanded · next: " + result["next"])
    lines.append(result["rule_scope"])
    lines.extend("unknown: " + item for item in result["unknown"])
    return "\n".join(lines)
