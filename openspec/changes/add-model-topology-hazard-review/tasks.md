# Tasks

## 1. Core Model Topology Hazard Review

- [x] 1.1 Add topology digest, usage intent, hazard candidate, report types,
  inference helpers, review decisions, and public exports.
- [x] 1.2 Add unit tests for landmark inference, unanchored observation-only
  hazards, anchored blocker hazards, handled hazards, and report formatting.

## 2. Runner, Maintenance, Ledger, and Templates

- [x] 2.1 Add an automatic `topology_hazard` section to
  `run_model_first_checks(...)`.
- [x] 2.2 Route topology-hazard gaps through maintenance scan.
- [x] 2.3 Add Risk Evidence Ledger fields/findings for required topology
  hazard review evidence.
- [x] 2.4 Add public template factory and CLI command.

## 3. OpenSpec, Models, Docs, and Skills

- [x] 3.1 Add a FlowGuard self-model for the topology hazard route.
- [x] 3.2 Add `flowguard-model-topology-hazard-review` skill, prompt protocol,
  installed skill sync path, and route-map updates.
- [x] 3.3 Update public docs, API docs, README, risk ledger docs, modeling
  protocol, productized helper docs, and AGENTS snippet.
- [x] 3.4 Add OpenSpec requirements and validate the change.

## 4. Validation and Sync

- [x] 4.1 Run focused tests and self-model checks.
- [x] 4.2 Run practical full regression in the background and collect evidence.
- [x] 4.3 Bump/sync package version, editable install, project record, shadow
  workspace, installed skills, local git commit, and local git tag.
