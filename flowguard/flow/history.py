"""Persistent model-side scope/obligation comparisons, owned by conflicts.json.

This module does not explore, run native code or close conflicts. Its model_absent
or source-bound requirement_changed result still needs the regression/native owner.
"""
from __future__ import annotations

from copy import deepcopy
import ast
import base64
import hashlib
import json
import re
import zlib

from ..map.common import normalize_newlines

VERSION = 1


class HistoryError(ValueError):
    """Invalid history is unknown evidence, never an empty successful scope."""


def definition_digest(source: str) -> str:
    """An invalidation identity, not a Python implication/weakening oracle."""
    return hashlib.sha256(normalize_newlines(source.encode("utf-8"))).hexdigest()


def _require(ok, message):
    if not ok:
        raise HistoryError(message)


def _shared_entries(entries):
    """Keep an exact retained table once, without merging its separate histories."""
    packed, tables = [], {}
    for index, entry in enumerate(entries):
        baseline = entry.get('history', {}).get('baseline', {})
        obligations = baseline.get('obligations')
        if isinstance(obligations, list):
            encoded = json.dumps(obligations, sort_keys=True, separators=(',', ':'))
            key = hashlib.sha256(encoded.encode()).hexdigest()
            prior = tables.get(key)
            if prior is not None and prior[0] == encoded:
                entry = {**entry, 'history':{**entry['history'], 'baseline':{
                    **baseline, 'obligations':{'same_as':prior[1]}}}}
            else:
                tables[key] = (encoded, index)
        packed.append(entry)
    return packed


def _wire_size(value, indent, depth):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=indent)
    return len(text.encode('utf-8', 'surrogatepass')) + (text.count('\n') * depth * indent if indent else 0)


def _compact(value, kind, indent, depth):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
           if kind == 'cases' else value.encode('utf-8', 'surrogatepass'))
    marker = {'$flowguard_' + kind:'zlib-base64-v1',
              'data':base64.b64encode(zlib.compress(raw)).decode('ascii')}
    return marker if _wire_size(marker, indent, depth) < _wire_size(value, indent, depth) else value


def _expand(value, kind):
    tag = '$flowguard_' + kind
    if not isinstance(value, dict) or tag not in value:
        return value
    # A legacy finite relation has only boolean values, so its case names can
    # include the reserved name without being a compact payload.
    if kind == 'cases' and type(value[tag]) is bool:
        return value
    _require(set(value) == {tag, 'data'} and value[tag] == 'zlib-base64-v1' and
             isinstance(value['data'], str), 'invalid compact ' + kind + ' encoding')
    try:
        raw = zlib.decompress(base64.b64decode(value['data'], validate=True))
        result = json.loads(raw) if kind == 'cases' else raw.decode('utf-8', 'surrogatepass')
    except (ValueError, UnicodeError, zlib.error) as error:
        raise HistoryError('cannot read compact ' + kind + ' evidence: ' + str(error)) from error
    _require(isinstance(result, dict) if kind == 'cases' else isinstance(result, str),
             'compact ' + kind + ' evidence has the wrong type')
    return result


def _wire(value, encode, indent=None, depth=0):
    # Descend only through owned storage fields. Native arguments, outputs and
    # states can legally contain dictionaries that resemble our internal tags.
    def facts(record, level):
        if not isinstance(record, dict) or not isinstance(record.get('obligations'), list):
            return record
        rows = []
        for row in record['obligations']:
            if isinstance(row, dict) and isinstance(row.get('cases'), dict):
                cases = row['cases']
                if encode and '$flowguard_cases' not in cases:
                    cases = _compact(cases, 'cases', indent, level + 3)
                elif not encode:
                    cases = _expand(cases, 'cases')
                row = {**row, 'cases':cases}
            rows.append(row)
        return {**record, 'obligations':rows}

    def entries(rows, level):
        if not isinstance(rows, list):
            return rows
        out = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get('history'), dict):
                old = row['history']
                if 'baseline' in old:
                    row = {**row, 'history':{**old, 'baseline':facts(old['baseline'], level + 3)}}
            out.append(row)
        return out

    def planned(record, level):
        if not isinstance(record, dict) or not isinstance(record.get('options'), list):
            return record
        options = []
        for pair in record['options']:
            if isinstance(pair, list) and len(pair) == 2 and pair[0] == 'native_stored':
                payload = pair[1]
                if encode and isinstance(payload, str):
                    payload = _compact(payload, 'option', indent, level + 3)
                elif not encode:
                    payload = _expand(payload, 'option')
                pair = [pair[0], payload]
            options.append(pair)
        return {**record, 'options':options}

    if isinstance(value, list):
        return entries(value, depth)              # pack_entries' owned list
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for key in ('conflicts', 'closed'):
        if key in value:
            result[key] = entries(value[key], depth + 1)
    if isinstance(value.get('info'), dict) and 'descriptor' in value['info']:
        result['info'] = {**value['info'], 'descriptor':facts(value['info']['descriptor'], depth + 2)}
    if isinstance(value.get('parts'), list):
        result['parts'] = [planned(row, depth + 2) for row in value['parts']]
    if 'planned' in value:                        # actual-recipe manifest
        result['planned'] = planned(value['planned'], depth + 1)
    if isinstance(value.get('models'), dict):
        models = {}
        for model, row in value['models'].items():
            if isinstance(row, dict):
                row = dict(row)
                if 'observation' in row:
                    row['observation'] = facts(row['observation'], depth + 3)
                if isinstance(row.get('core'), dict) and 'planned' in row['core']:
                    row['core'] = {**row['core'], 'planned':planned(row['core']['planned'], depth + 4)}
            models[model] = row
        result['models'] = models
    return result


