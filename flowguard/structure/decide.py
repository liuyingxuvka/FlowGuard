"""Fold source decisions to identity, field, version and literal-set signatures."""
from __future__ import annotations

import ast
import hashlib
import json
import re

from . import features as ff
from . import analysis as fgs

FLIP = {"Lt": "Gt", "Gt": "Lt", "LtE": "GtE", "GtE": "LtE", "Eq": "Eq", "NotEq": "NotEq"}
SET_ITEMS, ITEM_CHARS, VALUE_CHARS = 64, 60, 200    # stored values stay valid JSON within these sizes
BIG = 1000                                          # a site constant at least this large is a decision value
VERSION = re.compile(r"^v?(\d+)\.(\d+)(\.\d+){0,2}([abc]|rc|\.dev|\.post|\+)?\w*$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")
ORDERED = ("Lt", "Gt", "LtE", "GtE")


def _expr(text: str):
    try:
        return ff.expr(text)
    except SyntaxError:
        return None


def own_env(consts: list[tuple[str, str]]) -> dict:
    """{NAME or Cls.NAME: folded value} of one module, in assignment order."""
    env = {}
    for qual, src in consts:
        node = _expr(src)
        env[qual] = ff.fold(node, env, {}) if node is not None else None
    return env


def module_env(own: dict, imports: dict, env_of, canon=None) -> dict:
    """fgmap's module_envs for one module on the store: own constants, imported names
    (`from m import LIMIT`, `from m import Limits` gives Limits.X) and module aliases (`lim.LIMIT`).
    `env_of(module)` returns another module's own folded constants (or {})."""
    env = dict(own)
    for local, target in imports.items():
        if ":" in target:
            mod, _, name = target.partition(":")
            other = env_of(mod)
            value = other.get(name)
            if value is None and canon and (where := canon(mod, name)):   # re-exported by a package
                value = env_of(where.partition(":")[0]).get(where.partition(":")[2])
            if value is not None:
                env.setdefault(local, value)
            for k, v in other.items():
                if v is not None and k.startswith(name + "."):
                    env.setdefault(local + k[len(name):], v)
            sub = env_of(f"{mod}.{name}")          # from pkg import limits: limits.LIMIT
            for k, v in sub.items():
                if v is not None:
                    env.setdefault(f"{local}.{k}", v)
        else:
            for k, v in env_of(target).items():
                if v is not None:
                    env.setdefault(f"{local}.{k}", v)
                    env.setdefault(f"{target}.{k}", v)
    return env


def class_env(env: dict, cls: str, bases=()) -> dict:
    """Inside a method, `self.NAME` and `cls.NAME` are the class constants Cls.NAME, else a base's."""
    if not cls:
        return env
    extra = {}
    for owner in (*reversed(bases), cls):                 # the class's own constant wins over a base's
        head = owner + "."
        extra.update({f"{who}.{k[len(head):]}": v for k, v in env.items() if k.startswith(head) and "." not in
                      k[len(head):] for who in ("self", "cls")})
    return {**env, **extra} if extra else env


def class_bases(sig: str) -> list[str]:
    """The base classes written in a class node's signature `(Limits, Mixin)`."""
    node = _expr(f"({sig[1:-1]},)") if sig.startswith("(") and len(sig) > 2 else None
    return [ast.unparse(e) for e in node.elts] if isinstance(node, ast.Tuple) else []


def named_constant(node) -> bool:
    """fgmap's constant_like, also for one-letter names (`from pkg import G`)."""
    if isinstance(node, ast.Name):
        return node.id.strip("_").isupper()
    if isinstance(node, ast.Attribute):
        return node.attr.strip("_").isupper()
    if isinstance(node, ast.Subscript):
        return isinstance(node.slice, ast.Constant) and named_constant(node.value)
    return False


