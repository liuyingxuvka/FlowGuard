"""What one Python file says on its own (C-1): nodes, fingerprints, shapes, raw decision sites, keys.

Reading goes through the 1.x readers: `read_source` (BOM, PEP 263 cookie, CRLF), `parse_python`
(imports, symbols, lazy exports) and `discover.file_facts` (calls, effects, routes, constructor
bindings). fgmap's per-function analysis (comparisons, flags, deciders) is kept as raw data so the
store can fold constants again when an imported module changes, without reparsing this file.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

from flowguard.map.common import read_source
from flowguard.map.discovery_syntax import _FileVisitor
from flowguard.map.inventory import parse_python, syntax_tree
from . import analysis as fgs
from .roots import syspath_entries
from .query import exit_may_suppress, handler_outcome, numeric_atoms

DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
SHAPE_K = 64                                   # bottom-k sketch of fgmap's AST 3-gram shape
CONFIG_RE = re.compile(r"(conf|config|cfg|setting|option|opts|ini|toml|yaml|policy|params|prefs)", re.I)
VERSION_RE = re.compile(r"^v?\d+\.\d+(\.\d+){0,2}((a|b|rc|\.dev|\.post)\d*)?$")
ENV_CALLS = {"os.getenv", "getenv", "os.environ.get", "environ.get", "os.environ.setdefault", "os.environ.pop"}
FACT_KEYS = ("class", "calls", "local_imports", "effects", "raises", "line", "end_line", "params", "annotations", "ctor_calls")


def strip_doc(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def own_nodes(stmts: list) -> list:
    """Every AST node of these statements in depth-first order, without the bodies of nested defs."""
    out, stack = [], list(reversed(stmts))
    AST = ast.AST
    while stack:
        node = stack.pop()
        out.append(node)
        if isinstance(node, DEFS):
            continue
        for name in reversed(node._fields):
            value = getattr(node, name, None)
            if isinstance(value, list):
                stack.extend(x for x in reversed(value) if isinstance(x, AST))
            elif isinstance(value, AST):
                stack.append(value)
    return out


def fingerprint(node, name: str) -> str:
    """AST hash without the node's own name, its docstring and positions (a recursive call to its
    own name reads as `<self>`, so a rename keeps the fingerprint)."""
    if isinstance(node, ast.ClassDef):
        body = strip_doc(node.body)
        parts = [ast.dump(x) for x in (*node.bases, *node.keywords, *node.decorator_list)]
        parts += [ast.dump(s) for s in body if not isinstance(s, DEFS)]
        parts += sorted(f"def {s.name}" for s in body if isinstance(s, DEFS))
    else:
        parts = [type(node).__name__, ast.dump(node.args), ast.dump(node.returns) if node.returns else ""]
        parts += [ast.dump(x) for x in node.decorator_list] + [ast.dump(s) for s in strip_doc(node.body)]
    text = "\n".join(parts).replace(f"Name(id={name!r}", "Name(id='<self>'")
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def shape(nodes: list) -> list[int]:
    return fgs.shape_of(nodes)[:SHAPE_K]       # fgmap's sorted 3-gram hashes, cut to the smallest 64


BLOCKS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
MUTATORS = {"append", "add", "extend", "update", "setdefault", "insert", "appendleft"}


def _leads(stmts: list, returned: frozenset = frozenset()) -> str:
    """`raise` or `return` when a branch leaves the function, also from a nested block; `return` when it
    sets a name whose value is returned later (`status = "blocked"`, `reasons.append(...)`)."""
    sets = ""
    if (kind := fgs.exit_kind(stmts)):
        return kind
    for s in stmts:
        if isinstance(s, BLOCKS):
            inner = [*getattr(s, "body", []), *getattr(s, "orelse", []), *getattr(s, "finalbody", []),
                     *[x for h in getattr(s, "handlers", []) for x in h.body]]
            if (found := _leads(inner, returned)):
                return found
        elif returned and _target_names(s) & returned:
            sets = "return"
    return sets


def _target_names(s) -> set:
    """Names a statement stores into: `x = ...`, `x += ...`, `x[k] = ...`, `x.append(...)`."""
    if isinstance(s, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        targets = s.targets if isinstance(s, ast.Assign) else [s.target]
        out = set()
        for t in targets:
            while isinstance(t, (ast.Subscript, ast.Attribute)):
                t = t.value
            out |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)}
        return out
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Attribute) \
            and s.value.func.attr in MUTATORS and isinstance(s.value.func.value, ast.Name):
        return {s.value.func.value.id}
    return set()


def returned_names(nodes: list) -> frozenset:
    """Names whose value reaches a return: named in a return, or stored into such a name (two steps)."""
    out = {x.id for n in nodes if isinstance(n, ast.Return) and n.value is not None
           for x in ast.walk(n.value) if isinstance(x, ast.Name)}
    stores = [n for n in nodes if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr))]
    for _ in range(2):
        more = set()
        for n in stores:
            if _target_names(n) & out:
                value = n.value if not isinstance(n, ast.Expr) else n.value
                more |= {x.id for x in ast.walk(value) if isinstance(x, ast.Name)} if value is not None else set()
        if more <= out:
            break
        out |= more
    return frozenset(out)


SITE_CHARS, CONST_CHARS = 1000, 2000   # longer sides or constant values are left out, never cut


def _src(node, cap: int = 200) -> str:
    text = ast.unparse(node)
    return text if len(text) <= cap else ""


def _atoms(test, lead: str, line: int, neg: bool = False) -> list[dict]:
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id in ("any", "all") \
            and len(test.args) == 1 and isinstance(test.args[0], (ast.GeneratorExp, ast.ListComp, ast.SetComp)) \
            and isinstance(test.args[0].elt, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
        return _atoms(test.args[0].elt, lead, line, neg)        # any(size > LIMIT for size in sizes)
    if isinstance(test, ast.BoolOp):
        return [a for v in test.values for a in _atoms(v, lead, line, neg)]
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _atoms(test.operand, lead, line, not neg)
    if isinstance(test, ast.Compare):
        out, left = [], test.left
        for op, right in zip(test.ops, test.comparators):
            if (ls := _src(left, SITE_CHARS)) and (rs := _src(right, SITE_CHARS)):
                out.append({"line": line, "left": ls, "op": type(op).__name__, "right": rs, "neg": neg, "lead": lead})
            left = right
        return out
    if (text := _src(test)) and not isinstance(test, ast.Constant):
        return [{"line": line, "left": text, "op": "truth", "right": "", "neg": neg, "lead": lead}]
    return []


def decision_sites(nodes: list) -> list[dict]:
    """Comparisons, truth tests, membership tests and match arms that lead to a return or raise, also
    through a nested block or a name the function returns later (`if size > LIMIT: status = "ask"`,
    `too_big = size > LIMIT`)."""
    out = []
    returned = returned_names(nodes)
    for n in nodes:
        if isinstance(n, (ast.If, ast.While)) and (lead := _leads(n.body, returned) or _leads(n.orelse, returned)):
            out += _atoms(n.test, lead, n.lineno)
        elif isinstance(n, ast.Assign) and returned and _target_names(n) & returned:
            v = n.value
            out += _returned_atoms(v)
        elif isinstance(n, ast.Assert):
            out += _atoms(n.test, "raise", n.lineno)
        elif isinstance(n, ast.Return) and n.value is not None:
            v = n.value
            out += _returned_atoms(v)
        elif isinstance(n, ast.Match) and (subject := _src(n.subject)):
            for case in n.cases:
                if not (lead := _leads(case.body)):
                    continue
                pat = case.pattern
                values = pat.patterns if isinstance(pat, ast.MatchOr) else [pat]
                lits = [_src(p.value) if isinstance(p, ast.MatchValue) else repr(p.value) if isinstance(p, ast.MatchSingleton)
                        else None for p in values]
                if lits and all(lits):
                    right = lits[0] if len(lits) == 1 else "(" + ", ".join(lits) + ")"
                    out.append({"line": case.pattern.lineno, "left": subject, "op": "Eq" if len(lits) == 1 else "In",
                                "right": right, "neg": False, "lead": lead, "match": True})
                elif isinstance(pat, ast.MatchClass):
                    out.append({"line": pat.lineno, "left": subject, "op": "isinstance", "right": _src(pat.cls),
                                "neg": False, "lead": lead, "match": True})
                if case.guard is not None:
                    out += _atoms(case.guard, lead, case.guard.lineno)
    return out + _fed_tests(nodes, out, returned)


def _returned_atoms(value):
    """A comparison returned inside a dict, list or call is still a decision."""
    if isinstance(value, (ast.Compare, ast.BoolOp)) or isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
        return _atoms(value, 'return', value.lineno)
    if isinstance(value, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    return [site for child in ast.iter_child_nodes(value) for site in _returned_atoms(child)]


def _fed_tests(nodes: list, sites: list, returned: frozenset) -> list[dict]:
    """A comparison assigned to a local that a decision site then tests is a decision site with that site's
    lead: `needs_confirmation = size > LIMIT` before `if needs_confirmation and not ok: raise ...`."""
    lead_of: dict[str, str] = {}
    for s in sites:
        for name in re.findall(r"[A-Za-z_]\w*", s["left"] + " " + s["right"]):
            lead_of.setdefault(name, s["lead"])
    out = []
    for n in nodes:
        if not isinstance(n, ast.Assign) or (returned and _target_names(n) & returned):
            continue                               # an assignment to a returned name is a site already
        hit = [lead_of[t] for t in sorted(_target_names(n)) if t in lead_of]
        v = n.value
        if hit and (isinstance(v, (ast.Compare, ast.BoolOp)) or isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)):
            out += _atoms(v, hit[0], n.lineno)
    return out


def keys_of(nodes: list) -> list[tuple[str, str, int]]:
    """Environment variables, config keys and version literals read in these nodes: [(kind, value, line)]."""
    out, compared = [], set()
    for n in nodes:
        if isinstance(n, ast.Compare):
            for side in (n.left, *n.comparators):
                compared.add(id(side))
                if isinstance(side, (ast.Tuple, ast.List, ast.Set)):
                    compared.update(id(x) for x in side.elts)
        elif isinstance(n, ast.Call):
            name = fgs.dotted(n.func) or ""
            first = n.args[0] if n.args else None
            literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
            if name in ENV_CALLS and literal:
                out.append(("env", literal, n.lineno))
            elif isinstance(n.func, ast.Attribute) and n.func.attr in ("get", "getint", "getfloat", "getboolean") \
                    and literal and CONFIG_RE.search(fgs.dotted(n.func.value) or ""):
                second = n.args[1] if len(n.args) > 1 else None
                if n.func.attr != "get" and isinstance(second, ast.Constant) and isinstance(second.value, str):
                    literal = f"{literal}.{second.value}"
                out.append(("config", literal, n.lineno))
            for kw in n.keywords:
                if kw.arg and "version" in kw.arg.lower() and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str) and VERSION_RE.match(kw.value.value):
                    out.append(("version", kw.value.value, n.lineno))
        elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            owner = fgs.dotted(n.value) or ""
            if owner in ("os.environ", "environ"):
                out.append(("env", n.slice.value, n.lineno))
            elif CONFIG_RE.search(owner):
                out.append(("config", n.slice.value, n.lineno))
        elif isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) \
                and VERSION_RE.match(n.value.value) \
                and any("version" in (fgs.dotted(t) or "").lower() for t in n.targets):
            out.append(("version", n.value.value, n.lineno))
    for n in nodes:
        if id(n) in compared and isinstance(n, ast.Constant) and isinstance(n.value, str) and VERSION_RE.match(n.value):
            out.append(("version", n.value, n.lineno))
    return out


ENV_RECV = re.compile(r"(^|[._])(environ|environment|env)$", re.I)
ENV_FUNCS = {"os.getenv", "getenv", "os.environ.get", "environ.get"}
ENV_VERBS = {"getenv", "setenv", "putenv", "unsetenv", "delenv"}
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")


def env_reads(nodes: list, params: tuple = ()) -> tuple[list[str], list[str], list[str], set]:
    """(key expressions of environment reads, variable-name literals, parameters the key comes from) in one
    function's own nodes. A read is getenv, or get/pop/setdefault/[] on os.environ or on a mapping named
    like an environment (`self._environment`). A key that is a local or a loop variable also brings the
    expressions it was assigned from, so a key taken from a table of names reaches that table. A key that
    comes from a parameter makes the function a getenv wrapper: its callers' literal arguments are the
    variable names (the store links them). The fourth item is the set of locals that hold a variable's name
    or value (for env_linked)."""
    keys, sources, via = [], {}, set()
    if not any(isinstance(n, ast.Attribute) and (ENV_RECV.search(n.attr) or n.attr in ENV_VERBS)
               or isinstance(n, ast.Name) and (ENV_RECV.search(n.id) or n.id in ENV_VERBS)
               or isinstance(n, ast.keyword) and n.arg and ENV_RECV.search(n.arg) for n in nodes):
        return [], [], [], set()
    for n in nodes:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        sources.setdefault(x.id, []).append(n.value)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    sources.setdefault(x.id, []).append(n.iter)
    found, reads = [], []
    for n in nodes:
        if isinstance(n, ast.Call):
            name = fgs.dotted(n.func) or ""
            recv = fgs.dotted(n.func.value) if isinstance(n.func, ast.Attribute) else ""
            if n.args and (name in ENV_FUNCS or isinstance(n.func, ast.Attribute) and n.func.attr in
                           ("get", "pop", "setdefault") and ENV_RECV.search(recv or "")):
                found.append(n.args[0])
                reads.append(n)
        elif isinstance(n, ast.Subscript) and ENV_RECV.search(fgs.dotted(n.value) or ""):
            found.append(n.slice)
            reads.append(n)
        elif isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], (ast.In, ast.NotIn)) \
                and ENV_RECV.search(fgs.dotted(n.comparators[0]) or ""):     # "KWP_KEY" in os.environ
            found.append(n.left)
            reads.append(n)
    held = {x.id for k in found for x in ast.walk(k) if isinstance(x, ast.Name)}   # names and values of variables
    read_ids = {id(x) for r in reads for x in ast.walk(r)}
    for _ in range(3):
        for name, values in sources.items():
            if any(id(x) in read_ids or isinstance(x, ast.Name) and x.id in held
                   for v in values for x in ast.walk(v)):
                held.add(name)
    for key in found:
        stack, seen = [key], 0
        while stack and seen < 8:
            node, seen = stack.pop(), seen + 1
            if (text := _src(node)):
                keys.append(text)
            names_here = [x.id for x in ast.walk(node) if isinstance(x, ast.Name)]
            via |= {n for n in names_here if n in params and n not in sources}
            stack += [v for n in names_here for v in sources.get(n, [])]
    if found:
        names = sorted({n.value for n in nodes if isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and ENV_NAME.match(n.value)})
    else:                                    # no read: the names an environment is built with
        names = sorted(_placed_env_names(nodes))
    return sorted(set(keys))[:20], names[:20], sorted(via), held


def _envish(node) -> bool:
    return bool(ENV_RECV.search(fgs.dotted(node) or "")) if node is not None else False


def _placed_env_names(nodes: list) -> set[str]:
    """Variable-name literals where an environment is written or built: `env["KWP_KEY"] = ...`,
    `child_env = {"KWP_KEY": ...}`, `run(..., env={"KWP_KEY": ...})`, `env.update({...})`, `setenv("KWP_KEY")`,
    `{**os.environ, "KWP_KEY": ...}`."""
    def keys(d):
        return {k.value for k in d.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)
                and ENV_NAME.match(k.value)} if isinstance(d, ast.Dict) else set()
    out = set()
    for n in nodes:
        if isinstance(n, ast.Subscript) and _envish(n.value) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str) and ENV_NAME.match(n.slice.value):
            out.add(n.slice.value)
        elif isinstance(n, ast.Assign) and any(_envish(t) for t in n.targets):
            out |= keys(n.value)
        elif isinstance(n, ast.Dict) and any(k is None and _envish(v) for k, v in zip(n.keys, n.values)):
            out |= keys(n)
        elif isinstance(n, ast.Call):
            out |= {x for k in n.keywords if k.arg and ENV_RECV.search(k.arg) for x in keys(k.value)}
            attr = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if attr == "update" and isinstance(n.func, ast.Attribute) and _envish(n.func.value) and n.args:
                out |= keys(n.args[0])
            if attr in ("setenv", "putenv", "unsetenv", "delenv") and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str) and ENV_NAME.match(n.args[0].value):
                out.add(n.args[0].value)
    return out


def env_linked(sites: list, held: set) -> None:
    """Mark the decision sites whose sides name an environment read or a local that holds a variable's
    name or value (`if environment_variable is None`, `return value.strip() or None`): their decision is
    about those variables, so the variable names join the site's signature."""
    if not held:
        return
    for s in sites:
        names = set(re.findall(r"[A-Za-z_]\w*", s["left"] + " " + s["right"]))
        if names & held or "environ" in names or "getenv" in names:
            s["env"] = 1