def pack_wire(value, *, indent=None):
    """Transparent compact finite facts at the existing JSON storage boundaries."""
    return _wire(value, True, indent)


def unpack_wire(value):
    return _wire(value, False)


def pack_entries(entries):
    """A self-contained option, including every original case and history anchor."""
    return json.dumps(pack_wire(_shared_entries(entries)), sort_keys=True)


def unpack_entries(value):
    """Resolve plan-local sharing; legacy complete JSON lists remain complete."""
    entries = unpack_wire(json.loads(value) if isinstance(value, str) else value)
    _require(isinstance(entries, list), 'retained entries must be a list')
    restored = []
    for index, entry in enumerate(entries):
        _require(isinstance(entry, dict), 'retained entry must be an object')
        baseline = entry.get('history', {}).get('baseline', {})
        obligations = baseline.get('obligations')
        if isinstance(obligations, dict):
            reference = obligations.get('same_as')
            _require(set(obligations) == {'same_as'} and type(reference) is int and
                     0 <= reference < index, 'invalid retained-table reference')
            table = restored[reference].get('history', {}).get('baseline', {}).get('obligations')
            _require(isinstance(table, list), 'retained-table reference has no actual table')
            entry = {**entry, 'history':{**entry['history'], 'baseline':{
                **baseline, 'obligations':table}}}
        restored.append(entry)
    return restored


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _texts(value):
    return isinstance(value, list) and all(_text(v) for v in value) and len(value) == len(set(value))


def _scope(value):
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"model", "members", "bounds", "starts", "coverage"},
             "scope needs model, members, bounds, starts and coverage")
    _require(_text(value["model"]) and _texts(value["members"]), "invalid scope model/members")
    _require(isinstance(value["bounds"], dict) and all(_text(k) and type(v) is int and v >= 0
             for k, v in value["bounds"].items()), "invalid scope object bounds")
    _require(_texts(value["starts"]) and bool(value["starts"]), "scope must name its initial/saved starts")
    _require(isinstance(value["coverage"], dict) and bool(value["coverage"]) and
             all(_text(k) and _texts(v) and bool(v) for k, v in value["coverage"].items()),
             "scope must name its covered values/actions/anchors")


def _obligations(value):
    if value is None:
        return
    _require(isinstance(value, list), "obligations must be a list or unknown")
    ids = set()
    for row in value:
        _require(isinstance(row, dict) and {"id", "kind", "sources", "definition", "cases"} <= set(row) <= {"id", "kind", "sources", "definition", "cases", "dependencies", "terms"},
                 "obligation needs id, kind, sources, definition and cases")
        _require(_text(row["id"]) and row["id"] not in ids and _text(row["kind"]) and _texts(row["sources"]),
                 "invalid/duplicate obligation identity or sources")
        ids.add(row["id"])
        _require("terms" not in row or _texts(row["terms"]), "invalid obligation subject terms")
        _require(row["definition"] is None or isinstance(row["definition"], str) and
                 re.fullmatch(r"[0-9a-f]{64}", row["definition"]), "invalid obligation definition identity")
        dependencies = row.get("dependencies")
        _require(dependencies is None or isinstance(dependencies, dict) and bool(dependencies) and
                 all(_text(k) and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                     for k, v in dependencies.items()), "invalid semantic dependency identity")
        cases = row["cases"]
        _require(cases is None or isinstance(cases, dict) and bool(cases) and
                 all(_text(k) and type(v) is bool for k, v in cases.items()),
                 "obligation cases must be a finite boolean relation or unknown")


