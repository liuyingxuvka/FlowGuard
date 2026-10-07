---
name: flowguard
description: FlowGuard's single public entry for behavior and state modeling, lifecycle checks, and evidence-aware release boundaries.
---

# FlowGuard

FlowGuard is one public skill using an explicit finite model.
Domain references load on demand, never wholesale.

## Fixed public lifecycle

Only `read`, `change`, and `release` are public.

- `read` consumes accepted current and selected references: zero producers/writes.
- `change` freezes affected obligations, runs their native owners and accepts
  once through compare-and-swap.
- `release` checks declared scope, reuses exact evidence, fills missing artifact
  obligations and verifies the projection.

Use the real root and one request. Missing/ambiguous/foreign/stale/contradictory
inputs block; never guess a root, subject, command or profile.

## Model-purpose gate

Freeze each instance's task-specific failure(s), candidate, finite boundary and
native good/bad-per-failure/oracle/current evidence before claiming sufficiency.
Reusable model types are not permanently single-purpose.
Only FlowGuard-declared checks may support completion claims.
No mode/fallback path is available. Ordinary `change` runs
selected protected-failure checks and derived structure coverage; per-element
good/bad/draft evidence belongs only to explicit reduction or candidate comparison.

## Read only what is selected

Start with `references/route_index.md` and the required accepted model/index.
Load the selected `references/domains/<subject>/protocol.md` and named dependencies;
Model changes: `references/modeling_core_protocol.md`.

Read the functional map's current structure, admitted target, original gaps, real action locations
and unknown scope together. Start with required responsibilities/related contexts;
expand for named missing inputs/obligations. No arbitrary cost ceiling closes
understanding; no scoped pass proves whole-software optimality.
Bind finite add/modify/delete/rename observations to the task; absent growth stays
`NOT_OBSERVED`. Consume its verified result or original diagnostic's gap/input/owner.
Diagnostic and read
success cannot close the task: require current verified maturation, every
requested outcome and no required open gap. Share one invocation's cached reads;
retain the independent final input/head/index guard. Fetch exact pointer details
on demand; never invent locations/owners.

## Hard boundaries

- Preserve `unknown`, `blocked`, `not-run`, `skipped`, stale, and failed.
- Bind owners to real implementation/oracle/inputs/environment/evidence.
- Reuse exact functional identity; parent summaries/install receipts are not
  leaf business proof.
- Read never refreshes. Change/release stop on drift, CAS conflict, missing
  owners, cleanup failure or incomplete evidence.
- Installation, parity, Git, tags, and publication are separate claims.

## Result

Report operation/status, required/run/reuse counts, blockers, evidence locations,
claim boundary, residual risk and typed next actions. Keep the default result bounded;
put details at the explicit evidence location. Never truncate checks.