def identity(text: str, module: str, cls: str, imports: dict, own: set, lex: dict, canon, depth: int = 0,
             bases=()) -> str | None:
    """`module:NAME` (or `module:Cls.NAME`, `module:TABLE["key"]`) of the constant an expression names.
    `canon(module, dotted)` follows submodules and package re-exports to the module that assigns it."""
    node = _expr(text)
    if node is None or depth > 3:
        return None
    if isinstance(node, ast.Name) and node.id in lex and not named_constant(node):
        return identity(lex[node.id], module, cls, imports, own, lex, canon, depth + 1, bases)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and named_constant(node):
        base = identity(ast.unparse(node.value), module, cls, imports, own, lex, canon, depth + 1, bases)
        return f"{base}[{node.slice.value!r}]" if base else None
    if not named_constant(node):
        return None
    dotted = fgs.dotted(node)
    if not dotted:
        return None
    head, _, rest = dotted.partition(".")
    if head in ("self", "cls") and cls and rest:
        if f"{cls}.{rest}" in own or not bases:
            return f"{module}:{cls}.{rest}"
        for base in bases:                                # class Desk(Limits): self.GRACE is Limits.GRACE
            if (found := identity(f"{base}.{rest}", module, "", imports, own, lex, canon, depth + 1)):
                return found
        return f"{module}:{cls}.{rest}"
    if dotted in own or head in own:
        return f"{module}:{dotted}"
    target = imports.get(head)
    if target is None:
        return f"{module}:{dotted}" if not rest else None
    if ":" in target:
        mod, _, name = target.partition(":")
        return canon(mod, name + (f".{rest}" if rest else ""))
    return canon(target, rest) if rest else None


def _item(v):
    if isinstance(v, (tuple, list)) and 0 < len(v) <= 8 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                                for x in v):
        return list(v)                                    # ((3, 12), (3, 13)): a set of version tuples
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)[:ITEM_CHARS]


def _value(folded) -> tuple[str, str]:
    """(kind, JSON text) of a folded constant. A set keeps at most SET_ITEMS items and a text at most
    VALUE_CHARS characters, cut before encoding, so the stored text always parses."""
    if not folded:
        return "", ""
    kind, value = folded
    if kind == "map":
        return kind, ""
    if kind == "set":
        return kind, json.dumps([_item(v) for v in list(value)[:SET_ITEMS]])
    if isinstance(value, str):
        return kind, json.dumps(value[:VALUE_CHARS])
    return kind, json.dumps(value, default=str)


def _constant_side(node, env: dict, lex: dict) -> bool:
    """A side that is a constant: it folds, it is named like one, or it is a literal (a tuple of names such
    as `(major, minor)` is not; a tuple of literals is)."""
    if ff.scalar(node, env, lex) is not None or ff.constant_like(node) or isinstance(node, ast.Constant):
        return True
    return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and all(_constant_side(e, env, lex) for e in node.elts)


def fold_site(site: dict, env: dict, lex: dict, module: str, cls: str, imports: dict, own: set, canon,
              bases=()) -> dict:
    """One raw site oriented name-first with its constant folded and named."""
    left, op, right = site["left"], site["op"], site["right"]
    row = {"line": site["line"], "lead": site["lead"], "neg": int(site.get("neg", False)), "op": op,
           "field": left, "const": right, "vkind": "", "value": "", "identity": None, "pred": ""}
    if op == "truth":
        node = _expr(left)
        if isinstance(node, ast.Call):
            row["pred"] = fgs.dotted(node.func) or ""
        return row
    ln, rn = _expr(left), _expr(right)
    if ln is None or rn is None:
        return row
    lc = _constant_side(ln, env, lex)
    rc = _constant_side(rn, env, lex)
    if lc and not rc:
        if op in ("In", "NotIn"):                       # "key" in row: a presence test of a field
            row.update(op="has" if op == "In" else "lacks", field=right, const=left)
            row["vkind"], row["value"] = _value(ff.fold(ln, env, lex))
            return row
        row.update(op=FLIP.get(op, op), field=right, const=left)
        ln, rn = rn, ln
    if op in ("Is", "IsNot") and isinstance(rn, ast.Constant) and rn.value is None:
        row["op"] = "is None" if op == "Is" else "is not None"
        if isinstance(ln, ast.Call):
            row["pred"] = fgs.dotted(ln.func) or ""
        return row
    row["vkind"], row["value"] = _value(ff.fold(rn, env, lex))
    row["identity"] = identity(row["const"], module, cls, imports, own, lex, canon, bases=bases)
    if row["identity"] is None:                      # now > end + timedelta(days=lim.GRACE_DAYS): the named
        for side in (rn, ln):                        # constant inside either side is the site's constant
            for sub in ast.walk(side):
                if named_constant(sub) and (found := identity(ast.unparse(sub), module, cls, imports, own, lex, canon,
                                                                bases=bases)):
                    row["identity"] = found
                    return row
    return row