def call_args(nodes: list) -> list[list]:
    """Calls that pass a variable-name literal or a named constant: [dotted callee, position or keyword, text].
    The store reads them for calls into a getenv wrapper (`_secret("KWP_OPENAI_API_KEY")`)."""
    out = []
    for n in nodes:
        if not isinstance(n, ast.Call) or not (name := fgs.dotted(n.func)):
            continue
        given = [(i, a) for i, a in enumerate(n.args)] + [(k.arg, k.value) for k in n.keywords if k.arg]
        for where, a in given:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and ENV_NAME.match(a.value) \
                    or named_constant_node(a):
                out.append([name, where, ast.unparse(a)[:120]])
        if len(out) >= 40:
            break
    return out


def named_constant_node(node) -> bool:
    if isinstance(node, ast.Name):
        return len(node.id.strip("_")) > 1 and node.id.strip("_").isupper()
    if isinstance(node, ast.Attribute):
        return len(node.attr.strip("_")) > 1 and node.attr.strip("_").isupper()
    return False


VERSION_SUBJECT = {"sys.version_info", "sys.version", "sys.hexversion", "platform.python_version",
                   "platform.python_version_tuple", "sys.implementation.version"}


def subjects(nodes: list) -> list[str]:
    """Well-known subjects a function reads: the interpreter version (`sys.version_info`,
    `platform.python_version()`), whatever local names carry it to the comparison."""
    for n in nodes:
        if isinstance(n, (ast.Attribute, ast.Call)) and \
                (fgs.dotted(n.func if isinstance(n, ast.Call) else n) or "") in VERSION_SUBJECT:
            return ["python-version"]
    return []


