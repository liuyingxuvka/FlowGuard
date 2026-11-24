"""Plain words for static candidate ranking; no query language."""
import re
import ast
import operator
from collections import Counter


class Rows(list):
    """Fixed query rows, optionally excluding the declared owner module."""
    def outside(self, module):
        return Rows(row for row in self if row['node'].partition(':')[0] != module)




def numeric_atoms(node):
    """Only literal arithmetic; names and calls are never evaluated."""
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                  ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}

    def value(item):
        if isinstance(item, ast.Constant) and type(item.value) in (int, float):
            return item.value
        if isinstance(item, ast.UnaryOp) and type(item.op) in operations:
            return operations[type(item.op)](value(item.operand))
        if isinstance(item, ast.BinOp) and type(item.op) in operations:
            return operations[type(item.op)](value(item.left), value(item.right))
        raise ValueError('not literal arithmetic')

    result = set()
    def read(item):
        if isinstance(item, (ast.List, ast.Tuple, ast.Set)):
            for child in item.elts:
                read(child)
        elif isinstance(item, ast.Dict):
            for child in (*item.keys,*item.values):
                read(child)
        else:
            try:
                result.add(value(item))
            except (ValueError, TypeError, ArithmeticError):
                pass  # Calls and subscript indices are not literal table entries.
    read(node)
    return sorted(result)


def handler_outcome(statements, in_loop=False):
    """Whether a handler can finish normally or leave without raising.

    This shared syntax check replaces each repository's copy. It is conservative
    for loop entry and match exhaustiveness and never executes the handler.
    """
    falls, leaves = True, False
    for node in statements:
        if not falls:
            break
        branch = lambda body, loop=in_loop: handler_outcome(body, loop)
        if isinstance(node, ast.Raise):
            falls = False
        elif isinstance(node, ast.Return):
            falls, leaves = False, True
        elif isinstance(node, (ast.Break, ast.Continue)):
            falls, leaves = False, leaves or not in_loop
        elif isinstance(node, ast.If):
            first, second = branch(node.body), branch(node.orelse)
            falls, leaves = first[0] or second[0], leaves or first[1] or second[1]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            falls, extra = branch(node.body)
            leaves |= extra
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            leaves |= branch(node.body, True)[1] or branch(node.orelse)[1]
        elif isinstance(node, (ast.Try, getattr(ast, 'TryStar', ast.Try))):
            body, other = branch(node.body), branch(node.orelse)
            falls, extra = body[0] and other[0], body[1] or other[1]
            for handler in node.handlers:
                handled = branch(handler.body)
                falls, extra = falls or handled[0], extra or handled[1]
            if node.finalbody:
                final = branch(node.finalbody)
                falls, extra = falls and final[0], extra or final[1]
            leaves |= extra
        elif isinstance(node, ast.Match):
            leaves |= any(branch(case.body)[1] for case in node.cases)
    return falls, leaves


def exit_may_suppress(function):
    """Only an exit method returning None/False on every explicit return is quiet-safe."""
    if isinstance(function, ast.Lambda):
        values = [function.body]
    else:
        values, stack = [], list(function.body)
        while stack:
            node = stack.pop()
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):
                continue
            if isinstance(node,ast.Return):
                values.append(node.value)
            stack.extend(ast.iter_child_nodes(node))
    return any(value is not None and not (isinstance(value,ast.Constant) and value.value in (None,False)) for value in values)


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SOME_PATHS = (ast.Try, getattr(ast, 'TryStar', ast.Try), ast.Assert, getattr(ast, 'TypeAlias', ast.Assert), *_SCOPES)
_WITH = (ast.With, ast.AsyncWith)


def _returns(node):
    """Whether `node` holds a return of the function it is in (none of a nested def, lambda or class)."""
    stack = [] if isinstance(node, _SCOPES) else [node]
    while stack:
        item = stack.pop()
        if isinstance(item, ast.Return):
            return True
        stack.extend(child for child in ast.iter_child_nodes(item) if not isinstance(child, _SCOPES))
    return False


