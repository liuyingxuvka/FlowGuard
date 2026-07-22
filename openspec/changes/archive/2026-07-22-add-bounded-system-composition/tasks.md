## 1. Ownership and Model Grounding

- [x] 1.1 Record this work as `change_behavior` for `commitment:portable-compositional-verification`, preserving its existing owner model and canonical primary path.
- [x] 1.2 Extend the compositional-verification self-model with explicit `pass/fail/blocked/invalid/not_run` stage states, affected-slice/system-interaction/exploration gates, safety-witness-versus-temporal-truncation semantics, and known-bad bypasses.
- [x] 1.3 Freeze the implementation ownership map: strict system artifacts in `portable_system.py`, joint compilation/check projection in `system_composition.py`, and final verdict in the existing portable checker.
- [x] 1.4 Define Model-Test Alignment and TestMesh obligations for local, token, executable, truncation, counterexample, API/CLI, benchmark, and installed-projection evidence.

## 2. Strict Portable System Contract

- [x] 2.1 Implement separate current-schema `PortableSystemDefinition`, `SystemCompositionRequest`, and derived `PortableSystemSlice` records with component refs, transition refs, semantic event ports/bindings, resource semantics, joint steps, state patterns, system safety/temporal properties, and scheduler/bound inputs.
- [x] 2.2 Implement strict JSON parsing, canonical serialization/fingerprints, load/write helpers, and structural validation with no compatibility reader.
- [x] 2.3 Validate component and transition identities, port directions, declared identity/delivery/resource semantics, atomic step shape, property ownership, and complete transition coverage; keep code/runtime targets optional and non-semantic.
- [x] 2.4 Implement change-root affected-slice closure across the declared typed graph, including steps, bindings, resource co-use, special components, patterns, properties, and declared/unresolved dependencies; report discovery identity and the unknown-unknown claim boundary.
- [x] 2.5 Add focused contract tests for valid identity, order-independent fingerprints, unknown fields, stale refs, missing identity, exactly-once rejection, unowned properties, unresolved dependencies, and incomplete slices.

## 3. Canonical Joint Compilation and Checking

- [x] 3.1 Build deterministic joint initial states and enabled one-reference/multi-reference system steps over exact portable transitions.
- [x] 3.2 Compile reachable joint states, joint transitions, forbidden patterns, eventual/bounded/terminal obligations, and fairness step ids into one `PortableModel`.
- [x] 3.3 Enforce the joint-state bound, preserve unexplored frontier identity, return blocked for clean or temporal truncation, and preserve only a canonical-checker-confirmed reachable safety failure found before truncation with residual risk.
- [x] 3.4 Run component-local checks and token-level `check_composition()` before compilation while preserving invalid/blocked/fail status classes.
- [x] 3.5 Delegate each eligible system check to at most one `check_portable_model()` invocation (complete graph or selected safety-witness graph) and project its trace back to system steps, component states/transitions, relations, and optional code/runtime targets.
- [x] 3.6 Add tests for local-green/token-green/system-red, repaired green, atomic versus non-atomic schedules, temporal dead ends/cycles, weak fairness, blocked components, stale fingerprints, minimal mapped traces, and deterministic compiled identity.

## 4. Public Feature Activation

- [x] 4.1 Add the bounded system-composition cohort to the package facade and API registry while keeping compiler internals private.
- [x] 4.2 Add one `portable-system-check` CLI with exact system/component inputs, canonical JSON, concise human output, and status-preserving exit behavior.
- [x] 4.3 Add API/CLI parity tests for pass, fail, blocked, invalid, missing/extra component, fingerprint mismatch, and human projection.
- [x] 4.4 Document the system artifact, queue/resource-as-component pattern, typed bindings, atomic steps, affected slices, properties, bounds, counterexamples, and claim boundary in API/modeling/product helper docs.
- [x] 4.5 Advance local package, project, changelog, and rendered adoption records to `0.60.0`, reserving remote release actions for the final frozen gate.

## 5. Emergent Integration Benchmark

