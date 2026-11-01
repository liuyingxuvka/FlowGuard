"""Pictures of a flow model (FG-814 `show`): views over the explored states, the automatic
choice of layer and density (proto12-modelcheck 4.4), before/after colouring, Mermaid text,
the picture file (Mermaid in headless Chromium), the `picture` part and the body of `show`.

A picture is drawn from the same exploration and the same findings as the check, so it
cannot drift from what the check says. It explains; the check is the verdict.

Boxes are the values of the chosen fields over the drawn states; arrows are the steps
between different boxes, one arrow per pair of boxes labelled with the action names
(arguments folded). With interchangeable objects (m.objects) every renaming of an explored
state is drawn as a state of its own, so the view of T1 is the picture of any tool.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .checks import CONFLICT, Finding, Report, check_model
from .explore import Bounds, explore, show_step
from .model import ModelError, load_model, show_key
from .parts import PartContext, PartResult, PartSpec, kinds, part_digest, register, run_part
from .project import (PROG, ProjectError, cache_dir, changed_models, export_at, model_files, new_and_open,
                      read_conflicts, write_manifest)
from .routes import route_checks

MAX_BOXES = 12                 # a target the tool groups toward (proto12-modelcheck 4.3), never a pass mark
MAX_ARROWS = 20
MAX_PICTURES = 3               # pictures one default `show` draws; the rest are listed
ROUTE_KINDS = ("DUPLICATE ROUTE", "SUBSUMED ACTION", "FALLBACK ROUTE")   # Part A; detail["actions"]
RED, GREEN, GREY = "#c00", "#080", "#999"
_PKG = Path(__file__).resolve().parent
RENDER_JS = _PKG / "render.js"
MERMAID_JS = _PKG / "vendor" / "mermaid.min.js"        # Mermaid 10.9.1 (MIT), as the prototype used
PICTURES = "pictures"                                  # under .flowguard/cache/flow/


# ---------------------------------------------------------------------- keys
def family(key):
    return key[0] if isinstance(key, tuple) else key


def obj_of(key):
    """The object a key belongs to ("T1" for ("cond", "T1")), or None for a plain field."""
    if not isinstance(key, tuple):
        return None
    return key[1] if len(key) == 2 else tuple(key[1:])


def _show(value) -> str:
    return str(value)


def _esc(text: str) -> str:
    """Text inside a quoted Mermaid label (entity codes for the characters Mermaid reads)."""
    return (text.replace("#", "#35;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;"))


def _plural(n, word):
    if n == 1:
        return f"1 {word}"
    return f"{n:,} {word}{'es' if word.endswith(('x', 's')) else 's'}"


def _is_counter(domain) -> bool:
    return any(isinstance(v, int) and not isinstance(v, bool) for v in domain)


def _is_text(domain) -> bool:
    vals = [v for v in domain if v is not None]
    return len(vals) >= 2 and all(isinstance(v, str) for v in vals)


# ---------------------------------------------------------------------- concrete states
class Space:
    """The concrete states of an explored graph and the steps between them."""

    def __init__(self, graph):
        g = self.graph = graph
        self.keys = g.keys
        self.pos = {k: p for p, k in enumerate(g.keys)}
        self.domains = {f.key: f.domain for f in g.model.fields}
        self.inits = {f.key: f.init for f in g.model.fields}
        sym = g.sym
        if sym is None:
            self.states = g.states
            self.rep = None
            self.index = None
        else:
            self.states, self.rep, self.index = [], [], {}
            for i, s in enumerate(g.states):
                for p in range(sym.n):
                    t = sym.apply(p, s)
                    if t not in self.index:
                        self.index[t] = len(self.states)
                        self.states.append(t)
                        self.rep.append((i, p))
        self.names = [c.action.name for c in g.calls]
        self.call_of = {show_step(c.step()): c.index for c in g.calls}
        self._succ = None
        self._pred = None
        self._parent = None

    def __len__(self):
        return len(self.states)

    def succ(self) -> list:
        """succ[u]: {v: concrete call indices} for every step from u to another state v."""
        if self._succ is None:
            g, sym = self.graph, self.graph.sym
            out = []
            for u in range(len(self.states)):
                i, p = (u, 0) if sym is None else self.rep[u]
                nxt = {}
                for c, j in enumerate(g.out[i]):
                    if j < 0:
                        continue
                    if sym is None:
                        v, cc = j, c
                    else:
                        v, cc = self.index[sym.apply(p, g.raw_successor(i, c))], sym.call_perm[p][c]
                    if v != u:
                        nxt.setdefault(v, set()).add(cc)
                out.append(nxt)
            self._succ = out
        return self._succ

    def pred(self) -> list:
        if self._pred is None:
            pred = [[] for _ in self.states]
            for u, nxt in enumerate(self.succ()):
                for v in nxt:
                    pred[v].append(u)
            self._pred = pred
        return self._pred

    def step(self, u, c):
        """The concrete state after concrete call c from u, or None (refused, error, bound)."""
        g, sym = self.graph, self.graph.sym
        if sym is None:
            j = g.out[u][c]
            return j if j >= 0 else None
        i, p = self.rep[u]
        rc = sym.call_perm[sym.inv[p]][c]
        if g.out[i][rc] < 0:
            return None
        return self.index[sym.apply(p, g.raw_successor(i, rc))]

    def replay(self, steps) -> tuple[list, list]:
        """The concrete states and action names of a shown path from the start."""
        u, seq, names = 0, [0], []
        for text in steps:
            c = self.call_of[text]
            v = self.step(u, c)
            if v is None:
                break
            seq.append(v)
            names.append(self.names[c])
            u = v
        return seq, names

    def concrete(self, ids) -> set:
        """Unreduced state ids of a finding (i * renamings + renaming) as concrete states."""
        sym = self.graph.sym
        if sym is None:
            return set(ids)
        n = sym.n
        return {self.index[sym.apply(x % n, self.graph.states[x // n])] for x in ids}

    def path_to(self, target) -> list:
        """Action names of a shortest run from the start to target."""
        if self._parent is None:
            parent = {0: None}
            queue = deque([0])
            succ = self.succ()
            while queue:
                u = queue.popleft()
                for v, ccs in succ[u].items():
                    if v not in parent:
                        parent[v] = (u, self.names[min(ccs)])
                        queue.append(v)
            self._parent = parent
        out = []
        u = target
        while self._parent.get(u) is not None:
            u, name = self._parent[u]
            out.append(name)
        return out[::-1]

    def around(self, seeds, k) -> set:
        """States within k steps of the seeds, following steps either way."""
        succ, pred = self.succ(), self.pred()
        seen = {s: 0 for s in seeds}
        queue = deque(seeds)
        while queue:
            u = queue.popleft()
            if seen[u] >= k:
                continue
            for v in list(succ[u]) + pred[u]:
                if v not in seen:
                    seen[v] = seen[u] + 1
                    queue.append(v)
        return set(seen)

    def projector(self, keys, fill=None):
        """u -> the values of keys in state u; a key this model lacks takes fill[key]."""
        pos = [self.pos.get(k) for k in keys]
        fill = fill or {}
        consts = [fill.get(k) for k in keys]
        states = self.states
        if all(p is not None for p in pos):
            if len(pos) == 1:
                q = pos[0]
                return lambda u: (states[u][q],)
            return lambda u: tuple(states[u][q] for q in pos)
        return lambda u: tuple(states[u][q] if q is not None else c for q, c in zip(pos, consts))


# ---------------------------------------------------------------------- views
@dataclass(frozen=True)
class View:
    name: str                    # what it shows (first line, list of views)
    keys: tuple                  # the fields drawn in each box
    kind: str = "space"          # space | focus | story | new | group
    focus: int | None = None
    thin: bool = False           # a status view: used only with 4 boxes or more when a later view fits
    options: tuple = ()          # the show options that ask for exactly this view


@dataclass
class Box:
    id: str
    lines: list
    mark: str = ""
    style: str = ""              # "" | stuck | added | removed | dashed | refusal
    states: int = 0


@dataclass
class Arrow:
    a: str
    b: str
    label: str
    style: str = ""              # "" | red | green | grey | dashed
    dotted: bool = False


@dataclass
class Drawing:
    """One drawn view: what the first line says, the boxes and arrows, the caption."""
    model: str
    view: View
    boxes: list
    arrows: list
    start: tuple | None          # (box id, None, False) or (box id, way-in label, on the counterexample)
    caption: list
    shown: int                   # concrete states drawn
    total: int                   # concrete states explored
    folded: list
    subject: str                 # what the picture is about (first line)
    states_text: str             # "6 states" for the comment line

    @property
    def n_boxes(self):
        return len(self.boxes)

    @property
    def n_arrows(self):
        return len(self.arrows)

    def fits(self, max_boxes, max_arrows):
        return self.n_boxes <= max_boxes and self.n_arrows <= max_arrows


@dataclass
class Request:
    """The view options of a `show` call (all None: automatic)."""
    fields: tuple | None = None
    object: str | None = None
    focus: int | None = None
    story: bool = False
    group: str | None = None
    max_boxes: int = MAX_BOXES
    max_arrows: int = MAX_ARROWS

    def explicit(self):
        return bool(self.fields or self.object is not None or self.focus is not None or self.story or self.group)


@dataclass
class Change:
    """The before model of a change, explored and compared with the new one."""
    rev: str
    space: Space | None          # None: the model did not exist at rev
    keys: tuple = ()             # the fields the added or removed steps change (new model's keys)
    new_states: list = field(default_factory=list)
    added: int = 0
    removed: int = 0
    note: str = ""


# ---------------------------------------------------------------------- the scene
class Scene:
    """Everything a picture of one model can show: the concrete states, the subject (a
    finding or a change) and its counterexample, marks and extra parts."""

    def __init__(self, report: Report, subject: Finding | None = None, change: Change | None = None,
                 obj=None, bounds: Bounds | None = None):
        self.report = report
        self.model = report.loaded.model
        self.mid = self.model.id or self.model.name
        self.space = Space(report.graph)
        self.subject = subject
        self.change = change
        self.obj = obj
        self.bounds = bounds or Bounds(report.graph.max_states or Bounds().max_states)
        self.story, self.story_names = [], []
        self.marked, self.mark = set(), ""
        self.mark_key, self.mark_objs = None, ()
        self.targets, self.target_text = [], None
        self.red_actions = set()
        self.variant = None          # (setting text, Space)
        self.missing = None          # (key, value): a value no setting reaches, drawn dashed
        self.refusal = None          # (state, node text, arrow label)
        self.missing_key = None      # the field of an unreached value
        self.missing_item = None     # an unreached action, option or reach rule with no explanation
        self.head = ""
        self.extra_caption = []
        if change is not None and change.space is None:
            self.extra_caption.append(f"new model: no before picture ({change.note})")
            self.change = None
        if subject is not None:
            self._subject(subject)
        elif self.change is not None:
            self._change(self.change)
        elif change is not None:
            self.head = f"new model: no before picture ({change.note})"
            self.extra_caption = []

    # -------------------------------------------------------------- subjects
    def _key_named(self, text):
        return next((k for k in self.space.keys if show_key(k) == text), None)

    def _subject(self, f: Finding):
        sp = self.space
        d = f.detail
        if f.path or f.kind in ("STUCK", "BROKEN", "CONTRADICTION"):
            self.story, self.story_names = sp.replay(f.path)
        n = len(self.story_names)
        steps = f"its {n}-step path" if n != 1 else "its 1-step path"
        if f.kind == "STUCK":
            where = d.get("where", d.get("states", []))
            self.marked = sp.concrete(where)
            self.mark = " (STUCK)"
            if d.get("stuck") == "progress":
                self.mark_objs = tuple(f.objects)
            else:
                self.mark_key = self._key_named(d.get("key", ""))
            self.targets = [self.story[-1]]
            self.target_text = "the dead end"
            self.head = f"STUCK {f.subject} at {f.state} with {steps} [{f.id}]"
        elif f.kind == "BROKEN":
            end = self.story[-1]
            self.targets = sorted(set(self.story[-2:])) if d.get("rule") != "always" else [end]
            self.target_text = "where the rule breaks"
            if d.get("rule") == "always":
                self.marked, self.mark = {end}, " (rule broken)"
            self.extra_caption.append("red: the steps that break it")
            self.head = f"BROKEN {f.subject} with {steps} [{f.id}]"
        elif f.kind == "CONTRADICTION":
            end = self.story[-1]
            self.marked, self.mark = {end}, " (offered, refused)"
            self.targets = [end]
            self.target_text = "the offering state"
            self.refusal = (end, f"{d.get('call', '')} refused", f"offered, refused: {d.get('reason', '')}")
            self.head = f"CONTRADICTION {f.subject}: {d.get('call', '')} refuses {d.get('reason', '')!r} [{f.id}]"
        elif f.kind == "NEVER REACHED":
            self._never(f)
        elif f.kind in ROUTE_KINDS:
            self.red_actions = set(d.get("actions", ()))
            self.extra_caption.append("red: the arrows of the routes " + ", ".join(sorted(self.red_actions)))
            self.head = f"{f.kind} {f.subject} [{f.id}]"
        else:
            self.head = f"{f.kind} {f.subject} [{f.id}]"

    def _never(self, f: Finding):
        d = f.detail
        how = d.get("explained") or []
        key = self._key_named(d.get("key", "")) if d.get("item") == "value" else None
        self.missing_key = key
        if how:
            text = how[0]
            space = self._variant_space(text)
            if space is not None:
                self.variant = (text, space)
                self.extra_caption.append(f"dashed red: what the model also does only with {text}")
                self.head = f"NEVER REACHED {f.subject}: reached only with {', '.join(how)} [{f.id}]"
                return
        if key is not None:
            self.missing = (key, _value_from_repr(self.space.domains[key], d.get("value")))
        else:                                         # an action, option or reach rule: named, dashed
            self.missing_item = f"{f.subject}: never happens"
        if how:
            self.extra_caption.append(f"the variant {how[0]} could not be rebuilt")
        self.head = f"NEVER REACHED {f.subject}: no one-setting change reaches it [{f.id}]"

    def _variant_space(self, text):
        """Explore the model once more with one setting changed in place (the live dict, as
        the one-setting explanation does; domains keep the shipped values)."""
        model = self.model
        name, _, raw = text.partition("=")
        if name not in model.settings:
            return None
        cur = model.settings[name]
        info = model.setting_info.get(name)
        if isinstance(cur, bool):
            value = raw == "True"
        elif isinstance(cur, int):
            try:
                value = int(raw)
            except ValueError:
                return None
        else:
            value = next((v for v in ((info.vary or ()) if info else ()) if str(v) == raw), None)
            if value is None:
                return None
        model.settings[name] = value
        try:
            g = explore(model, self.bounds, check_domains=False)
        finally:
            model.settings[name] = cur
        if not g.complete:
            self.extra_caption.append(f"the variant {text} is capped at {self.bounds.max_states:,} states")
        return Space(g)

    def _change(self, ch: Change):
        new_keys = self.space.keys
        old_keys = ch.space.keys
        union = tuple(new_keys) + tuple(k for k in old_keys if k not in self.space.pos)
        fill_new = {k: ch.space.inits[k] for k in old_keys if k not in self.space.pos}
        fill_old = {k: self.space.inits[k] for k in new_keys if k not in ch.space.pos}
        tn, _ = _transitions(self.space, union, fill_new)
        to, so = _transitions(ch.space, union, fill_old)
        added, removed = tn - to, to - tn
        changed = set()
        for a, b, _ in added | removed:
            for k, x, y in zip(union, a, b):
                if x != y:
                    changed.add(k)
        ch.keys = tuple(k for k in new_keys if k in changed)
        proj = self.space.projector(union, fill_new)
        ch.new_states = [u for u in range(len(self.space)) if proj(u) not in so]
        ch.added, ch.removed = len(added), len(removed)
        self.targets = ch.new_states
        self.target_text = "what is new"
        if not added and not removed:
            self.head = f"the change against {ch.rev}: no step is added or removed"
        else:
            self.head = (f"the change against {ch.rev}: {_plural(len(added), 'step')} added (green), "
                         f"{_plural(len(removed), 'step')} removed (grey)")

    # -------------------------------------------------------------- candidate views
    def status(self):
        """The status field (the text field changed by the most actions) and its object."""
        sp = self.space
        cands = [k for k in sp.keys if _is_text(sp.domains[k])]
        if self.obj is not None:
            cands = [k for k in cands if obj_of(k) == self.obj]
        by = {}
        succ = sp.succ()
        cpos = [(sp.pos[k], family(k)) for k in cands]
        for u, nxt in enumerate(succ):
            su = sp.states[u]
            for v, ccs in nxt.items():
                sv = sp.states[v]
                for p, fam in cpos:
                    if su[p] != sv[p]:
                        by.setdefault(fam, set()).update(sp.names[c] for c in ccs)
        if not by:
            return None, None
        order = [family(k) for k in sp.keys]
        fam = max(by, key=lambda f: (len(by[f]), -order.index(f)))
        key = next(k for k in cands if family(k) == fam)
        return fam, obj_of(key)

    def keys_of(self, fam=None, obj=None, everything=False):
        out = []
        for k in self.space.keys:
            if fam is not None and family(k) != fam:
                continue
            if not everything and obj_of(k) != obj:
                continue
            out.append(k)
        return tuple(out)

    def candidates(self) -> list:
        out = []
        sp = self.space
        if self.subject is not None and self.story and len(self.story) > 1:
            keys = tuple(k for k in sp.keys if len({sp.states[u][sp.pos[k]] for u in self.story}) > 1)
            if self.obj is not None:
                keys = tuple(k for k in keys if obj_of(k) == self.obj)
            if keys:
                names = ", ".join(show_key(k) for k in keys)
                fo = ("--fields", ",".join(show_key(k) for k in keys))
                out.append(View(f"the fields the counterexample changes ({names}), whole space", keys, options=fo))
                for k in (3, 2, 1):
                    out.append(View(f"{_plural(k, 'step')} around {self.target_text}, fields {names}", keys, "focus", k,
                                    options=("--focus", str(k)) + fo))
                out.append(View(f"the counterexample alone, fields {names}", keys, "story",
                                options=("--story",) + fo))
        if self.subject is not None and self.subject.kind == "NEVER REACHED":
            key = self.missing_key
            fam, _ = self.status()
            if key is not None and fam is not None and family(key) != fam:
                keys = self.keys_of(fam, obj_of(key)) + (key,)
                out.append(View(f"{fam} of {obj_of(key)} + {show_key(key)}" if obj_of(key) is not None
                                else f"{fam} + {show_key(key)}", keys,
                                options=("--fields", ",".join(show_key(k) for k in keys))))
        if self.change is not None and self.change.keys:
            keys = self.change.keys
            names = ", ".join(show_key(k) for k in keys)
            fo = ("--fields", ",".join(show_key(k) for k in keys))
            out.append(View(f"the fields the change's steps change ({names}), whole space", keys, options=fo))
            if self.change.new_states:
                for k in (3, 2, 1):
                    out.append(View(f"{_plural(k, 'step')} around what is new, fields {names}", keys, "focus", k,
                                    options=("--focus", str(k)) + fo))
                out.append(View(f"the new part alone, fields {names}", keys, "new"))
        out += self.status_views()
        return out

    def status_views(self) -> list:
        out = []
        fam, obj = self.status()
        sp = self.space
        if fam is not None:
            status = f"{fam} of {obj}" if obj is not None else fam
            base = ("--object", str(obj)) if obj is not None else ()
            keys = self.keys_of(fam, obj)
            out.append(View(status, keys, thin=True, options=base + ("--fields", fam)))
            seen = []
            for k in sp.keys:
                f2 = family(k)
                if f2 == fam or f2 in seen or obj_of(k) != obj or _is_counter(sp.domains[k]):
                    continue
                seen.append(f2)
                out.append(View(f"{status} + {f2}", self.keys_of(fam, obj) + self.keys_of(f2, obj),
                                options=base + ("--fields", f"{fam},{f2}")))
            if obj is not None:
                out.append(View(f"the life cycle of {obj} (all its fields)", self.keys_of(obj=obj),
                                options=("--object", str(obj))))
                group = self.keys_of(fam, everything=True)
                if len(group) > 1:
                    out.append(View(f"{fam} of every object, grouped", group, "group", options=("--group", fam)))
        out.append(View("the whole state space", tuple(sp.keys), options=("--fields", "*")))
        return out

    def field_views(self) -> list:
        """One field family alone (of one object when it has objects): listed when nothing
        fits, never chosen automatically."""
        out, seen = [], set()
        for k in self.space.keys:
            fam, obj = family(k), obj_of(k)
            if fam in seen:
                continue
            seen.add(fam)
            keys = self.keys_of(fam, obj)
            base = ("--object", str(obj)) if obj is not None else ()
            out.append(View(f"{fam} of {obj}" if obj is not None else f"{fam} alone", keys,
                            options=base + ("--fields", fam)))
        return out

    def explicit(self, req: Request) -> View:
        sp = self.space
        if req.group:
            keys = self.keys_of(req.group, everything=True)
            if not keys:
                raise ProjectError(f"--group {req.group}: the model has no field {req.group!r}")
            return View(f"{req.group} of every object, grouped", keys, "group", options=("--group", req.group))
        keys = []
        objs = {str(obj_of(k)) for k in sp.keys if obj_of(k) is not None}
        if req.object is not None and req.object not in objs:
            raise ProjectError(f"--object {req.object}: the model has no object {req.object!r} "
                               f"(objects: {', '.join(sorted(objs)) or 'none'})")
        for item in (req.fields or ("*",)):
            if item == "*":
                hits = [k for k in sp.keys if req.object is None or str(obj_of(k)) == req.object]
            else:
                hits = [k for k in sp.keys if show_key(k) == item
                        or (family(k) == item and (req.object is None or str(obj_of(k)) == req.object))]
            if not hits:
                raise ProjectError(f"--fields: the model has no field {item!r} "
                                   f"(fields: {', '.join(dict.fromkeys(family(k) for k in sp.keys))})")
            keys += [k for k in hits if k not in keys]
        keys = tuple(keys)
        names = ", ".join(show_key(k) for k in keys)
        what = (f"fields {names}" if req.fields and req.fields != ("*",)
                else (f"the life cycle of {req.object}" if req.object else "the whole state space"))
        opts = (("--object", req.object) if req.object else ()) + (("--fields", ",".join(req.fields))
                                                                   if req.fields else ())
        if req.story:
            if len(self.story) < 2:
                raise ProjectError("--story: there is no counterexample here (no STUCK, BROKEN or CONTRADICTION "
                                   "with a path)")
            return View(f"the counterexample alone, {what}", keys, "story", options=("--story",) + opts)
        if req.focus is not None:
            if not self.targets:
                raise ProjectError("--focus: nothing to focus on (no finding with a state, no change)")
            return View(f"{_plural(req.focus, 'step')} around {self.target_text}, {what}", keys, "focus", req.focus,
                        options=("--focus", str(req.focus)) + opts)
        return View(what, keys, options=opts)

    # -------------------------------------------------------------- drawing one view
    def shown(self, view):
        sp = self.space
        if view.kind == "focus":
            return sp.around(self.targets, view.focus)
        if view.kind == "story":
            return set(self.story)
        if view.kind == "new":
            return set(self.change.new_states)
        return None

    def marks_apply(self, keys) -> bool:
        """Mark only what the picture is about: the finding's field or object is drawn,
        or no drawn field belongs to an object."""
        if not self.marked:
            return False
        objs = {obj_of(k) for k in keys if obj_of(k) is not None}
        if self.mark_key is not None:
            return self.mark_key in keys or obj_of(self.mark_key) in objs or not objs
        if self.mark_objs:
            return any(o in {str(x) for x in objs} for o in self.mark_objs) or not objs
        return True

    def draw(self, view: View) -> Drawing:
        sp = self.space
        keys = view.keys
        shown = self.shown(view)
        order = range(len(sp)) if shown is None else sorted(shown)
        proj = sp.projector(keys)
        box_states = {}
        for u in order:
            box_states.setdefault(proj(u), []).append(u)
        succ = sp.succ()
        arrows, folded_args, inside = {}, False, False
        if view.kind == "story":
            for a_, b_, name in zip(self.story, self.story[1:], self.story_names):
                a, b = proj(a_), proj(b_)
                if a != b:
                    arrows.setdefault((a, b), {}).setdefault(name, set()).add(name)
        else:
            for u in order:
                a = proj(u)
                for v, ccs in succ[u].items():
                    if shown is not None and v not in shown:
                        continue
                    b = proj(v)
                    if a == b:
                        inside = True
                        continue
                    labels = arrows.setdefault((a, b), {})
                    for c in ccs:
                        labels.setdefault(sp.names[c], set()).add(c)
        for labels in arrows.values():
            if any(len(cs) > 1 for cs in labels.values()):
                folded_args = True
        red_pairs = set()
        if self.story and len(self.story) > 1:
            for a_, b_ in zip(self.story, self.story[1:]):
                if (shown is None or (a_ in shown and b_ in shown)) and proj(a_) != proj(b_):
                    red_pairs.add((proj(a_), proj(b_)))
        # before / after
        old_boxes, old_arrows = None, None
        if self.change is not None and self.change.space is not None:
            osp = self.change.space
            fill = {k: sp.inits[k] for k in keys if k not in osp.pos}
            oproj = osp.projector(keys, fill)
            old_boxes = {oproj(u) for u in range(len(osp))}
            old_arrows = {}
            for u, nxt in enumerate(osp.succ()):
                a = oproj(u)
                for v, ccs in nxt.items():
                    b = oproj(v)
                    if a != b:
                        old_arrows.setdefault((a, b), set()).update(osp.names[c] for c in ccs)
        # the variant of a NEVER REACHED explanation
        var_boxes, var_arrows = set(), {}
        if self.variant is not None:
            vsp = self.variant[1]
            vproj = vsp.projector(keys)
            vb = {vproj(u) for u in range(len(vsp))}
            var_boxes = vb - set(box_states)
            for u, nxt in enumerate(vsp.succ()):
                a = vproj(u)
                for v, ccs in nxt.items():
                    b = vproj(v)
                    if a == b:
                        continue
                    new = {vsp.names[c] for c in ccs} - set(arrows.get((a, b), {}))
                    if new:
                        var_arrows.setdefault((a, b), set()).update(new)
        # boxes, in the order of their first state
        ordered = sorted(box_states, key=lambda b: box_states[b][0])
        removed_boxes, removed_arrows = [], {}
        if old_boxes is not None:
            drawn = set(ordered)
            for pair, labels in old_arrows.items():
                if pair in arrows:
                    continue
                if shown is None or pair[0] in drawn or pair[1] in drawn:
                    removed_arrows[pair] = labels
            extra = {b for pair in removed_arrows for b in pair} - drawn
            if shown is None:
                extra |= old_boxes - drawn
            removed_boxes = sorted(extra, key=repr)
        names = self.box_names(keys)
        constant = {}
        all_boxes = ordered + removed_boxes + sorted(var_boxes, key=repr)
        if len(all_boxes) > 1:
            for c, nm in enumerate(names):
                vals = {b[c] for b in all_boxes}
                if len(vals) == 1:
                    constant[nm] = next(iter(vals))
        ids = {}
        boxes = []
        apply_marks = self.marks_apply(keys)
        for n, b in enumerate(ordered):
            ids[b] = f"n{n}"
            lines = [f"{nm}={_show(v)}" for nm, v in zip(names, b) if nm not in constant]
            if view.kind == "group":
                lines.append(f"({_plural(len(box_states[b]), 'state')})")
            sts = box_states[b]
            mark, style = "", ""
            if apply_marks:
                hit = sum(1 for u in sts if u in self.marked)
                if hit == len(sts):
                    mark, style = self.mark, "stuck"
                elif hit:                                 # some states of the box only
                    mark = " (can be STUCK)" if self.mark == " (STUCK)" else self.mark
                    style = "stuck"
            if not style and old_boxes is not None and b not in old_boxes:
                style = "added"
            boxes.append(Box(ids[b], lines or ["(all)"], mark, style, len(sts)))
        for b in removed_boxes:
            ids[b] = f"n{len(ids)}"
            lines = [f"{nm}={_show(v)}" for nm, v in zip(names, b) if nm not in constant]
            boxes.append(Box(ids[b], lines or ["(all)"], " (removed)", "removed"))
        for b in sorted(var_boxes, key=repr):
            ids[b] = f"n{len(ids)}"
            lines = [f"{nm}={_show(v)}" for nm, v in zip(names, b) if nm not in constant]
            boxes.append(Box(ids[b], lines or ["(all)"], f" (only with {self.variant[0]})", "dashed"))
        out_arrows = []
        for (a, b), labels in sorted(arrows.items(), key=lambda x: (int(ids[x[0][0]][1:]), int(ids[x[0][1]][1:]))):
            label = ", ".join(sorted(labels))
            style = ""
            if (a, b) in red_pairs or (self.red_actions & set(labels)):
                style = "red"
            elif old_arrows is not None:
                before = old_arrows.get((a, b))
                if before is None:
                    style = "green"
                elif before != set(labels):
                    style = "green"
                    gone = sorted(before - set(labels))
                    label = ", ".join(("+" + x) if x not in before else x for x in sorted(labels))
                    if gone:
                        label += " (no longer: " + ", ".join(gone) + ")"
            out_arrows.append(Arrow(ids[a], ids[b], label, style))
        for (a, b), labels in sorted(removed_arrows.items(), key=lambda x: (ids[x[0][0]], ids[x[0][1]])):
            out_arrows.append(Arrow(ids[a], ids[b], ", ".join(sorted(labels)), "grey", True))
        for (a, b), labels in sorted(var_arrows.items(), key=lambda x: (repr(x[0][0]), repr(x[0][1]))):
            if a in ids and b in ids:
                out_arrows.append(Arrow(ids[a], ids[b], ", ".join(sorted(labels)), "dashed", True))
        if self.missing is not None and self.missing[0] in keys:
            key, value = self.missing
            boxes.append(Box("missing", [f"{names[keys.index(key)]}={_show(value)}"], " (never reached)", "dashed"))
        if self.missing_item is not None:
            boxes.append(Box("missing", [self.missing_item], "", "refusal"))
        if self.refusal is not None:
            u, text, label = self.refusal
            if shown is None or u in shown:
                b = proj(u)
                boxes.append(Box("refused", [text], "", "refusal"))
                out_arrows.append(Arrow(ids[b], "refused", label, "dashed", True))
        # the start, or the way in
        start = None
        if shown is None or 0 in shown:
            start = (ids[proj(0)], None, False)
        elif ordered:
            inside_story = next((u for u in self.story if u in shown), None)
            if inside_story is not None:
                k = self.story.index(inside_story)
                steps = self.story_names[:k]
            else:
                first = min(shown, key=lambda u: (len(sp.path_to(u)), u))
                inside_story, steps = first, sp.path_to(first)
            text = (f"{_plural(len(steps), 'step')}: " + ", ".join(steps) if len(steps) <= 4 else
                    f"{_plural(len(steps), 'step')}: {', '.join(steps[:2])} ... {steps[-1]}")
            start = (ids[proj(inside_story)], text, bool(self.story) and inside_story in self.story)
        # caption and what was folded
        caption = [self.head.split(" [C-")[0] if self.head else f"{self.mid}: {view.name}"]
        caption += self.extra_caption
        objs = sorted({str(obj_of(k)) for k in keys if obj_of(k) is not None})
        if self.report.graph.sym is not None and objs:
            kinds = sorted({f.kind for f in self.model.fields if f.kind and str(f.obj) in objs})
            if kinds:
                caption.append(f"{', '.join(objs)} stands for any {' or '.join(kinds)} (interchangeable)")
        if old_boxes is not None and self.subject is not None:
            caption.append(f"green: new since {self.change.rev}; grey dashed: gone since {self.change.rev}")
        if constant:
            caption.append("in every box: " + ", ".join(f"{k}={_show(v)}" for k, v in constant.items()))
        if not self.report.graph.complete:
            caption.append(f"CAPPED at {self.report.graph.max_states:,} states: only the explored part")
        n_shown = len(order)
        folded = []
        if view.kind == "focus":
            folded.append(f"only the {_plural(n_shown, 'state')} within {_plural(view.focus, 'step')} of "
                          f"{self.target_text} (of {len(sp):,}); the way in is one dashed arrow")
            caption.append(f"the {n_shown} of {len(sp)} states within {_plural(view.focus, 'step')}")
        elif view.kind == "story":
            folded.append(f"only the counterexample's own {_plural(n_shown, 'state')} and steps (of {len(sp):,})")
        elif view.kind == "new":
            folded.append(f"only the {_plural(n_shown, 'new state')} (of {len(sp):,})")
        if n_shown > len(ordered):
            folded.append(f"{n_shown:,} states merged into {_plural(len(ordered), 'box')}")
        left = [k for k in sp.keys if k not in keys]
        if left:
            folded.append("fields not drawn: " + _key_list(left))
        if inside:
            folded.append("steps that change only undrawn fields")
        if folded_args:
            folded.append("arguments on arrows")
        return Drawing(self.mid, view, boxes, out_arrows, start, caption, n_shown, len(sp), folded,
                       self.head, _plural(len(sp), "state"))

    def box_names(self, keys):
        objs = {obj_of(k) for k in keys if obj_of(k) is not None}
        if len(objs) <= 1 and len({family(k) for k in keys}) == len(keys):
            return [family(k) for k in keys]
        return [show_key(k) for k in keys]


def _key_list(keys, limit=8):
    """cond, branch of T2; rentals of T1, T2; day"""
    groups = {}
    for k in keys:
        groups.setdefault(family(k), []).append(obj_of(k))
    parts_ = []
    for fam, objs in groups.items():
        named = [str(o) for o in objs if o is not None]
        parts_.append(f"{fam}[{','.join(named)}]" if named else fam)
    if len(parts_) > limit:
        return ", ".join(parts_[:limit]) + f" and {len(parts_) - limit} more"
    return ", ".join(parts_)


def _transitions(space: Space, keys, fill):
    proj = space.projector(keys, fill)
    out = set()
    for u, nxt in enumerate(space.succ()):
        a = proj(u)
        for v, ccs in nxt.items():
            b = proj(v)
            for c in ccs:
                out.add((a, b, space.names[c]))
    return out, {proj(u) for u in range(len(space))}


def _value_from_repr(domain, text):
    for v in domain:
        if repr(v) == text:
            return v
    return text


# ---------------------------------------------------------------------- choosing
@dataclass
class Choice:
    """The outcome of choosing: the drawing, or none and every view with its size."""
    drawing: Drawing | None
    tried: list                  # (view, boxes, arrows)
    scene: Scene
    request: Request

    def refusal_lines(self, what: str) -> list:
        req = self.request
        out = [f"{self.scene.mid}: no picture drawn: "
               + (f"this view has {self.tried[0][1]} boxes and {self.tried[0][2]} arrows, above " if req.explicit()
                  else "every view is above ")
               + f"the readable size of {req.max_boxes} boxes and {req.max_arrows} arrows "
               f"(ask for a bigger one with --max-boxes N --max-arrows N). Views of this model:"]
        for view, nb, na in self.tried[(1 if req.explicit() else 0):]:
            opts = " ".join(view.options)
            out.append(f"  {PROG} show {what} {opts}".rstrip() + f": {view.name}, {nb} boxes, {na} arrows")
        return out


def choose_view(report: Report, subject: Finding | None = None, change: Change | None = None,
                request: Request | None = None, obj=None) -> Choice:
    """Draw the picture `show` draws: the requested view, or the first readable one of the
    automatic list (a finding: its counterexample's fields, a few steps around it, the
    counterexample alone; a change: the fields its steps change, around what is new, the
    new part; then one object's status field, plus one field, its life cycle, every
    object's status grouped, the whole space)."""
    req = request or Request()
    scene = Scene(report, subject, change, obj=obj if obj is not None else req.object)
    tried = []
    if req.explicit():
        view = scene.explicit(req)
        d = scene.draw(view)
        tried.append((view, d.n_boxes, d.n_arrows))
        if d.fits(req.max_boxes, req.max_arrows):
            return Choice(d, tried, scene, req)
        for v in scene.candidates() + scene.field_views():
            dv = scene.draw(v)
            if dv.fits(req.max_boxes, req.max_arrows):
                tried.append((v, dv.n_boxes, dv.n_arrows))
        return Choice(None, tried, scene, req)
    thin = None
    for view in scene.candidates():
        d = scene.draw(view)
        tried.append((view, d.n_boxes, d.n_arrows))
        if not d.fits(req.max_boxes, req.max_arrows):
            continue
        if view.thin and d.n_boxes < 4:
            thin = thin or d                      # too little to discuss: try adding a field first
            continue
        return Choice(d, tried, scene, req)
    if thin is None:                              # nothing fits: list one view per field as well
        names = {v.name for v, _, _ in tried}
        for view in scene.field_views():
            if view.name not in names:
                d = scene.draw(view)
                tried.append((view, d.n_boxes, d.n_arrows))
    return Choice(thin, tried, scene, req)


def full_size(space: Space) -> tuple[int, int]:
    """Boxes and arrows of the full expansion: every field of every state."""
    return len(space), sum(len(nxt) for nxt in space.succ())


# ---------------------------------------------------------------------- Mermaid text
def mermaid(d: Drawing) -> str:
    out = []
    if d.caption:
        title = "; ".join(d.caption).replace("\\", "/").replace('"', "'")
        out += ["---", f'title: "{title}"', "---"]
    out.append("flowchart LR")
    out.append(f"  %% {d.model}: {d.states_text}, {d.n_boxes} boxes, {d.n_arrows} arrows; view: {d.view.name}")
    for b in d.boxes:
        text = _esc("<br/>".join(b.lines) + b.mark).replace("#lt;br/#gt;", "<br/>")
        if b.style == "refusal":
            out.append(f'  {b.id}(["{text}"])')
        else:
            out.append(f'  {b.id}["{text}"]')
    links = []                                           # (index, style)
    n = 0
    if d.start is not None:
        box, way, red = d.start
        if way is None:
            out.append(f"  start(( )) --> {box}")
        else:
            out.append(f'  start(( )) -. "{_esc(way)}" .-> {box}')
            if red:                                      # the counterexample's own way in
                links.append((0, "dashed"))
        n = 1
    for a in d.arrows:
        if a.dotted:
            out.append(f'  {a.a} -. "{_esc(a.label)}" .-> {a.b}')
        else:
            out.append(f'  {a.a} -- "{_esc(a.label)}" --> {a.b}')
        if a.style:
            links.append((n, a.style))
        n += 1
    styles = {
        "stuck": f"fill:#fdd,stroke:{RED},stroke-width:2px",
        "added": f"fill:#dfd,stroke:{GREEN},stroke-width:2px",
        "removed": f"fill:#f4f4f4,stroke:{GREY},stroke-width:1px,stroke-dasharray:5 3,color:#777",
        "dashed": f"fill:#fff,stroke:{RED},stroke-width:2px,stroke-dasharray:5 3",
        "refusal": f"fill:#fff,stroke:{RED},stroke-width:2px,stroke-dasharray:5 3,color:{RED}",
    }
    for name, css in styles.items():
        members = [b.id for b in d.boxes if b.style == name]
        if members:
            out.append(f"  classDef {name} {css}")
            out.append(f"  class {','.join(members)} {name}")
    link_css = {"red": f"stroke:{RED},stroke-width:3px", "green": f"stroke:{GREEN},stroke-width:3px",
                "grey": f"stroke:{GREY},stroke-width:2px", "dashed": f"stroke:{RED},stroke-width:2px"}
    for k, style in links:
        out.append(f"  linkStyle {k} {link_css[style]}")
    return "\n".join(out) + "\n"


def first_line(d: Drawing) -> str:
    """What the picture covers and what was folded (the picture path is added by the caller)."""
    head = f"{d.model}: " + (d.subject + "; " if d.subject else "")
    return (f"{head}{d.view.name}: {_plural(d.n_boxes, 'box')}, {_plural(d.n_arrows, 'arrow')}; "
            f"folded: {'; '.join(d.folded) if d.folded else 'nothing'}")


# ---------------------------------------------------------------------- picture files
def render_files(items: list) -> tuple[list, str | None]:
    """Write <base>.svg and <base>.png for each (Mermaid text, base path) with Mermaid in
    headless Chromium (Playwright). Returns the files written per item and, when no file
    could be written, why (said plainly in the output, never skipped silently)."""
    if not items:
        return [], None
    node = shutil.which("node")
    if node is None:
        return [[] for _ in items], "node is not on PATH (pictures are drawn by Mermaid in headless Chromium)"
    jobs = [{"mmd": text, "svg": f"{base}.svg", "png": f"{base}.png"} for text, base in items]
    limit = 60 + 15 * len(items)
    try:
        res = subprocess.run([node, str(RENDER_JS), str(MERMAID_JS)], input=json.dumps(jobs), capture_output=True,
                             text=True, timeout=limit, check=False)
    except subprocess.TimeoutExpired:
        return [[] for _ in items], f"the renderer did not finish within {limit} s"
    lines = [x for x in res.stdout.splitlines() if x.strip()]
    try:
        data = json.loads(lines[-1])
    except (IndexError, ValueError):
        err = (res.stderr.strip().splitlines() or ["no output"])[-1]
        return [[] for _ in items], f"the renderer failed ({err})"
    if "error" in data:
        return [[] for _ in items], data["error"]
    written, errors = [], []
    for job, r in zip(jobs, data["results"]):
        if r.get("ok"):
            written.append([Path(job["svg"]), Path(job["png"])])
        else:
            written.append([])
            errors.append(r.get("error", "unknown error"))
    reason = None if not errors else f"Mermaid could not draw {len(errors)} of {len(items)} ({errors[0]})"
    return written, reason


def picture_name(model: str, subject: Finding | None, text: str, auto: bool) -> str:
    """<model>-<fingerprint> for the automatic picture of a conflict (the one `check`
    prints), else <model>-<digest of the Mermaid text>."""
    if subject is not None and auto:
        return f"{model}-{subject.id[2:]}"
    return f"{model}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def write_pictures(root: Path, entries: list) -> list:
    """entries: (name, Mermaid text). Writes .mmd, .svg, .png under the pictures cache and
    returns per entry (files written relative to the root, reason or None)."""
    root = Path(root)
    out_dir = cache_dir(root) / PICTURES
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    mmds = []
    for name, text in entries:
        mmd = out_dir / f"{name}.mmd"
        mmd.write_text(text, encoding="utf-8")
        mmds.append(mmd)
        items.append((text, out_dir / name))
    written, reason = render_files(items)
    out = []
    for mmd, files in zip(mmds, written):
        rel = [p.relative_to(root).as_posix() for p in [mmd] + list(files)]
        out.append((rel, None if files else (reason or "not written")))
    return out


def picture_text(line: str, files: list, reason: str | None) -> str:
    if reason is None:
        shown = [f for f in files if f.endswith(".png")] + [f for f in files if f.endswith(".svg")]
        return f"{line}; picture: {shown[0]} (also {', '.join(shown[1:] + [files[0]])})"
    return f"{line}; picture file not written: {reason} (the Mermaid text is {files[0]})"


def conflict_pictures(report: Report, root: Path) -> list:
    """The picture of every conflict of a core run: (finding id, first line, files)."""
    drawn, out = [], []
    for f in report.findings:
        if f.cls != CONFLICT:
            continue
        choice = choose_view(report, f)
        text, line = _choice_text(choice, f.id)
        if choice.drawing is None:                    # nothing readable: the line lists the views
            out.append((f.id, line, []))
            continue
        drawn.append((len(out), (picture_name(choice.scene.mid, f, text, True), text)))
        out.append((f.id, line, []))
    written = write_pictures(root, [e for _, e in drawn])
    for (n, _), (files, reason) in zip(drawn, written):
        fid, line, _ = out[n]
        out[n] = (fid, picture_text(line, files, reason), files)
    return out


_KIND_ORDER = ("STUCK", "BROKEN", "CONTRADICTION") + ROUTE_KINDS + ("NEVER REACHED",)


def order_conflicts(findings) -> list:
    """Conflicts in the order pictures take them: dead ends, broken rules, refused options,
    second routes, then what never happens (stable within a kind)."""
    rank = {k: n for n, k in enumerate(_KIND_ORDER)}
    return sorted(findings, key=lambda f: rank.get(f.kind, len(rank)))


def _choice_text(choice: Choice, what: str) -> tuple[str, str]:
    """(Mermaid text, first line) of a choice; a refusal is Mermaid comments."""
    if choice.drawing is None:
        lines = choice.refusal_lines(what)
        return "", "\n".join(lines)
    return mermaid(choice.drawing), first_line(choice.drawing)


# ---------------------------------------------------------------------- the picture part
def _git_commit(root: Path, rev: str) -> str:
    try:
        res = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", f"{rev}^{{commit}}"],
                             capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise ProjectError("git is not installed: the change cannot be computed") from None
    if res.returncode != 0:
        raise ProjectError(f"unknown revision {rev!r} (or not a git repository)")
    return res.stdout.strip()


def before_change(root: Path, path: Path, rev: str, commit: str, reads, bounds: Bounds) -> Change:
    """Load the model as it is at a revision (the files its current load reads, exported
    with git) and explore it."""
    with tempfile.TemporaryDirectory(prefix="flowguard-before-") as tmp:
        export_at(root, commit, list(reads), Path(tmp))
        rel = Path(path).resolve().relative_to(Path(root).resolve())
        old_path = Path(tmp) / rel
        if not old_path.is_file():
            return Change(rev, None, note=f"{rel.as_posix()} is not in {rev}")
        loaded = load_model(old_path, Path(tmp))
        g = explore(loaded.model, bounds)
    ch = Change(rev, Space(g))
    if not g.complete:
        ch.note = f"the model at {rev} is capped at {bounds.max_states:,} states"
    return ch


def picture_part(ctx: PartContext) -> PartResult:
    """One picture of one model: options what (a conflict id, or empty for the model's
    first conflict), before (REV and its commit), the view request and max_states."""
    root, spec = Path(ctx.root), ctx.spec
    opt = dict(spec.options)
    bounds = Bounds(opt.get("max_states", Bounds().max_states))
    try:
        loaded = load_model(ctx.path, root)
    except ModelError as err:
        reads = sorted(err.reads)
        line = f"{spec.model}: no picture: the model does not load: {err}"
        return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), True, [],
                          {"first_line": line, "mermaid": "", "error": str(err)}, reads, [])
    report = check_model(loaded, bounds)
    reads = list(loaded.reads)
    subject = None
    conflicts = order_conflicts(f for f in report.findings if f.cls == CONFLICT)
    what = opt.get("what") or ""
    if what.startswith("C-"):
        subject = next((f for f in conflicts if f.id == what), None)
        if subject is None:                           # a second route: the route checks name it
            try:
                _, _, routes = route_checks(ctx.path, root, bounds)
            except ModelError as err:
                line = f"{spec.model}: no picture: the route checks stop at a model error: {err}"
                return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.graph.complete, [],
                                  {"first_line": line, "mermaid": "", "error": str(err)}, reads, [])
            subject = next((f for f in routes.findings if f.cls == CONFLICT and f.id == what), None)
        if subject is None:
            line = f"{spec.model}: no picture: no conflict {what} in this model now"
            return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.graph.complete, [],
                              {"first_line": line, "mermaid": "", "error": line}, reads, [])
    elif opt.get("subject", True) and conflicts:
        subject = conflicts[0]
    change = None
    if opt.get("before"):
        change = before_change(root, ctx.path, opt["before"], opt["commit"], reads, bounds)
    req = Request(tuple(opt["fields"]) if opt.get("fields") else None, opt.get("object"), opt.get("focus"),
                  bool(opt.get("story")), opt.get("group"), opt.get("max_boxes", MAX_BOXES),
                  opt.get("max_arrows", MAX_ARROWS))
    try:
        choice = choose_view(report, subject, change, req, obj=opt.get("obj"))
    except ProjectError as err:
        line = f"{spec.model}: no picture: {err}"
        return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.graph.complete, [],
                          {"first_line": line, "mermaid": "", "error": str(err)}, reads, [])
    shown_what = what or spec.model
    text, line = _choice_text(choice, shown_what)
    auto = not req.explicit() and change is None
    name = picture_name(choice.scene.mid, subject, text, auto)
    info = {"first_line": line, "mermaid": text, "subject": subject.id if subject else None,
            "drawn": choice.drawing is not None, "states": len(choice.scene.space)}
    writes = []
    if choice.drawing is not None:
        (files, reason), = write_pictures(root, [(name, text)])
        info["first_line"] = picture_text(line, files, reason)
        info.update(files=files, rendered=reason is None, reason=reason,
                    boxes=choice.drawing.n_boxes, arrows=choice.drawing.n_arrows, view=choice.drawing.view.name)
        writes = files if reason is None else files[:1]
    return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.graph.complete, [], info,
                      reads, writes)


