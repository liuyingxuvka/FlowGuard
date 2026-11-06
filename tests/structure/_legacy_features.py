"""Frozen old whole-function presentation/focus helpers, used only by its regression reference."""
from __future__ import annotations
import ast
import builtins
import re
from fractions import Fraction
from functools import lru_cache

from flowguard.structure.features import (BUILTIN_NAMES, GENERIC, GENERIC_SHARE, NAME_UNIT, TD, UNIT, _map_key, dur_inside, expr, fold, name_parts, names_in, norm, num, scalar, span, unit_of)

WEIGHT = {"bnd": 3.0, "dur": 3.0, "eq": 2.5, "flag": 2.0, "pred": 2.0, "thr": 1.0, "cmp": 0.8, "d": 1.0, "c": 0.8,
          "n": 0.6, "t": 0.5}



DECISION = ("bnd", "dur", "eq", "flag", "pred")



def generic(tok: str) -> bool:
    """Too common to say which decision it is: a boundary at 0, 1, 2, or a field test on a one- or
    two-letter key (`"at" in event`, `row["id"]`)."""
    kind, _, body = tok.partition(":")
    if kind == "flag":
        return len(body) <= 2
    return body.rpartition("@")[2] in GENERIC if kind == "bnd" else body in GENERIC if kind == "thr" else False



def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0



def say(tok: str) -> str:
    kind, _, body = tok.partition(":")
    if kind == "dur":
        return span(float(body))
    if kind == "bnd":
        name, _, at = body.partition("@")
        return f"{name} vs {span(float(at[3:])) if at.startswith('dur') else at}"
    if kind == "eq":
        return body.replace("=", " == ", 1)
    if kind == "flag":
        return f"tests {body}"
    if kind == "pred":
        return f"tests {body}()"
    return {"d": "data ", "c": "calls ", "thr": "constant ", "n": "number ", "t": "date ", "cmp": "compares "}[kind] + body



STEPS = (1, 60, 3600, 86400, 604800)   # one unit of a duration: the two readings of `.days > 3` differ by one



def twin_in(tok: str, shared: set) -> bool:
    """Is the other reading of this duration token (one unit up or down) among `shared`?"""
    kind, _, body = tok.partition(":")
    if kind == "dur":
        head, value = "dur:", body
    elif kind == "bnd" and "@dur" in body:
        name, _, value = body.partition("@dur")
        head = f"bnd:{name}@dur"
    else:
        return False
    v = float(value)
    return any(f"{head}{num(v + sgn * st)}" in shared for st in STEPS for sgn in (1, -1))



FOCUS = 3.0   # weight of a decision token the rule's own words name



SECONDS = {"second": 1, "sec": 1, "s": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600, "h": 3600,
           "day": 86400, "week": 604800, "wk": 604800, "fortnight": 1209600,
           "秒": 1, "秒钟": 1, "分钟": 60, "小时": 3600, "钟头": 3600, "天": 86400, "周": 604800, "星期": 604800,
           "礼拜": 604800}



EN_NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}



CN_DIGIT = {c: i for i, c in enumerate("零一二三四五六七八九")}



EN_DUR = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?|" + "|".join(EN_NUM) + r")\s*-?\s*"
                    r"(?:(?!(?:per|a|an|each|every|for|of)\b)[a-z]+\s+)?"
                    r"(seconds?|secs?|s|minutes?|mins?|hours?|hrs?|h|days?|weeks?|wks?|fortnights?)\b")



CN_DUR = re.compile(r"(\d+(?:\.\d+)?|[零一二两三四五六七八九十百]+)\s*个?\s*(秒钟|秒|分钟|小时|钟头|天|周|星期|礼拜)")



PLAIN_NUM = re.compile(r"(?<![\w.§/#第-])(\d+(?:\.\d+)?)(?![\w/]|[.-]\d)")   # not 第 2 章, #3, §4.3, 0.8.0