- [x] 5.1 Add an additive benchmark manifest/report and one native runner; keep the existing 2100-case local corpus baseline unchanged.
- [x] 5.2 Implement the payment/order retry-identity family with local-green/token-green bad, repaired, missing-identity, and truncated variants.
- [x] 5.3 Implement the permission-revocation/cache family with local-green/token-green bad, repaired, missing-binding, and truncated variants.
- [x] 5.4 Implement the deletion/index/export family with local-green/token-green bad, repaired, incomplete-slice, and truncated variants.
- [x] 5.5 Report local-green count, executable failures, false findings, minimal trace length, affected/full model counts, explored states, and bounded claim scope.
- [x] 5.6 Register the benchmark owner and purpose/failure bindings in the model-regression manifest so the intended tier actually executes it.

## 6. FlowGuard Evidence and Governance Integration

- [x] 6.1 Update the Behavior Commitment Ledger source/owner/path/evidence rows in change mode without adding a new commitment or primary path.
- [x] 6.2 Update Existing Model Preflight outputs for current fingerprints/system-definition references, proposed relations, candidate changed roots/slices, discovery identity, and fail-closed unresolved dependencies without copying the system schema.
- [x] 6.3 Add ModelMesh composite-candidate and exact-receipt handoff semantics only for hierarchical parent/child/sibling closure or freshness work, without child-graph execution or a peer-network runtime.
- [x] 6.4 Add topology-anchored event/retry/resource/cache/atomicity/external-confirmation interaction seeds that reference an existing owner or emit `owner_missing`, without promoting them to executed findings.
- [x] 6.5 Add finite artifact/delivery/environment/fault/malformed/benchmark axes and case/oracle handoffs to ContractExhaustionMesh while retaining its non-execution boundary and avoiding duplicate schedule enumeration.
- [x] 6.6 Add system property → scenario → trace step → code/runtime → regression bindings to Model-Test Alignment.
- [x] 6.7 Project system/request/slice/component/compiled-model/bound/truncation/trace identities through existing TestMesh `ProofArtifactRef` fingerprints and owner receipts; add generic fields only if focused evidence proves a gap.
- [x] 6.8 Update DevelopmentProcessFlow ordering and freshness rules so executable evidence precedes prompt activation and background progress never becomes pass evidence.

## 7. Skill Prompt and SkillGuard Maintenance

- [x] 7.1 Update the default FlowGuard skill/protocol/OpenAI prompt with cross-model triggers, composite output fields, single-checker routing, and candidate model-delta status.
- [x] 7.2 Update only the affected Existing Model Preflight, ModelMesh (hierarchical case), Topology Hazard, Contract Exhaustion, Model-Test Alignment, TestMesh, and DevelopmentProcessFlow skill surfaces whose existing prompts/contracts need new routing or claim-boundary language; do not add runtime ownership to satellites.
- [x] 7.3 Preserve the current fifteen-member author suite and internal DPF modes; do not create a sixteenth public skill or restore retired standalone planning/workflow routes.
- [x] 7.4 Re-resolve latest stable SkillGuard v0.4.0 and compile the affected contracts/manifests under the frozen `unit:flowguard-suite` maintenance owner.
- [x] 7.5 Run target-owned native checks, SkillGuard static/depth/impact validation, and build/audit the clean consumer projection with no author control state.

## 8. Focused Verification and Repair

- [x] 8.1 Run strict validation for this OpenSpec change and reconcile every task/spec/code/test mapping.
- [x] 8.2 Run focused portable-system, composition, CLI/API, benchmark, behavior-ledger, preflight, ModelMesh, topology, exhaustion, alignment, TestMesh, DPF, prompt parity, and distribution tests.
- [x] 8.3 Run focused native FlowGuard models and verify every known-bad variant fails for its intended protected failure.
- [x] 8.4 Repair all affected failures and rerun only invalidated focused owners until the integration snapshot is stable.

## 9. Local Synchronization and OpenSpec Closure

- [x] 9.1 Synchronize the authoritative local Python package/runtime from the current checkout and verify imported version/schema/path identity.
- [x] 9.2 Transactionally install the clean Codex consumer skill projection and verify source/consumer/installed content parity.
- [x] 9.3 Update FlowGuard machine/human adoption records through the project-owned upgrade command, including commands, findings, revalidation requirements, and claim boundary.

The background full-model campaign, frozen-snapshot release validation, scoped Git commit, GitHub publication, post-publish parity, and predictive-KB postflight are downstream release operations. They remain explicit required items in the DevelopmentProcessFlow execution plan; they are not self-referential prerequisites for archiving this implementation change.

