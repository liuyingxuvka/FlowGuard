# Model-Test Transition Protocol

Load this file when a task contains state transitions, transition cells,
retry/repair loops, parent-child traces, or ModelMesh closure obligations.

## Transition Matrix

For each `(input class, source state)` cell, record allowed next states,
outputs, observable side effects, rejection behavior, and current evidence.
Preserve nondeterministic alternatives instead of forcing one expected result.

Each required transition needs:

- one model obligation and stable behavior-plane identity;
- one primary external `CodeContract` owner;
- positive or happy-path evidence;
- each protected failure-path and negative-path case;
- replay evidence when ordering, retry, idempotency, or recovery matters;
- a visible disposition for unreachable or intentionally scoped cells.

## System Trace Binding

For bounded system properties preserve:

`property -> definition/request/slice -> interaction case -> mapped system trace step -> component transition -> optional code/runtime target -> current regression evidence`

Code/runtime targets remain provenance until currentness is independently
proved. Component-local success cannot replace the mapped system trace.

## ModelMesh Closure

`model_mesh_closure_to_transition_coverage` must bind the closure model's
repeat-input tokens, repair feedback, blocker tokens, no-delta termination,
and same-packet behavior to happy-path, failure-path, negative-path, and replay
tests. A missing row remains open maturation work.

## Completion

Every transition cell is covered, explicitly unreachable with evidence, or
delegated to one typed owner. No blank cell and no locally green subset may
support a whole-transition claim.
