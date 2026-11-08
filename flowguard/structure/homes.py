"""Other homes (C-5): functions elsewhere that seem to decide what one node decides.

A single decision-site postings query over the generated store. Candidates come
from the postings index (token -> nodes): only nodes sharing a realized decision-site
signature are scored. The public ranking uses strength, coverage score and identity.
A candidate is a pointer, not proof.
"""
from __future__ import annotations

import json
import math
from collections import Counter

from . import features as ff
from . import decide
from .store import unpack

FUNCS = "('function','method')"


class Scorer:
    def __init__(self, con):
        self.con = con
        self.n = con.execute(f"SELECT COUNT(*) FROM node WHERE kind IN {FUNCS}").fetchone()[0] or 1
        self._df: dict[str, int] = {}


    def df(self, toks) -> dict[str, int]:
        need = [t for t in toks if t not in self._df]
        for i in range(0, len(need), 500):
            chunk = need[i:i + 500]
            for t in chunk:
                self._df[t] = 0
            for tok, count in self.con.execute(
                    f"SELECT t.tok, COUNT(*) FROM tok t JOIN post p ON p.tid = t.tid WHERE t.tok IN "
                    f"({','.join('?' * len(chunk))}) GROUP BY t.tok", chunk):
                self._df[tok] = count
        return self._df


    def row(self, ident: str):
        return self.con.execute("SELECT nid, id, kind, shape, size FROM node WHERE id = ?", (ident,)).fetchone()

    def common(self) -> frozenset:
        """Common decision fields from the same signature index used by candidate ranking."""
        build = self.con.execute("SELECT v FROM meta WHERE k='build'").fetchone()[0]
        cached = self.con.execute("SELECT v FROM meta WHERE k='common'").fetchone()
        if cached and json.loads(cached[0])[0] == build:
            return frozenset(json.loads(cached[0])[1])
        parts: dict[int, set] = {}
        for nid, tok in self.con.execute(
                "SELECT p.nid, t.tok FROM post p JOIN tok t ON t.tid = p.tid WHERE t.kind IN "
                "('sg') AND t.tok LIKE 'sg:field:%'"):
            body = tok[len('sg:field:'):]
            parts.setdefault(nid, set()).update(ff.name_parts(body))
        count = Counter(p for s in parts.values() for p in s)
        out = sorted(p for p, c in count.items() if c > ff.GENERIC_SHARE * self.n) if self.n >= 40 else []
        self.con.execute("INSERT OR REPLACE INTO meta VALUES('common', ?)", (json.dumps([build, out]),))
        self.con.commit()
        return frozenset(out)














# ---- decision-site matching ---------------------------------------------------------------------------

SIG_WEIGHT = {"id": 3.0, "env": 3.0, "cfg": 2.5, "set": 3.0, "tup": 2.5, "v": 2.5, "f": 2.5, "field": 0.5, "r": 1.5, "n": 1.5, "t": 1.0,
              "m": 1.0, "s": 1.5, "k": 1.0, "p": 1.0, "flag": 0.8}
STRONG_SIG = {"id", "env", "cfg", "set", "tup", "v", "f"}   # one shared site of these kinds names the decision
SHOWN_FIRST = ("id", "env", "v", "set", "f", "tup", "cfg", "n", "t", "m", "s", "k", "p", "flag")
RARE_SHARE = 0.002                                          # a large number in fewer functions than this is rare


def site_text(field: str, op: str, const: str) -> str:
    if op in ("is None", "is not None", "truth"):
        return f"{field} {op if op != 'truth' else ''}".strip()
    return f"{field} {OPS.get(op, op)} {const}".strip()


def sig_kind(tok: str) -> str:
    if tok.startswith("env:"):
        return "env"
    return tok[3:].split(":", 1)[0]


def _pick_rows(rows: list, line: int, text: str = "") -> list:
    """The map's sites of one realized site: those on its line (the engine counts the test's line, the map
    the statement's), else those of the nearest statement before it; among several, the ones whose sides
    the realized site's text names."""
    here = [r for r in rows if r[0] == line] or [r for r in rows if r[0] == max((x[0] for x in rows if x[0] <= line),
                                                                                  default=-1)]
    if text and len(here) > 1:
        named = [r for r in here if (r[1] and r[1] in text) or (r[3] and r[3] in text)]
        return named or here
    return here


