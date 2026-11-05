# Flow models: the design as a small model, checked in every order

A flowchart shows boxes and arrows; it does not show what happens when the arrows are taken
in every possible order. A flow model does. You write the part of the design a change
touches as a small machine (a few fields, the actions that change them, the promises the
requests make), and `check` tries every action with every argument in every reachable state
and reports what gets stuck, what never happens and which promise some order breaks, each
with the shortest path and the requests behind it. Keep it small: leave out everything that
does not change what can happen, and say what you left out in a `note=`.

Use a flow model when a request adds or changes state values, actions, conditions, settings
or endings: update the affected feature's model first, run `check`, then implement and test
the code. For other edits, use `status`, `where` and the project's tests. A feature may cross
modules and unchanged code. Turn affected old and new requested outcomes into explicit
`reach`/`progress` promises, even in the first model. Include shared writes, resets and new
routes, with bounds that preserve their conditions under the code's default settings.
Keep counts in separate fields when different actions reset them. An omitted required
outcome stays unresolved, even with a `note=` or passing isolated tests.
Code/tests, exposed behavior and composition are conceptual levels, not a required
three-file split; keep one feature model until a split helps explain it.

One model per file: `.flowguard/flow/<name>.py`, ending with `MODEL = m`. Check them all with
`python -m flowguard check` (files starting with `_` are helpers, never models).
Only `check --full` also breaks each model on purpose to see that its checks catch it;
ordinary `check` does not run these deliberate breaks.
`python -m flowguard release` runs `check --full` (and, with `--shards`, the tests),
also in a project with no legacy map. Open conflicts fail release; CI blocks them only
if it runs release. Without a hook that runs the check, a commit is not blocked.
`python -m flowguard show` draws what is under
discussion: the conflicts, else the change against
HEAD (`show MODEL`, `show C-...` or `--before REV` name it yourself; `show MODEL` of a model
with no conflict draws its latest change, one object's fields at a time).
Each `source=` names a request stored with `python -m flowguard req add <file> --id R10`
(never write a file in `.flowguard/requests/` by hand); an id with no stored request is a
model warning.

When a compatible design satisfies the requests, fix it yourself and show its before/after
with `show MODEL --before REV`. In a flow discussion, always use the picture with a few
plain sentences. If requirements genuinely collide, ask the owner with that picture and
the stored source words. While an answer is unavailable, take a safe reversible action
that keeps things working and label it temporary. Dead ends and never-happens behavior
must be fixed in code; a temporary decision does not settle them. Fix a broken main route
instead of adding a fallback.

The flow commands use the same models and checks on supported platforms. `status` reports
any platform limitation alongside the stored conflicts.

## Writing a model

- `m = Model(name, covers=["pkg/mod.py:Class"], config="pkg.config:Config", note=...)`:
  `covers` names the code it describes; `config` names the code's settings object.
- `m.setting("limit", source="R9")`: read a setting from the code
  (`getattr(Config, "limit")`). Use `S = m.settings`, then `S["limit"]` in actions.
- `m.setting("limit", 2, source="R12")`: give a value for a setting the code does not
  have yet. Giving an existing code setting a value is a model error naming both values:
  `settings not read from the code: limit=2 (code default 4)`. `m.settings` is read-only.
- `m.setting("limit", 2, propose=True, source="R12")`: explicitly try a change to a code
  setting before changing the code. `check` reports the proposed and current values as an
  advisory; `release` fails while they differ. `status` keeps showing the proposal until
  the code and model agree. Then remove `propose=True` and read the setting from the code.
- `IDS = m.objects("tool", "T1", "T2")`: interchangeable ids (at most 4); use a plain
  list when they are not interchangeable. Never order them (`<`, `sorted`, `min`), name
  one or read their text: ordering or naming one is a model error. A use the check cannot
  judge turns the renaming off (said on the last line).
- `m.field(name, domain, init, over=IDS, source=, value_sources={"transit": "R10"}, note=)`:
  one field, or one per object (`s[name, t]`); small domains, counters clamped.
- `@m.action(t=IDS, source="R4")` with `need(cond, "reason", source=)`: an action tried
  with every argument. `need` is the guard (it carries the action's source unless it names
  its own); assignments are the effect. `with s.source("R10"): ...` marks effects.
- `m.option(name, offered, action=, source=, **params)`: a screen option; where it is
  offered, the action must work (same parameter names).
- `m.terminal(field, values, source=)`: values that end an object's life on purpose.
  A step that leaves one is a model error.
- `m.always / only_when / after / progress / reach(...)`: promises that hold in every
  state; hold before every success of an action; hold after it; keep a goal reachable from
  every matching state; or have some state that reaches the goal, respectively.
- `m.second_route(a, b, source="R11", why=...)`: the only way to keep a second route
  to the same result. `source=` is the stored request's ID (`R11`), and `check` prints
  the kept pair.

## Compare the model with code

For a model whose field is `n` and action is `step`, connect the real object once:

```python
from flowguard.flow.adapter import fields
m.bind_adapter(
    {"system": "app:Program", "classes": ["app:Program"], "refusal": ["app:Refusal"]},
    state=lambda snapshot: fields(snapshot, names=("n",)),
    operations={"step": "step"},
)
```

`system` constructs the real object; `classes` names the project types in its state.
The projection reads captured real fields. Map every model action to its real operation;
an optional dispatch receives only actual call inputs, never the model's expected answer.
The same binding owns replay, snapshots, restoration and bounded walks. Ordinary checks
compare construction and one enabled witness per operation; a full check adds a seeded
walk. A model conflict is confirmed only with sufficient native evidence. An unsupported
observation stays UNKNOWN. A mismatch reports MODEL DRIFT and the actual input path;
inspect code and model before choosing which to fix. `show C-...` uses the cached witness.

Conflicts survive smaller models, removed starts and weakened sourced promises. Repair
the behavior and run a complete check of the retained scope; a code repair leaves an
executed regression. For a real replacement requirement, store the new owner's words
with `req add --supersedes`, update the affected contract and code, then cite those words
with `decide ID --owner "quote"`. The record distinguishes a requirement change from a
code fix. An AI provisional decision is only for genuinely contradictory requested rules.

`check --tests tests/test_app.py::test_case` explicitly audits selected native pytest
calls for fallback routes; ordinary `check` and `status` do not launch the project suite.
MASKING requires a witnessed failed primary and a passing test that fails when its
fallback is disabled. BOTH needs a real owner declaration for two intended routes;
VISIBLE failures reach the caller. Unreached handlers and defaults appear as counts.
For two already implemented and witnessed intended routes, use `decide ID --owner "quote"
--request Rn --existing-routes`; changing or retiring that authority reopens the finding.
Use `check --commit-ready` after staging to read the evidence for the actual staged bytes;
it runs no tests. A finished UNKNOWN permits a commit and remains visible in `status`.

Ids are used only symmetrically: in `over=`, action parameters, `[None] + IDS`, loops and
comprehensions over them. Picking one by its place (`IDS[0]`, unpacking, a loop that breaks)
or `"T1"` is a model error. These uses turn the renaming off (said on the last line): an id
made from text or taken from elsewhere (`m.kinds`, project code); a loop that carries more
than a count, a flag or each id's own cells on to the next id; per-id values in the declared
order compared as a whole (`==`, `in`, put in a container) or written into the state.

## A small example (not your application): `.flowguard/flow/parcels.py`

R1 already allows customers to collect parcels; R2 adds nightly expiry. The old outcome
becomes the explicit `reach` below. Merely leaving the locker is a different promise:
returning every parcel would satisfy it while making collection impossible.

```python
"""Parcel locker: parcels wait at most keep_days nights in the one locker.
Left out: the courier's route and the customers' codes (no rule reads them)."""
from flowguard.flow import Model, need

m = Model("parcel locker", note="one locker; a finished slot takes the next parcel")
S = m.settings
m.setting("keep_days", 2, source="R1")              # the code has no setting yet: a value
PARCELS = m.objects("parcel", "P1", "P2")            # interchangeable: explored up to renaming
m.field("where", ["depot", "locker", "collected", "returned"], "depot", over=PARCELS, source="R1")
m.field("days", range(0, S["keep_days"]), 0, over=PARCELS, source="R2",
        note="nights in the locker, 0..keep_days-1")
m.reach("customers can still collect parcels",
        lambda s: any(s["where", p] == "collected" for p in PARCELS), source="R1")


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

With R1 and R2 stored, `check` prints:

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

`clean, complete` describes the declared model and its bounds. It does not establish an
omitted outcome or that the application code follows the model.

- **Conflicts**: fix them in the design, then in the code, or ask the owner when two requests
  really collide. STUCK means a value that can never change again; an undeclared end where
  its object halts or loses an action it could take before; or a lost `progress` promise.
  Each names the stuck object's fields, refused calls with their requests and the step in.
  A bounded clock or counter's counting step is exempt only if it works in every reachable
  non-end counter context. A day that always advances until its limit is such a clock;
  a use count whose `rent` step needs a rentable object is not, even if another `inspect`
  action can still cycle. Declaring an intentional end uses `m.terminal`.
  BROKEN means a promise some order breaks; CONTRADICTION means an option is offered where
  its action refuses. NEVER REACHED covers an action, option, declared end, `reach` promise,
  or a field value with a source or named by a sourced promise; it says which one-setting
  change would reach it, or that none does. DUPLICATE ROUTE, SUBSUMED ACTION and FALLBACK
  ROUTE identify second routes to the same result. A fallback works exactly where another
  refuses, perhaps writing an otherwise unread field. Keep one route, or declare the second
  with `m.second_route`.
- **Model warnings** (never conflicts): other field values never reached, usually a domain
  wider than the design needs; a `source=` with no stored request; settings not read from
  the code although the model covers code; a proposed setting that differs from the code; a
  fallback on the status field only, an `if` whose two branches end the same, lines no call runs, a
  guard that never refuses. With `--full`, each deliberate break no check catches is advisory,
  and the first line counts them.
- **Model errors**: the model itself failed (an exception, a value outside its domain, a write to an
  unknown field or to `m.settings`, a declaration mistake, or an own value for an existing
  code setting without `propose=True`). Fix these first. Leaving a declared terminal value
  is a model error too.
- **UNKNOWN**: the search hit its state bound ("capped"), a model error cut it short (no STUCK or
  NEVER REACHED is decided there), or a model did not load ("not explored"). What it found with a
  path is certain; nothing is reported as holding or clean. Make the model smaller, not the bound.
- **OPEN ... (kept: ...)**: a proven conflict stays open, and release fails, until a complete check of its
  model no longer finds it ("closed ..."); nothing else closes it (a capped check, also one whose replay
  of the stored path fails, a model error, a rename, a deleted model file).
  `show` of it says so (exit 3). `check` keeps the open conflicts in
  `.flowguard/conflicts.json`: commit that file with the change.
- The last line per model says how complete the search was, which settings it used and from
  where, and `concurrency not checked` when the covered code runs threads or async code.
