## Why

The self-understanding closure change establishes the required behavior, but the existing implementation still carries duplicate route registries, duplicate owner-evidence entry, route-specific Closure re-scoring, and raw-count mesh activation. These implementation residues increase drift risk without adding observable capability.

## What Changes

- Derive admission and coverage projections from the canonical public-owner descriptors.
- Make task-coverage and maturation consume projections of one canonical owner resolution.
- Reduce Closure to a thin consumer of current receipt, admission, and risk decisions.
- Remove raw model-count activation and its unsupported public residues after lifecycle and facade evidence is complete.
- Preserve the externally supported behavior and status/serialization contracts established by `close-flowguard-self-understanding-loop`.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- None. This is a behavior-preserving implementation contraction governed by the requirements in `close-flowguard-self-understanding-loop` and existing main specs.

## Impact

The change affects internal route projections, task-coverage/maturation adapters, Closure composition, hierarchical mesh activation plumbing, public-facade lifecycle evidence, focused parity tests, and implementation documentation. It adds no route, skill, fallback, compatibility reader, or externally new behavior.