def _snapshot(value):
    _require(isinstance(value, dict) and set(value) == {"receipt", "scope", "obligations"}, "invalid baseline")
    _require(value["receipt"] is None or _text(value["receipt"]), "invalid baseline receipt")
    _scope(value["scope"])
    _obligations(value["obligations"])


def observation(value):
    """Validate an explicit model computation receipt; missing data is not complete.

    The future CLI must derive these flags from ModelView.explored, not a replay
    part's complete bit. cases, when present, must come from finite evaluation
    over the declared scope, with stable case identities, not a caller's verdict.
    """
    keys = {"receipt", "finished", "loaded", "complete", "errors", "scope", "obligations", "replay"}
    _require(isinstance(value, dict) and keys <= set(value) <= keys | {"note", "conflicts"}, "invalid model observation fields")
    _require("conflicts" not in value or isinstance(value["conflicts"], list) and all(
        isinstance(row, dict) and set(row) == {"id", "kind", "subject"} and all(_text(v) for v in row.values())
        for row in value["conflicts"]), "invalid current conflict observations")
    _require(isinstance(value.get("note", ""), str), "invalid observation explanation")
    _require(_text(value["receipt"]), "observation must reference its computation receipt")
    _require(all(type(value[k]) is bool for k in ("finished", "loaded", "complete")), "invalid computation flags")
    _require(type(value["errors"]) is int and value["errors"] >= 0, "invalid model error count")
    _require(value["replay"] in ("reproduced", "gone", "unknown", "not_run"), "invalid replay outcome")
    _scope(value["scope"])
    _obligations(value["obligations"])
    return deepcopy(value)


def _comparison(value):
    keys = {"outcome", "receipt", "reasons", "changes", "claim", "native", "regression", "note"}
    _require(isinstance(value, dict) and keys <= set(value) <= keys | {"resolution"}, "invalid comparison fields")
    _require(value["outcome"] in ("retain", "model_absent", "requirement_changed") and _text(value["receipt"]), "invalid comparison outcome")
    _require((value["outcome"] == "requirement_changed") == ("resolution" in value), "missing requirement-change evidence")
    _require(value["claim"] == "model_only" and value["native"] == "not_evaluated" and
             value["regression"] == "not_recorded", "model history cannot claim native/code-fixed proof")
    _require(isinstance(value["note"], str), "invalid comparison explanation")
    for key in ("reasons", "changes"):
        _require(isinstance(value[key], list) and all(isinstance(row, dict) and set(row) == {"code", "subject"}
                 and _text(row["code"]) and isinstance(row["subject"], str) for row in value[key]),
                 f"invalid comparison {key}")
    _require(bool(value["reasons"]) == (value["outcome"] == "retain"), "comparison outcome disagrees with reasons")


def validate(value):
    """Validate optional history on an existing conflict entry (legacy has none)."""
    _require(isinstance(value, dict) and set(value) == {"version", "baseline", "latest", "native_refs", "decision_refs"},
             "invalid history fields")
    _require(type(value["version"]) is int and value["version"] == VERSION, "unsupported history version")
    _snapshot(value["baseline"])
    if value["latest"] is not None:
        _comparison(value["latest"])
    _require(_texts(value["native_refs"]) and _texts(value["decision_refs"]), "invalid native/decision references")


def shape_problem(value):
    try:
        validate(value)
    except HistoryError as error:
        return str(error)
    return None


def bind(entry, current=None, previous=None):
    """Attach the first baseline, preserving it across same-ID rediscovery.

    Later native and immutable-decision owners may append receipt references;
    references alone do not confirm a code fix or authorize any decision here.
    """
    out = deepcopy(entry)
    if previous is not None:
        _require(previous["id"] == entry["id"], "cannot transfer history to another conflict identity")
        _require(all(previous[key] == entry[key] for key in ("kind", "model", "subject")) and
                 set(previous["sources"]) == set(entry["sources"]), "conflict identity fields changed")
    owner = previous if previous is not None else entry
    if "history" in owner:
        validate(owner["history"])
        scope = owner["history"]["baseline"]["scope"]
        _require(scope is None or scope["model"] == entry["model"], "baseline model mismatch")
        out["history"] = deepcopy(owner["history"])
    elif current is not None and previous is None:
        current = observation(current)
        _require(current["scope"] is None or current["scope"]["model"] == entry["model"], "baseline model mismatch")
        out["history"] = dict(version=VERSION, baseline={k: current[k] for k in ("receipt", "scope", "obligations")},
                              latest=None, native_refs=[], decision_refs=[])
    elif previous is not None:
        # Never manufacture the missing historical scope from today's smaller model.
        out["history"] = dict(version=VERSION, baseline=dict(receipt=None, scope=None, obligations=None),
                              latest=None, native_refs=[], decision_refs=[])
    return out


