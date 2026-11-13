"""Literal folding and source-field normalization for decision-site signatures."""
from __future__ import annotations
import ast
import builtins
import math
import re
from fractions import Fraction
from functools import lru_cache

UNIT = {"days": 86400, "seconds": 1, "total_seconds": 1, "microseconds": 1e-6}



TD = {"days": 86400, "seconds": 1, "microseconds": 1e-6, "milliseconds": 1e-3, "minutes": 60,
      "hours": 3600, "weeks": 604800}



NAME_UNIT = [(r"(^|_)weeks?($|_)", 604800), (r"(^|_)days?($|_)", 86400), (r"(^|_)hours?($|_)", 3600),
             (r"(^|_)(minutes?|mins?)($|_)", 60), (r"(^|_)(seconds?|secs?|ts|timestamp|epoch)($|_)", 1)]



GENERIC = {"0", "1", "-1", "2"}          # x > 0, len(x) == 1: too common to say much



BUILTIN_NAMES = set(dir(builtins))



def norm(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", str(name)).lower()
    return re.sub(r"[^a-z0-9_]+", "_", s).strip("_")



@lru_cache(maxsize=20000)
def expr(src: str):
    return ast.parse(src, mode="eval").body



def num(v) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.6g}"



def fold(node, env: dict, lex: dict, depth: int = 0):
    """Constant value of an expression: ('num', v), ('dur', seconds), ('str', s), ('set', items) or None."""
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or v is None:
            return None
        return ("num", v) if isinstance(v, (int, float)) else ("str", v) if isinstance(v, str) else None
    if isinstance(node, ast.Name):
        if node.id in lex and depth < 4:
            return fold(expr(lex[node.id]), env, lex, depth + 1)
        return env.get(node.id)
    if isinstance(node, ast.Attribute) and node.attr.isupper():   # pricing.LIMIT before a bare LIMIT
        return env.get(ast.unparse(node), env.get(node.attr))
    if isinstance(node, ast.Dict):   # POLICY = {"grace_days": 3}: a constant table
        if node.keys and all(k is not None and _map_key(k) is not None for k in node.keys):
            # fg2 addition: a key written as a name (`Provider.OPENAI: "KWP_OPENAI_KEY"`, an Enum member) is kept
            # as ("expr", its text), so the table still folds and a lookup by that same name finds its value
            return ("map", tuple((_map_key(k), fold(v, env, lex, depth)) for k, v in zip(node.keys, node.values)))
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args \
            and node.keywords and all(k.arg for k in node.keywords):   # fg2 addition: dict(openai="KWP_...")
        return ("map", tuple((k.arg, fold(k.value, env, lex, depth)) for k in node.keywords))
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Dict) \
            and (node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")) in \
            ("MappingProxyType", "OrderedDict", "frozendict", "dict"):   # fg2 addition: a read-only view of a table
        return fold(node.args[0], env, lex, depth)
    if isinstance(node, ast.Subscript) and _map_key(node.slice) is not None:   # POLICY["grace_days"], T[Provider.X]
        table = fold(node.value, env, lex, depth)
        if table and table[0] == "map":
            key = _map_key(node.slice)
            return next((v for k, v in table[1] if k == key), None)
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        r = fold(node.operand, env, lex, depth)
        return (r[0], -r[1]) if r and r[0] in ("num", "dur") else None
    if isinstance(node, ast.BinOp):
        a, b = fold(node.left, env, lex, depth), fold(node.right, env, lex, depth)
        if not (a and b) or {a[0], b[0]} - {"num", "dur"}:
            return None
        kinds = {a[0], b[0]}
        if isinstance(node.op, (ast.Add, ast.Sub)) and len(kinds) == 1:
            return (a[0], a[1] + b[1] if isinstance(node.op, ast.Add) else a[1] - b[1])
        if isinstance(node.op, ast.Mult) and kinds != {"dur"}:
            return ("dur" if "dur" in kinds else "num", a[1] * b[1])
        if isinstance(node.op, (ast.Div, ast.FloorDiv)) and b[0] == "num" and b[1]:
            return (a[0], a[1] / b[1] if isinstance(node.op, ast.Div) else a[1] // b[1])
        if kinds == {"num"} and isinstance(node.op, (ast.Pow, ast.LShift)) and isinstance(b[1], int) \
                and 0 <= b[1] <= 64:   # fg2 addition: 1024 ** 3 and 1 << 30 are 1 GiB
            return ("num", a[1] ** b[1] if isinstance(node.op, ast.Pow) else int(a[1]) << b[1])
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)) and \
            (node.func.id if isinstance(node.func, ast.Name) else node.func.attr) == "timedelta":
        vals = [(k, fold(v, env, lex, depth)) for k, v in zip(TD, node.args)]
        vals += [(k.arg, fold(k.value, env, lex, depth)) for k in node.keywords]
        if all(v and v[0] == "num" and k in TD for k, v in vals):
            return ("dur", sum(TD[k] * v[1] for k, v in vals))
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)) and len(node.args) == 1 \
            and (node.func.id if isinstance(node.func, ast.Name) else node.func.attr) in ("Decimal", "Fraction") \
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, (str, int, float)):
        try:   # Decimal("50.00") is the amount 50.00; a text that is not a number folds to nothing
            return ("num", float(Fraction(str(node.args[0].value))))
        except (ValueError, ZeroDivisionError):
            return None
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        items = [fold(e, env, lex, depth) for e in node.elts]
        return ("set", tuple(i[1] for i in items)) if all(items) else None
    return None



