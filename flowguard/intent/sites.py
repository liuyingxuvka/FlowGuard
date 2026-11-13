"""Decision sites of a real function, their constants, and mutants installed by swapping __code__.

A site is a comparison, membership test, truth test or and/or in the function's own body (nested
functions and lambdas are theirs). Its constant is folded in the home's globals, so
Limits.GRACE_DAYS, POLICY["grace"] and D("50.00") read as values. Mutants (design 3.6, at most 2
per site, without a cap): flip a boundary, move a constant by its step, negate a test, swap
and/or. Each is compiled in the home's globals and installed by swapping __code__ on the unwrapped
function, restored in finally. The __class__ closure is supported; other closures and private names
in methods read `not mutable`.
"""
from __future__ import annotations

import ast
import copy
import enum
import importlib
import inspect
import sys
import types
import weakref
import textwrap
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .cells import coerce, const_value, epsilon

_INSTALLED = ContextVar('flowguard_installed_code', default={})
_TRANSPORT = ContextVar('flowguard_transport_code', default={})
_MUTANTS = weakref.WeakKeyDictionary()


def is_transport(code):
    return _TRANSPORT.get().get(id(code)) is code


def source_caller(frame):
    """The actual caller with only this runtime's exact transport frames removed."""
    parent = frame.f_back
    while parent is not None and is_transport(parent.f_code):
        parent = parent.f_back
    return parent


def installed_replacement(code):
    return any(fn.__code__ is code and code is not original
               for fn, original in _INSTALLED.get().items())


@contextmanager
def transport(codes):
    token = _TRANSPORT.set({**_TRANSPORT.get(), **{id(code): code for code in codes if code is not None}})
    try:
        yield
    finally:
        _TRANSPORT.reset(token)

FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
NEGATE = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn,
          ast.NotIn: ast.In}
OPS = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=", ast.Is: "is",
       ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in"}


class NotMutable(Exception):
    pass


@dataclass
class Site:
    line: int                 # line in the file
    kind: str                 # cmp, in, truth, boolop
    text: str
    field_text: str
    key: tuple                # where the node sits in the function's own parse
    has_const: bool = False
    const: object = None
    const_side: str = ""      # left or right
    op: str = ""
    names: set = field(default_factory=set)


def resolve(target: str):
    module, _, qual = target.partition(":")
    return _member(importlib.import_module(module), qual)


def _member(obj, qual):
    for part in qual.split("."):
        owner = obj
        obj = vars(owner).get(part, getattr(owner, part)) if isinstance(owner, type) else getattr(owner, part)
        if isinstance(obj, classmethod):
            obj = getattr(owner, part)
        elif isinstance(obj, staticmethod):
            obj = obj.__func__
        elif isinstance(obj, property):
            obj = obj.fget
    return obj


def resolve_loaded(target: str):
    """Resolve a calibration target without importing it ahead of its test fixtures."""
    module, _, qual = target.partition(':')
    if module not in sys.modules:
        raise NotMutable('calibration target was not imported by test collection/setup')
    return _member(sys.modules[module], qual)


def unwrap(fn):
    """The function whose code runs: decorators unwrapped, a bound method's function, a class's __init__."""
    if isinstance(fn, type):
        fn = fn.__init__
    fn = inspect.unwrap(fn)
    return fn.__func__ if inspect.ismethod(fn) else fn


def code_key(code) -> tuple:
    return (code.co_filename, code.co_firstlineno)


class _Read(list):
    """Lines given to inspect.getblock, counting how many its tokenizer takes and whether it asked past the last."""
    taken, ended = 0, False

    def __iter__(self):
        for line in list.__iter__(self):
            self.taken += 1
            yield line
        self.ended = True


_BLOCKS = {}


