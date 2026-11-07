"""Reuse only results whose code, helpers and original sources still have the same identities."""
from __future__ import annotations

import ast
import copy
from collections import Counter
import json
from importlib.metadata import distributions
from importlib.machinery import BuiltinImporter, FrozenImporter, PathFinder
import sysconfig
import locale
from pathlib import Path
import site
import sys
import fnmatch
import tomllib

from flowguard.map.common import content_digest, read_source
from flowguard.structure.paths import project_code
from .config import is_test_rel
from .sources import parse


# These modules were initialized by this engine before project loading. This is
# import provenance, not permission to treat their functions as pure.
_ENGINE_MODULES = frozenset(sys.modules)


def _digest(data):
    return content_digest(Path('summary'), data=data.encode())


def file_digest(path):
    return content_digest(path, source_only=True) if path.is_file() else 'gone'


class _Module(ast.NodeTransformer):
    def __init__(self, retained, *, calls_only=False):
        self.retained, self.calls_only, self.stack = retained, calls_only, []

    def visit(self, node):
        self.stack.append(node)
        try:
            return super().visit(node)
        finally:
            self.stack.pop()

    def generic_visit(self, node):
        # A read-only AST view: share unchanged children and copy only the
        # containers whose definition bodies are pruned. No shared source AST
        # is ever edited, and a discarded function body is never deep-copied.
        changes = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                result = [self.visit(child) if isinstance(child, ast.AST) else child for child in value]
                if any(a is not b for a, b in zip(value, result)):
                    changes[field] = result
            elif isinstance(value, ast.AST):
                result = self.visit(value)
                if result is not value:
                    changes[field] = result
        if not changes:
            return node
        result = copy.copy(node)
        for field, value in changes.items():
            setattr(result, field, value)
        return result

    def visit_FunctionDef(self, node):
        if node.name not in self.retained:
            result = copy.copy(node)
            result.body = [ast.Pass()]
            return self.generic_visit(result) if self.calls_only else result
        return node
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        if not self.calls_only:
            return node
        executes = False
        for parent in reversed(self.stack[:-1]):
            if isinstance(parent, ast.Call):
                executes = True
                break
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                executes = node in parent.decorator_list
                break
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
                executes = any(isinstance(target, ast.Attribute) for target in targets)
                break
            if isinstance(parent, (ast.Lambda, ast.Return)):
                break
        if not executes:
            result = copy.copy(node)
            result.body = ast.Constant(None)
            return self.generic_visit(result)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        return node if node.name in self.retained else self.generic_visit(node)


def _module_tree(path):
    tree = ast.parse(read_source(path))
    definitions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    retained = {n.id for statement in tree.body if statement not in definitions.values()
                for n in ast.walk(statement) if isinstance(n, ast.Name)}
    while True:
        before = set(retained)
        retained.update(n.id for name in before & definitions.keys() for n in ast.walk(definitions[name]) if isinstance(n, ast.Name))
        if retained == before:
            return _Module(retained).visit(tree)


def module_digest(path):
    if not path.is_file():
        return 'gone'
    try:
        tree = _module_tree(path)
    except SyntaxError:
        return file_digest(path)
    return _digest(ast.dump(tree, include_attributes=False))


def module_paths(cfg, module, roots=()):
    parts = module.split('.')
    return sorted({cfg.rel(path) for root in dict.fromkeys([cfg.root, *cfg.roots, *roots]) for n in range(1, len(parts) + 1)
                   for stem in [root.joinpath(*parts[:n])] for path in (stem.with_suffix('.py'), stem / '__init__.py')
                   if path.resolve().is_relative_to(cfg.root)})


def _imports(path, cfg, tree=None):
    """Resolve local imports from paths, without importing a helper or a package initializer."""
    try:
        tree = tree if tree is not None else ast.parse(read_source(path))
    except (OSError, SyntaxError):
        return [], []
    base = next((r for r in sorted([cfg.root, *cfg.roots], key=lambda p: len(str(p)), reverse=True) if path.is_relative_to(r)), cfg.root)
    module = list(path.relative_to(base).with_suffix('').parts)
    package = module[:-1]
    modules, data = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = package[:len(package) - node.level + 1] if node.level else []
            name = '.'.join([*prefix, *(node.module or '').split('.')]).strip('.')
            modules.append(name)
            modules.extend(name + '.' + a.name for a in node.names if a.name != '*')
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and Path(node.value).suffix in {'.json', '.yaml', '.yml', '.csv', '.toml', '.txt', '.md'}:
            for candidate in (cfg.root / node.value, path.parent / node.value):
                if candidate.resolve().is_relative_to(cfg.root) and candidate.is_file():
                    data.append(cfg.rel(candidate))
    return modules, data


def _aliases(tree, path, cfg):
    """Lexical import bindings; test files intentionally have no runtime map facts."""
    base = next((r for r in sorted([cfg.root, *cfg.roots], key=lambda p: len(str(p)), reverse=True) if path.is_relative_to(r)), cfg.root)
    package = list(path.relative_to(base).with_suffix('').parts)[:-1]
    result = {}
    class Visit(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            pass
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, node):
            pass
        def visit_Import(self, node):
            for alias in node.names:
                result[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        def visit_ImportFrom(self, node):
            prefix = package[:len(package) - node.level + 1] if node.level else []
            module = '.'.join([*prefix, *(node.module or '').split('.')]).strip('.')
            for alias in node.names:
                if alias.name != '*':
                    result[alias.asname or alias.name] = module + ':' + alias.name
    Visit().visit(tree)
    return result


def _pytest_options(cfg):
    path = cfg.root / 'pyproject.toml'
    return tomllib.loads(path.read_text(encoding='utf-8-sig')).get('tool', {}).get('pytest', {}).get('ini_options', {}) if path.is_file() else {}


def _patterns(options, name, default):
    value = options.get(name, default)
    return value.split() if isinstance(value, str) else value


def test_scope(cfg):
    """The default pytest search scope, shared by selection and cached diagnostics."""
    options = _pytest_options(cfg)
    paths = []
    for value in _patterns(options, 'testpaths', ['.']):
        path = Path(value)
        if path.is_absolute() or not any(char in value for char in '*?['):
            path = path if path.is_absolute() else cfg.root / path
            paths.extend([path.resolve()] if path.exists() else [])
        else:
            paths.extend(p.resolve() for p in cfg.root.glob(value))
    # pytest falls back to the invocation directory when configured paths match nothing.
    paths = paths or [cfg.root]
    patterns = _patterns(options, 'python_files', ['test_*.py', '*_test.py'])
    def contains(relative):
        path = (cfg.root / relative).resolve()
        return (path.is_relative_to(cfg.root) and path.is_file()
                and any(path == base or path.is_relative_to(base) for base in paths)
                and path.suffix == '.py' and any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns))
    return contains


