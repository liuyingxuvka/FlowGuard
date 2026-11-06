"""Adapter guards (design 3.3): `adapter decides` and the adapter size.

An adapter `(c, fn)` may only build inputs from the case and read what fn produced. Its answer
must depend on the case only through fn. The guard reads the adapter's AST: tests, comparisons
and returned values that read the case outside fn's arguments, a constant answer whatever fn
does, an answer computed without fn at all, and helpers of the intent or test files that receive
fn and decide themselves (followed to any depth). Selecting from fn's result by identity or key
is reading the result, not deciding: `m in [n["member_id"] for n in fn(...)]`, where m is a handle
the builders got from project code (an id, a created object), is allowed; the same test against a
value taken from the case is not. A builder that sets the answer from the case (a helper that
passes `fee="10" if c.x >= 2 else "0"` to project code) is caught by tracing (engine.forced).
"""
from __future__ import annotations

import ast
import inspect
import textwrap

IMMUTABLE = (int, float, complex, str, bytes, bool, type(None), tuple, frozenset)
SELECT = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)


def _adapter_tree(adapter):
    src = textwrap.dedent(inspect.getsource(adapter))
    node = ast.parse(src).body[0]
    node.decorator_list = []
    return node


def adapter_lines(home) -> int:
    node = _adapter_tree(home.adapter)
    return node.end_lineno - node.lineno + 1


def adapter_decides(adapter, is_project=None) -> str:
    """The adapter decides instead of only building inputs and reading the result: its answer
    depends on the case other than through fn (a comparison, test, or returned value reading the
    case outside fn's arguments), it returns a constant, or a helper it passes fn to does so."""
    node = _adapter_tree(adapter)
    params = [a.arg for a in node.args.posonlyargs + node.args.args]
    if len(params) < 2:
        return "takes no fn: an adapter is (c, fn)"
    return _decides(node, {params[0]}, {params[1]}, adapter.__globals__, is_project, (adapter.__code__,))


def builder_decides(adapter, is_project):
    """Follow case-derived builder arguments without recording any real call values.

    A builder may translate days into a date or assemble records. If it turns those
    fields into a policy comparison before calling the home, the rule cannot use
    that adapter as independent evidence.
    """
    seen = set()

    def inspect_builder(function, tainted):
        key = (function.__code__, tuple(sorted(tainted)))
        if key in seen:
            return None
        seen.add(key)
        try:
            node = _adapter_tree(function)
        except (OSError, TypeError, SyntaxError, IndexError):
            return f'adapter builder {function.__name__} cannot be read -> use a transparent builder'
        assignments = [(n.targets, n.value) for n in ast.walk(node) if isinstance(n, ast.Assign)]
        names = set(tainted)
        home_names = {list(inspect.signature(adapter).parameters)[1]} if function is adapter else set()
        # A project-created handle selects this member from the result; it is
        # not a policy answer computed from the case. The same helper analysis
        # already licenses such handles for the primary adapter guard.
        handles = _handles(node, function.__globals__, is_project, (function.__code__,),
                           {id(call) for call in ast.walk(node) if isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Name) and call.func.id in home_names})

        def reads_case(expression):
            protected = {id(n) for call in ast.walk(expression)
                         if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in home_names
                         for n in ast.walk(call)}
            return any(isinstance(n, ast.Name) and n.id in names and id(n) not in protected for n in ast.walk(expression))

        while True:
            old = set(names)
            for targets, value in assignments:
                if reads_case(value):
                    names.update(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name) and n.id not in handles)
            if old == names:
                break
        for expression in ast.walk(node):
            if isinstance(expression, (ast.Compare, ast.BoolOp)) and reads_case(expression):
                return f'adapter forces the answer via {function.__name__}: {ast.unparse(expression)} -> move the decision into the home'
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            obj = _resolve(call.func, function.__globals__)
            if not inspect.isfunction(obj) or is_project(obj.__code__.co_filename):
                continue
            params = list(inspect.signature(obj).parameters)
            arguments = list(zip(params, call.args)) + [(k.arg, k.value) for k in call.keywords]
            passed = {p for p, argument in arguments if p and any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(argument))}
            if passed:
                problem = inspect_builder(obj, passed)
                if problem:
                    return problem
        return None

    return inspect_builder(adapter, {next(iter(inspect.signature(adapter).parameters))})