def _const_reads(nodes: list) -> list[str]:
    """Constant-looking names this code reads: GRACE_DAYS, limits.LIMIT, Limits.GRACE, self.GRACE, POLICY."""
    out = set()
    attrs = {id(n.value) for n in nodes if isinstance(n, ast.Attribute)}
    for n in nodes:
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in attrs \
                and len(n.id.strip("_")) > 1 and n.id.strip("_").isupper():
            out.add(n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and n.attr.strip("_").isupper() \
                and len(n.attr.strip("_")) > 1 and (d := fgs.dotted(n)):
            out.add(d)
    return sorted(out)


def _optional_import_lines(tree) -> set[int]:
    """Lines of module-level imports inside `try:` blocks that catch an error (optional dependencies)."""
    lines, stack = set(), list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Try) and any(h.type is None or "Error" in ast.unparse(h.type)
                                             or "Exception" in ast.unparse(h.type) for h in node.handlers):
            lines |= {s.lineno for s in node.body if isinstance(s, (ast.Import, ast.ImportFrom))}
        if isinstance(node, (ast.If, ast.Try, ast.With)):
            stack += node.body + getattr(node, "orelse", []) + getattr(node, "finalbody", []) \
                + [s for h in getattr(node, "handlers", []) for s in h.body]
    return lines