# The sealed environments' constant folding (design 4.5): one operation at a time, bounded and fail-closed.
FOLD_EXPONENT, FOLD_NUMBER, FOLD_TEXT = 64, 2 ** 256, 10_000
FOLD_OPERATORS = ('+', '-', '*', '/', '//', '%', '**')



def fold_step(operator, operands, *, javascript=False):
    """One operation of a sealed constant's right side, computed without running code: `operator` is one of
    FOLD_OPERATORS with two operands, or `+`/`-` with one (a sign). An operand is an int, float or str; with
    `javascript` a float or str, as JavaScript numbers are doubles, and `//` is no operator. Returns (value, '')
    or (None, why it is not folded). Not folded: an exponent outside -64..64, a number above 2**256, a text over
    10,000 characters, a result that is not finite, and what the language refuses or computes differently (a
    division by zero, a string with a number, `%` of a text; in JavaScript a sign, `-`, `*`, `/`, `%` or `**` of a
    text, a fractional exponent, or a power whose double is not exact, as V8 does not round those correctly)."""
    numbers = (float,) if javascript else (int, float)
    if operator not in FOLD_OPERATORS or javascript and operator == '//' or len(operands) not in (1, 2) \
            or len(operands) == 1 and operator not in ('+', '-'):
        raise ValueError(f'fold_step has no operation {operator} of {len(operands)} operands')
    def kind(item):
        return ('number' if type(item) is float else 'string' if type(item) is str else type(item).__name__) \
            if javascript else type(item).__name__
    refused = (None, 'cannot fold ' + (f'{operator}{kind(operands[0])}' if len(operands) == 1
                                      else f'{kind(operands[0])} {operator} {kind(operands[1])}'))
    if any(type(item) not in (*numbers, str) for item in operands):
        return refused
    for item in operands:
        if type(item) is int and abs(item) > FOLD_NUMBER:
            return None, 'a number above 2**256'
        if type(item) is float and not math.isfinite(item):
            return None, 'a number that is not finite'
    texts = [type(item) is str for item in operands]
    if len(operands) == 1:
        if texts[0]:
            return refused
        value = operands[0] if operator == '+' else -operands[0]
    elif any(texts):
        left, right = operands
        if operator == '+' and all(texts):
            if len(left) + len(right) > FOLD_TEXT:
                return None, f'text is longer than {FOLD_TEXT} characters'
            return left + right, ''
        if operator == '*' and not javascript and texts.count(True) == 1 and int in (type(left), type(right)):
            text, times = (left, right) if texts[0] else (right, left)
            if len(text) * max(times, 0) > FOLD_TEXT:
                return None, f'text is longer than {FOLD_TEXT} characters'
            return text * times, ''
        return refused
    else:
        left, right = operands
        if operator in ('/', '//', '%') and right == 0:
            return None, 'divides by zero'
        if operator == '**':
            value, why = _power(left, right, javascript)
            if why:
                return None, why
        elif operator == '%' and javascript:
            value = math.fmod(left, right)      # JavaScript's remainder keeps the dividend's sign
        elif operator == '+':
            value = left + right
        elif operator == '-':
            value = left - right
        elif operator == '*':
            value = left * right
        elif operator == '/':
            value = left / right
        elif operator == '//':
            value = left // right
        else:
            value = left % right
    if type(value) is float and not math.isfinite(value):
        return None, 'result is not finite'
    if type(value) not in numbers:
        return None, 'result is not a real number'
    if abs(value) > FOLD_NUMBER:
        return None, 'result is above 2**256'
    return value, ''



def _shown(number):
    """A number of a folding reason: a whole one as written (300, not 300.0), a long one with six digits."""
    return str(int(number)) if float(number).is_integer() and abs(number) < 1e16 else f'{number:.6g}'



def _power(left, right, javascript):
    """(left ** right, '') for fold_step, or (None, why). The magnitude is bounded before anything is computed."""
    if right > FOLD_EXPONENT:
        return None, f'exponent {_shown(right)} is above {FOLD_EXPONENT}'
    if right < -FOLD_EXPONENT:
        return None, f'exponent {_shown(right)} is below -{FOLD_EXPONENT}'
    if javascript and not right.is_integer():
        return None, f'exponent {_shown(right)} is not a whole number'
    if left == 0:
        return (None, 'divides by zero') if right < 0 else (left ** right, '')
    if left < 0 and type(right) is float and not right.is_integer():
        return None, 'result is not a real number'
    if math.log2(abs(left)) * right > math.log2(FOLD_NUMBER) + 1:
        return None, 'result is above 2**256'
    if not javascript:
        return left ** right, ''
    exact = Fraction(left) ** int(right)
    value = float(exact)
    if Fraction(value) != exact:
        return None, f'{_shown(left)} ** {_shown(right)} is not exact in floating point'
    return value, ''