register("picture", picture_part, on_request=True)


# ---------------------------------------------------------------------- show
def inprocess_runner(root: Path):
    """Runs parts in this process (until the job system runs them); records manifests
    of core parts, as the job system does."""
    root = Path(root)
    flow = root / ".flowguard" / "flow"

    def run(specs):
        out = []
        for spec in specs:
            res = run_part(PartContext(root, spec, flow / f"{spec.model}.py", cache_dir(root)))
            if spec.kind == "core":
                write_manifest(root, spec.model, res.reads)
            out.append(res)
        return out
    return run


class _Usage(Exception):
    pass


def show_main(root: Path, a, runner) -> tuple[int, str]:
    """`show [WHAT] [--before REV] [view options]`: returns (exit code, stdout text).
    a: the parsed arguments of the show verb (cli.parser); runner(specs) -> PartResults
    runs the parts (the job system, or in process)."""
    root = Path(root).resolve()
    view_opts = (("fields", tuple(a.fields.split(",")) if a.fields else None), ("object", a.object),
                 ("focus", a.focus), ("story", a.story), ("group", a.group), ("max_boxes", a.max_boxes),
                 ("max_arrows", a.max_arrows), ("max_states", a.max_states))
    try:
        code, pictures, more, message = _plan_show(root, a, view_opts, runner)
    except (ProjectError, _Usage) as err:
        code, pictures, more, message = 2, [], [], str(err)
    if a.json:
        return code, json.dumps({"exit": code, "message": message, "pictures": pictures, "more": more,
                                 "resume": None}, ensure_ascii=False, sort_keys=True) + "\n"
    out = []
    if message:
        out.append(message)
    for n, pic in enumerate(pictures):
        if n:
            out.append("")                                 # a blank line between pictures
        out.append(pic["first_line"])
        if pic.get("mermaid"):
            out.append(pic["mermaid"].rstrip("\n"))
    if more:
        out.append(f"{len(more)} more not drawn:")
        out += [f"  {m}" for m in more]
    return code, "\n".join(out) + "\n"


