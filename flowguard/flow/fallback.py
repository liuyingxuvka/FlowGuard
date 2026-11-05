"""Static route candidates judged only through the shared native pytest recorder."""
from __future__ import annotations

import ast
import copy
import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ..map.common import DEFAULT_IGNORE, content_digest, matches_any, normalize_newlines
from ..map.inventory import list_files


@dataclass(frozen=True)
class Site:
    id: str
    kind: str
    path: str
    function: str
    line: int
    end: int
    primary: tuple[int, ...]
    alternate: tuple[int, ...]
    node: tuple[int, int]
    reminder: bool = False
    primary_calls: tuple[str, ...] = ()
    alternate_calls: tuple[str, ...] = ()
    source_identity: str = ""
    peer_path: str = ""
    peer_function: str = ""
    report_lines: tuple[int, ...] = ()
    primary_call_lines: tuple[int, ...] = ()
    alternate_call_lines: tuple[int, ...] = ()
    ambiguous: bool = False
    truth_names: tuple[str, ...] = ()

    def to_json(self):
        return asdict(self)


def _identity(source):
    return hashlib.sha256(normalize_newlines(source.encode("utf-8"))).hexdigest()


def _lines(nodes):
    return tuple(sorted({line for node in nodes for line in range(node.lineno, node.end_lineno + 1)}))


def _definitions(tree):
    names, functions = {}, []
    def visit(node, scope="", kind="module"):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = (scope + (".<locals>." if kind == "function" else ".") if scope else "") + child.name
                names[id(child)] = qual
                child_kind = "class" if isinstance(child, ast.ClassDef) else "function"
                if child_kind == "function":
                    functions.append((child, qual, scope, kind))
                visit(child, qual, child_kind)
            else:
                visit(child, scope, kind)
    visit(tree)
    return names, functions


def _references(values, path, function, definitions):
    refs = []
    for value in values:
        if not isinstance(value, ast.Call):
            continue
        callee = value.func
        if isinstance(callee, ast.Name):
            candidates = [function + ".<locals>." + callee.id, callee.id]
        elif isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name) and callee.value.id in {"self", "cls"}:
            owner = function.split(".<locals>.")[0].rpartition(".")[0]
            candidates = [owner + "." + callee.attr]
        else:
            continue  # A dynamic receiver is not established by a matching basename.
        refs.extend(path + "#" + name for name in candidates if name in definitions)
    return tuple(dict.fromkeys(refs))


