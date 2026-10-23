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

Selectors are `MODEL_ID` for top-level contract files and the containing directory id for
registered `run_checks.py`; component ids are for `read --component`. Unknown selectors fail.
Every selected model executes on every call (no result cache). A model without anchors or
without conformance fails as "abstract boundary only".
A model of code that does not exist yet is a target model: write it under `.flowguard/target/models/` (SKILL.md, target first).

`TESTED_BY = {"invariant_name": ["tests/test_x.py:test_name"]}` binds model rules
to real test anchors in both directions. Missing or renamed tests fail `map check`; keys must
be actual design invariants. `NOT_MODELED = {"path.py:Symbol": "reason"}` records an explicit
unmodeled entry; it grants no implementation proof. Each implementation anchor must be called, or its
file read as code facts (`flowguard.map.facts.CodeFacts`), during exploration or conformance; a bad
variant must violate the intended design's property. `map lint` warns when a model names no tests.

Run: `python -m flowguard map models <MODEL_ID>`. Copy `assets/model_template.py` to start.
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
- **UI journey**: state = screen + form data; inputs = user actions (submit, cancel, back, retry);
  invariants: every non-terminal screen has an action, cancel always reaches a stable screen, an
  error screen offers recovery; `require_reachable` for the success screen.
- **Permissions**: inputs carry a role; invariant: a forbidden role never reaches the protected
  effect; broken variant = check placed after the effect.

## When a green model missed a bug

A model passed, then a test, a run or a user hit a bug in the same behavior. Make the owning
model reject the escaped case and keep one real regression test:

1. Reproduce the failure; keep its evidence (failing test node id, log line, steps).
2. `python -m flowguard map impact <file under the failure>` names the owning component and its
   model. No model covers the behavior: write one (Five steps above).
3. Classify the miss: an input the model lacks (timeout, empty list, second click), state too
   coarse to tell the cases apart, an invariant too weak to see the bad state, or a conformance
   adapter that maps the real code wrongly.
4. Start the target flow in SKILL.md, then `python -m flowguard target add <id>`. In `.flowguard/target/models/`, add the missing input or state, or strengthen the invariant; add the escaped behavior as a broken variant (`broken_variants()`) that must FAIL. Recurring miss: add one sibling case of the same class.
5. Run `python -m flowguard target check`: the intended design passes, every broken variant fails, and code/test TO-DO stays visible.
6. Add or update one regression test and list it in the owner's target `tests`; fix the code until target check is clean, then `python -m flowguard target promote`. Confirm its listed components, run `python -m flowguard change` and the tests and models it lists.

## Grow a model

Use this when `change` names a model in REVIEW, reports `model_writer_unbound`, or a task adds behavior to an already modeled component.

1. **Reuse** when existing invariants already cover the new behavior: add its real tests to `TESTED_BY`.
2. **Extend** for a new input or rule over the same state: add inputs, state fields or invariants to the existing model, plus a known-bad variant that violates the new rule.
3. **Add a child** for an independent operation over the same state: write a child model and import its blocks into the parent; imports infer the parent.
4. **New model** for a different boundary and state: follow Five steps above.
5. Do the change as a target (`python -m flowguard target add <id>`, after target start in SKILL.md): bind new code in `IMPLEMENTED_BY`, cover it in `conformance()`, check until clean and promote. Then run `python -m flowguard change` and its listed models; importers and ancestors are selected too.

## Split a model

Apply this split through SKILL.md's target-first flow.

