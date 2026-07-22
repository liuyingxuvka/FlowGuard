## Why

FlowGuard can validate each portable model and close declared assumption/guarantee tokens, but that evidence does not execute asynchronous events, retries, shared resources, or other cross-model interleavings. This leaves a distinct class of integration defects able to pass every local model and the current token-level composition check.

The next product step is a bounded, change-scoped composition capability that can prove the narrower and testable claim: all selected local components are green, yet one declared system safety property can still fail under an explored interaction schedule.

## What Changes

- Add a strict `flowguard.portable_system.v1` family with three separate identities: a stable `PortableSystemDefinition`, one task-local `SystemCompositionRequest`, and the derived `PortableSystemSlice`. The definition references current component fingerprints and declares typed event ports, bindings, shared resources, transition effects, and owner-bound system properties; the request carries changed-model roots, selected properties, and scheduler bounds.
- Compile the exact affected system slice into the existing finite portable model/checker path, so FlowGuard gains cross-model scheduling semantics without creating a second verdict engine or replacing native local-model owners.
- Add a public Python API and one `python -m flowguard portable-system-check` command that fail closed on stale components, missing identity or atomicity semantics, unresolved dependencies, incomplete slices, unsupported effects, or truncated exploration.
- Preserve `check_composition()` as the token-provider/conflict gate and make its claim boundary visibly distinct from executable system-composition evidence.
- Add an Emergent Integration Benchmark covering payment/order retry identity, permission revocation with stale cache, and deletion propagation to index/export, including local-green, token-green, system-red, repaired-green, malformed, and truncated cases.
- Extend the default FlowGuard kernel, existing-model discovery, and Model-Test Alignment with the minimum typed handoffs needed for this feature. Extend ModelMesh only for actual parent/child or sibling reattachment, and reuse current topology, ContractExhaustionMesh, TestMesh, and DevelopmentProcessFlow contracts unless focused evidence proves a missing generic field or gate; none becomes a second system checker.
- Allow AI guidance to propose a model delta, but keep that proposal in the agent-operation/process plane until an explicit owner accepts or rejects it and refreshes the current product artifact and code/test bindings.
- Activate the feature through the public API/CLI, default FlowGuard guidance, author-side SkillGuard contracts, and a clean installed consumer-skill projection.

## Capabilities

### New Capabilities

- `flowguard-bounded-system-composition`: Strict system definition/request/slice IR, declared-graph affected-slice compilation, bounded scheduler semantics, owner-bound safety and existing portable temporal projections, minimal counterexamples, fail-closed limits, benchmark, and public API/CLI behavior.

### Modified Capabilities

- `flowguard-compositional-verification`: Distinguish token-level closure from executable system composition while retaining one canonical checker owner and one primary behavior path.
- `existing-model-preflight`: Discover current models/owners, existing system-definition references, proposed relations, affected-slice candidates, and unresolved dependencies before composition without becoming a second system-artifact authority.
- `hierarchical-model-mesh`: When a parent/child or sibling reattachment is actually involved, emit and consume exact composite-candidate/receipt references without expanding child graphs or executing product state.
- `pre-implementation-model-hardening`: Preserve anchored event, retry, shared-writer, cache, atomicity, and external-confirmation hazards as candidate scenario seeds without choosing a missing owner or claiming execution.
- `contract-exhaustion-mesh`: Generate owner-declared finite policy variants, initial environments, fault profiles, malformed boundaries, and test shards without duplicating the scheduler's exploration of one fixed system graph.
- `model-test-alignment`: Bind system invariant to composite scenario, minimal trace step, real code/runtime target, and current regression evidence.
- `test-evidence-mesh`: Consume the canonical system report through the existing proof-artifact fingerprint map and preserve terminal/blocked/truncated evidence without copying product-domain fields into TestMesh.
- `development-process-flow`: Apply its existing proof-first, background-liveness, peer-write, install-domain, and final-freeze rules to this delivery; add no system-specific process authority unless a focused test proves a generic gap.
- `flowguard-skill-kernel`: Route cross-model event/resource/retry/ordering triggers to the bounded system-composition path and keep candidate model deltas non-authoritative until accepted.
- `flowguard-api-registry`: Add the bounded system-composition cohort to public API discovery without exposing internal compiler helpers.

## Impact

- Affects portable model/composition modules, the public package facade and CLI, behavior-commitment/model artifacts, benchmark examples, tests, documentation, and selected FlowGuard author skills.
- Reuses the existing `commitment:portable-compositional-verification`, its primary owner model, and its canonical checker path; no new public satellite skill or parallel interpreter is introduced.
- Adds no third-party runtime dependency and does not claim unbounded, probabilistic, real-time, production-conformance, or automatically learned system truth.
- Requires current component artifacts and exact fingerprints. Missing or ambiguous dependency semantics block the executable-composition claim rather than falling back to token closure. Slice completeness is exact only over the declared system graph; undeclared real-world dependencies remain explicit residual risk.
- Advances the completed local capability to FlowGuard `0.60.0`, synchronizes the clean 15-skill consumer projection, and publishes one source-only GitHub tag and Release after local and remote verification.