def _exprs(node):
    """The expression nodes under node. ast.walk also yields Load() and operator objects, which the
    parser shares between all nodes, so only expressions may be compared by id()."""
    return (x for x in ast.walk(node) if isinstance(x, ast.expr))


def _root(e):
    """The variable an argument is read from (store, w.store, w["store"]); a call builds something new."""
    while isinstance(e, (ast.Attribute, ast.Subscript)):
        e = e.value
    return e.id if isinstance(e, ast.Name) else None


def _resolve(func, g):
    if isinstance(func, ast.Name):
        return g.get(func.id, getattr(__import__("builtins"), func.id, None))
    if isinstance(func, ast.Attribute):
        owner = _resolve(func.value, g)
        return getattr(owner, func.attr, None) if owner is not None else None
    return None


def _project_obj(obj, is_project) -> bool:
    """A project function, class or module, or an object of a project class."""
    if is_project is None or obj is None:
        return False
    if inspect.ismodule(obj):
        return bool(getattr(obj, "__file__", None)) and is_project(obj.__file__)
    target = obj if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj) else type(obj)
    target = inspect.unwrap(target) if callable(target) and not inspect.isclass(target) else target
    code = getattr(target, "__code__", None)
    if code is not None:
        return is_project(code.co_filename)
    mod = __import__("sys").modules.get(getattr(target, "__module__", "") or "")
    return bool(getattr(mod, "__file__", None)) and is_project(mod.__file__)


def _returns_handles(obj, is_project, seen) -> bool:
    """A test-side builder whose every returned value comes from project code (ids, created objects)."""
    if obj.__code__ in seen:
        return False
    try:
        node = _adapter_tree(obj)
    except (OSError, TypeError, SyntaxError, IndexError):
        return False
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    made = _handles(node, obj.__globals__, is_project, (*seen, obj.__code__), set())
    rets = [r.value for r in ast.walk(node) if isinstance(r, ast.Return)]
    if not rets:
        return False

    def handle(e) -> bool:
        if e is None or (isinstance(e, ast.Constant) and e.value is None):
            return True
        if isinstance(e, ast.Tuple):
            return all(handle(x) for x in e.elts)
        if isinstance(e, ast.Name):
            return e.id in made
        return isinstance(e, ast.Call) and _handle_call(e, obj.__globals__, is_project, (*seen, obj.__code__), made)
    return all(handle(e) for e in rets)


def _handle_call(call, g, is_project, seen, made) -> bool:
    """The call returns something project code made: a project function or class, a method of a
    handle, or a test-side builder that returns only such things."""
    if isinstance(call.func, ast.Attribute) and _root(call.func) in made:
        return True
    obj = _resolve(call.func, g)
    if obj is None:
        return False
    if _project_obj(obj, is_project):
        return True
    obj = inspect.unwrap(obj) if callable(obj) else obj
    return inspect.isfunction(obj) and _returns_handles(obj, is_project, seen)


def _handles(fnode, g, is_project, seen, fn_like: set) -> set:
    """Names bound to what project code made (fixpoint over the function's assignments)."""
    made: set = set()
    changed = True
    while changed:
        changed = False
        for n in ast.walk(fnode):
            if not isinstance(n, ast.Assign) or id(n.value) in fn_like:
                continue
            v = n.value
            while isinstance(v, (ast.Subscript, ast.Attribute)) and not isinstance(v, ast.Call):
                v = v.value
            ok = (isinstance(v, ast.Call) and id(v) not in fn_like and _handle_call(v, g, is_project, seen, made)) or \
                (isinstance(v, ast.Name) and v.id in made)
            if ok:
                new = {x.id for t in n.targets for x in ast.walk(t) if isinstance(x, ast.Name)} - made
                if new:
                    made |= new
                    changed = True
    return made