def _value_calls(nodes):
    return [node if isinstance(node, ast.Call) else node.value for node in nodes if isinstance(node, ast.Call) or
            isinstance(node, (ast.Return, ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call)]


def _report_lines(handler):
    """An error report is not evidence of alternate success; keep that distinction unknown."""
    if not handler.name or any(isinstance(n, ast.Name) and n.id == handler.name and isinstance(n.ctx, ast.Store) for n in ast.walk(handler)):
        return ()
    sinks = {"print", "append", "extend", "write", "echo"}
    trivial = {"str", "repr", "format", "isinstance", "int", "dict"}
    values = [n.value for n in ast.walk(handler) if isinstance(n, (ast.Return, ast.Assign, ast.AnnAssign)) and n.value]
    calls = [n for value in values for n in ast.walk(value) if isinstance(n, ast.Call)]
    if any((call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")) not in trivial | sinks for call in calls):
        return ()
    reports = [n for n in ast.walk(handler) if isinstance(n, ast.Return) and n.value or
               isinstance(n, ast.Call) and (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")) in sinks]
    return tuple(sorted({n.lineno for n in reports if any(isinstance(v, ast.Name) and v.id == handler.name for v in ast.walk(n))}))


def _canonical(node):
    value = copy.deepcopy(node)
    locals_ = [arg.arg for arg in (*value.args.posonlyargs, *value.args.args, *value.args.kwonlyargs)]
    locals_.extend(item.id for item in ast.walk(value) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store))
    renamed = {name: "v" + str(index) for index, name in enumerate(dict.fromkeys(locals_))}
    class Normalize(ast.NodeTransformer):
        def visit_Name(self, item):
            return ast.copy_location(ast.Name(id=renamed.get(item.id, item.id), ctx=item.ctx), item)
        def visit_UnaryOp(self, item):
            # Floor/ceiling variants retain the same external calls and arithmetic shape.
            return self.visit(item.operand) if isinstance(item.op, (ast.USub, ast.UAdd)) else self.generic_visit(item)
    body = value.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    shape = ast.dump(Normalize().visit(ast.Module(body=body, type_ignores=[])), include_attributes=False)
    args = value.args
    signature = (len(args.posonlyargs), len(args.args), len(args.kwonlyargs), bool(args.vararg), bool(args.kwarg),
                 tuple(ast.dump(v) for v in args.defaults), tuple(ast.dump(v) if v else None for v in args.kw_defaults))
    effects = {ast.dump(item, include_attributes=False) for statement in body for item in ast.walk(statement)
               if isinstance(item, ast.Attribute)}
    return signature, shape, bool(effects or any(isinstance(item, ast.Call) for statement in body for item in ast.walk(statement)))


def _duplicates(sources):
    groups, sites = defaultdict(list), []
    for path, source in sources.items():
        _, functions = _definitions(ast.parse(source, filename=path))
        for node, function, owner, kind in functions:
            if not node.name.startswith("__"):
                signature, shape, effects = _canonical(node)
                groups[(signature, shape)].append((path, source, node, function, owner, kind, effects))
    for group in groups.values():
        for index, first in enumerate(group):
            for second in group[index + 1:]:
                path, source, node, function, owner, kind, effects = first
                peer_path, _, peer, peer_function, peer_owner, peer_kind, _ = second
                if not ((path == peer_path and owner == peer_owner) or
                        (kind == peer_kind == "module" and effects)):
                    continue
                identity = f"{path}:{function}:{peer_path}:{peer_function}:duplicate"
                sites.append(Site(hashlib.sha256(identity.encode()).hexdigest()[:20], "duplicate", path, function,
                                  node.lineno, node.end_lineno, _lines(node.body), _lines(peer.body),
                                  (node.lineno, node.col_offset), source_identity=_identity(source),
                                  peer_path=peer_path, peer_function=peer_function))
    return sites


def find_sites(path, source):
    """Static candidates and exact source identities; none is yet a conflict."""
    tree = ast.parse(source, filename=path)
    qualifiers, functions = _definitions(tree)
    definitions = {function for _, function, _, _ in functions}
    sites, contexts, optional, parameters, operand_calls = [], [], [], [], {}
    parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    def add(kind, node, primary=(), alternate=(), reminder=False, primary_calls=(), alternate_calls=(), report_lines=()):
        function = contexts[-1] if contexts else "<module>"
        identity = f"{path}:{function}:{node.lineno}:{node.col_offset}:{kind}"
        sites.append(Site(hashlib.sha256(identity.encode()).hexdigest()[:20], kind, path, function,
                          node.lineno, node.end_lineno, tuple(primary), tuple(alternate), (node.lineno, node.col_offset),
                          reminder, _references(primary_calls, path, function, definitions),
                          _references(alternate_calls, path, function, definitions), _identity(source), report_lines=report_lines,
                          primary_call_lines=_lines([n for n in primary_calls if isinstance(n, ast.Call)]),
                          alternate_call_lines=_lines([n for n in alternate_calls if isinstance(n, ast.Call)])))
        operand_calls[sites[-1].id] = {id(n) for n in (*primary_calls, *alternate_calls) if isinstance(n, ast.Call)}
    class Finder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            # Defaults/decorators execute in the enclosing scope, before a call.
            for value in (*node.decorator_list, *node.args.defaults, *node.args.kw_defaults):
                if value is not None:
                    self.visit(value)
            contexts.append(qualifiers[id(node)])
            args = node.args.posonlyargs + node.args.args
            defaults = {arg.arg for arg, value in zip(args[-len(node.args.defaults):], node.args.defaults)
                        if isinstance(value, ast.Constant) and value.value is None} if node.args.defaults else set()
            defaults.update(arg.arg for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults)
                            if isinstance(value, ast.Constant) and value.value is None)
            optional.append(defaults)
            assigned = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
            parameters.append({arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)} - assigned)
            for statement in node.body:
                self.visit(statement)
            optional.pop(); parameters.pop(); contexts.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_Try(self, node):
            for handler in node.handlers:
                add("handler", handler, _lines(node.body), _lines(handler.body), report_lines=_report_lines(handler),
                    alternate_calls=_value_calls(handler.body))
            self.generic_visit(node)
        visit_TryStar = visit_Try
        def visit_BoolOp(self, node):
            parent = parents.get(id(node))
            names = (tuple(value.id for value in node.values)
                     if len(node.values) == 2 and all(isinstance(value, ast.Name) for value in node.values) else ())
            if (isinstance(node.op, ast.Or) and (names or any(isinstance(v, ast.Call) for v in node.values[1:]))
                    and not isinstance(parent, (ast.If, ast.While, ast.Assert, ast.BoolOp, ast.UnaryOp))):
                input_default = names and parameters and any(name in parameters[-1] for name in names)
                add("input-default" if input_default else "or-call", node, _lines(node.values[:1]), _lines(node.values[1:]),
                    reminder=bool(input_default),
                    primary_calls=node.values[:1], alternate_calls=node.values[1:])
                if names and not input_default:
                    sites[-1] = replace(sites[-1], truth_names=names)
            self.generic_visit(node)
        def visit_Call(self, node):
            if ((isinstance(node.func, ast.Attribute) and node.func.attr == "get" and len(node.args) == 2)
                    or (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) == 3)):
                add("input-default", node, reminder=True)
            self.generic_visit(node)
        def visit_If(self, node):
            test = node.test
            if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value is None and isinstance(test.ops[0], (ast.Is, ast.IsNot))):
                if not (isinstance(test.left, ast.Name) and optional and test.left.id in optional[-1]):
                    body, other = ([node.body], [node.orelse]) if isinstance(node, ast.IfExp) else (node.body, node.orelse)
                    if not other and any(isinstance(n, ast.Return) for n in body):
                        parent = parents.get(id(node))
                        statements = getattr(parent, "body", [])
                        if isinstance(statements, list) and node in statements:
                            other = statements[statements.index(node) + 1:]
                    primary, alternate = (other, body) if isinstance(test.ops[0], ast.Is) else (body, other)
                    prior = [test.left] if isinstance(test.left, ast.Call) else []
                    if isinstance(test.left, ast.Name):
                        function_node = next((fn for fn, qual, _, _ in functions if contexts and qual == contexts[-1]), None)
                        prior = [stmt.value for stmt in (function_node.body if function_node else ())
                                 if isinstance(stmt, ast.Assign) and stmt.lineno < node.lineno
                                 and any(isinstance(t, ast.Name) and t.id == test.left.id for t in stmt.targets)]
                    add("none-switch", node, _lines(primary), _lines(alternate),
                        primary_calls=prior[-1:] or _value_calls(primary), alternate_calls=_value_calls(alternate))
            self.generic_visit(node)
        visit_IfExp = visit_If
    Finder().visit(tree)
    counts = defaultdict(int)
    for site in sites:
        counts[(site.kind, site.function, site.line)] += 1
    bound = []
    for site in sites:
        if site.kind in {"or-call", "none-switch"}:
            own = operand_calls[site.id]
            refs = set(site.primary_calls + site.alternate_calls)
            lines = set(site.primary_call_lines + site.alternate_call_lines)
            siblings = any(isinstance(n, ast.Call) and id(n) not in own and n.lineno in lines
                           and refs.intersection(_references([n], path, site.function, definitions)) for n in ast.walk(tree))
            site = replace(site, ambiguous=siblings or counts[(site.kind, site.function, site.line)] > 1)
        bound.append(site)
    return bound + _duplicates({path: source})