def _source(fn):
    """inspect.getsource(fn), the steps of inspect.getsourcelines for a function: findsource, then getblock. Every
    test's call hooks tokenize the same few functions, so a block is reused while the lines its tokenizer took are
    the same, and the file still ends there if it took them all; any other text is tokenized again."""
    function = inspect.unwrap(fn)
    if type(function) is not types.FunctionType:
        return inspect.getsource(fn)
    lines, lnum = inspect.findsource(function)
    rest, key = lines[lnum:], (function.__code__.co_filename, lnum)
    if key in _BLOCKS:
        taken, ended, block = _BLOCKS[key]
        if (len(rest) == len(taken) if ended else len(rest) >= len(taken)) and tuple(rest[:len(taken)]) == taken:
            return ''.join(block)
    read = _Read(rest)
    block = inspect.getblock(read)
    _BLOCKS[key] = tuple(rest[:read.taken]), read.ended, block
    return ''.join(block)


def _function(src):
    tree = ast.parse(src)
    fdef = tree.body[0]
    if not isinstance(fdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise NotMutable("not a function definition")
    return tree, fdef


def _parse(fn):
    return _function(textwrap.dedent(_source(fn)))


def _private(fdef):
    return any(isinstance(n, ast.Attribute) and n.attr.startswith("__") and not n.attr.endswith("__")
               for n in ast.walk(fdef))


def _strip(fdef):
    """No decorators, defaults or annotations: the compiled copy keeps the function's own."""
    fdef.decorator_list = []
    fdef.returns = None
    a = fdef.args
    a.defaults, a.kw_defaults = [], [None] * len(a.kwonlyargs)
    for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
        arg.annotation = None


_HEADERS = {}


def _header(fn):
    """_parse(fn) for a copy whose body is replaced whole: a copy of the stripped function without its body, and whether
    that body names a private attribute. The same source text always parses the same, so each text is parsed once."""
    src = textwrap.dedent(_source(fn))
    if src not in _HEADERS:
        tree, fdef = _function(src)
        private = _private(fdef)
        fdef.body = []
        _strip(fdef)
        _HEADERS[src] = tree, private
    tree, private = _HEADERS[src]
    tree = copy.deepcopy(tree)
    return tree, tree.body[0], private


def own_nodes(fdef):
    """Nodes of the function's own body, not of nested functions, lambdas or classes."""
    stack = list(fdef.body)
    while stack:
        n = stack.pop(0)
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.append(c)


def _key(n) -> tuple:
    return (n.lineno, n.col_offset, n.end_lineno, n.end_col_offset, type(n).__name__)


def _plain(n) -> bool:
    return not isinstance(n, (ast.Compare, ast.BoolOp, ast.Constant)) and \
        not (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not))


def data_names(node) -> set:
    """Names supplying a decision's data; callable names do not identify fields."""
    names = set()

    class Data(ast.NodeVisitor):
        def visit_Name(self, n):
            names.add(n.id)

        def visit_Attribute(self, n):
            names.add(n.attr)
            self.visit(n.value)

        def visit_Subscript(self, n):
            if isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
                names.add(n.slice.value)
            self.generic_visit(n)

        def visit_Call(self, n):
            if isinstance(n.func, ast.Attribute):
                self.visit(n.func.value)
            for arg in n.args:
                self.visit(arg)
            for keyword in n.keywords:
                self.visit(keyword.value)

    Data().visit(node)
    return names


