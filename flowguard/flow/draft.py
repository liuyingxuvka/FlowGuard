"""Static vocabulary and one-time TODO files; behavior belongs to the model author."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re

from ..map.common import DEFAULT_IGNORE, matches_any, read_source
from ..map.discovery_syntax import _FileVisitor, _annotation_class, _mutating_method_writes, _name
from ..map.inventory import list_files, module_name, python_roots, syntax_tree


class DraftError(ValueError):
    """The requested source cannot be drafted statically."""


@dataclass(frozen=True)
class Draft:
    """CLI-independent result: candidates and two deliberately incomplete files."""
    vocabulary: dict
    model: str
    adapter: str

    def to_dict(self):
        return {"vocabulary": self.vocabulary, "model": self.model, "adapter": self.adapter}


def _signature(node, kind):
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    default_start = len(positional) - len(args.defaults)
    parameters = [{"name": arg.arg,
                   "kind": "positional_only" if i < len(args.posonlyargs) else "positional_or_keyword",
                   "annotation": _name(arg.annotation), "has_default": i >= default_start}
                  for i, arg in enumerate(positional)]
    if kind in {"method", "class", "property"} and parameters:
        parameters = parameters[1:]
    if args.vararg:
        parameters.append({"name": args.vararg.arg, "kind": "var_positional",
                           "annotation": _name(args.vararg.annotation), "has_default": False})
    parameters.extend({"name": arg.arg, "kind": "keyword_only", "annotation": _name(arg.annotation),
                       "has_default": default is not None}
                      for arg, default in zip(args.kwonlyargs, args.kw_defaults))
    if args.kwarg:
        parameters.append({"name": args.kwarg.arg, "kind": "var_keyword",
                           "annotation": _name(args.kwarg.annotation), "has_default": False})
    return parameters


def _kind(node, owner):
    decorators = {_name(decorator).rsplit(".", 1)[-1] for decorator in node.decorator_list}
    if decorators & {"property", "cached_property", "setter", "deleter"}:
        return "property"
    if "staticmethod" in decorators:
        return "static"
    if "classmethod" in decorators:
        return "class"
    return "method" if owner else "function"


def _direct_nodes(node):
    """A definition's own syntax, without nested function/class/lambda bodies."""
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from _direct_nodes(child)