def version_of(value) -> str | None:
    """`3.12` for (3, 12), (3, 12, 1), "3.12.10" or "v3.12"; None for anything else."""
    if isinstance(value, (list, tuple)) and 2 <= len(value) <= 4 and all(
            isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in value) and value[0] >= 1:
        return f"{value[0]}.{value[1]}"
    if isinstance(value, str) and (m := VERSION.match(value.strip())):
        return f"{int(m.group(1))}.{int(m.group(2))}"
    return None


def boundary(op: str, v: float) -> float:
    """fgmap's boundary: `x > 17` and `x <= 17` decide at 18, `x >= 18` and `x < 18` at 18."""
    return int(v) + 1 if float(v).is_integer() and op in ("Gt", "LtE") else v








def _strings(folded) -> list[str]:
    if not folded:
        return []
    kind, value = folded
    if kind == "str":
        return [value]
    if kind == "set":
        return [x for x in value if isinstance(x, str)]
    if kind == "map":
        return [x for _, v in value for x in _strings(v)] + [k for k, _ in value if isinstance(k, str)]
    return []


def env_tokens(raw: dict, env: dict, lex: dict) -> set[str]:
    """`env:NAME` for each environment variable a function reads: the key folded through the module's
    constants and locals, any constant the key expression or its local sources name (a table of
    provider -> variable names), and literal variable names in a function that reads the environment."""
    keys = raw.get("envk", [])
    names = set(raw.get("envs", []))
    if not keys:
        return {f"env:{n}" for n in names if ENV_NAME.match(n)}
    for text in keys:
        node = _expr(text)
        if node is None:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Name, ast.Attribute, ast.Subscript, ast.Constant, ast.Tuple, ast.List, ast.Set)):
                names |= set(_strings(ff.fold(sub, env, lex)))
            if isinstance(sub, (ast.Name, ast.Attribute)):      # a class or Enum of names: `for v in EnvVar`,
                names |= members(sub, env)                       # `EnvVar.OPENAI.value`
    return {f"env:{n}" for n in names if ENV_NAME.match(n)}


def members(node, env: dict) -> set[str]:
    """The text values of a class's constants (an Enum of variable names) when an expression names the
    class itself (`EnvVar`, `config.EnvVar`), or of one member reached as `EnvVar.OPENAI.value`."""
    text = ast.unparse(node)
    if text.endswith((".value", ".name")):
        text = text.rpartition(".")[0]
        value = env.get(text)
        return set(_strings(value)) if value else set()
    if not text.rpartition(".")[2][:1].isupper() or text.split(".")[0] in ("self", "cls"):
        return set()
    head = text + "."
    return {x for k, v in env.items() if k.startswith(head) and "." not in k[len(head):] for x in _strings(v)}


def wrapper_env(calls: list, env: dict, lex: dict, envp_of) -> set[str]:
    """`env:NAME` for calls into a getenv wrapper: `envp_of(call)` gives the wrapper's name-carrying
    parameters ([position, name], position counted as the call passes arguments), and the literal or
    folded argument there is the variable name."""
    out = set()
    for call, where, text in calls:
        params = envp_of(call)
        if not params:
            continue
        if not any(where == pos or where == name for pos, name in params):
            continue
        node = _expr(text)
        if node is not None:
            out |= {n for n in _strings(ff.fold(node, env, lex)) if ENV_NAME.match(n)}
    return {f"env:{n}" for n in out}




# ---- decision-site signatures (other homes by the sites a rule turns on, not by whole-function likeness) ----