def test_files(cfg, graph):
    """Potential Python test files inside pytest's default scope; never import them."""
    options, contains = _pytest_options(cfg), test_scope(cfg)
    functions = _patterns(options, 'python_functions', ['test'])
    classes = _patterns(options, 'python_classes', ['Test'])
    def matches(name, patterns):
        return any(name.startswith(pattern) or fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
    def disabled(body):
        return any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__test__' for t in n.targets)
                   and isinstance(n.value, ast.Constant) and n.value.value is False for n in body)
    result = set()
    for file, error in graph.con.execute('SELECT path,parse_error FROM file'):
        path = cfg.root / file
        if not contains(file) or path.suffix != '.py' or path.is_relative_to(cfg.intent) or file == 'tests/test_flowguard_intent.py':
            continue
        if error:
            result.add(file)
            continue
        try:
            body = ast.parse(read_source(path)).body
        except (OSError, SyntaxError):
            result.add(file)
            continue
        if disabled(body):
            continue
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(node.name, functions):
                result.add(file)
            elif isinstance(node, ast.ClassDef) and not disabled(node.body) and (matches(node.name, classes) or node.bases):
                if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(n.name, functions) for n in node.body):
                    result.add(file)
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and options.get('collect_imported_tests', True):
                if any(a.name == '*' or matches(a.asname or a.name.split('.')[-1], [*functions, *classes]) for a in node.names):
                    result.add(file)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and matches(t.id, [*functions, *classes]) for t in targets):
                    result.add(file)
    return result


def _map_imports(graph, nodes=None):
    files = {node['id']: node['file'] for node in (graph.nodes() if nodes is None else nodes)}
    targets, unknown = {}, set()
    for edge in graph.imports():
        if edge['prov'] == 'unknown':
            unknown.add(edge['file'])
        if edge['dst'] in files:
            if files[edge['dst']]:
                targets.setdefault(edge['file'], set()).add(files[edge['dst']])
            else:
                unknown.add(edge['file'])
    return targets, unknown


def _path(node, file, bindings=None, aliases=None, seen=()):
    bindings, aliases = bindings or {}, aliases or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value)
    if isinstance(node, ast.Name) and node.id == '__file__':
        return file
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        return _path(bindings[node.id], file, bindings, aliases, (*seen, node.id))
    if isinstance(node, ast.Attribute) and node.attr == 'parent':
        value = _path(node.value, file, bindings, aliases, seen)
        return value.parent if value is not None else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents' and isinstance(node.slice, ast.Constant) and type(node.slice.value) is int:
        value = _path(node.value.value, file, bindings, aliases, seen)
        try:
            return value.parents[node.slice.value] if value is not None else None
        except IndexError:
            return None
    if isinstance(node, ast.Call):
        name = _name(node.func, aliases)
        if name in {'Path', 'pathlib.Path', 'pathlib.PosixPath', 'pathlib.WindowsPath'} and len(node.args) == 1:
            return _path(node.args[0], file, bindings, aliases, seen)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {'resolve', 'absolute'} and not node.args:
            value = _path(node.func.value, file, bindings, aliases, seen)
            return value.resolve() if value is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = _path(node.left, file, bindings, aliases, seen), _path(node.right, file, bindings, aliases, seen)
        return left / right if left is not None and right is not None else None
    return None


def _name(node, aliases=None):
    if isinstance(node, ast.Name):
        return (aliases or {}).get(node.id, node.id).replace(':', '.')
    if isinstance(node, ast.Attribute):
        base = _name(node.value, aliases)
        return base + '.' + node.attr if base else ''
    return ''


def _bindings(tree):
    result = {}
    class Visit(ast.NodeVisitor):
        def bind(self, target, value=None):
            if isinstance(target, ast.Name):
                old = result.get(target.id)
                result[target.id] = value if target.id not in result or old is not None and value is not None and ast.dump(old) == ast.dump(value) else None
            elif isinstance(target, (ast.Tuple, ast.List)):
                for child in target.elts:
                    self.bind(child)
        def visit_FunctionDef(self, node):
            pass
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, node):
            pass
        def visit_Assign(self, node):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                self.bind(target, node.value)
            self.generic_visit(node)
        visit_AnnAssign = visit_Assign
        def visit_AugAssign(self, node):
            self.bind(node.target)
            self.generic_visit(node)
        def visit_For(self, node):
            self.bind(node.target)
            self.generic_visit(node)
        visit_AsyncFor = visit_For
        def visit_With(self, node):
            for item in node.items:
                if item.optional_vars:
                    self.bind(item.optional_vars)
            self.generic_visit(node)
        visit_AsyncWith = visit_With
        def visit_NamedExpr(self, node):
            self.bind(node.target, node.value)
            self.generic_visit(node)
    Visit().visit(tree)
    return result


def _read_path(call, file, bindings=None, aliases=None):
    """One owner for builtin/io.open, Path.open and Path.read_* argument positions."""
    name = _name(call.func, aliases)
    short = call.func.attr if isinstance(call.func, ast.Attribute) else name.rsplit('.', 1)[-1]
    if short in {'read_text', 'read_bytes'} and isinstance(call.func, ast.Attribute):
        return True, _path(call.func.value, file, bindings, aliases)
    if short != 'open':
        return False, None
    builtin = name in {'open', 'builtins.open', 'io.open'}
    expression = call.args[0] if builtin and call.args else call.func.value if isinstance(call.func, ast.Attribute) else None
    offset = 1 if builtin else 0
    mode = next((k.value for k in call.keywords if k.arg == 'mode'), call.args[offset] if len(call.args) > offset else ast.Constant('r'))
    if not isinstance(mode, ast.Constant) or not isinstance(mode.value, str):
        return True, None
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(x in mode.value for x in 'wax') and '+' not in mode.value:
        return False, None
    return True, _path(expression, file, bindings, aliases)


def _data_reads(cfg, node):
    """Literal file dependencies only; dynamic reads explicitly prevent reuse."""
    path = cfg.root / node['file']
    tree = _module_tree(path) if node['kind'] == 'module' else ast.parse(read_source(path))
    if node['kind'] == 'const':
        tree = ast.parse(node['sig'], mode='eval')
    for name in node['qual'].split('.') if node['qual'] and node['kind'] != 'const' else []:
        tree = next((child for child in tree.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name), tree)
    if node['kind'] == 'class':
        tree = _Module(set()).visit(tree)
    dependencies, reasons = [], []
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        reading, value = _read_path(call, path)
        if not reading:
            continue
        value = (cfg.root / value).resolve() if value is not None else None
        if value is None or not value.is_relative_to(cfg.root):
            reasons.append(f'dynamic or external data read at {node["file"]}:{call.lineno} -> declare a literal input before reusing this result')
        else:
            dependencies.append(cfg.rel(value))
    return dependencies, reasons


