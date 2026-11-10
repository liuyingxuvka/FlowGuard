"""One Map-owned, file-grained dependency identity; unknown inputs are rerun."""
from __future__ import annotations

import ast
import codecs
from importlib.metadata import distributions
import fnmatch
import json
import locale
from pathlib import Path
import site
import sys
import tomllib

from flowguard.map.common import content_digest, read_source
from .sources import parse


def _digest(text):
    return content_digest(Path('dependencies'), data=text.encode())


def file_digest(path):
    return content_digest(path, source_only=True) if path.is_file() else 'gone'


def _pytest_options(cfg):
    path = cfg.root / 'pyproject.toml'
    return tomllib.loads(path.read_text(encoding='utf-8-sig')).get('tool', {}).get('pytest', {}).get('ini_options', {}) if path.is_file() else {}


def _patterns(options, name, default):
    value = options.get(name, default)
    return value.split() if isinstance(value, str) else value


# pytest's own default; a project's `norecursedirs` replaces it.
NORECURSEDIRS = ['*.egg', '.*', '_darcs', 'build', 'CVS', 'dist', 'node_modules', 'venv', '{arch}']


def kept_out(folder, patterns):
    """Whether pytest's `norecursedirs` keeps it out of `folder` (an absolute path), as pytest's fnmatch_ex
    matches: a pattern without a path separator matches the folder's name (`flowguard`), one with a
    separator the folder's whole path (`tests/legacy` matches any path ending in it)."""
    import os
    for pattern in patterns:
        if os.sep != '/' and os.sep not in pattern:
            pattern = pattern.replace('/', os.sep)
        if os.sep not in pattern:
            if fnmatch.fnmatch(folder.name, pattern):
                return True
        elif fnmatch.fnmatch(str(folder), pattern if os.path.isabs(pattern) else f'*{os.sep}{pattern}'):
            return True
    return False


def test_scope(cfg):
    """pytest's configured default file scope, never production testfile APIs: `testpaths`, `python_files`
    and the folders `norecursedirs` keeps pytest out of (below a testpaths entry, `kept_out`)."""
    options, paths = _pytest_options(cfg), []
    for value in _patterns(options, 'testpaths', ['.']):
        path = Path(value)
        if path.is_absolute() or not any(char in value for char in '*?['):
            path = path if path.is_absolute() else cfg.root / path
            paths.extend([path.resolve()] if path.exists() else [])
        else:
            paths.extend(path.resolve() for path in cfg.root.glob(value))
    paths = paths or [cfg.root]
    patterns = _patterns(options, 'python_files', ['test_*.py', '*_test.py'])
    skipped = _patterns(options, 'norecursedirs', NORECURSEDIRS)
    def recursed(path, base):
        return path == base or path.is_relative_to(base) and not any(
            kept_out(folder, skipped) for folder in path.parents if folder != base and folder.is_relative_to(base))
    def contains(relative):
        path = (cfg.root / relative).resolve()
        return (path.is_relative_to(cfg.root) and path.is_file() and path.suffix == '.py'
                and any(recursed(path, base) for base in paths)
                and any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns))
    return contains


SENTINEL_FILE = 'tests/test_flowguard_intent.py'      # FlowGuard's own collection test, which init writes


def npm_packages(root):
    """The package.json files `init` serves: the project root's, else those up to two folders down."""
    if (root / 'package.json').is_file():
        return [root / 'package.json']
    return sorted(path for pattern in ('*/package.json', '*/*/package.json') for path in root.glob(pattern)
                  if not any(part == 'node_modules' or part.startswith('.') for part in path.relative_to(root).parts[:-1]))


def own_python_tests(cfg):
    """Whether pytest's default scope (`test_scope`) holds a test file of the project's own, other than
    FlowGuard's sentinel. Folders pytest does not enter (`norecursedirs`, node_modules) are not read."""
    import os
    scope, skipped = test_scope(cfg), _patterns(_pytest_options(cfg), 'norecursedirs', NORECURSEDIRS)
    for folder, names, files in os.walk(cfg.root):
        names[:] = [name for name in names if name not in ('node_modules', '__pycache__')
                    and not kept_out(Path(folder, name).resolve(), skipped)]
        for name in files:
            relative = (Path(folder) / name).relative_to(cfg.root).as_posix()
            if name.endswith('.py') and relative != SENTINEL_FILE and scope(relative):
                return True
    return False


