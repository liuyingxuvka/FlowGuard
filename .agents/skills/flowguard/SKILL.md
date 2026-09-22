---
name: flowguard
description: FlowGuard's single public entry for behavior and state modeling, lifecycle checks, and evidence-aware release boundaries.
---

# FlowGuard

FlowGuard is one public skill. Use it when behavior, state, ownership, or a
cross-route boundary needs an explicit finite model. Domain protocols remain
available as on-demand material in the references domain tree; they are not
independent skills and must not be loaded wholesale.

## Fixed public lifecycle

The only public operations are `read`, `change`, and `release`.

- `read` reads the accepted current and selected domain references; it never
  creates, mutates, executes, accepts, installs, or publishes.
- `change` freezes the requested affected obligations, runs only their native
  owners, and accepts once through the compare-and-swap boundary.
- `release` checks its declared scope, reuses exact evidence, fills missing
  artifact obligations, and verifies the release projection.

Use the real repository root and one request file. A missing, ambiguous,
foreign, stale, or contradictory input is a typed blocker; never guess a root,
select another subject, or fall back to an old command or profile.

## Model-purpose gate

For every concrete instance, freeze task-specific failure(s), the candidate,
and native good/bad-per-failure/oracle/current evidence before claiming
sufficiency. Reusable model types are not permanently single-purpose: each
instance declares its finite boundary and failures. Only FlowGuard-declared checks may support completion claims. No mode/fallback path is available. An
ordinary `change` runs selected protected-failure checks and derived structure
coverage; per-element good, bad, or draft evidence is only for an explicit
reduction or candidate comparison. `read` creates no evidence and missing
inputs block with zero producers and writes.

## Read only what is selected

Start with `references/route_index.md` and the accepted model/index required by
the request. After a subject is selected, load only its concrete
`references/domains/<subject>/protocol.md` and explicitly named dependencies.
The domain folders preserve protocol detail; they are reference documents, not
additional public entrypoints.

## Hard boundaries

- Preserve `unknown`, `blocked`, `not-run`, `skipped`, stale, and failed.
- Bind each owner to its real implementation, oracle, input, environment, and
  evidence identity.
- Reuse only exact functional identity; parent summaries and install receipts
  are not leaf business proof.
- Read never refreshes. Change/release stop on drift, CAS conflict, missing
  owners, cleanup failure, or incomplete evidence.
- Installation, parity, Git, tags, and publication are separate claims.

## Result

Report the operation, status, required/run/reuse counts, blockers, evidence
locations, claim boundary, residual risk, and typed next actions. Keep the
default result bounded; write full details to the explicit evidence location.
The default JSON is a transport summary, not a truncated substitute for the
underlying checks.
