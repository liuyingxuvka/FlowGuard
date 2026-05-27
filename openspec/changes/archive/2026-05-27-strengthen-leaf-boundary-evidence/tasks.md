## 1. Specification And Model

- [x] 1.1 Define evidence-role, duplicate-primary-edge, Cartesian leaf matrix, TestMesh leaf-cell, and preflight layered-status requirements.
- [x] 1.2 Record why downgrading a duplicate primary proof without a child split is not acceptable closure.

## 2. Core API

- [x] 2.1 Extend `TestEvidence` with evidence roles and target ids.
- [x] 2.2 Add Model-Test Alignment findings for duplicate primary edge proof and missing supporting/leaf targets.
- [x] 2.3 Extend `LeafBoundaryMatrix` with input/state axes, Cartesian checks, unexpected-cell checks, and missing observed behavior checks.
- [x] 2.4 Extend TestMesh with required leaf matrix-cell evidence ownership.
- [x] 2.5 Extend Existing Model Preflight with layered proof status fields and blockers.
- [x] 2.6 Export new public constants and update API-surface docs.

## 3. Skills, Docs, And Templates

- [x] 3.1 Update satellite skills and route references for the new hard gates.
- [x] 3.2 Update public docs and templates so duplicate primary edge evidence routes to child split or leaf matrix cells.
- [x] 3.3 Update release notes and visible version surfaces.

## 4. Validation And Local Sync

- [x] 4.1 Add focused tests for Model-Test Alignment, layered proof, TestMesh, Existing Model Preflight, public templates, and skill docs.
- [x] 4.2 Run OpenSpec validation and focused tests.
- [x] 4.3 Run full regression, self-review/conformance, and public evidence suites.
- [x] 4.4 Sync editable install, local shadow workspace, and installed skills.
- [x] 4.5 Commit, tag, push, and publish the GitHub release after the latest user instruction restored publication scope.