def static_only(cfg):
    """A project whose tests npm runs and pytest has none of its own (a TS/JS project): FlowGuard's checks there
    are `check --static` and the npm test it is wired into, never a pytest run."""
    return bool(npm_packages(cfg.root)) and not own_python_tests(cfg)


def test_files(cfg, graph):
    """Potential default Python test files; imports and fixtures never execute."""
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
        if not contains(file):
            continue
        if error:
            result.add(file)
            continue
        try:
            body = ast.parse(read_source(cfg.root / file)).body
        except (OSError, SyntaxError):
            result.add(file)
            continue
        if disabled(body):
            continue
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(node.name, functions):
                result.add(file)
            elif isinstance(node, ast.ClassDef) and not disabled(node.body) and (matches(node.name, classes) or node.bases):
                if any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(child.name, functions) for child in node.body):
                    result.add(file)
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and options.get('collect_imported_tests', True):
                if any(a.name == '*' or matches(a.asname or a.name.split('.')[-1], [*functions, *classes]) for a in node.names):
                    result.add(file)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and matches(target.id, [*functions, *classes]) for target in targets):
                    result.add(file)
    return result


def project_functions(graph, targets, *, stop=()):
    """The Map's function identities and known project call/read closure."""
    pending, seen, stop = list(targets), set(), set(stop)
    while pending:
        identifier = pending.pop()
        if identifier is None:
            continue
        identifier = graph.canonical(identifier.replace('.<locals>.', '.')) or identifier
        if identifier in seen or identifier in stop:
            continue
        seen.add(identifier)
        node = graph.node(identifier)
        yield identifier, node
        if node:
            pending.extend(edge['dst'] for edge in graph.edges(identifier)
                           if edge['kind'] in {'reads', 'calls'} and edge['prov'] != 'guessed')


def function_fingerprints(graph, targets):
    """Function bodies and their project callees; not an input-closure proof."""
    result = {}
    for identifier, node in project_functions(graph, targets):
        if not node or not node['file']:
            raise ValueError('unmapped project dependency: ' + identifier)
        result.setdefault(node['file'], {})[node['qual']] = node['fp']
    return result


# Builtins whose result depends on their arguments alone; the same names the file closure accepts below.
_PURE = frozenset({'bool', 'int', 'float', 'str', 'len', 'sum', 'min', 'max', 'all', 'any', 'range', 'enumerate',
                   'zip', 'sorted', 'tuple', 'list', 'dict', 'set', 'frozenset', 'abs', 'round'})


def comparison_inputs(graph, target):
    """What one anchor comparison runs, read from the Map: (fingerprints, constants, reasons).

    The fingerprints are the bodies of the target and of the project functions it calls; the constants
    are the module names they read, whose current values belong to the comparison's key. A reason means
    an input the Map cannot read (an effect, a call other than to those functions or a pure builtin, a
    read of an import, a dynamic boundary): that comparison is computed again, never reused."""
    from flowguard.structure.store import unpack
    fingerprints, constants, reasons, files = {}, [], [], {}
    closure = dict(project_functions(graph, [target]))
    for identifier, node in closure.items():
        if not node or not node['file']:
            reasons.append('unmapped project dependency: ' + identifier)
            continue
        fingerprints[identifier] = node['fp']
        if node['kind'] == 'const':
            constants.append((node['module'], node['qual']))
            continue
        if node['kind'] not in {'function', 'method'}:
            reasons.append(f'{identifier} is a {node["kind"]}')
            continue
        if node['effects']:
            reasons.append(f'{identifier} has effects: {node["effects"]}')
        if node['file'] not in files:
            row = graph.con.execute('SELECT data FROM file WHERE path=?', (node['file'],)).fetchone()
            files[node['file']] = unpack(row[0]) if row else {'parse_error': 'not mapped'}
        raw = files[node['file']]
        if raw.get('parse_error') or raw.get('unknown_dynamic_imports') or raw.get('star') or raw.get('getattr') or raw.get('syspath'):
            reasons.append('dynamic source boundary in ' + node['file'])
        bound, owner = set(raw.get('bound', ())), node['module'] + ':' + node['qual'].rpartition('.')[0]
        def known(name):
            """A project symbol of this closure under its dotted name, its module-level name, or `self.x` of
            the method's own class; or a project module read for one of its attributes."""
            if name.startswith(('self.', 'cls.')) and node['kind'] == 'method':
                candidates = [owner + '.' + name.partition('.')[2]]
            elif '.' not in name:
                candidates = [node['module'] + ':' + name]
            else:
                parts = name.split('.')
                candidates = ['.'.join(parts[:cut]) + ':' + '.'.join(parts[cut:]) for cut in range(len(parts) - 1, 0, -1)]
            return (any((graph.canonical(candidate) or candidate) in closure for candidate in candidates)
                    or (graph.node(name) or {}).get('kind') == 'module')
        for call in raw.get('syntax_calls', ()):
            name = call['resolved'] or call['text']
            if call['node'] == identifier and not (name in _PURE and name not in bound or known(name)):
                reasons.append(f'{identifier} calls {name}')
        for read in raw.get('symbol_reads', ()):
            name = read['resolved'] or read['text']
            if read['node'] != identifier or name.partition('.')[0] in {'self', 'cls'} and node['kind'] == 'method':
                continue
            # A plain name the module does not bind is a parameter, a local or a builtin.
            if (name in bound or '.' in name) and not known(name):
                reasons.append(f'{identifier} reads {name}')
    return fingerprints, constants, list(dict.fromkeys(reasons))


