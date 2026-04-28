# Loop and Stuck-State Detection

Phase 10 adds a small deterministic graph checker for workflow designs that can loop, get stuck, or never reach a required success state.

It does not use random testing, Hypothesis, Monte Carlo, or external graph libraries.

## Reachable State Graph

A loop check starts from finite `initial_states` and a transition function:

```python
transition_fn(state) -> iterable[GraphEdge]
```

Each `GraphEdge` records:

- `old_state`
- `new_state`
- `label`
- `reason`
- optional metadata

The graph builder explores all reachable states up to optional `max_states` or `max_depth` bounds.

Important: the transition function should be raw. It should return outgoing edges even for terminal states. Terminal classification happens after graph construction so the checker can detect terminal states that still have outgoing transitions.

## Stuck State

A stuck state is reachable, not terminal, and has no outgoing edges.

This catches designs such as:

```text
new -> maybe
maybe -> no transition
```

If `maybe` is not terminal, the workflow is stuck.

## Strongly Connected Components

An SCC is a group of states where every state can reach every other state in the group.

Example:

```text
maybe -> rewrite
rewrite -> maybe
```

`maybe` and `rewrite` form one SCC.

FlowGuard implements Tarjan's SCC algorithm using only the Python standard library.

## Bottom SCC

A bottom SCC has no outgoing edge to a state outside the SCC.

If a reachable bottom SCC contains no terminal state and no success state, the model can remain there forever. This is reported as a non-terminating component.

Examples caught by bottom SCC detection:

- `maybe -> rewrite -> maybe`
- `error -> retry -> error`
- `waiting -> waiting`
- `cached -> refresh_requested -> invalidated -> cached`

## Unreachable Success

If `required_success=True`, the checker verifies that at least one reachable state satisfies `is_success`.

This catches workflows where the only terminal is `ignored`, but the required success is `applied`.

## Terminal With Outgoing Edges

If a terminal state still has outgoing edges, the checker reports `terminal_with_outgoing_edges`.

This catches unclear termination semantics:

```text
new -> done
done -> maybe
```

## What Bottom SCC Detection Can Catch

It can catch closed loops with no escape:

```text
rewrite <-> maybe
retry <-> error
waiting -> waiting
```

It can also catch dead non-terminal states and unreachable required success states.

## What It Cannot Prove Yet

Cycles with escape edges are harder:

```text
maybe -> done
maybe -> rewrite
rewrite -> maybe
```

There is a path to `done`, but there is also a path that can keep cycling. A bottom-SCC-only checker will not flag this as a closed non-terminating component because the SCC has an outgoing edge to `done`.

This needs future fairness or progress modeling, such as:

- every retry must increase a counter;
- every rewrite must eventually hit a limit;
- every loop edge must decrease a ranking function;
- branch selection must eventually choose an escape edge.

In Phase 10, L13 and L14 are deliberately marked `known_limitation` rather than falsely passed or falsely failed.

## Example Review

Run:

```powershell
python examples/looping_workflow/run_loop_review.py
```

The review includes:

- good bounded rewrite;
- infinite rewrite loop;
- bounded retry;
- retry without limit;
- waiting self-loop;
- nonterminal dead state;
- human-review terminal;
- terminal with outgoing edge;
- unreachable success;
- refresh/invalidate cycle;
- known limitations for cycles with escape edges.