class Now:
    def __init__(self, cfg, graph):
        self.cfg, self.graph, self.memo = cfg, graph, {}
        self.trace_groups = {}

    def __call__(self, key):
        if key not in self.memo:
            kind, _, value = key.partition(':')
            if kind == 'node':
                node = self.graph.node(value)
                digest = node['fp'] if node else 'gone'
            elif kind == 'anchor':
                from dataclasses import asdict
                from .anchors import collect
                if not hasattr(self, 'anchor_index'):
                    self.anchor_index = collect(self.graph)
                anchors = []
                for anchor in self.anchor_index.entries:
                    if value not in (anchor.name, anchor.target):
                        continue
                    data = asdict(anchor)
                    for field in ('line', 'target_line', 'source_digest'):
                        data.pop(field, None)
                    data['issues'] = [dict(level=issue.level,code=issue.code,message=issue.message,name=issue.name)
                                      for issue in anchor.issues]
                    anchors.append(data)
                digest = _digest(json.dumps(anchors,sort_keys=True,default=repr))
            elif kind == 'module':
                digest = module_digest(self.cfg.root / value)
            elif kind == 'authority':
                from .sources import Archive
                if not hasattr(self, 'archive'):
                    self.archive = Archive(self.cfg.root)
                digest = _digest(repr(self.archive.status(value)))
            elif kind == 'engine':
                base = Path(__file__).resolve().parents[1]
                files = sorted(base.rglob('*.py'))
                locations = list(site.getsitepackages())
                if site.ENABLE_USER_SITE:
                    user = site.getusersitepackages()
                    locations.extend([user] if isinstance(user, str) else user)
                # Build tools may add their private vendor directories to sys.path.
                # They do not change the interpreter's installed package identities.
                packages = sorted({(d.metadata.get('Name', ''), d.version)
                                   for d in distributions(path=list(dict.fromkeys(locations)))})
                context = (str(self.cfg.root), sys.version, repr(sys.flags), locale.getencoding(),
                           sys.get_int_max_str_digits() if hasattr(sys, 'get_int_max_str_digits') else None)
                digest = _digest('\n'.join(str(p.relative_to(base)) + ':' + file_digest(p) for p in files) + repr(context) + repr(packages))
            elif kind == 'listing':
                digest = _digest('\n'.join(r[0] for r in self.graph.con.execute('SELECT path FROM file ORDER BY path')))
            else:
                digest = file_digest(self.cfg.root / value)
            self.memo[key] = digest
        return self.memo[key]

    def trace_changes(self, identifier):
        if identifier not in self.trace_groups:
            con = self.graph.con
            owned = not con.in_transaction
            if owned:
                con.execute('BEGIN')
            try:
                row = con.execute('SELECT refs FROM trace_group WHERE id=?', (identifier,)).fetchone()
                if row is None:
                    changes = ['recorded dependency group is missing']
                else:
                    refs, values = json.loads(row[0]), {}
                    for offset in range(0, len(refs), 900):
                        part = refs[offset:offset + 900]
                        values.update((identifier, (key, digest)) for identifier, key, digest in con.execute(
                            'SELECT id,key,digest FROM trace_value WHERE id IN (' + ','.join('?' for _ in part) + ')', part))
                    changes = (['recorded dependency values are missing'] if len(values) != len(set(refs)) else
                               [key for ref in refs for key, value in [values[ref]] if self(key) != value])
            finally:
                if owned:
                    con.rollback()  # End only this read snapshot; never commit another owner's work.
            self.trace_groups[identifier] = changes
        return self.trace_groups[identifier]