def digest(value):
    """One key for a value already reduced to text-stable data (repr of primitives and tuples)."""
    return _digest(repr(value))


class Now:
    def __init__(self, cfg, graph):
        self.cfg, self.graph, self.memo = cfg, graph, {}

    def __call__(self, key):
        if key not in self.memo:
            kind, _, value = key.partition(':')
            if kind == 'node':
                node = self.graph.node(value)
                digest = node['fp'] if node else 'gone'
            elif kind == 'engine':
                base = Path(__file__).resolve().parents[1]
                locations = list(site.getsitepackages())
                if site.ENABLE_USER_SITE:
                    user = site.getusersitepackages()
                    locations.extend([user] if isinstance(user, str) else user)
                packages = sorted({(item.metadata.get('Name', ''), item.version)
                                   for item in distributions(path=list(dict.fromkeys(locations)))})
                # A C/POSIX locale puts the parent in UTF-8 mode and hands its child C.UTF-8 (PEP 538/540): the
                # two decode alike but differ in utf8_mode, so the effective encoding stands in for that flag.
                flags = tuple((name, getattr(sys.flags, name)) for name in sys.flags.__match_args__ if name != 'utf8_mode')
                context = (str(self.cfg.root), sys.version, repr(flags), codecs.lookup(locale.getpreferredencoding(False)).name,
                           sys.get_int_max_str_digits() if hasattr(sys, 'get_int_max_str_digits') else None)
                digest = _digest('\n'.join(str(path.relative_to(base)) + ':' + file_digest(path)
                                          for path in sorted(base.rglob('*.py'))) + repr(context) + repr(packages))
            elif kind == 'listing':
                digest = _digest('\n'.join(row[0] for row in self.graph.con.execute('SELECT path FROM file ORDER BY path')))
            elif kind == 'authority':
                from .sources import Archive
                if not hasattr(self, 'archive'):
                    self.archive = Archive(self.cfg.root)
                digest = _digest(repr(self.archive.status(value)))
            else:
                digest = file_digest(self.cfg.root / value)
            self.memo[key] = digest
        return self.memo[key]


