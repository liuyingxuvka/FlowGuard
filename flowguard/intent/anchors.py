"""Code-owned observation points. Parsing belongs to the existing source map.

An anchor declares a role; it does not prove the author's interpretation.  Pure
observation calls the real, source-verified function in the execution session.
Unproved initialization/calls stay grey and require a calibrated project test.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import enum
import importlib
import inspect
import io
import keyword
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
    role: str = 'input'
    inferred: bool = False
    alias: str = ''          # the source parameter this declared name maps to: ELIGIBLE(days=overdue_days)

    @property
    def source(self):
        return self.alias or self.name


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
    owner: bool = False      # `# flowguard: owner NAME` on a function: the reference its same-name copies follow
    writers: tuple = ()      # a data owner `owner Table.column writers=module:function,...`
    pairs: tuple = ()        # `with=Model.field[=value],...`: fields every write of this one also writes
    alone: tuple = ()        # `alone=function(reason),...`: writers that may write it alone, with why
    on: str = ''             # `on=update` / `on=create`: the pairs hold only for writes that change a row / make one
    projection: str = ''     # `-> result[0]` / `-> result.ok`: copies are compared on this part of the result
    fields: tuple = ()       # `fields days=(today - hire.due).days`: rule fields read from each call's own arguments

    @property
    def inputs(self):
        return tuple(p for p in self.parameters if p.role == 'input')

    @property
    def contexts(self):
        return tuple(p for p in self.parameters if p.role == 'context')

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
_HEAD = re.compile(r'#\s*flowguard:\s*(sensor|states|event|owner|same|together|writers)\b\s*(.*)')
_FOREIGN_HEAD = re.compile(r'//\s*flowguard:\s*(sensor|owner|same|together|writers)\b\s*(.*)$')
_QUAL = r'(?:[^\W\d]|\$)[\w$]*(?:\.(?:[^\W\d]|\$)[\w$]*)*'
_PROJECTION = r'result(?:\[[^\]]*\]|\.[^\W\d]\w*)+'
_SESSION = ContextVar('flowguard_anchor_session', default=None)
# What one verified session already read about a source anchor before calling it: the project's sources,
# configuration and import path are fixed for the session (imports.prepare refuses a change).
_SESSION_FACTS = ContextVar('flowguard_anchor_session_facts', default=None)
_TYPES = {'bool': bool, 'int': int, 'float': float, 'str': str, 'None': type(None),
          'Decimal': Decimal, 'date': date, 'datetime': datetime, 'timedelta': timedelta}


def _agreement(kind, body):
    """Translate the public spellings into the one existing anchor representation."""
    if kind == 'same':
        reference = re.match(r'(' + _NAME + r')\s+ref\b(.*)', body)
        return 'sensor', reference[1] + reference[2] if reference else body, bool(reference), False
    if kind in ('together', 'writers'):
        parts = re.fullmatch(r'(' + _NAME + r')\s+(\S+)(.*)', body)
        if parts is None:
            raise ValueError(f'{kind} needs a field and its {"partners" if kind == "together" else "writers"}')
        name, values, options = parts.groups()
        if kind == 'writers' and options.strip():
            raise ValueError('writers needs a comma-separated list of functions')
        if kind == 'together':
            if re.search(r'(?<!\S)(?:writers|with|alone)=', options):
                raise ValueError('together options are on= and except=')
            options = re.sub(r'(?<!\S)except=', 'alone=', options)
        return 'owner', name + (' with=' if kind == 'together' else ' writers=') + values + options, False, True
    return kind, body, False, False


def _position(text, file, module):
    """Scope new bare names locally; repository paths are resolved by the source index."""
    from ..structure.readers.registry import language_for, module_name
    path, colon, qual = text.rpartition(':')
    if not colon:
        if not re.fullmatch(_QUAL, text):
            raise ValueError('a writer needs a function name or repository-relative path:function')
        return module + ':' + text
    if not re.fullmatch(_QUAL, qual) or not path or path.startswith('/') or '\\' in path \
            or any(part in ('', '.', '..') for part in path.split('/')) or ':' in path:
        raise ValueError('a code position needs a repository-relative path:function')
    language = language_for(path)
    if language is None:
        raise ValueError('a code position needs a source file path:function')
    target = module if path == file else path if language == 'python' else module_name(path)
    return target + ':' + qual


def _indexed_agreement(anchor, kind, modules, positions=None):
    """Resolve new agreement positions to the source map's actual function identities."""
    if kind not in ('writers', 'together'):
        return anchor
    issues = list(anchor.issues)
    def resolve(position):
        target, colon, qual = position.rpartition(':')
        target = modules.get(target, target)
        if positions is not None:
            matches = positions[target].get(qual, ())
            if len(matches) == 1:
                return matches[0]
            issues.append(Issue('red', 'position', f'cannot resolve {position} to one declared function; '
                                'use the actual function or object and method in that source file',
                                anchor.file, anchor.line, anchor.name))
        return target + colon + qual
    writers = tuple(resolve(value) for value in anchor.writers)
    alone = tuple(resolve(value.partition('(')[0]) + '(' + value.partition('(')[2] for value in anchor.alone)
    return replace(anchor, writers=writers, alone=alone, issues=tuple(issues))


class _Positions(dict):
    """{module: {declared qual: [function id]}}, each module's entry read from the map when first asked for."""

    def __init__(self, graph, foreign):
        super().__init__()
        self.graph, self.foreign = graph, foreign

    def __missing__(self, module):
        from ..structure import store
        declared = {}
        for qual, raw in self.graph.con.execute(
                "SELECT qual, raw FROM node WHERE module = ? AND kind IN ('function', 'method') ORDER BY nid", (module,)):
            name = qual
            if module in self.foreign:
                data = store.unpack(raw)
                name = (data['holder'] + '.' + data['name']) if data.get('holder') else data['declared_qual']
            declared.setdefault(name, []).append(module + ':' + qual)
        self[module] = declared
        return declared


def _agreement_positions(graph, modules):
    """Actual function ids, retaining the foreign reader's named object holders: {module: {declared qual: [id]}}, a
    module's read when it is first asked for (`positions[module]`; one that is no module of the map has none)."""
    from ..structure.readers.registry import ECMA, language_for
    return _Positions(graph, {module for file, module in modules.items() if language_for(file) in ECMA})


def _spelling_at(lines, number, file):
    if not 0 < number <= len(lines):
        return None
    text = lines[number - 1]
    return _HEAD.fullmatch(text.lstrip()) if file.endswith('.py') else _FOREIGN_HEAD.search(text)