def code_facts(tree, module: str, package: str) -> dict:
    """Calls, effects, raises, routes and constructor bindings on the already parsed tree."""
    visitor = _FileVisitor(module, package)
    visitor.visit(tree)
    functions = {s: {"line": f["line"], "class": f["class"], "calls": sorted(f["calls"]), "effects": f["effects"],
                     "raises": sorted(x for x in f["raises"] if x), "end_line": f["end_line"],
                     "local_imports": dict(sorted(f["local_imports"].items())),
                     **{key:f[key] for key in ("params", "annotations", "ctor_calls") if key in f}} for s, f in visitor.functions.items()}
    return {"module": module, "imports": visitor.imports, "instances": visitor.instances, "classes": visitor.classes,
            "entrypoints": visitor.entrypoints, "functions": functions, "injected": visitor.injected}


def module_bindings(tree, text: str = "") -> set[str]:
    """Every name a module binds at module level, also inside if/try/with/for blocks: assignment targets
    with tuple unpacking and starred names, augmented and annotated assignments, loop and with targets,
    walrus names, imports, defs, and names a function declares `global` and assigns."""
    out, stack = set(), list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
            if not isinstance(node, ast.ClassDef) and "global" in text:
                declared = {n for g in statements(node.body) if isinstance(g, ast.Global) for n in g.names}
                if declared:
                    out |= {x.id for x in ast.walk(node) if isinstance(x, ast.Name)
                            and isinstance(x.ctx, ast.Store) and x.id in declared}
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name.split(".")[0] for a in node.names if a.name != "*"}
            continue
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [i.optional_vars for i in node.items if i.optional_vars is not None]
        for t in targets:
            out |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)}
        if ":=" in text and not isinstance(node, BLOCKS):
            out |= {x.target.id for x in ast.walk(node) if isinstance(x, ast.NamedExpr) and isinstance(x.target, ast.Name)}
        if isinstance(node, BLOCKS):
            stack += [*getattr(node, "body", []), *getattr(node, "orelse", []), *getattr(node, "finalbody", []),
                      *[x for h in getattr(node, "handlers", []) for x in h.body]]
    return out


def statements(body: list):
    """Every statement in these bodies, nested ones too (if/for/while/with/try/match and def bodies), in
    source order, without walking into expressions: imports and module bindings are statements."""
    stack = list(reversed(body))
    while stack:
        node = stack.pop()
        yield node
        inner = [*getattr(node, "body", ()), *getattr(node, "orelse", ()), *getattr(node, "finalbody", ())]
        inner += [s for h in getattr(node, "handlers", ()) for s in h.body]
        inner += [s for c in getattr(node, "cases", ()) for s in c.body]
        stack.extend(reversed([s for s in inner if isinstance(s, ast.stmt)]))


def _type_checking(node) -> bool:
    return isinstance(node, ast.If) and (getattr(node.test, "id", "") == "TYPE_CHECKING"
                                         or getattr(node.test, "attr", "") == "TYPE_CHECKING")


def import_lines_all(tree, package: str) -> dict[str, list[int]]:
    """Every line of every import statement, keyed like 1.x `parse_python` keys `import_lines` (which keeps
    one line per import): `a.b` for `import a.b`, `pkg.mod:name` for `from pkg.mod import name`. Imports
    under `if TYPE_CHECKING:` are not runtime imports (as in 1.x)."""
    out: dict[str, list[int]] = {}
    skip = {id(s) for n in statements(tree.body) if _type_checking(n) for s in statements(n.body)}
    for node in statements(tree.body):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            for a in node.names:
                out.setdefault(a.name, []).append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts)
                target = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                target = node.module or ""
            for a in node.names if target else ():
                out.setdefault(f"{target}:{a.name}", []).append(node.lineno)
    return {k: sorted(set(v)) for k, v in out.items()}


def _from_target(node, package: str) -> str:
    """The module a `from ... import` names, as 1.x parse_python computes it ("" when nothing anchors it)."""
    if not node.level:
        return node.module or ""
    parts = package.split(".") if package else []
    parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
    base = ".".join(parts)
    return f"{base}.{node.module}" if node.module and base else (node.module or base)


def typing_imports(tree, package: str) -> dict[str, list[int]]:
    """Imports under `if TYPE_CHECKING:` (not run, but they name a module the code depends on for its types),
    keyed like `import_lines_all`."""
    out: dict[str, list[int]] = {}
    for guard in statements(tree.body):
        if not _type_checking(guard):
            continue
        for node in statements(guard.body):
            if isinstance(node, ast.Import):
                for a in node.names:
                    out.setdefault(a.name, []).append(node.lineno)
            elif isinstance(node, ast.ImportFrom) and (target := _from_target(node, package)):
                for a in node.names:
                    out.setdefault(f"{target}:{a.name}", []).append(node.lineno)
    return {k: sorted(set(v)) for k, v in out.items()}


def dir_relative_imports(tree, package: str) -> list[list]:
    """Relative imports that no package name anchors (`from . import X` in a module whose name has no
    package, or more dots than the package has): [level, module, name, line]. Python resolves them only when
    the file is imported as part of its directory's package, so the store resolves them against the
    importer's directory."""
    depth = len(package.split(".")) if package else 0
    out = []
    for node in statements(tree.body):
        if isinstance(node, ast.ImportFrom) and node.level and node.level - 1 >= depth:
            out += [[node.level, node.module or "", a.name, node.lineno] for a in node.names if a.name != "*"]
    return out


