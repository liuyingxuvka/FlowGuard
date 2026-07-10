## 1. Lock Current Adoption Semantics

- [x] 1.1 Extract the complete current managed `AGENTS.md` rule set into stable rule identifiers, including BCL modes, PPA/path-sensitive evidence, latest-schema-first behavior, default replacement, field lifecycle, UI evidence, DevelopmentProcessFlow, post-change scanning, and no-fake-adoption boundaries.
- [x] 1.2 Add golden tests proving the generator contains every required rule and the package/manifest/rendered versions agree; keep real `project-upgrade` disabled until these tests pass.
- [x] 1.3 Add negative fixtures in which the generator drops BCL, PPA, `path_sensitive`, default replacement, or uses a stale rendered version, with deterministic expected audit codes.

## 2. Build Canonical Suite Inventory

- [x] 2.1 Add `.skillguard/flowguard-suite/suite-map.json` with schema/version metadata and all seventeen current skills: one kernel and sixteen satellites.
- [x] 2.2 Implement `flowguard/skill_suite.py` to load the inventory, discover all `SKILL.md` directories, verify uniqueness/cardinality/required files, and report deterministic inventory and semantic hashes.
- [x] 2.3 Make missing `.skillguard`, `agents/openai.yaml`, or other member requirements visible on the declared skill record rather than excluding the member from the scan.
- [x] 2.4 Add `tests/test_skill_suite_inventory.py` with known-bad cases for omitted BCL, undeclared skill directory, missing declared directory, duplicate id, missing control root, and a second private hard-coded member list.

## 3. Repair Project Adoption Generation

- [x] 3.1 Refactor `flowguard/project_adoption.py` so managed-block generation is driven by the stable current rule set and records the current package version without deleting newer policy.
- [x] 3.2 Extend project audit to compare stable rule ids and normalized managed-block content as well as package, manifest, and rendered adoption versions.
- [x] 3.3 Add `project-upgrade --dry-run` and JSON output that reports proposed files, semantic rule changes, suite findings, minimum revalidation, blockers, and claim boundary without writing files or logs.
- [x] 3.4 Make writing upgrade fail before mutation when the installed engine is older, suite membership is unresolved, or the proposed block loses a required rule; retain no alternate successful legacy rewrite path.
- [x] 3.5 Update adoption log records with before/after versions and hashes, actual mode, checks, skipped steps, findings, and next actions without treating log creation as validation.

## 4. Remove Parallel Suite Inventories

- [x] 4.1 Convert `scripts/verify_skill_suite_markers.py` into a thin adapter over the canonical suite validator with `--root` and `--json` support.
- [x] 4.2 Convert the suite/control discovery in `scripts/verify_guard_simulation_readiness.py` to use the same canonical result; preserve other readiness responsibilities without maintaining another member list.
- [x] 4.3 Add a repository test that detects unapproved hard-coded FlowGuard suite lists and proves both compatibility scripts report the same inventory hash and seventeen-member set.

## 5. Validate Safe Migration

- [x] 5.1 Run the focused adoption tests from `check.adoption.tests` and fix every positive and known-bad failure without weakening the oracles.
- [x] 5.2 Run `check.suite.inventory` and `check.readiness`; confirm BCL is included and any remaining missing control root is reported as a failure owned by the later contract-governance change.
- [x] 5.3 Run `project-upgrade --dry-run --json`, capture a pre/post repository hash/status comparison, and prove no tracked or untracked repository file was changed by dry-run.
- [x] 5.4 Review the dry-run semantic diff; only then execute the real project upgrade, rerun `project-audit --json`, and verify the managed block preserves every locked rule.

## 6. Close The Change

- [x] 6.1 Run every required command in `verification-contract.yaml`, including strict OpenSpec validation, and produce a current verification report bound to watched-file hashes.
- [x] 6.2 Confirm the change modifies only adoption/inventory-owned surfaces and leaves route topology, skill prompt contracts, runtime receipts, regression orchestration, installation, and release to their dependent changes.
- [x] 6.3 Record residual gaps explicitly: a member-level missing SkillGuard control root may remain visible after this change, but suite membership, generator integrity, dry-run safety, and project audit MUST be complete before handing off to `harden-flowguard-route-topology-and-ownership`.
