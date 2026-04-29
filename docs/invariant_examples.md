# Invariant Examples

Invariants are executable rules over reachable states and traces. They should be small, concrete, and tied to the failure mode that matters.

FlowGuard also provides standard property factories in `flowguard.checks` for
common patterns. They are optional helpers, not a larger modeling framework:
use them when the names match the bug class, and keep custom invariants when a
domain rule is clearer.

## No Duplicate Records

Use when a workflow persists records, events, applications, scores, or decisions.

Intent:

```text
For every reachable state, each persisted id appears at most once.
```

Example:

```python
def no_duplicate_records(state, trace):
    return len(state.record_ids) == len(set(state.record_ids))
```

Helper:

```python
from flowguard import no_duplicate_by

no_duplicate_records = no_duplicate_by(
    name="no_duplicate_records",
    description="records are unique by job_id",
    selector=lambda state: state.records,
    key=lambda record: record.job_id,
    value_name="record",
)
```

This catches missing deduplication and non-idempotent retries.

## No Repeated Scoring Without Refresh

Use when scoring, ranking, classification, or matching should happen once unless a refresh input exists.

Intent:

```text
For every reachable state, each job_id appears in score_attempts at most once.
```

Example:

```python
def no_repeated_scoring_without_refresh(state, trace):
    return len(state.score_attempts) == len(set(state.score_attempts))
```

Helper:

```python
from flowguard import at_most_once_by

score_once = at_most_once_by(
    name="score_once",
    description="each job is scored at most once without refresh",
    selector=lambda state: state.score_attempts,
    key=lambda attempt: attempt.job_id,
    value_name="score_attempt",
)
```

This catches blocks that ignore score cache and recompute on repeated input.

## Every Downstream Object Has Source Traceability

Use when downstream objects must be derived from upstream validated or scored objects.

Intent:

```text
Every persisted or decided object can be traced to a prior source object in state or trace.
```

Example:

```python
def every_record_has_source_score(state, trace):
    scored = {entry.job_id for entry in state.score_cache}
    return all(job_id in scored for job_id in state.application_records)
```

Helper:

```python
from flowguard import all_items_have_source

records_have_scores = all_items_have_source(
    name="records_have_scores",
    description="every application record has a source score",
    item_selector=lambda state: state.application_records,
    source_selector=lambda state: state.score_cache,
    item_key=lambda record: record.job_id,
    source_key=lambda score: score.job_id,
    item_name="application_record",
    source_name="score",
)
```

This catches persistence from raw input or missing upstream state.

## No Contradictory Final Decisions

Use when the same object cannot receive mutually exclusive outcomes.

Intent:

```text
No job has both apply and ignore decisions.
```

Example:

```python
def no_contradictory_final_decisions(state, trace):
    actions_by_job = {}
    for decision in state.decisions:
        actions_by_job.setdefault(decision.job_id, set()).add(decision.action)
    return all(
        not {"apply", "ignore"}.issubset(actions)
        for actions in actions_by_job.values()
    )
```

Helper:

```python
from flowguard import no_contradictory_values

no_apply_and_ignore = no_contradictory_values(
    name="no_apply_and_ignore",
    description="same job cannot be both applied and ignored",
    selector=lambda state: state.decisions,
    key=lambda decision: decision.job_id,
    value=lambda decision: decision.action,
    forbidden_pairs=(("apply", "ignore"),),
    key_name="job_id",
    value_name="decision",
)
```

This catches branches that make incompatible decisions across repeated inputs.

## Cache Consistency

Use when state contains both cached derived data and source-of-truth records.

Intent:

```text
Cache entries and source records must not disagree about the same object.
```

Example:

```python
def cache_matches_source_of_truth(state, trace):
    source = dict(state.source_scores)
    return all(source.get(job_id) == score for job_id, score in state.score_cache)
```

Helper:

```python
from flowguard import cache_matches_source

cache_consistent = cache_matches_source(
    name="cache_consistent",
    description="score cache agrees with source scores",
    cache_selector=lambda state: state.score_cache,
    source_selector=lambda state: state.source_scores,
    key=lambda score: score.job_id,
    value=lambda score: score.value,
)
```

This catches stale cache writes and hidden alternate scoring paths.

## Exactly One State Owner

Use when only one function block should write a given state field.

Intent:

```text
Only the owning block writes each protected state field.
```

Example:

```python
def only_record_block_writes_records(state, trace):
    return all(
        step.function_name == "RecordScoredJob"
        for step in trace.steps
        if step.old_state.application_records != step.new_state.application_records
    )
```

Helper:

```python
from flowguard import only_named_block_writes

only_record_block_writes_records = only_named_block_writes(
    field_name="application_records",
    owner_function_name="RecordScoredJob",
)
```

This catches state mutation from the wrong module.

## Label Ordering

Use when one observable step must happen before another, or when a terminal
decision should prevent a later side effect.

Helpers:

```python
from flowguard import forbid_label_after, require_label_order

validated_before_record = require_label_order("validated", "record_added")
no_ship_after_cancel = forbid_label_after("cancelled", "shipped")
```

These helpers inspect `trace.steps`. They are ordinary invariants, so they
describe all explored traces rather than proving anything about production code
without conformance evidence.

## Idempotent Record Operation

Use when recording the same object twice should not create a second side effect.

Intent:

```text
Repeating the same recordable object leaves at most one persisted record.
```

Example:

```python
def record_operation_is_idempotent(state, trace):
    return len(state.application_records) == len(set(state.application_records))
```

This catches append-only broken record blocks.

## No Hidden Second Source Of Truth

Use when a workflow has one authoritative state field and other fields are derived.

Intent:

```text
No block should derive decisions from a shadow copy that can diverge from the authoritative state.
```

Example:

```python
def decisions_use_record_state(state, trace):
    recorded = set(state.application_records)
    return all(
        decision.action in {"ignore"} or decision.job_id in recorded
        for decision in state.decisions
    )
```

This catches duplicated state ownership and divergent caches.

## No Output That Downstream Cannot Consume

Use when a composed workflow must pass each block output to the next block.

Intent:

```text
The report has no non-consumable branch unless explicitly modeled as terminal.
```

Example check:

```python
report = explorer.explore()
assert not report.dead_branches
```

This catches output type drift, missing adapters, and incomplete workflow composition.