def _index_recordings(recordings):
    """Operation-local references into the original facts; never alter or persist the receipt."""
    indexed = []
    for row in recordings:
        functions, parents, calls, frames, ends = defaultdict(list), defaultdict(list), defaultdict(list), {}, {}
        for event in row.get("observer_events", ()):
            functions[(event.get("path"), event.get("function"))].append(event)
            token = event.get("call_token")
            if token is not None:
                calls[token].append(event)
                frames[token] = event
                if event.get("kind") == "statement":
                    parents[token].append(event)
                elif event.get("kind") == "return":
                    ends[token] = event
            if event.get("kind") == "return" and event.get("parent_call_token") is not None:
                parents[event["parent_call_token"]].append(event)
        indexed.append({**row, "_function_events": functions, "_parent_events": parents,
                        "_call_events": calls, "_frames": frames, "_ends": ends})
    return indexed


def _child_returns(row, token, refs, lines):
    if not refs or not lines:
        return []
    result, parent_line = [], None
    events = row["_parent_events"].get(token, ()) if "_parent_events" in row else row.get("observer_events", ())
    for event in events:
        if event.get("call_token") == token and event.get("kind") == "statement":
            parent_line = event.get("line")
        if (event.get("kind") == "return" and event.get("parent_call_token") == token and parent_line in lines
                and event.get("path", "") + "#" + event.get("function", "") in refs):
            result.append(event)
    return result


def _complete_row(row):
    return (row.get("pytest_outcome") in {"passed", "failed"} and "observer_events" in row
            and {r.get("when") for r in row.get("pytest_reports", ())} == {"setup", "call", "teardown"}
            and row.get("binding_status", "current") == "current")


def _cli_entrypoints(root, sources):
    """Literal packaging roles use the existing discovery/import-root owners."""
    from ..map.discover import console_scripts
    from ..map.inventory import module_name, python_roots
    roots = python_roots(list(sources))
    modules = defaultdict(list)
    for path in sources:
        modules[module_name(path, roots)].append(path)
    result = []
    for name, target, via in console_scripts(root):
        module, separator, symbol = target.partition(":")
        symbol = symbol.strip().split("[", 1)[0].strip()
        paths = modules.get(module.strip(), [])
        if not separator or len(paths) != 1:
            continue
        path = paths[0]
        _, functions = _definitions(ast.parse(sources[path], filename=path))
        if symbol in {qual for _node, qual, _owner, _kind in functions}:
            result.append({"name": name, "path": path, "function": symbol, "via": via,
                           "metadata_identity": content_digest(root / via), "status": "current"})
    return result


def _cli_return(row, token, entrypoints):
    """The outermost observed console-script caller determines standard exit semantics."""
    roles = {(entry["path"], entry["function"]): entry for entry in entrypoints}
    frames, ends = row.get("_frames", {}), row.get("_ends", {})
    if "_frames" not in row:
        for event in row.get("observer_events", ()):
            current = event.get("call_token")
            if current is not None:
                frames[current] = event
                if event.get("kind") == "return":
                    ends[current] = event
    entry, seen = None, set()
    while token is not None and token not in seen:
        seen.add(token)
        frame = frames.get(token, {})
        role = roles.get((frame.get("path"), frame.get("function")))
        if role is not None:
            entry = {"entrypoint": role, "call_token": token, **ends.get(token, {})}
        token = frame.get("parent_call_token")
    if entry is None:
        return None
    result = entry.get("result", {})
    status = "unknown"
    if (entry["entrypoint"]["status"] == "current" and entry.get("return_status") == "returned"
            and result.get("status") == "current"):
        value = result["value"]
        if value is None or type(value) in (int, bool) and value == 0:
            status = "success"
        elif type(value) in (int, bool) and 0 < value < 256 or type(value) in (str, float):
            status = "failure"
    return {"test": row["test"], "status": status, "entrypoint": entry["entrypoint"],
            "call_token": entry["call_token"], "return_status": entry.get("return_status"), "result": result}


