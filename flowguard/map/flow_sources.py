"""Static flow declarations and source-bound Request commit links for ``where``.

No model imports, condition evaluation or project calls belong to this source view.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

from .common import git_blob, git_run, normalize_newlines, read_source
from .discover import function_spans
from .inventory import syntax_tree
from .mapfile import MapError
from .requests import request_commits, validate_request_links


_RULES = {"always", "only_when", "after", "reach", "progress", "option", "second_route"}
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


_UNKNOWN = object()
_MODEL_TYPE = object()
_FLOW_MODULE = object()
_FLOW_ROOT = object()
_MODEL_METHODS = _RULES | {"field", "objects", "setting", "action", "terminal",
                          "calls", "action_named", "init_state", "setting_proposals", "replace_actions",
                          "bind_adapter"}


class _Declaration:
    """One construction, shared by aliases; name reassignment never rewrites it."""

    def __init__(self, relative, line):
        self.data = dict(model=Path(relative).stem, path=relative, covers=[], line=line, rules=[])
        self.unknown = []

    def uncertain(self, line, what):
        self.unknown.append(f"{self.data['path']}:{line}: {what} unknown; declaration is not executed")
        self.data["covers"] = []
        self.data["rules"] = []


def _literal(node, bindings):
    if isinstance(node, ast.Name):
        value = bindings.get(node.id, _UNKNOWN)
        if value is _UNKNOWN:
            raise ValueError(f"{node.id} has no known literal binding")
        return value
    if isinstance(node, ast.Attribute):
        owner = _literal(node.value, bindings)
        if owner is _FLOW_ROOT and node.attr == "flow":
            return _FLOW_MODULE
        if owner is _FLOW_MODULE and node.attr == "Model":
            return _MODEL_TYPE
        raise ValueError("computed attribute")
    return ast.literal_eval(node)


def _covers(node, bindings):
    value = _literal(node, bindings)
    if not isinstance(value, (tuple, list)) or not all(isinstance(item, str) for item in value):
        raise ValueError("covers must be literal file[:symbol] strings")
    return list(value)  # Model copies the passed sequence when it is constructed.


def _read_declaration(tree, relative):
    bindings = {}

    def value(node):
        if isinstance(node, ast.Call):
            try:
                constructor = _literal(node.func, bindings) is _MODEL_TYPE
            except (ValueError, TypeError):
                constructor = False
            if constructor:
                dynamic = expression_calls(node.func)
                for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                    dynamic = expression_calls(argument) or dynamic
                declaration = _Declaration(relative, node.lineno)
                covers = next((kw.value for kw in node.keywords if kw.arg == "covers"),
                              node.args[1] if len(node.args) > 1 else ast.Tuple(elts=[], ctx=ast.Load()))
                try:
                    declaration.data["covers"] = _covers(covers, bindings)
                except (ValueError, TypeError) as error:
                    declaration.uncertain(node.lineno, f"covers cannot be resolved statically ({error}); coverage")
                if dynamic:
                    declaration.uncertain(node.lineno, "dynamic constructor argument; coverage and rules")
                return declaration
        try:
            return _literal(node, bindings)
        except (ValueError, TypeError):
            return _UNKNOWN

    def root_binding(node):
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        return bindings.get(node.id, _UNKNOWN) if isinstance(node, ast.Name) else _UNKNOWN

    def invalidate(node, line, what):
        bound = root_binding(node)
        if isinstance(bound, _Declaration):
            bound.uncertain(line, what + "; coverage and rules")
        elif bound is not _UNKNOWN:
            for name, alias in list(bindings.items()):
                if alias is bound:
                    bindings[name] = _UNKNOWN

    def expression_calls(node):
        """Observe calls evaluated now; a lambda body runs only when called later."""
        if isinstance(node, ast.Call):
            return call(node)
        children = [*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)] if isinstance(node, ast.Lambda) else ast.iter_child_nodes(node)
        dynamic = False
        for child in children:
            dynamic = expression_calls(child) or dynamic
        return dynamic

    def call(node):
        if not isinstance(node, ast.Call):
            return False
        dynamic = expression_calls(node.func)
        for argument in [*node.args, *(kw.value for kw in node.keywords)]:
            dynamic = expression_calls(argument) or dynamic
        if isinstance(node.func, ast.Attribute):
            owner = value(node.func.value)
            if isinstance(owner, _Declaration):
                if node.func.attr not in _MODEL_METHODS:
                    owner.uncertain(node.lineno, f"model mutation {node.func.attr}; coverage and rules")
                    return True
                elif node.func.attr in _RULES:
                    if dynamic:
                        return True
                    source = next((kw.value for kw in node.keywords if kw.arg == "source"), None)
                    if source is None:
                        return dynamic
                    try:
                        rid = _literal(source, bindings)
                        title = _literal(node.args[0], bindings)
                        if not isinstance(rid, str) or not isinstance(title, str):
                            raise ValueError("rule name and source must be strings")
                    except (IndexError, TypeError, ValueError) as error:
                        owner.unknown.append(f"{relative}:{node.lineno}: rule source/name cannot be resolved statically: {error}")
                    else:
                        owner.data["rules"].append(dict(model=owner.data["model"], path=relative, line=node.lineno,
                                                        kind=node.func.attr, name=title, source=rid))
                return dynamic
            # A container mutation is not an operation on another model instance.
            # Invalidating a literal alias never changes an earlier Model copy.
            if isinstance(root_binding(node.func.value), _Declaration):
                invalidate(node.func.value, node.lineno, "dynamic model-container call")
                return True
            elif owner is not _UNKNOWN and isinstance(node.func.value, ast.Name):
                invalidate(node.func.value, node.lineno, "literal mutation")
                return True
        for argument in [*node.args, *(kw.value for kw in node.keywords)]:
            if isinstance(root_binding(argument), _Declaration):
                invalidate(argument, node.lineno, "model passed to a dynamic call")
        # A helper can mutate a model through a global, without an argument.
        # This source view does not execute arbitrary top-level calls to discover that effect.
        for bound in list(bindings.values()):
            if isinstance(bound, _Declaration):
                bound.uncertain(node.lineno, "dynamic top-level call; coverage and rules")
        return True

    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                name = alias.asname or alias.name
                bindings[name] = (_MODEL_TYPE if statement.module in {"flowguard.flow", "flowguard.flow.model"} and alias.name == "Model"
                                  else _FLOW_MODULE if statement.module == "flowguard" and alias.name == "flow" else _UNKNOWN)
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                bindings[alias.asname or alias.name.split(".")[0]] = (_FLOW_MODULE if alias.asname else _FLOW_ROOT) if alias.name == "flowguard.flow" else _UNKNOWN
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            bound = value(statement.value)
            if bound is _UNKNOWN:
                call(statement.value)  # RHS sees the bindings before assignment.
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = bound
                elif isinstance(target, ast.Attribute):
                    owner = value(target.value)
                    if isinstance(owner, _Declaration):
                        if target.attr == "covers":
                            try:
                                owner.data["covers"] = _covers(statement.value, bindings)
                            except (ValueError, TypeError) as error:
                                owner.uncertain(target.lineno, f"covers mutation ({error}); coverage and rules")
                        else:
                            owner.uncertain(target.lineno, f"model attribute mutation {target.attr}; coverage and rules")
                    else:
                        invalidate(target, target.lineno, "literal attribute mutation")
                elif isinstance(target, ast.Subscript):
                    invalidate(target, target.lineno, "subscript mutation")
        elif isinstance(statement, ast.AugAssign):
            invalidate(statement.target, statement.lineno, "augmented mutation")
            if isinstance(statement.target, ast.Name):
                bindings[statement.target.id] = _UNKNOWN
        elif isinstance(statement, ast.Delete):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    bindings.pop(target.id, None)
                else:
                    invalidate(target, statement.lineno, "deletion")
        elif isinstance(statement, ast.Expr):
            call(statement.value)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[statement.name] = _UNKNOWN
            for decorator in statement.decorator_list:
                call(decorator)
        elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)):
            for node in ast.walk(statement):
                if isinstance(node, ast.Name):
                    bound = bindings.get(node.id)
                    if isinstance(bound, _Declaration):
                        bound.uncertain(statement.lineno, "conditional or dynamic declaration mutation; coverage and rules")
                    if isinstance(node.ctx, ast.Store):
                        bindings[node.id] = _UNKNOWN
    return bindings.get("MODEL")


def declarations(root):
    """Read literal declarations in source order, preserving model object bindings."""
    rows, unknown = [], []
    directory = Path(root) / ".flowguard/flow"
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            tree = syntax_tree(read_source(path))
        except (OSError, UnicodeError, SyntaxError) as error:
            unknown.append(f"{relative}: flow declarations unreadable: {error}")
            continue
        model = _read_declaration(tree, relative)
        if not isinstance(model, _Declaration):
            unknown.append(f"{relative}: exported MODEL has no static Model declaration; its coverage and rules are unknown")
            continue
        rows.append(model.data)
        unknown.extend(model.unknown)
    return rows, list(dict.fromkeys(unknown))


def binding_matches(cover, identifier):
    """A declared file or enclosing class covers that symbol; no textual similarity."""
    path, _, symbol = cover.replace("#", ":", 1).partition(":")
    target_path, _, target_symbol = identifier.partition("#")
    return path == target_path and (not symbol or symbol == target_symbol or target_symbol.startswith(symbol + "."))


def _spans(raw, symbol):
    if raw is None:
        return []
    tree = syntax_tree(read_source(Path("<git-source>.py"), data=raw))
    spans = [row[:2] for row in function_spans(tree) if row[2] == symbol]
    # Decorators are part of the function binding too; function_spans owns lexical names.
    decorators = {node.lineno: min([node.lineno, *(d.lineno for d in node.decorator_list)])
                  for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return [(decorators.get(start, start), end) for start, end in spans]


def symbol_request_commits(root, identifiers):
    """Commit trailers join only hunks intersecting that historical symbol's source."""
    output = {identifier: [] for identifier in identifiers}
    history = request_commits(root)
    unknown = list(history["unknown"])
    shallow = any("is shallow" in item for item in unknown)
    paths = {identifier.partition("#")[0] for identifier in identifiers}
    for entry in history["commits"]:
        if not entry["requests"]:
            continue
        commit, parents = entry["commit"], entry["parents"]
        if shallow and not parents:
            unknown.append(f"commit {commit[:12]} is a shallow boundary; its symbol changes are unknown")
            continue
        for path in sorted(paths):
            args = ("diff", parents[0], commit) if parents else ("show", "--format=", "--root", commit)
            patch = git_run(root, *args, "--no-ext-diff", "--no-textconv", "--no-renames", "--unified=0", "--", path).stdout.decode("utf-8", errors="replace")
            hunks = [(int(a), int(b or 1), int(c), int(d or 1)) for a, b, c, d in _HUNK.findall(patch)]
            if not hunks:
                continue
            try:
                before = git_blob(root, parents[0], path) if parents else None
                after = git_blob(root, commit, path)
                if before is not None and after is not None and normalize_newlines(before) == normalize_newlines(after):
                    continue
                for identifier in identifiers:
                    own_path, _, symbol = identifier.partition("#")
                    if own_path != path:
                        continue
                    old_spans, new_spans = _spans(before, symbol), _spans(after, symbol)
                    touched = any((count > 0 and any(start <= line + count - 1 and line <= end for start, end in spans))
                                  for old, old_count, new, new_count in hunks
                                  for line, count, spans in ((old, old_count, old_spans), (new, new_count, new_spans)))
                    if touched:
                        output[identifier].append(dict(commit=commit, requests=list(entry["requests"])))
            except (MapError, UnicodeError, SyntaxError) as error:
                unknown.append(f"commit {commit[:12]} {path}: symbol/request link unknown: {error}")
    return output, list(dict.fromkeys(unknown))


def live_request_ids(root, identifiers):
    live, unknown = [], []
    for identifier in sorted(set(identifiers)):
        try:
            validate_request_links(root, [dict(id=identifier, part=False)])
        except MapError as error:
            unknown.append(f"request {identifier} is not a live source: {error}")
        else:
            live.append(identifier)
    return live, unknown