def _old_spellings(match, notices):
    """Collect notices for this index read, rather than suppressing later warm reads."""
    if match is None:
        return
    kind, body = match.groups()
    if kind == 'sensor':
        notices.add(('sensor', 'same NAME'))
    elif kind == 'owner':
        writers, pairs = 'writers=' in body, 'with=' in body
        if writers and pairs:
            notices.add(('owner with writers= and with=', 'separate writers and together comments'))
        elif writers:
            notices.add(('owner writers=', 'writers FIELD FUNCTIONS'))
        elif pairs:
            notices.add(('owner with=', 'together FIELD PARTNERS'))
        else:
            notices.add(('function owner', 'same NAME ref'))
        if 'alone=' in body:
            notices.add(('alone=', 'except=path:function(reason)'))


def _inline(spelled):
    """A comment's or the code's own spelling inside a message: its ` -> ` written `->`, as ` -> ` is where a FlowGuard
    line puts its next step (`red: comment a.py:5: anchor return type bool->extra != source bool -> correct ...`)."""
    return str(spelled).replace(' -> ', '->')


def _warn_spellings(notices):
    from .deprecation import warn
    for feature, replacement in sorted(notices):
        warn(feature, replacement)


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


def _source_types(tree):
    aliases, modules = {}, {}
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and not statement.level:
            allowed = _TYPE_IMPORTS.get(statement.module, ())
            aliases.update({a.asname or a.name: a.name for a in statement.names if a.name in allowed})
        elif isinstance(statement, ast.Import):
            modules.update({a.asname or a.name: a.name for a in statement.names if a.name in ('typing', 'decimal', 'datetime')})
    def annotation(node):
        if node is None:
            return '?'
        class Names(ast.NodeTransformer):
            def visit_Name(self, current):
                return ast.Name(id=aliases.get(current.id, current.id), ctx=ast.Load())
            def visit_Attribute(self, current):
                if isinstance(current.value, ast.Name) and current.value.id in modules and current.attr in _TYPE_IMPORTS[modules[current.value.id]]:
                    return ast.Name(id=current.attr, ctx=ast.Load())
                return self.generic_visit(current)
        # Parse a fresh expression; never mutate the extractor's source AST.
        return ast.unparse(Names().visit(_type_node(_annotation(node))))
    return annotation


def _parameter_role(text, enum_names=()):
    if text == '?' or text in enum_names:
        return 'input'  # The runtime may infer this one parameter from an actual primitive.
    try:
        _kind(text)
        return 'input'
    except (ValueError, SyntaxError, TypeError, AttributeError):
        return 'context'


def parameter_kind(parameter, actual=...):
    """One input-kind owner; actual values never override explicit context roles."""
    if parameter.role == 'context' and not (parameter.inferred and isinstance(actual, enum.Enum)):
        return None
    try:
        kind = _kind(parameter.source_type)
        if kind is None:
            raise ValueError('None alone has no varying domain')
        return kind
    except (ValueError, SyntaxError, TypeError, AttributeError):
        if isinstance(actual, enum.Enum):
            return cells.kind_of(type(actual))
        if parameter.source_type == '?' and actual is not ...:
            if type(actual) in (bool, int, float, str, Decimal, date, datetime, timedelta):
                return cells.kind_of(type(actual))
            if parameter.inferred:
                return None
        raise ValueError(f'{parameter.name}: simple source type or actual primitive is unavailable') from None


def _enum_names(tree):
    names, modules = set(), set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.module == 'enum' and not statement.level:
            names.update(a.asname or a.name for a in statement.names if a.name in ('Enum', 'IntEnum', 'StrEnum'))
        elif isinstance(statement, ast.Import):
            modules.update(a.asname or a.name for a in statement.names if a.name == 'enum')
    return {n.name for n in tree.body if isinstance(n, ast.ClassDef) and any(
        isinstance(b, ast.Name) and b.id in names or isinstance(b, ast.Attribute) and
        isinstance(b.value, ast.Name) and b.value.id in modules and b.attr in ('Enum', 'IntEnum', 'StrEnum') for b in n.bases)}


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


FIELDS_HELP = ('syntax: fields name=expression name=expression; expressions use the function parameters and module names, for example '
               '# flowguard: sensor FEE fields days=(today - hire.due).days member=customer.is_member')


def _tokens(text):
    return [token for token in tokenize.generate_tokens(io.StringIO(text).readline)
            if token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT)]


def _split_fields(body):
    """(head, field text or None): an anchor's head before its top-level `fields` keyword. `fields` is
    the keyword when a field name follows it, so `-> fields: int` stays an output name."""
    tokens, depth = _tokens(body), 0
    for index, token in enumerate(tokens):
        if token.type == tokenize.OP and token.string in ('(', '[', '{'):
            depth += 1
        elif token.type == tokenize.OP and token.string in (')', ']', '}'):
            depth -= 1
        elif index and depth == 0 and token.type == tokenize.NAME and token.string == 'fields' and (
                index + 1 == len(tokens) or tokens[index + 1].type == tokenize.NAME):
            return body[:token.start[1]].rstrip(), body[token.end[1]:].strip()
    return body, None