def _class_scope(tree, classes, selected):
    """Candidate same-module source bases, without resolving imports or running code."""
    definitions = [node.name for node in ast.walk(tree)
                   if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    rebound = {node.id for node in _direct_nodes(tree)
               if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
    for node in _direct_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            rebound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            if any(alias.name == "*" for alias in node.names):
                rebound.update(classes)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            rebound.add(node.name)
        elif isinstance(node, ast.MatchMapping):
            rebound.add(node.rest)
    known = {name: cls for name, cls in classes.items()
             if definitions.count(name) == 1 and name not in rebound and not cls.decorator_list}
    scope = []

    def include(name):
        if name in scope:
            return
        scope.append(name)
        for base in classes[name].bases:
            if isinstance(base, ast.Name) and base.id in known and known[base.id].lineno < classes[name].lineno:
                include(base.id)

    include(selected)
    return scope


def _fields(visitor, classes, definitions):
    fields = {}
    for name, cls in classes.items():
        names = {field.rsplit(".", 1)[1] for field in visitor.state if field.rsplit(".", 1)[0] == name}
        names.update(target.id for node in cls.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                     for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                     if isinstance(target, ast.Name) and not target.id.startswith("__"))
        for field in sorted(names):
            fields[name + "." + field] = {"name": field, "owner": name, "literals": [], "symbols": [], "truth_tested": False}
    for owner, fn in definitions:
        if not owner:
            continue
        def attribute(node):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                key = owner + "." + node.attr
                return fields.setdefault(key, {"name": node.attr, "owner": owner, "literals": [], "symbols": [], "truth_tested": False})
            return None
        for node in _direct_nodes(fn):
            if isinstance(node, ast.Compare):
                values = [node.left, *node.comparators]
                for position, value in enumerate(values):
                    field = attribute(value)
                    if field is None:
                        continue
                    for other in values[:position] + values[position + 1:]:
                        members = other.elts if isinstance(other, (ast.Set, ast.Tuple, ast.List)) else [other]
                        for member in members:
                            if isinstance(member, ast.Constant) and type(member.value) in (str, bool):
                                if member.value not in field["literals"]:
                                    field["literals"].append(member.value)
                            elif isinstance(member, ast.Attribute) and not _name(member).startswith("self."):
                                if _name(member) not in field["symbols"]:
                                    field["symbols"].append(_name(member))
            if isinstance(node, (ast.If, ast.While)):
                pending = [node.test]
                while pending:
                    test = pending.pop()
                    if isinstance(test, ast.BoolOp):
                        pending.extend(test.values)
                    elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                        pending.append(test.operand)
                    field = attribute(test)
                    if field is not None:
                        field["truth_tested"] = True
    return list(fields.values())


_SETTINGS = re.compile(r"config|settings|options", re.I)


def _settings(tree, path, definitions):
    """Source candidates, not a second lexical/runtime binding resolver."""
    parameters = [{"name": arg.arg, "source": None, "line": node.lineno, "kind": "parameter",
                   "annotation": _annotation_class(arg.annotation) or _name(arg.annotation)}
                  for _, node in definitions
                  for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                  if _SETTINGS.search(arg.arg)]
    references = {row["annotation"].partition(".")[0] for row in parameters}
    candidates = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if _SETTINGS.search(name) or _SETTINGS.search(node.module or "") or name in references:
                    candidates.append({"name": name, "source": "." * node.level + (node.module or "") + ":" + alias.name,
                                       "line": node.lineno, "kind": "import"})
        elif isinstance(node, ast.Import):
            candidates.extend({"name": alias.asname or alias.name.split(".")[0], "source": alias.name,
                               "line": node.lineno, "kind": "import"}
                              for alias in node.names if _SETTINGS.search(alias.name) or _SETTINGS.search(alias.asname or "")
                              or (alias.asname or alias.name.split(".")[0]) in references)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if _SETTINGS.search(node.name) or node.name in references:
                candidates.append({"name": node.name, "source": path + ":" + node.name,
                                   "line": node.lineno, "kind": "local_class" if isinstance(node, ast.ClassDef) else "local_function"})
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.Assign, ast.AnnAssign)):
                        for target in member.targets if isinstance(member, ast.Assign) else [member.target]:
                            if isinstance(target, ast.Name) and (_SETTINGS.search(target.id) or target.id in references):
                                candidates.append({"name": target.id, "source": path + ":" + node.name + "." + target.id,
                                                   "line": member.lineno, "kind": "class_name"})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name) and (_SETTINGS.search(target.id) or target.id in references):
                    candidates.append({"name": target.id, "source": path + ":" + target.id,
                                       "line": node.lineno, "kind": "local_name"})
    return candidates + parameters