def _literal_reads(tree, relative, cfg, modules):
    """Use the Map's literal path resolver, with actual stdlib import bindings."""
    from flowguard.structure.roots import _path_value
    constructors, namespace, assigned = set(), set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'pathlib':
                    namespace.add(alias.asname or 'pathlib')
                    constructors.add((alias.asname or 'pathlib') + '.Path')
        elif isinstance(node, ast.ImportFrom) and node.module == 'pathlib' and not node.level:
            for alias in node.names:
                if alias.name == 'Path':
                    constructors.add(alias.asname or alias.name)
                    namespace.add(alias.asname or alias.name)
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) else []
        for target in targets:
            for part in ast.walk(target):
                if isinstance(part, ast.Name):
                    assigned.setdefault(part.id, []).append(node.value if target is part and isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) else None)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            assigned.setdefault(node.name, []).append(None)
        if isinstance(node, ast.arg):
            assigned.setdefault(node.arg, []).append(None)
    if 'pathlib' in modules or namespace & assigned.keys():
        return set(), set(), False
    env = {name: values[0] if len(values) == 1 else None for name, values in assigned.items()}
    def expanded(node, seen=frozenset()):
        return expanded(env[node.id], seen | {node.id}) if isinstance(node, ast.Name) and node.id in env and node.id not in seen else node
    from .cache import _literal
    unreadable = object()
    def literal(node):
        return _literal(node, unreadable) is not unreadable
    def read_open(call):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or call.func.attr != 'open':
            return None
        if not all(literal(value) for value in [*call.args, *(keyword.value for keyword in call.keywords)]) or any(keyword.arg is None for keyword in call.keywords):
            return None
        mode = next((value.value for value in call.keywords if value.arg == 'mode'), call.args[0] if call.args else ast.Constant('r'))
        if not isinstance(mode, ast.Constant) or mode.value not in {'r', 'rt', 'rb'}:
            return None
        return call.func.value
    def path_calls(expression):
        pending, found, names = [expression], set(), set()
        while pending:
            part = pending.pop()
            if isinstance(part, ast.Name) and part.id in env and part.id not in names:
                names.add(part.id)
                if env[part.id] is not None:
                    pending.append(env[part.id])
            if isinstance(part, ast.Call):
                name = ast.unparse(part.func)
                if not (name in constructors and len(part.args) == 1 and not part.keywords
                        or name == 'str' and 'str' not in assigned and len(part.args) == 1 and not part.keywords
                        or isinstance(part.func, ast.Attribute) and part.func.attr in {'resolve', 'absolute'} and not part.args and not part.keywords):
                    return None
                found.add(id(part))
            if isinstance(part, ast.Subscript) and (not isinstance(part.slice, ast.Constant) or type(part.slice.value) is not int or part.slice.value < 0):
                return None
            pending.extend(ast.iter_child_nodes(part))
        return found, names
    def canonical(node):
        if node is None:
            return None
        result = ast.parse(ast.unparse(node), mode='eval').body
        for call in ast.walk(result):
            if isinstance(call, ast.Call) and ast.unparse(call.func) in constructors:
                call.func = ast.Name(id='Path', ctx=ast.Load())
        return result
    allowed, files = set(), set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        if not all(literal(value) for value in [*call.args, *(keyword.value for keyword in call.keywords if keyword.arg is not None)]) or any(keyword.arg is None for keyword in call.keywords):
            continue
        expression, extra = None, set()
        if call.func.attr in {'read_text', 'read_bytes'}:
            expression = call.func.value
        elif call.func.attr == 'open':
            expression = read_open(call)
        elif call.func.attr == 'read':
            stream = expanded(call.func.value)
            expression = read_open(stream)
            if expression is not None:
                extra.add(id(stream))
        if expression is None:
            continue
        calls = path_calls(expression)
        if calls is None:
            continue
        calls, names = calls
        value = _path_value(canonical(expression), relative, {name: canonical(env[name]) for name in names})
        if value is None:
            continue
        path = (cfg.root / value).resolve()
        if not path.is_relative_to(cfg.root) or path.exists() and not path.is_file():
            continue
        allowed.update(calls | extra | {id(call)})
        files.add(cfg.rel(path))
    return allowed, files, bool(constructors)


