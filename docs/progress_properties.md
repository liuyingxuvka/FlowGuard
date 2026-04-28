# Progress Properties

Phase 13 adds pragmatic progress checks on top of the Phase 10 loop checker.

The Phase 10 loop checker detects closed bottom strongly connected components,
stuck states, unreachable success, and terminal states with outgoing edges.
That catches designs such as:

```text
maybe -> rewrite -> maybe
```

when the cycle has no escape to a terminal state.

Phase 13 handles the common harder case:

```text
maybe -> done
maybe -> rewrite
rewrite -> maybe
```

The graph has an escape edge to `done`, so it is not a bottom SCC. However,
the model still allows a path that keeps choosing rewrite forever. `flowguard`
now reports this as:

- `potential_nontermination`
- `missing_progress_guarantee`

unless the model supplies a ranking function or bounded progress property that
shows forced progress.

## Checks

- `ProgressCheckConfig` describes a finite reachable graph, terminal states,
  optional success states, optional ranking function, and optional eventually
  properties.
- `check_progress()` builds the reachable graph and reports actionable progress
  findings.
- `BoundedEventuallyProperty` checks that a trigger state can reach a target
  state within a finite number of graph steps.
- Ranking functions can show that a cycle makes monotonic progress, such as
  decreasing remaining retries or remaining rewrites.

This is still not a complete temporal-logic or liveness proof. It is a
deterministic bounded engineering check that makes missing progress guarantees
visible before production code is changed.
