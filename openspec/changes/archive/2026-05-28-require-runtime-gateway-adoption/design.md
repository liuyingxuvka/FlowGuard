## Overview

This change adds a small review helper that answers one question:

> Has the target project actually routed all critical runtime state writes
> through FlowGuard-backed gateways, or is FlowGuard only being used as a model
> and after-the-fact checker?

The helper does not intercept writes itself. A target project such as FlowPilot
must implement its own transaction gateway. FlowGuard provides the declaration
and review layer that makes incomplete adoption visible.

## Adoption Levels

FlowGuard adoption is classified into three levels:

- `design_model`: the project has a model, but no claim that tests or runtime
  code are bound to it.
- `test_aligned`: model obligations and test or code-boundary evidence are
  aligned, but critical runtime state writes can still bypass a gateway.
- `runtime_gateway`: every declared critical state surface has a gateway owner,
  every known write path is inventoried, and every current critical write
  observation is mediated by the declared gateway with current step, boundary,
  replay, and proof evidence.

The new helper blocks `runtime_gateway` when evidence is incomplete. It does
not make lower levels invalid; it prevents lower-level evidence from being
reported as runtime protection.

## Data Model

`RuntimeStateSurface` names a critical state surface such as a ledger, database
table, JSON state file, status projection, or side-effect register.

`RuntimeGatewayContract` names the gateway responsible for one or more state
surfaces and declares whether atomic commit, replay observation, step-contract
binding, code-boundary binding, and proof artifacts are required.

`RuntimeWriteObservation` records a known write path from source audit,
instrumented tests, replay, or runtime logs. It records the target surface,
whether the write went through a gateway, the gateway id, step contract ids,
code-boundary ids, proof artifact ids, result status, and whether the
observation is current.

`RuntimeGatewayAdoptionPlan` joins the surfaces, gateways, observations, and
inventory evidence into a single review.

`review_runtime_gateway_adoption(...)` returns a structured report. Error
findings block green runtime-gateway adoption. Warning findings stay visible
for lower-level or migration claims.

## Review Rules

For `runtime_gateway` claims, the review blocks when:

- no complete writer inventory evidence is supplied;
- a critical state surface has no declared gateway owner;
- a gateway owner referenced by a surface does not exist;
- a gateway does not declare atomic commit or replay observation when required;
- a current critical write observation is direct, missing a gateway id, or
  declares a legacy bypass;
- a write observation goes through a gateway that does not manage the target
  surface;
- a gateway-mediated write lacks required step contract ids, code-boundary ids,
  or proof artifact ids;
- a writer observation is stale, skipped, failed, timeout, running, not-run, or
  otherwise non-passing.

For lower adoption levels, the report may stay OK while still listing warnings
that the project has not proved runtime protection.

## Non-Goals

- Do not rewrite FlowGuard core modeling semantics.
- Do not make every FlowGuard model require runtime-gateway adoption.
- Do not scan arbitrary source code perfectly. Source scanning can feed
  observations into this helper, but complete inventory remains a project
  evidence obligation.
- Do not implement FlowPilot's transaction gateway inside FlowGuard.

## Validation

Focused unit tests cover:

- design-only adoption remains valid without a runtime gateway;
- runtime-gateway adoption passes with complete inventory, managed surfaces,
  gateway-mediated write observations, and required evidence ids;
- missing inventory, unmanaged surfaces, direct writes, stale writes, gateway
  surface mismatch, missing step/code/proof evidence, and declared legacy
  bypasses block runtime-gateway adoption;
- public API exports expose the new helper without moving it into the core API.