def _dependency_index(graph):
    """Read the unchanged Map once per dependency analysis, never across calls."""
    from flowguard.structure.store import unpack
    facts = {path: (module, unpack(data), sha) for path, module, data, sha in graph.con.execute('SELECT path,module,data,sha FROM file')}
    nodes = graph.nodes()
    by_id = {node['id']: node for node in nodes}
    imports, unknown = {}, {}
    for edge in graph.imports():
        target = by_id.get(edge['dst'])
        if target and target['file']:
            imports.setdefault(edge['file'], set()).add(target['file'])
        elif edge['prov'] == 'unknown':
            name = edge['dst'].removeprefix('missing:')
            if name.split('.')[0].split(':')[0] not in {'flowguard', 'pytest'}:
                unknown.setdefault(edge['file'], []).append('unverified external import ' + name)
    modules = {module: data for module, data, _ in facts.values()}
    declarations = graph.imports(declarations=True)
    def known_export(module, name, seen=frozenset()):
        entry = by_id.get(module)
        module = entry['module'] if entry and entry['file'] else module
        pair = module, name
        if pair in seen:
            return False
        target = graph.canonical(module + ':' + name)
        if target and (node := graph.node(target)) and node['file']:
            return True
        if module + '.' + name in modules:
            return True
        raw = modules.get(module, {})
        binding = (raw.get('facts') or {}).get('imports', {}).get(name)
        links = set()
        if binding and ':' in binding:
            links.add(tuple(binding.split(':', 1)))
        elif binding in modules:
            return True
        if name in raw.get('bound', ()):
            links.update((row.get('module', ''), name) for row in declarations
                         if row['src'] == module and row.get('name') == name and not row.get('typing'))
        return bool(links) and all(known_export(origin, member, seen | {pair}) for origin, member in links)
    for declaration in declarations:
        if declaration.get('typing'):
            continue
        module = declaration.get('module', '')
        if module not in modules and module not in {'flowguard.intent', 'flowguard.intent.api', '__future__', 'pathlib', 'pytest'}:
            unknown.setdefault(declaration['file'], []).append('unverified external import ' + module)
        name = declaration.get('name', '')
        if module in modules and name and name != '*' and not known_export(module, name):
            unknown.setdefault(declaration['file'], []).append('unresolved import ' + module + ':' + name)
    return facts, nodes, imports, unknown, modules, declarations


