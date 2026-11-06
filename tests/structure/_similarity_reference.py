"""Frozen pre-replacement whole-function scorer, only a regression comparison.

The public map uses one site-postings algorithm. This reference keeps the
original prototype comparison (the old method misses busy-function copies).
Do not route product queries through it or evolve it as another implementation.
"""
from __future__ import annotations
import json
import math
from collections import Counter
import _legacy_features as ff
import _legacy_decide as decide
from pathlib import Path
from flowguard.structure.store import SKETCH, shape_list
FUNCS = "('function','method')"
class Scorer:
    def __init__(self, con):
        self.con = con
        self.n = con.execute(f"SELECT COUNT(*) FROM node WHERE kind IN {FUNCS}").fetchone()[0] or 1
        self._df: dict[str, int] = {}

    def feats(self, nid: int) -> set[str]:
        return {t for (t,) in self.con.execute(
            "SELECT t.tok FROM legacy_post p JOIN legacy_tok t ON t.tid = p.tid WHERE p.nid = ? AND t.kind NOT IN ('sh', 'sg')",
            (nid,))}

    def df(self, toks) -> dict[str, int]:
        need = [t for t in toks if t not in self._df]
        for i in range(0, len(need), 500):
            chunk = need[i:i + 500]
            for t in chunk:
                self._df[t] = 0
            for tok, count in self.con.execute(
                    f"SELECT t.tok, COUNT(*) FROM legacy_tok t JOIN legacy_post p ON p.tid = t.tid WHERE t.tok IN "
                    f"({','.join('?' * len(chunk))}) GROUP BY t.tok", chunk):
                self._df[tok] = count
        return self._df

    def weight(self, tok: str) -> float:
        kind = tok.split(":", 1)[0]
        return decide.WEIGHT.get(kind, 0.5) * math.log(1 + self.n / max(self._df.get(tok, 0), 1)) \
            * (0.3 if ff.generic(tok) else 1.0)

    def row(self, ident: str):
        return self.con.execute("SELECT nid, id, kind, shape, size FROM node WHERE id = ?", (ident,)).fetchone()

    def common(self) -> frozenset:
        """fgmap's generic_parts: name parts used by more than 15% of the functions (cached per build)."""
        build = self.con.execute("SELECT v FROM meta WHERE k='build'").fetchone()[0]
        cached = self.con.execute("SELECT v FROM meta WHERE k='common'").fetchone()
        if cached and json.loads(cached[0])[0] == build:
            return frozenset(json.loads(cached[0])[1])
        parts: dict[int, set] = {}
        for nid, tok in self.con.execute(
                "SELECT p.nid, t.tok FROM legacy_post p JOIN legacy_tok t ON t.tid = p.tid WHERE t.kind IN "
                "('d','cmp','flag','bnd','eq','pred')"):
            body = tok.partition(":")[2].partition("@")[0].partition("=")[0]
            parts.setdefault(nid, set()).update(ff.name_parts(body))
        count = Counter(p for s in parts.values() for p in s)
        out = sorted(p for p, c in count.items() if c > ff.GENERIC_SHARE * self.n) if self.n >= 40 else []
        self.con.execute("INSERT OR REPLACE INTO meta VALUES('common', ?)", (json.dumps([build, out]),))
        self.con.commit()
        return frozenset(out)

def covered(con, ident: str, feats: set) -> dict[str, set[str]]:
    """{token: covering tokens} for the readings of one site (fgmap's twin rule): a site's constant identity
    (`id:limits:MIN_PYTHON`) and its value readings (`tup:3,12`, `ver:3.12`, `val:1073741825`) are one
    decision, so once either is shared the other is no miss; so are the boundaries on a field
    (`bnd:ended@4`, `dur:259200` for a `days` field) and the `eq:` tokens of a literal set's items."""
    out: dict[str, set[str]] = {}

    def add(tok: str, cover: str) -> None:
        if tok != cover:
            out.setdefault(tok, set()).add(cover)
    for op, value, identity, vkind, const in con.execute(
            "SELECT op, value, identity, vkind, const FROM site WHERE node = ?", (ident,)):
        row = {"op": op, "value": value, "identity": identity, "vkind": vkind, "const": const}
        readings = decide.value_tokens(row) | ({"id:" + identity} if identity else set())
        for a in readings:
            for b in readings:
                add(a, b)
        if vkind in ("set", "str") and value:          # x in ("1", "true"): eq:get=1 and eq:getenv=1 are one set;
            loaded = json.loads(value)                  # (major, minor) < (3, 13): eq:minor=13 is its item;
            items = {str(i)[:30] for i in (loaded if vkind == "set" else [loaded])}   # v != "3.12.10": its eq: token
            for tok in feats:
                if tok.startswith("eq:") and tok.partition("=")[2] in items:
                    for r in readings:
                        add(tok, r)
        for subject, parts in decide.SUBJECT_NAMES.items():   # sys.version_info, python_version(): the subject
            if f"subj:{subject}" in feats:
                for tok in feats:
                    if tok.split(":", 1)[0] in ("flag", "cmp", "eq", "c") and \
                            tok.partition(":")[2].partition("=")[0] in parts:
                        add(tok, f"subj:{subject}")
        if vkind == "num" and value:
            v = float(json.loads(value))
            nums = {v, v + 1} | {x * step for x in (v, v + 1) for step in ff.STEPS}
            for tok in feats:
                kind, _, body = tok.partition(":")
                if kind not in ("bnd", "thr", "dur"):
                    continue
                at = body.rpartition("@")[2] if kind == "bnd" else body
                try:
                    hit = float(at.removeprefix("dur")) in nums
                except ValueError:
                    continue
                if hit:
                    for r in readings:
                        add(tok, r)
    return out