def _helper(call, case, fns, g, is_project, seen) -> str | None:
    """None when the helper that receives fn is clean (it then acts like fn), else why it decides."""
    obj = _resolve(call.func, g)
    obj = inspect.unwrap(obj) if callable(obj) else obj
    name = ast.unparse(call.func)
    if not inspect.isfunction(obj):
        return None   # a builtin or class that receives fn (partial, map): it only passes fn on
    if is_project is not None and is_project(obj.__code__.co_filename):
        return None   # project code that receives fn is the code under test, not adapter logic
    if obj.__code__ in seen:
        return None   # a helper already being read (recursion): its own reading decides
    try:
        hnode = _adapter_tree(obj)
    except (OSError, TypeError, SyntaxError, IndexError):
        return f"passes fn to {name}, whose source cannot be read"
    if not isinstance(hnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    hp = [a.arg for a in hnode.args.posonlyargs + hnode.args.args]
    hcase, hfns = set(), set()
    pairs = list(zip(hp, call.args)) + [(k.arg, k.value) for k in call.keywords if k.arg in hp]
    for p, a in pairs:
        if isinstance(a, ast.Name) and a.id in fns:
            hfns.add(p)
        elif any(isinstance(x, ast.Name) and x.id in case for x in ast.walk(a)):
            hcase.add(p)
    why = _decides(hnode, hcase, hfns, obj.__globals__, is_project, (*seen, obj.__code__))
    return f"helper {name} {why}" if why else None


def _decides(fnode, case: set, fns: set, g, is_project, seen) -> str:
    calls = [n for n in ast.walk(fnode) if isinstance(n, ast.Call)]
    fn_like = set()
    for n in calls:   # calls of fn, and of helpers that receive fn and are clean
        if isinstance(n.func, ast.Name) and n.func.id in fns:
            fn_like.add(id(n))
        elif any(isinstance(a, ast.Name) and a.id in fns for a in list(n.args) + [k.value for k in n.keywords]):
            why = _helper(n, case, fns, g, is_project, seen)
            if why:
                return why
            fn_like.add(id(n))
    args_of = [a for n in calls if id(n) in fn_like for a in list(n.args) + [k.value for k in n.keywords]]
    zone = {id(x) for a in args_of for x in _exprs(a)}              # inputs built for fn
    result = {id(x) for n in calls if id(n) in fn_like for x in _exprs(n)}
    assigns = []
    for n in ast.walk(fnode):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and n.value is not None:
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            assigns.append(({x.id for t in targets for x in ast.walk(t) if isinstance(x, ast.Name)}, n.value))
        elif isinstance(n, ast.NamedExpr):
            assigns.append(({n.target.id}, n.value))
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            assigns.append(({x.id for x in ast.walk(n.target) if isinstance(x, ast.Name)}, n.iter))
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if item.optional_vars is not None:
                    assigns.append(({x.id for x in ast.walk(item.optional_vars) if isinstance(x, ast.Name)},
                                    item.context_expr))
        elif isinstance(n, ast.comprehension):   # [n for n in fn(...)]: n is an element of the result
            assigns.append(({x.id for x in ast.walk(n.target) if isinstance(x, ast.Name)}, n.iter))
    stored = {x.id for x in ast.walk(fnode) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)} | \
        {a.arg for a in fnode.args.posonlyargs + fnode.args.args + fnode.args.kwonlyargs}

    def mutable(name) -> bool:   # a local, or a global object fn can change (not TODAY, not a number)
        return name in stored or (name in g and not isinstance(g[name], IMMUTABLE) and
                                  not inspect.isfunction(g[name]) and not inspect.isclass(g[name]) and
                                  not inspect.ismodule(g[name]) and type(g[name]).__module__ != "datetime" and
                                  type(g[name]).__name__ != "Decimal")
    res = {r for a in args_of if (r := _root(a)) and r not in case and mutable(r)}   # what fn received and may change
    taint = set(case)
    changed = True
    while changed:
        changed = False
        for names, val in assigns:
            has_r = any(id(x) in result or (isinstance(x, ast.Name) and x.id in res) for x in _exprs(val))
            has_c = any(isinstance(x, ast.Name) and x.id in taint for x in ast.walk(val))
            new = names - (res if has_r else taint) if (has_r or has_c) else set()
            if new:
                (res if has_r else taint).update(new)
                changed = True
    cnames = (taint - res) | case                                    # names that carry the case only
    loads = [x for x in ast.walk(fnode) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)]
    pure = taint - case                                              # case-built inputs used only for fn
    while True:
        inside = {id(x) for names, val in assigns if names and names <= pure for x in _exprs(val)}
        drop = {x.id for x in loads if x.id in pure and id(x) not in zone and id(x) not in inside}
        if not drop:
            break
        pure -= drop
    zone |= {id(x) for names, val in assigns if names and names <= pure for x in _exprs(val)}

    allowed: set = set()   # tests that only choose how to build the inputs, and selections (filled below)
    handles = _handles(fnode, g, is_project, seen, fn_like) - res

    def from_result(e) -> bool:
        return any(id(x) in result or (isinstance(x, ast.Name) and x.id in res) for x in _exprs(e))

    def handle_side(e) -> bool:   # reads the case only through handles project code made
        names = {x.id for x in ast.walk(e) if isinstance(x, ast.Name)}
        return bool(names & handles) and not (names & ((taint - handles) | case)) and not from_result(e)
    for n in ast.walk(fnode):   # selection: the result's element whose id or key is this handle
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], SELECT):
            a, b = n.left, n.comparators[0]
            if (handle_side(a) and from_result(b)) or (handle_side(b) and from_result(a)):
                allowed |= {id(x) for x in _exprs(n)}

    def reads(e) -> bool:
        return any(isinstance(x, ast.Name) and x.id in cnames and id(x) not in zone and id(x) not in result
                   and id(x) not in allowed for x in ast.walk(e))
    returns = [n for n in ast.walk(fnode) if isinstance(n, ast.Return)]
    first_call = min((n.lineno for n in calls if id(n) in fn_like), default=None)
    ret_names = {x.id for r in returns if r.value is not None for x in ast.walk(r.value) if isinstance(x, ast.Name)}

    def assigns_in(stmts):
        return {x.id for s in stmts for n in ast.walk(s) if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign))
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                for x in ast.walk(t) if isinstance(x, ast.Name)}

    def calls_fn(nodes):
        return any(isinstance(x, ast.Call) and id(x) in fn_like for n in nodes for x in ast.walk(n))
    for n in ast.walk(fnode):
        if isinstance(n, (ast.If, ast.While)):
            branch = n.body + n.orelse
            before_fn = first_call is not None and n.end_lineno < first_call   # it builds what fn will get
            if not any(isinstance(x, (ast.Return, ast.Raise)) for s in branch for x in ast.walk(s)) and \
                    (before_fn or not (assigns_in(branch) & ret_names)):
                allowed |= {id(x) for x in _exprs(n.test)}
        elif isinstance(n, ast.IfExp) and calls_fn([n.body]) and calls_fn([n.orelse]):
            allowed |= {id(x) for x in _exprs(n.test)}
    for n in ast.walk(fnode):
        if id(n) in zone or id(n) in result or id(n) in allowed:
            continue
        test = None
        if isinstance(n, (ast.Compare, ast.BoolOp)) or (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)):
            test = n
        elif isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            test = n.test
        elif isinstance(n, ast.Match):
            test = n.subject
        if test is not None and id(test) not in allowed and reads(test):
            return f"compares {ast.unparse(test)[:50]}"
    for r in returns:
        if r.value is not None and reads(r.value):
            return f"returns {ast.unparse(r.value)[:50]}, read from the case, not from fn"

    def project_state(e) -> bool:   # reads project state fn may have changed (a project module's store)
        return any(isinstance(x, ast.Name) and _project_obj(g.get(x.id), is_project) for x in ast.walk(e))
    for r in returns:   # an answer computed with neither fn's result nor anything fn received
        v = r.value
        if v is None or isinstance(v, ast.Constant) or not fns or not fn_like:
            continue
        names = {x.id for x in ast.walk(v) if isinstance(x, ast.Name)}
        if all(x in g and not callable(g[x]) for x in names) and not any(isinstance(x, ast.Call) for x in ast.walk(v)):
            continue   # a named constant: the constant-answer check below reads it
        if not from_result(v) and not project_state(v) and not (names & handles) and not calls_fn([v]):
            return f"returns {ast.unparse(v)[:50]}, which does not come from fn"

    def guarded(target) -> bool:   # a constant answer chosen by fn's result or by fn raising
        for n in ast.walk(fnode):
            if isinstance(n, ast.Try) and calls_fn(n.body) and \
                    any(x is target for s in n.body + [h for hd in n.handlers for h in hd.body] + n.orelse
                        for x in ast.walk(s)):
                return True
            if isinstance(n, (ast.If, ast.IfExp)) and any(id(x) in result or (isinstance(x, ast.Name) and x.id in res)
                                                          for x in _exprs(n.test)) and \
                    any(x is target for s in ([n.body, n.orelse] if isinstance(n, ast.IfExp) else n.body + n.orelse)
                        for x in ast.walk(s)):
                return True
        return False
    for r in returns:
        v = r.value
        const = v is None or isinstance(v, ast.Constant) or (isinstance(v, ast.Name) and v.id in ("True", "False", "None"))
        if const and fns and not guarded(r):
            return f"returns {ast.unparse(v) if v is not None else 'None'} whatever fn does"
    return ""