def _asserted_failure_return(row, token, end):
    """A passing test must actually assert the returned error code, not merely call it."""
    facts = end.get("return_fields", {})
    status, code = facts.get("status", {}), facts.get("exit_code", {})
    if not (status.get("status") == code.get("status") == "current" and status.get("value") == "failed"
            and type(code.get("value")) is int and 0 < code["value"] < 256):
        known_builtin = (end.get("result", {}).get("status") == "current"
                         or end.get("return_kind") in {"dict", "list", "tuple", "set", "frozenset", "str", "bytes",
                                                       "bool", "int", "float", "complex", "none"}
                         or any(fact.get("status") == "current" for fact in facts.values()))
        return None if known_builtin else {"status": "unknown", "reason":
            "The completed fallback return has no current built-in representation; alternate success is unproved."}
    source = Path(row.get("source", ""))
    try:
        if content_digest(source) != row.get("digest"):
            return {"status": "unknown", "reason": "The assertion source is not current."}
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return {"status": "unknown", "reason": "The assertion source cannot be checked."}
    parent = end.get("parent_call_token")
    events = row.get("_parent_events", {}).get(parent, ())
    if "_parent_events" not in row:
        events = [e for e in row.get("observer_events", ()) if e.get("call_token") == parent
                  or e.get("kind") == "return" and e.get("parent_call_token") == parent]
    call_line, returned_at = None, None
    for index, event in enumerate(events):
        if event.get("call_token") == parent and event.get("kind") == "statement":
            call_line = event.get("line")
        if event.get("call_token") == token and event.get("kind") == "return":
            returned_at = index
            break
    test_path = row.get("test", "").split("::", 1)[0]
    frames = row.get("_frames", {})
    frame = frames.get(parent) or next((e for e in events if e.get("call_token") == parent), {})
    if frame.get("path") != test_path or returned_at is None:
        return {"status": "unknown", "reason": "The structured failure has no directly observed test receiver."}
    functions = _definitions(tree)[1]
    function = next((node for node, qual, _owner, _kind in functions if qual == frame.get("function")), None)
    if function is None:
        return {"status": "unknown", "reason": "The structured failure receiver cannot be bound."}
    statement = next((node for node in function.body if node.lineno == call_line), None)
    def same_call(call):
        if not isinstance(call, ast.Call):
            return False
        leaf = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)
        return leaf == end.get("function", "").split(".")[-1]
    name = None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name) and same_call(statement.value):
        name = statement.targets[0].id
    elif not isinstance(statement, ast.Assert):
        return {"status": "unknown", "reason": "The returned failure is not bound to a direct assertion."}
    def asserted_result(expression):
        if isinstance(expression, ast.BoolOp) and isinstance(expression.op, (ast.And, ast.Or)):
            values = [asserted_result(value) for value in expression.values]
            if any(value is None for value in values):
                return None
            return all(values) if isinstance(expression.op, ast.And) else any(values)
        if not (isinstance(expression, ast.Compare) and len(expression.ops) == 1 and isinstance(expression.ops[0], ast.Eq)):
            return None
        left, right = expression.left, expression.comparators[0]
        if isinstance(left, ast.Constant):
            left, right = right, left
        if not (isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Constant)
                and left.slice.value in ("status", "exit_code") and isinstance(right, ast.Constant)):
            return None
        receiver = (isinstance(left.value, ast.Name) and left.value.id == name if name else same_call(left.value))
        fact = facts.get(left.slice.value, {})
        if not receiver or fact.get("status") != "current" or type(right.value) not in (str, int, bool, float, type(None)):
            return None
        actual = fact["value"]
        return type(actual) is type(right.value) and actual == right.value
    after_lines = {e.get("line") for e in events[returned_at + 1:] if e.get("call_token") == parent and e.get("kind") == "statement"}
    position = function.body.index(statement) if statement in function.body else -1
    assertion = statement if isinstance(statement, ast.Assert) else next(iter(function.body[position + 1:position + 2]), None)
    if isinstance(assertion, ast.Assert):
        calls = [node for node in ast.walk(assertion.test) if isinstance(node, ast.Call)]
        direct = assertion is statement
        pure_receiver = not calls if name else len(calls) == 1 and same_call(calls[0])
        if pure_receiver and (direct or assertion.lineno in after_lines) and asserted_result(assertion.test) is True:
            return {"status": "failure", "exit_code": code["value"], "assertion_line": assertion.lineno,
                    "test": row["test"], "call_token": token, "return_fields": facts}
    return {"status": "unknown", "reason": "The passing test does not have a fully observed literal assertion of the returned failure fields."}