def _suppressing(node, suppresses):
    """Whether `node` holds a with statement of the function it is in whose context manager may suppress an error of
    its block (`suppresses`)."""
    stack = [] if isinstance(node, _SCOPES) else [node]
    while stack:
        item = stack.pop()
        if isinstance(item, _WITH) and any(suppresses(part.context_expr) for part in item.items):
            return True
        stack.extend(child for child in ast.iter_child_nodes(item) if not isinstance(child, _SCOPES))
    return False


def _always_parts(node, suppresses):
    """The children of `node` that run whenever it does; a statement list is one child. Of an if or while its test, of
    a for its iterable, of a match its subject, of and/or its first operand, of a chained comparison its first two
    operands, of a comprehension its first iterable and of an annotated assignment its target and value (a local
    name's annotation is never evaluated); nothing of a try, assert, type alias, nested def, lambda or class; of a with
    its items, and its block too unless the context manager of an item may suppress an error of it (`suppresses`); all
    of any other node."""
    if isinstance(node, (ast.If, ast.While, ast.IfExp)):
        return [node.test]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.iter]
    if isinstance(node, ast.BoolOp):
        return node.values[:1]
    if isinstance(node, ast.Compare):
        return [node.left, *node.comparators[:1]]
    if isinstance(node, ast.Match):
        return [node.subject]
    if isinstance(node, _COMPREHENSIONS):
        return [node.generators[0].iter]
    if isinstance(node, ast.AnnAssign):
        return [node.target, *([node.value] if node.value is not None else [])]
    if isinstance(node, _SOME_PATHS):
        return []
    if isinstance(node, _WITH):
        return [*node.items, *([] if any(suppresses(part.context_expr) for part in node.items) else [node.body])]
    return list(ast.iter_child_nodes(node))


def on_every_path(function, found, suppresses):
    """Whether a node of `function` (an ast def) that `found` accepts runs whenever the function returns: in a
    statement of its body or of a with block in it, outside the branches of an if/elif/else, for, while,
    try/except/finally, match, assert, conditional expression, and/or and chained comparison (`_always_parts`),
    inside no comprehension, lambda, nested def or class, and after no statement that holds a return. A with whose
    context manager may suppress an error of its block (`suppresses`, asked of each item's context manager: the
    block may stop at any of its statements and the function go on after it) runs neither its block nor, read
    conservatively, what follows it. A raise ends on an error path, not a return, so a guard that raises leaves the
    node on every path."""
    def reached(item):
        if isinstance(item, list):
            for statement in item:
                if reached(statement):
                    return True
                if _returns(statement) or _suppressing(statement, suppresses):
                    return False
            return False
        return found(item) or any(reached(child) for child in _always_parts(item, suppresses))
    return reached(function.body)


def anywhere(function, found):
    """Whether `function` (an ast def) holds a node that `found` accepts on any path, in a nested def, lambda or
    comprehension too: where `on_every_path` says no, whether the node is there at all."""
    return any(found(node) for node in ast.walk(function) if node is not function)


def calls(node, name):
    """Whether `node` is a call of `name` (`name(...)` or `x.name(...)`). A call under another name (an import
    alias) is not one of `name`."""
    callee = node.func if isinstance(node, ast.Call) else None
    return isinstance(callee, ast.Name) and callee.id == name or isinstance(callee, ast.Attribute) and callee.attr == name


def call_on_every_path(function, name, suppresses):
    """Whether `function` (an ast def) calls `name` (`calls`) where the call runs whenever the function returns
    (`on_every_path`)."""
    return on_every_path(function, lambda node: calls(node, name), suppresses)


def assigns(node, line, field):
    """Whether `node` is an assignment statement on `line` whose target writes `field` (`x.field = ...`,
    `x['field'] = ...`, one of a tuple's), the place of a Python write row (`MapHandle.writes`)."""
    if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) or node.lineno != line:
        return False
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return any(isinstance(part, ast.Attribute) and part.attr == field
               or isinstance(part, ast.Subscript) and isinstance(part.slice, ast.Constant) and part.slice.value == field
               for target in targets for part in ast.walk(target))


