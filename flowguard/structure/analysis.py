"""Derived from fgmap/structure.py (fgmap 0.2.0, sha256 8a8da264afd919c8...):
SQL/file keys, lexical bindings and decision feeds for the generated map.
"""
from __future__ import annotations

import ast
import re
import zlib
from collections import defaultdict


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


def ends(stmts: list) -> bool:
    """Does this branch leave the function (a raise or a return among its own statements)?"""
    return any(isinstance(s, (ast.Raise, ast.Return)) for s in stmts)


def analyze(nodes: list, mod_aliases: set) -> dict:
    """Keys and bindings, plus calls feeding a return, raise or an exiting branch."""
    f = {k: set() for k in ("sr", "sw", "fr", "fw")}
    assigns, used, files, writes_files = {}, set(), set(), False
    sources, fed = defaultdict(list), []   # local -> every value assigned to it; expressions that decide
    for n in nodes:
        if isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            if isinstance(n, ast.Assert) or (isinstance(n, (ast.If, ast.While)) and (ends(n.body) or ends(n.orelse))):
                fed.append(n.test)
        if isinstance(n, ast.Return) and n.value is not None:
            fed.append(n.value)
        elif isinstance(n, ast.Raise) and n.exc is not None:
            fed.append(n.exc)
        elif isinstance(n, ast.Assign):
            for tgt in n.targets:
                for x in ast.walk(tgt):
                    if isinstance(x, ast.Name):
                        sources[x.id].append(n.value)
        if isinstance(n, ast.Call):
            name = dotted(n.func)
            last = name.rsplit(".", 1)[-1] if name else ""
            if last == "open":
                modes = n.args[1:2] + [k.value for k in n.keywords if k.arg == "mode"]
                writes_files |= any(isinstance(x, ast.Constant) and bool(set(str(x.value)) & set("wax")) for x in modes)
            writes_files |= last in WRITE_CALLS
        elif isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, str) and len(v) < 2000:
                if SQL_RE.match(v):
                    r, w, _ = sql_names(v)
                    f["sr"] |= r
                    f["sw"] |= w
                elif FILE_RE.match(v.strip()):
                    files.add(v.strip())
        elif isinstance(n, ast.Compare):
            used |= {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            assigns[n.targets[0].id] = n.value
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
    out.update(lex=lex, feeds=sorted(feeds))
    return out


def shape_of(nodes: list) -> list[int]:
    kinds = [type(n).__name__ for n in nodes]
    return sorted({zlib.crc32("/".join(kinds[i:i + 3]).encode()) & 0xFFFFF for i in range(len(kinds) - 2)})[:400]