def _field_items(text):
    """[(name, expression)] of `name=expression name=expression`; ValueError says what is wrong.
    An expression runs to the next top-level `name=`; `==` and keyword arguments inside calls stay in it."""
    tokens, depth, starts = _tokens(text), 0, []
    for index, token in enumerate(tokens):
        if token.type == tokenize.OP and token.string in ('(', '[', '{'):
            depth += 1
        elif token.type == tokenize.OP and token.string in (')', ']', '}'):
            depth -= 1
        elif depth == 0 and token.type == tokenize.NAME and index + 1 < len(tokens) \
                and tokens[index + 1].type == tokenize.OP and tokens[index + 1].string == '=':
            starts.append(index)
    if not starts or starts[0] != 0:
        raise ValueError('fields must be followed by name=expression' + (f', {text!r} is not' if text else ''))
    items = []
    for position, index in enumerate(starts):
        name = tokens[index].string
        end = tokens[starts[position + 1]].start[1] if position + 1 < len(starts) else len(text)
        expression = text[tokens[index + 1].end[1]:end].strip()
        if keyword.iskeyword(name):
            raise ValueError(f'field name {name} is a Python keyword')
        if not expression:
            raise ValueError(f'field {name} has no expression')
        try:
            ast.parse(expression, mode='eval')
        except SyntaxError as error:
            raise ValueError(f'field {name} expression {expression} is not a Python expression ({error.msg})') from None
        items.append((name, expression))
    names = [name for name, _ in items]
    if len(set(names)) != len(names):
        raise ValueError('duplicate field names: ' + ', '.join(sorted({name for name in names if names.count(name) > 1})))
    return tuple(items)


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
    enum_names, annotation = _enum_names(tree), _source_types(tree)
    lines = text.splitlines()
    def issue(level, code, message, line, name=''):
        return Issue(level, code, message, file, line, name)
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        match = _HEAD.fullmatch(token.string) if token.type == tokenize.COMMENT else None
        if not match:
            continue
        kind, body = match.groups()
        line, column = token.start
        try:
            kind, body, reference, scoped = _agreement(kind, body)
        except ValueError as error:
            problems.append(issue('red', 'syntax', str(error), line))
            continue
        calibration = re.search(r'\s+calibrated_by=(\S+)(?=\s+fields\s|\s*$)', body)
        calibrated_by = calibration[1] if calibration else ''
        body = body[:calibration.start()] + body[calibration.end():] if calibration else body
        local = []
        is_owner = kind == 'owner' or reference
        try:
            body, field_text = _split_fields(body)
            fields = _field_items(field_text) if field_text is not None else ()
        except (ValueError, tokenize.TokenError) as error:
            # A wrong anchor is red at its own line, with the way to write it.
            reason = (f'invalid anchor: unmatched parentheses or quotes ({error.args[0]})' if isinstance(error, tokenize.TokenError)
                      else f'invalid fields: {error}')
            problems.append(issue('red', 'syntax', f'{file}:{line} {reason}' + ('' if isinstance(error, tokenize.TokenError)
                                  else '. ' + FIELDS_HELP), line))
            continue
        if fields and kind in ('states', 'event'):
            problems.append(issue('red', 'syntax', f'{file}:{line} fields apply only to sensor and function owner anchors. {FIELDS_HELP}', line))
            continue
        if kind == 'owner':
            data_owner = _data_owner(body, file, module, line, is_test, scoped=scoped)
            if data_owner is not None and fields:
                problems.append(issue('red', 'syntax', f'{file}:{line} data owners cannot have fields; fields apply only to decision functions. {FIELDS_HELP}', line))
                continue
            if data_owner is not None:
                (entries if isinstance(data_owner, dict) else problems).append(data_owner)
                continue
            kind = 'sensor'          # A function owner is the reference copy of its same-name sensors.
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
            # The values written to the field are checked by value_gate, over all of its writes.
            entry = Anchor(kind, name, file, module, name, line, field_nodes[0].lineno if field_nodes else 0,
                           values=tuple(values), calibrated_by=calibrated_by, issues=tuple(local),
                           source_digest=source_digest, source_role='test' if is_test else 'production')
        else:
            parsed = re.fullmatch(r'(' + _NAME + r')(?:\s*\((.*)\))?(?:\s*->\s*(?:(' + _NAME + r')\s*:\s*(.+)|(' + _PROJECTION + r')))?\s*', body)
            if not parsed or kind == 'event' and (parsed[3] or parsed[5]) or parsed[5] and not _projection_path(parsed[5]):
                problems.append(issue('red', 'syntax', f'invalid {"owner" if is_owner else kind} anchor syntax', line))
                continue
            name, raw, output_name, output_type, projection = parsed.groups()
            candidates = []
            for qual, (node, cls) in definitions.items():
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                first = min([node.lineno] + [d.lineno for d in node.decorator_list if d.lineno > line])
                if first > line and len(lines[first - 1]) - len(lines[first - 1].lstrip()) == column and \
                        all(not s.strip() or s.lstrip().startswith('#') for s in lines[line:first - 1]):
                    candidates.append((qual, node, cls))
            qual, node, cls = min(candidates, key=lambda x: x[1].lineno) if candidates else ('', None, '')
            declared, context, aliases = [], [], {}
            try:
                sides = _parts(raw, ';') if raw is not None else []
                if len(sides) > 2:
                    raise ValueError('anchor has more than one context separator')
                for part in _parts(sides[0]) if sides else ():
                    item = re.fullmatch(r'([^\W\d]\w*)(?:\s*=\s*([^\W\d]\w*))?(?:\s*:\s*(.+))?', part)
                    if item is None:
                        raise ValueError(f'invalid parameter: {part}')
                    declared.append((item[1], item[3]))
                    if item[2] and item[2] != item[1]:
                        aliases[item[2]] = item[1]
                context = _parts(sides[1]) if len(sides) == 2 else []
                if any(not item.isidentifier() for item in context):
                    raise ValueError('context parameters need names')
            except (ValueError, tokenize.TokenError) as error:
                local.append(issue('red', 'syntax', str(error), line, name))
            names = [p[0] for p in declared] + context
            source_of = {value: key for key, value in aliases.items()}       # declared name -> source parameter
            spelled = [source_of.get(item, item) for item in names]          # the source spelling of each parameter
            if len(set(names)) != len(names) or len(set(spelled)) != len(spelled):
                local.append(issue('red', 'signature', 'anchor parameters repeat', line, name))
            names, canonical = spelled, source_of
            actual, receiver, return_type = {}, '', '?'
            if node is None:
                local.append(issue('red', 'target-missing', 'anchor has no following function in source', line, name))
            else:
                args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if cls and args and args[0].arg in ('self', 'cls'):
                    receiver = args.pop(0).arg
                actual = {a.arg: annotation(a.annotation) for a in args}
                if raw is not None and (len(names) != len(actual) or set(names) != set(actual)):
                    local.append(issue('red', 'signature', f'anchor parameters {_inline(names)} != source {_inline(list(actual))}', line, name))
                if node.args.vararg or node.args.kwarg:
                    local.append(issue('grey', 'variadic', 'variadic parameters require a calibrated test', line, name))
                return_type = annotation(node.returns) if node.returns is not None else _return_type(node, actual)
            meanings = {canonical.get(key, key): value for key, value in declared} if raw is not None else {key: None for key in actual}
            params = []
            if aliases and calibrated_by:
                local.append(issue('grey', 'parameter-map', 'a parameter mapping needs a directly observed sensor, not a calibration test', line, name))
            for parameter in sorted(dict.fromkeys([*meanings, *context]), key=lambda p: list(actual).index(p) if p in actual else len(actual)):
                source_type, meaning = actual.get(parameter, '?'), meanings.get(parameter)
                role = 'context' if parameter in context or len(sides) < 2 and _parameter_role(source_type, enum_names) == 'context' else 'input'
                if source_type == '?' and raw is not None and role == 'input':
                    local.append(issue('grey', 'type-missing', f'parameter {parameter} has no source type', line, name))
                if kind == 'sensor':
                    if meaning == '?':
                        local.append(issue('grey', 'unit-missing', f'parameter {parameter} needs its unit confirmed', line, name))
                    if meaning is not None and _unit(source_type) and _unit(source_type) != meaning:
                        local.append(issue('red', 'unit', f'parameter {parameter} unit {_inline(meaning)} != source {_inline(_unit(source_type))}', line, name))
                elif meaning is not None and meaning != '?' and _type_id(meaning) != _type_id(source_type) and source_type != '?':
                    local.append(issue('red', 'type', f'parameter {parameter} type {_inline(meaning)} != source {_inline(source_type)}', line, name))
                params.append(Parameter(aliases.get(parameter, parameter), (meaning if meaning is not None else _unit(source_type)) if kind == 'sensor' else '',
                                        source_type, role, len(sides) < 2, parameter if parameter in aliases else ''))
            taken = set(actual) | {p.name for p in params} | ({receiver} if receiver else set())
            for field_name, _ in fields:
                if field_name in taken:
                    local.append(issue('red', 'syntax', f'{file}:{line} field {field_name} matches a parameter: parameters are already rule fields, '
                                       f'do not repeat them in fields. {FIELDS_HELP}', line, name))
            output_name = output_name or ''
            output_type = output_type or (return_type if kind == 'sensor' and not projection else '')
            if kind == 'sensor' and not projection:
                if output_type == '?' or return_type == '?':
                    local.append(issue('grey', 'return-missing', 'return type cannot be checked from source', line, name))
                elif _type_id(output_type) != _type_id(return_type):
                    local.append(issue('red', 'return', f'anchor return type {_inline(output_type)} != source {_inline(return_type)}', line, name))
            entry = Anchor(kind, name, file, module, qual, line, node.lineno if node else 0,
                           tuple(params), output_name, output_type, calibrated_by=calibrated_by,
                           issues=tuple(local), source_digest=source_digest, receiver=receiver,
                           source_role='test' if is_test else 'production', owner=is_owner,
                           projection=projection or '', fields=fields)
        entries.append(asdict(entry))
    return {'anchors': entries, 'anchor_issues': [asdict(p) for p in problems]} if entries or problems else {}


