"""Reuse only results whose code, helpers and original sources still have the same identities."""
from __future__ import annotations

import ast
import json
from importlib.metadata import distributions
from pathlib import Path
import site
import sys
import fnmatch
import tomllib

from flowguard.map.common import content_digest, read_source
from .config import is_test_rel
from .sources import parse


def _digest(data):
    return content_digest(Path('summary'), data=data.encode())


def file_digest(path):
    return content_digest(path, source_only=True) if path.is_file() else 'gone'


class _Module(ast.NodeTransformer):
    def __init__(self, retained):
        self.retained = retained

    def visit_FunctionDef(self, node):
        if node.name not in self.retained:
            node.body = [ast.Pass()]
        return node
    visit_AsyncFunctionDef = visit_FunctionDef

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


def _imports(path, cfg):
    """Resolve local imports from paths, without importing a helper or a package initializer."""
    try:
        tree = ast.parse(read_source(path))
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


def _path(node, file):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value)
    if isinstance(node, ast.Name) and node.id == '__file__':
        return file
    if isinstance(node, ast.Attribute) and node.attr == 'parent':
        value = _path(node.value, file)
        return value.parent if value is not None else None
    if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'Path' and len(node.args) == 1:
        return _path(node.args[0], file)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = _path(node.left, file), _path(node.right, file)
        return left / right if left is not None and right is not None else None
    return None


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
        name = call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else ''
        if name == 'open' and call.args:
            mode = next((k.value.value for k in call.keywords if k.arg == 'mode' and isinstance(k.value, ast.Constant)), None)
            if mode is None and len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
                mode = call.args[1].value
            if isinstance(mode, str) and any(flag in mode for flag in 'wax'):
                continue
            expression = call.args[0]
        elif name in {'read_text', 'read_bytes'} and isinstance(call.func, ast.Attribute):
            expression = call.func.value
        else:
            continue
        value = _path(expression, path)
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
                digest = _digest('\n'.join(str(p.relative_to(base)) + ':' + file_digest(p) for p in files) + sys.version + repr(packages))
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
    for home in getattr(rule, 'homes', []):
        node = graph.canonical(home.target)
        if node:
            nodes.add(node)
        else:
            keys.update('file:' + p for p in module_paths(cfg, home.target.partition(':')[0], roots))
            keys.add('listing:')
        files.update(p for p in module_paths(cfg, home.target.partition(':')[0], roots) if (cfg.root / p).is_file())
        files.add(cfg.rel(home.adapter.__code__.co_filename))
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
    source = parse(rule.source)
    if source.kind == 'doc':
        files.add(source.path)
    for rid in source.rids + ((rule.confirmed,) if getattr(rule, 'confirmed', None) else ()):
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


def test_dependencies(cfg, graph, now=None):
    """Static file dependencies conservatively supplement actual test footprints.

    A file is the selection unit. Imports include helpers, package initializers and
    conftest files. Unresolved dynamic imports/reads cannot claim reusable test
    coverage; the conservative rerun stays local to the tests that use them.
    """
    roots = [cfg.root / root['path'] for root in graph.roots()]
    now = now or Now(cfg, graph)
    parsed = {}
    nodes = graph.nodes()
    import_files, unknown_imports = _map_imports(graph, nodes)

    def inspect_file(relative):
        if relative in parsed:
            return parsed[relative]
        path = cfg.root / relative
        modules, data = _imports(path, cfg)
        dependencies = {path for module in modules for path in module_paths(cfg, module, roots)} | set(data) | import_files.get(relative, set())
        try:
            tree = ast.parse(read_source(path))
            launches = {alias.asname or alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                        and node.module in {'subprocess', 'os'} for alias in node.names
                        if alias.name in {'run', 'Popen', 'check_call', 'check_output', 'system', 'execv', 'execve'}}
            dynamic = relative in unknown_imports or any(isinstance(n, ast.Call) and (
                isinstance(n.func, ast.Name) and n.func.id in {'__import__', 'exec', 'eval', *launches}
                or isinstance(n.func, ast.Attribute) and n.func.attr == 'import_module'
                or isinstance(n.func, ast.Name) and n.func.id == 'open'
                or isinstance(n.func, ast.Attribute) and n.func.attr in {'read_text', 'read_bytes', 'run', 'Popen', 'check_call', 'check_output', 'system', 'execv', 'execve'}) for n in ast.walk(tree))
        except (OSError, SyntaxError):
            dynamic = True
        parsed[relative] = dependencies, dynamic
        return parsed[relative]

    output = {}
    config = cfg.root / 'pyproject.toml'
    ini = tomllib.loads(config.read_text(encoding='utf-8-sig')).get('tool', {}).get('pytest', {}).get('ini_options', {}) if config.is_file() else {}
    patterns = ini.get('python_functions', ['test'])
    patterns = patterns.split() if isinstance(patterns, str) else patterns
    file_patterns = ini.get('python_files', ['test_*.py', '*_test.py'])
    file_patterns = file_patterns.split() if isinstance(file_patterns, str) else file_patterns
    def test_file(file):
        return any(fnmatch.fnmatchcase(Path(file).name, pattern) for pattern in file_patterns)
    tests = {node['file'] for node in nodes if node['kind'] in {'function', 'method', 'test'}
             and test_file(node['file']) and any(node['qual'].rsplit('.', 1)[-1].startswith(pattern)
                 or fnmatch.fnmatchcase(node['qual'].rsplit('.', 1)[-1], pattern) for pattern in patterns)}
    tests.update(file for file, error in graph.con.execute('SELECT path,parse_error FROM file') if error and test_file(file))
    for relative in sorted(tests):
        path = (cfg.root / relative).resolve()
        if path.is_relative_to(cfg.intent) or path == cfg.root / 'tests/test_flowguard_intent.py':
            continue
        pending = [relative, 'pyproject.toml']
        for parent in (path.parent, *path.parent.parents):
            if not parent.is_relative_to(cfg.root):
                break
            pending.append(cfg.rel(parent / 'conftest.py'))
        dependencies, dynamic = {'<engine>': now('engine:')}, False
        while pending:
            file = pending.pop()
            if file in dependencies:
                continue
            dependencies[file] = now('file:' + file)
            if file.endswith('.py') and (cfg.root / file).is_file():
                imports, unknown = inspect_file(file)
                pending.extend(imports)
                dynamic |= unknown
        if dynamic:
            dependencies['<unresolved>'] = None
        output[relative] = dependencies
    return output


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
