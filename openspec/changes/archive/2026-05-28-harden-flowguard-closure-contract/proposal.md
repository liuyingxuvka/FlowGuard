## Why

FlowGuard already has the right building blocks for high-confidence AI-agent
work, but broad "done", release, or production-confidence claims can still be
overstated when runtime traces, evidence freshness, model quality, model-miss
closure, runtime gateway adoption, and risk-ledger support are reviewed as
separate tools. This change makes the existing closure contract executable so a
missing, stale, too-coarse, or bypassed gate blocks full confidence instead of
silently becoming a green claim.

## What Changes

- Add an executable FlowGuard Closure Contract review that consumes existing
  FlowGuard evidence instead of introducing a parallel process.
- Require runtime traces to map back to declared model obligations before they
  can support production confidence.
- Require artifact changes to invalidate dependent model, test, gateway, code
  boundary, or ledger evidence when declared freshness rules apply.
- Add model quality signals for hidden state, missing side effects, owner
  ambiguity, helper-only proof, missing public boundary, and parent/child
  evidence gaps.
- Require in-scope runtime/model misses to include observed failure evidence and
  same-class closure evidence before broad confidence is restored.
- Strengthen runtime gateway adoption claims by making writer inventory source,
  coverage evidence, and path-owner conflicts visible to the closure review.
- Require Risk Evidence Ledger support before a full confidence decision.

## Capabilities

### New Capabilities

- `flowguard-closure-contract`: executable full-confidence closure review for
  FlowGuard claims, grounded in existing trace, freshness, model-quality,
  model-miss, runtime gateway, and risk-ledger evidence.

### Modified Capabilities

None. The change introduces a closure review that consumes existing freshness
evidence rather than changing the model-impact freshness gate requirements.

## Impact

- Adds a public Python review helper and template material.
- Updates public API exports, docs, and tests.
- Does not add runtime dependencies.
- Does not replace existing FlowGuard routes; it coordinates their current
  evidence for final confidence.