_DATA_OWNER = re.compile(r'(?P<name>' + _NAME + r')(?:\s+writers=(?P<writers>\S+))?(?:\s+with=(?P<with>\S+))?'
                         r'(?:\s+on=(?P<on>\S+))?(?:\s+alone=(?P<alone>(?:[^\s(),]+\([^()]*\),?)+))?\s*')


def _data_owner(body, file, module, line, is_test, *, scoped=False):
    """`Table.column writers=f,... with=Model.field[=value],... on=update alone=f(reason),...` as an owner
    anchor (a dict), a syntax Issue, or None for a function owner (a bare name above a function)."""
    listed = _DATA_OWNER.fullmatch(body.strip())
    if listed and not scoped and listed['alone'] and not re.fullmatch(r'(?:[\w.:]+\([^()]*\),?)+', listed['alone']):
        listed = None                 # Keep the old spelling's accepted grammar and bindings.
    if listed and not (listed['writers'] or listed['with'] or listed['alone'] or listed['on']):
        return None
    writers = tuple(dict.fromkeys(part for part in (listed['writers'] or '').split(',') if part)) if listed else ()
    pairs = tuple(dict.fromkeys(part for part in (listed['with'] or '').split(',') if part)) if listed else ()
    alone = tuple(re.findall(r'[^\s(),]+\([^()]*\)', listed['alone'] or '')) if listed else ()
    on = (listed['on'] or '') if listed else ''
    # an on= the line spells (also one after alone=, which the form does not read) gets the on= form
    if on not in ('', 'update', 'create') or on and not pairs or not listed and re.search(r'(?:^|\s)on=', body):
        return Issue('red', 'syntax', 'on= is update or create and limits with=: owner Model.field with=Other.field on=update '
                     '(alone=function(reason) after it)', file, line)
    if not listed or '.' not in listed['name'].strip('.') or not (writers or pairs) \
            or any('.' not in pair.partition('=')[0].strip('.') for pair in pairs) or alone and not pairs:
        return Issue('red', 'syntax', 'a data owner needs Table.column (or Model.field) with writers=function,... '
                     'and/or with=Model.field[=value],...; alone=function(reason) needs with=', file, line)
    if scoped:
        try:
            writers = tuple(_position(value, file, module) for value in writers)
            exceptions = []
            for value in alone:
                target, _, reason = value.partition('(')
                if ':' not in target:
                    raise ValueError('except needs a repository-relative path:function(reason)')
                exceptions.append(_position(target, file, module) + '(' + reason)
            alone = tuple(exceptions)
        except ValueError as error:
            return Issue('red', 'syntax', str(error), file, line)
    return asdict(Anchor('owner', listed['name'], file, module, '', line, line, writers=writers, pairs=pairs, alone=alone,
                         on=on, source_role='test' if is_test else 'production'))


def foreign_owners(text, module, file, *, is_test=False, functions=()):
    """`// flowguard: owner Table.column writers=fn,... with=... alone=...` (and a bare `owner NAME`) in a
    JS/TS source. Foreign code does not run here: a data owner checks static writes; a function owner is
    navigation. `// flowguard: sensor NAME` names the function declared on the next lines (`functions` are
    the reader's node rows); the vitest adapter observes it, and same-name sensors are copies."""
    entries, problems = [], []
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        found = _FOREIGN_HEAD.search(line)
        if not found:
            continue
        spelling, body = found.groups()
        if spelling in ('sensor', 'same') and not re.match(r'\s*//', line):
            continue
        try:
            kind, body, reference, scoped = _agreement(spelling, body)
        except ValueError as error:
            problems.append(asdict(Issue('red', 'syntax', str(error), file, number)))
            continue
        if kind == 'sensor':
            name = body.strip()
            following = [row for row in functions if row.get('kind') in ('function', 'method')
                         and number < row['line'] <= number + 3 and not row['qual'].rpartition('.')[2].startswith('<anonymous')]
            if not re.fullmatch(_NAME, name):
                problems.append(asdict(Issue('red', 'syntax', f'{file}:{number}: sensor needs one NAME: // flowguard: sensor NAME',
                                             file, number)))
            elif not following:
                problems.append(asdict(Issue('red', 'syntax', f'{file}:{number}: sensor {name} needs a function declared on the next line',
                                             file, number, name)))
            else:
                target = min(following, key=lambda row: row['line'])
                params = tuple(Parameter(value, '', '', 'input', True) for value in target.get('raw', {}).get('parameters', ()))
                entries.append(asdict(Anchor('sensor', name, file, module, target['qual'], number, target['line'], params,
                                             source_role='test' if is_test else 'production', owner=reference)))
            continue
        owner = _data_owner(body, file, module, number, is_test, scoped=scoped)
        if owner is None and re.fullmatch(_NAME + r'\s*', body):
            owner = asdict(Anchor('owner', body.strip(), file, module, '', number, number,
                                  source_role='test' if is_test else 'production'))
        elif owner is None:
            owner = Issue('red', 'syntax', 'owner needs NAME, or Table.column writers=function,...', file, number)
        (entries if isinstance(owner, dict) else problems).append(owner if isinstance(owner, dict) else asdict(owner))
    return {'anchors': entries, 'anchor_issues': problems} if entries or problems else {}