def sites_of(fn) -> list[Site]:
    fn = unwrap(fn)
    tree, fdef = _parse(fn)
    offset = fn.__code__.co_firstlineno - 1
    env = {**vars(__import__("builtins")), **fn.__globals__}
    args = fdef.args
    local = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs} | \
        {a.arg for a in (args.vararg, args.kwarg) if a} | \
        {n.id for n in ast.walk(fdef) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    out, seen = [], set()

    def add(site):
        if site.key not in seen:
            seen.add(site.key)
            out.append(site)
    for n in own_nodes(fdef):
        if isinstance(n, ast.Compare):
            op = type(n.ops[0])
            left, right = n.left, n.comparators[0]
            cl, cr = const_value(left, env, local), const_value(right, env, local)
            side, var, cv = ("right", left, cr) if cr is not None else ("left", right, cl) if cl is not None \
                else ("", left, None)
            add(Site(n.lineno + offset, "in" if op in (ast.In, ast.NotIn) else "cmp", ast.unparse(n),
                     ast.unparse(var), _key(n), cv is not None, cv[1] if cv else None, side, OPS.get(op, "?"),
                     data_names(var)))
        tests = []
        if isinstance(n, (ast.If, ast.IfExp, ast.Assert)):   # no while: a negated loop test would hang
            tests.append(n.test)
        if isinstance(n, ast.BoolOp):
            tests.extend(n.values)
            add(Site(n.lineno + offset, "boolop", ast.unparse(n), "", _key(n), op="and" if isinstance(n.op, ast.And)
                     else "or", names=data_names(n)))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            tests.append(n.operand)
        for t in tests:
            if _plain(t):
                text = ast.unparse(t)
                add(Site(t.lineno + offset, "truth", text, text, _key(t), names=data_names(t)))
    return sorted(out, key=lambda s: (s.line, s.key))


def compatible(v, kind) -> bool:
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, enum.Enum):
        return kind.name == "enum"
    if isinstance(v, str):
        return kind.name in ("str", "enum")
    if isinstance(v, (int, float, Decimal)):
        return kind.name in ("int", "float", "dec")
    if isinstance(v, datetime):
        return kind.name == "datetime"
    if isinstance(v, date):
        return kind.name == "date"
    if isinstance(v, timedelta):
        return kind.name == "td" or (kind.name == "int" and v.total_seconds() % 86400 == 0)
    if isinstance(v, (tuple, list, set, frozenset)):
        return any(compatible(x, kind) for x in v)
    return False


def site_constants(site: Site) -> list:
    if not site.has_const:
        return []
    v = site.const
    return list(v) if isinstance(v, (tuple, list, set, frozenset)) else [v]


# ---------------------------------------------------------------- mutants

@dataclass
class Mutant:
    site: Site
    label: str
    how: str   # flip, move, negate, swap


def mutants_of(sites: list[Site], realized: set) -> list[Mutant]:
    """At most 2 per site (a boundary flip and a moved constant, or one negation or swap), realized
    sites first. Every applicable mutant is returned."""
    out = []
    for s in sorted(sites, key=lambda s: (s.key not in realized, s.line)):
        mine = []
        if s.kind == "cmp" and s.op in ("<", "<=", ">", ">="):
            flipped = {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}[s.op]
            mine.append(Mutant(s, f"{s.text} becomes {s.text.replace(s.op, flipped, 1)}", "flip"))
            if s.has_const and epsilon(s.const) is not None:
                mine.append(Mutant(s, f"the bound of {s.text} moves by {_show(epsilon(s.const))}", "move"))
        elif s.kind in ("cmp", "in"):
            mine.append(Mutant(s, f"{s.text} is negated", "negate"))
        elif s.kind == "truth":
            mine.append(Mutant(s, f"the test {s.text} is negated", "negate"))
        elif s.kind == "boolop":
            mine.append(Mutant(s, f"{s.op} becomes {'or' if s.op == 'and' else 'and'} in {s.text[:40]}", "swap"))
        out.extend(mine)
    return out


def _show(v):
    return f"{v.days} day" if isinstance(v, timedelta) and v.days else str(v)


def _value_expr(v) -> ast.expr:
    if isinstance(v, Decimal):
        text = f"__import__('decimal').Decimal({str(v)!r})"
    elif isinstance(v, timedelta):
        text = f"__import__('datetime').timedelta(seconds={v.total_seconds()!r})"
    else:
        text = repr(v)
    return ast.parse(text, mode="eval").body


class _Apply(ast.NodeTransformer):
    def __init__(self, m: Mutant):
        self.m = m
        self.done = False

    def visit(self, node):
        if isinstance(node, ast.AST) and hasattr(node, "lineno") and _key(node) == self.m.site.key:
            self.done = True
            return self.change(node)
        return super().visit(node)

    def change(self, n):
        how = self.m.how
        if how == "flip":
            n.ops = [FLIP[type(n.ops[0])]()] + n.ops[1:]
        elif how == "move":
            target = "comparators" if self.m.site.const_side == "right" else "left"
            old = n.comparators[0] if target == "comparators" else n.left
            moved = ast.BinOp(left=old, op=ast.Add(), right=_value_expr(epsilon(self.m.site.const)))
            if target == "comparators":
                n.comparators = [moved] + n.comparators[1:]
            else:
                n.left = moved
        elif how == "negate" and isinstance(n, ast.Compare):
            n.ops = [NEGATE[type(n.ops[0])]()] + n.ops[1:]
        elif how == "negate":
            return ast.UnaryOp(op=ast.Not(), operand=n)
        elif how == "swap":
            n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
        return n


