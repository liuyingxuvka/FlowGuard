## Context

FlowGuard currently has two different kinds of long-running checks:

- `Explorer` enumerates finite input sequences and reports bounded ten-step
  progress on `stderr`.
- Graph helpers such as loop and progress checks build a reachable graph in
  memory before reviewing it.

The progress output solves observability, but not weight. A model with millions
of reachable states can still require a large in-memory graph or repeated full
reruns. The new capability must make the run physically smaller by processing a
bounded shard at a time and recording enough ledger state to continue later.

## Goals / Non-Goals

**Goals:**

- Let callers run large graph-style models in shards, defaulting to 10,000
  processed states per shard.
- Persist a model-group ledger so a later run continues pending states instead
  of recomputing already processed states.
- Keep progress meaningful at two levels: shard-local ten-step progress and
  model-group completion status.
- Make stale proof reuse difficult by fingerprinting the model inputs and
  configuration.
- Return a structured report that clearly distinguishes complete, incomplete,
  and failed model-group evidence.

**Non-Goals:**

- Do not replace `Explorer` or change its existing progress contract.
- Do not add a lightweight substitute model path. If the large model is only
  partially processed, the report must say it is incomplete.
- Do not require a new third-party dependency.
- Do not promise full loop/SCC or temporal-progress proof for unfinished model
  groups; those checks still require complete reachable evidence.

## Decisions

1. Add a new helper API rather than changing `Explorer`.
   - Rationale: the heavy FlowPilot cases are graph-style checks, while
     `Explorer` is input-sequence based. Keeping the APIs separate avoids
     breaking existing model scripts.
   - Alternative considered: make `Explorer` internally shard all work. That
     would not solve the graph-check memory problem and would alter existing
     behavior.

2. Use a small SQLite ledger in the run directory.
   - Rationale: SQLite is in the Python standard library, handles large pending
     queues better than repeatedly rewriting JSON files, and lets FlowGuard
     deduplicate state ids without keeping the full graph in memory.
   - Alternative considered: JSONL only. It is simpler, but less practical for
     millions of pending states.

3. Require caller-provided state encoding for durable resume.
   - Rationale: FlowGuard can deterministically export arbitrary states for
     reporting, but reconstructing arbitrary Python objects is model-specific.
     Callers that want resume must provide `encode_state` and `decode_state`.
   - Alternative considered: infer dataclass reconstruction automatically. That
     is fragile across nested objects and model code changes.

4. Fingerprint the model group before choosing a ledger directory.
   - Rationale: if the model, required labels, invariants, budget, or caller
     supplied fingerprint parts change, old results must not be silently reused.
   - Alternative considered: always reuse a fixed model-name directory. That
     risks mixing stale evidence with a changed model.

5. Treat "queue still has pending states" as incomplete, not OK.
   - Rationale: a shard finishing only means that shard's budget was exhausted.
     The model group is only complete when the pending queue is empty and all
     global requirements have been checked.
   - Alternative considered: return OK for each passing shard. That recreates
     the user's current concern: progress visibility without whole-model proof.

## Risks / Trade-offs

- [Risk] Callers without state encoders can run one shard but cannot resume
  after process exit. -> Mitigation: validate this at configuration time when a
  persistent run directory is used, and document the encoder requirement.
- [Risk] SQLite ledger files can grow large. -> Mitigation: store compact state
  ids and encoded state payloads, cap per-shard processing, and avoid storing
  full edge lists by default.
- [Risk] A complete global SCC/progress proof still needs a complete reachable
  graph. -> Mitigation: report budgeted model-group completeness separately and
  keep existing full graph helpers available for models that fit in memory.
- [Risk] A bad `state_id` function can merge distinct states. -> Mitigation:
  document that state ids must be stable and unique for the model abstraction,
  and test duplicate-prevention behavior.

## Migration Plan

1. Add the new budgeted graph/model-group API and tests.
2. Add an example and documentation that show how FlowPilot-style models can use
   the API.
3. Keep existing APIs compatible.
4. Bump the package version and release the change as a minor version.

Rollback is straightforward: callers can keep using existing `Explorer`, loop,
and progress helpers. No existing data format is changed.

## Open Questions

- None for the first implementation. Future work can add complete-graph export
  hooks for downstream SCC/progress checks after the budgeted run finishes.