def _anchor(data):
    data = dict(data)
    data['parameters'] = tuple(Parameter(**p) for p in data.get('parameters', ()))
    data['issues'] = tuple(Issue(**p) for p in data.get('issues', ()))
    data['values'] = tuple(data.get('values', ()))
    data['writers'] = tuple(data.get('writers', ()))
    data['pairs'] = tuple(data.get('pairs', ()))
    data['alone'] = tuple(data.get('alone', ()))
    data['fields'] = tuple(tuple(item) for item in data.get('fields', ()))
    return Anchor(**data)


def _projection_path(text):
    """The fixed read steps of `result[0]`, `result['ok']` or `result.ok.value`; None for anything else."""
    try:
        node = ast.parse(text, mode='eval').body
    except SyntaxError:
        return None
    steps = []
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        if isinstance(node, ast.Attribute):
            steps.append(('attr', node.attr))
        elif isinstance(node.slice, ast.Constant) and type(node.slice.value) in (int, str):
            steps.append(('item', node.slice.value))
        else:
            return None
        node = node.value
    return tuple(reversed(steps)) if isinstance(node, ast.Name) and node.id == 'result' and steps else None


def project(anchor, value):
    """The part of an actual result a projected sensor compares; a raised outcome stays raised."""
    if not anchor.projection or isinstance(value, cells.Raised):
        return value
    for kind, key in _projection_path(anchor.projection):
        if kind == 'attr':
            if isinstance(value, (dict, list, tuple)) or inspect.getattr_static(value, key, _NO_VALUE) is _NO_VALUE:
                raise ValueError(f'{anchor.projection}: the result has no attribute {key}')
            value = getattr(value, key)
        else:
            if type(value) not in (tuple, list, dict) or type(value) is dict and key not in value or \
                    type(value) is not dict and not (type(key) is int and -len(value) <= key < len(value)):
                raise ValueError(f'{anchor.projection}: the result has no item {key!r}')
            value = value[key]
    return value


_NO_VALUE = object()


def _data_agreements(entries):
    """Combine only one writer declaration and one complementary pair declaration."""
    groups = {}
    for number, anchor in enumerate(entries):
        if anchor.kind == 'owner':
            groups.setdefault(anchor.name, []).append((number, anchor))
    combined, omitted = {}, set()
    for group in groups.values():
        if len(group) != 2:
            continue
        writers = [(number, anchor) for number, anchor in group
                   if anchor.writers and not (anchor.pairs or anchor.on or anchor.alone)]
        pairs = [(number, anchor) for number, anchor in group if anchor.pairs and not anchor.writers]
        if len(writers) != 1 or len(pairs) != 1:
            continue
        writer_number, writer = writers[0]
        pair_number, pair = pairs[0]
        if (writer.file, writer.module, writer.source_role, writer.source_digest) != \
                (pair.file, pair.module, pair.source_role, pair.source_digest):
            continue
        if any(anchor.owner or anchor.qual or anchor.parameters or anchor.values or anchor.fields or anchor.issues
               or anchor.output or anchor.output_type or anchor.calibrated_by or anchor.receiver
               for anchor in (writer, pair)):
            continue
        first, second = sorted((writer_number, pair_number))
        combined[first] = replace(pair, writers=writer.writers)
        omitted.add(second)
    return tuple(combined.get(number, anchor) for number, anchor in enumerate(entries) if number not in omitted)


def _index(entries, problems):
    index = Index(_data_agreements(tuple(entries)))
    for name, group in index.by_name.items():
        # Omitted labels/units are unknown metadata, not conflicting declarations.
        roles = {(a.kind, a.values) for a in group}
        inputs = [(set(p.name for p in a.inputs if not (p.inferred and p.source_type == '?')),
                   set(p.name for p in a.inputs)) for a in group]
        types = [{_type_id(value) for value in values if value not in ('', '?')} for values in
                 [[a.output_type for a in group], *[[p.source_type for a in group for p in a.inputs if p.name == name]
                   for name in {p.name for a in group for p in a.inputs}]]]
        labels = [{a.output for a in group if a.output}, *[{p.unit for a in group for p in a.inputs if p.name == name and p.unit not in ('', '?')}
                  for name in {p.name for a in group for p in a.inputs}]]
        if len(roles) > 1 or any(required - allowed for required, _ in inputs for _, allowed in inputs) or any(len(values) > 1 for values in types + labels):
            reference = next((a for a in group if a.owner), group[0])
            wanted = [p.name for p in reference.inputs]
            for anchor in group:
                own = [p.name for p in anchor.inputs]
                hint = ''
                if len(roles) == 1 and anchor is not reference and own != wanted and len(own) == len(wanted):
                    # Parameters correspond only by name; the mapping is written, never guessed from position or type.
                    hint = (f'; parameters correspond only by name: write # flowguard: same {name}('
                            + ', '.join(f'{p}=<its parameter>' for p in wanted) + ') on this copy')
                problems.append(Issue('red', 'identity', f'same anchor {name} has conflicting roles, units or signature' + hint, anchor.file, anchor.line, name))
        owners = [anchor for anchor in group if anchor.owner or anchor.kind == 'owner']
        if len(owners) > 1:
            data_only = all(anchor.kind == 'owner' and not anchor.qual and (anchor.writers or anchor.pairs)
                            for anchor in owners)
            for anchor in owners:
                places = ', '.join(f'{a.file}:{a.line}' for a in owners)
                message = (f'{name} has repeated or incompatible data agreements ({places}): '
                           'use one writers declaration and one together declaration in the same file; '
                           'multiple together declarations or different on= scopes cannot share one registration') if data_only else \
                    (f'{name} has {len(owners)} references ({places}): '
                     'keep one reference; mark the copies # flowguard: same ' + name)
                problems.append(Issue('red', 'owner', message, anchor.file, anchor.line, name))
    index.issues = tuple(problems)
    return index