def classify(site, recordings, *, capture_status, probe=None, authorization=None, root=None, binding_status="current", test_scope=None, cli_entrypoints=()):
    """Labels follow real, ordered invocations; the baseline failure stays in the receipt."""
    reached, primary, alternate, alt_reached, failed, visible = (set() for _ in range(6))
    primary_failures = []
    name_observations, all_name_alternates_empty = [], True
    cli_returns, structured_returns = [], []
    reported = set()
    incomplete = binding_status != "current" or site.function == "<module>"
    negative_complete = (capture_status == "current" and bool(recordings) and (test_scope or {}).get("finished") is True
                         and not (test_scope or {}).get("observer_gaps"))
    unassigned = [event for event in (test_scope or {}).get("unassigned_events", ())
                  if (event.get("path") == site.path and event.get("function") == site.function)
                  or (site.kind == "duplicate" and event.get("path") == site.peer_path and event.get("function") == site.peer_function)]
    negative_complete &= not unassigned
    observed_complete = (not incomplete and not site.ambiguous and not unassigned
                         and (test_scope or {}).get("finished") is True)
    observed_calls, completed_calls, site_executions = 0, 0, 0
    unresolved = site.ambiguous
    for row in recordings:
        if not _complete_row(row):
            negative_complete = False
            if any(e.get("path") == site.path and e.get("function") == site.function
                   for e in row.get("observer_events", ())):
                observed_complete = False
            continue
        negative_complete &= not row.get("observer_gaps")
        test = row.get("test")
        calls = defaultdict(list)
        if "_function_events" in row:
            keys = [(site.path, site.function)]
            if site.kind == "duplicate":
                keys.append((site.peer_path, site.peer_function))
            events = (event for key in dict.fromkeys(keys) for event in row["_function_events"].get(key, ()))
        else:
            events = row.get("observer_events", ())
        for event in events:
            first = event.get("path") == site.path and event.get("function") == site.function
            second = site.kind == "duplicate" and event.get("path") == site.peer_path and event.get("function") == site.peer_function
            if first or second:
                if event.get("call_token") is None:
                    negative_complete = observed_complete = False
                else:
                    calls[(second, event["call_token"])].append(event)
        for (peer, token), sequence in calls.items():
            observed_calls += 1
            statements = {e.get("line") for e in sequence if e.get("kind") == "statement"}
            end = next((e for e in reversed(sequence) if e.get("kind") == "return"), {})
            returned, propagated = end.get("return_status") == "returned", end.get("return_status") == "raised"
            if not end or end.get("return_status") not in {"returned", "raised"}:
                negative_complete = observed_complete = False
                continue
            completed_calls += 1
            p, a = bool(statements.intersection(site.primary)), bool(statements.intersection(site.alternate))
            faults = [e for e in sequence if e.get("kind") == "exception" and e.get("line") in site.primary]
            name_primary_served, name_alternate_served = False, False
            if site.kind == "duplicate":
                p, a = not peer, peer
                faults = []
            elif site.truth_names:
                if site.line not in statements:
                    continue
                observations = [event for event in sequence if event.get("kind") == "statement"
                                and event.get("line") == site.line and event.get("statement") == site.id]
                name_observations.extend({"test": test, "site_call_token": token, **event} for event in observations)
                site_executions += len(observations)
                p, a, faults = False, False, []
                empty = []
                if not observations:
                    negative_complete = observed_complete = False
                for event in observations:
                    left, right = [event.get("name_truth", {}).get(name, {}) for name in site.truth_names]
                    if (any(fact.get("status") != "current" or type(fact.get("truth")) is not bool for fact in (left, right))
                            or left.get("type") == right.get("type") == "builtins:bool"):
                        negative_complete = observed_complete = False
                        continue
                    p = True
                    name_primary_served |= left["truth"]
                    if not left["truth"]:
                        a = True
                        faults.append(event)
                        name_alternate_served |= right["truth"]
                        empty.append(not right["truth"] and right.get("type") in {
                            "builtins:list", "builtins:tuple", "builtins:dict", "builtins:set",
                            "builtins:frozenset", "builtins:str", "builtins:bytes"})
                if a:
                    all_name_alternates_empty &= bool(empty) and all(empty) and returned
            elif site.kind in {"or-call", "none-switch"}:
                p_calls = _child_returns(row, token, site.primary_calls, site.primary_call_lines)
                a_calls = _child_returns(row, token, site.alternate_calls, site.alternate_call_lines)
                faults = [event for call in p_calls if call.get("return_status") == "raised"
                          for event in (row["_call_events"].get(call.get("call_token"), ())
                                        if "_call_events" in row else row.get("observer_events", ()))
                          if event.get("call_token") == call.get("call_token") and event.get("kind") == "exception"]
                known_p = [e for e in p_calls if e.get("return_status") == "returned" and e.get("result", {}).get("status") == "current"]
                if site.kind == "or-call":
                    p, a = bool(p_calls), bool(a_calls)
                    unresolved |= not site.primary_calls or not site.alternate_calls or bool(set(site.primary_calls) & set(site.alternate_calls))
                else:
                    if set(site.primary).intersection(site.alternate):
                        p, a = bool(known_p), bool(a_calls)
                        unresolved |= not site.alternate_calls
                    else:
                        p |= bool(known_p)
                        a |= bool(a_calls)
                if known_p and a and (not known_p[-1]["result"]["value"] if site.kind == "or-call" else known_p[-1]["result"]["value"] is None):
                    faults.append(known_p[-1])
            if not (p or a or site.line in statements):
                continue
            reached.add(test)
            primary_failures.extend({"test": test, "site_call_token": token, **event} for event in faults)
            if a:
                alt_reached.add(test)
            alternate_served = end.get("line") in site.alternate
            if site.truth_names:
                alternate_served = name_alternate_served
            if site.alternate_calls:
                alternate_served |= any(e.get("return_status") == "returned" for e in
                                        _child_returns(row, token, site.alternate_calls, site.alternate_call_lines))
            if site.kind == "duplicate":
                alternate_served = peer
            caller = (_cli_return(row, token, cli_entrypoints)
                      if faults and a and alternate_served and returned and cli_entrypoints else None)
            if caller is not None and caller["status"] == "failure":
                candidate = end.get("result", {})
                if candidate.get("status") != "current" or candidate.get("value") != caller["result"]["value"]:
                    caller = {**caller, "status": "unknown", "reason":
                              "The CLI failed, but its exit result is not the candidate's observed return; this failure is not correlated."}
            structured = _asserted_failure_return(row, token, end) if faults and a and alternate_served and returned and (caller is None or caller["status"] != "success") else None
            if structured is not None:
                structured_returns.append({"site_call_token": token, **structured})
                if structured["status"] == "failure":
                    visible.add(test)
                else:
                    negative_complete = False
            caller_accepts = (caller is None or caller["status"] == "success") and structured is None
            if caller is not None:
                cli_returns.append({"site_call_token": token, **caller})
                if caller["status"] == "failure":
                    visible.add(test)
                elif caller["status"] == "unknown":
                    negative_complete = False
            if ((name_primary_served if site.truth_names else p and not a and not faults)
                    and returned and row.get("pytest_outcome") == "passed"):
                primary.add(test)
            if a and alternate_served and returned and caller_accepts and row.get("pytest_outcome") == "passed":
                alternate.add(test)
                if statements.intersection(site.report_lines):
                    reported.add(test)
                if faults:
                    failed.add(test)
            if faults and propagated and caller is None and end.get("line") in set(site.primary + site.alternate):
                visible.add(test)
    authorized = None
    if authorization is not None:
        if root is None or not isinstance(authorization, dict):
            raise ValueError("route authority needs a stored request and the source root")
        from ..map.requests import owner_quote
        terms = [site.function.split(".")[-1]] + ([site.peer_function.split(".")[-1]] if site.peer_function else [])
        for term in terms:
            authorized = owner_quote(root, authorization["quote"], [term], request=authorization.get("request"))
    confirmed = []
    if ((probe or {}).get("site") == site.id and (probe or {}).get("binding_status") == "current"
            and (probe or {}).get("source_identity") == site.source_identity):
        marker = "FlowGuard disabled fallback " + site.id
        for row in probe.get("recordings", ()):
            exceptions = [e for e in row.get("observer_events", ()) if e.get("kind") == "exception"]
            test_exceptions = [e for e in exceptions if e.get("path") == row.get("test", "").split("::")[0]]
            if _complete_row(row) and row.get("test") in failed and row.get("pytest_outcome") == "failed" and test_exceptions and marker in test_exceptions[-1].get("exception", {}).get("message", ""):
                confirmed.append(row["test"])
    observed_empty = (bool(site.truth_names) and observed_complete and site_executions > 0
                      and alt_reached and all_name_alternates_empty and not alternate)
    scope = "recorded tests only"
    label, reason = "UNKNOWN", "Detailed native observations do not resolve this route."
    if incomplete:
        reason = "Native scope, completed tests or invocation identity is missing; absence cannot establish DEAD."
    elif site.reminder:
        reason = "Input defaults are counted; their selected input values are not inferred from line hits."
    elif authorized and reached:
        label, reason = "DECLARED", "A validated live owner quotation authorizes these routes."
    elif reported:
        reason = "The executed handler reports the bound exception; a passing error-report test does not establish alternate success."
    elif unresolved:
        reason = "The invocation cannot distinguish this candidate's exact call sites or receiver values."
    elif confirmed:
        label, reason = "MASKING", "The retained primary failure was hidden by a passing fallback; disabling that fallback failed its reaching test."
    elif primary and alternate and (site.kind != "none-switch" or site.primary_calls and site.alternate_calls):
        label, reason = "BOTH", "Both implementations served actual passing tests without live route authority."
    elif visible:
        label, reason = "VISIBLE", ("The selected passing test asserted the actual returned structured failure code."
                                    if any(row["status"] == "failure" for row in structured_returns)
                                    else "The observed console-script caller returned a standard failing exit result."
                                    if any(row["status"] == "failure" for row in cli_returns)
                                    else "The primary failure propagated to the caller.")
    elif negative_complete and not alt_reached:
        label, reason = "DEAD", "The alternate was not reached within this recorded finite test scope."
    elif negative_complete and site.truth_names and all_name_alternates_empty and not alternate:
        label, reason = "DEAD", "The alternate was attempted but only produced empty built-in values within this recorded finite test scope."
    elif observed_empty:
        label, reason = "DEAD", "The alternate only produced empty built-in values in the completed observed invocations; unobserved child calls are outside this scope."
        scope = "completed observed invocations only"
    elif any(row["status"] == "unknown" for row in structured_returns):
        reason = next(row["reason"] for row in structured_returns if row["status"] == "unknown")
    elif any(row["status"] == "unknown" for row in cli_returns):
        reason = next((row["reason"] for row in cli_returns if row.get("reason")),
                      "The observed console-script caller has no current standard exit result; alternate success is unproved.")
    elif not negative_complete:
        reason = "The requested negative scope is incomplete; completed local positive witnesses remain usable."
    return {"site": site.to_json(), "classification": label, "reason": reason, "scope": scope,
            "observation_scope": {"calls": observed_calls, "completed_calls": completed_calls,
                                  "site_executions": site_executions, "primary_served_tests": len(primary),
                                  "alternate_attempt_tests": len(alt_reached), "alternate_served_tests": len(alternate),
                                  "selected_test_scope_complete": bool(negative_complete),
                                  "limits": sorted(set((test_scope or {}).get("observer_gaps", ()))
                                            | {gap for row in recordings for gap in row.get("observer_gaps", ())})},
            "reached": sorted(reached), "primary": sorted(primary), "alternate": sorted(alternate),
            "primary_failed": sorted(failed), "primary_failures": primary_failures, "visible": sorted(visible),
            "alternate_reached": sorted(alt_reached), "probe_confirmed": sorted(confirmed), "authority": authorized,
            "reported_errors": sorted(reported),
            "name_observations": name_observations,
            "cli_returns": cli_returns, "structured_returns": structured_returns,
            "unassigned_events": unassigned,
            "probe_tests": sorted(failed) if not (incomplete or unresolved or reported or authorized) else [],
            "negative_scope_complete": bool(negative_complete or observed_empty)}