def _plan_show(root, a, view_opts, runner):
    models = {p.stem: p for p in model_files(root)}
    if not models:
        raise _Usage("nothing under discussion: no flow models in .flowguard/flow/")
    before = None
    if a.before:
        before = (a.before, _git_commit(root, a.before))
    subjects = []                                         # (model, what, before)
    message = ""
    more = []
    if a.what:
        what = a.what
        if what.startswith("C-"):
            found = _conflicts(root, runner, list(models), a.max_states)
            hit = [(m, f) for m, fs in found.items() for f in fs if f.id == what]
            if not hit:
                raise _Usage(f"no conflict {what} now (conflicts: "
                             + (", ".join(f.id for fs in found.values() for f in fs) or "none") + ")")
            subjects.append((hit[0][0], what, before, None))
        else:
            model, _, obj = what.partition(":")
            if model not in models:
                raise _Usage(f"{model}: no such model (models: {', '.join(sorted(models))})")
            found = _conflicts(root, runner, [model], a.max_states)
            subjects.append((model, found[model][0].id if found[model] else "", before, obj or None))
    elif before is not None:
        subjects += [(m, "", before, None) for m in sorted(models)]
    else:
        found = _conflicts(root, runner, list(models), a.max_states)
        previous = read_conflicts(root)
        try:
            changed = [p.stem for p in changed_models(root)]
            git = True
        except (ProjectError, FileNotFoundError):        # not a git repository, or no git installed
            changed, git = [], False
        ordered = []
        for group in (changed, [m for m in sorted(models) if m not in changed]):
            ids = [f.id for m in group for f in found.get(m, [])]
            new, open_ = new_and_open(previous, ids)
            for fid in new + open_:
                m = next(m for m in group if any(f.id == fid for f in found.get(m, [])))
                ordered.append((m, fid))
            if ordered:
                break
            if group is changed and changed:
                head = _git_commit(root, "HEAD") if _has_head(root) else None
                if head is not None:
                    ordered = [(m, ("HEAD", head)) for m in changed]
                    break
        if not ordered:
            if not git:
                raise _Usage("nothing under discussion: no conflict, and the change cannot be computed without git; "
                             f"name a model (models: {', '.join(sorted(models))})")
            raise _Usage(f"nothing under discussion: no conflict and no changed model; name a model "
                         f"(models: {', '.join(sorted(models))})")
        for m, x in ordered:
            if isinstance(x, tuple):
                subjects.append((m, "", x, None))
            else:
                subjects.append((m, x, None, None))
    if len(subjects) > MAX_PICTURES:
        for m, x, b, _ in subjects[MAX_PICTURES:]:
            more.append(f"{PROG} show {x or m}" + (f" --before {b[0]}" if b else ""))
        subjects = subjects[:MAX_PICTURES]
    specs = []
    for model, what, bef, obj in subjects:
        opts = dict(view_opts)
        opts.update(what=what, obj=obj)
        if bef is not None:
            opts.update(before=bef[0], commit=bef[1], subject=bool(a.what) or bool(what))
        specs.append(PartSpec("picture", model, tuple(sorted(opts.items()))))
    results = runner(specs)
    pictures = []
    code = 0
    for spec, res in zip(specs, results):
        info = res.info
        if info.get("error"):
            code = 2
        pictures.append({"model": spec.model, "first_line": info.get("first_line", ""),
                         "mermaid": info.get("mermaid", ""), "files": info.get("files", []),
                         "rendered": info.get("rendered", False), "reason": info.get("reason"),
                         "subject": info.get("subject"), "boxes": info.get("boxes"), "arrows": info.get("arrows")})
    return code, pictures, more, message


def _has_head(root) -> bool:
    try:
        _git_commit(root, "HEAD")
        return True
    except ProjectError:
        return False


def _conflicts(root, runner, models, max_states) -> dict:
    """model id -> its conflicts now, in picture order: the parts `check` runs (core and
    routes, the same parts, so a check before is a cache hit)."""
    specs = [PartSpec(kind, m, (("max_states", max_states),)) for m in sorted(models) for kind in kinds()]
    found = {m: [] for m in sorted(models)}
    for spec, res in zip(specs, runner(specs)):
        found[spec.model] += [Finding.from_json(d) for d in res.findings if d["cls"] == CONFLICT]
    return {m: order_conflicts(fs) for m, fs in found.items()}
