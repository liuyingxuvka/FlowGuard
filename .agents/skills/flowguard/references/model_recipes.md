# Writing a FlowGuard model

A model is a Python file in `.flowguard/models/` with this contract:

```python
MODEL_ID = "order_placement"                                  # unique id, also used on the command line
COMPONENTS = ["orders"]                                       # map components this model protects
IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}   # block -> real code (checked by `check`)
def build_explorer(): ...     # REQUIRED: Explorer of the intended design; must pass
def broken_variants(): ...    # REQUIRED: {name: Explorer}; each must FAIL, and together they should break every invariant (map models warns otherwise; release fails)
def conformance(): ...        # REQUIRED: replay the real code, or compare it as code facts; .ok must be True
```

Selectors are `MODEL_ID` for top-level contract files; component ids are for
`read --component`. Unknown selectors fail.
Every selected model executes on every call (no result cache). A model without anchors or
without conformance fails as "abstract boundary only".
A model of code that does not exist yet is a target model: write it under `.flowguard/target/models/` (SKILL.md, target first).

`TESTED_BY = {"invariant_name": ["tests/test_x.py:test_name"]}` binds model rules
to real test anchors in both directions. Missing or renamed tests fail `map check`; keys must
be actual design invariants. `NOT_MODELED = {"path.py:Symbol": "reason"}` records an explicit
unmodeled entry; it grants no implementation proof. Each implementation anchor must be called, or its
file read as code facts (`flowguard.map.facts.CodeFacts`), during conformance (abstract exploration grants no anchor credit); a bad
variant must violate the intended design's property. `map lint` warns when a model names no tests.

Run: `python -m flowguard map models <MODEL_ID>`. Start with `python -m flowguard template behaviour --write .`.
Models import project code; for a src layout, first run `python -m pip install -e .` or set `PYTHONPATH`.

## Five steps

1. Name the failure you protect against in one sentence ("a retry charges the card twice").
2. Inputs: a small finite set of abstract events (2-5), including the repeat/retry/out-of-order one.
3. State: a frozen dataclass with only the facts that affect future behavior or the invariant.
4. Blocks: classes with `apply(input, state)` returning `FunctionResult(output, new_state, label=...)`
   for every possible branch (return more than one result for nondeterministic outcomes).
   For an input invalid in this state, return an explicit ignored result such as `FunctionResult("ignored", state, label="ignored")`; `[]` is a dead branch.
   Never call network, clock, random or databases inside a model.
5. Invariants that must hold in every reachable state, one broken variant per protected
   failure, and a conformance adapter.

Keep `max_sequence_length` at 2-5. Split a model that exceeds the size limits;
keep inputs and states finite.

## Ready-made invariants (`from flowguard import ...`)

| need | helper |
| --- | --- |
| effect at most once per key (charges, emails, records) | `at_most_once_by(name, description, selector, key)` |
| no duplicate rows | `no_duplicate_by(name, description, selector, key)` |
| every derived item has a source | `all_items_have_source(...)` |
| cache equals source of truth | `cache_matches_source(name, description, cache_selector, source_selector, key, value)` |
| only one block writes a field | `only_named_block_writes(field_name, owner_function_name)` |
| B never before A / X never after Y | `require_label_order(before, after)`, `forbid_label_after(anchor, forbidden)` |
| anything else | `Invariant(name, description, lambda state, trace: InvariantResult.pass_() or .fail("why"))` |
| something must be reachable | `require_label(label)`, `require_reachable(name, predicate)` (pass to Explorer `required_reachable=`) |


## Recipes