def record_tests(root, nodeids=None, *, timeout=30, statements=None):
    """One native pytest run, including its actual per-nodeid result and source digest."""
    from ..native.session import replay
    spec = {"root": str(Path(root).resolve()), "classes": []}
    if statements:
        spec["statements"] = statements
    result = replay(spec, [], operation="record",
                    options={"test_nodeids": nodeids} if nodeids is not None else {}, timeout=timeout)
    rows = result.get("recordings", ())
    current = (result.get("test_scope", {}).get("finished") is True and not result.get("test_scope", {}).get("observer_gaps")
               and result.get("pytest_exitcode") in (0, 1)
               and bool(rows) and all(_complete_row(row) and not row.get("observer_gaps") for row in rows))
    errors = []
    for row in rows:
        try:
            source = Path(row["source"]).resolve()
            imported = result.get("footprint", {}).get("files", {}).get(str(source), {}).get("source_sha256")
            if not source.is_relative_to(Path(root).resolve()) or imported != row["digest"] or content_digest(source) != row["digest"]:
                errors.append({"test": row["test"], "source": str(source), "status": "stale", "reason": "test source changed during capture"})
        except OSError as error:
            errors.append({"test": row["test"], "source": row["source"], "status": "unknown", "reason": str(error)})
    stale_sources = {error["source"] for error in errors}
    for row in rows:
        row["binding_status"] = "unknown" if row["source"] in stale_sources else "current"
    return {**result, "capture_status": "current" if current and not errors else "unknown", "capture_errors": errors,
            "binding_status": "current" if not errors else "unknown"}


