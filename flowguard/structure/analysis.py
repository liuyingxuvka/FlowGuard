"""Verbatim excerpt of fgmap/structure.py (fgmap 0.2.0, sha256 8a8da264afd919c8...): the per-function
analysis fgmap's features read, without fgmap's file reader (the design does not port it).

Kept: FILE_RE 26-27; SQL_RE 28-28; SQL_WORDS 29-30; WRITE_CALLS 31-31; COMMON 32-36; DEFS 37-37; dotted 78-86; sql_names 89-107; field_of 110-119; ends 122-124; analyze 127-248; shape_of 251-253.
"""
from __future__ import annotations

import ast
import re
import zlib
from collections import defaultdict

from . import features


FILE_RE = re.compile(r"^[\w./-]*\w\.(?:json|jsonl|csv|tsv|txt|ya?ml|toml|db|sqlite3?|md|log|ini|cfg|"
                     r"xml|html|pkl|parquet|npy|npz)$", re.I)


SQL_RE = re.compile(r"^\s*(select|insert|update|delete|create|with|replace)\s", re.I)


SQL_WORDS = {"and", "or", "not", "null", "is", "in", "like", "select", "from", "where", "set", "values",
             "as", "on", "by", "into", "table", "exists", "if", "count", "sum", "max", "min", "avg"}


WRITE_CALLS = {"write", "write_text", "write_bytes", "dump", "to_csv", "to_json", "save", "savez", "writerow"}


COMMON = {"get", "items", "keys", "values", "append", "extend", "pop", "update", "add", "remove", "join",
          "split", "strip", "format", "read", "write", "close", "open", "copy", "sort", "index", "count",
          "replace", "startswith", "endswith", "lower", "upper", "encode", "decode", "setdefault", "run",
          "send", "put", "clear", "insert", "find", "match", "search", "sub", "group", "exists", "mkdir",
          "resolve", "load", "loads", "dump", "dumps", "execute", "fetchone", "fetchall", "main", "__init__"}


DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def dotted(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        if base is None and isinstance(node.value, ast.Call) and dotted(node.value.func) == "super":
            base = "super"
        return f"{base}.{node.attr}" if base else None
    return None


def sql_names(text: str) -> tuple[set, set, list]:
    """Tables/columns read and written by one SQL string, plus `col op constant` comparisons."""
    t = " ".join(text.split())
    reads, writes = set(), set()
    for m in re.finditer(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", t, re.I):
        reads.add("sql:" + m.group(1).lower())
    w = r"\b(?:insert\s+(?:or\s+\w+\s+)?into|replace\s+into|update|create\s+table(?:\s+if\s+not\s+exists)?|delete\s+from)\s+([A-Za-z_][\w.]*)"
    for m in re.finditer(w, t, re.I):
        writes.add("sql:" + m.group(1).lower())
    for m in re.finditer(r"\binto\s+[\w.]+\s*\(([^)]*)\)|\bset\s+(.*?)(?:\bwhere\b|$)|create\s+table[^(]*\((.*)\)", t, re.I):
        chunk = next(g for g in m.groups() if g is not None)
        writes |= {"col:" + c.split()[0].split("=")[0].strip().lower() for c in chunk.split(",") if c.strip()}
    sel = re.search(r"\bselect\s+(.*?)\s+from\b", t, re.I)
    names = re.findall(r"[A-Za-z_]\w*", sel.group(1)) if sel else []
    names += re.findall(r"([A-Za-z_]\w*)\s*(?:=|<|>|!=|\bin\b|\blike\b|\bis\b)", t, re.I)
    reads |= {"col:" + n.lower() for n in names if n.lower() not in SQL_WORDS}
    cmps = [f"{c} {op.replace('<>', '!=').replace('=', '==') if op in ('=', '<>') else op} {v}"
            for c, op, v in re.findall(r"([A-Za-z_]\w*)\s*(>=|<=|<>|!=|=|<|>)\s*(-?\d+(?:\.\d+)?|'[^']*')", t)]
    return reads, writes - {"col:"}, cmps


def field_of(node) -> str | None:
    """The data field an expression reads: obj.attr, obj["key"], obj.get("key", ...)."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    if isinstance(node, ast.Call) and (dotted(node.func) or "").rsplit(".", 1)[-1] == "get" and node.args \
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


def ends(stmts: list) -> bool:
    """Does this branch leave the function (a raise or a return among its own statements)?"""
    return any(isinstance(s, (ast.Raise, ast.Return)) for s in stmts)


def analyze(nodes: list, mod_aliases: set) -> dict:
    """Facts about one function body: calls, data touched, comparisons, numbers, date use, and the
    calls whose results feed a raise, a return or the test of a branch that raises or returns."""
    call_funcs = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    f = {k: set() for k in ("calls", "ar", "aw", "kr", "kw", "sr", "sw", "fr", "fw", "dates", "nums", "flags")}
    cmps, assigns, used, files, writes_files, tests = [], {}, set(), set(), False, []
    sources, fed = defaultdict(list), []   # local -> every value assigned to it; expressions that decide
    for n in nodes:
        if isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            tests.append(n.test)
            if isinstance(n, ast.Assert) or (isinstance(n, (ast.If, ast.While)) and (ends(n.body) or ends(n.orelse))):
                fed.append(n.test)
        elif isinstance(n, ast.BoolOp):
            tests.extend(n.values)
        if isinstance(n, ast.Return) and n.value is not None:
            fed.append(n.value)
        elif isinstance(n, ast.Raise) and n.exc is not None:
            fed.append(n.exc)
        elif isinstance(n, ast.Assign):
            for tgt in n.targets:
                for x in ast.walk(tgt):
                    if isinstance(x, ast.Name):
                        sources[x.id].append(n.value)
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Constant) and isinstance(n.left.value, str) \
                and all(isinstance(op, (ast.In, ast.NotIn)) for op in n.ops):
            f["flags"].add(n.left.value)   # "actor_state_free" in event: a presence test of a data field
        if isinstance(n, ast.Call):
            name = dotted(n.func)
            last = name.rsplit(".", 1)[-1] if name else ""
            if name:
                f["calls"].add(name)
            if last in ("get", "pop", "setdefault") and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str):
                f["kr"].add(n.args[0].value)
            if last in ("timedelta", "relativedelta"):
                f["dates"].add("timedelta")
            elif last in ("now", "today", "utcnow", "time", "monotonic"):
                f["dates"].add("clock")
            if last == "open":
                modes = n.args[1:2] + [k.value for k in n.keywords if k.arg == "mode"]
                writes_files |= any(isinstance(x, ast.Constant) and bool(set(str(x.value)) & set("wax")) for x in modes)
            writes_files |= last in WRITE_CALLS
        elif isinstance(n, ast.Attribute) and id(n) not in call_funcs:
            if not (isinstance(n.value, ast.Name) and n.value.id in mod_aliases):
                (f["aw"] if isinstance(n.ctx, (ast.Store, ast.Del)) else f["ar"]).add(n.attr)
            if n.attr in features.UNIT:
                f["dates"].add("days")
        elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            (f["kw"] if isinstance(n.ctx, (ast.Store, ast.Del)) else f["kr"]).add(n.slice.value)
        elif isinstance(n, ast.Dict):
            f["kw"] |= {k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        elif isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, str) and len(v) < 2000:
                if SQL_RE.match(v):
                    r, w, c = sql_names(v)
                    f["sr"] |= r
                    f["sw"] |= w
                    cmps += c
                elif FILE_RE.match(v.strip()):
                    files.add(v.strip())
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and v not in (0, 1, -1):
                f["nums"].add(v)
        elif isinstance(n, ast.Compare):
            src = ast.unparse(n)
            if len(src) <= 300:   # long comparisons are left out rather than cut into invalid text
                cmps.append(src)
            used |= {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            assigns[n.targets[0].id] = n.value
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub):
            names = {x.id if isinstance(x, ast.Name) else x.attr for x in (n.left, n.right)
                     if isinstance(x, (ast.Name, ast.Attribute))}
            if any(re.search(r"date|time|day|today|now|_at$|_on$", s) for s in names):
                f["dates"].add("diff")
    preds = set()   # calls whose result is tested: `not is_transducer_output(u)`, `known is None`

    def called(e) -> list:
        """The calls an expression's value comes from: the call itself, or a local assigned from one."""
        if isinstance(e, ast.Call) and dotted(e.func):
            return [dotted(e.func)]
        if isinstance(e, ast.Name):
            return [dotted(v.func) for v in sources.get(e.id, []) if isinstance(v, ast.Call) and dotted(v.func)]
        return []
    for t in tests:   # `if member.get('overdue')`, `if not asset['active']`: a decision on a data field
        while isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
            t = t.operand
        if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], (ast.Is, ast.IsNot)) \
                and isinstance(t.comparators[0], ast.Constant) and t.comparators[0].value is None:
            preds |= set(called(t.left))   # known = known_conversion(a, b); if known is None: ...
            continue
        name = field_of(t)
        if name:
            f["flags"].add(name)
        elif isinstance(t, ast.Name):   # actor = event.get("actor"); if not actor: the field, not the local
            f["flags"] |= {x for x in map(field_of, sources.get(t.id, [])) if x}
            preds |= set(called(t))
        elif isinstance(t, ast.Call):
            preds |= set(called(t))
    feeds, seen = set(), set()
    for _ in range(2):   # one step back through a local: why = refusal(m); if why: raise (no further: a
        # name reused for an unrelated value would make every helper a decider)
        more = []
        for e in fed:
            for x in ast.walk(e):
                if isinstance(x, ast.Call) and dotted(x.func):
                    feeds.add(dotted(x.func))
                elif isinstance(x, ast.Name) and x.id in sources and x.id not in seen:
                    seen.add(x.id)
                    more += sources[x.id]
        fed = more
    lex = {}
    for _ in range(3):   # locals used by comparisons, and the locals those use
        for name in sorted(used & assigns.keys() - lex.keys()):
            src = ast.unparse(assigns[name])
            if len(src) <= 300:
                lex[name] = src
            used |= {x.id for x in ast.walk(assigns[name]) if isinstance(x, ast.Name)}
    (f["fw"] if writes_files else f["fr"]).update(files)
    out = {k: sorted(v, key=str) for k, v in f.items()}
    out.update(cmps=cmps, lex=lex, feeds=sorted(feeds), preds=sorted(preds))
    return out


def shape_of(nodes: list) -> list[int]:
    kinds = [type(n).__name__ for n in nodes]
    return sorted({zlib.crc32("/".join(kinds[i:i + 3]).encode()) & 0xFFFFF for i in range(len(kinds) - 2)})[:400]