def syntax_records(tree, module, rel):
    """Fixed structural facts, retained once with the file parse (never a second scanner)."""
    found = {"handlers": [], "literal_sets": [], "assignments": [], "syntax_calls": [], "symbol_reads": [], "field_types": [],
             "literals": []}
    package = module if rel.endswith('__init__.py') else module.rpartition('.')[0]
    aliases = {}
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            origin = _from_target(statement, package)
            aliases.update((name.asname or name.name, origin + ':' + name.name) for name in statement.names if name.name != '*')
        elif isinstance(statement, ast.Import):
            aliases.update((name.asname or name.name.split('.')[0], name.name if name.asname else name.name.split('.')[0]) for name in statement.names)

    def annotation_class(annotation):
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode='eval').body
            except SyntaxError:
                return None
        if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value).split('.')[-1] == 'Optional':
            return annotation_class(annotation.slice)
        if isinstance(annotation, ast.Name):
            return aliases.get(annotation.id) if ':' in aliases.get(annotation.id, '') else module + ':' + annotation.id if annotation.id in classes else None
        if isinstance(annotation, ast.Attribute):
            parts = ast.unparse(annotation).split('.')
            origin = aliases.get(parts[0])
            if origin and ':' not in origin:
                return '.'.join([origin, *parts[1:-1]]) + ':' + parts[-1]
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            if isinstance(annotation.left, ast.Constant) and annotation.left.value is None:
                return annotation_class(annotation.right)
            if isinstance(annotation.right, ast.Constant) and annotation.right.value is None:
                return annotation_class(annotation.left)
        return None

    class Reader(ast.NodeVisitor):
        qual = ""
        cls = ""
        typed = {}
        literal_depth = 0
        bindings = dict(aliases)
        or_nonfinal = set()
        quiet = 0                 # inside raise or a logging/print/exception call: strings are messages
        declaring = ""            # Kind = Literal['a', 'b'] at module level: the union's declaration name
        consumed = set()

        # String literals that decide or name a value, in the TS/JS reader's terms: comparisons (compare),
        # the containers of `in` tests (member), match cases (case), returned values through ?: and
        # and/or (return), set literals and set()/frozenset() arguments (set) and Literal[...] members
        # (union). Dict keys, `'key' in mapping`, messages and raise statements are never recorded.
        def label(self, node, context):
            if self.quiet or not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in self.consumed:
                return
            self.consumed.add(id(node))
            self.add('literals', node, column=node.col_offset + 1, value=node.value, context=context,
                     function=self.qual or '<module>',
                     **({'declaration': self.declaring} if context == 'union' and self.declaring else {}))

        def labels(self, node, context):
            if isinstance(node, ast.IfExp) and context == 'return':
                self.labels(node.body, context)
                self.labels(node.orelse, context)
            elif isinstance(node, ast.BoolOp) and context == 'return':
                for value in node.values:
                    self.labels(value, context)
            elif isinstance(node, (ast.Tuple, ast.List, ast.Set)) and context in ('member', 'set', 'union'):
                for item in node.elts:
                    self.label(item, context)
            else:
                self.label(node, context)

        def visit_Compare(self, node):
            sides = [node.left, *node.comparators]
            for left, operator, right in zip(sides, node.ops, sides[1:]):
                if isinstance(operator, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                    self.label(left, 'compare')
                    self.label(right, 'compare')
                elif isinstance(operator, (ast.In, ast.NotIn)) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
                    self.labels(right, 'member')
            self.generic_visit(node)

        def visit_Return(self, node):
            if node.value is not None:
                self.labels(node.value, 'return')
            self.generic_visit(node)

        def visit_Lambda(self, node):
            self.labels(node.body, 'return')
            self.generic_visit(node)

        def visit_MatchValue(self, node):
            self.label(node.value, 'case')
            self.generic_visit(node)

        def visit_Raise(self, node):
            self.quiet += 1
            self.generic_visit(node)
            self.quiet -= 1

        def visit_Subscript(self, node):
            base = node.value
            if isinstance(base, ast.Name) and base.id == 'Literal' or isinstance(base, ast.Attribute) and base.attr == 'Literal':
                self.labels(node.slice, 'union')
            self.generic_visit(node)

        def add(self, category, node, **facts):
            found[category].append(dict(node=module + (":" + self.qual if self.qual else ""),
                                   file=rel, line=node.lineno, **facts))

        def visit_FunctionDef(self, node):
            # These expressions belong to the enclosing definition scope, not
            # to a future call of the function. The facts remain syntactic.
            expressions = [*node.decorator_list, *node.args.defaults,
                           *(value for value in node.args.kw_defaults if value is not None)]
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                         *([node.args.vararg] if node.args.vararg else []),
                         *([node.args.kwarg] if node.args.kwarg else [])]
            expressions += [arg.annotation for arg in arguments if arg.annotation is not None]
            if node.returns is not None:
                expressions.append(node.returns)
            for expression in expressions:
                self.visit(expression)
            old = self.qual, self.typed, self.bindings
            self.qual = old[0] + ('.' if old[0] else '') + node.name
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            self.typed = {arg.arg: kind for arg in args if (kind := annotation_class(arg.annotation))}
            self.bindings = {name:value for name,value in self.bindings.items() if name not in {arg.arg for arg in args}}
            if node.name in ('__exit__','__aexit__') and exit_may_suppress(node):
                self.add('handlers',node,kind='exit_method',type='may return true',name=None,end_line=node.end_lineno,
                         raises=False,reraise=False,non_raising=True,body=ast.unparse(node))
            for child in node.body:
                self.visit(child)
            self.qual, self.typed, self.bindings = old

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            for expression in [*node.decorator_list, *node.bases, *(key.value for key in node.keywords)]:
                self.visit(expression)
            old = self.qual, self.cls
            self.qual = self.qual + ("." if self.qual else "") + node.name
            self.cls = self.qual
            for child in node.body:
                self.visit(child)
            self.qual, self.cls = old

        def visit_ExceptHandler(self, node):
            body = own_nodes(node.body)
            raises = any(isinstance(n, ast.Raise) for n in body)
            self.add("handlers", node, kind='except', type=ast.unparse(node.type) if node.type else "", name=node.name,
                     end_line=node.end_lineno, raises=raises,
                     reraise=any(isinstance(n, ast.Raise) and n.exc is None for n in body),
                     non_raising=handler_outcome(node.body) != (False, False), ends=_ending(node.body, body, raises),
                     body="\n".join(ast.unparse(n) for n in node.body))
            self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):
                self.add('symbol_reads', node, text=node.id, resolved=self.resolve(node), read=True)

        def visit_Attribute(self, node):
            if isinstance(node.ctx, ast.Load):
                self.add('symbol_reads', node, text=ast.unparse(node), resolved=self.resolve(node), read=True)
            self.generic_visit(node)

        def visit_Call(self, node):
            resolved = self.resolve(node.func)
            dotted = fgs.dotted(node.func)
            self.add("syntax_calls", node, text=dotted or ast.unparse(node.func),resolved=resolved,
                     positional_arg_count=len(node.args), keyword_count=len(node.keywords),
                     boolop_or_nonfinal=id(node) in self.or_nonfinal)
            if resolved == 'contextlib.suppress':
                self.add('handlers',node,kind='suppress',type='suppress('+', '.join(ast.unparse(arg) for arg in node.args)+')',
                         name=None,end_line=node.end_lineno,raises=False,reraise=False,non_raising=True,body=ast.unparse(node))
            if dotted in ('set', 'frozenset') and len(node.args) == 1:
                self.labels(node.args[0], 'set')
            quiet = _message_call(dotted or '')
            depth, self.literal_depth = self.literal_depth, 0
            self.quiet += quiet
            self.generic_visit(node)
            self.quiet -= quiet
            self.literal_depth = depth

        def visit_BoolOp(self, node):
            if isinstance(node.op, ast.Or):
                self.or_nonfinal.update(id(value) for value in node.values[:-1] if isinstance(value, ast.Call))
            self.generic_visit(node)

        def resolve(self, expression):
            if isinstance(expression,ast.Name):
                return self.bindings.get(expression.id,expression.id).replace(':','.')
            if isinstance(expression,ast.Attribute):
                return self.resolve(expression.value)+'.'+expression.attr
            if isinstance(expression,ast.Call) and isinstance(expression.func,ast.Name) and expression.func.id=='getattr' and len(expression.args)>1 and isinstance(expression.args[1],ast.Constant) and isinstance(expression.args[1].value,str):
                return self.resolve(expression.args[0])+'.'+expression.args[1].value
            if isinstance(expression,ast.Subscript) and isinstance(expression.slice,ast.Constant) and isinstance(expression.slice.value,str):
                return self.resolve(expression.value).removesuffix('.__dict__')+'.'+expression.slice.value
            return ast.unparse(expression)

        def visit_Import(self, node):
            self.bindings.update((name.asname or name.name.split('.')[0],name.name if name.asname else name.name.split('.')[0]) for name in node.names)

        def visit_ImportFrom(self, node):
            origin = _from_target(node,package)
            self.bindings.update((name.asname or name.name,origin+'.'+name.name) for name in node.names if name.name!='*')

        def visit_Try(self, node):
            if handler_outcome(node.finalbody)[1]:
                self.add('handlers',node,kind='finally',type='finally exits',name=None,end_line=node.end_lineno,
                         raises=False,reraise=False,non_raising=True,body='\n'.join(ast.unparse(n) for n in node.finalbody))
            self.generic_visit(node)

        visit_TryStar = visit_Try

        def assignment(self, node, targets, value):
            if value is None:
                return
            for target in targets:
                if isinstance(target,ast.Name):
                    if isinstance(value,(ast.Name,ast.Attribute,ast.Subscript)) or isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='getattr':
                        self.bindings[target.id] = self.resolve(value)
                    else:
                        self.bindings.pop(target.id,None)
                if isinstance(target,ast.Name) and target.id in ('__exit__','__aexit__') and isinstance(value,ast.Lambda) and exit_may_suppress(value):
                    self.add('handlers',node,kind='exit_method',type=target.id+' may return true',name=None,end_line=node.end_lineno,
                             raises=False,reraise=False,non_raising=True,body=ast.unparse(value))
            literal = isinstance(value, ast.Constant) and isinstance(value.value, (str, int, float, bool, type(None)))
            # A computed right side keeps its text; the map folds enum members and named constants at query time.
            computed = {'expr': ast.unparse(value)[:300]} if not literal and isinstance(
                value, (ast.Name, ast.Attribute, ast.IfExp, ast.Subscript, ast.UnaryOp, ast.BinOp)) else {}
            for target in targets:
                field = ast.unparse(target)
                owner, unresolved, form = module, False, {}
                key = target.slice.value if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) \
                    and isinstance(target.slice.value, str) else None
                if key is not None:                        # row['status'] = ...: the key is the field name
                    receiver, attr, form = target.value, key, {'form': 'key'}
                elif isinstance(target, ast.Attribute):
                    receiver, attr = target.value, target.attr
                else:
                    receiver, attr = None, ''
                if isinstance(receiver, ast.Name) and receiver.id in ("self", "cls") and self.cls:
                    field = self.cls + "." + attr
                elif isinstance(receiver, ast.Name):
                    kind = self.typed.get(receiver.id)
                    if kind:
                        owner, _, cls = kind.partition(':')
                        field = cls + '.' + attr
                    else:
                        field, unresolved = receiver.id + '.' + attr, True
                elif receiver is not None and key is not None:
                    field, unresolved = ast.unparse(receiver) + '.' + key, True
                elif isinstance(target, ast.Name) and self.cls and self.qual == self.cls:
                    field = self.cls + '.' + target.id     # a class-body default belongs to its class
                self.add("assignments", node, field=owner + ":" + field,
                         value=value.value if literal else None, literal=literal, unresolved=unresolved, **computed, **form)

        def literal(self, node):
            if isinstance(node, ast.Set):
                self.labels(node, 'set')
            if self.literal_depth or isinstance(getattr(node, 'ctx', None), ast.Store):
                self.generic_visit(node)
                return
            try:
                parsed = ast.literal_eval(node)
            except (ValueError, TypeError, SyntaxError):
                parsed = None
            def serializable(value):
                if isinstance(value, dict):
                    return {key if isinstance(key, (str, int, float, bool, type(None))) else repr(key): serializable(item) for key, item in value.items()}
                if isinstance(value, (set, tuple, list)):
                    return [serializable(item) for item in (sorted(value, key=repr) if isinstance(value, set) else value)]
                if isinstance(value, bytes):
                    return {'literal_type': 'bytes', 'hex': value.hex()}
                if isinstance(value, complex):
                    return {'literal_type': 'complex', 'real': value.real, 'imag': value.imag}
                if value is Ellipsis:
                    return {'literal_type': 'ellipsis'}
                return value
            parsed = serializable(parsed)
            self.add('literal_sets', node, value=parsed, text=ast.unparse(node),
                     numeric_values=numeric_atoms(node), partial=parsed is None)
            self.literal_depth += 1
            self.generic_visit(node)
            self.literal_depth -= 1

        visit_List = literal
        visit_Tuple = literal
        visit_Set = literal
        visit_Dict = literal

        def visit_Assign(self, node):
            self.assignment(node, node.targets, node.value)
            named = not self.qual and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            declaring, self.declaring = self.declaring, node.targets[0].id if named else self.declaring
            self.generic_visit(node)
            self.declaring = declaring

        def visit_AnnAssign(self, node):
            if isinstance(node.target, ast.Name) and self.cls and self.qual == self.cls and (kind := annotation_class(node.annotation)):
                # `status: RunStatus` in a class body: the field's declared type (an enum's members are its values)
                optional = 'None' in ast.unparse(node.annotation) or 'Optional' in ast.unparse(node.annotation)
                self.add('field_types', node, field=module + ':' + self.cls + '.' + node.target.id, type=kind,
                         **({'optional': True} if optional else {}))
            if isinstance(node.target, ast.Name) and (kind := annotation_class(node.annotation)):
                self.typed[node.target.id] = kind
            self.assignment(node, [node.target], node.value)
            declaring, self.declaring = self.declaring, node.target.id if not self.qual and isinstance(node.target, ast.Name) else self.declaring
            self.generic_visit(node)
            self.declaring = declaring

    Reader().visit(tree)
    return found


