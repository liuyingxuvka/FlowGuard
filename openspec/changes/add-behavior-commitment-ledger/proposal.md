## Why

FlowGuard already has model ownership, coverage evidence, risk gates, and the
new Primary Path Authority rule for rejecting fallback success paths. Those
pieces still start from local work units: a model, a route, a field, a runtime
path, or a test gate. That leaves one upstream gap: an agent can modify or
validate a local path while never stating the complete set of user-visible
behaviors the project promises to cover.

That gap is exactly where long-lived maintenance debt enters. If an AI does
not know the full behavior inventory, it may add a helper branch, compatibility
surface, backup read, or alternate implementation and call the local change
safe. The path may pass locally while the product now has duplicated,
overlapping, or extra behavior that no single owner can maintain.

This change adds a project-level Behavior Commitment Ledger. The ledger is the
full account book of external behavioral promises. Each commitment has one
primary owner model, explicit source evidence, explicit dependencies, explicit
test/evidence bindings, and a current disposition. When a commitment is
path-sensitive, the ledger must hand it to Primary Path Authority rather than
letting the ledger invent another fallback-path checker.

## What Changes

- Add a `behavior-commitment-ledger` capability, public API, template, docs,
  and agent skill.
- Require full-scope FlowGuard adoption, broad planning, release, publish,
  archive, or done confidence to account for all in-scope external behavior
  commitments.
- Define a behavior commitment as a user/API/CLI/UI/skill/workflow observable
  promise, not as every helper function, file, internal model, or button.
- Require every commitment to name exactly one primary owner model and only
  supporting or child models after that owner is selected.
- Require each commitment to trace to at least one source surface, and require
  each in-scope source surface to map back to one or more commitments.
- Reject missing behavior, extra behavior, overlapping owners, unknown
  dependencies, and scoped-out behavior without owner, reason, validation
  boundary, and rationale.
- Connect the ledger to Primary Path Authority: every `path_sensitive=true`
  commitment must carry PPA evidence, and a blocked PPA result blocks the
  commitment and any broad claim that depends on it.
- Expose commitment-level coverage ids so ContractExhaustionMesh, TestMesh,
  Model-Test Alignment, RiskEvidenceLedger, and DevelopmentProcessFlow consume
  the same boundary.
- Add Cartesian coverage over commitment class, source surface, owner model,
  evidence state, path-sensitivity, PPA result, dependency state, and release
  gate outcome.

## Capabilities

### New Capabilities
- `behavior-commitment-ledger`: Maintains the full behavior account book for a
  project or work package; checks commitment completeness, source coverage,
  owner-model uniqueness, dependency closure, scoped-out disposition, evidence
  freshness, and PPA handoff for path-sensitive commitments.

### Modified Capabilities
- `model-first-function-flow`: Models prove behavior commitments; they are not
  themselves the complete behavior inventory unless the commitment is a simple
  leaf.
- `existing-model-preflight`: Reuse-first lookup must identify the affected
  commitment, primary owner model, and sibling commitments before non-trivial
  planning or changes.
- `development-process-flow`: Broad staged-work claims must include current
  behavior ledger coverage and must route path-sensitive commitments through
  PPA before done/release/publish confidence.
- `primary-path-authority`: PPA becomes the downstream path authority for
  `path_sensitive=true` behavior commitments and reports results back to the
  ledger.
- `risk-evidence-ledger`: Adds a behavior-commitment coverage gate and treats
  missing or blocked ledger/PPA evidence as release-blocking for broad claims.
- `contract-exhaustion-mesh`: Adds a canonical commitment-coverage universe
  for no-missing, no-extra, no-overlap, dependency, evidence, and PPA
  combinations.
- `test-evidence-mesh`: Child suites can own commitment coverage shards, but
  the parent gate must reconcile all required commitment case ids.
- `model-test-alignment`: Tests and model obligations must bind back to
  commitment ids rather than only local model ids when the claim is behavioral.
- `flowguard-ui-flow-structure`: UI-visible capabilities must map to ledger
  commitments and avoid duplicate screen/control ownership.
- `flowguard-codex-skill-satellites`: Agent-facing prompts must register and
  review behavior commitments by default for non-trivial FlowGuard work.

## Impact

- Adds a core ledger module, public exports, template text, documentation,
  OpenSpec artifacts, and tests.
- Adds a new FlowGuard skill for behavior commitment ledger creation and
  review, then wires existing skills to it.
- Updates RiskEvidenceLedger and DevelopmentProcessFlow with a
  behavior-commitment gate.
- Connects ledger rows to the existing Primary Path Authority module and test
  suite without duplicating PPA logic.
- Requires installed skill synchronization, local package verification,
  shadow-workspace synchronization, OpenSpec validation, and focused regression
  tests before release confidence.