def _file_dependencies(cfg, graph, seeds, now, *, index=None):
    """Conservative file closure shared by intent and ordinary test selection.

    A whole imported file is one unit: unused dynamic siblings also stay opaque.
    No project/external initializer is imported to discover an origin.
    """
    facts, nodes, imports, unknown, modules, declarations = _dependency_index(graph) if index is None else index
    seeds = {cfg.rel(cfg.root / seed) for seed in seeds}
    pending = list(seeds) + ['pyproject.toml', 'pytest.ini', 'setup.cfg', 'tox.ini']
    for seed in seeds:
        parent = (cfg.root / seed).parent
        while parent.is_relative_to(cfg.root):
            pending.extend(cfg.rel(parent / name) for name in ('conftest.py', '__init__.py') if (parent / name).is_file())
            if parent == cfg.root:
                break
            parent = parent.parent
    result, reasons, seen = {'<engine>': now('engine:'), '<listing>': now('listing:')}, [], set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        path = (cfg.root / relative).resolve()
        if not path.is_relative_to(cfg.root):
            reasons.append('dependency is outside the project: ' + relative)
            continue
        result[relative] = file_digest(path)
        if path.suffix != '.py':
            continue
        if not path.is_file():
            if relative in facts:
                reasons.append('Map source identity changed: ' + relative + '; rebuild map before reuse')
            continue
        if relative not in facts:
            reasons.append('source is not mapped: ' + relative)
            continue
        module, raw, mapped_digest = facts[relative]
        if result[relative] != mapped_digest:
            reasons.append('Map source identity changed: ' + relative + '; rebuild map before reuse')
        parent = path.parent
        while parent.is_relative_to(cfg.root):
            initializer = parent / '__init__.py'
            if initializer.is_file():
                pending.append(cfg.rel(initializer))
            if parent == cfg.root:
                break
            parent = parent.parent
        pending.extend(imports.get(relative, ()))
        reasons.extend(unknown.get(relative, ()))
        if raw.get('parse_error') or raw.get('unknown_dynamic_imports') or raw.get('star') or raw.get('getattr') or raw.get('syspath'):
            reasons.append('dynamic source boundary in ' + relative)
        targets = [node['id'] for node in nodes if node['file'] == relative and node['kind'] in {'function', 'method', 'test'}]
        try:
            for file, definitions in function_fingerprints(graph, targets).items():
                pending.append(file)
                for qual in definitions:
                    target = next((node for node in nodes if node['file'] == file and node['qual'] == qual), None)
                    if target:
                        result['node:' + target['id']] = target['fp']
        except ValueError as error:
            reasons.append(str(error))
        try:
            tree = ast.parse(read_source(path))
        except (OSError, SyntaxError) as error:
            reasons.append(str(error))
            continue
        literal_calls, literal_files, trusted_pathlib = _literal_reads(tree, relative, cfg, modules)
        pending.extend(literal_files)
        if not trusted_pathlib and any(row.get('module') == 'pathlib' for row in declarations if row['file'] == relative):
            reasons.append('unverified pathlib binding in ' + relative)
        definitions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        from .loader import api_aliases, api_call_name
        aliases = api_aliases(tree)
        rules = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and any(isinstance(decorator, ast.Call) and api_call_name(decorator, aliases) == 'rule'
                         for decorator in node.decorator_list)}
        project_names, bindings = set(), {}
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else []
            if isinstance(node, (ast.Global, ast.Nonlocal)) or any(isinstance(target, (ast.Attribute, ast.Subscript)) for target in targets):
                reasons.append('unverified shared-state writes in ' + relative)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id == 'pytest_plugins' for target in targets):
                    try:
                        plugins = ast.literal_eval(node.value)
                        plugins = [plugins] if isinstance(plugins, str) else plugins
                    except (TypeError, ValueError):
                        plugins = None
                    if type(plugins) not in (list, tuple, set) or any(plugin != 'flowguard.intent.plugin' for plugin in plugins):
                        reasons.append('unverified pytest plugin inputs in ' + relative)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound = alias.asname or alias.name.split('.')[0]
                    project_names.add(bound)
                    bindings[bound] = alias.name if isinstance(node, ast.Import) else (node.module or '') + '.' + alias.name
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and Path(node.value).suffix in {'.json', '.yaml', '.yml', '.csv', '.toml', '.txt', '.md'}:
                pending.extend(cfg.rel(candidate) for candidate in (cfg.root / node.value, path.parent / node.value)
                               if candidate.resolve().is_relative_to(cfg.root) and candidate.is_file())
        # Only actual fixture decorators are framework declarations. Runtime
        # pytest calls and aliases escaping that declaration remain opaque.
        framework_nodes, framework_calls = set(), set()
        if 'pytest' not in modules:
            for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
                for decorator in function.decorator_list:
                    target = decorator.func if isinstance(decorator, ast.Call) else decorator
                    name = ast.unparse(target)
                    first, _, rest = name.partition('.')
                    qualified = bindings.get(first, first) + ('.' + rest if rest else '')
                    if qualified != 'pytest.fixture':
                        continue
                    if isinstance(decorator, ast.Call):
                        try:
                            for argument in [*decorator.args, *(keyword.value for keyword in decorator.keywords)]:
                                ast.literal_eval(argument)
                        except (TypeError, ValueError):
                            continue
                        if any(keyword.arg is None for keyword in decorator.keywords):
                            continue
                        framework_calls.add(id(decorator))
                    framework_nodes.update(id(part) for part in ast.walk(decorator))
        pytest_names = {name for name, value in bindings.items() if value == 'pytest' or value.startswith('pytest.')}
        if any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in pytest_names
               and id(node) not in framework_nodes for node in ast.walk(tree)):
            reasons.append('unverified pytest runtime use in ' + relative)
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if id(call) in literal_calls or id(call) in framework_calls:
                continue
            name = ast.unparse(call.func)
            first, _, rest = name.partition('.')
            if first in bindings:
                qualified = bindings[first] + ('.' + rest if rest else '')
                module = qualified.rpartition('.')[0]
                if module not in modules and bindings[first].split('.')[0] not in {'flowguard', '__future__'}:
                    reasons.append(('dynamic or external data read' if bindings[first].split('.')[0] == 'pathlib' else 'unverified external call ' + qualified) + ' in ' + relative)
            if isinstance(call.func, ast.Name) and name == 'type' and len(call.args) == 1 and not call.keywords:
                continue
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'rows' and isinstance(call.func.value, ast.Name) and call.func.value.id in rules:
                continue
            if isinstance(call.func, ast.Name) and (name in definitions or name in {'bool','int','float','str','len','sum','min','max','all','any','range','enumerate','zip','sorted','tuple','list','dict','set','frozenset','abs','round','rule','row','flow','node','relation','transition','state','read'} or name in project_names):
                continue
            if isinstance(call.func, ast.Attribute) and name.partition('.')[0] in project_names:
                # External imports already keep this whole file unverified.
                continue
            reasons.append('unverified call ' + name + ' in ' + relative)
    if reasons:
        result['<unresolved>'] = sorted(set(reasons))
    return result


