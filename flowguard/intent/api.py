"""The intent API used in tests/intent/*.py (design 2.3).

A rule is a partial predicate over typed fields: it returns a value, Refused(type, contains=...)
or None (no opinion). Rows hold literals only (checked from the file's AST at load time), and
every row says why it matters. Source anchors and Flow relations bind real code readings.
`distinct` names two rules or two source anchors that must stay different. Declarations are checked by the loader and executed only as ordinary pytest items.
"""
from __future__ import annotations

import re
import sys
from itertools import islice
from datetime import date, datetime, timedelta
from decimal import Decimal as D

__all__ = ["rule", "row", "distinct", "states", "structure_rule", "allow", "flow", "Node", "Transition", "Read", "Relation",
           "precedes", "guarded_by", "transitions", "checks", "Refused", "IntentError", "D", "date", "datetime", "timedelta"]

ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
TARGET = re.compile(r"[A-Za-z_][\w.]*:[A-Za-z_][\w.]*\Z")
WHERE = re.compile(r"[^:\s][^:]*\.py:[1-9][0-9]*\Z")
_MISSING = object()
DECLARED: list = []   # rules and distincts of the intent file being loaded (the loader empties it per file)


class IntentError(Exception):
    """A load-time refusal of intent the tool cannot check; the message names the line."""


class Refused:
    """An expected refusal: the code must raise an exception of this type (or a subclass) whose
    message contains every `contains` text. 1.x could not say "must raise X naming both requirements"."""
    __slots__ = ("type", "contains")

    def __init__(self, type, contains=()):
        self.type = type if isinstance(type, str) else type.__name__
        self.contains = (contains,) if isinstance(contains, str) else tuple(contains)

    def matches(self, error: BaseException) -> bool:
        names = {k.__name__ for k in builtins_type(error).__mro__}
        return self.type in names and all(text in str(error) for text in self.contains)

    def __eq__(self, other):
        return isinstance(other, Refused) and (self.type, self.contains) == (other.type, other.contains)

    def __hash__(self):
        return hash((self.type, self.contains))

    def __repr__(self):
        tail = "" if not self.contains else f", contains={self.contains[0]!r}" if len(self.contains) == 1 \
            else f", contains={self.contains!r}"
        return f"Refused({self.type}{tail})"


builtins_type = type


class Row:
    """One literal case: inputs, the expected answer and why it matters (a lesson never shrinks silently)."""

    def __init__(self, inputs: dict, expect, why: str, retired, line: int, origin=None):
        self.inputs, self.expect, self.why, self.retired, self.line = inputs, expect, why, retired, line
        self.origin = origin
        self.rule = None

    def __repr__(self):
        return "row(" + ", ".join(f"{k}={v!r}" for k, v in self.inputs.items()) + f" -> {self.expect!r})"


