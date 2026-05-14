# Budgeted Model Groups

Budgeted model groups are for graph-style FlowGuard models that are too large
to run comfortably as one in-memory graph. They do not make a smaller substitute
model. They run the same model in bounded pieces and keep a ledger so the next
piece continues where the previous one stopped.

Plainly:

- a shard is one small work package, defaulting to 10,000 processed states;
- the model group is the whole large model across all shards;
- shard progress reaching 100% only means that shard finished;
- the whole model group is complete only when the pending queue is empty;
- if pending states remain, the report is `incomplete`, not `ok`.

## When To Use

Use `BudgetedGraphConfig` and `run_budgeted_graph_checks()` when a model is
naturally expressed as reachable states and transitions:

```text
state -> labeled edges -> next states
```

This fits large meta/capability checks, planner state graphs, queue/retry
graphs, and other FlowGuard models where the next states are generated from the
current state.

Keep using `Explorer` for finite input-sequence workflows:

```text
initial_state x input_sequence -> trace
```

`Explorer` still emits ten-step progress, but that progress is only visibility.
It does not shard a graph model or reduce graph memory use.

## The Ledger

Each model group gets a run directory:

```text
.flowguard/budgeted-model-groups/<model-name>/<fingerprint>/
```

Inside that directory FlowGuard writes a SQLite ledger with:

- `seen` states, so duplicate states are not reprocessed;
- `pending` states, so the next run can continue;
- `processed` states, so old work is not repeated;
- observed labels and failure samples;
- one summary row per shard.

The fingerprint includes the model name, initial state ids, shard budget,
required labels, invariants, FlowGuard schema version, and caller-supplied
fingerprint parts or files. If the model changes, use `fingerprint_parts` or
`fingerprint_files` so the new run gets a separate ledger.

## Minimal Example

```python
from flowguard import BudgetedGraphConfig, run_budgeted_graph_checks


def next_states(state: int):
    if state < 50_000:
        return (("advance", state + 1),)
    return ()


config = BudgetedGraphConfig(
    model_name="large-counter",
    initial_states=(0,),
    transition_fn=next_states,
    budget_per_shard=10_000,
    required_labels=("advance",),
    fingerprint_parts=("large-counter-v1",),
)

report = run_budgeted_graph_checks(config)
print(report.format_text())
```

The first call processes at most 10,000 states. If the graph is not exhausted,
the report status is `incomplete`. Running the same call again resumes from the
pending queue recorded in the ledger.

## Custom State Objects

For dataclasses or other custom states, provide stable state encoding and
decoding:

```python
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelState:
    phase: str
    depth: int


def encode_state(state: ModelState):
    return asdict(state)


def decode_state(payload):
    return ModelState(**payload)


def state_id(state: ModelState) -> str:
    return f"{state.phase}:{state.depth}"
```

The `state_id` must be stable and unique for the abstraction. If two different
states share one id, FlowGuard records a state-id collision failure.

## Progress Output

Budgeted model groups write progress to `stderr`:

```text
[flowguard-budget] start model=large-counter shard=1 budget=10000 processed_total=0 pending=1
[flowguard-budget] progress model=large-counter shard=1 10% work=1000/10000 total_processed=1000 pending=1
[flowguard-budget] shard_end model=large-counter shard=1 status=incomplete processed=10000/10000 total_processed=10000 pending=1
```

This keeps the old idea of 10%/20% progress, but gives it the right meaning:
the percentage is for the current shard, while `total_processed` and `pending`
describe the whole model group.

Use `progress_steps=0` or `FLOWGUARD_PROGRESS=0` for silent runs.

## Result Meaning

- `complete`: all pending states were exhausted and no failures remain.
- `incomplete`: the current shard finished but pending states remain.
- `failed`: an invariant, transition, decode, edge, state-id, or required-label
  failure was found.

`ok` is true only for a complete model group with no failures and no missing
required labels.
