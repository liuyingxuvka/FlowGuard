## Why

FlowGuard can execute many individual models, but it cannot yet answer one
authoritative project-level question: which exact model system describes the
software that exists now? Current, proposed, and experimental models can share
the same registry and evidence vocabulary, so a locally green candidate can be
mistaken for the observed software model and a multi-model change cannot be
accepted or rolled back as one unit.

## What Changes

- Add one immutable, content-addressed model-system snapshot format with
  explicit `observed_implementation`, `normative_target`, and
  `counterfactual_experiment` subject lanes.
- Add one project-owned compare-and-swap pointer to the sole observed
  implementation head. Target and experiment snapshots never become current by
  declaration.
- Replace mutable `:current` model-instance naming with exact model, runner,
  purpose, source-revision, and resolved-input identities.
- Add a finite, fingerprinted coverage universe and require full-coverage claims
  to prove set equality across external surfaces, commitments, model instances,
  fields and side effects, code contracts, tests, and evidence.
- Generalize the existing task-local revision lifecycle into an atomic
  multi-model revision set. Every affected model, relation, commitment, field,
  contract, and test closes together or none of them is promoted.
- Separate pre-code candidate rejection, target withdrawal, and post-deployment
  operational rollback. A post-deployment rollback must restore or compensate
  implementation effects and revalidate the old observed snapshot before the
  authority pointer moves.
- Make Existing Model Preflight resolve the observed head first, reject stale or
  retired owners, and report candidate models only as non-authoritative context.
- Connect Behavior Commitment Ledger, Field Lifecycle Mesh, Model-Test
  Alignment, TestMesh, and DevelopmentProcessFlow through typed snapshot
  references while preserving each existing owner's responsibility.
- Contract proven duplicate control surfaces and obsolete compatibility
  discovery without merging semantically distinct FlowGuard owners.
- Update the installed FlowGuard skill suite so AI guidance always reports the
  observed snapshot, selected owners, candidate snapshot, affected closure,
  unresolved gaps, and bounded claim language.
- **BREAKING**: project-level current-model authority is no longer inferred from
  a registry label, file presence, lexical match, or a model id ending in
  `:current`.

## Capabilities

### New Capabilities

- `authoritative-model-system`: Immutable project model-system snapshots,
  subject lanes, exact model-instance identities, typed relations, finite
  coverage universes, and the sole observed-head pointer.
- `model-revision-set`: Atomic multi-model candidate construction, validation,
  activation, rejection, target withdrawal, and evidence-backed operational
  rollback.

### Modified Capabilities

- `hierarchical-model-mesh`: Persist and review an actual project snapshot,
  affected closure, parent/child joins, and typed cross-model relations.
- `existing-model-preflight`: Select the current observed snapshot first and
  stop treating file discovery or ledger presence as current evidence.
- `behavior-commitment-ledger`: Bind active commitments to exact observed model
  instances and exclude replaced or retired commitments from primary lookup.
- `field-lifecycle-mesh`: Bind field and side-effect inventories to the same
  revision set and prevent partial field replacement.
- `model-test-alignment`: Compare obligations and evidence against exact
  snapshot identities and report unresolved closure members.
- `test-evidence-mesh`: Bind test evidence to resolved source inputs and the
  observed or candidate snapshot it actually validates.
- `development-process-flow`: Own ordering, freshness, compare-and-swap
  activation, rollback gates, installation synchronization, and release
  closure for model-system revisions.
- `architecture-reduction`: Contract only proof-ready duplicate authorities,
  compatibility discovery, and helper control surfaces while preserving public
  observable behavior.
- `structure-refactor-mesh`: Split oversized modules behind one canonical
  facade with dependency and parity evidence.
- `project-adoption-version-gate`: Audit source, project record, installed
  package, installed skills, observed snapshot, Git commit, tag, and release as
  distinct identities.
- `flowguard-codex-skill-satellites`: Teach current/target/experiment
  separation, revision-set replacement, bounded coverage, and rollback in the
  existing FlowGuard routes.

## Impact

The change affects the FlowGuard Python model mesh, task-local revision
lifecycle, regression manifest and receipts, project adoption records, selected
self-maintenance models, CLI/API exports, tests, OpenSpec reconciliation,
author-side skill sources, consumer skill installation, package versioning, and
release evidence. Existing public model and skill entrypoints remain facades;
obsolete alternate success paths are removed after parity evidence.
