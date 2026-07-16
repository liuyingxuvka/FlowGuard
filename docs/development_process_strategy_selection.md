# Conditional Development-Process Optimization

Process optimization is a small internal capability of
`development_process_flow`. It is not a new route or skill, and ordinary work
does not have to fill in an optimization form.

The short rule is:

> First prove that two routes owe the same result, evidence, safety, side
> effects, dependencies, and owner authority. Only then prefer the route that
> current evidence suggests will cause less repeated work.

## When It Activates

Optimization activates only when at least one stable reason exists:

- `explicit_request`: the user explicitly asks for a better process;
- `multiple_equivalent_routes`: two or more routes appear to achieve the same
  contract;
- `material_rework_risk`: the current order is likely to repeat diagnosis,
  edits, validation, or coordination;
- `diagnostic_boundary_choice`: deciding how far to diagnose before repair is
  itself important.

With none of these reasons, the result is `not_needed`: no candidates, cost
records, repair groups, or optimization evidence are required.

## The Two Decisions

The old mixed strategy menu is reduced to two independent questions.

First choose the diagnostic boundary:

- `targeted`: inspect the most informative affected area;
- `declared_complete`: inspect every item in a named finite boundary;
- `budgeted`: inspect until a named time, cost, or side-effect limit.

Then choose the execution mode:

- `sequential`: run checks in dependency order;
- `safe_parallel`: run isolated checks together only when dependency, mutable
  state, side effects, and execution ownership are all proven independent.

Two rules do not need to become selectable strategies:

- a hard blocker always stops work whose result would be invalid or unsafe;
- material new evidence always makes an old decision stale.

## The Original Test-and-Repair Example

If several related tests are cheap and valid to run, a
`declared_complete` or `budgeted` diagnostic pass may expose a shared root
cause before any code is changed. Related findings can then be repaired as one
group and all affected obligations revalidated once.

That is not a command to run every test. If a prerequisite is missing, a
database migration makes later tests misleading, or a safety failure makes
continuation dangerous, the hard blocker stops the run and the remaining work
is recorded as not run. If only one subsystem is relevant, `targeted` is the
smaller valid boundary.

## Repair Groups

Raw findings keep their stable Finding Ledger ids. Several findings may enter
one repair group only when current relation evidence supports a shared root
cause. Each group names:

- the finding ids and relation evidence;
- a falsifiable root-cause claim and disproof checks;
- affected obligations and repair actions;
- the ordinary primary owner evidence;
- required and current affected revalidation evidence.

The group remains open while any affected revalidation is missing. Mere
co-occurrence in one test run is not relation evidence.

## Owner Boundaries

- DevelopmentProcessFlow owns activation, ordering, freshness, and the final
  process claim.
- TestMesh owns the diagnostic boundary, planned/executed/failed/not-run
  counts, not-run reasons, and finding references.
- Finding Ledger owns raw finding identity and source evidence.
- SpecWorkPackage owns provider dependency graphs and immutable receipts.
- Model-Test Alignment owns ordinary obligation, primary code owner, and test
  evidence closure.
- PlanDetail carries only the plan-level activation reasons and current
  decision-evidence id; it does not copy the decision into every step.

## Claim Boundary

Estimated or qualitative evidence may justify a preferred route. The word
`minimum` is allowed only for measured costs over a named, exhausted finite
candidate set. FlowGuard never claims a global workflow optimum, and the
maintained examples prove only the declared failure families.