def record(cfg, model, rule, results, graph):
    """Return dependency keys and explicit incompleteness; never refresh a rule that did not run."""
    now, keys, reasons = Now(cfg, graph), {'engine:'}, []
    roots = [cfg.root / root['path'] for root in graph.roots()]
    files, nodes = {model.file_of[rule.id]}, set()
    declarations = [rule]
    if getattr(rule, 'nodes', ()):
        from .flow import _registered_flow, Unverified
        pending, registered = [(rule, (rule.id,))], {rule.id}
        while pending:
            declaration, ancestry = pending.pop()
            references = [node.model for node in getattr(declaration, 'nodes', ()) if node.model is not None]
            references.extend(relation.rule for relation in getattr(declaration, 'relations', ())
                              if hasattr(relation, 'rule'))
            references.extend(getattr(declaration, 'uses', ()))
            for reference in references:
                try:
                    child = _registered_flow(reference, model.flows)
                except Unverified as error:
                    reasons.append(str(error)); continue
                identifier = getattr(reference, 'id', reference)
                if child is None:
                    child = model.rules.get(identifier) if isinstance(identifier, str) else None
                if child is None:
                    reasons.append(f'unresolved lower declaration {identifier!r}'); continue
                if child.id in ancestry:
                    reasons.append('lower declaration cycle: ' + ' -> '.join((*ancestry, child.id))); continue
                if child.id not in registered:
                    registered.add(child.id)
                    declarations.append(child)
                    pending.append((child, (*ancestry, child.id)))
    for declaration in declarations:
        declaration_file = model.file_of.get(declaration.id)
        if declaration_file:
            files.add(declaration_file)
        else:
            reasons.append(f'unregistered lower declaration {declaration.id}')
    for home in (home for declaration in declarations for home in getattr(declaration, 'homes', [])):
        node = graph.canonical(home.target)
        if node:
            nodes.add(node)
        else:
            keys.update('file:' + p for p in module_paths(cfg, home.target.partition(':')[0], roots))
            keys.add('listing:')
        files.update(p for p in module_paths(cfg, home.target.partition(':')[0], roots) if (cfg.root / p).is_file())
        if hasattr(home, 'anchor'):
            if home.anchor:
                files.add(home.anchor.file)
                keys.add('anchor:' + home.anchor.target)  # Source role/type/unit/calibration contract, without unrelated bodies.
                keys.add('anchor:' + home.anchor.name)  # New same-name sites change this binding, unrelated files do not.
            else:
                keys.add('listing:')
        if hasattr(home, 'scenario'):
            files.update((home.scenario.file, home.flow.file))
        for anchor in getattr(home, 'measurement_anchors', (home.anchor,) if home.anchor else ()):
            files.add(anchor.file)
            keys.add('anchor:' + anchor.target)
            keys.add('anchor:' + anchor.name)
            if anchor.calibrated_by:
                files.add(anchor.calibrated_by.partition('::')[0])
    for node in (node for declaration in declarations for node in getattr(declaration, 'nodes', ())):
        for anchor in model.anchor_index.named(node.reference):
            nodes.add(graph.canonical(anchor.target) or anchor.target)
            files.add(anchor.file)
            keys.add('anchor:' + anchor.target)
        keys.add('listing:')
    if getattr(rule, 'binding_kind', '') == 'anchor':
        keys.add('listing:')
        for anchor in model.anchor_index.entries:
            if any(value in (anchor.name, anchor.target) for value in (rule.a, rule.b)):
                nodes.add(graph.canonical(anchor.target) or anchor.target)
                keys.add('anchor:' + anchor.target)
    entries = list(results.values()) if isinstance(results, dict) else list(results)
    for result in entries:
        nodes.update(result.get('footprint', []))
        for relative in result.get('files', []):
            if is_test_rel(relative):
                files.add(relative)
    seen = set()
    while nodes:
        identifier = nodes.pop()
        identifier = graph.canonical(identifier.replace('.<locals>.', '.')) or identifier
        if identifier in seen:
            continue
        seen.add(identifier)
        node = graph.node(identifier)
        if not node:
            reasons.append('unmapped footprint ' + identifier)
            continue
        keys.add('node:' + identifier)
        keys.add('module:' + node['file'])
        data, unread = _data_reads(cfg, node)
        files.update(data)
        reasons.extend(unread)
        for edge in graph.edges(identifier):
            if edge['kind'] in {'reads', 'calls'} and edge['prov'] != 'guessed':
                nodes.add(edge['dst'])
    for declaration in declarations:
        source = parse(declaration.source)
        if source.kind == 'doc':
            files.add(source.path)
        for rid in source.rids + ((declaration.confirmed,) if getattr(declaration, 'confirmed', None) else ()):
            files.update('.flowguard/requests/' + rid + suffix for suffix in ('.md', '.json'))
            keys.add('authority:' + rid)
    # A changed allowlist changes which original document counts as authority.
    files.add('pyproject.toml')
    production = {graph.node(identifier)['file'] for identifier in seen if graph.node(identifier)}
    imported_files, unknown_imports = _map_imports(graph)
    pending, visited = list(files), set()
    while pending:
        relative = pending.pop()
        key = 'file:' + relative
        if relative in visited:
            continue
        visited.add(relative)
        keys.add(('module:' if relative in production and not is_test_rel(relative) else 'file:') + relative)
        path = cfg.root / relative
        if path.suffix != '.py' or not path.is_file():
            continue
        pending.extend(imported_files.get(relative, ()))
        if relative in unknown_imports:
            reasons.append('unresolved import in ' + relative)
        modules, data = _imports(path, cfg)
        pending.extend(data)
        for module in modules:
            candidates = module_paths(cfg, module, roots)
            keys.update('file:' + p for p in candidates if not (cfg.root / p).is_file())
            existing = [p for p in candidates if (cfg.root / p).is_file()]
            for imported in existing:
                pending.append(imported)
    if getattr(rule, 'target', None) or getattr(rule, 'pred', None) and not hasattr(rule, 'decides'):
        keys.add('listing:')
    child_homes = {graph.canonical(h.target) for child in getattr(rule, 'uses', []) if child in model.rules for h in model.rules[child].homes}
    own, frontier = set(), [graph.canonical(h.target) for h in getattr(rule, 'homes', [])]
    while frontier:
        identifier = frontier.pop()
        if identifier is None or identifier in own:
            continue
        own.add(identifier)
        frontier.extend(edge['dst'] for edge in graph.edges(identifier) if edge['kind'] in {'calls', 'reads'}
                        and edge['prov'] != 'guessed' and edge['dst'] not in child_homes)
    contracts = {child: summary for result in entries for child, summary in result.get('contracts', {}).items()}
    return dict(dependencies={key: now(key) for key in sorted(keys)}, reasons=sorted(set(reasons)),
                own_nodes=sorted(own), contracts=contracts)


def stale(saved, now):
    if not saved or saved.get('reasons'):
        return ['no complete reusable result']
    return [key for key, digest in saved['dependencies'].items() if now(key) != digest]


def affected(data, model, now):
    chosen = {rid for rid in model.rules if rid not in data.get('results', {}) or stale(data.get('deps', {}).get(rid), now)}
    while True:
        before = set(chosen)
        keys = {model.rules[r].decides for r in chosen}
        chosen.update(r.id for r in model.rules.values() if r.decides in keys or set(r.uses) & chosen)
        if chosen == before:
            return sorted(chosen)


def contract_cut(data, model, now, fresh_contracts, selected=None):
    """A verified unchanged lower contract may stop only its own internal node changes."""
    selected = set(affected(data, model, now) if selected is None else selected)
    for rid in sorted(selected):
        saved = data.get('deps', {}).get(rid, {})
        changes = stale(saved, now)
        if not changes or any(not key.startswith('node:') for key in changes):
            continue
        if any(key[5:] in saved.get('own_nodes', []) for key in changes):
            continue
        covered = set()
        for child in model.rules[rid].uses:
            new = fresh_contracts.get(child, {})
            old = saved.get('contracts', {}).get(child, {})
            if (new.get('verdict') != 'ok' or old.get('verdict') != 'ok'
                    or not new.get('complete') or not old.get('complete') or new.get('outcomes') != old.get('outcomes')):
                continue
            covered.update(key for key in data.get('deps', {}).get(child, {}).get('dependencies', {}) if key.startswith('node:'))
        if set(changes) <= covered:
            selected.remove(rid)
    return sorted(selected)


