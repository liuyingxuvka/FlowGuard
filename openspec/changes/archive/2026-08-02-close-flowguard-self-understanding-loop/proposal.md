## Why

FlowGuard already has task coverage, model maturation, receipt, admission, risk, and closure components, but an AI can still omit task facts, route identities can drift, and one owner result can be represented twice. The framework therefore cannot yet produce a current, independently verifiable answer to “how deeply is this exact task understood?” or prove that the whole current FlowGuard has completed that path.

## What Changes

- Derive task facts from independent request, current-model, public-surface, and lifecycle observations, preserving unknown, omitted, contradictory, and scoped facts instead of trusting a caller-selected denominator.
- Replace independently maintained route-admission and coverage-owner identities with one canonical public-owner descriptor projection; retired identities are rejected rather than aliased or repaired at runtime.
- Introduce one owner-resolution value that projects to both TaskCoverageDemand display and ModelMaturation input so the same professional result cannot drift across two submissions.
- Add a read-only understanding-status API/CLI projection that reports understanding sufficiency, implementation admission, and user execution choice separately without executing owners or publishing evidence.
- Remove raw model-count activation from ModelMesh and require semantic dispositions and current consumer edges for every model participating in a whole-flow claim.
- Distinguish pre-code contract/test design from post-code executed evidence and bind the model-to-structure recommendation to the exact maturation/admission identity.
- Run one exact current whole-FlowGuard self-understanding task through demand, owner resolution, maturation, canonical receipt, independent verification, admission, risk, and closure.
- Update only the affected FlowGuard skill prompts/contracts, then rebuild and verify the clean consumer projection and local installation under SkillGuard author supervision.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `task-coverage-demand`: Compiles independently sourced, provenance-bound facts and preserves unknown, omitted, contradictory, and unmapped facts in the minimum denominator.
- `flowguard-route-topology-governance`: Projects admission, owner, coverage, documentation, and contract identities from one canonical public-owner declaration.
- `model-maturation-loop`: Consumes one canonical owner resolution per demanded owner instead of a separately re-entered contribution.
- `model-maturation-receipt`: Supports a read-only current-status projection without creating or upgrading maturation authority.
- `flowguard-ai-entry-simplification`: Reports understanding sufficiency, FlowGuard implementation admission, and user choice as independent results while preserving lightweight use.
- `existing-model-preflight`: Emits provenance-bound task-fact observations and unresolved/unmapped surfaces without claiming task sufficiency.
- `hierarchical-model-mesh`: Uses affected semantic topology only and requires a disposition for every model in a whole-flow claim.
- `model-test-alignment`: Separates pre-code obligation/oracle readiness from executed implementation evidence.
- `development-process-flow`: Preserves direct-user-choice and no-code outcomes without upgrading the verified maturation decision.
- `flowguard-self-maintenance-mesh`: Exercises the exact whole-FlowGuard understanding path and consumes one current verified maturation identity.
- `authoritative-model-system`: Requires semantic model relations and whole-system dispositions rather than inventory presence for the current self-understanding claim.
- `flowguard-validation-command-surface`: Exposes a read-only model-understanding status command with no execution or publication side effects.
- `flowguard-api-registry`: Registers the read-only status types and functions as one kernel-owned public surface rather than a new skill route.

## Impact

The change affects the task-coverage, route-topology, maturation, receipt, admission, risk/closure, hierarchical mesh, CLI/API registry, self-model, behavior/alignment inventory, evidence-object storage on deep Windows paths, focused tests, affected skill source prompts, SkillGuard contracts, consumer projection, local installation, version metadata, documentation, and Git/release evidence. It is completed in the same authorized patch-release batch as `close-model-implementation-blueprint-loop`; remote push, tag, and GitHub Release publication occur only after both changes, the contraction change, installation, and the single frozen final validation owner are current. Public field or signature removals remain governed by the behavior-preserving reduction change after conformance evidence exists.