1. Move shared `State`, inputs, invariants and adapter into `_<name>_common.py`; underscore helpers are not models, and editing one reruns its importers.
2. Give each operation a child model with its own blocks, anchors, known-bad variants and replay.
3. Import child blocks into the parent with `Workflow((SetBlock(), DelBlock()), mode="choice")`; each declares `accepted_input_type`, so no pass-through steps are needed.
4. A child that slices parent state declares `project_parent_state(state)` (`return state` when reusing the parent's `State`) and starts from `flowguard.kit.reachable_states(parent.build_explorer(), project_parent_state)`; `map models` warns with `child_start_gap` when it misses parent states. An independent sub-check grouped under a parent needs neither projection nor reachable-state starts.
In this split, the parent imports its children. A child that imports its parent (for `reachable_states`) must import it inside a function; a top-level import is circular.

5. Lift the children's known-bad variants into the parent too, prefixing their names to avoid collisions.
6. Run `python -m flowguard target check` until clean, then `python -m flowguard target promote` and confirm its listed components. Run `python -m flowguard map models` so the now-current parent and children pass, then inspect their subtree with `python -m flowguard read --component <id>`.

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
need a new adapter. Report model-level confidence when no runtime replay was needed.

## Capability models (kits and runners)

`python -m flowguard template field-lifecycle | contract-exhaustion | ui-flow-structure | code-structure |
behavior-commitment --write .` writes one contract model built from a kit (`flowguard.kit`: `feature_explorer`, `plan_explorer`;
code facts or replay as conformance). A feature model lists `Feature(name, rejects, codes, apply)` rows:
each changes a clean input (a defect the code must reject and report, or a benign variation); the kit
explores each allowed feature set once (up to `max_features=2` by default), generates the known-bad variants (`feature_variants`) and, in
`feature_conformance(features, base, review)`, runs each combination on the real code and prints a
counterexample (features, expected and observed verdict) for each one that disagrees. `codes="all"` reports all defects;
use `codes="first"` for a validator that stops at the first defect in declaration order. `requires=("other",)`
requires another feature in the set; `conflicts=("other",)` forbids their combination, symmetrically.
`exclusive=True` still excludes every other feature. Impossible requirements and unknown names are errors. Invariants without a reachable nonempty witness
are omitted; conformance still checks the clean base against the design, including adapter errors. Every capability
template writes one top-level `.flowguard/models/<name>.py` kit contract model. The behavior-commitment
model also retains its canonical auxiliary ledger. Existing user-written runners remain accepted;
a runner declares `IMPLEMENTED_BY` (and `TESTED_BY`) at top level and follows the same anchor rule.
Template code and test anchors contain `REPLACE_ME`
and fail until you name your code and tests. Components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only for placement. User-written runners remain registered through the component `models` field. Run
`python -m flowguard map models <name>`: exit code 0 means the intended plan passes and the
broken plans are rejected. A runner should print one line per case, return a non-zero exit code
when any case disagrees with its expectation, and end with `raise SystemExit(run_owner(main))`
(`from flowguard.map.runner import run_owner`); a `main()` that returns `None` is reported as an error.

## Helpers

- `minimize_failing_sequence(...)` (flowguard.minimize): shrink a failing input sequence.
- `mermaid_code_block(...)` / `loop_report_to_mermaid_text(...)`: render a model/report;
  see examples/mermaid_export_example.py.


### Parent and child models

`PARENT` may name a component, another model's `MODEL_ID`, or `"system"`.
`parent_unknown`, `parent_cycle`, `parent_import_mismatch`, `child_outside_parent` and
`duplicate_child_owner` are errors; `test_not_nested` and `child_start_gap` remain warnings.
Without it, the parent is the unique importing contract model, then `COMPONENTS[0]`,
the first anchor's owner, a runner's first listed component, or `system`.
Prefer a parent model importing its child's blocks to compose their behavior.
FlowGuard adds `.flowguard/models` to `sys.path`; sibling imports need no path edits.
Prefix helper files with `_` so they are not registered as executable models.

`PARENT = "system"` places a cross-component model directly under the built-in system root.
The root lives in the map, not in a user model file; its reserved id is `system`.

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
Non-Python test bindings and design-only models are warned about, not executed.
Checking Python bindings requires pytest in the environment (`.[dev]` provides it).