def _start_preserved(start, candidates):
    """Only a symbolic initial state may gain fields without removing its old projection."""
    if start in candidates:
        return True
    def fields(text):
        if not text.startswith("initial:"):
            return None
        try:
            value = ast.literal_eval(text[len("initial:"):])
        except (ValueError, SyntaxError):
            return None
        if not isinstance(value, tuple) or not all(isinstance(row, tuple) and len(row) == 2 for row in value):
            return None
        pairs = {repr(key): repr(item) for key, item in value}
        return pairs if len(pairs) == len(value) else None
    before = fields(start)
    return before is not None and any(after is not None and before.items() <= after.items()
                                     for after in (fields(candidate) for candidate in candidates))


def assess(entry, current, *, root=None):
    """Compare absence from a final model computation; do not close or run anything."""
    current = observation(current)
    reasons, changes = [], []

    def add(rows, code, subject=""):
        item = dict(code=code, subject=subject)
        if item not in rows:
            rows.append(item)

    result = dict(outcome="retain", receipt=current["receipt"], reasons=reasons, changes=changes,
                  claim="model_only", native="not_evaluated", regression="not_recorded", note=current.get("note", ""))
    old = entry.get("history")
    if old is None:
        add(reasons, "historical_scope_unknown")
        return result
    validate(old)
    baseline = old["baseline"]
    if not current["finished"] or not current["loaded"] or not current["complete"] or current["errors"]:
        add(reasons, "model_exploration_incomplete")
    if current["replay"] == "reproduced":
        add(reasons, "condition_reproduced")
    before, after = baseline["scope"], current["scope"]
    if before is None or after is None:
        add(reasons, "scope_unknown")
    else:
        for key in ("model", "members", "bounds"):
            a, b = before[key], after[key]
            if (set(a) if key == "members" else a) != (set(b) if key == "members" else b):
                add(reasons, "scope_changed", key)
        if after["model"] != entry["model"]:
            add(reasons, "scope_changed", "conflict model")
        for start in sorted(before["starts"]):
            if not _start_preserved(start, after["starts"]):
                add(reasons, "start_removed", start)
        for key, values in sorted(before["coverage"].items()):
            for value in sorted(set(values) - set(after["coverage"].get(key, []))):
                add(reasons, "coverage_removed", f"{key}: {value}")
    previous_obligations, current_obligations = baseline["obligations"], current["obligations"]
    if previous_obligations is None or current_obligations is None:
        add(reasons, "obligations_unknown")
    else:
        protected_sources = {source for row in previous_obligations for source in row["sources"]}
        if not set(entry["sources"]) <= protected_sources:
            add(reasons, "source_obligations_unknown")
        now = {row["id"]: row for row in current_obligations}
        for row in previous_obligations:
            if not row["sources"]:
                continue
            other = now.get(row["id"])
            if other is None:
                add(reasons, "sourced_obligation_removed", row["id"])
                continue
            if row["kind"] != other["kind"] or not set(row["sources"]) <= set(other["sources"]):
                add(reasons, "sourced_obligation_changed", row["id"])
            changed = row["definition"] != other["definition"]
            if changed:
                add(changes, "definition_changed", row["id"])
            a, b = row["cases"], other["cases"]
            dependencies = row.get("dependencies")
            semantic_identity = (dependencies is not None and dependencies == other.get("dependencies")
                                 and not changed and row["definition"] is not None)
            if not semantic_identity or a is not None or b is not None:
                if a is None or b is None or not set(a) <= set(b):
                    add(reasons, "obligation_relation_unknown", row["id"])
                elif any(not allowed and b[case] for case, allowed in a.items()):
                    add(reasons, "sourced_obligation_weakened", row["id"])
    if not reasons:
        result["outcome"] = "model_absent"
    elif root is not None:
        from .resolution import derive
        resolution = derive(root, entry, current, reasons)
        if resolution is not None:
            result.update(outcome="requirement_changed", resolution=resolution, reasons=[])
    reasons.sort(key=lambda r: (r["code"], r["subject"]))
    changes.sort(key=lambda r: (r["code"], r["subject"]))
    return result


def compared(entry, current, *, root=None):
    """Persist a comparison on an open entry; candidate closure remains open here."""
    out = bind(entry, previous=entry)
    out["history"]["latest"] = assess(out, current, root=root)
    return out


def resolution_current(root, entry, resolution):
    """Revalidate stored owner authority without exploring or executing a model."""
    from .resolution import revalidate
    return revalidate(root, entry, resolution)