def draft(root: Path, target: str) -> Draft:
    """Read one Python file, class or direct method without executing project code.

    Candidates are lexical vocabulary, not domains, initial values, guards,
    effects, verified refusals, or a claim that native construction is supported.
    """
    root = Path(root).resolve()
    file, _, selector = target.partition(":")
    source = (root / file.replace("\\", "/")).resolve()
    if not source.is_relative_to(root):
        raise DraftError("draft source must be inside the project")
    path = source.relative_to(root).as_posix()
    if source.suffix != ".py" or matches_any(path, DEFAULT_IGNORE):
        raise DraftError("draft needs an inventoried Python source: " + path)
    files = [name for name in list_files(root) if name.endswith(".py") and not matches_any(name, DEFAULT_IGNORE)]
    if path not in files:
        raise DraftError("draft source is not in the project inventory: " + path)
    roots = python_roots(files)
    module = module_name(path, roots)
    try:
        tree = syntax_tree(read_source(source))
    except SyntaxError as error:
        raise DraftError(f"{path}:{error.lineno}: {error.msg}") from error
    source_classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    classes = source_classes
    top = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    definitions = [("", node) for node in top.values()]
    definitions.extend((owner, node) for owner, cls in classes.items() for node in cls.body
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    if selector:
        if selector in classes:
            definitions = [(owner, node) for owner, node in definitions if owner == selector]
            classes = {selector: classes[selector]}
        else:
            definitions = [(owner, node) for owner, node in definitions
                           if (owner + "." if owner else "") + node.name == selector]
            if not definitions:
                raise DraftError("no direct source definition: " + target)
            classes = {owner: classes[owner] for owner, _ in definitions if owner}
    visitor = _FileVisitor(module, module if path.endswith("/__init__.py") else module.rpartition(".")[0])
    visitor.visit(tree)
    _mutating_method_writes(visitor)
    operations, queries, constructors = [], [], []
    for owner, node in definitions:
        symbol = (owner + "." if owner else "") + node.name
        kind = _kind(node, owner)
        row = {"name": node.name, "symbol": symbol, "line": node.lineno, "kind": kind,
               "parameters": _signature(node, kind), "async": isinstance(node, ast.AsyncFunctionDef),
               "decorators": [_name(decorator) for decorator in node.decorator_list],
               "raises": sorted({_name(item.exc.func if isinstance(item.exc, ast.Call) else item.exc)
                                 for item in _direct_nodes(node) if isinstance(item, ast.Raise)
                                 and item.exc is not None})}
        if node.name == "__init__":
            constructors.append(row)
        elif kind == "property":
            queries.append(row)
        elif not node.name.startswith("_"):
            operations.append(row)
    unknown = ["inherited members need author review: " + name for name, cls in classes.items() if cls.bases]
    unknown.extend("async operation needs an explicit native boundary: " + row["symbol"] for row in operations if row["async"])
    known_descriptors = {"classmethod", "staticmethod", "property", "cached_property", "setter", "deleter"}
    unknown.extend("decorated operation needs author review: " + row["symbol"] for row in operations
                   if any(name.rsplit(".", 1)[-1] not in known_descriptors for name in row["decorators"]))
    names = [name for name in files if module_name(name, roots) == module]
    unique_import = len(names) == 1 and all(part.isidentifier() for part in module.split("."))
    if not unique_import:
        unknown.append("the source has no unique direct import binding")
    vocabulary = {"schema": "flowguard.draft.v1", "target": path + (":" + selector if selector else ""),
                  "module": module, "fields": _fields(visitor, classes, definitions), "operations": operations,
                  "queries": queries, "constructors": constructors, "settings": _settings(tree, path, definitions),
                  "unknown": unknown, "boundary": "static vocabulary only; literal labels are not domains, settings references are not resolved bindings, and behavior belongs to the author"}
    title = selector or module
    model = ("from flowguard.flow import Model\n\n" + f"m = Model({title!r}, covers={[path + ':' + selector if selector and selector.partition('.')[0] in classes else path]!r})\n"
             + "# TODO choose abstract fields/domains and initial states from the requirements.\n"
             + "# TODO write independent actions, guards, effects and obligations; bind the completed adapter.\n"
             + "# Candidate fields: " + ", ".join(field["owner"] + "." + field["name"] for field in vocabulary["fields"]) + "\n"
             + "# Candidate operations: " + ", ".join(row["symbol"] for row in operations) + "\n"
             + "raise NotImplementedError('TODO: independent model behavior and adapter binding')\nMODEL = m\n")
    system = module + ":" + next(iter(classes)) if len(classes) == 1 and unique_import else None
    class_scope = [module + ":" + name for name in _class_scope(tree, source_classes, next(iter(classes)))] if system else []
    adapter = ("# TODO review construction, argument recipes, legitimate refusals and projection.\n"
               + "# This file belongs to its author after creation; draft never updates it.\n"
               + "SPEC = " + repr({"system": system, "classes": class_scope, "refusal": []}) + "\n"
               + "OPERATIONS = {}  # TODO explicit model action -> native operation recipes\n\n"
               + "def state(snapshot):\n    raise NotImplementedError('TODO: actual snapshot to abstract state')\n\n"
               + "def bind(model):\n    return model.bind_adapter(SPEC, state=state, operations=OPERATIONS)\n")
    return Draft(vocabulary, model, adapter)


def write_once(result: Draft, model_path: Path, adapter_path: Path) -> tuple[Path, Path]:
    """Create TODO files exclusively. There is deliberately no overwrite/update mode."""
    paths = (Path(model_path), Path(adapter_path))
    if paths[0].resolve() == paths[1].resolve():
        raise DraftError("model and adapter need different paths")
    for path in paths:
        if path.exists() or path.is_symlink():
            raise FileExistsError("draft does not overwrite author-owned files: " + str(path))
    for path, text in zip(paths, (result.model, result.adapter)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    return paths
