"""Detached public observations and exact public-prefix references, never norms."""

from __future__ import annotations

import hashlib
import json


def _key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _copy(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


class Ledger:
    """Intern executed facts; these keys never merge native execution states."""

    def __init__(self, spec):
        self.spec = spec
        self.prefixes, self.observations, self.steps, self.states = {}, {}, {}, {}
        self.depths, self.missing = {}, []

    def origin(self, start, prefix=(), outcomes=()):
        if len(prefix) != len(outcomes):
            raise ValueError("public prefix and outcome lengths differ")
        row = {"start": start}
        ref = _key(row)
        if ref not in self.prefixes:
            self.prefixes[ref] = _copy(row)
            self.depths[ref] = 0
        for call, outcome in zip(prefix, outcomes):
            ref = self.advance(ref, call, outcome)
        return ref

    def advance(self, parent, call, outcome):
        row = {"parent": parent, "call": call, "outcome": outcome}
        ref = _key(row)
        if ref not in self.prefixes:
            self.prefixes[ref] = _copy(row)
            self.depths[ref] = self.depths[parent] + 1
        return ref

    def view(self, state_key, observation, prefix_ref):
        row = {"state_key": state_key, "observation": observation}
        ref = _key(row)
        if ref not in self.observations:
            self.observations[ref] = _copy(row)
        origins = self.states.setdefault(ref, set())
        if not origins or self._depth(prefix_ref) < self._depth(next(iter(origins))):
            origins.clear()
            origins.add(prefix_ref)
        return ref

    def state(self, start, prefix, outcomes, state_key, observation):
        return self.view(state_key, observation, self.origin(start, prefix, outcomes))

    def record(self, prefix_ref, row, before_ref, after_ref):
        if row["outcome"] != "success":
            return
        item = {"prefix_ref": prefix_ref, "before_ref": before_ref, "after_ref": after_ref,
                **({"args_graph": row["resolved_args_graph"]} if row.get("resolved_args_graph") is not None
                   else {"args": row.get("resolved_args")})}
        self.steps.setdefault(_key(item), _copy(item))

    def step(self, start, prefix, outcomes, row, before, after):
        ref = self.origin(start, prefix, outcomes)
        parent = self.prefixes[ref]["parent"]
        before_ref = self.view(row["before_key"], before, parent)
        after_ref = self.view(row["after_key"], after, ref)
        self.record(ref, row, before_ref, after_ref)

    def update(self, captured):
        if captured.get("wire") != 2:
            self.missing.append("native producer returned an unsupported capture wire")
            return
        self.prefixes.update(captured["prefixes"])
        self.observations.update(captured["observations"])
        self.steps.update(captured["steps"])
        for view, origin in captured["states"].items():
            origins = self.states.setdefault(view, set())
            if not origins or self._depth(origin) < self._depth(next(iter(origins))):
                origins.clear()
                origins.add(origin)
        self.missing.extend(captured.get("missing", ()))
        if not captured.get("complete", False):
            self.missing.append("a native capture producer did not finish its declared scope")

    def _depth(self, ref):
        pending = []
        while ref not in self.depths:
            pending.append(ref)
            row = self.prefixes[ref]
            if "start" in row:
                self.depths[ref] = 0
                break
            ref = row["parent"]
        for item in reversed(pending):
            row = self.prefixes[item]
            self.depths[item] = 0 if "start" in row else self.depths[row["parent"]] + 1
        return self.depths[ref] if not pending else self.depths[pending[0]]

    def dump(self, *, complete=True, missing=(), accepted=None):
        allowed = None
        if accepted is not None:
            allowed = set()
            for ref in accepted:
                while ref not in allowed:
                    allowed.add(ref)
                    row = self.prefixes[ref]
                    if "start" in row:
                        break
                    ref = row["parent"]
        states = {}
        for view, refs in self.states.items():
            choices = refs if allowed is None else refs & allowed
            if choices:
                states[view] = min(choices, key=lambda ref: (self._depth(ref), ref))
        steps = {key: row for key, row in self.steps.items() if allowed is None or row["prefix_ref"] in allowed}
        used = set(states)
        needed = set(states.values())
        for row in steps.values():
            used.update((row["before_ref"], row["after_ref"]))
            needed.add(row["prefix_ref"])
        prefix_refs = set()
        for ref in needed:
            while ref not in prefix_refs:
                prefix_refs.add(ref)
                row = self.prefixes[ref]
                if "start" in row:
                    break
                ref = row["parent"]
        problems = sorted(set([*self.missing, *missing]))
        return {"wire": 2, "spec": self.spec,
                "prefixes": {key: self.prefixes[key] for key in prefix_refs},
                "observations": {key: self.observations[key] for key in used},
                "states": states, "steps": steps, "complete": bool(complete and not problems), "missing": problems}


def merge(spec, ledgers, *, complete=True, missing=()):
    ledger = Ledger(spec)
    for captured in ledgers:
        ledger.update(captured)
    return ledger.dump(complete=complete, missing=missing)


def failure_context(row):
    context = row.get("_capture_context")
    if context is None:
        return {key: row[key] for key in ("start", "prefix", "outcomes") if key in row}
    captured, ref = context
    calls, outcomes = [], []
    while "start" not in captured["prefixes"][ref]:
        item = captured["prefixes"][ref]
        calls.append(item["call"])
        outcomes.append(item["outcome"])
        ref = item["parent"]
    return {"start": captured["prefixes"][ref]["start"],
            "prefix": list(reversed(calls)), "outcomes": list(reversed(outcomes))}


def iter_states(captured):
    if captured.get("wire") != 2:
        yield from captured.get("states", ())
        return
    for view, origin in captured["states"].items():
        yield {**captured["observations"][view], "_capture_context": (captured, origin)}


def iter_steps(captured):
    if captured.get("wire") != 2:
        yield from captured.get("steps", ())
        return
    for row in captured["steps"].values():
        prefix = captured["prefixes"][row["prefix_ref"]]
        before, after = (captured["observations"][row[name]] for name in ("before_ref", "after_ref"))
        yield {"call": prefix["call"], "outcome": prefix["outcome"],
               **({"args_graph": row["args_graph"]} if "args_graph" in row else {"args": row["args"]}),
               "before_key": before["state_key"], "after_key": after["state_key"],
               "before": before["observation"], "after": after["observation"],
               "_capture_context": (captured, row["prefix_ref"])}
