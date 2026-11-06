"""Frozen old whole-function value tokens, only for the historical regression scorer."""
from __future__ import annotations
import ast
import hashlib
import json
import _legacy_features as ff
from flowguard.structure.decide import BIG, ORDERED, _expr, boundary, version_of

NEW_WEIGHT = {"id": 3.0, "set": 3.0, "tup": 2.5, "ver": 2.5, "val": 2.5, "env": 3.0, "subj": 2.0, "sh": 0.0}



WEIGHT = {**ff.WEIGHT, **NEW_WEIGHT}



DECISION = (*ff.DECISION, "id", "set", "tup", "ver", "val", "env", "subj")



SUBJECT_NAMES = {"python-version": {"version_info", "version", "hexversion", "python_version",
                                     "python_version_tuple"}}



def value_tokens(r: dict) -> set[str]:
    """The value readings of one site: set, tuple, version and large-number tokens."""
    out, op = set(), r["op"]
    if not r["value"]:
        return out
    value = json.loads(r["value"])
    if r["vkind"] == "set":
        if op in ("In", "NotIn") and len(value) >= 2:
            out.add("set:" + hashlib.sha1(json.dumps(sorted(map(str, value))).encode()).hexdigest()[:10])
            out |= {f"ver:{v}" for x in value if isinstance(x, str) and (v := version_of(x))}
        elif op in (*ORDERED, "Eq", "NotEq"):
            if op in ORDERED or isinstance(_expr(r["const"]), ast.Tuple) or r["identity"]:
                out.add("tup:" + ",".join(map(str, value))[:40])
            if (v := version_of(value)):
                out.add(f"ver:{v}")
    elif r["vkind"] == "str" and op in (*ORDERED, "Eq", "NotEq", "In", "NotIn") and (v := version_of(value)):
        out.add(f"ver:{v}")
    elif r["vkind"] == "num" and isinstance(value, (int, float)) and abs(value) >= BIG:
        out.add(f"val:{ff.num(boundary(op, value))}")
    return out



def say(tok: str) -> str:
    kind, _, body = tok.partition(":")
    if kind == "id":
        return f"compares with {body}"
    if kind == "set":
        return "the same literal set"
    if kind == "tup":
        return f"compares with ({body})"
    if kind == "ver":
        return f"version {body}"
    if kind == "val":
        return f"constant {body}"
    if kind == "env":
        return f"reads env {body}"
    if kind == "subj":
        return f"tests the {body.replace('-', ' ')}"
    return ff.say(tok)