def row(*args, expect=_MISSING, why=None, retired=None, **inputs) -> Row:
    caller = sys._getframe(1)
    position = next(islice(caller.f_code.co_positions(), caller.f_lasti // 2, None))
    line = position[0] or caller.f_lineno
    if args:
        raise IntentError(f"line {line}: row() takes named fields only")
    if expect is _MISSING:
        raise IntentError(f"line {line}: a row needs expect=")
    if not isinstance(why, str) or not why.strip():
        raise IntentError(f"line {line}: a row needs why= (the reason this case matters)")
    if retired is not None and (not isinstance(retired, str) or not retired.strip()):
        raise IntentError(f"line {line}: retired= takes the reason the row no longer applies")
    return Row(inputs, expect, why, retired, line, (caller.f_code.co_filename, *position))


def equivalents(value, line: int) -> tuple:
    """equivalent=("file.py:line", "reason") or a list of them: decision sites whose surviving mutant
    cannot change any answer of the rule (design 3.6: equivalent mutants need a reason)."""
    if not value:
        return ()
    items = [value] if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str) else list(value)
    out = []
    for it in items:
        if not (isinstance(it, (tuple, list)) and len(it) == 2 and isinstance(it[0], str) and WHERE.match(it[0])
                and isinstance(it[1], str) and it[1].strip()):
            raise IntentError(f"line {line}: equivalent= takes (\"file.py:line\", \"reason\") pairs, got {it!r}")
        out.append((it[0], it[1].strip()))
    return tuple(out)


class _AnchorBinding:
    """A resolved code comment, without a project-owned call adapter."""
    def __init__(self, rule, anchor, name='', equivalent=()):
        self.rule, self.anchor = rule, anchor
        self.name = name or anchor.name
        self.target = anchor.target if anchor else 'anchor:' + self.name
        self.line = anchor.line if anchor else rule.line
        self.equivalent = equivalent

    @property
    def short(self):
        return self.target.replace(':', '.')


def _ids(value) -> tuple:
    values = value if isinstance(value, (list, tuple, set, frozenset)) else [value] if value else []
    return tuple(v.id if isinstance(v, Rule) else v for v in values)


class Rule:
    def __init__(self, id, decides, source, fields, pred, overrides=(), supersedes=(), total=False, uses=(),
                 confirmed=None, equivalent=(), quote=None, anchor=()):
        line = pred.__code__.co_firstlineno
        if not isinstance(id, str) or not ID.match(id):
            raise IntentError(f"line {line}: rule id must be a word such as STANDING, got {id!r}")
        if not isinstance(decides, str) or not decides.strip():
            raise IntentError(f"line {line}: rule {id} needs decides= (the decision key it shares with other rules)")
        if not isinstance(source, str) or not source.strip():
            raise IntentError(f"line {line}: rule {id} needs source= ('owner R<n>: ...', 'doc PATH:LINE', "
                              "'assumed: ...' or 'lesson: ...')")
        if not isinstance(fields, dict) or not fields:
            raise IntentError(f"line {line}: rule {id} needs fields={{name: type}}")
        params = list(pred.__code__.co_varnames[:pred.__code__.co_argcount])
        if sorted(params) != sorted(fields):
            raise IntentError(f"line {line}: rule {id}: the predicate's parameters {params} must be the fields "
                              f"{sorted(fields)}")
        self.id, self.decides, self.source, self.fields, self.pred = id, decides, source, dict(fields), pred
        self.overrides, self.supersedes, self.uses = _ids(overrides), _ids(supersedes), _ids(uses)
        self.total, self.confirmed, self.line = bool(total), confirmed, line
        self.quote = quote
        self.equivalent = equivalents(equivalent, line)
        self.file = pred.__code__.co_filename
        self.doc = (pred.__doc__ or "").strip()
        self._rows: list[Row] = []
        self.homes: list[_AnchorBinding] = []
        self.anchors = (anchor,) if isinstance(anchor, str) else tuple(anchor)
        if any(not isinstance(name, str) or not name.strip() for name in self.anchors):
            raise IntentError(f'line {line}: anchor= names code observation points')

    def rows(self, *rows) -> "Rule":
        for r in rows:
            if not isinstance(r, Row):
                raise IntentError(f"line {self.line}: {self.id}.rows() takes row(...) values, got {r!r}")
            r.rule = self
            self._rows.append(r)
        return self

    @property
    def all_rows(self) -> list[Row]:
        return list(self._rows)

    @property
    def live_rows(self) -> list[Row]:
        return [r for r in self._rows if r.retired is None]

    def eval(self, cell: dict):
        return self.pred(**{name: cell[name] for name in self.fields})

    def __call__(self, **fields):
        return self.pred(**fields)

    def __repr__(self):
        return f"<rule {self.id} decides {self.decides}>"


def rule(id, decides, source, fields, overrides=(), supersedes=(), total=False, uses=(), confirmed=None,
         equivalent=(), quote=None, anchor=()):
    """Declare a rule on a partial predicate; the predicate's parameters are the fields."""
    def wrap(pred):
        r = Rule(id, decides, source, fields, pred, overrides, supersedes, total, uses, confirmed, equivalent, quote, anchor)
        DECLARED.append(r)
        return r
    return wrap


def flow(identifier, *, source, nodes, edges, transitions=(), relations=()):
    """A small observation model: anchors, paths, state transitions and relations."""
    return _declare_flow(identifier, source, nodes, edges, transitions, relations)


def _declare_flow(identifier, source, nodes, edges, transitions=(), relations=(), optional=(), depth=2):
    from .flow import Flow
    caller = sys._getframe(depth)
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise IntentError(f'line {caller.f_lineno}: flow id must be a word, got {identifier!r}')
    item = Flow(identifier, source, nodes, edges, transitions, relations, optional=optional)
    item.file, item.line = caller.f_code.co_filename, caller.f_lineno
    DECLARED.append(item)
    return item


# ---- one-line relation templates: each is an ordinary Flow, checked by the existing flow checks ----

def _template_id(kind, *names):
    return kind.upper() + '_' + '_'.join(re.sub(r'\W+', '_', name).strip('_') for name in names)


def _template_source(kind, source, *arguments):
    return source or f'assumed: {kind}(' + ', '.join(map(repr, arguments)) + ')'


def precedes(first, then, *, source=None):
    """Every observed `then` comes after a `first` in the same test: `first` starts each path."""
    from .flow import Node
    edges = (('first', 'then'), ('first', 'first'), ('then', 'then'), ('then', 'first'))
    return _declare_flow(_template_id('precedes', first, then), _template_source('precedes', source, first, then),
                         (Node('first', first, start=True, end=True), Node('then', then, end=True)), edges,
                         optional=edges[1:], depth=2)


def guarded_by(guard, action, *, source=None):
    """Every observed `action` has its own `guard` before it: no action follows an action directly."""
    from .flow import Node
    edges = (('guard', 'action'), ('guard', 'guard'), ('action', 'guard'))
    return _declare_flow(_template_id('guarded_by', guard, action), _template_source('guarded_by', source, guard, action),
                         (Node('guard', guard, start=True, end=True), Node('action', action, end=True)), edges,
                         optional=edges[1:], depth=2)


def transitions(state, *, source=None, **allowed):
    """The allowed changes of one `states` field wherever an anchored call changes it:
    transitions("Job.status", new={"saved"}, saved={"published"}). Its values come from the field's
    existing `# flowguard: states` comment; this line only says which changes are allowed."""
    from .flow import Transition
    if not allowed:
        raise IntentError(f'transitions({state!r}) needs before={{after, ...}} pairs')
    steps = []
    for before, afters in allowed.items():
        values = afters if isinstance(afters, (set, frozenset, list, tuple)) else (afters,)
        steps.extend(Transition(state, before, after, '*') for after in sorted(values, key=repr))
    return _declare_flow(_template_id('transitions', state), _template_source('transitions', source, state),
                         (), (), tuple(steps), depth=2)


def checks(rule, case, *, actual=None, source=None, **fields):
    """A rule checked on a scenario test's own arguments: checks("FEE", "FEE_CASE", days="arg.days").
    The decision read is `actual` (an anchor name, optionally `NAME.result...`), by default the rule's
    single anchor or the anchor named like the rule; the existing scenario binding derives the rest."""
    from .flow import Node, Read, Relation
    identifier = rule.id if isinstance(rule, Rule) else rule
    if not fields:
        raise IntentError(f'checks({identifier!r}, {case!r}) needs field="arg.name" readings')
    if actual is None:
        anchors = rule.anchors if isinstance(rule, Rule) else ()
        actual = anchors[0] if len(anchors) == 1 else identifier
    anchor, _, path = actual.partition('.')
    relation = Relation(rule, {name: Read('case', value) for name, value in fields.items()},
                        actual=Read('actual', path or 'result'), on='actual')
    return _declare_flow(_template_id('checks', identifier, case), _template_source('checks', source, identifier, case),
                         (Node('case', case, start=True), Node('actual', anchor, phase='return', end=True)),
                         (('case', 'actual'), ('actual', 'actual')), relations=(relation,),
                         optional=(('actual', 'actual'),), depth=2)


from .flow import Node, Transition, Read, Relation


class Distinct:
    """Two rules or two source anchors that must retain different decisions."""

    def __init__(self, a, b, why, source, line):
        self.rule_sides = (isinstance(a, Rule), isinstance(b, Rule))
        self.a = a.id if isinstance(a, Rule) else a
        self.b = b.id if isinstance(b, Rule) else b
        self.why, self.source, self.line = why, source, line
        self.file = None
        self.binding_kind = 'rules'

    def __call__(self, function):
        raise IntentError(f"line {self.line}: distinct call adapters were removed; rebuild the original "
                          "test using source anchors and Flow relations; declare distinct between two rules or two anchors")


def distinct(a, b, why, source) -> Distinct:
    """Declare two rules or two source anchors as separate decisions, with their source and reason."""
    line = sys._getframe(1).f_lineno
    if not isinstance(why, str) or not why.strip():
        raise IntentError(f"line {line}: distinct() needs why=")
    if not isinstance(source, str) or not source.strip():
        raise IntentError(f"line {line}: distinct() needs source=")
    d = Distinct(a, b, why, source, line)
    DECLARED.append(d)
    return d


class States:
    """Only a real field's allowed literals; no state-machine execution."""
    def __init__(self, target, values, source):
        self.id = 'states:' + target
        self.target, self.values, self.source = target, tuple(values), source
        self.line = sys._getframe(2).f_lineno


def states(target, values, *, source):
    if not isinstance(target, str) or not TARGET.fullmatch(target) or '.' not in target.split(':')[1]:
        raise IntentError('states needs module:Class.field')
    if not isinstance(values, (list, tuple)) or not values:
        raise IntentError('states needs an explicit nonempty list of literals')
    item = States(target, values, source)
    DECLARED.append(item)
    return item


def allow(node, why):
    if not isinstance(why, str) or not why.strip():
        raise IntentError('allow needs the reason this node is an exception')
    return (node, why)


class StructureRule:
    def __init__(self, identifier, source, predicate):
        self.id, self.source, self.pred = identifier, source, predicate
        self.file, self.line = predicate.__code__.co_filename, predicate.__code__.co_firstlineno
        self.allowed = {}

    def allows(self, *entries):
        for node, why in entries:
            self.allowed[node] = why
        return self


def structure_rule(identifier, *, source):
    """A Python function selects violations from six fixed generated queries."""
    def declare(predicate):
        item = StructureRule(identifier, source, predicate)
        DECLARED.append(item)
        return item
    return declare