def _project_files(root):
    return [name for name in list_files(root) if not matches_any(name, DEFAULT_IGNORE)]


def scan_project(root):
    """Scan project code through the existing file inventory; preserve unreadable/invalid sources."""
    root = Path(root).resolve()
    sources, errors = {}, []
    for name in _project_files(root):
        if not name.endswith(".py") or "tests" in Path(name).parts or Path(name).name.startswith("test_") or Path(name).name == "conftest.py":
            continue
        path = root / name
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("source path is a symlink or outside its project")
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=name)
            sources[name] = source
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            errors.append({"path": name, "status": "unknown", "reason": f"{type(error).__name__}: {error}"})
    sites = {site.id: site for path, source in sources.items() for site in find_sites(path, source) if site.kind != "duplicate"}
    sites.update((site.id, site) for site in _duplicates(sources))
    return {"sites": list(sites.values()), "sources": {path: _identity(source) for path, source in sources.items()},
            "cli_entrypoints": _cli_entrypoints(root, sources), "errors": errors}


def disable_probe(root, site, nodeids, *, timeout=30):
    """Change one AST route only in a private regular-file copy, then use the same recorder."""
    import shutil
    import tempfile
    root = Path(root).resolve()
    relative = Path(site.path)
    source_path = root / relative
    if relative.is_absolute() or ".." in relative.parts or source_path.is_symlink() or not source_path.resolve().is_relative_to(root):
        raise ValueError("fallback source is outside its project or a symlink")
    before = content_digest(source_path)
    if not site.source_identity or before != site.source_identity:
        raise ValueError("fallback source changed since its site was scanned")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=site.path)
    target = next((n for n in ast.walk(tree) if (getattr(n, "lineno", None), getattr(n, "col_offset", None)) == site.node and
                  (isinstance(n, ast.ExceptHandler) if site.kind == "handler" else isinstance(n, (ast.If, ast.IfExp)) if site.kind == "none-switch" else
                   isinstance(n, ast.BoolOp) if site.kind == "or-call" else False)), None)
    if target is None:
        raise ValueError("fallback source changed or this candidate has no executable disable probe")
    marker = "FlowGuard disabled fallback " + site.id
    failure = ast.Raise(exc=ast.Call(func=ast.Name(id="RuntimeError", ctx=ast.Load()), args=[ast.Constant(marker)], keywords=[]), cause=None)
    if isinstance(target, ast.ExceptHandler):
        target.body.insert(0, failure)
    elif isinstance(target, ast.If):
        branch = target.body if isinstance(target.test.ops[0], ast.Is) else target.orelse
        if branch:
            branch.insert(0, failure)
        else:
            target.orelse = [failure]  # Disable its actual fall-through alternate only.
    elif isinstance(target, ast.IfExp):
        name = "body" if isinstance(target.test.ops[0], ast.Is) else "orelse"
        setattr(target, name, ast.parse("(_ for _ in ()).throw(RuntimeError(" + repr(marker) + "))", mode="eval").body)
    else:
        for index in range(1, len(target.values)):
            target.values[index] = ast.parse("(_ for _ in ()).throw(RuntimeError(" + repr(marker) + "))", mode="eval").body
    ast.fix_missing_locations(tree)
    with tempfile.TemporaryDirectory(prefix="flowguard-disable-") as directory:
        private = Path(directory) / "source"
        for name in _project_files(root):
            path = root / name
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
                raise ValueError("disable probe refuses project symlinks")
            destination = private / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        (private / relative).write_text(ast.unparse(tree) + "\n", encoding="utf-8")
        result = record_tests(private, sorted(set(nodeids)), timeout=timeout)
    if content_digest(source_path) != before:
        raise ValueError("original fallback source changed during its probe")
    return {**result, "site": site.id, "source_identity": before, "changed": "private copy only"}