def collect(graph):
    """Read the single stored source index, including anchored project tests."""
    entries, problems, field_types = [], [], []
    files = list(graph.con.execute('SELECT path, sha, module FROM file'))
    shas = {file: sha for file, sha, module in files}
    modules = {file: module for file, sha, module in files}
    positions = _agreement_positions(graph, modules)
    notices = set()
    # Only the kinds the index reads; assignments only when a declared set needs the value gate.
    for file, error, data in graph._kinds('anchors', 'anchor_issues', 'field_types'):
        if error and file.endswith('.py'):
            problems.append(Issue('grey', 'source-syntax', error, file))
        lines = read_source(graph.root / file).splitlines() if data.get('anchors') or data.get('anchor_issues') else []
        for value in data.get('anchors', ()):
            anchor = _anchor(dict(value, source_digest=shas[file]))
            spelling = _spelling_at(lines, anchor.line, file)
            _old_spellings(spelling, notices)
            if spelling is not None:
                anchor = _indexed_agreement(anchor, spelling[1], modules, positions)
            entries.append(anchor)
            problems.extend(anchor.issues)
        for value in data.get('anchor_issues', ()):
            _old_spellings(_spelling_at(lines, value['line'], file), notices)
        problems.extend(Issue(**value) for value in data.get('anchor_issues', ()))
        field_types.extend(data.get('field_types', ()))
    classes = dict(graph.con.execute("SELECT id, sig FROM node WHERE kind='class'"))
    table = declared_sets(entries, field_types, classes, graph._value_env)
    if table:      # one value gate over the assignment facts of the files that assign a declared field
        problems.extend(value_gate(table, [graph._folded(row) for row in graph.assignments_to(table)
                                           if row['field'] in table]))
    _warn_spellings(notices)
    return _index(entries, problems)


_ENUM_BASES = {'Enum', 'StrEnum', 'IntEnum', 'Flag', 'IntFlag'}


def declared_sets(entries, field_types=(), classes=None, constants=None, foreign=()):
    """The one table of declared value sets the value gate reads, keyed `module:Class.field`: each
    `# flowguard: states` anchor, and each class field annotated with an enum (`status: RunStatus`),
    whose members' folded values are its set. `classes` gives a class id's signature (its bases);
    `constants(module)` the module's folded constants. `foreign` adds the rows other languages declare
    (`MapHandle.value_sets()`), keyed by their `field` (`Model.field`, `ts:Type.field`); a second set of one
    field (a Prisma enum and a SQL CHECK) is kept in `also`, and a value must be in each. A foreign set keeps
    its `kind`, `guessed`, `files`, `place`, `scope` (the schemas or files whose writes it alone judges) and
    `excluded_packages` (the packages whose writes it does not judge)."""
    from ..structure import decide
    table = {}
    for anchor in entries:
        if anchor.kind == 'states':
            table[anchor.module + ':' + anchor.name] = dict(name=anchor.name, values=tuple(anchor.values),
                                                            where=f'states {anchor.file}:{anchor.line}')
    for row in field_types:
        bases = decide.class_bases((classes or {}).get(row['type']) or '')
        if not {base.rpartition('.')[2] for base in bases} & _ENUM_BASES or constants is None:
            continue
        module, _, cls = row['type'].partition(':')
        values = tuple(folded[1] for key, folded in constants(module).items() if key.startswith(cls + '.')
                       and '.' not in key[len(cls) + 1:] and folded and folded[0] in ('str', 'num'))
        if values:
            table.setdefault(row['field'], dict(name=row['field'].partition(':')[2],
                                                values=values + ((None,) if row.get('optional') else ()),
                                                where=f'enum {row["type"]} ({row["file"]}:{row["line"]})'))
    for row in foreign:             # MapHandle.value_sets(): Prisma enums, SQL CHECK sets, JS/TS annotated members
        declared = dict(name=row['name'], values=tuple(row['values']), where=row['where'], fold=row['fold'],
                        file=row['file'], files=row['files'], kind=row['kind'], guessed=row['guessed'], place=row['place'],
                        scope=row['scope'], excluded_packages=row['excluded_packages'])
        key = row.get('field', row['key'])
        if key in table:
            table[key].setdefault('also', []).append(declared)
        else:
            table[key] = declared
    return table


def outside_sets(table, writes):
    """(write, declared set, value) for every readable value written to a declared field that its set (or
    one of its sets) does not hold. A write whose value cannot be read (a parameter, a call) is not judged;
    a set with `fold` compares text without case (the database's collation does); a set does not judge the
    writes of a package (the write's `package`) in its `excluded_packages`, and a set with a `scope` judges
    only the writes whose `scope` (the schema or declaring file the write is resolved to) is in it."""
    for row in writes:
        first = table.get(row.get('gate', row['field']))       # a write's `gate` key, when its field name is not it
        values = row.get('values') or ([row['value']] if row.get('literal') else None)
        if first is None or values is None:
            continue
        for declared in (first, *first.get('also', ())):
            if declared.get('excluded_packages') and row['package'] in declared['excluded_packages']:
                continue
            if declared.get('scope') and row['scope'] not in declared['scope']:
                continue
            for value in values:
                if declared.get('fold') and isinstance(value, str):
                    held = any(isinstance(allowed, str) and allowed.casefold() == value.casefold() for allowed in declared['values'])
                else:
                    held = any(type(value) is type(allowed) and value == allowed for allowed in declared['values'])
                if not held:
                    yield row, declared, value


def value_gate(table, writes):
    """Every value written to a declared field must be in its declared set (red otherwise)."""
    issues = []
    for row, declared, value in outside_sets(table, writes):
        issues.append(Issue('red', 'states-values',
                            f'code writes {declared["name"]}={value!r}; allowed: '
                            + ' | '.join(map(repr, declared['values'])) + f' ({row["file"]}:{row["line"]})'
                            f' -> write a declared value; to add one, change the declaration first ({declared["where"]})',
                            row['file'], row['line'], declared['name']))
    return issues


