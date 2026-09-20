# Model Topology Hazard Review Protocol

Use this route when a locally green FlowGuard model's shape may imply future-use
risk. Start from topology, not a fixed checklist.

## Trigger

Create or update a review when:

- broad done/release/publish/archive/production/full-confidence claims rely on
  a model that proved only local paths;
- the topology contains repeatable side effects, shared state writers, external
  confirmation boundaries, broad terminal states, old/new compatibility paths,
  migration/history surfaces, duplicate or conflicting business paths,
  unproven important business paths, or parent/child compression;
- model and ordinary tests pass but future real use may expose more;
- state-closure, model-test alignment, model maturation, process freshness, or
  risk ledger evidence points to a hidden model-shape hazard.

Do not trigger this route for generic risk brainstorming with no model topology.
Unanchored concerns stay as observations and cannot block confidence.

## Input Checklist

Use grouped rows, not blank field lists:

- usage intent: local/CLI/library/plugin/service/release/migration, final claim,
  history/compatibility possibility and policy, and goal;
- topology digest: state nodes, input nodes, block nodes, workflow edges,
  reads/writes, side effects, external boundaries, terminal nodes, old/new
  paths, business path identities, parent/child links, and landmark ids;
- business path identities: stable path id, business intent, trigger,
  preconditions, expected terminal, state writes, side effects, equivalent
  paths, exclusive paths, superseded old paths, compatibility disposition,
  source labels, and evidence ids;
- candidate hazards: anchor ids, topology rationale, future failure, affected
  state/edge/effect/terminal/boundary, disposition, required routes,
  handled/scoped status, and proof ids.

## Review Rules

Every hard hazard names a concrete state, edge, side-effect edge,
terminal/success node, compatibility/business path, external boundary, shared
writer, or parent/child compression landmark.

Classify dispositions:

- model patch or maturation when the model is too coarse;
- model-test alignment when a model obligation lacks ordinary test evidence;
- Risk Evidence Ledger when broad user-risk confidence depends on the hazard;
- DevelopmentProcessFlow when local evidence is being overclaimed as release or
  process confidence;
- Architecture Reduction plus ledger when old/new compatibility paths need a
  preserve, migrate, block, delete, or latest-schema-first decision;
- Architecture Reduction with exact CanonicalRelation evidence when two
  business paths do the same useful job;
- Model Maturation plus Model-Test Alignment when business paths conflict or
  lack path-specific evidence;
- scoped out only with a concrete reason.
Scoped or unresolved anchored hazards become maintenance obligations so
DevelopmentProcessFlow can reopen the affected owner when its model,
entrypoint, or artifact changes.

## Prompt Template

Use `references/templates/topology_hazard_prompt_template.md` only to scaffold
a fresh AI review; ordinary use follows this checklist and public helper APIs.

## Completion Standard

A topology hazard review can support broad confidence only when:

- unanchored hard candidates have been downgraded to observation-only;
- each anchored unresolved hazard has an owner route or is handled/scoped with
  current evidence;
- scoped anchored hazards are exported as maintenance obligations when they can
  affect later work;
- compatibility/history surfaces have an explicit disposition;
- duplicate, conflicting, or unproven business paths have owner routes or
  current evidence;
- repeatable side effects and external boundaries are covered by current
  model-test, process, or risk-ledger evidence when broad usage is possible;
- scoped confidence is carried into the final Risk Evidence Ledger instead of
  being described as a clean pass.

## Portable temporal topology

For `flowguard.portable_model.v1`, use portable state and transition ids as the
topology anchors. Universal eventuality is blocked by a reachable
target-avoiding dead end or cycle. Bounded eventuality also retains an
over-bound path. Weak fairness may exclude a cyclic schedule only when the
declared fair transition group is continuously enabled across that component
and taking any declared fair transition leaves it. The review consumes the
canonical checker report for the exact model fingerprint; it never converts
descriptive route metadata into an executable fairness pass.

Topology-anchored cross-model event, retry-identity, shared-writer/resource,
commit/emit/ack atomicity, cache-authority, external-confirmation, or finite
delivery hazards may seed bounded interactions. Each seed names exact
model/transition/binding/resource/property anchors and a property owner already
resolved by BCL or Existing Model Preflight, else emits `owner_missing`.
Topology review neither appoints owners nor calls unexecuted seeds findings.