def cn_number(text: str) -> float | None:
    """一 .. 九十九 (and 百), plain digits too: enough for the durations and counts rules name."""
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    total, cur = 0, 0
    for ch in text:
        if ch in CN_DIGIT:
            cur = CN_DIGIT[ch]
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
        else:
            return None
    return float(total + cur)



def durations_in(text: str) -> tuple[set, list]:
    """Durations the words name, in seconds ("3 grace days", "30-day", "48h", "two weeks", "3 天", "两周"),
    and the character spans they use (so their numbers are not read again as plain numbers)."""
    out, spans, low = set(), [], text.lower()
    for m in EN_DUR.finditer(low):
        n = EN_NUM.get(m.group(1))
        n = float(m.group(1)) if n is None else float(n)
        unit = m.group(2).rstrip("s") if m.group(2) not in ("s", "hrs", "wks") else m.group(2)[:-1] or "s"
        out.add(n * SECONDS.get(unit, SECONDS.get(m.group(2), 0)))
        spans.append(m.span())
    for m in CN_DUR.finditer(text):
        n = cn_number(m.group(1))
        if n is not None:
            out.add(n * SECONDS[m.group(2)])
            spans.append(m.span())
    return {d for d in out if d}, spans



def numbers_in(text: str, skip: list) -> set:
    """Plain numbers the words name ("more than 3 items", "at most 50.00"), not dates, versions or durations."""
    out = set()
    for m in PLAIN_NUM.finditer(text):
        if not any(a <= m.start() < b for a, b in skip) and float(m.group(1)) > 2:   # 0, 1, 2 name nothing
            out.add(float(m.group(1)))
    return out



def focus_of(words: str, toks: set, common: frozenset = frozenset(), decides: list | None = None) -> set:
    """Decision tokens of the home that the owner's words name: `overdue` in "overdue members never
    receive a new loan" picks flag:overdue out of everything checkout_problem decides; "3 grace days"
    picks the 3-day boundary, "at most 50.00" the 50 boundary. The words are the owner's, so this cannot
    copy the AI's reading. Words are compared with identifier parts (ASCII words and CJK character pairs,
    `common` parts left out); an identifier written in the words (`expires_on`) matches whole.
    `decides` (a rule's own list, each entry taken from its words) replaces the words when given."""
    from flowguard.structure.query import tokens
    texts = decides if decides else [words]
    common = frozenset() if decides else common
    ws, idents, durs, nums = set(), set(), set(), set()
    for text in texts:
        ws |= tokens(text)
        idents |= {norm(x) for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text) if "_" in x.strip("_")}
        idents |= {norm(x) for x in re.findall(r"`([^`]+)`", text)}
        if decides and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", text.strip()):
            idents.add(norm(text.strip().rpartition(".")[2]))
        d, spans = durations_in(text)
        durs |= d
        nums |= numbers_in(text, spans)
    out = set()
    for t in toks:
        kind, _, body = t.partition(":")
        if kind not in DECISION or generic(t):
            continue
        name = body.partition("@")[0].partition("=")[0]
        if name in idents:
            out.add(t)
        parts = [x for x in name_parts(name) if x not in common]
        if any(x == w or (len(x) >= 6 and len(w) >= 6 and x[:6] == w[:6]) for x in parts for w in ws):
            out.add(t)
        if kind == "dur" or "@dur" in body:
            at = float(body.rpartition("dur")[2])
            if any(abs(at - d) < 1e-6 for d in durs):
                out.add(t)
        elif kind == "bnd" or kind == "eq":
            at = body.rpartition("@")[2] if kind == "bnd" else body.partition("=")[2]
            try:
                v = float(at)
            except ValueError:
                continue
            if any(abs(v - x) < 1e-9 or (x.is_integer() and abs(v - x - 1) < 1e-9) for x in nums):
                out.add(t)   # "more than 3" decides at 4 on the map
    return out
