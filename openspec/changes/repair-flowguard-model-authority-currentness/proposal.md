## Why

FlowGuard v0.65.1 is the current source/tag/release, but recent adoption evidence records model authority as invalid or blocked. Model-miss diagnostics cannot be validated against a model system whose observed head is not current.

## What Changes

- Audit the existing model-authority store and repair the sole observed head without rewriting historical snapshots.
- Run current model-system and project audits against exact v0.65.1 source/toolchain identities.
- Publish a behavior-neutral patch baseline before extending model-miss evidence.

## Capabilities

### New Capabilities

- `flowguard-model-authority-currentness`: Defines observed-head integrity, snapshot/current-source parity, and repair evidence for the FlowGuard repository itself.

## Impact

Affected surfaces: model-authority store/snapshots, adoption records, currentness tests, README/changelog/version, and release evidence.
