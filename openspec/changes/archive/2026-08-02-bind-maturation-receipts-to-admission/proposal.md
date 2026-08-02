## Why

FlowGuard currently lets downstream admission and confidence gates accept a freely constructed maturation object whose `current` flag is caller-controlled. The same immutable, independently verified maturation result must govern implementation admission, broad confidence, and final closure.

## What Changes

- Add a content-addressed ModelMaturation receipt projection over FlowGuard's canonical evidence receipt store.
- Make currentness, identity binding, terminal decision, confidence, and open gaps verifier-derived rather than caller-declared.
- **BREAKING**: Remove raw mapping coercion and direct `ModelMaturationEvidenceRef` authority from implementation admission, RiskLedger, and ClosureContract normal paths.
- Keep sufficiency and permission separate: maturation answers whether the model is deep enough; DevelopmentProcessFlow answers whether the requested implementation may start.
- Make RiskLedger the sole final broad-confidence owner and reduce ClosureContract to identity/material consistency and terminal-integrity checking.

## Capabilities

### New Capabilities

- `model-maturation-receipt`: Publishes and independently verifies an immutable receipt for one exact task, demand, candidate, input, evidence set, and maturation decision.

### Modified Capabilities

- `flowguard-evidence-receipts`: Supports a specialized maturation receipt projection without creating a parallel receipt authority.
- `development-process-flow`: Admits implementation only from a verified maturation receipt plus independent authorization.
- `risk-evidence-ledger`: Owns the final broad/scoped/blocked confidence decision using the same verified maturation result.
- `flowguard-closure-contract`: Checks shared identity, material consistency, and terminal integrity without recomputing sufficiency or broad confidence.
- `model-maturation-loop`: Publishes its terminal result through the canonical maturation receipt boundary.

## Impact

This changes public types and downstream gate inputs in `model_maturation`, `evidence_receipts`, `development_process_flow`, `risk_evidence_ledger`, and `closure_contract`, plus CLI examples, API registry entries, models, and tests. Existing raw-dictionary admission is intentionally not retained.