def collect_sources(root, files_with_modules):
    """Same facts/index for a historical source slice, without a second full map.

    Entries are (relative_file, module[, is_test]); source identity uses the same
    reader digest as the map. No project module is imported.
    """
    root = Path(root)
    files_with_modules = tuple(files_with_modules)
    modules = {item[0]: item[1] for item in files_with_modules}
    entries, problems = [], []
    notices = set()
    for item in files_with_modules:
        file, module, *role = item
        raw = (root / file).read_bytes()
        text = read_source(root / file, data=raw)
        try:
            tree = ast.parse(text, str(root / file))
        except SyntaxError as error:
            # An unparsable file is unknown, not a verdict: only this file stays grey.
            problems.append(Issue('grey', 'source-syntax', str(error), file, error.lineno or 0))
            continue
        data = source_facts(tree, text, module, file, source_digest=content_digest(root / file, data=raw), is_test=bool(role and role[0]))
        for value in data.get('anchors', ()):
            anchor = _anchor(value)
            spelling = _spelling_at(text.splitlines(), anchor.line, file)
            _old_spellings(spelling, notices)
            if spelling is not None:
                anchor = _indexed_agreement(anchor, spelling[1], modules)
            entries.append(anchor)
            problems.extend(anchor.issues)
        for value in data.get('anchor_issues', ()):
            _old_spellings(_spelling_at(text.splitlines(), value['line'], file), notices)
        problems.extend(Issue(**value) for value in data.get('anchor_issues', ()))
        if any(value['kind'] == 'states' for value in data.get('anchors', ())):
            problems.extend(_slice_gate(root, file, module, raw, [_anchor(value) for value in data['anchors']]))
    _warn_spellings(notices)
    return _index(entries, problems)


def _slice_gate(root, file, module, raw, entries):
    """The value gate on one file of a source slice, with that file's own constants (no map)."""
    from ..structure import decide
    from ..structure.api import _fold_values
    from ..structure.extract import extract
    facts = extract(root, file, raw, module, False)
    env = decide.own_env([(node['qual'], node['sig']) for node in facts['nodes'] if node['kind'] == 'const'])
    classes = {module + ':' + node['qual']: node['sig'] for node in facts['nodes'] if node['kind'] == 'class'}
    writes = []
    for row in facts.get('assignments', ()):
        values = _fold_values(row['expr'], env) if row.get('expr') else None
        writes.append(dict(row, values=values) if values else row)
    return value_gate(declared_sets(entries, facts.get('field_types', ()), classes, lambda name: env if name == module else {}), writes)


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
    """Fold literals and known stdlib value constructors, never project imports."""
    result = {}
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.pop(statement.name, None)
        elif isinstance(statement, ast.ImportFrom):
            allowed = _TYPE_IMPORTS.get(statement.module, ())
            for alias in statement.names:
                target = alias.asname or alias.name
                result.pop(target, None)
                if alias.name in allowed and alias.name in _TYPES:
                    result[target] = _TYPES[alias.name]
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            previous = dict(result)
            for target in targets:
                if isinstance(target, ast.Name):
                    result.pop(target.id, None)
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, SyntaxError):
                call = statement.value
                constructor = previous.get(call.func.id) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) else None
                if constructor not in (Decimal, date, datetime, timedelta):
                    continue
                try:
                    value = constructor(*(ast.literal_eval(v) for v in call.args), **{k.arg: ast.literal_eval(k.value) for k in call.keywords})
                except (ValueError, TypeError, SyntaxError, ArithmeticError):
                    continue
            for target in targets:
                if isinstance(target, ast.Name):
                    result[target.id] = value
    return result


def _read_decision(function, parameters, env, file, line, name, initial=()):
    kinds, issues = {}, list(initial)
    for parameter in parameters:
        if parameter.role == 'context':
            continue
        try:
            kind = parameter_kind(parameter)
            if kind is None:
                raise ValueError('None alone has no varying domain')
            kinds[parameter.name] = kind
        except (SyntaxError, ValueError, TypeError, AttributeError) as error:
            issues.append(Issue('grey', 'range-missing', f'{parameter.name}: {error}', file, line, name))
    reading = cells.read_predicate(types.SimpleNamespace(__globals__=env), kinds, node=function)
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
    initial = anchor.issues
    if any(parameter.alias for parameter in anchor.parameters):
        function, problem = _declared_names(function, anchor.parameters)
        initial += (Issue('grey', 'parameter-map', problem, anchor.file, anchor.line, anchor.name),) if problem else ()
    kinds, reading, issues = _read_decision(function, anchor.parameters, env, anchor.file, anchor.line, anchor.name, initial)
    from ..structure.extract import fingerprint
    definitions, dependencies, seen, complete = _definitions(tree), {}, set(), True
    pure = _pure_bindings(tree)
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
                if not (_immutable(env[name]) or any(env[name] is constructor for constructor in (Decimal, date, datetime, timedelta))):
                    complete = False
            elif name in definitions and isinstance(definitions[name][0], ast.FunctionDef):
                dependency(definitions[name][0], name)
            elif name not in _TYPES and name not in _PURE_BUILTINS | _ERRORS | pure:
                complete = False
    dependency(function, anchor.qual)
    return DecisionReading(kinds, reading, tuple(issues), function, env,
                           fingerprint(function, function.name), dependencies, complete)


def _declared_names(function, parameters):
    """A copy of the function read under its declared parameter names (days for overdue_days), never run."""
    import copy
    renamed = {p.alias: p.name for p in parameters if p.alias}
    taken = {n.id for n in ast.walk(function) if isinstance(n, ast.Name)} | {a.arg for a in ast.walk(function) if isinstance(a, ast.arg)}
    clash = sorted((set(renamed.values()) & taken) - set(renamed))
    if clash:
        return function, 'parameter mapping cannot be read: the copy already uses ' + ', '.join(clash)
    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id=renamed.get(node.id, node.id), ctx=node.ctx), node)
        def visit_arg(self, node):
            node.arg = renamed.get(node.arg, node.arg)
            return node
    return Rename().visit(copy.deepcopy(function)), ''


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
    annotation, enum_names = _source_types(tree), _enum_names(tree)
    parameters = tuple(Parameter(a.arg, _unit(annotation(a.annotation)), annotation(a.annotation), _parameter_role(annotation(a.annotation), enum_names), True) for a in args)
    kinds, reading, issues = _read_decision(function, parameters, _literal_globals(tree), file, function.lineno, qual)
    ranges = {}
    if kinds:
        space = cells.build_space(kinds, reading.consts, reading.planes, reading.links, reading.reasons, reading.hints)
        rows = [row for row in space.cells if all(k.name != 'enum' or row[n] in k.literals for n, k in kinds.items())]
        ranges = {'points': {n: [v for v in values if kinds[n].name != 'enum' or v in kinds[n].literals]
                             for n, values in space.pts.items()},
                  'cells': rows, 'complete': space.complete and not issues,
                  'reasons': list(space.reasons), 'total': len(rows),
                  'inputs': [p.name for p in parameters if p.role == 'input'],
                  'context': [p.name for p in parameters if p.role == 'context']}
        issues.extend(Issue('grey', 'range-incomplete', reason, file, function.lineno) for reason in space.reasons
                      if not any(i.code == 'range-incomplete' and i.message == reason for i in issues))
    name = qual.replace('.', '_')
    comment = f'# flowguard: same {name}'
    if any(p.unit for p in parameters):
        inputs = ', '.join(p.name + (': ' + p.unit if p.unit else '') for p in parameters if p.role == 'input')
        context = ', '.join(p.name for p in parameters if p.role == 'context')
        comment += '(' + inputs + ('; ' + context if context else '') + ')'
    return Draft(comment, ranges, tuple(issues))


