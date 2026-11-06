"""Files, Python import roots and module bindings for the generated structure map."""
from __future__ import annotations

import ast
import os
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path

from .common import git_common_directory, git_run, norm, read_source

@lru_cache(maxsize=4096)
def syntax_tree(text):
    """Read-only syntax shared by inventory and test analysis in this process."""
    return ast.parse(text)



@dataclass
class PyInfo:
    module: str
    symbols: set[str] = field(default_factory=set)   # "name" and "Class.method"
    imports: set[str] = field(default_factory=set)   # "a.b" for import, "a:b" for from-import
    loc: int = 0                                     # non-blank, non-comment lines
    parse_error: str = ""
    lazy_exports: dict[str, str] = field(default_factory=dict)
    import_lines: dict[str, int] = field(default_factory=dict)
    import_reads: dict[str, list[int]] = field(default_factory=dict)
    literal_dynamic_imports: dict[str, list[int]] = field(default_factory=dict)
    unknown_dynamic_imports: list[dict] = field(default_factory=list)



def list_files(root: Path) -> list[str]:
    """Tracked plus untracked-but-not-ignored files in a Git repository; the folder walk outside any repository.

    A failing Git inside a repository raises with Git's own message instead of walking ignored files."""
    if git_common_directory(root) is not None:
        listed = git_run(root, "ls-files", "-z", "-co", "--exclude-standard").stdout
        return sorted(f for f in (norm(os.fsdecode(x)) for x in listed.split(b"\0") if x) if (root / f).is_file())
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        found += [norm(str(Path(dirpath, n).relative_to(root))) for n in filenames]
    return sorted(found)



def python_roots(files: list[str]) -> list[str]:
    """Import roots: '' (repo root) plus every parent directory of a top-level package (e.g. 'src')."""
    roots = {""}
    present = set(files)
    for f in files:
        if f.endswith("/__init__.py"):
            pkg_dir = f.rsplit("/", 1)[0]
            parent = pkg_dir.rsplit("/", 1)[0] if "/" in pkg_dir else ""
            if (f"{parent}/__init__.py" if parent else "__init__.py") not in present:
                roots.add(parent)
    return sorted(roots, key=len, reverse=True)



def is_type_checking_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
            or isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")