def _controlled_code(fn, code):
    _MUTANTS.setdefault(unwrap(fn), weakref.WeakValueDictionary())[id(code)] = code
    return code


def mutant_code(fn, m: Mutant):
    """One source-site mutant, with precise weak provenance for controlled capture."""
    fn = unwrap(fn)
    t = _Apply(m)
    return _controlled_code(fn, _recompile(fn, t, lambda: t.done))


def controlled_mutation(function, code):
    function = unwrap(function)
    registered = _MUTANTS.get(function)
    return (registered is not None and registered.get(id(code)) is code
            and function.__code__ is code and function in _INSTALLED.get())


class _Probe(ast.NodeTransformer):
    """Wraps every site of one function in flowguard.intent.probe recorders: the outcome of the site and, for a
    comparison, the values of its two first operands. The values pass through unchanged."""
    REC = "__import__('flowguard.intent.probe', fromlist=('out',))"

    def __init__(self, fi: int, keys: dict):
        self.fi, self.keys, self.done = fi, keys, set()

    def _call(self, name, si, node):
        func = ast.Attribute(value=ast.parse(self.REC, mode="eval").body, attr=name, ctx=ast.Load())
        return ast.copy_location(ast.Call(func=func, args=[ast.Constant(self.fi), ast.Constant(si), node],
                                          keywords=[]), node)

    def visit(self, node):
        node = super().visit(node)
        si = self.keys.get(_key(node)) if isinstance(node, ast.expr) and hasattr(node, "lineno") else None
        if si is None:
            return node
        self.done.add(si)
        if isinstance(node, ast.Compare):
            node.left = self._call("lv", si, node.left)
            node.comparators = [self._call("rv", si, node.comparators[0])] + node.comparators[1:]
        return self._call("out", si, node)


def probe_code(fn, fi: int, sites: list, home: bool = False):
    """The code object of fn with every site recorded (flowguard.intent.probe), compiled like a mutant. The
    home's copy also marks while it runs (probe.enter/leave), so only its own calls are counted."""
    keys = {s.key: si for si, s in enumerate(sites)}
    t = _Probe(fi, keys)

    def mark(fdef):
        call = lambda name: ast.Expr(ast.parse(f"{_Probe.REC.replace('out', name)}.{name}()", mode="eval").body)
        fdef.body = [call("enter"), ast.Try(body=fdef.body, handlers=[], orelse=[], finalbody=[call("leave")])]
    return _controlled_code(fn, _recompile(fn, t, lambda: bool(t.done) or home, mark if home else None))


def _recompile(fn, transformer, found, post=None):
    fn = unwrap(fn)
    free = fn.__code__.co_freevars
    if free and free != ("__class__",):
        raise NotMutable("closure (free variables)")
    if transformer is None:         # the call hook: post() replaces the whole body, so only the rest is copied
        tree, fdef, private = _header(fn)
        if "." in fn.__qualname__ and private:
            raise NotMutable("private names in a method")
    else:
        tree, fdef = _parse(fn)
        if "." in fn.__qualname__ and _private(fdef):
            raise NotMutable("private names in a method")
        _strip(fdef)
        tree = transformer.visit(tree)
    if not found():
        raise NotMutable("site not found again")
    if post is not None:
        post(fdef)
    ast.fix_missing_locations(tree)
    ast.increment_lineno(tree, fn.__code__.co_firstlineno - 1)
    if free == ('__class__',):
        factory = ast.parse('def __flowguard_factory(__class__):\n    pass\n').body[0]
        factory.body = [tree.body[0], ast.Return(ast.Name(fdef.name, ast.Load()))]
        tree.body = [factory]
        ast.fix_missing_locations(tree)
    code = compile(tree, fn.__code__.co_filename, "exec")
    ns: dict = {}
    exec(code, fn.__globals__, ns)
    new = ns['__flowguard_factory'](fn.__closure__[0].cell_contents) if free else ns[fdef.name]
    if new.__code__.co_freevars != fn.__code__.co_freevars:
        raise NotMutable("free variables differ")
    # Compiling a method outside its class (or inside the __class__ factory)
    # changes co_qualname. It is still the same source function: preserve that
    # identity for real-frame anchor capture, imported aliases and footprints.
    return new.__code__.replace(co_qualname=fn.__code__.co_qualname)


