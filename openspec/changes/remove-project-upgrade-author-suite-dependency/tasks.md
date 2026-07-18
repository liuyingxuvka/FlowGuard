## 1. Model-Miss Boundary

- [x] 1.1 Preserve the v0.58.2 non-editable `suite_map_missing` reproduction and classify it as an editable-layout evidence overclaim.
- [x] 1.2 Extend the project-adoption FlowGuard model with package-authority and editable-author-map bad cases.

## 2. Consumer Authority

- [x] 2.1 Add the deterministic package-owned clean-consumer authority schema, compiler, loader, and package-data configuration.
- [x] 2.2 Add exact author-source-to-authority and authority-to-global-consumer validation with visible mismatch findings.
- [x] 2.3 Make install and currentness operations block when the packaged authority is stale.

## 3. Project Adoption Root Fix

- [x] 3.1 Replace `_load_suite_evidence` author-suite-map validation with the packaged-authority/global-consumer validator.
- [x] 3.2 Preserve strict pre-write blocking for absent, incomplete, modified, reserved-extra, or author-control-polluted global consumers.
- [x] 3.3 Keep target-local `.agents/skills`, `.skillguard`, and suite maps outside the runtime authority path.

## 4. Executable Regressions

- [x] 4.1 Add focused authority compiler, exact-parity, mismatch, and no-fallback tests.
- [x] 4.2 Add a real non-editable installation regression that upgrades an empty ordinary project and then passes project audit.
- [x] 4.3 Assert expected adoption outputs and zero project-local suite, suite-map, script, or author-control residue.

## 5. Maintainer Synchronization

- [x] 5.1 Update project integration guidance, changelog, release checklist, and visible version to 0.58.3.
- [x] 5.2 Regenerate the affected FlowGuard SkillGuard contract and packaged consumer authority after all skill-source edits.
- [x] 5.3 Run strict OpenSpec validation and affected FlowGuard model, package, skill, and project-adoption checks.

## 6. Release Closure

- [ ] 6.1 Run all 15 native skill owners, parent self-governance, and one clean eight-owner final full gate.
- [ ] 6.2 Verify an exact Git commit non-editable installation, global 15-skill parity, empty-project upgrade writes, and post-write audit.
- [ ] 6.3 Commit, tag, push, pass GitHub CI, publish source-only v0.58.3 with zero assets, and pass the published verifier.
- [ ] 6.4 Release the exact immutable installation owner to Khaos and record the model-miss lesson through KB postflight.