def parse_python(root: Path, path: str, module: str, *, data: bytes | None = None) -> PyInfo:
    """Parse ``data`` when the caller already read the file's bytes, otherwise read them."""
    info = PyInfo(module=module)
    try:
        text = read_source(root / path, data=data)
    except OSError as exc:
        info.parse_error = str(exc)
        return info
    info.loc = sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("#"))
    try:
        tree = syntax_tree(text)
    except SyntaxError as exc:
        info.parse_error = f"SyntaxError: {exc.msg} line {exc.lineno}"
        return info
    package = module if path.endswith("__init__.py") else module.rpartition(".")[0]


    module_nodes = list(tree.body)
    cursor = 0
    while cursor < len(module_nodes):
        node = module_nodes[cursor]
        cursor += 1
        if isinstance(node, (ast.If, ast.Try, ast.With)):
            module_nodes.extend(node.body)
            module_nodes.extend(getattr(node, "orelse", []))
            module_nodes.extend(getattr(node, "finalbody", []))
            for handler in getattr(node, "handlers", []):
                module_nodes.extend(handler.body)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.symbols.add(node.name)
        elif isinstance(node, ast.ClassDef):
            info.symbols.add(node.name)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info.symbols.add(f"{node.name}.{sub.name}")
        elif isinstance(node, ast.Assign):
            info.symbols.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            info.symbols.add(node.target.id)

    if any(isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body):
        for node in tree.body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            if not isinstance(value, ast.Dict):
                continue
            for key, val in zip(value.keys, value.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                if isinstance(val, (ast.Tuple, ast.List)):
                    for name in val.elts:
                        if isinstance(name, ast.Constant) and isinstance(name.value, str):
                            info.lazy_exports[name.value] = key.value
                elif isinstance(val, ast.Constant) and isinstance(val.value, str):
                    info.lazy_exports[key.value] = val.value
    stack: list[ast.AST] = [tree]          # one traversal; "if TYPE_CHECKING:" imports are not runtime deps
    while stack:
        node = stack.pop()
        if is_type_checking_guard(node):
            stack.extend(node.orelse)
            continue
        if isinstance(node, ast.Import):
            info.imports.update(alias.name for alias in node.names)
            for alias in node.names:
                info.import_lines[alias.name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts)
                target = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                target = node.module or ""
            if target:
                info.imports.update(f"{target}:{alias.name}" for alias in node.names)
                for alias in node.names:
                    info.import_lines[f"{target}:{alias.name}"] = node.lineno
        else:
            stack.extend(ast.iter_child_nodes(node))
    _read_import_uses(tree, info)
    return info



def _read_import_uses(tree, info):
    """Potential source dependencies with literal names; never import the project.

    Only known import bindings qualify. Parameters or assignments that shadow an
    importer make it unknown rather than pretending it is the standard library.
    """
    scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
              ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

    def own_nodes(body):
        stack = list(body)
        while stack:
            node = stack.pop()
            if is_type_checking_guard(node):
                stack.extend(node.orelse)
                continue
            yield node
            if not isinstance(node, scopes):
                stack.extend(ast.iter_child_nodes(node))

    def bindings(body, inherited, args=()):
        found = {arg.arg: {None} for arg in args}
        for node in own_nodes(body):
            if isinstance(node, ast.Import):
                for item in node.names:
                    origin = item.name if item.asname else item.name.split('.')[0]
                    found.setdefault(item.asname or origin, set()).add(('module', origin))
            elif isinstance(node, ast.ImportFrom):
                for item in node.names:
                    origin = ('dynamic', 'importlib.import_module') if node.module == 'importlib' and not node.level and item.name == 'import_module' else ('namespace', 'builtins.' + item.name) if node.module == 'builtins' and item.name in {'exec', 'eval', 'globals', 'locals', 'vars', 'setattr', 'delattr'} else None
                    found.setdefault(item.asname or item.name, set()).add(origin)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found.setdefault(node.name, set()).add(None)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                found.setdefault(node.name, set()).add(None)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                found.setdefault(node.id, set()).add(None)
        result = dict(inherited)
        result.update((name, next(iter(origins)) if len(origins) == 1 else None) for name, origins in found.items())
        return result

    # A source-closed scalar export table is finite; this is not a claim about
    # arbitrary external monkeypatching. Rebinding, mutation and escaping the
    # table in this source prevent this proof. Keep this in the import reader.
    tables = {}
    for statement in tree.body:
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
        value = statement.value if targets else None
        if (len(targets) == 1 and isinstance(targets[0], ast.Name) and isinstance(value, ast.Dict)
                and value.keys and all(isinstance(key, ast.Constant) and isinstance(key.value, str)
                                      and isinstance(item, ast.Constant) and isinstance(item.value, str)
                                      and item.value and all(part.isidentifier() for part in item.value.split('.'))
                                      for key, item in zip(value.keys, value.values))):
            tables[targets[0].id] = (targets[0], {key.value for key in value.keys},
                                    tuple(sorted({item.value for item in value.values})))
    if tables and not any(name == 'importlib' or name.startswith('importlib:') for name in info.imports) and not any(
            isinstance(node, ast.Name) and node.id == '__import__' for node in ast.walk(tree)):
        tables.clear()
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)} if tables else {}
    namespace_aliases, builtins_aliases = set(), set()
    if tables:
        for node in (item for item in ast.walk(tree) if isinstance(item, (ast.Import, ast.ImportFrom))):
            for alias, origin in bindings([node], {}).items():
                if origin and origin[0] == 'namespace':
                    namespace_aliases.add(alias)
                elif origin == ('module', 'builtins'):
                    builtins_aliases.add(alias)
    protected = set(bindings(tree.body, {})) | {'globals', 'getattr', '__import__'} if tables else set()

    def lookup(statement, guard):
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
        value = statement.value if targets else None
        if not (len(targets) == 1 and isinstance(targets[0], ast.Name) and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute) and value.func.attr == 'get'
                and isinstance(value.func.value, ast.Name) and value.func.value.id in tables
                and len(value.args) in (1, 2) and not value.keywords and isinstance(value.args[0], ast.Name)
                and (len(value.args) == 1 or isinstance(value.args[1], ast.Constant) and value.args[1].value is None)):
            return None
        name = targets[0].id
        if not (isinstance(guard, ast.If) and not guard.orelse and len(guard.body) == 1
                and isinstance(guard.body[0], ast.Raise) and isinstance(guard.test, ast.Compare)
                and isinstance(guard.test.left, ast.Name) and guard.test.left.id == name
                and len(guard.test.ops) == 1 and isinstance(guard.test.ops[0], ast.Is)
                and isinstance(guard.test.comparators[0], ast.Constant) and guard.test.comparators[0].value is None):
            return None
        return name, value.func.value.id, value.args[0].id, guard.end_lineno

    def rebound(name):
        return any(isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))
                   or isinstance(node, ast.arg) and node.arg == name
                   or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
                   or isinstance(node, (ast.Import, ast.ImportFrom)) and any((alias.asname or alias.name.split('.')[0]) == name for alias in node.names)
                   for node in ast.walk(tree))

    def export_cache(call, table):
        # The real facade caches only successfully looked-up export keys. It
        # cannot replace the table/importer or another existing module binding.
        if rebound('globals'):
            return False
        target = parents.get(call)
        if (isinstance(target, ast.Call) and isinstance(target.func, ast.Name) and target.func.id == 'set'
                and target.args == [call] and not target.keywords
                and not rebound('set')):
            return True  # __dir__ enumerates namespace keys, never exposing the table.
        if not (isinstance(target, ast.Subscript) and isinstance(target.ctx, ast.Store)
                and isinstance(target.slice, ast.Name) and tables[table][1].isdisjoint(protected)):
            return False
        owner = target
        while owner in parents and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parents[owner]
        if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        key = target.slice.id
        if any(isinstance(node, ast.Name) and node.id == key and isinstance(node.ctx, (ast.Store, ast.Del))
               for node in own_nodes(owner.body)):
            return False
        return any(item and item[1:3] == (table, key) and item[3] < call.lineno
                   for item in (lookup(a, b) for a, b in zip(owner.body, owner.body[1:])))

    @lru_cache(maxsize=None)
    def closed_table(name):
        declaration = tables[name][0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in {'exec', 'eval', 'globals', 'locals', 'vars', 'setattr', 'delattr'}:
                parent = parents.get(node)
                if not isinstance(parent, ast.Call) or parent.func is not node:
                    return False
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in namespace_aliases
                    or isinstance(node, ast.Attribute) and node.attr in {'exec', 'eval', 'globals', 'locals', 'vars', 'setattr', 'delattr'}
                    and isinstance(node.value, ast.Name) and node.value.id in builtins_aliases
                    or isinstance(node, ast.Attribute) and node.attr == name):
                return False
            if isinstance(node, ast.Name) and node.id == name and node is not declaration:
                parent = parents.get(node)
                call = parents.get(parent)
                if not (isinstance(node.ctx, ast.Load) and isinstance(parent, ast.Attribute)
                        and parent.attr == 'get' and isinstance(call, ast.Call) and call.func is parent):
                    return False
            if (isinstance(node, ast.arg) and node.arg == name
                    or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
                    or isinstance(node, (ast.Import, ast.ImportFrom)) and any((alias.asname or alias.name.split('.')[0]) == name or alias.name == name for alias in node.names)):
                return False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {'eval', 'exec', 'locals', 'vars'}:
                    return False
                if node.func.id == 'globals' and not export_cache(node, name):
                    return False
                if node.func.id == 'getattr' and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value == name:
                    return False
                if node.func.id in {'setattr', 'delattr'} and (len(node.args) < 2 or not isinstance(node.args[1], ast.Constant) or node.args[1].value == name):
                    return False
        return True

    def add(mapping, key, line):
        lines = mapping.setdefault(key, [])
        if line not in lines:
            lines.append(line)

    class Reader(ast.NodeVisitor):
        def __init__(self):
            self.env = {'__import__': ('dynamic', '__import__'),
                        'getattr': ('reflect', 'getattr'), 'hasattr': ('reflect', 'hasattr')}
            self.class_parent = None

        def visit_If(self, node):
            if is_type_checking_guard(node):
                for item in node.orelse:
                    self.visit(item)
            else:
                self.generic_visit(node)

        def scope(self, body, args=(), *, parent=None, is_class=False, local_result=False):
            previous, old_class_parent = self.env, self.class_parent
            inherited = previous if parent is None else parent
            self.env = bindings(body, inherited, args)
            if tables:
                if body is tree.body:
                    self.env.update((name, ('literal-map', values)) for name, (_target, _keys, values) in tables.items() if closed_table(name))
                stores = {}
                for statement in body:
                    for node in ast.walk(statement):
                        names = [node.id] if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) else []
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            names += [alias.asname or alias.name.split('.')[0] for alias in node.names]
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            names.append(node.name)
                        elif isinstance(node, ast.ExceptHandler) and node.name:
                            names.append(node.name)
                        for name in names:
                            stores[name] = stores.get(name, 0) + 1
                for first, second in zip(body, body[1:]):
                    item = lookup(first, second)
                    if item:
                        name, table, _key, after = item
                        origin = self.env.get(table)
                        if (local_result and stores.get(name) == 1 and name not in {arg.arg for arg in args}
                                and not any(isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names for node in own_nodes(body))
                                and origin and origin[0] == 'literal-map'):
                            self.env[name] = ('finite-modules', origin[1], after)
            self.class_parent = inherited if is_class else None
            try:
                for item in body:
                    self.visit(item)
            finally:
                self.env, self.class_parent = previous, old_class_parent

        def visit_Module(self, node):
            self.scope(node.body)

        def visit_FunctionDef(self, node):
            for expression in [*node.decorator_list, *node.args.defaults, *filter(None, node.args.kw_defaults)]:
                self.visit(expression)
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            args += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
            self.scope(node.body, args, parent=self.class_parent, local_result=True)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            for expression in [*node.bases, *node.decorator_list, *(item.value for item in node.keywords)]:
                self.visit(expression)
            self.scope(node.body, is_class=True)

        def visit_Lambda(self, node):
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            args += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
            self.scope([node.body], args)

        def comprehension(self, node):
            previous = self.env
            self.env = dict(previous)
            for generator in node.generators:
                for target in ast.walk(generator.target):
                    if isinstance(target, ast.Name):
                        self.env[target.id] = None
            try:
                self.generic_visit(node)
            finally:
                self.env = previous

        visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = comprehension

        def module(self, node):
            if isinstance(node, ast.Name):
                origin = self.env.get(node.id)
                return origin[1] if origin and origin[0] == 'module' else None
            if isinstance(node, ast.Attribute) and (base := self.module(node.value)):
                return base + '.' + node.attr
            return None

        def visit_Attribute(self, node):
            if module := self.module(node.value):
                name = '*' if node.attr == '__all__' else node.attr
                key = module + ':' + name
                info.imports.add(key)
                add(info.import_reads, key, node.lineno)
            self.generic_visit(node)

        def visit_Call(self, node):
            origin = self.env.get(node.func.id) if isinstance(node.func, ast.Name) else None
            if origin and origin[0] == 'reflect' and node.args and (module := self.module(node.args[0])):
                name = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str) else '*'
                key = module + ':' + name
                info.imports.add(key)
                add(info.import_reads, key, node.lineno)
            importer = origin[1] if origin and origin[0] == 'dynamic' else None
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module' and self.module(node.func.value) == 'importlib':
                importer = 'importlib.import_module'
            if importer:
                argument = node.args[0] if node.args else next((item.value for item in node.keywords if item.arg == 'name'), None)
                name = argument.value if isinstance(argument, ast.Constant) and isinstance(argument.value, str) else None
                level = node.args[4] if importer == '__import__' and len(node.args) > 4 else next(
                    (item.value for item in node.keywords if item.arg == 'level'), None)
                absolute = importer != '__import__' or level is None or isinstance(level, ast.Constant) and level.value == 0
                finite = self.env.get(argument.id) if isinstance(argument, ast.Name) else None
                if name and not name.startswith('.') and absolute:
                    add(info.literal_dynamic_imports, name, node.lineno)
                elif absolute and finite and finite[0] == 'finite-modules' and node.lineno > finite[2]:
                    for candidate in finite[1]:
                        add(info.literal_dynamic_imports, candidate, node.lineno)
                else:
                    reason = ('module name is not an absolute string literal' if absolute
                              else 'relative import level needs an explicit package context')
                    info.unknown_dynamic_imports.append({'line': node.lineno, 'call': importer, 'reason': reason})
            self.generic_visit(node)

    Reader().visit(tree)
    for values in (info.import_reads, info.literal_dynamic_imports):
        for lines in values.values():
            lines.sort()
    info.unknown_dynamic_imports.sort(key=lambda item: (item['line'], item['call']))



def resolve_module(module: str, importer: str, mod_to_path: dict[str, str], py_paths,
                   import_roots=()) -> str | None:
    """Resolve package modules, then an actual script directory, then declared roots."""
    if not module:
        return None
    parts = module.split(".")
    while parts:
        target = mod_to_path.get(".".join(parts))
        if target:
            return target
        parts.pop()
    present = set(py_paths)
    directories = []
    if importer:
        directory = importer.rpartition("/")[0]
        init = f"{directory}/__init__.py" if directory else "__init__.py"
        if init not in present:
            directories.append(directory)
    directories.extend(import_roots)
    relative = module.replace(".", "/")
    for directory in dict.fromkeys(directories):
        prefix = directory.rstrip("/") + "/" if directory not in ("", ".") else ""
        for path in (prefix + relative + ".py", prefix + relative + "/__init__.py"):
            if path in present:
                return path
    return None