def site_groups(con, fid: str, sites=None) -> tuple[list[dict], str]:
    """The decision-site signature groups of a home: one per realized site (`sites`: [(node, line, text)],
    sites of the home or of functions it calls), or, without them, one per decision site of the home plus
    its environment variables and config keys. Returns (groups, mode)."""
    groups, mode = [], "realized sites" if sites is not None else "the home's sites"
    by_node: dict = {}
    for node, line, text in (sites or ()):
        if node not in by_node:
            by_node[node] = con.execute("SELECT line, field, op, const, sigs FROM site WHERE node = ? ORDER BY line",
                                        (node,)).fetchall()
        for r in _pick_rows(by_node[node], line, text):
            sigs = set(json.loads(r[4] or "[]"))
            if sigs:
                groups.append({"node": node, "line": r[0], "field": r[1], "text": site_text(r[1], r[2], r[3]), "sigs": sigs})
    if not groups and sites is None:
        mode = "the home's sites"
        for r in con.execute("SELECT line, field, op, const, sigs FROM site WHERE node = ? ORDER BY line", (fid,)):
            sigs = set(json.loads(r[4] or "[]"))
            if sigs:
                groups.append({"node": fid, "line": r[0], "field": r[1], "text": site_text(r[1], r[2], r[3]), "sigs": sigs})
        covered_env = {t for g in groups for t in g["sigs"]}
        for (tok,) in con.execute("SELECT t.tok FROM post p JOIN tok t ON t.tid = p.tid JOIN node n ON n.nid = p.nid "
                                  "WHERE n.id = ? AND (t.kind = 'env' OR t.tok LIKE 'sg:cfg:%') ORDER BY t.tok", (fid,)):
            if tok not in covered_env:
                groups.append({"node": fid, "line": 0, "text": tok, "sigs": {tok}})
        row = con.execute('SELECT raw FROM node WHERE id=?',(fid,)).fetchone()
        for line,kind,text in unpack(row[0]).get('results',[]) if row else []:
            if text.strip().casefold() not in ('','pass','error','ok'):
                groups.append(dict(node=fid,line=line,field='',text=kind+' '+repr(text),sigs={'sg:r:'+text}))
    merged: dict = {}
    for g in groups:                                   # one group per distinct signature set
        merged.setdefault(frozenset(g["sigs"]), g)
    return list(merged.values()), mode


OPS = {"Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=", "Eq": "==", "NotEq": "!=", "In": "in", "NotIn": "not in",
       "truth": "", "has": "has", "lacks": "lacks"}


