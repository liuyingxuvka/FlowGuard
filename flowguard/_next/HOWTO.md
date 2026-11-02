# Flow models: the design as a small model, checked in every order

A flowchart shows boxes and arrows; it does not show what happens when the arrows are taken
in every possible order. A flow model does. You write the part of the design a change
touches as a small machine (a few fields, the actions that change them, the promises the
requests make), and `check` tries every action with every argument in every reachable state
and reports what gets stuck, what never happens and which promise some order breaks, each
with the shortest path and the requests behind it. Keep it small: leave out everything that
does not change what can happen, and say what you left out in a `note=`.

One model per file: `.flowguard/flow/<name>.py`, ending with `MODEL = m`. Check them all with
`python -m flowguard._next check` (files starting with `_` are helpers, never models); `check
--full` also breaks each model on purpose to see that its checks catch it. `python -m
flowguard._next show` draws what is under discussion: the conflicts, else the change against
HEAD (`show MODEL`, `show C-...` or `--before REV` name it yourself; `show MODEL` of a model
with no conflict draws its latest change, one object's fields at a time).

## Writing a model

| Call | Meaning |
|---|---|
| `m = Model(name, covers=["pkg/mod.py:Class"], config="pkg.config:Config", note=...)` | the model; `covers` names the code it describes, `config` the code's settings object |
| `m.setting("limit", source="R9")` | a setting read from the code (`getattr(Config, "limit")`); read it in actions as `S["limit"]` with `S = m.settings` |
| `m.setting("limit", 2, source="R12")` | a setting the code does not have yet (only then give a value) |
| `IDS = m.objects("tool", "T1", "T2")` | interchangeable ids (at most 4); a plain list when they are not interchangeable. Never order them (`<`, `sorted`, `min`), name one, or read their text: ordering or naming one is a model error, and a use the check cannot judge turns the renaming off (said on the last line) |
| `m.field(name, domain, init, over=IDS, source=, value_sources={"transit": "R10"}, note=)` | one field, or one per object (`s[name, t]`); small domains, counters clamped |
| `@m.action(t=IDS, source="R4")` with `need(cond, "reason", source=)` | an action tried with every argument; `need` is the guard (it carries the action's source unless it names its own), assignments are the effect; `with s.source("R10"): ...` marks effects |
| `m.option(name, offered, action=, source=, **params)` | a screen option: where it is offered, the action must work (same parameter names) |
| `m.terminal(field, values, source=)` | the values that end an object's life on purpose |
| `m.always / only_when / after / progress / reach(...)` | the promises: hold in every state; hold before every success of an action; hold after it; from every such state the goal stays reachable; some state has it |
| `m.second_route(a, b, source="R11", why=...)` | the only way to keep a second route to the same result; `source=` must be a stored request (`.flowguard/requests/R11.md`), and `check` prints the kept pair |

Ids are used only symmetrically: in `over=`, action parameters, `[None] + IDS`, loops and comprehensions
over them. Picking one by its place (`IDS[0]`, unpacking, a loop that breaks) or `"T1"` is a model error; an id
made from text or taken from elsewhere (`m.kinds`, project code), or a loop that carries more than a count, a flag or each id's own cells on to the next id, turns the renaming off (said on the last line).

## A small example (not your application): `.flowguard/flow/parcels.py`

```python
"""Parcel locker: parcels wait at most keep_days nights in the one locker.
Left out: the courier's route and the customers' codes (no rule reads them)."""
from flowguard._next import Model, need

m = Model("parcel locker", note="one locker; a finished slot takes the next parcel")
S = m.settings
m.setting("keep_days", 2, source="R1")              # the code has no setting yet: a value
PARCELS = m.objects("parcel", "P1", "P2")            # interchangeable: explored up to renaming
m.field("where", ["depot", "locker", "collected", "returned"], "depot", over=PARCELS, source="R1")
m.field("days", range(0, S["keep_days"]), 0, over=PARCELS, source="R2",
        note="nights in the locker, 0..keep_days-1")


@m.action(p=PARCELS, source="R1")
def deliver(s, p):                                   # the courier fills the single locker
    need(s["where", p] == "depot", "not at the depot")
    need(all(s["where", q] != "locker" for q in PARCELS), "the locker is full")
    s["where", p], s["days", p] = "locker", 0


@m.action(p=PARCELS, source="R1")
def pick_up(s, p):                                   # the customer opens it with the code
    need(s["where", p] == "locker", "not in the locker")
    s["where", p] = "collected"


@m.action(source="R2")
def night(s):                                        # parcels kept too long go back
    for p in PARCELS:
        if s["where", p] == "locker":
            s["days", p] += 1
            if s["days", p] >= S["keep_days"]:
                s["where", p], s["days", p] = "returned", 0


@m.action(p=PARCELS)
def new_parcel(s, p):                                # a finished slot takes the next parcel
    need(s["where", p] in ("collected", "returned"), "slot in use")
    s["where", p] = "depot"


m.option("pick up", lambda s, p: s["where", p] == "locker", action="pick_up", p=PARCELS, source="R1")
m.always("one parcel at a time in the locker",
         lambda s: sum(s["where", p] == "locker" for p in PARCELS) <= 1, source="R1")
m.progress("a parcel in the locker always leaves it", over=PARCELS, source="R2",
           when=lambda s, p: s["where", p] == "locker", goal=lambda s, p: s["where", p] != "locker")
MODEL = m
```

`check` prints:

```text
clean, complete
parcels: complete, 25 states (parcels explored up to renaming); settings keep_days=2 (model only)
```

Delete the `"the locker is full"` line and it prints the broken promise with its path:

```text
1 new conflict; complete
NEW BROKEN parcels: always 'one parcel at a time in the locker'
  path (2 steps): deliver(p='P1') ; deliver(p='P2')
```

## Reading the report

- **Conflicts** (fix them in the design, then in the code, or ask the owner when two requests
  really collide): STUCK (a value some state can never leave again; a value no state leaves where
  its object halts or can never again take a step it took before, unless `m.terminal` declares that
  end; a `progress` promise lost; each names the stuck object's fields, every call that refuses there with its request, and
  the step that led in), BROKEN (a promise some order breaks), CONTRADICTION (an option
  offered where its action refuses), NEVER REACHED for an action, an option, a declared end,
  a `reach` promise, or a field value that has a source or that a sourced promise names (each
  says which one-setting change would reach it, or that none does); a second route to the same
  result: DUPLICATE ROUTE, SUBSUMED ACTION, FALLBACK ROUTE (one action works exactly where
  another refuses and makes the same change, perhaps writing a field nothing reads besides).
  Keep one route, or declare the second with `m.second_route`.
- **Model warnings** (never conflicts): other field values never reached, usually a domain
  wider than the design needs; settings not read from the code although the model covers code; a
  fallback on the status field only, an `if` whose two branches end the same, lines no call runs, a
  guard that never refuses; with `--full`, each break of the model that no check catches.
- **Model errors**: the model itself failed (an exception, a value outside its domain, a write
  to an unknown field, a declaration mistake). Fix these first.
- **UNKNOWN**: the search hit its state bound ("capped"), a model error cut it short (no STUCK or
  NEVER REACHED is decided there), or a model did not load ("not explored"). What it found with a
  path is certain; nothing is reported as holding or clean. Make the model smaller, not the bound.
- **OPEN ... (kept: ...)**: a proven conflict stays open until a complete check of its model no
  longer finds it or its stored path no longer reproduces it; nothing else closes it (a capped check,
  a model error, a rename, a deleted model file). `show` of it under a capped search says so (exit 3).
- The last line per model says how complete the search was, which settings it used and from
  where, and `concurrency not checked` when the covered code runs threads or async code.
