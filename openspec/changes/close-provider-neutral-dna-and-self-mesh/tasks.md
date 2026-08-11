## 1. OpenSpec and public contract

- [x] 1.1 Confirm the existing target-system registry and layer-plan types are the only provider/profile authority.
- [x] 1.2 Add provider-neutral declaration and qualification result types with explicit statuses and claim boundary.
- [x] 1.3 Export the new types through the existing public module without adding an alternate import path.

## 2. Registry admission

- [x] 2.1 Validate unique provider ids, profile ids, target kinds, layer plans, and owners.
- [x] 2.2 Reject duplicate provider/profile-owner declarations with a deterministic error reason.
- [x] 2.3 Reject unknown profiles and unsupported target kinds without fallback registration.
- [x] 2.4 Add tests for valid admission, duplicate rejection, unknown profile rejection, and deterministic ordering.

## 3. Self-DNA qualification

- [x] 3.1 Add separate static, semantic, code-binding, and test-binding status projections.
- [x] 3.2 Require current semantic mesh status and exact parent-child fingerprints for qualified self-DNA.
- [x] 3.3 Require exact code-owner and test-owner bindings; keep missing, stale, candidate, and unknown reasons visible.
- [x] 3.4 Keep reconstruction outside ordinary qualification and document the explicit caller-owned boundary.
- [x] 3.5 Add tests for static-ready/semantic-stale, candidate-mesh blocked, fully qualified, and reconstruction-request separation.

## 4. Reduction truthfulness

- [ ] 4.1 Add independent inventory-complete, proof-complete, and applied-and-verified fields to the reduction projection.
- [ ] 4.2 Preserve unresolved candidates and ensure cleanup-release-ready is false when any required proof or application step is missing.
- [ ] 4.3 Add tests covering unresolved candidates, proven-but-unapplied candidates, and applied-and-verified simplification.

## 5. Validation and downstream handoff

- [ ] 5.1 Run focused FlowGuard tests, project-audit, and the relevant OpenSpec verification.
- [ ] 5.2 Update the FlowGuard adoption log with model files, commands, evidence identities, and skipped work.
- [ ] 5.3 Install the source projection only after author-side SkillGuard checks are current and passing.
- [ ] 5.4 Hand the provider-neutral contract to ResearchGuard, PhysicsGuard, and WorldGuard without embedding their domain logic in FlowGuard.