def side_total(feats: set, shared: set, cover: dict, wt) -> float:
    """One side's weight for the two-sided score: shared tokens, plus each missed decision once. A token
    another reading of which is shared is no miss, and the readings of one site that all miss count once,
    at the largest weight (the identity, tuple and version of `< MAX_PYTHON` are one boundary)."""
    total, missed = 0.0, set()
    for t in sorted(feats, key=lambda t: (-wt(t), t)):
        if t in shared:
            total += wt(t)
            continue
        group = cover.get(t, set())
        if ff.twin_in(t, shared) or group & shared or group & missed:
            continue
        missed.add(t)
        total += wt(t)
    return total or 1.0

def decision_tokens(feats: set) -> set:
    return {t for t in feats if t.split(":", 1)[0] in decide.DECISION and not ff.generic(t)}

def _edges(con, src: str, kind: str) -> set[str]:
    return {d for (d,) in con.execute(
        "SELECT dst FROM edge WHERE src = ? AND kind = ? AND (prov != 'guessed' OR EXISTS (SELECT 1 FROM edge o "
        "WHERE o.src = edge.src AND o.dst = edge.dst AND o.prov = 'observed'))", (src, kind))}

def closure(sc: Scorer, fid: str, words: str, common: frozenset, decides, depth: int = 2):
    """rules.decision_closure on the store: (tokens of its deciders, deciders, their other users, callees)."""
    con = sc.con

    def walk(kind: str) -> set:
        seen, frontier = set(), {fid}
        for _ in range(depth):
            frontier = {c for f in frontier for c in _edges(con, f, kind) if c != fid and c not in seen}
            seen |= frontier
        return seen
    callees, fed = walk("calls"), walk("feeds")
    tokens, deciders = set(), []
    for c in sorted(callees):
        row = sc.row(c)
        if row is None or row[2] not in ("function", "method"):
            continue
        dec = decision_tokens(sc.feats(row[0]))
        named = ff.focus_of(words, dec, common, decides) if dec and (words or decides) else set()
        if dec and (c in fed or named):
            tokens |= dec
            deciders.append(c)
    users = set()
    for c in deciders:
        users |= {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'calls' AND prov != 'guessed'", (c,))}
    return tokens, deciders, sorted(users - callees - {fid}), callees

def similar_homes(con, fid: str, k: int = 5, words: str = "", decides=None, threshold: float = 0.3,
                  not_same=(), weak: bool = False) -> list[dict]:
    """Other homes by whole-function decision likeness (fgmap's two-sided score): [{id, score, reason,
    strength, relation}] (strong first). The rule's words weight the decisions they name; they never
    select or demote a candidate."""
    _reference_postings(con)
    sc = Scorer(con)
    home = sc.row(fid)
    if home is None:
        raise KeyError(f"no node {fid} on the map")
    common = sc.common()
    extra, deciders, users, callees = closure(sc, fid, words, common, decides)
    own = sc.feats(home[0])
    hfull = own | extra
    focus = ff.focus_of(words, hfull, common, decides) if (words or decides) else set()
    exclude = set(deciders) | set(not_same) | {fid}
    neutral: dict[str, set] = {}
    for c in deciders:
        dec = decision_tokens(sc.feats(sc.row(c)[0]))
        for (u,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'calls'", (c,)):
            neutral.setdefault(u, set()).update(dec)
    gen = sorted(decision_tokens(hfull))         # the words re-rank (FOCUS weight); they never select candidates
    df = sc.df(gen)
    cand: Counter = Counter()
    for tok in gen:
        if df[tok] > 0:
            w = sc.weight(tok)
            for (nid,) in con.execute("SELECT p.nid FROM legacy_post p JOIN legacy_tok t ON t.tid = p.tid WHERE t.tok = ?", (tok,)):
                cand[nid] += w
    hshape = shape_list(home[3])
    if home[4] >= 20:
        sk = [f"sh:{v}" for v in hshape[:SKETCH]]
        sdf = sc.df(sk)
        for tok in sk:
            if sdf[tok] > 0:
                for (nid,) in con.execute("SELECT p.nid FROM legacy_post p JOIN legacy_tok t ON t.tid = p.tid WHERE t.tok = ?", (tok,)):
                    cand[nid] += 0.01
    rows = []
    for nid, _ in cand.most_common():
        r = con.execute(f"SELECT nid, id, kind, shape, size FROM node WHERE nid = ? AND kind IN {FUNCS}", (nid,)).fetchone()
        if r and r[1] not in exclude:
            rows.append(r)
    feats = {r[1]: sc.feats(r[0]) for r in rows}
    hcover = covered(con, fid, hfull)
    sc.df(set(hfull).union(*feats.values()) if feats else hfull)
    up = {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'calls'", (fid,))}
    down = {d for (d,) in con.execute("SELECT dst FROM edge WHERE src = ? AND kind = 'calls'", (fid,))} | callees

    def wt(t):
        return sc.weight(t) * (ff.FOCUS if t in focus else 1.0)
    out, low = [], []
    for r in rows:
        cid, cfeats = r[1], feats[r[1]]
        hset = hfull - neutral.get(cid, set())
        shared = hset & cfeats
        decision = sorted((t for t in shared if t.split(":", 1)[0] in decide.DECISION and not ff.generic(t)),
                          key=lambda t: (-wt(t), t))
        shape = ff.jaccard(hshape, shape_list(r[3])) if min(home[4], r[4]) >= 20 else 0.0
        if not decision and shape < 0.85:
            continue
        ccover = covered(con, cid, cfeats)
        got = sum(wt(t) for t in shared)
        home_all = side_total(hset, shared, hcover, wt)
        cand_all = side_total(cfeats, shared, ccover, wt)
        score = max(math.sqrt(got / home_all * got / cand_all), 0.9 * shape if shape >= 0.85 else 0.0)
        if score < threshold:
            continue
        named, shown = [], set()
        for t in decision:   # a bare value (a duration, a threshold, a large number) is a constant, not a decision:
            if t.split(":", 1)[0] not in ("dur", "thr", "val") and not ff.twin_in(t, shown):   # site matching
                named.append(t)                                                                # weighs those
                shown.add(t)
        consts = [t for t in decision if t.startswith(("dur:", "thr:", "val:"))][:1]
        tail = f"; code shape {shape:.2f}" if shape >= 0.85 else ""
        relation = ("calls the home" if cid in up else "called by the home" if cid in down
                    else "also calls its deciders" if cid in users else "")
        item = {"id": cid, "score": round(min(score, 1.0), 2), "relation": relation}
        hid, cid_ids = {t for t in hset if t.startswith("id:")}, {t for t in cfeats if t.startswith("id:")}
        if hid and cid_ids and not hid & cid_ids and shape < 0.85 and \
                all(t.split(":", 1)[0] in ("bnd", "dur", "thr", "val") for t in decision):
            low.append({**item, "reason": "same value under other named constants: " +   # GRACE_DAYS / REMINDER_DAYS
                        ", ".join(decide.say(t) for t in decision[:2]) + tail, "strength": "weak"})
        elif len(decision) == 1 and decision[0].startswith("pred:") and shape < 0.85:
            low.append({**item, "reason": "same predicate only: " + decide.say(decision[0]) + tail, "strength": "weak"})
        elif named or shape >= 0.85:
            reason = ("same decision: " + ", ".join(decide.say(t) for t in named[:3]) if named else "") + tail
            out.append({**item, "reason": reason.lstrip("; "), "strength": "strong", "how": "similar"})
        else:
            low.append({**item, "reason": "same constant only: " + ", ".join(decide.say(t) for t in consts) + tail,
                        "strength": "weak"})
    key = lambda x: (-x["score"], x["id"])
    result = sorted(out, key=key)
    low = sorted(low, key=key)
    return (result[:k] if k is not None else result) + ((low[:k] if k is not None else low) if weak else [])


def _reference_postings(con):
    """Use the original whole-function inputs of the one frozen busy-function example.

    Product builds no longer calculate these unused tokens. Fingerprints prevent
    a changed example from silently consuming an unrelated frozen observation.
    """
    frozen = json.loads((Path(__file__).parent / 'fixtures/whole_function_posts.json').read_text())
    actual = {ident:(nid,fp) for nid,ident,fp in con.execute(
        "SELECT nid,id,fp FROM node WHERE kind IN ('function','method')")}
    assert set(actual) == set(frozen), 'the frozen whole-function example changed'
    assert all(actual[ident][1] == row['fp'] for ident,row in frozen.items())
    con.execute('CREATE TEMP TABLE IF NOT EXISTS legacy_tok(tid INTEGER PRIMARY KEY,tok TEXT,kind TEXT)')
    con.execute('CREATE TEMP TABLE IF NOT EXISTS legacy_post(tid INTEGER,nid INTEGER)')
    con.execute('DELETE FROM legacy_post')
    con.execute('DELETE FROM legacy_tok')
    tids = {}
    for ident,row in frozen.items():
        for tok in row['tokens']:
            if tok not in tids:
                tids[tok] = len(tids)+1
                con.execute('INSERT INTO legacy_tok VALUES(?,?,?)',(tids[tok],tok,tok.partition(':')[0]))
            con.execute('INSERT INTO legacy_post VALUES(?,?)',(tids[tok],actual[ident][0]))
