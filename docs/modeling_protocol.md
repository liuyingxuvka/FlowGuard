# Modeling Protocol

Use this protocol before implementing non-trivial behavior or modifying a
stateful workflow.

## 1. Identify External Inputs

List the inputs that enter the workflow from outside the modeled system.
Examples: a job posting, a webhook event, a retry request, a file, a queued
task, a user action, or a cache refresh request.

## 2. Identify Abstract Finite State

Model only the state needed to expose workflow risk. Use immutable, hashable
objects such as frozen dataclasses, tuples, or frozensets.

Good abstract state usually records source records, cache entries, attempts,
side effects, decisions, terminal records, and ownership markers.

## 3. Identify Function Blocks

Split the workflow into named function blocks. Each block should correspond to
one behavioral boundary, such as scoring, recording, routing, validation,
cache lookup, persistence, retry, or decisioning.

Represent each block as:

```text
Input x State -> Set(Output x State)
```

If a block can produce multiple valid outcomes, enumerate all of them.

## 4. Calibrate Model Fidelity

Treat the model as a falsifiable simulator of the real workflow, not as ground
truth. Before trusting model findings, compare representative traces with real
code paths, logs, tests, user workflows, or production conformance evidence when
available.

Choose the smallest model that is faithful enough for the current risk. Include
details that could affect the bug class under review:

- control-flow branches and terminal paths;
- state reads, writes, and ownership;
- retries, queues, waiting states, and reprocessing;
- cache and deduplication behavior;
- exceptions, rejected inputs, and dead branches;
- side effects that must not duplicate or silently disappear.

If a trace is impossible, suspicious, or misses known production behavior,
revise the model, scenario oracle, or replay adapter first, then rerun the
checks. Do not report model-level confidence as production confidence until
conformance evidence supports it.

## 5. Define Reads, Writes, and Ownership

For every block, write down:

- state it reads;
- state it writes;
- state it must not write;
- the module or owner responsible for that state.

This catches wrong state owner bugs that final-state invariants can miss.

## 6. Define Idempotency

For repeated input, define what should happen on the second and third pass.
Examples:

- a duplicate record should return `already_exists`;
- a cached score should not add a second score attempt;
- a retry should reuse an idempotency key;
- a completed task should not be completed again.

## 7. Define Failure Modes

Model expected failures as possible outputs or structured dead branches. Do not
hide exceptions or silently skip branches.

## 8. Define Invariants

Hard invariants should be executable. Common examples:

- no duplicate records;
- no repeated scoring without refresh;
- every downstream object has a source;
- no contradictory final decisions;
- cache matches source of truth;
- only one owner writes a state slot;
- downstream blocks can consume upstream outputs.

## 9. Run Explorer

Run deterministic exhaustive exploration over a finite input set and sequence
bound. Include repeated input sequences when duplicate side effects are
possible.

## 10. Add Scenario Sandbox

For important hand-designed cases, write a `Scenario` with a human oracle:

- expected status;
- expected violation names;
- required trace labels;
- forbidden trace labels;
- scenario-specific oracle checks when needed.

Expected violations in broken models are successful review outcomes when
FlowGuard observes the intended violation.

## 11. Add Loop and Progress Checks

For retry, refresh, queue, waiting, rewrite, or reprocessing flows, build a
reachable state graph and check:

- stuck states;
- bottom SCCs without terminal/success;
- unreachable success;
- terminal states with outgoing edges;
- potential non-termination when a cycle has an escape edge but no forced
  progress guarantee.

## 12. Add Conformance Replay

After production code exists, export representative abstract traces and replay
them through an adapter. The adapter should expose observed output and a
projection of real state. Projection must not hide bugs such as duplicate raw
side effects.

## 13. Revise Before Production Edits

If the model finds a counterexample, revise the model or architecture before
editing production code. Do not weaken hard invariants merely to pass checks.
