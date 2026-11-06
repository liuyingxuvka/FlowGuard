"""Code-owned observation points. Parsing belongs to the existing source map.

An anchor declares a role; it does not prove the author's interpretation.  Pure
observation calls the real, source-verified function in the execution session.
Unproved initialization/calls stay grey and require a calibrated project test.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import importlib
import io
import math
from pathlib import Path, PosixPath, WindowsPath
import re
import sys
import tokenize
import types
import typing

from ..map.common import content_digest, read_source, is_test_file
from . import cells


@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    message: str
    file: str = ''
    line: int = 0
    name: str = ''


def _status(issues):
    return 'red' if any(i.level == 'red' for i in issues) else 'grey' if issues else 'ok'


@dataclass(frozen=True)
class Parameter:
    name: str
    unit: str
    source_type: str


@dataclass(frozen=True)
class Anchor:
    kind: str
    name: str
    file: str
    module: str
    qual: str
    line: int
    target_line: int
    parameters: tuple[Parameter, ...] = ()
    output: str = ''
    output_type: str = ''
    values: tuple = ()
    calibrated_by: str = ''
    issues: tuple[Issue, ...] = ()
    source_digest: str = ''
    receiver: str = ''
    source_role: str = 'production'

    @property
    def target(self):
        return self.module + ':' + self.qual

    @property
    def status(self):
        return _status(self.issues)


@dataclass
class Index:
    entries: tuple[Anchor, ...]
    issues: tuple[Issue, ...] = ()

    @property
    def by_name(self):
        result = {}
        for anchor in self.entries:
            result.setdefault(anchor.name, []).append(anchor)
        return {name: tuple(values) for name, values in result.items()}

    def named(self, name, kind=None):
        return tuple(a for a in self.by_name.get(name, ()) if kind is None or a.kind == kind)

    @property
    def status(self):
        return _status(self.issues)


@dataclass(frozen=True)
class Draft:
    text: str
    ranges: dict
    issues: tuple[Issue, ...]

    @property
    def status(self):
        return _status(self.issues)


@dataclass(frozen=True)
class Observation:
    status: str
    value: object = None
    reasons: tuple[str, ...] = ()
    anchor: str = ''


@dataclass(frozen=True)
class DecisionReading:
    kinds: dict
    reading: object
    issues: tuple[Issue, ...]
    node: object
    literal_globals: dict
    fingerprint: str
    dependencies: dict = field(default_factory=dict)
    dependencies_complete: bool = True


_NAME = r'[^\W\d][\w.-]*'
_HEAD = re.compile(r'#\s*flowguard:\s*(sensor|states|event)\b\s*(.*)')
_SESSION = ContextVar('flowguard_anchor_session', default=None)
_TYPES = {'bool': bool, 'int': int, 'float': float, 'str': str, 'None': type(None),
          'Decimal': Decimal, 'date': date, 'datetime': datetime, 'timedelta': timedelta}


def _annotation(node):
    if node is None:
        return '?'
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


def _type_node(text):
    node = ast.parse(text, mode='eval').body
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _type_node(node.value)
    return node


def _kind(text):
    """Types are syntax, never eval of a project's annotations."""
    node = _type_node(text)
    if isinstance(node, ast.Name) and node.id in _TYPES:
        return cells.kind_of(_TYPES[node.id])
    if isinstance(node, ast.Constant) and node.value is None:
        return None
    if isinstance(node, ast.Subscript):
        name = ast.unparse(node.value).removeprefix('typing.')
        if name == 'Annotated':
            return _kind(ast.unparse(node.slice.elts[0]))
        if name == 'Optional':
            result = _kind(ast.unparse(node.slice))
            result.optional = True
            return result
        if name == 'Literal':
            values = ast.literal_eval(node.slice)
            values = values if isinstance(values, tuple) else (values,)
            if not values or any(type(v) not in (bool, int, float, str, type(None)) for v in values):
                raise ValueError('Literal needs simple literal values')
            return cells.Kind('enum', literals=values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        a, b = ast.unparse(node.left), ast.unparse(node.right)
        if a == 'None' or b == 'None':
            result = _kind(b if a == 'None' else a)
            result.optional = True
            return result
    raise ValueError(f'unsupported simple type: {text}')


def _base_type(text):
    try:
        node = _type_node(text)
    except SyntaxError:
        return text
    if isinstance(node, ast.Subscript) and ast.unparse(node.value).split('.')[-1] == 'Annotated':
        return ast.unparse(node.slice.elts[0])
    return ast.unparse(node).removeprefix('typing.')


def _type_id(text):
    try:
        kind = _kind(text)
        return (kind.name, kind.optional, tuple(sorted((type(v).__name__, repr(v)) for v in kind.literals))) if kind else ('None',)
    except (ValueError, SyntaxError, TypeError, AttributeError):
        return _base_type(text)


def _unit(text):
    try:
        node = _type_node(text)
        if isinstance(node, ast.Subscript) and ast.unparse(node.value).split('.')[-1] == 'Annotated':
            values = node.slice.elts
            if len(values) == 2 and isinstance(values[1], ast.Constant) and isinstance(values[1].value, str):
                return values[1].value
    except (SyntaxError, AttributeError):
        return ''
    return ''


def _definitions(tree):
    """Use the map's spelling of lexical quals, without executing a definition."""
    found = {}
    def visit(body, prefix='', cls=''):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefix + node.name
                found[qual] = (node, cls)
                visit(node.body, qual + '.', qual if isinstance(node, ast.ClassDef) else '')
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                visit(node.body + getattr(node, 'orelse', []) + getattr(node, 'finalbody', [])
                      + [s for h in getattr(node, 'handlers', []) for s in h.body], prefix, cls)
    visit(tree.body)
    return found


def _class_nodes(node):
    stack = list(node.body)
    while stack:
        current = stack.pop()
        if isinstance(current, ast.ClassDef):
            continue
        yield current
        stack.extend(ast.iter_child_nodes(current))


def _parts(text, delimiter=','):
    """Split annotations without splitting Literal['a', 'b'] or quoted units."""
    start, depth, result = 0, 0, []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.OP:
            continue
        if token.string in ('(', '[', '{'):
            depth += 1
        elif token.string in (')', ']', '}'):
            depth -= 1
        elif token.string == delimiter and depth == 0:
            result.append(text[start:token.start[1]].strip())
            start = token.end[1]
    return result + ([text[start:].strip()] if text[start:].strip() else [])


def _return_type(node, params):
    if node.returns is not None:
        return _annotation(node.returns)
    def value_type(value):
        if value is None:
            return 'None'
        if isinstance(value, ast.Constant):
            return 'None' if value.value is None else type(value.value).__name__
        if isinstance(value, ast.Compare) or isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
            return 'bool'
        if isinstance(value, ast.Name):
            return params.get(value.id, '?')
        if isinstance(value, ast.IfExp):
            a, b = value_type(value.body), value_type(value.orelse)
            return a if a == b else '?'
        if isinstance(value, ast.BoolOp):
            types = {value_type(x) for x in value.values}
            return next(iter(types)) if len(types) == 1 else '?'
        return '?'
    def returns(body):
        if not body:
            return False
        last = body[-1]
        return isinstance(last, (ast.Return, ast.Raise)) or isinstance(last, ast.If) and returns(last.body) and returns(last.orelse)
    own = []
    def walk(body):
        for n in body:
            if isinstance(n, ast.Return):
                own.append(value_type(n.value))
            elif not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for _, field in ast.iter_fields(n):
                    if isinstance(field, list) and any(isinstance(x, ast.stmt) for x in field):
                        walk([x for x in field if isinstance(x, ast.stmt)])
    walk(node.body)
    if not returns(node.body):
        own.append('None')
    kinds = set(own)
    return next(iter(kinds)) if len(kinds) == 1 else '?'


def source_facts(tree, text, module, file, *, source_digest='', is_test=False):
    """Canonical comment parse, called with the extractor's already parsed AST."""
    definitions, entries, problems = _definitions(tree), [], []
    lines = text.splitlines()
    def issue(level, code, message, line, name=''):
        return Issue(level, code, message, file, line, name)
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        match = _HEAD.fullmatch(token.string) if token.type == tokenize.COMMENT else None
        if not match:
            continue
        kind, body = match.groups()
        line, column = token.start
        calibration = re.search(r'\s+calibrated_by=(\S+)\s*$', body)
        calibrated_by = calibration[1] if calibration else ''
        body = body[:calibration.start()] if calibration else body
        local = []
        if kind == 'states':
            parsed = re.fullmatch(r'(' + _NAME + r')\s*=\s*(.+)', body)
            if not parsed or '.' not in parsed[1]:
                problems.append(issue('red', 'syntax', 'states needs Class.field = value | value', line))
                continue
            name, raw = parsed.groups()
            cls, _, field_name = name.rpartition('.')
            target = definitions.get(cls)
            values = []
            try:
                parts = _parts(raw, '|')
            except tokenize.TokenError as error:
                parts = []
                local.append(issue('red', 'syntax', str(error), line, name))
            for part in parts:
                try:
                    value = ast.literal_eval(part)
                except (ValueError, SyntaxError):
                    value = part if part.isidentifier() else None
                if value is None and part != 'None':
                    local.append(issue('red', 'states-values', f'unsupported state literal: {part}', line, name))
                if type(value) not in (str, bool, int, float, type(None)):
                    local.append(issue('red', 'states-values', 'states need simple literal values', line, name))
                    value = repr(value)
                values.append(value)
            if len(set(map(repr, values))) != len(values):
                local.append(issue('red', 'states-values', 'state values repeat', line, name))
            if not values:
                local.append(issue('red', 'states-values', 'states need at least one literal value', line, name))
            field_nodes = []
            if target and isinstance(target[0], ast.ClassDef):
                field_nodes = [n for n in _class_nodes(target[0]) if isinstance(n, (ast.Assign, ast.AnnAssign)) and
                               any(isinstance(t, ast.Name) and t.id == field_name or isinstance(t, ast.Attribute) and
                                   isinstance(t.value, ast.Name) and t.value.id == 'self' and t.attr == field_name
                                   for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
            if not field_nodes:
                local.append(issue('red', 'target-missing', f'state field {name} is not in source', line, name))
            for field_node in field_nodes:
                if isinstance(field_node.value, ast.Constant) and field_node.value.value not in values:
                    local.append(issue('red', 'states-values', f'source writes state {field_node.value.value!r} outside {name}', field_node.lineno, name))
            entry = Anchor(kind, name, file, module, name, line, field_nodes[0].lineno if field_nodes else 0,
                           values=tuple(values), calibrated_by=calibrated_by, issues=tuple(local),
                           source_digest=source_digest, source_role='test' if is_test else 'production')
        else:
            parsed = re.fullmatch(r'(' + _NAME + r')\s*\((.*)\)' + (r'\s*->\s*(' + _NAME + r')\s*:\s*(.+)' if kind == 'sensor' else ''), body)
            if not parsed:
                problems.append(issue('red', 'syntax', f'invalid {kind} anchor syntax', line))
                continue
            name, raw, *output = parsed.groups()
            candidates = []
            for qual, (node, cls) in definitions.items():
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                first = min([node.lineno] + [d.lineno for d in node.decorator_list if d.lineno > line])
                if first > line and len(lines[first - 1]) - len(lines[first - 1].lstrip()) == column and \
                        all(not s.strip() or s.lstrip().startswith('#') for s in lines[line:first - 1]):
                    candidates.append((qual, node, cls))
            qual, node, cls = min(candidates, key=lambda x: x[1].lineno) if candidates else ('', None, '')
            declared = []
            try:
                for part in _parts(raw):
                    item = re.fullmatch(r'([^\W\d]\w*)\s*:\s*(.+)', part)
                    if item is None:
                        raise ValueError(f'parameter needs name: {"unit" if kind == "sensor" else "type"}: {part}')
                    declared.append(item.groups())
            except (ValueError, tokenize.TokenError) as error:
                local.append(issue('red', 'syntax', str(error), line, name))
            if len({p[0] for p in declared}) != len(declared):
                local.append(issue('red', 'signature', 'anchor parameters repeat', line, name))
            actual, receiver, return_type = {}, '', '?'
            if node is None:
                local.append(issue('red', 'target-missing', 'anchor has no following function in source', line, name))
            else:
                args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if cls and args and args[0].arg in ('self', 'cls'):
                    receiver = args.pop(0).arg
                actual = {a.arg: _annotation(a.annotation) for a in args}
                if len(declared) != len(actual) or {p[0] for p in declared} != set(actual):
                    local.append(issue('red', 'signature', f'anchor parameters {[p[0] for p in declared]} != source {list(actual)}', line, name))
                if node.args.vararg or node.args.kwarg:
                    local.append(issue('grey', 'variadic', 'variadic parameters require a calibrated test', line, name))
                return_type = _return_type(node, actual)
            params = []
            declared = sorted(declared, key=lambda p: list(actual).index(p[0]) if p[0] in actual else len(actual))
            for parameter, meaning in declared:
                source_type = actual.get(parameter, '?')
                if source_type == '?':
                    local.append(issue('grey', 'type-missing', f'parameter {parameter} has no source type', line, name))
                if kind == 'sensor':
                    if meaning == '?':
                        local.append(issue('grey', 'unit-missing', f'parameter {parameter} needs its unit confirmed', line, name))
                    if _unit(source_type) and _unit(source_type) != meaning:
                        local.append(issue('red', 'unit', f'parameter {parameter} unit {meaning} != source {_unit(source_type)}', line, name))
                elif meaning == '?':
                    local.append(issue('grey', 'type-missing', f'event parameter {parameter} needs its type confirmed', line, name))
                elif _type_id(meaning) != _type_id(source_type) and source_type != '?':
                    local.append(issue('red', 'type', f'parameter {parameter} type {meaning} != source {source_type}', line, name))
                params.append(Parameter(parameter, meaning if kind == 'sensor' else '', source_type))
            output_name, output_type = output if output else ('', '')
            if kind == 'sensor':
                if output_type == '?' or return_type == '?':
                    local.append(issue('grey', 'return-missing', 'return type cannot be checked from source', line, name))
                elif _type_id(output_type) != _type_id(return_type):
                    local.append(issue('red', 'return', f'anchor return type {output_type} != source {return_type}', line, name))
            entry = Anchor(kind, name, file, module, qual, line, node.lineno if node else 0,
                           tuple(params), output_name, output_type, calibrated_by=calibrated_by,
                           issues=tuple(local), source_digest=source_digest, receiver=receiver,
                           source_role='test' if is_test else 'production')
        entries.append(asdict(entry))
    return {'anchors': entries, 'anchor_issues': [asdict(p) for p in problems]} if entries or problems else {}


def _anchor(data):
    data = dict(data)
    data['parameters'] = tuple(Parameter(**p) for p in data.get('parameters', ()))
    data['issues'] = tuple(Issue(**p) for p in data.get('issues', ()))
    data['values'] = tuple(data.get('values', ()))
    return Anchor(**data)


def _index(entries, problems):
    index = Index(tuple(entries))
    for name, group in index.by_name.items():
        roles = {(a.kind, tuple((p.name, p.unit, _type_id(p.source_type)) for p in a.parameters),
                  a.output, _type_id(a.output_type), a.values) for a in group}
        if len(roles) > 1:
            for anchor in group:
                problems.append(Issue('red', 'identity', f'same anchor {name} has conflicting roles, units or signature', anchor.file, anchor.line, name))
    index.issues = tuple(problems)
    return index


def collect(graph):
    """Read the single stored source index, including anchored project tests."""
    from ..structure.store import unpack
    entries, problems = [], []
    for file, sha, blob in graph.con.execute('SELECT path,sha,data FROM file ORDER BY path'):
        data = unpack(blob)
        for value in data.get('anchors', ()):
            anchor = _anchor(dict(value, source_digest=sha))
            entries.append(anchor)
            problems.extend(anchor.issues)
        problems.extend(Issue(**value) for value in data.get('anchor_issues', ()))
    return _index(entries, problems)


def collect_sources(root, files_with_modules):
    """Same facts/index for a historical source slice, without a second full map.

    Entries are (relative_file, module[, is_test]); source identity uses the same
    reader digest as the map. No project module is imported.
    """
    root = Path(root)
    entries, problems = [], []
    for item in files_with_modules:
        file, module, *role = item
        raw = (root / file).read_bytes()
        text = read_source(root / file, data=raw)
        try:
            tree = ast.parse(text, str(root / file))
        except SyntaxError as error:
            problems.append(Issue('red', 'source-syntax', str(error), file, error.lineno or 0))
            continue
        data = source_facts(tree, text, module, file, source_digest=content_digest(root / file, data=raw), is_test=bool(role and role[0]))
        for value in data.get('anchors', ()):
            anchor = _anchor(value)
            entries.append(anchor)
            problems.extend(anchor.issues)
        problems.extend(Issue(**value) for value in data.get('anchor_issues', ()))
    return _index(entries, problems)


def _source(root, anchor):
    path = Path(root) / anchor.file
    if not anchor.source_digest or content_digest(path) != anchor.source_digest:
        raise ValueError(f'{anchor.target}: anchor source changed; rebuild the map')
    text = read_source(path)
    tree = ast.parse(text, str(path))
    current = source_facts(tree, text, anchor.module, anchor.file, source_digest=anchor.source_digest,
                           is_test=anchor.source_role == 'test' or is_test_file(anchor.file) or anchor.file.endswith('conftest.py'))
    if anchor not in [_anchor(row) for row in current.get('anchors', ())]:
        raise ValueError(f'{anchor.target}: anchor metadata does not match the source comment')
    found = _definitions(tree).get(anchor.qual)
    if not found or not isinstance(found[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f'{anchor.target}: observation function is gone')
    return path.resolve(), tree, found[0]


def _literal_globals(tree):
    result = {}
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, SyntaxError):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    result[target.id] = value
    return result


def _read_decision(function, parameters, env, file, line, name, initial=()):
    kinds, issues = {}, list(initial)
    for parameter in parameters:
        try:
            kind = _kind(parameter.source_type)
            if kind is None:
                raise ValueError('None alone has no varying domain')
            kinds[parameter.name] = kind
        except (SyntaxError, ValueError, TypeError, AttributeError) as error:
            issues.append(Issue('grey', 'range-missing', f'{parameter.name}: {error}', file, line, name))
    reading = cells.read_predicate(types.SimpleNamespace(__globals__=env), kinds, node=function) if len(kinds) == len(parameters) else cells.Reading(consts={})
    for parameter, kind in kinds.items():
        evidence = kind.name in ('bool', 'enum') or reading.consts.get(parameter) or any(parameter in plane.coefs for plane in reading.planes) or any(parameter in link for link in reading.links)
        if not evidence:
            issues.append(Issue('grey', 'range-missing', f'{parameter}: no readable comparison bounds or finite type', file, line, name))
    issues.extend(Issue('grey', 'range-incomplete', reason, file, line, name) for reason in reading.reasons)
    return kinds, reading, issues


def decision_reading(graph_or_root, anchor):
    """Canonical static cells/linear reading; never imports project annotations."""
    root = Path(graph_or_root if isinstance(graph_or_root, (str, Path)) else graph_or_root.root)
    _, tree, function = _source(root, anchor)
    env = _literal_globals(tree)
    kinds, reading, issues = _read_decision(function, anchor.parameters, env, anchor.file, anchor.line, anchor.name, anchor.issues)
    from ..structure.extract import fingerprint
    definitions, dependencies, seen, complete = _definitions(tree), {}, set(), True
    def dependency(node, qual):
        nonlocal complete
        if qual in seen:
            return
        seen.add(qual)
        dependencies['node:' + anchor.module + ':' + qual] = fingerprint(node, node.name)
        locals_ = {a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
        locals_ |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - locals_
        for name in names:
            if name in env:
                dependencies['literal:' + anchor.module + ':' + name] = content_digest(root / anchor.file, data=repr(env[name]).encode())
                if not _immutable(env[name]):
                    complete = False
            elif name in definitions and isinstance(definitions[name][0], ast.FunctionDef):
                dependency(definitions[name][0], name)
            elif name not in _TYPES and name not in _PURE_BUILTINS | _ERRORS:
                complete = False
    dependency(function, anchor.qual)
    return DecisionReading(kinds, reading, tuple(issues), function, env,
                           fingerprint(function, function.name), dependencies, complete)


def draft(graph, target):
    """Suggest a source comment and the existing cells/linear partitions; no project import."""
    node = graph.node(target)
    if node is None and ':' in target:
        file, _, qual = target.partition(':')
        node = next((n for n in graph.nodes(file=file) if n['qual'] == qual), None)
    if node is None or node['kind'] not in ('function', 'method', 'test'):
        return Draft('', {}, (Issue('red', 'target-missing', f'function {target} is not in the map'),))
    file, module, qual = node['file'], node['module'], node['qual']
    raw = (graph.root / file).read_bytes()
    text = read_source(graph.root / file, data=raw)
    tree = ast.parse(text)
    function, cls = _definitions(tree)[qual]
    args = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    if cls and args and args[0].arg in ('self', 'cls'):
        args.pop(0)
    parameters = tuple(Parameter(a.arg, _unit(_annotation(a.annotation)), _annotation(a.annotation)) for a in args)
    kinds, reading, issues = _read_decision(function, parameters, _literal_globals(tree), file, function.lineno, qual)
    ranges = {}
    if len(kinds) == len(args):
        if not any(i.code != 'range-incomplete' for i in issues):
            space = cells.build_space(kinds, reading.consts, reading.planes, reading.links, reading.reasons, reading.hints)
            # Literal annotation is a finite type; do not manufacture <other> outside it.
            rows = [row for row in space.cells if all(k.name != 'enum' or row[n] in k.literals for n, k in kinds.items())]
            ranges = {'points': {n: [v for v in values if kinds[n].name != 'enum' or v in kinds[n].literals]
                                 for n, values in space.pts.items()},
                      'cells': rows, 'complete': space.complete, 'reasons': list(space.reasons), 'total': len(rows)}
            issues.extend(Issue('grey', 'range-incomplete', reason, file, function.lineno) for reason in space.reasons
                          if not any(i.code == 'range-incomplete' and i.message == reason for i in issues))
    name = qual.replace('.', '_')
    comment = f'# flowguard: sensor {name}(' + ', '.join(f'{a.arg}: {_unit(_annotation(a.annotation)) or "?"}' for a in args)
    comment += f') -> result: {_return_type(function, {a.arg: _annotation(a.annotation) for a in args})}'
    if any(not _unit(_annotation(a.annotation)) for a in args):
        issues.append(Issue('grey', 'unit-missing', 'confirm the meaning and units of the proposed parameters', file, function.lineno, name))
    return Draft(comment, ranges, tuple(issues))


@contextmanager
def _execution_session(root):
    """Only the verified execution worker/pytest integration opens this session."""
    token = _SESSION.set(Path(root).resolve())
    try:
        # The backend owns calibration facts in the same worker lifetime.
        from .calibration import _execution_session as backend_session
        with backend_session(root):
            yield
    finally:
        _SESSION.reset(token)


def observe(root, anchor, values):
    """One entry: verified session preserves real mutant/probe function objects."""
    if _SESSION.get() == Path(root).resolve():
        return _observe_current(root, anchor, values)
    from .calibration import execute
    return execute(root, anchor, values)


def _observe_current(root, anchor, values):
    if _SESSION.get() != Path(root).resolve():
        raise RuntimeError('project observation requires the verified execution session')
    if anchor.issues:
        return Observation(anchor.status, reasons=tuple(i.message for i in anchor.issues), anchor=anchor.target)
    if anchor.kind == 'states':
        return Observation('grey', reasons=('state fields are read by their existing project lifecycle check',), anchor=anchor.target)
    try:
        path, tree, function = _source(root, anchor)
    except (ValueError, SyntaxError, OSError) as error:
        return Observation('red', reasons=(str(error),), anchor=anchor.target)
    if anchor.calibrated_by:
        from .calibration import _observe_current as calibrated
        return calibrated(root, anchor, values)
    if anchor.kind != 'sensor' or anchor.source_role != 'production':
        return Observation('grey', reasons=('direct observation needs a production sensor; use its project test',), anchor=anchor.target)
    if set(values) != {p.name for p in anchor.parameters}:
        return Observation('red', reasons=('observation fields differ from the real anchor parameters',), anchor=anchor.target)
    for parameter in anchor.parameters:
        try:
            _kind(parameter.source_type)  # point container shapes are not a pure finite input proof
            accepted = _accepts(parameter.source_type, values[parameter.name])
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return Observation('grey', reasons=(f'{parameter.name}: simple source type is not known',), anchor=anchor.target)
        if not accepted:
            return Observation('red', reasons=(f'{parameter.name}: input does not have source type {parameter.source_type}',), anchor=anchor.target)
    from .config import load_config, setup_path
    from .imports import prepare
    cfg = load_config(root)
    setup_path(cfg)
    try:
        reasons = _pure_reasons(cfg, anchor, tree, function)
    except (ValueError, SyntaxError, OSError, ImportError) as error:
        return Observation('red', reasons=(f'source verification: {type(error).__name__}: {error}',), anchor=anchor.target)
    if reasons:
        return Observation('grey', reasons=tuple(reasons), anchor=anchor.target)
    try:
        prepare(cfg.root)
        fn = importlib.import_module(anchor.module)
        for name in anchor.qual.split('.'):
            fn = getattr(fn, name)
    except Exception as error:
        return Observation('red', reasons=(f'loading source anchor: {type(error).__name__}: {error}',), anchor=anchor.target)
    code = getattr(fn, '__code__', None)
    if code is None or Path(code.co_filename).resolve() != path or fn.__qualname__.replace('.<locals>', '') != anchor.qual:
        return Observation('red', reasons=('loaded callable does not match the actual source anchor',), anchor=anchor.target)
    positional = [values[a.arg] for a in function.args.posonlyargs]
    kwargs = {name: value for name, value in values.items() if name not in {a.arg for a in function.args.posonlyargs}}
    try:
        value = fn(*positional, **kwargs)
    except Exception as error:
        return Observation('ok', value=cells.Raised(error), anchor=anchor.target)
    try:
        accepted = _accepts(anchor.output_type, value)
    except (ValueError, SyntaxError, TypeError, AttributeError):
        return Observation('grey', value=value, reasons=('simple return type is not known',), anchor=anchor.target)
    return Observation('ok' if accepted else 'red', value=value,
                       reasons=() if accepted else (f'real return does not have declared type {anchor.output_type}',), anchor=anchor.target)


def _accepts(spec, value):
    """Point shape validation, never a finite domain or a purity proof.

    Annotation syntax is read, not evaluated. Exact builtins/stdlib paths prevent
    custom iterators, __fspath__, __class_getitem__ and coercion from running here.
    Unknown actual objects/cycles are unsupported (grey), not made into literals.
    """
    any_node = ast.Name(id='Any', ctx=ast.Load())
    active = set()
    containers = {'list': list, 'dict': dict, 'tuple': tuple, 'List': list, 'Dict': dict, 'Tuple': tuple,
                  'typing.List': list, 'typing.Dict': dict, 'typing.Tuple': tuple}

    def validate(node):
        name = ast.unparse(node)
        if name in ('Any', 'typing.Any', 'Path', 'pathlib.Path', 'bytes', 'None') or name in containers:
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            validate(node.left)
            validate(node.right)
            return
        if isinstance(node, ast.Subscript):
            base = ast.unparse(node.value)
            args = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
            if base in ('Annotated', 'typing.Annotated') and len(args) >= 2:
                validate(args[0])
                return
            if base in ('Optional', 'typing.Optional') and len(args) == 1:
                validate(args[0])
                return
            if base in ('Union', 'typing.Union') and args or base in containers:
                kind = containers.get(base)
                if kind is list and len(args) != 1 or kind is dict and len(args) != 2:
                    raise ValueError('point container annotation has the wrong number of types')
                if kind is tuple and len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                    args = args[:1]
                for argument in args:
                    validate(argument)
                return
        _kind(name)  # rejects unknown classes/calls, including inside empty containers

    def union(parts, actual):
        unknown = False
        for part in parts:
            try:
                if check(part, actual):
                    return True
            except ValueError:
                unknown = True
        if unknown:
            raise ValueError('point union contains an unsupported type')
        return False

    def container(kind, args, actual):
        if type(actual) is not kind:
            return False
        if id(actual) in active:
            raise ValueError('cyclic point values are not supported')
        active.add(id(actual))
        try:
            if kind is dict:
                if args is None:
                    args = [any_node, any_node]
                if len(args) != 2:
                    raise ValueError('dict point annotation needs key and value types')
                return all(check(args[0], k) and check(args[1], v) for k, v in actual.items())
            if kind is list:
                if args is not None and len(args) != 1:
                    raise ValueError('list point annotation needs one item type')
                return all(check(args[0] if args is not None else any_node, v) for v in actual)
            if args is None:
                return all(check(any_node, v) for v in actual)
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                return all(check(args[0], v) for v in actual)
            return len(args) == len(actual) and all(check(t, v) for t, v in zip(args, actual))
        finally:
            active.remove(id(actual))

    def check(node, actual):
        name = ast.unparse(node)
        if name in ('Any', 'typing.Any'):
            if type(actual) in (type(None), bool, int, float, str, bytes, Decimal, date, datetime, timedelta, PosixPath, WindowsPath):
                return True
            if type(actual) in (list, dict, tuple):
                return container(type(actual), None, actual)
            raise ValueError('point value has an unsupported object type')
        if name in ('Path', 'pathlib.Path'):
            return type(actual) in (PosixPath, WindowsPath)
        if name in containers:
            return container(containers[name], None, actual)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return union([node.left, node.right], actual)
        if isinstance(node, ast.Subscript):
            base = ast.unparse(node.value)
            args = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
            if base in ('Annotated', 'typing.Annotated') and args:
                return check(args[0], actual)
            if base in ('Optional', 'typing.Optional') and len(args) == 1:
                return actual is None or check(args[0], actual)
            if base in ('Union', 'typing.Union'):
                return union(args, actual)
            if base in containers:
                return container(containers[base], args, actual)
        if name == 'bytes':
            return type(actual) is bytes
        if _base_type(name) == 'None':
            return actual is None
        kind = _kind(name)
        if actual is None:
            return kind.optional or kind.name == 'enum' and None in kind.literals
        if kind.name == 'enum':
            return any(type(actual) is type(v) and actual == v for v in kind.literals)
        expected = {'bool': (bool,), 'int': (int,), 'float': (int, float), 'str': (str,),
                    'dec': (Decimal,), 'date': (date,), 'datetime': (datetime,), 'td': (timedelta,)}[kind.name]
        return type(actual) in expected and not (type(actual) is float and not math.isfinite(actual)) \
            and not (type(actual) is Decimal and not actual.is_finite()) \
            and not (type(actual) is datetime and actual.tzinfo is not None and type(actual.tzinfo) is not timezone)

    node = _type_node(spec)
    validate(node)
    return check(node, value)


def _immutable(value):
    return type(value) in (str, bool, int, float, type(None)) or type(value) is tuple and all(_immutable(x) for x in value)


_PURE_BUILTINS = {'abs', 'min', 'max', 'round', 'len', 'int', 'float', 'str', 'bool'}
_ERRORS = {'ValueError', 'TypeError', 'ZeroDivisionError', 'OverflowError', 'AssertionError', 'RuntimeError', 'KeyError'}
_INTRINSICS = {'Decimal', 'date', 'datetime', 'timedelta'}
_TYPE_IMPORTS = {'typing': {'Literal', 'Optional', 'Annotated'}, 'decimal': {'Decimal'},
                 'datetime': {'date', 'datetime', 'timedelta'}}


def _pure_reasons(cfg, anchor, tree, function):
    """A small positive proof, not an inference from missing I/O evidence."""
    from .imports import _find
    from ..structure.paths import project_code
    reasons, checked = [], set()
    def unknown(message):
        if message not in reasons:
            reasons.append(message)
    if anchor.receiver:
        unknown('instance/class receiver needs a calibrated project test')
    if isinstance(function, ast.AsyncFunctionDef) or function.args.vararg or function.args.kwarg:
        unknown('async/variadic execution is not proved pure')
    globals_ = _literal_globals(tree)
    definitions = _definitions(tree)
    bindings = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    bindings |= set(globals_)
    bindings |= {a.asname or a.name.split('.')[0] for s in tree.body if isinstance(s, ast.Import) for a in s.names}
    bindings |= {a.asname or a.name for s in tree.body if isinstance(s, ast.ImportFrom) for a in s.names}
    imports = {}

    def annotation_safe(node):
        if node is None or isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, str)):
            return True
        if isinstance(node, ast.Name):
            return node.id in _TYPES or node.id in imports or node.id in definitions
        if isinstance(node, ast.Subscript):
            return isinstance(node.value, ast.Name) and imports.get(node.value.id) in ('Literal', 'Optional', 'Annotated') and \
                (annotation_safe(node.slice) or isinstance(node.slice, ast.Tuple) and all(annotation_safe(x) for x in node.slice.elts))
        if isinstance(node, ast.Constant):
            return type(node.value) in (bool, int, float)
        return isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) and annotation_safe(node.left) and annotation_safe(node.right)

    def definition_safe(node, postponed):
        if isinstance(node, ast.ClassDef):
            if node.decorator_list or node.keywords or any(not isinstance(b, ast.Name) or b.id != 'object' for b in node.bases):
                unknown(f'module class initialization is not proved pure: {node.name}')
            statements(node.body, postponed)
            return
        if node.decorator_list:
            unknown(f'function decorators are not proved pure: {node.name}')
        for value in [*node.args.defaults, *[x for x in node.args.kw_defaults if x is not None]]:
            try:
                ast.literal_eval(value)
            except (ValueError, SyntaxError):
                unknown(f'function default initialization is not a literal: {node.name}')
        if not postponed and not all(annotation_safe(x) for x in [node.returns, *[a.annotation for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]]):
            unknown(f'function annotation initialization is not proved pure: {node.name}')

    def imported(module, names, here):
        for count in range(1, len(module.split('.')) + 1):
            name = '.'.join(module.split('.')[:count])
            spec = _find(name)
            if spec is None or not spec.origin:
                unknown(f'module initialization import is unresolved: {name}')
                continue
            trusted = name in _TYPE_IMPORTS and name in sys.modules and spec.origin == getattr(sys.modules[name].__spec__, 'origin', None)
            if trusted and names <= _TYPE_IMPORTS[name]:
                continue
            if not str(spec.origin).endswith('.py') or not project_code(spec.origin, cfg.root):
                unknown(f'module initialization of {name} is not proved pure')
                continue
            module_safe(Path(spec.origin), name)
        # A from import may initialize a child submodule, not only its package.
        for member in names:
            child = _find(module + '.' + member)
            if child and child.origin:
                if str(child.origin).endswith('.py') and project_code(child.origin, cfg.root):
                    module_safe(Path(child.origin), module + '.' + member)
                else:
                    unknown(f'imported child initialization is not proved pure: {module}.{member}')

    def statements(body, postponed=False, module=''):
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definition_safe(statement, postponed)
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str) or isinstance(statement, ast.Pass):
                continue
            elif isinstance(statement, ast.ImportFrom) and statement.module == '__future__':
                if any(a.name != 'annotations' for a in statement.names):
                    unknown('unknown future initialization')
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                if isinstance(statement, ast.Import):
                    for alias in statement.names:
                        imported(alias.name, set(), module)
                else:
                    name = statement.module or ''
                    if statement.level:
                        package = module if module and _find(module) and _find(module).submodule_search_locations is not None else module.rpartition('.')[0]
                        try:
                            name = importlib.util.resolve_name('.' * statement.level + name, package)
                        except ImportError:
                            unknown('relative module initialization is unresolved')
                            continue
                    names = {a.name for a in statement.names}
                    if '*' in names:
                        unknown('star import initialization is not proved pure')
                    imported(name, names, module)
                    if name in _TYPE_IMPORTS and module == anchor.module:
                        imports.update({a.asname or a.name: a.name for a in statement.names if a.name in _TYPE_IMPORTS[name]})
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if not all(isinstance(t, ast.Name) for t in targets):
                    unknown('module initialization writes an attribute or item')
                if statement.value is not None:
                    try:
                        ast.literal_eval(statement.value)
                    except (ValueError, SyntaxError):
                        unknown('module initialization computes a nonliteral value')
                if isinstance(statement, ast.AnnAssign) and not postponed and not annotation_safe(statement.annotation):
                    unknown('module field annotation initialization is not proved pure')
            elif isinstance(statement, ast.If) and ast.dump(statement.test) == ast.dump(ast.parse('__name__ == "__main__"', mode='eval').body):
                statements(statement.orelse, postponed, module)
            else:
                unknown(f'module initialization contains {type(statement).__name__}')

    def module_safe(path, module):
        path = path.resolve()
        if path in checked:
            return
        checked.add(path)
        module_tree = tree if path == (cfg.root / anchor.file).resolve() else ast.parse(read_source(path), str(path))
        postponed = any(isinstance(s, ast.ImportFrom) and s.module == '__future__' and any(a.name == 'annotations' for a in s.names) for s in module_tree.body)
        statements(module_tree.body, postponed, module)

    # Importing a package child executes each parent initializer as well.
    imported(anchor.module, set(), anchor.module)
    if (bindings & set(_TYPES)) - set(imports):
        unknown('simple type name is shadowed by a project binding')
    active = set()
    closed = {}
    def closed_call(call, caller):
        """Only same-module scalar forwarding; annotations alone are no proof."""
        name = call.func.id if isinstance(call.func, ast.Name) else ''
        found = definitions.get(name)
        if not found or found[1] or not isinstance(found[0], ast.FunctionDef):
            return False
        callee = found[0]
        arguments = [*callee.args.posonlyargs, *callee.args.args, *callee.args.kwonlyargs]
        positional = [*callee.args.posonlyargs, *callee.args.args]
        if callee.args.vararg or callee.args.kwarg or len(call.args) > len(positional):
            return False
        supplied = dict(zip((a.arg for a in positional), call.args))
        for keyword in call.keywords:
            if keyword.arg is None or keyword.arg in supplied:
                return False
            supplied[keyword.arg] = keyword.value
        defaults = dict(zip((a.arg for a in positional[-len(callee.args.defaults):]), callee.args.defaults)) if callee.args.defaults else {}
        defaults.update({a.arg: v for a, v in zip(callee.args.kwonlyargs, callee.args.kw_defaults) if v is not None})
        caller_types = {a.arg: _annotation(a.annotation) for a in (*caller.args.posonlyargs, *caller.args.args, *caller.args.kwonlyargs)}
        if set(supplied) - {a.arg for a in arguments}:
            return False
        for argument in arguments:
            value = supplied.get(argument.arg, defaults.get(argument.arg))
            if isinstance(value, ast.Name) and value.id in caller_types:
                if _type_id(caller_types[value.id]) != _type_id(_annotation(argument.annotation)):
                    return False
            elif isinstance(value, ast.Constant):
                try:
                    if not _accepts(_annotation(argument.annotation), value.value):
                        return False
                except (ValueError, SyntaxError, TypeError, AttributeError):
                    return False
            else:
                return False
        if name in closed:
            return bool(closed[name])
        closed[name] = None
        before = len(reasons)
        body_safe(callee)
        assignments = {}
        for statement in ast.walk(callee):
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                assignments.setdefault(statement.targets[0].id, []).append(statement.value)
        def primitive(expression, seen=()):
            if expression is None or isinstance(expression, ast.Constant) and _immutable(expression.value):
                return True
            if isinstance(expression, ast.Name):
                if expression.id in assignments:
                    values = assignments[expression.id]
                    return expression.id not in seen and len(values) == 1 and primitive(values[0], (*seen, expression.id))
                return expression.id in {a.arg for a in arguments} or expression.id in globals_ and _immutable(globals_[expression.id])
            if isinstance(expression, (ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Subscript, ast.Tuple)):
                return all(primitive(child, seen) for child in ast.iter_child_nodes(expression) if isinstance(child, ast.expr))
            if isinstance(expression, ast.Call):
                builtin = isinstance(expression.func, ast.Name) and expression.func.id in _PURE_BUILTINS and expression.func.id not in bindings
                return (builtin and all(primitive(x, seen) for x in [*expression.args, *[k.value for k in expression.keywords]])
                        or closed_call(expression, callee))
            return False
        closed[name] = len(reasons) == before and all(primitive(r.value) for r in ast.walk(callee) if isinstance(r, ast.Return))
        return closed[name]

    def body_safe(node):
        if node.name in active:
            unknown(f'recursive call is not bounded: {node.name}')
            return
        active.add(node.name)
        params = {a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
        nodes = [n for statement in node.body for n in ast.walk(statement)]
        local = params | {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        literal_locals = {}
        for statement in nodes:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                try:
                    literal_locals[statement.targets[0].id] = ast.literal_eval(statement.value)
                except (ValueError, SyntaxError):
                    pass
        decimal_input = any(_base_type(_annotation(a.annotation)) == 'Decimal' for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs))
        for value in nodes:
            if isinstance(value, (ast.Global, ast.Nonlocal, ast.Delete, ast.Yield, ast.YieldFrom, ast.Await, ast.For, ast.AsyncFor,
                                  ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                                  ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)) and value is not node:
                unknown(f'function {node.name} contains unproved {type(value).__name__}')
            elif isinstance(value, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = value.targets if isinstance(value, ast.Assign) else [value.target]
                if any(not isinstance(t, ast.Name) for t in targets):
                    unknown(f'function {node.name} writes an attribute or item')
                if any(isinstance(t, ast.Name) and t.id in params for t in targets):
                    unknown(f'function {node.name} rebinds an input; primitive forwarding is not proved')
            elif isinstance(value, ast.Attribute):
                unknown(f'attribute access is not proved pure: {ast.unparse(value)}')
            elif isinstance(value, ast.Subscript):
                if not isinstance(value.value, ast.Name) or value.value.id not in params and \
                        not _immutable(literal_locals.get(value.value.id, globals_.get(value.value.id, object()))):
                    unknown(f'item access is not proved to use a primitive value: {ast.unparse(value)}')
            elif isinstance(value, ast.BinOp) and decimal_input:
                unknown('Decimal arithmetic reads the current decimal context; use a calibrated test')
            elif isinstance(value, ast.Call):
                name = value.func.id if isinstance(value.func, ast.Name) else ''
                if name in _PURE_BUILTINS | _ERRORS and name not in bindings | local:
                    continue
                if name in imports and imports[name] in _INTRINSICS and name not in local and name not in globals_ and name not in definitions:
                    if imports[name] == 'Decimal' and (len(value.args) != 1 or not isinstance(value.args[0], ast.Constant) or value.keywords):
                        unknown('Decimal construction from a varying value is not proved context-free')
                    continue
                if not closed_call(value, node):
                    unknown(f'call is not proved pure: {ast.unparse(value.func)}')
            elif isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load):
                if value.id in local or value.id in _PURE_BUILTINS | _ERRORS or value.id in imports or value.id in definitions or value.id in _TYPES:
                    continue
                if value.id not in globals_ or not _immutable(globals_[value.id]):
                    unknown(f'global value is not a proved immutable literal: {value.id}')
        active.remove(node.name)
    body_safe(function)
    return reasons