UNIT_WORDS = {"day", "days", "hour", "hours", "minute", "minutes", "min", "mins", "second", "seconds", "sec",
              "secs", "week", "weeks", "ms", "millis", "pence", "penny", "pennies", "cent", "cents", "pound",
              "pounds", "gbp", "eur", "euro", "euros", "usd", "dollar", "dollars", "minor", "major", "bytes",
              "byte", "count", "num", "number", "value", "total", "len", "size", "amount", "max", "min",
              "limit", "the", "get", "self", "cls", "info", "data", "item", "items", "result", "now", "today",
              # glue words that qualify a field without naming its subject (days_since_signup is about signup)
              "since", "until", "after", "before", "from", "last", "first", "elapsed", "remaining", "left",
              "current", "prev", "previous", "next", "old", "new", "start", "end", "begin", "time", "delta", "diff",
              "duration", "period", "threshold", "sum", "avg", "mean", "raw", "base", "per", "and", "for", "with",
              "expected", "estimated", "actual", "available", "requested", "allowed", "maximum", "minimum",
              # generic attribute names: a value on `code` or `status` says nothing about which decision it is
              "code", "status", "state", "type", "kind", "mode", "name", "key", "level", "index", "idx", "pos",
              "position", "length", "flag", "flags", "option", "options", "opt", "opts", "arg", "args", "param",
              "params", "val", "var", "obj", "res", "ret", "resp", "response", "request", "req", "msg", "message",
              "text", "line", "lines", "char", "chars", "word", "words", "token", "tokens", "field", "fields",
              "attr", "attrs", "self", "other", "out", "src", "dst", "tmp", "buf", "error", "errors", "err"}
MONEY_MINOR = re.compile(r"(^|_)(pence|penny|pennies|cents?|minor_units?)($|_)")
MONEY_MAJOR = re.compile(r"(^|_)(pounds?|gbp|eur|euros?|usd|dollars?)($|_)")
BYTES_NAME = re.compile(r"(^|_)bytes?($|_)")
SIG_KINDS = {"id": "compares with", "env": "reads env", "cfg": "reads config", "set": "the same literal set",
             "tup": "compares with tuple", "v": "version", "t": "duration", "m": "amount", "n": "constant",
             "s": "equals", "k": "key", "p": "tests", "flag": "tests", "f": "field"}


def _field_names(text: str, env: dict, lex: dict) -> set[str]:
    node = _expr(text) if text else None
    if node is None:
        return set()
    try:
        return {n for n in ff.data_names(node, env, lex) if n}
    except (SyntaxError, RecursionError):
        return set()


def _parts(names: set[str]) -> set[str]:
    return {p for n in names for p in ff.name_parts(n) if p not in UNIT_WORDS and not p.isdigit()}


CONFIG_READ = re.compile(r"""([A-Za-z_][\w.]*)\s*(?:\.get(?:int|float|boolean)?\(\s*|\[\s*)['"]([^'"\n]{1,80})['"]""")
CONFIG_RECV = re.compile(r"(conf|config|cfg|setting|option|opts|ini|toml|yaml|policy|params|prefs)", re.I)


def config_keys(text: str, lex: dict, depth: int = 0) -> set[str]:
    """Config keys a site's side reads: `config.get("max_retries")`, `settings["limits"]`, also through a local
    assigned from such a read."""
    out = {k for recv, k in CONFIG_READ.findall(text or "") if CONFIG_RECV.search(recv)}
    if depth < 2:
        for name in set(re.findall(r"[A-Za-z_]\w*", text or "")) & set(lex):
            out |= config_keys(lex[name], lex, depth + 1)
    return out


