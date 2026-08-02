## Context

FlowGuard already has an immutable `EvidenceReceipt` store and independent verifier. Model maturation instead exposes a freely constructible evidence reference, and three downstream gates accept it or a raw mapping. The result is structurally descriptive but not authoritative.

## Goals / Non-Goals

**Goals:**

- Reuse the canonical receipt authority for maturation.
- Make downstream decisions consume one independently verified projection.
- Separate model sufficiency, implementation permission, broad confidence, and terminal integrity.

**Non-Goals:**

- Providing cryptographic protection against a malicious writer with filesystem control.
- Keeping raw mapping compatibility in the normal path.
- Making ClosureContract another risk or sufficiency engine.

## Decisions

### Build a typed projection over EvidenceReceipt

`ModelMaturationReceiptRef` contains only the canonical receipt id and content fingerprint. Publication converts one terminal maturation report into an `EvidenceReceipt` whose subject, snapshots, covered obligations, result, and typed metadata bind the exact task, demand, candidate, inputs, evidence, decision, confidence, and gaps.

A specialized verifier first calls the canonical receipt verifier, then validates the maturation metadata and returns a frozen `VerifiedModelMaturation` projection. No authoritative `current` input exists.

### Downstream APIs require the verified projection

DevelopmentProcessFlow, RiskLedger, and ClosureContract accept `VerifiedModelMaturation` only. This makes the verification boundary explicit and removes mapping coercion. Test helpers must produce a real canonical receipt and verify it.

### Keep four decisions separate

ModelMaturation owns `closed` versus `blocked` sufficiency. DevelopmentProcessFlow combines verified sufficiency with current user/work authorization and returns `ready`, `ready_scoped`, `no_code_requested`, or `blocked`. RiskLedger owns final `full`, `scoped`, or `blocked` confidence. ClosureContract verifies shared fingerprints, material presence, and terminal agreement, then preserves the RiskLedger decision.

### Bind authorization to evidence

Implementation authorization carries the exact task identity, allowed action/scope, provenance reference, content fingerprint, and explicit presence/expiry state. It cannot upgrade maturation and is checked separately.

## Risks / Trade-offs

- [API break for direct constructors] → Update all in-repository callers atomically and provide a clear error; do not retain dual authority.
- [Receipt metadata drifts from report] → Centralize publication and verify every duplicated identity against subject/snapshot fields.
- [Closure still recomputes confidence accidentally] → Remove confidence scoring inputs from closure and assert equality with the RiskLedger result.

## Migration Plan

1. Add specialized receipt model and canonical-verifier tests.
2. Update the three consumers in dependency order: DevelopmentProcessFlow, RiskLedger, ClosureContract.
3. Remove raw mapping coercion and direct evidence-reference authority.
4. Update models, API registry, docs, and all tests in the same change.
5. Roll back by reverting the complete atomic commit, not by enabling a compatibility reader.
