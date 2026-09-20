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

- `read` reads the accepted current model and the selected subject's domain
  references. It does not create, mutate, execute, accept, install, or publish.
- `change` observes the explicit root and request, freezes the affected
  obligations, runs only the required native owners, and accepts through the
  current compare-and-swap boundary.
- `release` checks the declared release scope, reuses exact valid evidence,
  fills only missing artifact obligations, and verifies the actual release
  projection. It does not mean that every business proof is regenerated.

Use the real repository root and one request file. A missing, ambiguous,
foreign, stale, or contradictory input is a typed blocker; never guess a root,
select a heavier route, or fall back to an old command/profile.

## Model-purpose gate

For every concrete instance, freeze task-specific failure(s), the candidate,
and native good/bad-per-failure/oracle/current evidence before claiming model
sufficiency. Reusable model types are not permanently single-purpose: the
instance declares its finite boundary and protected failures. Only FlowGuard-declared checks may support completion claims. No mode/fallback path is
available.

## Read only what is selected

Start with `references/route_index.md` and the accepted model/index required by
the request. After a subject is selected, load only the matching domain file
and its explicitly named dependencies. The selected domain path is
`references/domains/<subject>/`. The domain folders under the references
directory preserve protocol detail; they are reference documents, not
additional public entrypoints.

## Hard boundaries

- Preserve `unknown`, `blocked`, `not-run`, `skipped`, stale, and failed states.
- Bind each required owner to its real implementation, oracle, input bytes,
  environment, and evidence identity.
- Reuse only an exact functional identity. A parent summary is not leaf proof,
  and an installation receipt is not business evidence.
- Read never refreshes current state. Change and release stop on source drift,
  CAS conflict, missing owners, failed cleanup, or incomplete evidence.
- Installation, consumer parity, Git, tags, and GitHub publication are
  separate claims; none is implied by a green model check.

## Result

Report the operation, status, required/run/reuse counts, blockers, evidence
locations, claim boundary, residual risk, and typed next actions. Keep the
default result bounded; write full details to the explicit evidence location.
The default JSON is a transport summary, not a truncated substitute for the
underlying checks.
