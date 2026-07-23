## 1. Authority Schema and Formal Model

- [x] 1.1 Add strict subject-lane, lifecycle, model-instance, typed-relation, coverage-universe, system-snapshot, authority-head, revision-set, decision, activation, and rollback schemas
- [x] 1.2 Add canonical serialization, content fingerprints, strict parsing, duplicate and unknown-reference checks, and compare-and-swap authority validation
- [x] 1.3 Build a FlowGuard self-model for observed/target/experiment separation, multi-model atomic replacement, bounded coverage, promotion, and rollback
- [x] 1.4 Run known-good, known-bad, transition, stuck-loop, fairness/progress, composition, and rollback checks before production integration

## 2. Project Authority and Baseline

- [x] 2.1 Add one `[model_authority]` observed-head pointer to the generated and audited project manifest
- [x] 2.2 Add content-addressed snapshot storage and atomic pointer-last activation without a second current authority
- [x] 2.3 Bootstrap the v0.61 observed snapshot from the registered inventory with exact set-equality coverage inside the declared, fingerprinted boundary
- [x] 2.4 Extend project audit to verify snapshot existence, fingerprint, subject revision, coverage status, and separate source/install/Git identities

## 3. Exact Model and Regression Evidence

- [x] 3.1 Replace mutable `regression:<model_id>:current` evidence identity with immutable model-instance fingerprints
- [x] 3.2 Resolve every regression input glob to exact normalized paths and content hashes and persist the input inventory
- [x] 3.3 Make code, test, skill, document, manifest, and purpose changes stale only the exact consuming model instances and affected closure
- [x] 3.4 Remove pre-manifest compatibility discovery after explicit registration and undeclared-runner failure evidence pass

## 4. Existing Owner Integration

- [x] 4.1 Update Existing Model Preflight to validate the observed head first and label lexical/filesystem discovery non-authoritative
- [x] 4.2 Exclude replaced and retired commitments from current lookup and bind active commitments to exact observed model instances
- [x] 4.3 Bind field and side-effect lifecycle changes to revision-set members and block partial replacement
- [x] 4.4 Bind Model-Test Alignment and TestMesh evidence to exact instance, snapshot, subject revision, and resolved input identities
- [x] 4.5 Project ModelMesh, Behavior Commitment Ledger, FieldLifecycleMesh, Model-Test Alignment, TestMesh, and PortableSystem refs through typed snapshot edges without changing their owner responsibilities

## 5. Atomic Revision Sets

- [x] 5.1 Generalize the existing task-local base/candidate state machine into one- or many-member `ModelRevisionSet`
- [x] 5.2 Compute declared-versus-observed diffs and the affected parent, child, sibling, dependency, commitment, field, contract, test, and system-property closure
- [x] 5.3 Require aggregate evidence closure and reject independent member acceptance
- [x] 5.4 Persist immutable candidate, decision, and activation receipts and update the observed head once by compare-and-swap
- [x] 5.5 Block stale-base activation and preserve candidate evidence for rebase or diagnosis

## 6. Return and Rollback Paths

- [x] 6.1 Implement experiment discard and target withdrawal without changing observed authority
- [x] 6.2 Implement observed-system rollback gates for code/config restore, data restore or compensation, external effects, and old-snapshot conformance
- [x] 6.3 Block pointer-only rollback, head rewind after later revisions, and exact-rollback claims for irreversible effects
- [x] 6.4 Add forward-repair disposition when exact operational rollback is unavailable

## 7. Coverage Closure

- [x] 7.1 Enumerate a fingerprinted finite coverage universe across external surfaces, commitments, models, fields/state/side effects, contracts, tests, and evidence
- [x] 7.2 Require per-dimension set equality for `complete_within_declared_boundary`
- [x] 7.3 Report unknown, excluded, stale, skipped, not-run, orphan, duplicate-owner, and unmapped rows
- [x] 7.4 Add the FlowGuard project baseline coverage inventory and retain any unresolved gaps without broadening the claim

## 8. Architecture and Structure Contraction

- [x] 8.1 Centralize proof-ready duplicate package-owned suite/version vocabulary and exact duplicate private helpers without crossing semantic owner boundaries
- [x] 8.2 Review the `model_test_alignment` source-cycle candidate and defer structural change because this release has no facade-complete, parity-proven split
- [x] 8.3 Review the `self_maintenance`/`route_topology` cycle candidate and defer structural change because neutral ownership and parity are not yet proven
- [x] 8.4 Register oversized modules as later StructureMesh review targets and execute only the authority/store/revision/manifest splits that have facade and parity evidence in this release
- [x] 8.5 Preserve public imports, CLI behavior, JSON shape, finding codes/order, templates, and observable side effects

## 9. CLI, API, Skills, and Documentation

- [x] 9.1 Export the authority and revision-set API through the existing FlowGuard facade
- [x] 9.2 Add model-system bootstrap/audit, revision activate/rollback, and simulator-list projection behaviors through existing CLI ownership
- [x] 9.3 Update affected FlowGuard skill sources to report observed revision/snapshot, candidate snapshot, affected closure, gaps, and claim boundary
- [x] 9.4 Update project rules, modeling protocols, route references, examples, and human documentation without creating a second authority

## 10. Focused Validation and Source Freeze

- [x] 10.1 Add unit tests for strict schemas, fingerprints, coverage equality, typed edges, pointer integrity, and invalid current labels
- [x] 10.2 Add integration tests for single/multi-model activation, partial failure, base drift, crash safety, concurrent candidates, withdrawal, rollback, compensation, and forward repair
- [x] 10.3 Add preflight, commitment, field, alignment, TestMesh, project-audit, CLI/API, installation, and compatibility-removal regression tests
- [x] 10.4 Run affected FlowGuard models and focused tests until green, resolve model misses, and freeze source/toolchain/impact identities

## 11. Full Evidence, SkillGuard, and Installation

- [x] 11.1 Launch exactly one persistent all-model regression owner and exactly one persistent full-test owner for the frozen source snapshot
- [x] 11.2 Verify terminal result artifacts, exit codes, source fingerprints, skipped/not-run rows, and zero leftover descendants
- [x] 11.3 Use the then-current SkillGuard authority to maintain the changed FlowGuard suite and obtain exact terminal maintenance evidence
- [x] 11.4 Build and transactionally install a clean consumer skill projection and current Python package
- [x] 11.5 Verify source, installed package, installed skills, project record, observed snapshot, and target functionality parity
- [x] 11.6 Retire the old v0.55 checkout from active tool routing without deleting its parallel or historical work

## 12. Version, GitHub Release, and Closure

- [x] 12.1 Select and apply the next semantic version, release notes, changelog, project records, and source package metadata
- [x] 12.2 Validate OpenSpec implementation, reconcile delta specs, and archive the completed change
- [x] 12.3 Commit only owned and deliberately integrated paths, push the release branch, and publish the new tag and GitHub Release
- [x] 12.4 Verify the published source in a clean environment and rerun installation/currentness checks
- [x] 12.5 Perform the predictive-KB postflight, record any reusable miss or route lesson once, and close the goal with explicit evidence and bounded claims