def analyze(root, *, nodeids=None, authorizations=None, timeout=30):
    """Record once, then probe only actual passing tests that reached a failed primary's fallback."""
    root = Path(root).resolve()
    scan = scan_project(root)
    statements = [{"id": site.id, "path": site.path, "function": site.function, "line": site.line,
                   "unambiguous": True, "truth_names": list(site.truth_names),
                   "return_fields": ["status", "exit_code"] if site.kind == "handler" else []}
                  for site in scan["sites"] if (site.truth_names or site.kind == "handler") and not site.ambiguous]
    baseline = record_tests(root, nodeids, timeout=timeout, statements=statements)
    status = baseline["capture_status"] if not scan["errors"] else "unknown"
    stale = set()
    for name, digest in scan["sources"].items():
        try:
            changed = content_digest(root / name) != digest
        except OSError as error:
            scan["errors"].append({"path": name, "status": "unknown", "reason": str(error)})
            changed = True
        if changed:
            stale.add(name)
            status = "unknown"
            scan["errors"].append({"path": name, "status": "stale", "reason": "source changed during capture"})
    for entry in scan["cli_entrypoints"]:
        try:
            current = content_digest(root / entry["via"]) == entry["metadata_identity"] and entry["path"] not in stale
        except OSError:
            current = False
        entry["status"] = "current" if current else "unknown"
    recordings = _index_recordings(baseline["recordings"])
    results, probes = [], []
    for site in scan["sites"]:
        authority = (authorizations or {}).get(site.id)
        binding = "unknown" if site.path in stale or site.peer_path in stale else "current"
        result = classify(site, recordings, capture_status=status, authorization=authority, root=root, binding_status=binding, test_scope=baseline["test_scope"], cli_entrypoints=scan["cli_entrypoints"])
        if result["probe_tests"]:
            try:
                probe = disable_probe(root, site, result["probe_tests"], timeout=timeout)
            except (OSError, ValueError) as error:
                probe = {"site": site.id, "capture_status": "unknown", "error": f"{type(error).__name__}: {error}"}
            probes.append(probe)
            result = classify(site, recordings, capture_status=status, probe=probe, authorization=authority, root=root, binding_status=binding, test_scope=baseline["test_scope"], cli_entrypoints=scan["cli_entrypoints"])
        results.append(result)
    return {"capture_status": status, "sites": results, "conflicts": [r for r in results if r["classification"] in {"MASKING", "BOTH"}],
            "counts": {"dead": sum(r["classification"] == "DEAD" for r in results),
                       "unreached_handlers": sum(r["site"]["kind"] == "handler" and not r["alternate_reached"] and not r["unassigned_events"] for r in results),
                       "input_defaults": sum(r["site"]["reminder"] for r in results),
                       "unknown": sum(r["classification"] == "UNKNOWN" for r in results)},
            "recording": baseline, "probes": probes, "sources": scan["sources"], "errors": scan["errors"],
            "cli_entrypoints": scan["cli_entrypoints"]}