class _TestDependencies:
    """One-call static closure. Imports execute definitions, not every function body.

    Function bodies enter through actual source references and the map's call/read
    edges. No past trace is used to exclude a possible dependency.
    """
    def __init__(self, cfg, graph, now):
        from flowguard.structure.store import unpack
        self.cfg, self.graph, self.now = cfg, graph, now
        self.roots = [cfg.root / r['path'] for r in graph.roots()]
        self.nodes = {n['id']: n for n in graph.nodes()}
        self.files = {p: (m, data) for p, m, data in graph.con.execute('SELECT path,module,data FROM file')}
        self.unpack = unpack
        self.parsed, self.summaries, self.path_cache, self.exists_cache, self.symbols = {}, {}, {}, {}, {}
        self.initials = {}
        self.origins = {}
        stdlib = Path(sysconfig.get_path("stdlib")).resolve()
        self.stdlib = stdlib
        extras = _patterns(_pytest_options(cfg), "pythonpath", [])
        self.search_paths = list(dict.fromkeys(str(p) for p in [cfg.root, *cfg.roots,
                                 *(cfg.root / value for value in extras), *map(Path, sys.path)]))
        self.imports = {}
        for edge in graph.imports():
            self.imports.setdefault((edge['file'], edge['line']), []).append(edge)

    def exists(self, relative):
        if relative not in self.exists_cache:
            self.exists_cache[relative] = (self.cfg.root / relative).is_file()
        return self.exists_cache[relative]

    def paths(self, module):
        if module not in self.path_cache:
            self.path_cache[module] = tuple(module_paths(self.cfg, module, self.roots))
        return self.path_cache[module]

    def origin(self, module):
        """Locate an import without executing a project or third-party initializer."""
        if not module:
            return 'unknown', None
        if module not in self.origins:
            spec = None
            cached = sys.modules.get(module)
            if cached is not None and module in _ENGINE_MODULES:
                spec = getattr(cached, '__spec__', None)
            if spec is None:
                search = self.search_paths
                for index, part in enumerate(module.split('.')):
                    name = '.'.join(module.split('.')[:index + 1])
                    try:
                        spec = (BuiltinImporter.find_spec(name) or FrozenImporter.find_spec(name)
                                or PathFinder.find_spec(name, search))
                    except KeyError as error:
                        # PathFinder's namespace path expects its parent in
                        # sys.modules. Discovery must not initialize that parent
                        # just to establish provenance; leave this import opaque.
                        parent = name.rpartition('.')[0]
                        if error.args != (parent,) or parent in sys.modules:
                            raise
                        spec = None
                        break
                    if spec is None:
                        break
                    search = spec.submodule_search_locations
                    if index < len(module.split('.')) - 1 and search is None:
                        spec = None
                        break
            location = getattr(spec, 'origin', None)
            if location in {'built-in', 'frozen'}:
                kind = 'interpreter'
            elif location and location not in {'namespace'}:
                path = Path(location).resolve()
                if project_code(str(path), self.cfg.root):
                    kind = 'project'
                elif path.is_relative_to(Path(__file__).resolve().parents[1]):
                    kind = 'engine'
                elif path.is_relative_to(self.stdlib) and not {'site-packages', 'dist-packages'} & set(path.parts):
                    kind = 'stdlib'
                else:
                    kind = 'external'
            else:
                kind = 'unknown'
            self.origins[module] = kind, location
        return self.origins[module]

    def import_reason(self, module):
        kind, location = self.origin(module)
        if kind in {'project', 'engine'}:
            return ''
        if kind in {'stdlib', 'interpreter'} and module in _ENGINE_MODULES:
            return ''
        return 'unverified external import ' + module

    def modeled_path_call(self, node, file, bindings, aliases):
        """The existing Path/read model, bound to the actual stdlib implementation."""
        name = _name(node.func, aliases)
        if self.origin('pathlib')[0] != 'stdlib':
            return False
        if name in {'pathlib.Path', 'pathlib.PosixPath', 'pathlib.WindowsPath'}:
            return len(node.args) == 1 and _path(node, file, bindings, aliases) is not None
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {'resolve', 'absolute'}:
                return not node.args and _path(node, file, bindings, aliases) is not None
            reading, path = _read_path(node, file, bindings, aliases)
            if reading and path is not None:
                return True  # Input tracking (including outside-project refusal) follows below.
            if node.func.attr == 'read' and isinstance(node.func.value, ast.Call):
                reading, path = _read_path(node.func.value, file, bindings, aliases)
                return reading and path is not None
        return False

    def file(self, relative):
        if relative not in self.parsed:
            tree = ast.parse(read_source(self.cfg.root / relative))
            data = self.unpack(self.files[relative][1]) if relative in self.files else {}
            definitions = {}
            def collect(body, prefix=''):
                for node in body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        qual = prefix + node.name
                        definitions[qual] = node
                        collect(node.body, qual + '.')
            collect(tree.body)
            initial = _Module(set(), calls_only=True).visit(tree)
            self.initials[relative] = initial
            self.parsed[relative] = tree, data, definitions, _bindings(initial)
        return self.parsed[relative]

    def symbol(self, module, qual, seen=()):
        key = module, qual
        if key in seen:
            return None
        if key not in self.symbols:
            self.symbols[key] = self._symbol(module, qual, seen)
        return self.symbols[key]

    def _symbol(self, module, qual, seen=()):
        key = module, qual
        ident = self.graph.canonical(module + ':' + qual)
        if ident in self.nodes:
            node = self.nodes[ident]
            return (node['file'], node['qual']) if node['file'] else None
        stem = module.replace('.', '/')
        for relative in self.paths(module):
            if not self.exists(relative) or not (relative.endswith(stem + '.py') or relative.endswith(stem + '/__init__.py')):
                continue
            tree, data, definitions, _ = self.file(relative)
            if qual in definitions:
                return relative, qual
            first, dot, rest = qual.partition('.')
            if first in definitions and isinstance(definitions[first], ast.ClassDef):
                return relative, first
            bound = data.get('facts', {}).get('imports', {}).get(first)
            lazy = data.get('lazy', {}).get(first)
            if lazy:
                found = self.symbol(lazy, qual, (*seen, key))
                if found:
                    return found
            if bound:
                mod, _, name = bound.partition(':')
                found = self.symbol(mod, '.'.join(p for p in (name, rest) if p), (*seen, key))
                if found:
                    return found
        return None

    def summary(self, relative, qual):
        key = relative, qual
        if key in self.summaries:
            return self.summaries[key]
        dependencies, references, reasons = {relative}, set(), set()
        result = dependencies, references, reasons
        self.summaries[key] = result
        if not relative.endswith('.py') or not self.exists(relative):
            return result
        try:
            tree, data, definitions, globals_ = self.file(relative)
        except (OSError, SyntaxError) as error:
            reasons.add(f'{relative}: cannot read source ({type(error).__name__})')
            return result
        aliases = _aliases(tree, self.cfg.root / relative, self.cfg)
        aliases.update(data.get('facts', {}).get('imports', {}))
        for name in definitions:
            if '.' not in name:
                aliases[name] = self.files.get(relative, ('',))[0] + ':' + name
        for name in globals_:
            aliases[name] = '?'
        if qual == '*':
            active = self.initials[relative]
            patterns = _patterns(_pytest_options(self.cfg), 'python_functions', ['test'])
            for name, node in definitions.items():
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(node.name.startswith(p) or fnmatch.fnmatchcase(node.name, p) for p in patterns):
                    references.add((relative, name))
        elif not qual:
            active = self.initials[relative]
        elif qual in definitions:
            node = definitions[qual]
            if isinstance(node, ast.ClassDef):
                active = ast.Module(body=[_Module(set(), calls_only=True).visit(node)], type_ignores=[])
            else:
                active = _Module(set(), calls_only=True).visit(ast.Module(body=node.body, type_ignores=[]))
            function = data.get('facts', {}).get('functions', {}).get(qual, {})
            aliases.update(function.get('local_imports', function.get('imports', {})))
        else:
            return result  # Constants are covered by their whole source file and module initialization.
        bindings = dict(globals_)
        if qual not in {'', '*'}:
            aliases.update(_aliases(active, self.cfg.root / relative, self.cfg))
            for name in definitions:
                if name.rpartition('.')[0] == qual:
                    aliases[name.rsplit('.',1)[-1]] = self.files.get(relative, ('',))[0] + ':' + name
        parameters = set()
        if qual in definitions and isinstance(definitions[qual], (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*definitions[qual].args.posonlyargs, *definitions[qual].args.args, *definitions[qual].args.kwonlyargs]:
                bindings[arg.arg] = None
                parameters.add(arg.arg)
                aliases[arg.arg] = '?'
            if qual.rpartition('.')[0] in definitions:
                aliases['self'] = aliases['cls'] = self.files.get(relative, ('',))[0] + ':' + qual.rpartition('.')[0]
        local_bindings = _bindings(active)
        bindings.update(local_bindings)
        def alias_of(value):
            if isinstance(value, ast.Name):
                return aliases.get(value.id, '?')
            if isinstance(value, ast.Attribute):
                base = alias_of(value.value)
                return base + ('.' if ':' in base else ':') + value.attr if base != '?' else '?'
            if isinstance(value, ast.Call) and _name(value.func, aliases).rsplit('.',1)[-1] == 'import_module' and value.args and isinstance(value.args[0], ast.Constant) and isinstance(value.args[0].value, str):
                return value.args[0].value
            if isinstance(value, ast.Call) and _name(value.func, aliases) == 'getattr' and len(value.args) >= 2 and isinstance(value.args[1], ast.Constant) and isinstance(value.args[1].value, str):
                base = alias_of(value.args[0])
                return base + ('.' if ':' in base else ':') + value.args[1].value if base != '?' else '?'
            return '?'
        for name in local_bindings:
            aliases[name] = alias_of(local_bindings[name])
        for instance, constructor in data.get('facts', {}).get('instances', {}).items():
            scope, _, name = instance.partition('|')
            if scope == qual and aliases.get(name, '?') == '?':
                aliases[name] = aliases.get(constructor, constructor)
        parents = {child: parent for parent in ast.walk(active) for child in ast.iter_child_nodes(parent)}
        module = self.files.get(relative, ('',))[0]
        ident = module + (':' + qual if qual and qual != '*' else '')
        project_calls = set()
        for edge in self.graph.edges(ident):
            if edge['kind'] in {'calls', 'reads'} and edge['prov'] != 'guessed' and edge['dst'] in self.nodes:
                target = self.nodes[edge['dst']]
                if target['file']:
                    # A read keeps the definition's identity, not an assertion
                    # that its body ran. Actual/escaping calls are added below.
                    dependencies.add(target['file'])
                    references.add((target['file'], target['qual'] if edge['kind'] == 'calls' else ''))
                    if edge['kind'] == 'calls' and edge['prov'] == 'resolved':
                        project_calls.add((edge['line'], target['qual'].rsplit('.',1)[-1]))
        modules, resources = _imports(self.cfg.root / relative, self.cfg, active)
        for imported in modules:
            dependencies.update(self.paths(imported))
        dependencies.update(resources)
        for path in list(dependencies):
            if path != relative and path.endswith('.py') and self.exists(path):
                references.add((path, ''))

        def construct(found):
            if not found:
                return
            file, name = found
            _, _, defs, _ = self.file(file)
            if name in defs and isinstance(defs[name], ast.ClassDef):
                for member in defs[name].body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                            member.name.startswith('__') or any(_name(d.func if isinstance(d, ast.Call) else d).rsplit('.',1)[-1] not in {'classmethod','staticmethod'} for d in member.decorator_list)):
                        references.add((file, name + '.' + member.name))

        def reference(name, called=False):
            first, _, rest = name.partition('.')
            # Local source references, including a callback handed to another function.
            local = next((q for q in [qual + '.' + name, qual.rpartition('.')[0] + '.' + name, name] if q.strip('.') in definitions), None)
            if local:
                found = relative, local.strip('.')
                dependencies.add(found[0])
                if called:
                    references.add(found)
                    construct(found)
            bound = aliases.get(first)
            if bound and bound != '?':
                mod, _, attr = bound.partition(':')
                wanted = '.'.join(p for p in (attr, rest) if p)
                stem = mod.replace('.', '/')
                for file in self.paths(mod):
                    if (self.exists(file) and
                            (file.endswith(stem + '.py') or file.endswith(stem + '/__init__.py'))):
                        _, metadata, defs, _ = self.file(file)
                        if '__getattr__' in defs and wanted.partition('.')[0] not in metadata.get('bound', []):
                            references.add((file, '__getattr__'))
                found = self.symbol(mod, wanted)
                if found:
                    dependencies.add(found[0])
                    references.add((found[0], found[1] if called else ''))
                    if called:
                        construct(found)

        def executes(node):
            parent = parents.get(node)
            if isinstance(parent, ast.Call) and parent.func is node:
                return True
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node in parent.decorator_list or isinstance(parent, ast.ClassDef) and node in parent.bases:
                    return True
            # A callable escaping to a call may be invoked. Merely putting it in
            # an assigned literal mapping/list does not execute it.
            while parent is not None and not isinstance(parent, (ast.Assign, ast.AnnAssign, ast.Return, ast.Expr)):
                if isinstance(parent, ast.Call):
                    return True
                parent = parents.get(parent)
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
                return any(isinstance(target, ast.Attribute) for target in targets)
            return False

        def imported_receiver(value, seen=()):
            if isinstance(value, ast.Name):
                bound = aliases.get(value.id)
                if bound and bound != '?':
                    return bound.partition(':')[0]
                if value.id in bindings and value.id not in seen:
                    return imported_receiver(bindings[value.id], (*seen, value.id))
            if isinstance(value, (ast.Attribute, ast.Call)):
                return imported_receiver(value.value if isinstance(value, ast.Attribute) else value.func, seen)
            if isinstance(value, ast.BinOp) and _path(value, self.cfg.root / relative, bindings, aliases) is not None:
                return 'pathlib'
            return None

        def known_value(value, seen=()):
            if isinstance(value, (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set)):
                return True
            if isinstance(value, ast.Name) and value.id in bindings and value.id not in seen:
                return known_value(bindings[value.id], (*seen, value.id))
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
                reading, path = _read_path(value, self.cfg.root / relative, bindings, aliases)
                if reading and path is not None:
                    return True
                if value.func.attr == 'read' and isinstance(value.func.value, ast.Call):
                    reading, path = _read_path(value.func.value, self.cfg.root / relative, bindings, aliases)
                    return reading and path is not None
            return False

        call_counts = Counter((n.lineno, n.func.attr if isinstance(n.func, ast.Attribute) else _name(n.func, aliases).rsplit('.',1)[-1]) for n in ast.walk(active) if isinstance(n, ast.Call))
        for node in ast.walk(active):
            parent = parents.get(node)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and not (isinstance(parent, ast.Attribute) and parent.value is node):
                reference(node.id, executes(node))
            elif isinstance(node, ast.Attribute) and not (isinstance(parent, ast.Attribute) and parent.value is node):
                reference(ast.unparse(node), executes(node))
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
                targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
                for target in targets:
                    if isinstance(target, (ast.Attribute, ast.Subscript)):
                        imported = imported_receiver(target.value)
                        if imported and self.origin(imported)[0] != 'project':
                            reasons.add(f'{relative}:{node.lineno}: external binding mutation')
                        value = getattr(node, 'value', None)
                        supplied = imported_receiver(value)
                        if isinstance(target, ast.Attribute) and supplied and self.origin(supplied)[0] != 'project':
                            reasons.add(f'{relative}:{node.lineno}: unverified callable/value binding')
            full = _name(node, aliases)
            if full == 'os.environ' or full in {'sys.argv', 'sys.stdin'}:
                reasons.add(f'{relative}:{node.lineno}: external environment/input')
            if not isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                continue
            edges = self.imports.get((relative, node.lineno), ())
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported, _ = _imports(self.cfg.root / relative, self.cfg, ast.Module(body=[node], type_ignores=[]))
                # ImportFrom adds symbol-as-module candidates for invalidation;
                # only the source module is initialized by that statement.
                imported = imported[:1] if isinstance(node, ast.ImportFrom) else imported
                for imported_module in imported:
                    reason = self.import_reason(imported_module)
                    if reason:
                        reasons.add(f'{relative}:{node.lineno}: {reason}')
            if isinstance(node, ast.ImportFrom) and any(alias.name == '*' for alias in node.names):
                reasons.add(f'{relative}:{node.lineno}: wildcard binding')
            if isinstance(node, ast.ImportFrom):
                for imported, bound in _aliases(ast.Module(body=[node], type_ignores=[]), self.cfg.root / relative, self.cfg).items():
                    mod, _, wanted = bound.partition(':')
                    stem = mod.replace('.', '/')
                    if relative in self.paths(mod) and (relative.endswith(stem + '.py') or relative.endswith(stem + '/__init__.py')):
                        # A self-import cannot manufacture its own missing export.
                        # The import binding in a whole-module symbol table is not
                        # evidence that the name already existed during execution.
                        earlier = {statement.name for statement in tree.body if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and statement.lineno < node.lineno}
                        earlier.update(name for statement in tree.body if statement.lineno < node.lineno for name in _bindings(ast.Module(body=[statement], type_ignores=[])))
                        child = mod + '.' + wanted
                        child_stem = child.replace('.', '/')
                        submodule = any(self.exists(p) and (p.endswith(child_stem + '.py') or p.endswith(child_stem + '/__init__.py')) for p in self.paths(child))
                        if wanted not in earlier and not submodule:
                            reasons.add(f'{relative}:{node.lineno}: unresolved self import')
            for edge in edges:
                target = self.nodes.get(edge['dst'])
                if edge['prov'] == 'unknown' or target and not target['file']:
                    reasons.add(f'{relative}:{node.lineno}: unresolved import')
                elif target and target['file']:
                    references.add((target['file'], ''))
            if not isinstance(node, ast.Call):
                continue
            name = _name(node.func, aliases)
            short = node.func.attr if isinstance(node.func, ast.Attribute) else name.rsplit('.', 1)[-1]
            project_call = (node.lineno, short) in project_calls and call_counts[node.lineno, short] == 1
            raw = ast.unparse(node.func)
            first, _, rest = raw.partition('.')
            if aliases.get(first) not in (None, '?'):
                mod, _, attr = aliases[first].partition(':')
                found = self.symbol(mod, '.'.join(p for p in (attr, rest) if p))
                if found:
                    _, _, defs, _ = self.file(found[0])
                    if isinstance(defs.get(found[1]), (ast.FunctionDef, ast.AsyncFunctionDef)):
                        project_call = call_counts[node.lineno, short] == 1
                        references.add(found)
            imported_module = imported_receiver(node.func)
            modeled_path = self.modeled_path_call(node, self.cfg.root / relative, bindings, aliases)
            local_import = (name == 'importlib.import_module' and self.origin('importlib')[0] == 'stdlib'
                            and len(node.args) >= 1 and isinstance(node.args[0], ast.Constant)
                            and isinstance(node.args[0].value, str) and not node.args[0].value.startswith('.')
                            and self.origin(node.args[0].value)[0] == 'project')
            if name in {'setattr', 'delattr'} and node.args:
                imported = imported_receiver(node.args[0])
                if imported and self.origin(imported)[0] != 'project':
                    reasons.add(f'{relative}:{node.lineno}: external binding mutation')
            if imported_module and not project_call:
                kind, _ = self.origin(imported_module)
                if kind != 'project' and not modeled_path and not local_import:
                    reasons.add(f'{relative}:{node.lineno}: unverified external call {name or raw}')
            if (isinstance(node.func, ast.Attribute) and not project_call and not modeled_path and not local_import
                    and not known_value(node.func.value)):
                reasons.add(f'{relative}:{node.lineno}: unresolved receiver call')
            if name in {'os.getenv', 'getenv', 'input'} or name in {'eval', 'exec', 'builtins.eval', 'builtins.exec'}:
                reasons.add(f'{relative}:{node.lineno}: dynamic input/execution')
            if name == 'getattr' and len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                value = bindings.get(node.args[0].id) if isinstance(node.args[0], ast.Name) else node.args[0] if isinstance(node.args[0], ast.Call) else None
                finite_lazy = qual == '__getattr__' and data.get('lazy') and value is not None and any(
                    isinstance(call, ast.Call) and _name(call.func, aliases).rsplit('.',1)[-1] == 'import_module'
                    and self.imports.get((relative, call.lineno)) and not any(e['prov'] == 'unknown' for e in self.imports[relative, call.lineno])
                    for call in ast.walk(value))
                if not finite_lazy:
                    reasons.add(f'{relative}:{node.lineno}: unresolved attribute')
            if name in {'globals', 'locals', 'vars'} and not (isinstance(parent, ast.Subscript) and isinstance(parent.ctx, ast.Store)):
                reasons.add(f'{relative}:{node.lineno}: dynamic namespace')
            if short in {'import_module', '__import__'}:
                literal = node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and not node.args[0].value.startswith('.')
                if literal:
                    module_name = node.args[0].value
                    dependencies.update(self.paths(module_name))
                    references.update((p, '') for p in self.paths(module_name) if self.exists(p))
                    stem = module_name.replace('.', '/')
                    if not any(self.exists(p) and (p.endswith(stem + '.py') or p.endswith(stem + '/__init__.py')) for p in self.paths(module_name)):
                        reasons.add(f'{relative}:{node.lineno}: external dynamic import')
                elif not edges or any(e['prov'] == 'unknown' for e in edges) or not any(self.nodes.get(e['dst'], {}).get('file') for e in edges):
                    reasons.add(f'{relative}:{node.lineno}: unresolved import')
            if short in {'run', 'Popen', 'check_call', 'check_output', 'system', 'execv', 'execve'} and not project_call:
                reasons.add(f'{relative}:{node.lineno}: child/process input')
            reading, value = _read_path(node, self.cfg.root / relative, bindings, aliases)
            if reading and not project_call:
                value = (self.cfg.root / value).resolve() if value is not None else None
                if value is None or not value.is_relative_to(self.cfg.root):
                    reasons.add(f'{relative}:{node.lineno}: dynamic or external file')
                else:
                    dependencies.add(self.cfg.rel(value))
            if isinstance(node.func, (ast.Call, ast.Subscript)):
                reasons.add(f'{relative}:{node.lineno}: unresolved callable')
            if isinstance(node.func, ast.Name) and (node.func.id in parameters or aliases.get(node.func.id) == '?') and aliases.get(node.func.id, '?') == '?' and not project_call:
                reasons.add(f'{relative}:{node.lineno}: unresolved callback')
            if name.startswith('sys.path.') or name in {'site.addsitedir', 'os.chdir', 'os.getcwd'}:
                reasons.add(f'{relative}:{node.lineno}: dynamic location/import path')
            if short == 'getfixturevalue':
                reasons.add(f'{relative}:{node.lineno}: dynamic fixture')
        references.discard(key)
        return result

    def record(self, relative):
        pending, seen, files, reasons = [(relative, '*')], set(), {'pyproject.toml'}, set()
        path = self.cfg.root / relative
        try:
            test_tree = self.file(relative)[0]
        except (OSError, SyntaxError):
            test_tree = ast.Module(body=[], type_ignores=[])
            reasons.add(f'{relative}: source could not be collected')
        fixture_names = {arg.arg for node in ast.walk(test_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        for node in ast.walk(test_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'usefixtures':
                fixture_names.update(arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str))
                if any(not isinstance(arg, ast.Constant) or not isinstance(arg.value, str) for arg in node.args):
                    reasons.add(f'{relative}:{node.lineno}: dynamic fixture declaration')
        fixture_sources = {relative}
        for parent in (path.parent, *path.parent.parents):
            if not parent.is_relative_to(self.cfg.root):
                break
            file = self.cfg.rel(parent / 'conftest.py')
            pending.append((file, ''))
            if self.exists(file):
                fixture_sources.add(file)
        registry, visited_sources = {}, set()
        while fixture_sources:
            file = fixture_sources.pop()
            if file in visited_sources:
                continue
            visited_sources.add(file)
            try:
                tree, data, definitions, bindings = self.file(file)
            except (OSError, SyntaxError):
                reasons.add(f'{file}: fixture source could not be collected')
                continue
            aliases = _aliases(tree, self.cfg.root / file, self.cfg)
            candidates = [(file, qual, node, node.name) for qual, node in definitions.items() if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for imported, bound in aliases.items():
                module, _, qual = bound.partition(':')
                found = self.symbol(module, qual) if qual else None
                if found:
                    _, _, defs, _ = self.file(found[0])
                    node = defs.get(found[1])
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        candidates.append((*found, node, imported))
            plugins = bindings.get('pytest_plugins')
            if plugins is not None:
                try:
                    names = ast.literal_eval(plugins)
                    names = [names] if isinstance(names, str) else names
                    for module in names:
                        matches = [p for p in self.paths(module) if self.exists(p)]
                        if not matches and not module.startswith('flowguard.'):
                            reasons.add(f'{file}: external pytest plugin {module}')
                        fixture_sources.update(matches)
                        pending.extend((p, '') for p in matches)
                except (ValueError, TypeError):
                    reasons.add(f'{file}: dynamic pytest plugins')
            for owner, qual, node, exposed in candidates:
                owner_tree, _, _, _ = self.file(owner)
                owner_aliases = _aliases(owner_tree, self.cfg.root / owner, self.cfg)
                for mark in node.decorator_list:
                    call = mark if isinstance(mark, ast.Call) else None
                    name = _name(call.func if call else mark, owner_aliases)
                    if name not in {'pytest.fixture', 'fixture'}:
                        continue
                    public = next((k.value.value for k in call.keywords if k.arg == 'name' and isinstance(k.value, ast.Constant)), exposed) if call else exposed
                    auto = next((not isinstance(k.value, ast.Constant) or bool(k.value.value) for k in call.keywords if k.arg == 'autouse'), False) if call else False
                    registry.setdefault(public, []).append((owner, qual, [arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]]))
                    if auto:
                        fixture_names.add(public)
        selected_fixtures = set()
        while fixture_names:
            name = fixture_names.pop()
            if name in selected_fixtures:
                continue
            selected_fixtures.add(name)
            for file, qual, required in registry.get(name, ()):
                pending.append((file, qual))
                fixture_names.update(required)
        while pending:
            scope = pending.pop()
            if scope in seen:
                continue
            seen.add(scope)
            dependencies, references, unknown = self.summary(*scope)
            files.update(dependencies)
            reasons.update(unknown)
            pending.extend(references)
            if scope[1]:
                pending.append((scope[0], ''))
        record = {file: self.now('file:' + file) for file in sorted(files)}
        record['<engine>'] = self.now('engine:')
        if reasons:
            record['<unresolved>'] = sorted(reasons)
        return record


def test_dependencies(cfg, graph, now=None):
    """Current default Python tests, with shared module/active-source dependencies."""
    context = _TestDependencies(cfg, graph, now or Now(cfg, graph))
    return {file: context.record(file) for file in sorted(test_files(cfg, graph))}


def trace_signatures(cfg, graph, tests):
    """Version a real recording by its test, known dependencies and observed code.

    Unknown runtime inputs remain an explicit boundary, rather than destroying a
    useful code-navigation clue or licensing safe result reuse.
    """
    now = Now(cfg, graph)
    static = test_dependencies(cfg, graph, now)
    mapped = {row[0] for row in graph.con.execute('SELECT id FROM node')}
    shared = {}
    for test in tests:
        file = test.partition('::')[0]
        known = static.get(file, {file: now('file:' + file), '<engine>': now('engine:')})
        if file not in shared:
            from .cache import standard_dependencies
            shared[file] = standard_dependencies(known)
        observed = {}
        for node, source, encoded in graph.con.execute('SELECT node,file,call_lines FROM footprint WHERE test=?', (test,)):
            if node in mapped:
                observed['node:' + node] = now('node:' + node)
            paths = [source, *(path for path, line in json.loads(encoded or '[]'))]
            for relative in paths:
                path = (cfg.root / relative).resolve()
                if path.is_relative_to(cfg.root):
                    relative = cfg.rel(path)
                    observed['file:' + relative] = now('file:' + relative)
        yield test, dict(static=shared[file], observed=observed, unknown=file not in static or '<unresolved>' in known)


def trace_changes(saved, now):
    if not saved or not saved.get('groups'):
        return ['no recorded dependency signature']
    return [key for group in saved['groups'] for key in now.trace_changes(group)]
