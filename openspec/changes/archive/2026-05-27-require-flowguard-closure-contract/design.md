## Context

FlowGuard already has the concrete route pieces: Existing Model Preflight,
Model-Miss Review, Model-Test Alignment, TestMesh, ModelMesh, Layered Boundary
Proof, DevelopmentProcessFlow, Risk Evidence Ledger, plan-intake helpers, and
typed claim-chain helpers. The gap is semantic and operational: users and
agents can still describe a run as "using FlowGuard" after only a subset of
the gates pass.

The user clarified that this must not be framed as an added default mode. The
closure chain is part of FlowGuard's definition. A partial model, partial test,
or partial ledger pass is useful evidence, but it is not a complete FlowGuard
use claim.

## Goals / Non-Goals

**Goals:**

- Make the closure contract visible in public docs, skill guidance, and release
  evidence.
- Preserve the small entry path while making completion claims stricter.
- Add executable local model evidence that rejects completion without closure.
- Keep the change mostly in documentation, skill guidance, and local model
  checks so it does not collide with peer agents editing core helper APIs.
- Sync installed skills, editable package install, shadow workspace, and source
  version surfaces.

**Non-Goals:**

- Do not add a new broad satellite skill or make helper APIs into skills.
- Do not claim FlowGuard proves arbitrary real-world software has no bugs.
- Do not require ordinary small exploratory models to run internal framework
  benchmark suites.
- Do not overwrite or revert peer-agent source changes.

## Decisions

### Closure Contract Is Intrinsic

The wording will say that complete FlowGuard use requires the closure contract.
It will not say "optional mode" or "default mode." When a task stops before
claim review, the report should say which partial FlowGuard evidence exists and
which closure gate remains missing.

Alternative considered: add a named "zero-bug mode." That keeps the feature
optional and conflicts with the user's requirement, so it is rejected.

### Thin Path Remains An Entry Path

The existing thin path stays because it is useful for adoption and small risk
boundaries. The wording changes from "default completion path" to "entry path":
start small, then escalate only when the claim needs broader closure evidence.

Alternative considered: remove the thin path. That would overburden small
tasks and contradict the public minimal product shape.

### Reuse Existing Gates

The contract composes existing routes instead of adding another monolithic
skill. The mandatory gates are plan/risk intake, existing-model ownership,
model repair or model creation, same-class bad-case evidence, model/test/code
alignment, mesh or boundary proof when required, evidence freshness, Risk
Evidence Ledger, and typed claim-chain review.

Alternative considered: add a new package API that reruns every route. That
would create duplicate ownership and likely overclaim automation that still
depends on project-specific adapters.

### Release Sync Stays Explicit

This change touches public guidance and installed skills, so completion must
verify source, installed skill copies, editable install, shadow workspace, and
visible version metadata. A source git checkout may remain dirty because peer
agents are active, but this change's files must be synchronized and reported
separately.

## Risks / Trade-offs

- **Over-triggering small work** -> Keep the thin entry path and scope closure
  gates to completion/full-confidence claims.
- **False "no bugs" interpretation** -> State that FlowGuard blocks unsupported
  green claims; it cannot certify arbitrary unmodeled behavior.
- **Peer-agent collisions** -> Avoid core helper files currently modified by
  other agents; synchronize only the files owned by this change.
- **Stale install surfaces** -> Verify installed skill hashes or quick
  validation plus editable install version after copying.