def sql_writes(nodes: list, module: str, rel: str, qual: str) -> list[dict]:
    """INSERT, UPDATE and DELETE statements spelled in this scope's string literals, read by the one SQL
    statement reader and recorded for the function that holds them (`<module>` outside functions). A value
    the statement spells as a literal is kept per column; a placeholder or expression has none."""
    from .readers.sql import statements, line_of
    rows = []
    for node in nodes:
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 20000
                and fgs.SQL_RE.match(node.value)):
            continue
        for row in statements(node.value):
            if row['verb'] not in ('insert', 'update', 'delete'):
                continue
            fact = dict(node=module + (':' + qual if qual else ''), file=rel,
                        line=node.lineno + line_of(node.value, row['offset']) - 1, via='sql', statement=row['verb'],
                        function=qual or '<module>', table=row['table'], schema=row['schema'],
                        columns=[column['name'] for column in row['columns']] or ['*'])
            values = {column['name']: column['value'] for column in row['columns'] if 'value' in column}
            if values:
                fact['values'] = values
            rows.append(fact)
    return rows


MESSAGE_CALLS = {'debug', 'info', 'warning', 'warn', 'error', 'exception', 'critical', 'log', 'fatal'}


def _ending(statements, nodes, raises) -> str:
    """How an except body ends (readers.common.ENDINGS): it raises somewhere, returns or assigns a substitute,
    only logs, is empty (`pass`, `...`, a docstring) or does other work."""
    if raises:
        return 'handed'
    work = [node for node in statements if not isinstance(node, ast.Pass)
            and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))]
    if not work:
        return 'empty'
    if all(isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and _message_call(ast.unparse(node.value.func))
           and not ast.unparse(node.value.func).endswith(('Error', 'Exception', 'Warning')) for node in work):
        return 'log'
    if any(isinstance(node, ast.Return) and node.value is not None or isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
           for node in nodes):
        return 'substitute'
    return 'other'


