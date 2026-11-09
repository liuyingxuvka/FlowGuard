"""Plain words for static candidate ranking; no query language."""
import re
import ast
import operator


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