@contextmanager
def installed(fn, code):
    fn = unwrap(fn)
    old = fn.__code__
    active = dict(_INSTALLED.get())
    active.setdefault(fn, old)
    token = _INSTALLED.set(active)
    fn.__code__ = code
    try:
        yield
    finally:
        fn.__code__ = old
        _INSTALLED.reset(token)


def installed_origin(fn):
    if type(fn) is types.FunctionType and not hasattr(fn, '__wrapped__'):
        return _INSTALLED.get().get(fn)     # unwrap(fn) is fn: every capture asks this of every function it walks
    return _INSTALLED.get().get(unwrap(fn))


def covered_constant(v) -> bool:
    """None and booleans are always points of their field (Optional adds None, bool has both)."""
    return v is None or isinstance(v, bool)


def orderable(v) -> bool:
    """A constant that bounds an interval: its c-e, c, c+e must be points for the cells to be complete."""
    return isinstance(v, (int, float, Decimal, date, timedelta)) and not isinstance(v, bool)


@contextmanager
def intercepted(fn, callback, *, keep=None):
    """One mechanical call hook on the same function object, including imported aliases.

    The original code runs in a clone with the same globals/defaults.  The hook
    sees its final return/exception after all of its finally blocks, not a
    rewritten early return.  No frame-local writes or business projection.
    """
    fn = unwrap(fn)
    if not isinstance(fn, types.FunctionType):
        raise NotMutable('calibration target is not a Python function')
    if fn.__code__.co_freevars:
        raise NotMutable('calibration closure is unsupported')
    # Such a call returns a coroutine or a generator, not its result: say which the function is.
    for kind, test in (('an async generator', inspect.isasyncgenfunction), ('async', inspect.iscoroutinefunction),
                       ('a generator', inspect.isgeneratorfunction)):
        if test(fn):
            raise NotMutable(f'is {kind}; its calls are not recorded')
    signature = inspect.signature(fn, follow_wrapped=False)
    if any(p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in signature.parameters.values()):
        raise NotMutable('calibration variadic signature is unsupported')
    original = types.FunctionType(fn.__code__, fn.__globals__, fn.__name__, fn.__defaults__)
    original.__kwdefaults__ = fn.__kwdefaults__
    original.__annotations__ = fn.__annotations__
    key = '__flowguard_calibration_' + str(id(callback))
    while key in fn.__globals__ or key in signature.parameters:
        key += '_'
    def invoke(*args, **kwargs):
        try:
            return callback(original, signature.bind(*args, **kwargs))
        finally:
            if keep is not None and not keep():
                fn.__code__ = original.__code__
                fn.__globals__.pop(key, None)
    def body(fdef):
        args = [ast.Name(p.name, ast.Load()) for p in signature.parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        keywords = [ast.keyword(p.name, ast.Name(p.name, ast.Load()))
                    for p in signature.parameters.values() if p.kind == p.KEYWORD_ONLY]
        fdef.body = [ast.Return(ast.Call(ast.Name(key, ast.Load()), args, keywords))]
    code = _recompile(fn, None, lambda: True, body)      # the body is replaced whole: nothing to transform
    original.__flowguard_transport__ = (code, invoke.__code__)
    mechanical = (*original.__flowguard_transport__, getattr(callback, '__code__', None),
                  *getattr(callback, '__flowguard_transport__', ()))
    fn.__globals__[key] = invoke
    try:
        with transport(mechanical), installed(fn, code):
            yield original
    finally:
        fn.__globals__.pop(key, None)