def _message_call(name: str) -> bool:
    """A logging, print, warning or exception-construction call (by its dotted name): its strings are
    messages, not values."""
    head, _, last = name.rpartition('.')
    receiver = head.rpartition('.')[2]
    receiver = receiver.casefold()
    return (name == 'print' or last.endswith(('Error', 'Exception', 'Warning'))
            or last in MESSAGE_CALLS and (receiver in ('logging', 'log', 'logger', 'warnings') or receiver.endswith('logger')))


def _extract_python(root: Path, rel: str, data: bytes, module: str, is_test: bool) -> dict:
    """Everything the store keeps for one file; nothing here depends on another file."""
    info = parse_python(root, rel, module, data=data)
    out = {"module": module, "loc": info.loc, "source_lines": len(data.splitlines()), "parse_error": info.parse_error, "imports": sorted(info.imports),
           "import_lines": info.import_lines, "import_reads": info.import_reads,
           "literal_dynamic_imports": info.literal_dynamic_imports,
           "unknown_dynamic_imports": info.unknown_dynamic_imports,
           "lazy": info.lazy_exports, "bound": sorted(info.symbols),
           "nodes": [], "syspath": [], "keys": [], "facts": {}, "optional": [], "star": False, "getattr": False,
           "submodules": False, "writes": [], "literals": []}
    if info.parse_error:
        return out
    text = read_source(root / rel, data=data)
    tree = syntax_tree(text)
    if 'flowguard:' in text:
        from flowguard.intent.anchors import source_facts
        from flowguard.map.common import content_digest
        out.update(source_facts(tree, text, module, rel,
                                source_digest=content_digest(root / rel, data=data), is_test=is_test))
    out.update(syntax_records(tree, module, rel))
    if is_test:
        out["literals"] = []          # a test's strings are its own data, not the code's labels
    out["syspath"] = syspath_entries(tree, rel) if "sys.path" in text or "addsitedir" in text else []
    out["optional"] = sorted(_optional_import_lines(tree))
    out["star"] = any(i.endswith(":*") for i in info.imports)
    out["getattr"] = any(isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body) \
        or "globals()" in text or "sys.modules[" in text     # names this module binds at run time
    out["submodules"] = "sys.modules[" in text                 # os.py binds os.path at run time
    out["doc"] = (ast.get_docstring(tree) or "").strip().split("\n")[0][:100]
    out["module_fp"] = hashlib.sha256("\n".join(ast.dump(s) for s in strip_doc(tree.body) if not isinstance(s, DEFS))
                                      .encode()).hexdigest()[:20]   # module-level code, not the defs in it
    package = module if rel.endswith("__init__.py") else module.rpartition(".")[0]
    out["bound"] = sorted(set(out["bound"]) | module_bindings(tree, text))
    out["lines_all"] = import_lines_all(tree, package)
    out["typing"] = typing_imports(tree, package) if "TYPE_CHECKING" in text else {}
    out["dirrel"] = dir_relative_imports(tree, package) if "from ." in text else []
    facts ={} if is_test else code_facts(tree, module, package)
    if facts:
        out["facts"] = {"module": module, "imports": facts["imports"], "instances": facts["instances"],
                        "classes": facts["classes"], "injected": facts["injected"],
                        "functions": {s: {k: f[k] for k in FACT_KEYS if k in f} for s, f in facts["functions"].items()}}
        out["bound"] = sorted(set(out["bound"]) | set(facts["imports"]))
        routes = [e for e in facts["entrypoints"] if e["kind"] == "http_route"]
        out["keys"] += [("route", e["name"], e.get("line", 0), e.get("symbol", "")) for e in routes]
    aliases = {a.asname or a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    module_level = [n for s in tree.body if not isinstance(s, DEFS) for n in own_nodes([s])]
    out["keys"] += [(k, v, line, "") for k, v, line in keys_of(module_level)]
    if not is_test:
        out["writes"] += sql_writes(module_level, module, rel, "")

    def consts(body, prefix):
        for node in body:
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else \
                node.target if isinstance(node, ast.AnnAssign) and node.value is not None else None
            pairs = [(target, node.value)] if isinstance(target, ast.Name) else []
            if isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List)) \
                    and len(target.elts) == len(node.value.elts):     # ATOL, RTOL = 1e-8, 1e-9
                pairs = [(t, v) for t, v in zip(target.elts, node.value.elts) if isinstance(t, ast.Name)]
            for name, value in pairs:
                if name.id.strip("_").isupper() and len(name.id.strip("_")) > 1 and (src := _src(value, CONST_CHARS)):
                    out["nodes"].append({"qual": prefix + name.id, "kind": "const", "line": node.lineno,
                                         "end": node.end_lineno, "sig": src, "doc": "", "cls": prefix.rstrip("."),
                                         "fp": hashlib.sha256(ast.dump(value).encode()).hexdigest()[:20],
                                         "shape": [], "size": 0})

    def visit(body, prefix, cls, in_function):
        if not in_function:
            consts(body, prefix)
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefix + node.name
                is_class = isinstance(node, ast.ClassDef)
                kind = "class" if is_class else "test" if is_test else "method" if cls else "function"
                own = own_nodes(strip_doc(node.body) + ([] if is_class else
                                node.args.defaults + [d for d in node.args.kw_defaults if d is not None]))
                if is_class:
                    sig = "(" + ", ".join(ast.unparse(b) for b in node.bases) + ")"
                else:
                    sig = "(" + ast.unparse(node.args) + ")" + (" -> " + ast.unparse(node.returns) if node.returns else "")
                row = {"qual": qual, "kind": kind, "line": min([d.lineno for d in node.decorator_list] + [node.lineno]),
                       "end": node.end_lineno,
                       "column": len(text.splitlines()[node.lineno-1].encode('utf-8')[:node.col_offset].decode('utf-8')) + 1,
                       "end_column": len(text.splitlines()[node.end_lineno-1].encode('utf-8')[:node.end_col_offset].decode('utf-8')) + 1,
                       "sig": sig[:160], "cls": cls or "",
                       "doc": (ast.get_docstring(node) or "").strip().split("\n")[0][:100],
                       "fp": fingerprint(node, node.name), "shape": shape(own), "size": len(own)}
                if not is_test and not is_class:
                    raw = fgs.analyze(own, aliases)
                    raw["sites"] = decision_sites(own)
                    raw['results'] = [(n.lineno,'return',n.value.value) for n in own if isinstance(n,ast.Return) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)]
                    raw['results'] += [(n.lineno,'raise',a.value) for n in own if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call)
                                       for a in n.exc.args if isinstance(a,ast.Constant) and isinstance(a.value,str)]
                    raw["consts"] = _const_reads(own)
                    params = [a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
                    raw["envk"], raw["envs"], via, held = env_reads(own, tuple(params))
                    if via:                                  # a getenv wrapper: where its callers put the name
                        bound = 1 if cls and params and params[0] in ("self", "cls") else 0
                        raw["envp"] = [[params.index(v) - bound if v in params[:len(node.args.posonlyargs)
                                                                                   + len(node.args.args)] else -1, v]
                                       for v in via]
                    raw["cargs"] = call_args(own)
                    env_linked(raw["sites"], held)
                    raw["subj"] = subjects(own)
                    row["raw"] = {k: v for k, v in raw.items() if v}
                    out["keys"] += [(k, v, line, qual) for k, v, line in keys_of(own)]
                    out["keys"] += [("sql", t[4:], node.lineno, qual) for t in raw["sr"] + raw["sw"] if t.startswith("sql:")]
                    out["writes"] += sql_writes(own, module, rel, qual)
                    out["keys"] += [("file", f, node.lineno, qual) for f in raw["fr"] + raw["fw"]]
                out["nodes"].append(row)
                if is_class:
                    visit(node.body, qual + ".", qual, False)
                else:
                    visit(node.body, qual + ".", None, True)
            elif isinstance(node, (ast.If, ast.Try, ast.With)) and not in_function:
                visit(node.body + getattr(node, "orelse", []) + getattr(node, "finalbody", [])
                      + [s for h in getattr(node, "handlers", []) for s in h.body], prefix, cls, False)
    visit(tree.body, "", None, False)
    return out


def extract(root: Path, rel: str, data: bytes, module: str, is_test: bool) -> dict:
    """One file-fact interface; Python remains native and grammars load on demand."""
    from .readers.registry import language_for, extract as foreign
    language = language_for(rel)
    if language != 'python':
        from importlib.metadata import PackageNotFoundError
        from .readers.common import GRAMMARS
        from flowguard.map.common import MapError
        try:
            return foreign(root, rel, data, module, is_test)
        except (PackageNotFoundError, ModuleNotFoundError) as error:
            missing = getattr(error, 'name', None)
            if missing not in {'tree-sitter', 'tree_sitter', *GRAMMARS[language][:2]}:
                raise
            raise MapError(f'{rel}: {language} reader unavailable: missing {missing}; '
                           'install the optional dependencies with pip install '
                           '"flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git"') from error
    facts = _extract_python(root, rel, data, module, is_test)
    facts['language'] = 'python'
    import sys
    facts['parser'] = dict(engine='stdlib ast', version=sys.version.split()[0])
    return facts
