# Writing a FlowGuard model

A model is a Python file in `.flowguard/models/` with this contract:

```python
MODEL_ID = "order_placement"                                  # unique id, also used on the command line
COMPONENTS = ["orders"]                                       # map components this model protects
IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}   # block -> real code (checked by `check`)
def build_explorer(): ...     # REQUIRED: Explorer of the intended design; must pass
def broken_variants(): ...    # REQUIRED in practice: {name: Explorer}; each must FAIL (proves the invariants have teeth)
def conformance(): ...        # STRONGLY RECOMMENDED: replay model traces against the real code; .ok must be True
```

Selectors are `MODEL_ID` for top-level contract files and the containing directory id for
registered `run_checks.py`; component ids are for `read --component`. Unknown selectors fail.
Every selected model executes on every call (no result cache). Missing conformance means only
the abstract boundary was checked.

Optional `TESTED_BY = {"invariant_name": ["tests/test_x.py:test_name"]}` binds model rules
to real test anchors in both directions. Missing or renamed tests fail `map check`; keys must
be actual design invariants. `NOT_MODELED = {"path.py:Symbol": "reason"}` records an explicit
unmodeled entry; it grants no implementation proof. Declared implementation anchors must run
during exploration or conformance; a bad variant must violate the intended design's property.

Run: `python -m flowguard map models <MODEL_ID>`. Copy `assets/model_template.py` to start.

## Five steps

1. Name the failure you protect against in one sentence ("a retry charges the card twice").
2. Inputs: a small finite set of abstract events (2-5), including the repeat/retry/out-of-order one.
3. State: a frozen dataclass with only the facts that affect future behavior or the invariant.
4. Blocks: classes with `apply(input, state)` returning `FunctionResult(output, new_state, label=...)`
   for every possible branch (return more than one result for nondeterministic outcomes).
   Never call network, clock, random or databases inside a model.
5. Invariants that must hold in every reachable state, one broken variant per protected
   failure, and a conformance adapter.

Keep `max_sequence_length` at 2-5. If exploration is slow, shrink inputs or state, or use
`flowguard.budgeted` for large graphs.

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

Packs bundle invariants and scenarios: `RetryPack`, `DeduplicationPack`, `CachePack`, `SideEffectPack`.

## Recipes

- **Retry / idempotency**: inputs `Request(id)` with repeated ids; state holds processed ids and
  effects; invariant `at_most_once_by` on effects; broken variant = handler without the "already
  processed" branch.
- **Cache freshness**: inputs `Write(key, v)`, `Read(key)`, `Invalidate(key)`; state holds source and
  cache; invariant: a read never returns a value different from the source after the write was
  acknowledged; broken variant = write that does not invalidate.
- **Multi-step workflow / state machine**: one block per step, a `phase` field in state; invariants
  with `require_label_order`; use `flowguard.loop.check_loops` to find stuck states.
- **UI journey**: state = screen + form data; inputs = user actions (submit, cancel, back, retry);
  invariants: every non-terminal screen has an action, cancel always reaches a stable screen, an
  error screen offers recovery; `require_reachable` for the success screen.
- **Permissions**: inputs carry a role; invariant: a forbidden role never reaches the protected
  effect; broken variant = check placed after the effect.

## Conformance (model <-> code)

When the changed contract depends on order, repeated inputs, state or side effects,
write an adapter with `reset(initial_state)`, `apply_step(step) -> ReplayObservation`,
`observe_state()`, `observe_output()`. It calls the real code for `step.function_input` and
projects the real state into the model's `State`. Replay only the traces that cover every
modeled transition:

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
need a new adapter. Report model-level confidence when no runtime replay was needed.

## Model runners (capability models)

Capability reviews (UI flow, model mesh, contract exhaustion, ...) are usually checked by a runner:
`python -m flowguard template <name> --write .` writes `.flowguard/models/owners/<name>/model.py`
and `.flowguard/verification/owners/<name>/run_checks.py`. Edit the model for your project, list
the runner (`.../run_checks.py`) in the owning component's `models`, and run
`python -m flowguard map models <name>`: exit code 0 means the intended plan passes and the
broken plans are rejected. A runner should print one line per case and end with a non-zero exit
when any case disagrees with its expectation.

## Helpers

- `minimize_failing_sequence(...)` (flowguard.minimize): shrink a failing input sequence.
- `audit_model(...)` with `RiskProfile` (flowguard.audit): list gaps for the declared risks.
- `mermaid_code_block(...)` / `loop_report_to_mermaid_text(...)`: render a model/report;
  see examples/mermaid_export_example.py.
