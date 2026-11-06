"""A bounded, read-only projection of explicit Python control to anchor calls.

This is not a CFG or an execution proof. Given an entry invocation, only literal
boolean branches and straight-line calls/returns are established. Unknown
branches, dispatch or control constructs stay unknown, never possible bypasses.
Call sequences say that an anchor is invoked, not that its operation succeeds.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from ..map.common import content_digest, read_source
from ..structure.store import unpack


@dataclass(frozen=True)
class PathReport:
    paths: tuple[tuple[str, ...], ...] = ()
    unknown: tuple[str, ...] = ()
    files: tuple[str, ...] = ()

    @property
    def complete(self):
        return not self.unknown


_UNPROVED = object()


class _Projection:
    def __init__(self, graph, index, node_names):
        self.graph, self.root = graph, Path(graph.root).resolve()
        self.nodes = set(node_names)
        self.targets, self.by_name = {}, {}
        self.sources, self.files, self.unknown = {}, set(), set()
        for anchor in index.entries:
            if anchor.name not in self.nodes:
                continue
            target = graph.canonical(anchor.target)
            if target is not None:
                self.targets.setdefault(target, set()).add(anchor.name)
            self.by_name.setdefault(anchor.name, []).append(anchor)

    def issue(self, file, node, reason):
        self.unknown.add(f'{file}:{getattr(node, "lineno", 0)}: {reason}')
        return None

    def file_source(self, file):
        self.files.add(file)
        if file not in self.sources:
            path = (self.root / file).resolve()
            row = self.graph.con.execute('SELECT sha,parse_error,data FROM file WHERE path=?', (file,)).fetchone()
            if not path.is_relative_to(self.root) or path.suffix != '.py' or row is None:
                self.unknown.add(f'{file}: static path source is unavailable or not Python')
                self.sources[file] = None
            elif row[1]:
                self.unknown.add(f'{file}: source parse failed: {row[1]}')
                self.sources[file] = None
            elif not path.is_file() or content_digest(path) != row[0]:
                self.unknown.add(f'{file}: source map is stale; rebuild before checking paths')
                self.sources[file] = None
            else:
                try:
                    tree = ast.parse(read_source(path), filename=file)
                except (OSError, SyntaxError) as error:
                    self.unknown.add(f'{file}: cannot read source ({type(error).__name__})')
                    self.sources[file] = None
                else:
                    definitions = {}
                    def collect(body, prefix=''):
                        for statement in body:
                            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                qual = prefix + statement.name
                                definitions[qual] = statement
                                collect(statement.body, qual + '.')
                    collect(tree.body)
                    self.sources[file] = definitions, unpack(row[2]).get('syntax_calls', ()), tree
        return self.sources[file]

    def source(self, target):
        node = self.graph.node(target)
        if node is None or not node.get('file'):
            self.unknown.add(f'{target}: no mapped Python source')
            return None
        parsed = self.file_source(node['file'])
        function = parsed[0].get(node['qual']) if parsed else None
        if not isinstance(function, ast.FunctionDef):
            if parsed:
                self.unknown.add(f'{target}: only synchronous Python function paths are supported')
            return None
        return node, function, parsed[1]

    def target(self, caller, function, call, facts, constants=None):
        # Map lexical call facts locate the spelling; resolved call edges must
        # confirm the project target. Guessed/observed edges do not establish it.
        parameters = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args,
                                           *function.args.kwonlyargs]}
        parameters.update(arg.arg for arg in (function.args.vararg, function.args.kwarg) if arg)
        if isinstance(call.func, ast.Name):
            if call.func.id in parameters:
                return self.issue(caller['file'], call, f'dynamic callable parameter {call.func.id}')
        elif isinstance(call.func, ast.Attribute):
            receiver = call.func.value
            while isinstance(receiver, ast.Attribute):
                receiver = receiver.value
            if isinstance(receiver, ast.Name) and receiver.id in parameters:
                return self.issue(caller['file'], call, f'dynamic receiver parameter {receiver.id}')
        elif not isinstance(call.func, ast.Attribute):
            return self.issue(caller['file'], call, 'dynamic callable expression')
        raw = ast.unparse(call.func)
        spellings = {fact.get('resolved', raw) for fact in facts
                     if fact['node'] == caller['id'] and fact['line'] == call.lineno and fact.get('text') == raw}
        if len(spellings) != 1:
            return self.issue(caller['file'], call, 'call target is not uniquely mapped')
        spelling = spellings.pop()
        found = self.candidates(caller, spelling)
        if caller['qual']:
            edges = {edge['dst'] for edge in self.graph.edges(caller['id'])
                     if edge['kind'] == 'calls' and edge['prov'] == 'resolved'}
            # The map omits a resolved self-call edge. It is still enough to report
            # recursion as unknown, never enough to turn recursion into a path.
            edges.add(caller['id'])
            found &= edges
        # Module root calls have lexical facts, but no function call edge. Their
        # unique lexical identity is used only by analyze_root_paths below.
        if len(found) != 1:
            return self.issue(caller['file'], call, 'call target is not uniquely mapped')
        return found.pop()

    def candidates(self, caller, spelling):
        candidates = []
        if '.' not in spelling:
            qual = caller['qual'].rpartition('.')[0]
            candidates.extend(caller['module'] + ':' + name for name in
                              (qual + '.' + spelling if qual else spelling, spelling))
        else:
            parts = spelling.split('.')
            candidates.extend('.'.join(parts[:cut]) + ':' + '.'.join(parts[cut:])
                              for cut in range(len(parts) - 1, 0, -1))
        found = {self.graph.canonical(candidate) for candidate in candidates}
        found.discard(None)
        return found

    def anchored_call(self, name, target, arguments, stack):
        return arguments + [name]

    def expression(self, expression, caller, function, facts, constants, stack):
        if expression is None or isinstance(expression, (ast.Constant, ast.Name)):
            return []
        if isinstance(expression, ast.Call):
            result = []
            # Python evaluates arguments before invoking the outer function.
            if any(isinstance(arg, ast.Starred) for arg in expression.args) or any(key.arg is None for key in expression.keywords):
                return self.issue(caller['file'], expression, 'expanded call arguments are not supported')
            for argument in [*expression.args, *(key.value for key in expression.keywords)]:
                calls = self.expression(argument, caller, function, facts, constants, stack)
                if calls is None:
                    return None
                result += calls
            target = self.target(caller, function, expression, facts, constants)
            if target is None:
                return None
            names = self.targets.get(target, set())
            if len(names) > 1:
                return self.issue(caller['file'], expression, 'one call resolves to several modeled anchor names')
            if names:
                name = next(iter(names))
                sites = [anchor for anchor in self.by_name[name] if self.graph.canonical(anchor.target) == target]
                if any(getattr(anchor, 'status', 'ok') != 'ok' for anchor in sites):
                    return self.issue(caller['file'], expression, 'anchor source is unverified')
                if self.source(target) is None:
                    return None
                return self.anchored_call(name, target, result, stack)
            nested = self.function(target, stack)
            return result + nested if nested is not None else None
        if isinstance(expression, ast.Set) and not all(isinstance(child, ast.Constant) for child in expression.elts):
            return self.issue(caller['file'], expression, 'set hashing may dispatch')
        if isinstance(expression, (ast.Tuple, ast.List, ast.Set)):
            children = expression.elts
        elif isinstance(expression, ast.Dict):
            if any(key is None for key in expression.keys):
                return self.issue(caller['file'], expression, 'mapping expansion may dispatch')
            if not all(isinstance(key, ast.Constant) for key in expression.keys):
                return self.issue(caller['file'], expression, 'mapping key hashing may dispatch')
            children = [part for pair in zip(expression.keys, expression.values) for part in pair if part is not None]
        elif isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
            children = [expression.operand]
        elif isinstance(expression, (ast.Attribute, ast.Subscript)):
            return self.issue(caller['file'], expression, 'dynamic attribute or subscript evaluation')
        else:
            return self.issue(caller['file'], expression, f'{type(expression).__name__} expression order is not supported')
        result = []
        for child in children:
            calls = self.expression(child, caller, function, facts, constants, stack)
            if calls is None:
                return None
            result += calls
        return result

    def boolean(self, expression, constants):
        if isinstance(expression, ast.Constant) and type(expression.value) is bool:
            return expression.value
        if isinstance(expression, ast.Name):
            return constants.get(expression.id, _UNPROVED)
        if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
            value = self.boolean(expression.operand, constants)
            return not value if value is not _UNPROVED else _UNPROVED
        return _UNPROVED

    def statements(self, body, caller, function, facts, constants, stack):
        result = []
        for statement in body:
            if not caller['qual'] and isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                                              ast.Import, ast.ImportFrom)):
                continue  # Root discovery concerns explicit calls, not initialization proof.
            if isinstance(statement, (ast.Pass, ast.Import, ast.ImportFrom)):
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    return self.issue(caller['file'], statement, 'function-local import execution is unproved'), False
                continue
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue  # A function docstring has no calls.
            if isinstance(statement, ast.If):
                value = self.boolean(statement.test, constants)
                if value is _UNPROVED:
                    return self.issue(caller['file'], statement, 'branch condition is not a proved boolean literal'), False
                nested, returned = self.statements(statement.body if value else statement.orelse,
                                                    caller, function, facts, constants, stack)
                if nested is None:
                    return None, False
                result += nested
                if returned:
                    return result, True
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if not all(isinstance(target, ast.Name) for target in targets):
                    return self.issue(caller['file'], statement, 'nonlocal assignment may dispatch'), False
                calls = self.expression(statement.value, caller, function, facts, constants, stack)
                value = self.boolean(statement.value, constants)
                for target in targets:
                    constants[target.id] = value
            elif isinstance(statement, (ast.Expr, ast.Return)):
                calls = self.expression(statement.value, caller, function, facts, constants, stack)
            else:
                return self.issue(caller['file'], statement, f'{type(statement).__name__} control flow is not supported'), False
            if calls is None:
                return None, False
            result += calls
            if isinstance(statement, ast.Return):
                return result, True
        return result, False

    def function(self, target, stack=()):
        if target in stack:
            self.unknown.add(f'{target}: recursive helper is not a finite source path')
            return None
        source = self.source(target)
        if source is None:
            return None
        caller, function, facts = source
        constants = {}
        result, _ = self.statements(function.body, caller, function, facts, constants, (*stack, target))
        return result


def analyze_paths(graph, index, entry_names, node_names=None):
    """Project provable normal source sequences onto named anchors, without imports.

    ``paths`` retains repeated anchor calls. It is conditional on entry invocation
    and concerns explicit source control, not operation completion, arbitrary
    runtime dispatch or exception safety. Any unsupported entry path adds a grey
    reason; consumers must not turn an absent sequence into proof of no route.
    """
    names = set(node_names if node_names is not None else (anchor.name for anchor in index.entries))
    context = _Projection(graph, index, names)
    paths = []
    for entry in entry_names:
        sites = context.by_name.get(entry, ())
        if not sites:
            context.unknown.add(f'{entry}: entry anchor is not mapped')
        for anchor in sites:
            target = graph.canonical(anchor.target)
            if target is None or getattr(anchor, 'status', 'ok') != 'ok':
                context.unknown.add(f'{entry}: entry anchor source is unverified')
                continue
            calls = context.function(target)
            if calls is not None:
                path = (entry, *calls)
                if path not in paths:
                    paths.append(path)
    return PathReport(tuple(paths), tuple(sorted(context.unknown)), tuple(sorted(context.files)))


class _RootProjection(_Projection):
    def __init__(self, graph, index, node_names):
        production = tuple(anchor for anchor in index.entries
                           if getattr(anchor, 'source_role', 'production') == 'production')
        super().__init__(graph, type('ProductionAnchors', (), {'entries': production})(),
                         {anchor.name for anchor in production})
        self.protected = set(node_names)
        self.prefix, self.first_known = [], False
        self.root_assignments = {}

    def anchored_call(self, name, target, arguments, stack):
        self.prefix.append(name)
        if name in self.protected:
            if self.first_known:
                return arguments + [name]
            self.first_known = True
        # Expand new wrappers and the first protected entry. Later protected
        # anchors remain atomic observations, not proofs of operation success.
        nested = self.function(target, stack)
        return arguments + [name] + nested if nested is not None else None

    def boolean(self, expression, constants):
        if (isinstance(expression, ast.Compare) and isinstance(expression.left, ast.Name)
                and expression.left.id == '__name__' and len(expression.ops) == len(expression.comparators) == 1
                and isinstance(expression.comparators[0], ast.Constant)
                and expression.comparators[0].value == '__main__'
                and '__name__' in constants and isinstance(expression.ops[0], (ast.Eq, ast.NotEq))):
            equal = constants['__name__'] == '__main__'
            return equal if isinstance(expression.ops[0], ast.Eq) else not equal
        return super().boolean(expression, constants)

    def statements(self, body, caller, function, facts, constants, stack):
        # Do not mistake a module-reassigned function name for its earlier
        # declaration. A general binding interpreter is deliberately absent.
        if caller['qual']:
            return super().statements(body, caller, function, facts, constants, stack)
        result = []
        for statement in body:
            self.root_assignments[caller['file']] = set(constants) - {'__name__'}
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                class Initialization(ast.NodeVisitor):
                    called = False
                    def visit_Call(self, node):
                        self.called = True
                    def visit_FunctionDef(self, node):
                        for expression in [*node.decorator_list, *node.args.defaults,
                                           *(value for value in node.args.kw_defaults if value is not None),
                                           *(arg.annotation for arg in [*node.args.posonlyargs, *node.args.args,
                                                                       *node.args.kwonlyargs] if arg.annotation),
                                           *([node.returns] if node.returns else [])]:
                            self.visit(expression)
                    visit_AsyncFunctionDef = visit_FunctionDef
                initialization = Initialization()
                initialization.visit(statement)
                if initialization.called:
                    return self.issue(caller['file'], statement, 'definition initialization call order is unproved'), False
            calls, returned = super().statements([statement], caller, function, facts, constants, stack)
            if calls is None:
                return None, False
            result += calls
            if returned:
                return result, True
        return result, False

    def target(self, caller, function, call, facts, constants=None):
        if not caller['qual']:
            self.root_assignments.setdefault(caller['file'], set()).update(set(constants or {}) - {'__name__'})
        first = call.func
        while isinstance(first, ast.Attribute):
            first = first.value
        if isinstance(first, ast.Name) and first.id in self.root_assignments.get(caller['file'], ()):
            return self.issue(caller['file'], call, 'module callable was reassigned; root dispatch is unproved')
        target = super().target(caller, function, call, facts, constants)
        if target is not None and not caller['qual']:
            node = self.graph.node(target)
            if node['file'] == caller['file'] and node['line'] >= call.lineno:
                return self.issue(caller['file'], call, 'function is defined after this root call')
        return target


def analyze_root_paths(graph, index, node_names):
    """Discover bounded module/script source routes into protected anchor names.

    Only actual module-level call facts (including explicit ``__main__`` arms)
    provide roots. Source routes are conditional on module/script execution, not
    evidence that a module ran. Library functions are never declared entries
    merely because callers are absent. Framework registration, dynamic module
    dispatch and general initialization/exception behavior are outside this
    finite scope. New wrappers are retained before the first protected anchor.
    """
    protected = set(node_names)
    production = tuple(anchor for anchor in index.entries
                       if getattr(anchor, 'source_role', 'production') == 'production')
    canonical = {anchor.name: {target for site in production if site.name == anchor.name
                              if (target := graph.canonical(site.target)) is not None}
                 for anchor in production}
    ancestors = {target for name in protected for target in canonical.get(name, ())}
    pending = list(ancestors)
    while pending:
        for edge in graph.edges(pending.pop(), direction='in', kind='calls'):
            # This is scope selection only, never proof of a route. Guesses may
            # pull a source into analysis, but cannot make its path definite.
            if edge['src'] not in ancestors:
                ancestors.add(edge['src'])
                pending.append(edge['src'])
    paths, unknown, files, rooted = [], set(), set(), set()
    for file, module, data in graph.con.execute('SELECT path,module,data FROM file WHERE is_test=0 ORDER BY path'):
        if not file.endswith('.py'):
            continue
        facts = unpack(data).get('syntax_calls', ())
        roots = [fact for fact in facts if fact['node'] == module or
                 (owner := graph.node(fact['node'])) is not None and owner['kind'] == 'class']
        if not roots:
            continue
        probe = _RootProjection(graph, index, protected)
        caller = dict(id=module, module=module, qual='', file=file)
        if not any(probe.candidates(caller, fact.get('resolved', fact['text'])) & ancestors for fact in roots):
            continue
        parsed = probe.file_source(file)
        if parsed is None:
            unknown.update(probe.unknown)
            files.update(probe.files)
            continue
        for main in (True, False):
            context = _RootProjection(graph, index, protected)
            context.sources.update(probe.sources)
            function = ast.parse('def __module_root__(): pass').body[0]
            context.statements(parsed[2].body, caller, function, facts,
                               {'__name__': '__main__' if main else module}, ())
            if context.prefix:
                rooted.update(context.prefix)
                if protected.intersection(context.prefix) and tuple(context.prefix) not in paths:
                    paths.append(tuple(context.prefix))
            unknown.update(context.unknown)
            files.update(context.files)
    for anchor in production:
        if anchor.name not in protected and anchor.name not in rooted and canonical.get(anchor.name, set()) & ancestors:
            unknown.add(f'{anchor.name}: external entry status is not proved by a module/script root')
    return PathReport(tuple(paths), tuple(sorted(unknown)), tuple(sorted(files)))