def site_signatures(r: dict, env: dict, lex: dict, subjects=(), env_names=()) -> list[str]:
    """The signatures of one folded decision site, `sg:<kind>:<body>`. Two sites that share one decide on
    the same thing: the same constant identity (`id:`), the same value after unit conversion (durations in
    seconds `t:`, money in minor units `m:`, other numbers at their boundary `n:`, so `> 17` and `>= 18`
    agree), the same version (`v:3.12`, `@py` when the function reads the interpreter version), literal set
    (`set:`), tuple (`tup:`), compared text (`s:`), key presence (`k:`), the truth of the same in-repo
    predicate (`p:`) or of a field (`flag:`), and the environment variables a site's sides carry (`env:`). A
    value signature also comes qualified by each non-generic part of the compared field's name
    (`f:transfer@n:1073741825`), which is what keeps a small common constant (3 days) specific."""
    op, kind, value = r["op"], r["vkind"], r["value"]
    bodies: list[str] = []
    names = _field_names(r["field"], env, lex)
    loaded = json.loads(value) if value else None
    if op in (*ORDERED, "Eq", "NotEq") and kind in ("num", "dur") and isinstance(loaded, (int, float)):
        b = boundary(op, loaded) if op in ORDERED and kind == "num" else loaded
        node = _expr(r["field"])
        unit = None
        if kind == "num" and node is not None:
            try:
                unit = ff.unit_of(node, ff.names_in(node, env, lex), lex)
            except (SyntaxError, RecursionError):
                unit = None
        text = " ".join(sorted(ff.norm(n) for n in names))
        if kind == "dur":
            bodies.append(f"t:{ff.num(abs(b))}")
        elif unit:
            bodies += sorted({f"t:{ff.num(b * unit)}", f"t:{ff.num(loaded * unit)}"})
        elif MONEY_MINOR.search(text):
            bodies.append(f"m:{ff.num(b)}")
        elif MONEY_MAJOR.search(text):
            bodies.append(f"m:{ff.num(round(b * 100, 6))}")
        elif ff.num(b) not in ff.GENERIC and ff.num(b) != "0":
            bodies.append(f"n:{ff.num(b)}")
            if BYTES_NAME.search(text):
                bodies.append(f"n:bytes:{ff.num(b)}")
    elif op in ORDERED and not value:               # two variable sides: a date against a date shifted by a duration
        for side in (r["field"], r["const"]):
            node = _expr(side)
            d = ff.dur_inside(node, env, lex) if node is not None else None
            if d:
                bodies.append(f"t:{ff.num(abs(d))}")
                names |= _field_names(r["const"], env, lex)
                break
    elif kind == "str" and op in (*ORDERED, "Eq", "NotEq", "In", "NotIn") and isinstance(loaded, str):
        if (v := version_of(loaded)):
            bodies.append(f"v:{v}")
        elif op in ("Eq", "NotEq", "In", "NotIn") and len(loaded) >= 2:
            bodies.append(f"s:{loaded[:60]}")
    elif kind == "set" and isinstance(loaded, list):
        if op in ("In", "NotIn"):
            if len(loaded) >= 2:
                bodies.append("set:" + hashlib.sha1(json.dumps(sorted(map(str, loaded))).encode()).hexdigest()[:10])
            bodies += sorted({f"v:{v}" for x in loaded if isinstance(x, (str, list)) and (v := version_of(x))})
        elif op in (*ORDERED, "Eq", "NotEq"):
            bodies.append("tup:" + ",".join(map(str, loaded))[:40])
            if (v := version_of(loaded)):
                bodies.append(f"v:{v}")
    elif op in ("has", "lacks") and kind == "str" and isinstance(loaded, str):
        bodies.append(f"k:{loaded[:60]}")
    elif op in ("truth", "is None", "is not None"):
        if r["pred"] and ":" in r["pred"]:
            bodies.append(f"p:{r['pred']}")
        elif op == "truth" and (node := _expr(r["field"])) is not None and isinstance(node, (ast.Name, ast.Attribute)):
            last = ff.norm(node.attr if isinstance(node, ast.Attribute) else node.id)
            if len(last) >= 4 and last not in UNIT_WORDS:
                bodies.append(f"flag:{last}")
    out = {"sg:" + b for b in bodies}
    # A changed threshold may share no value with its old copies. The shared
    # field is only a weak pointer, never proof that two policies are identical.
    # With no shared value, a word from a compound name is too weak: source_ids
    # and source_model need not make the same decision. Keep the complete name.
    out |= {f'sg:field:{ff.norm(name)}' for name in names if _parts({name})}
    if r["identity"]:
        out.add("sg:id:" + r["identity"])
    if "python-version" in subjects:
        out |= {f"sg:{b}@py" for b in bodies if b.startswith("v:")}
    for b in bodies:
        if b.split(":", 1)[0] in ("t", "m", "n", "s"):
            out |= {f"sg:f:{p}@{b}" for p in sorted(_parts(names))[:4]}
    if r.get("env"):
        out |= {f"env:{n}" for n in env_names}
    out |= {f"sg:cfg:{k}" for k in config_keys(r["field"], lex) | config_keys(r["const"], lex)}
    return sorted(out)


def say_signature(sig: str) -> str:
    kind, _, body = sig.removeprefix("sg:").partition(":")
    if kind == "f":
        part, _, rest = body.partition("@")
        return f"{say_signature('sg:' + rest)} on {part}"
    if kind == "t":
        return ff.span(float(body))
    if kind == "v":
        return "version " + body.replace("@py", " (interpreter)")
    if kind == "set":
        return "the same literal set"
    if kind == "env":
        return f"reads env {body}"
    return f"{SIG_KINDS.get(kind, kind)} {body}"