def _map_key(node):
    """A table key: a str or int literal, or ("expr", text) for a dotted name such as an Enum member."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (str, int)) and not isinstance(node.value, bool) else None
    if isinstance(node, (ast.Name, ast.Attribute)):
        text = ast.unparse(node)
        return ("expr", text) if all(part.isidentifier() for part in text.split(".")) else None
    return None



def names_in(node, env: dict, lex: dict, depth: int = 0) -> set:
    """Normalised data names an expression reads (locals expanded, constants and units left out)."""
    out = set()
    receivers = {id(n.value) for n in ast.walk(node) if isinstance(n, (ast.Attribute, ast.Subscript))}
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and id(n) not in receivers and n.id not in env:
            if n.id in lex and depth < 4:
                out |= names_in(expr(lex[n.id]), env, lex, depth + 1)
            elif not n.id.isupper():
                out.add(norm(n.id))
        elif isinstance(n, ast.Attribute) and n.attr not in UNIT and not n.attr.isupper():
            out.add(norm(n.attr))
        elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            out.add(norm(n.slice.value))
    called = {norm(n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id) for n in ast.walk(node)
              if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
    return out - called - BUILTIN_NAMES - {"timedelta", "date", "datetime"}



def unit_of(node, names: set, lex: dict, depth: int = 0) -> float | None:
    if isinstance(node, ast.Attribute) and node.attr in UNIT:
        return UNIT[node.attr]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in UNIT:
        return UNIT[node.func.attr]
    if isinstance(node, ast.Name) and node.id in lex and depth < 4:
        u = unit_of(expr(lex[node.id]), names, lex, depth + 1)
        if u:
            return u
    for pat, u in NAME_UNIT:
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)) and any(re.search(pat, n) for n in names):
            return u
    return None



def dur_inside(node, env: dict, lex: dict, depth: int = 0) -> float | None:
    """A constant duration added to or subtracted from a date inside an expression."""
    r = fold(node, env, lex, depth)
    if r and r[0] == "dur":
        return r[1]
    if isinstance(node, ast.Name) and node.id in lex and depth < 4:
        return dur_inside(expr(lex[node.id]), env, lex, depth + 1)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        return dur_inside(node.left, env, lex, depth) or dur_inside(node.right, env, lex, depth)
    return None



def scalar(node, env: dict, lex: dict):
    """fold() for one side of a comparison: a constant table is not a value to compare with."""
    r = fold(node, env, lex)
    return r if r and r[0] != "map" else None



def span(seconds: float) -> str:
    for unit, size in (("days", 86400), ("hours", 3600), ("minutes", 60)):
        if seconds >= size and seconds % size == 0:
            return f"{num(seconds / size)} {unit}"
    return f"{num(seconds)} s"



GENERIC_SHARE = 0.15   # a name part in more than this share of a repository's functions names nothing



def name_parts(name: str) -> list[str]:
    parts = [p for p in name.split("_") if len(p) > 2]
    cjk = re.findall(r"[\u4e00-\u9fff]", name)
    return parts + [a + b for a, b in zip(cjk, cjk[1:])]



CLOCK = re.compile(r"^(today|now|utcnow|clock|now_\w+|\w+_now|today_\w+|\w+_today|current_(time|date|day|ts))$")



VALUES = {"timedelta", "relativedelta", "date", "datetime", "Decimal", "Fraction", "parse_day", "fromisoformat"}



def data_names(node, env: dict, lex: dict, depth: int = 0) -> set:
    """What a comparison side is about: its data names, without the clock. A side that is the result of a
    call (`billing.balance(store, member_id) > 50`, also through a local `owed = ...`) is about that
    call (`balance`), not about the arguments it happens to pass."""
    while isinstance(node, ast.Name) and node.id in lex and depth < 4:
        node, depth = expr(lex[node.id]), depth + 1
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in WRAPPERS and node.args:
        node = node.args[0]
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        if name not in VALUES and name not in UNIT and name not in BUILTIN_NAMES:
            return {norm(name)}
    return {n for n in names_in(node, env, lex) if not CLOCK.match(n)}



def constant_like(node) -> bool:
    """LIMIT, Limits.GRACE_DAYS, _POLICY["days"]: written as a constant, whatever its value is."""
    if isinstance(node, ast.Name):
        return len(node.id.strip("_")) > 1 and node.id.strip("_").isupper()
    if isinstance(node, ast.Attribute):
        return len(node.attr.strip("_")) > 1 and node.attr.strip("_").isupper()
    if isinstance(node, ast.Subscript):
        return isinstance(node.slice, ast.Constant) and constant_like(node.value)
    return False


WRAPPERS = {"len", "abs", "int", "float", "round", "str", "bool", "list", "sorted", "set", "tuple", "sum"}