- **Primary path with a fallback**: see [External promise (no silent fallback)](routes.md#external-promise-no-silent-fallback).

- **API with several operations**: use `Workflow((SetBlock(), DelBlock()), mode="choice")`; each
  block declares `accepted_input_type`. Each input runs exactly one accepting block; no match is
  a dead branch and multiple matches are an `AmbiguousChoice` exception branch.

- **Retry / idempotency**: inputs `Request(id)` with repeated ids; state holds processed ids and
  effects; invariant `at_most_once_by` on effects; broken variant = handler without the "already
  processed" branch.
- **Cache freshness**: inputs `Write(key, v)`, `Read(key)`, `Invalidate(key)`; state holds source and
  cache; invariant: a read never returns a value different from the source after the write was
  acknowledged; broken variant = write that does not invalidate.
- **Multi-step workflow / state machine**: one block per step, a `phase` field in state; invariants
  with `require_label_order`; use `flowguard.loop.check_loops` to find stuck states.
- **Permissions**: inputs carry a role; invariant: a forbidden role never reaches the protected
  effect; broken variant = check placed after the effect.

## Conformance (model <-> code)

When the changed contract depends on order, repeated inputs, state or side effects,
write an adapter with `reset(initial_state)`, `apply_step(step) -> ReplayObservation`,
`observe_state()`, `observe_output()`. It calls the real code for `step.function_input` and
projects the real state into the model's `State`. Replay only the traces that cover every
modeled transition:

If real code ends in an error, return an explicit observation such as `ReplayObservation(name, observed_output="error:<type>", observed_state=State(error="<type>"))`; model that error state and let invariants handle it, rather than returning a sentinel that breaks invariant unpacking.

```python
from flowguard import replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches

def conformance():
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=Adapter(), invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        if not last.ok:
            return last
    return last
```

A model is done when the intended design passes, its relevant business broken variants
fail, required conformance passes, and `python -m flowguard map check` reports no
`model_*` errors. A pure anchor rename reuses the existing model/tests and does not
need a new adapter. Report which code facts or real replay ran; do not describe an unrun replay as passed.


## Helpers

`read` never imports a model: it reads rules from the `invariants=` of the explorer that
`build_explorer()` returns. Write rules as module-level `Invariant(...)` values, import them
from a `_helper` file, or build them with a small wrapper returning `Invariant(name, text, ...)`;
`read` then shows each name and description. When it cannot, it shows `?` and
`python -m flowguard map models` prints the real names.


### Run the bound tests

`python -m flowguard map models --tests` checks each model's `TESTED_BY` tests;
`python -m flowguard release` always includes this check. Without `--tests`,
`map models` does not run tests. Each model uses one fresh pytest process.
Every bound test, including each parameter case, must pass and call a Python
`IMPLEMENTED_BY` body or explicitly read at least one anchored file during its
own test call. Another test's calls, collection imports and import-loader reads
do not supply that reach. A real body call or explicit read through a helper or
conformance check in that same window does count.

Only calls and reads in the same process are visible: subprocess-only tests miss
the anchors. A weaker assertion that still calls the code cannot be detected.
Non-Python test bindings are warned about, not executed.
Checking Python bindings requires pytest in the environment (`.[dev]` provides it).

**Which tests to bind:** give every rule a test that fails when that rule breaks, plus a real normal-path or replay test; one test may guard several rules.
`TESTED_BY` uses real paths: `tests/test_x.py:test_name` runs every parameter case; `tests/test_x.py:test_name[param-id]` binds that exact case.
`invariant_untested` names rules with no `TESTED_BY` key; it is a warning that does not gate `release`, and its absence does not prove assertion strength.
The tests facet of `python -m flowguard read --component <id>` shows each node's bindings.

USES binds code a model reads but does not own; conformance must call it.

## Ports

Ports are read from the actual explorer/state and literal declarations; no saved port copy is authoritative. A field's rule belongs to the model that holds every field it reads. IMPLEMENTED_BY names owned functions once; USES binds code owned elsewhere, grants no primary credit and must be reached by native conformance.

- `OUTPUTS = {"answer": ("lent", "refused")}` declares a finite tuple per output field. A producing step really writes each value; merely declaring or initializing it is not a production trace. Declare OUTPUTS only for a real receiver.
- `HANDOFF = {"lending": {"answer": "answer"}}` receives every current producer value unchanged into State.answer. The string is field-name shorthand, not a saved list of values. Full form: `{"answer": ("decision", {"lent": "yes", "refused": "no"})}`. A consumer outside the producer's parent may map an unused value to None. A composing parent must receive every value and never drops one.
- `READS_PARENT = ("request",)` names fields the child takes; they exist in both State types and the parent supplies them. An explicit parent-state projection declares the same reads by its field accesses. Independent replay fixtures need not run another model first to obtain a start.
- `KEEPS = ("request", "phase", "reply")` is the coarse parent's own input, forward step marker and aggregate. Every other parent field is supplied to a child or receives its output. Don't keep the child's domain state or copy its decision table into the parent.
- `DISPATCH = {"mode": {"show": "read_show", "find": "read_find"}}` chooses exclusive branch children. Every reached choice has its PARENT-linked child. A call receives only its chosen branch's answer; a call refused before dispatch keeps the selector's default and runs no branch. Required stages can coexist with one chosen branch.

Receive an actual event: a step's input, label or output contains the original producer value and that step holds the mapped value in the named receiving field. A value placed somewhere else in State, emitted in another call or computed without receiving it does not satisfy HANDOFF. Use literal reads/writes on blocks; the runtime checks actual changed fields, output values and receipt traces. Parent rules judge order, conditions, choice and aggregation. Their case tables contain only received child OUTPUTS; conformance calls the parent's real composing function and compares its own result, never re-explores or re-renders children.

Different aspects and shared mechanisms stay component models. A command consuming a check is not its parent: declare HANDOFF in the command, OUTPUTS in the check. Child code belongs exclusively to the composing function. `COMPONENTS` gives allowed code scope, while PARENT determines placement; widening scope grants no duplicate ownership.

Changing an interface prints `port changed`: include the named parent, HANDOFF consumer or child-input reader in the same target and make it receive/supply the new value. A new dispatch choice needs its branch rather than an upward escalation. See [Interface change](routes.md#interface-change) and [Split a model](routes.md#split-a-model).