def standard_keys(record):
    return {('engine:' if key == '<engine>' else 'listing:' if key == '<listing>' else key if key.startswith('node:') else 'file:' + key): value
            for key, value in record.items() if key != '<unresolved>'}


def record(cfg, model, rule, results, graph, now=None, found=None):
    """One coarse source/word identity; a grey/failed result never becomes reusable. The records of one
    session may share `now` (its digests) and `found` (seed files -> their dependencies): most rules have
    the same seeds, every declaration's files."""
    seeds = {model.file_of[rule.id], 'pyproject.toml'}
    nodes, authorities = set(), set()
    entries = list(results.values()) if isinstance(results, dict) else list(results)
    # All declarations are cheap inputs; this avoids a second lower-model resolver.
    seeds.update(model.file_of.values())
    for declaration in [rule, *model.rules.values(), *model.flows.values()]:
        for home in getattr(declaration, 'homes', ()):
            if home.anchor:
                seeds.add(home.anchor.file)
                nodes.add(home.anchor.target)
                if home.anchor.calibrated_by:
                    seeds.add(home.anchor.calibrated_by.partition('::')[0])
            if hasattr(home, 'scenario'):
                seeds.update((home.scenario.file, home.flow.file))
        for node in getattr(declaration, 'nodes', ()):
            for anchor in model.anchor_index.named(node.reference):
                seeds.add(anchor.file)
                nodes.add(anchor.target)
        source = parse(declaration.source)
        if source.kind == 'doc':
            seeds.add(source.path)
        for rid in source.rids + ((declaration.confirmed,) if getattr(declaration, 'confirmed', None) else ()):
            seeds.update('.flowguard/requests/' + rid + suffix for suffix in ('.md', '.json'))
            authorities.add(rid)
    for entry in entries:
        seeds.update(entry.get('files', ()))
        for identifier in entry.get('footprint', ()):
            node = graph.node(identifier)
            if node and node['file']:
                seeds.add(node['file'])
    now = Now(cfg, graph) if now is None else now
    found = {} if found is None else found
    if frozenset(seeds) not in found:
        found[frozenset(seeds)] = _file_dependencies(cfg, graph, seeds, now)
    dependencies = found[frozenset(seeds)]
    keys = standard_keys(dependencies)
    keys['listing:'] = now('listing:')
    keys.update(('authority:' + rid, now('authority:' + rid)) for rid in authorities)
    return dict(dependencies=keys, reasons=list(dependencies.get('<unresolved>', [])), own_nodes=sorted(nodes),
                contracts={child: value for result in entries for child, value in result.get('contracts', {}).items()})


def stale(saved, now):
    if not saved or saved.get('reasons'):
        return ['no complete reusable result']
    return [key for key, digest in saved['dependencies'].items() if now(key) != digest]


def reusable(data, identifier, now):
    values = data.get('results', {}).get(identifier, {}).get('items', {}).values()
    return bool(values) and all(value.get('verdict') in {'ok', 'red'} for value in values) and not stale(data.get('deps', {}).get(identifier), now)


def affected(data, model, now):
    chosen = {identifier for identifier in model.rules if not reusable(data, identifier, now)}
    while True:
        before = set(chosen)
        keys = {model.rules[identifier].decides for identifier in chosen}
        chosen.update(rule.id for rule in model.rules.values() if rule.decides in keys or set(rule.uses) & chosen)
        if chosen == before:
            return sorted(chosen)


def test_dependencies(cfg, graph, now=None):
    now = now or Now(cfg, graph)
    files = sorted(test_files(cfg, graph))
    if not files:
        return {}
    index = _dependency_index(graph)
    return {file: _file_dependencies(cfg, graph, {file}, now, index=index) for file in files}
