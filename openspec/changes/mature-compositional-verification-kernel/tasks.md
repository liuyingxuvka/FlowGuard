## 1. Freeze Ownership And Semantic Boundary

- [x] 1.1 Record the existing-model preflight, product-runtime Behavior Commitment, protected failure classes, and smallest faithful FlowGuard model for the portable verification boundary.
- [x] 1.2 Reconcile this OpenSpec work package with FlowGuard obligations and freeze the focused check owner plan before executing checks.

## 2. Implement Portable Model IR

- [x] 2.1 Add current-schema dataclasses for states, transitions, invariants, temporal obligations, contracts, portable models, and refinement bindings.
- [x] 2.2 Implement strict parsing, unknown-field rejection, reference validation, canonical JSON, stable SHA-256 identity, and artifact load/write helpers.
- [x] 2.3 Add IR tests for current/retired schema behavior, nondeterministic relation preservation, canonical equivalence, semantic staleness, malformed values, and dangling references.

## 3. Implement Reference Checker

- [x] 3.1 Implement bounded input-sequence execution with all nondeterministic traces and visible truncation.
- [x] 3.2 Implement reachable-graph safety, terminal progress, universal eventuality, bounded eventuality, and weak-fairness-aware SCC checks.
- [x] 3.3 Implement canonical reports with findings, checked obligations, counterexamples, blockers, residual risk, and claim boundary.
- [x] 3.4 Add checker tests with native positive and one generalized bad case per protected safety, liveness, bound, fairness, and truncation failure.

## 4. Implement Composition And Refinement

- [x] 4.1 Implement complete state/transition mapping checks, mapped step simulation, initial/terminal projection, and declared stutter handling.
- [x] 4.2 Implement assumption weakening, guarantee strengthening, component provider closure, and explicit conflict checks.
- [x] 4.3 Preserve smallest child/parent traces and contract gaps in refinement/composition reports.
- [x] 4.4 Add composition tests for valid refinement, unmapped steps, symbol mismatch, stronger child assumptions, missing guarantees/providers, and conflicts.

## 5. Integrate Public API, CLI, Models, And Skills

- [x] 5.1 Export the narrow portable verification cohort and register validate, check, and refinement CLI commands using the canonical report model.
- [x] 5.2 Add CLI/API parity, exit-status, human/JSON, invalid-file, and private-helper tests.
- [x] 5.3 Add the compositional verification FlowGuard model with current purpose closure and register it in the model-regression manifest.
- [x] 5.4 Update model-first, ModelMesh, topology-hazard, relevant references, and generated SkillGuard contracts without adding a duplicate public skill.
- [x] 5.5 Update README and concept documentation with the intrinsic capability boundary and non-goals.

## 6. Focused Verification And Closure

- [x] 6.1 Execute each frozen focused owner once, fix failures, and retain current receipts for IR, checker, composition, CLI/API, model, skills, and OpenSpec strict validation.
- [x] 6.2 Run official OpenSpec 1.6 strict validation plus the project verification contract (`python scripts/check_openspec_change.py --change mature-compositional-verification-kernel --strict`) and resolve every required obligation/evidence gap.
- [x] 6.3 Run the post-change owner scan, affected model regression, SkillGuard project audit, and template-harvest disposition; record remaining claim boundaries.

## 7. Portfolio Release Handoff

- [x] 7.1 Hand the frozen source identity and affected-only results to the single final portfolio validation owner; do not launch a second equivalent full run.
- [ ] 7.2 After final validation, synchronize the installation projection, version/changelog/docs, local editable package, and local Git commit. Do not push, create a remote tag, or publish a GitHub Release.
- [ ] 7.3 Archive this OpenSpec change only after current implementation, verification, installation, and local-release evidence all pass.