NEVER_SUPPRESS = frozenset({'open'})     # built-ins whose context manager never suppresses, called by their bare name


def bindings(tree):
    """{name: how often} of the names `tree` (a module's ast) binds, in any of its scopes: a def's or class's name, a
    target an assignment, for, with, walrus or del binds, a parameter, an import's name, an except's name, a match
    pattern's capture and a global or nonlocal declaration; '*' counts the star imports, which may bind any name."""
    found = Counter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found[node.name] += 1
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            found[node.id] += 1
        elif isinstance(node, ast.arg):
            found[node.arg] += 1
        elif isinstance(node, ast.alias):
            found['*' if node.name == '*' else node.asname or node.name.partition('.')[0]] += 1
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            found[node.name] += 1
        elif isinstance(node, ast.MatchMapping) and node.rest:
            found[node.rest] += 1
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            found.update(node.names)
    return found


def may_suppress(lines, names, held, never, bound):
    """The question `on_every_path` asks of a with item's context manager (an ast expression): whether it may suppress
    an error of its block, as the map's handlers read the project's production code. A call is read as not
    suppressing only where the reader sees that it never does: the built-in `open(...)` (NEVER_SUPPRESS) called by its
    bare name where the module binds no name of it and has no star import (`bound`, its `bindings`; `x.open(...)` is
    another function), or a call `never` accepts (the caller's reading of the definition the call reaches: the
    project's own class whose `__exit__` never returns a true value, its `@contextmanager` generator that holds no
    quiet handler). Any other call may suppress: one on one of `lines` (where the map has a `contextlib.suppress(...)`
    call, under any name), one of `names` (a class whose `__exit__` may return a true value, `exit_may_suppress`, or a
    function holding a handler that can end without raising or a suppress, which a `@contextmanager` generator that
    swallows the error at its yield is), a `contextlib.ExitStack()`, which suppresses whatever a context manager
    entered on it suppresses, and any call whose definition the reader does not reach (a library's,
    `lock.acquire_timeout()`, `self.session.begin()` where the project defines a `begin` too, or a function that
    returns a context manager). Any other expression (`with lock:`, `with self._guard:`) may suppress where `held`
    (the project has such a class or keeps a suppress object outside a with): the object it holds may be one; where
    not, it is read as not suppressing, though it may hold a library's context manager that does."""
    def suppresses(expression):
        if isinstance(expression, ast.Call):
            callee = expression.func
            name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else None
            if expression.lineno in lines or name in names:
                return True
            if isinstance(callee, ast.Name) and name in NEVER_SUPPRESS and not bound[name] and not bound['*']:
                return False
            return not never(expression)
        return held
    return suppresses


_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")


def tokens(text):
    """Query words: each ASCII run whole (as before) plus its camelCase parts.

    Punctuation, '_' and '-' already separated words; `countWorkingDays` now also
    gives `count`, `working`, `days`, so a phrase finds a camelCase name.
    """
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    for run in re.findall(r"[A-Za-z0-9]+", text):
        words.update(part.lower() for part in _CAMEL.findall(run))
    words = {w for w in words if len(w) > 2}
    cjk = re.findall(r"[一-鿿]", text)
    return words | {a + b for a, b in zip(cjk, cjk[1:])}


def may_share(words, text):
    """False only when tokens(text) has none of `words`, decided without splitting `text`.

    Every ASCII word of tokens(text) is a piece of text.lower(), and every other word is a pair of
    CJK characters that both occur in text: a text without such a piece or pair cannot give one."""
    lowered = None
    for word in words:
        if word.isascii():
            lowered = text.lower() if lowered is None else lowered
            if word in lowered:
                return True
        elif all(character in text for character in word):
            return True
    return False