def site_homes(con, fid: str, sites=None, words: str = "", exclude=(), groups=None) -> list[dict]:
    """Other homes by decision-site matching: every function holding a site with one of the home's (or the
    rule's realized) site signatures, with a coverage score weighted by kind x idf.
    A function that does much else is still a candidate. Listed when it shares one site of a
    strong kind (a constant identity, an environment variable or config key, a literal set, tuple or
    version, a value on a field of the same name, or a large rare number), or at least half of the sites
    (two or more) of weaker kinds. Each result names the matched sites."""
    sc = Scorer(con)
    home = sc.row(fid)
    if home is None:
        raise KeyError(f"no node {fid} on the map")
    if groups is None:
        groups, mode = site_groups(con, fid, sites)
    else:
        mode = 'old sites'
    if not groups:
        return []
    common = sc.common()
    toks = sorted({t for g in groups for t in g["sigs"]})
    df = sc.df(toks)
    n = sc.n

    def weight(t):
        return SIG_WEIGHT.get(sig_kind(t), 1.0) * math.log(1 + n / max(df.get(t, 0), 1))

    def strong(t):
        kind = sig_kind(t)
        if kind == "f":
            return t[5:].partition("@")[0] not in common
        if kind == "n":
            body = t[5:].removeprefix("bytes:")
            try:
                big = abs(float(body)) >= decide.BIG
            except ValueError:
                return False
            return big and df.get(t, 0) <= max(5, RARE_SHARE * n)
        if kind == 'r':
            return df.get(t,0) <= max(5,RARE_SHARE*n)
        return kind in STRONG_SIG
    skip = set(exclude) | {fid} | {g["node"] for g in groups}
    hits: dict[int, dict[int, set]] = {}               # candidate -> {group: the group's signatures it shares}
    for gi, g in enumerate(groups):
        for t in g["sigs"]:
            if df.get(t, 0) <= 0:
                continue
            for (nid,) in con.execute("SELECT p.nid FROM post p JOIN tok t ON t.tid = p.tid WHERE t.tok = ?", (t,)):
                hits.setdefault(nid, {}).setdefault(gi, set()).add(t)

    def order(t):
        return (SHOWN_FIRST.index(sig_kind(t)) if sig_kind(t) in SHOWN_FIRST else 99, t)
    best_of = [max(weight(t) for t in g["sigs"]) for g in groups]
    need = max(2, math.ceil(len(groups) / 2))
    up = {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'calls'", (fid,))}
    down = {d for (d,) in con.execute("SELECT dst FROM edge WHERE src = ? AND kind = 'calls'", (fid,))}
    out = []
    for nid, matched in hits.items():
        row = con.execute(f"SELECT id, kind, doc FROM node WHERE nid = ? AND kind IN {FUNCS}", (nid,)).fetchone()
        if row is None or row[0] in skip:
            continue
        field_only = {t for said in matched.values() for t in said if t.startswith('sg:field:') and t[9:] not in common}
        cid = row[0]
        crow = con.execute("SELECT line, field, op, const, sigs FROM site WHERE node = ? ORDER BY line", (cid,)).fetchall()
        rsigs = [set(json.loads(r[4] or "[]")) for r in crow]
        is_strong = any(group_strong(groups[gi]["sigs"], ts, rsigs, strong) for gi, ts in matched.items())
        # A sole duration comparison loses its field token during unit
        # normalization. Preserve its exact source field as a weak clue, only
        # when the normalized boundary set also agrees. Do not relax a
        # multi-site decision to one shared time value.
        time_field = False
        if len(groups) == 1 and groups[0].get('field'):
            boundary = {token for token in groups[0]['sigs'] if token.startswith('sg:t:')}
            time_field = bool(boundary) and any(
                row[1] == groups[0]['field'] and boundary == {token for token in sigs if token.startswith('sg:t:')}
                for row, sigs in zip(crow, rsigs))
        shared_predicate = any(t.startswith('sg:p:') for said in matched.values() for t in said)
        if not is_strong and len(matched) < need and not field_only and not shared_predicate and not time_field:
            continue
        got = sum(max(weight(t) for t in ts) for ts in matched.values())
        score = got / sum(best_of)
        shown = []
        for gi, ts in sorted(matched.items(), key=lambda kv: (min(order(t) for t in kv[1]), kv[0])):
            said = sorted(ts, key=order)
            t = said[0]
            at = next((r for r in crow if set(said) & set(json.loads(r[4] or "[]"))), None)
            if at is None and t.startswith("env:"):
                key = con.execute("SELECT line FROM key WHERE node = ? AND kind = 'env' AND value = ? ORDER BY line",
                                  (cid, t[4:])).fetchone()
                where = f"L{key[0]} " if key else ""
            else:
                where = f"L{at[0]} {site_text(at[1], at[2], at[3])}"[:60] + " " if at else ""
            shown.append(f"{where}({', '.join(dict.fromkeys(decide.say_signature(x) for x in said[:2]))})")
        relation = "calls the home" if cid in up else "called by the home" if cid in down else ""
        out.append({"id": cid, "score": round(min(score, 1.0), 2), "relation": relation, "how": "sites",
                    "strength": "strong" if is_strong else "weak", "matched": len(matched), "of": len(groups),
                    "reason": ("shared temporal field (candidate only)" if time_field and not is_strong else
                               "shared decision field" if field_only and not is_strong else "same decision sites") + f" ({len(matched)} of {len(groups)} {mode}): " + "; ".join(shown[:3])
                              + (f"; +{len(shown) - 3} more" if len(shown) > 3 else ""),
                    "sites": shown})
    return out


def group_strong(gsigs: set, shared: set, rsigs: list[set], strong) -> bool:
    """Does a candidate's match of one home site name that decision? Its shared signatures must include a
    strong one, at a candidate site that does not compare with another named constant: two sites that
    compare with differently named constants of equal value (RETURN_DAYS and LOYALTY_DAYS, both 30 days)
    are two decisions that happen to agree today. Environment and config signatures are the function's."""
    home_ids = {t for t in gsigs if t.startswith("sg:id:")}
    for t in shared:
        if not strong(t):
            continue
        if t.startswith(("env:", "sg:cfg:")) or t.startswith(("sg:id:",'sg:r:')):
            return True
        for rs in rsigs:
            if t in rs:
                own_ids = {x for x in rs if x.startswith("sg:id:")}
                if not (home_ids and own_ids and not home_ids & own_ids):
                    return True
    return False


def other_homes(con, fid: str, k=None, words: str = "", decides=None,
                not_same=(), weak: bool = False, sites=None) -> list[dict]:
    """One postings query over the declared decision sites; never execute candidates."""
    if Scorer(con).row(fid) is None:
        raise KeyError(f"no node {fid} on the map")
    if decides:
        words += ' ' + (decides if isinstance(decides,str) else ' '.join(decides))
    by_site = site_homes(con, fid, sites, words, not_same)
    strong = [row for row in by_site if row['strength']=='strong']
    low = [row for row in by_site if row['strength']=='weak']
    return (strong[:k] if k is not None else strong) + ((low[:k] if k is not None else low) if weak else [])


def ranked(candidates, k=None):
    """The public candidate order and per-strength limit, applied after all homes merge."""
    rows = sorted(candidates, key=lambda row: (row['strength'] != 'strong', -row['score'], row['id']))
    if k is not None:
        rows = [row for strength in ('strong', 'weak') for row in [c for c in rows if c['strength'] == strength][:k]]
    return rows