@contextmanager
def _execution_session(root, facts=None):
    """Only the verified execution worker/pytest integration opens this session. `facts` keeps what its
    observations read about a source anchor (a pytest session passes one record for all its items)."""
    token = _SESSION.set(Path(root).resolve())
    facts_token = _SESSION_FACTS.set({} if facts is None else facts)
    try:
        # The backend owns calibration facts in the same worker lifetime.
        from .calibration import _execution_session as backend_session
        with backend_session(root):
            yield
    finally:
        _SESSION_FACTS.reset(facts_token)
        _SESSION.reset(token)


def _session_fact(key, compute):
    """compute() once per verified session for `key`; outside a session (no record) every call computes."""
    facts = _SESSION_FACTS.get()
    if facts is None:
        return compute()
    if key not in facts:
        facts[key] = compute()
    return facts[key]


def observe(root, anchor, values):
    """One entry: verified session preserves real mutant/probe function objects."""
    if _SESSION.get() == Path(root).resolve():
        return _observe_current(root, anchor, values)
    from .calibration import execute
    return execute(root, anchor, values)


def _observe_current(root, anchor, values):
    if _SESSION.get() != Path(root).resolve():
        raise RuntimeError('project observation requires the verified execution session')
    # Worker and in-process verification use this one boundary. Synthetic
    # sensor calls must not become coverage of an ordinary project test.
    from .flow import _without_ordinary_observers
    with _without_ordinary_observers():
        return _observe_verified(root, anchor, values)


def _observe_verified(root, anchor, values):
    if anchor.issues:
        return Observation(anchor.status, reasons=tuple(i.message for i in anchor.issues), anchor=anchor.target)
    if anchor.kind == 'states':
        return Observation('grey', reasons=('state fields are read by their existing project lifecycle check',), anchor=anchor.target)
    try:
        # The digest is checked on every call; the parse and the comment check once per session and digest.
        digest = content_digest(Path(root) / anchor.file)
        path, tree, function = _session_fact(('source', str(root), anchor, digest), lambda: _source(root, anchor))
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
            kind = _kind(parameter.source_type)  # point container shapes are not a pure finite input proof
            value = values[parameter.name]
            # A float parameter's representative values include NaN and the infinities.
            accepted = _accepts(parameter.source_type, value) or kind is not None and kind.name == 'float' \
                and type(value) is float and not math.isfinite(value)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return Observation('grey', reasons=(f'{parameter.name}: simple source type is not known',), anchor=anchor.target)
        if not accepted:
            return Observation('red', reasons=(f'{parameter.name}: input does not have source type {parameter.source_type}',), anchor=anchor.target)
    from .config import load_config, search_paths, setup_path
    from .imports import prepare
    cfg = _session_fact(('config', str(root)), lambda: load_config(root))
    setup_path(cfg, _session_fact(('search paths', str(root)), lambda: search_paths(cfg)))
    try:
        # The same anchor source, import path and loaded standard modules give the same reasons.
        loaded = tuple((name, getattr(sys.modules.get(name), '__file__', None),
                        getattr(getattr(sys.modules.get(name), '__spec__', None), 'origin', None))
                       for name in sorted(_PURE_MODULES | _TYPE_IMPORTS.keys()))
        reasons = list(_session_fact(('imports', anchor, digest, tuple(sys.path), loaded),
                                     lambda: tuple(_import_reasons(cfg, anchor, tree, function))))
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
    values = {parameter.source: values[parameter.name] for parameter in anchor.parameters}
    positional = [values[a.arg] for a in function.args.posonlyargs]
    kwargs = {name: value for name, value in values.items() if name not in {a.arg for a in function.args.posonlyargs}}
    from .runtime import Runtime
    runtime = Runtime(root, previous={})
    bound = inspect.signature(fn, follow_wrapped=False).bind(*positional, **kwargs)
    problem = runtime.safety(fn, bound.arguments)
    if problem:
        return Observation('grey', reasons=(problem,), anchor=anchor.target)
    value, refused = runtime.guarded(fn, bound, current=True)
    if refused:
        return Observation('grey', reasons=(refused,), anchor=anchor.target)
    if isinstance(value, cells.Raised) and isinstance(value.error, ImportError):
        # An import inside the function failed in this observation's environment: not its behaviour.
        return Observation('grey', reasons=(f'unavailable: import failed during observation: {type(value.error).__name__}: {value.error}',), anchor=anchor.target)
    if isinstance(value, cells.Raised):
        return Observation('ok', value=value, anchor=anchor.target)
    if anchor.projection:
        try:
            return Observation('ok', value=project(anchor, value), anchor=anchor.target)
        except ValueError as error:
            return Observation('grey', reasons=(str(error),), anchor=anchor.target)
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
    return type(value) in (str, bool, int, float, Decimal, date, datetime, timedelta, type(None)) or type(value) is tuple and all(_immutable(x) for x in value)


_PURE_BUILTINS = {'abs', 'min', 'max', 'round', 'len', 'int', 'float', 'str', 'bool'}
_PURE_MODULES = {'math'}     # standard modules of pure functions: importing them initializes nothing of the project


def _pure_bindings(tree):
    """Module names and functions bound by `import math` / `from math import floor` at module level."""
    names = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            names.update(a.asname or a.name for a in statement.names if a.name in _PURE_MODULES)
        elif isinstance(statement, ast.ImportFrom) and not statement.level and statement.module in _PURE_MODULES:
            names.update(a.asname or a.name for a in statement.names if a.name != '*')
    return names
_ERRORS = {'ValueError', 'TypeError', 'ZeroDivisionError', 'OverflowError', 'AssertionError', 'RuntimeError', 'KeyError'}
_INTRINSICS = {'Decimal', 'date', 'datetime', 'timedelta'}
_TYPE_IMPORTS = {'typing': {'Literal', 'Optional', 'Annotated'}, 'decimal': {'Decimal'},
                 'datetime': {'date', 'datetime', 'timedelta'}}


def _import_reasons(cfg, anchor, tree, function):
    """Verify initialization before importing an otherwise unobserved function."""
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
        if module in _PURE_MODULES and not project_code(getattr(sys.modules.get(module), '__file__', None) or 'built-in', cfg.root):
            return
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
    return reasons
