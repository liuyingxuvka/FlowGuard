## 1. OpenSpec And Model Surface

- [x] 1.1 Add OpenSpec deltas for capability coverage inside the existing UI, implementation, human-operability, plan, model-miss, process, risk, agent-workflow, and closure routes.
- [x] 1.2 Add UI functional capability inventory, output contract, capability binding, report, and review helper objects in `flowguard.ui_structure`.
- [x] 1.3 Add additive capability/output fields to `UIFeatureContract`, `UIUserTaskCoverageLedger`, and `UIImplementationValidation`.

## 2. Existing Route Integration

- [x] 2.1 Wire implementation validation to require current capability coverage for broad runnable/complete UI claims.
- [x] 2.2 Wire human-operability review to validate capability-to-task coverage when a capability inventory is supplied.
- [x] 2.3 Add ClosureContract, RiskEvidenceLedger, DevelopmentProcessFlow, AgentWorkflowRehearsal, and PlanDetailing constants/guidance for capability coverage without creating a parallel UI route.
- [x] 2.4 Extend Model-Miss guidance so missing promised UI capabilities are treated as `boundary_missing` or `evidence_overclaimed`.

## 3. Docs, Skills, And Templates

- [x] 3.1 Update UI Flow Structure skill and protocol to place capability coverage inside the existing workflow.
- [x] 3.2 Update public docs/API/template text and field inventory docs for the new capability models and fields.
- [x] 3.3 Sync installed Codex FlowGuard skill copies and verify source/installed parity.

## 4. Tests And Counterexamples

- [x] 4.1 Add UI structure tests for missing required capability contracts, missing tasks, missing journey/control/event binding, missing output contracts, dependency gaps, stale/failed evidence, and scoped-out capability defects.
- [x] 4.2 Add implementation validation tests proving a complete UI claim blocks when capability coverage is missing or failed.
- [x] 4.3 Add process/risk/closure/plan/model-miss/API/template/skill-doc tests for the new route integration.
- [x] 4.4 Add known-good examples proving greenfield and source-based work both use the same capability coverage layer while source-baseline remains source-only.

## 5. Version, Validation, And Sync

- [x] 5.1 Bump version metadata and changelog for the new local version.
- [x] 5.2 Validate this OpenSpec change and all current specs strictly, accounting for parallel active changes without reverting them.
- [x] 5.3 Run focused tests and the strongest practical full regression.
- [x] 5.4 Reinstall/editable-sync the local package and verify import path/version.
- [x] 5.5 Sync the FlowGuard_20260427 shadow workspace and verify import/version there.
- [x] 5.6 Record FlowGuard adoption evidence and predictive-KB postflight.
- [x] 5.7 Commit only this work's files and create a local version tag without reverting peer-agent changes.
