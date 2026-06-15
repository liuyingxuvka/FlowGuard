## 1. Planning And FlowGuard Evidence

- [x] 1.1 Create OpenSpec proposal, design, specs, and tasks for validation evidence gates.
- [x] 1.2 Add a FlowGuard rollout model that rejects known-bad missing UI click-through, payload pack, manual evidence, and installed prompt sync gates.
- [x] 1.3 Validate the OpenSpec change with strict validation.

## 2. Core Helper Implementation

- [x] 2.1 Add artifact payload contract, evidence, finding, report, and review helper types under Model-Test Alignment.
- [x] 2.2 Integrate artifact payload contracts/evidence into `ModelTestAlignmentPlan` and block alignment on payload validation failures.
- [x] 2.3 Export the new public helper API and update API surface grouping.
- [x] 2.4 Extend RiskEvidenceLedger gate constants and guidance for UI implementation and artifact payload evidence.

## 3. Guidance, Templates, And Docs

- [x] 3.1 Strengthen UI Flow Structure skill and protocol wording for reachable actionable controls/events and conditional manual evidence.
- [x] 3.2 Update Model-Test Alignment, TestMesh, DevelopmentProcessFlow, PlanDetailing, AgentWorkflowRehearsal, RiskEvidenceLedger, and kernel guidance for payload/manual evidence gates.
- [x] 3.3 Update generated template text for UI Flow Structure, Model-Test Alignment, TestMesh, DevelopmentProcessFlow, PlanDetailing, and RiskEvidenceLedger.
- [x] 3.4 Update user-facing docs, API surface docs, AGENTS snippet, and project adoption managed block text.

## 4. Tests And Regression

- [x] 4.1 Add focused unit tests for artifact payload validation success, missing case, stale/non-passing evidence, output mismatch, and alignment integration.
- [x] 4.2 Add focused tests for risk ledger gate constants and skill/template guidance coverage.
- [x] 4.3 Run focused tests, public template execution tests, skill-doc tests, OpenSpec validation, and FlowGuard rollout checks.
- [x] 4.4 Run or record broad regression evidence and fix discovered failures.

## 5. Version, Install, And Repository Sync

- [x] 5.1 Bump package version and changelog/README release notes for the validation gate upgrade.
- [x] 5.2 Refresh editable/local install and verify imported package path, version, and new helper symbols.
- [x] 5.3 Sync repository-managed skills to installed Codex skills and verify installed content includes validation gate guidance.
- [x] 5.4 Locate and sync the local git source repository or explicitly record if the active workspace has no git repository available.
- [x] 5.5 Record FlowGuard adoption evidence and KB postflight observation for the completed upgrade.
