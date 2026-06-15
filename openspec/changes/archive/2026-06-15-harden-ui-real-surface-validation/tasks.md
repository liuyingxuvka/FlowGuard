## 1. OpenSpec And FlowGuard Model Setup

- [x] 1.1 Validate this OpenSpec change strictly and keep proposal, design, specs, and tasks aligned. Evidence: `openspec validate --strict`.
- [x] 1.2 Record an existing-model preflight for the UI Flow, Model Miss, process, risk, closure, and skill-satellite owner routes. Evidence: model/preflight notes and project audit.
- [x] 1.3 Add a FlowGuard development-process/adoption log entry for this change, including touched artifacts, validation expectations, sync surfaces, and final claim boundaries. Evidence: `.flowguard/adoption_log.jsonl` and `docs/flowguard_adoption_log.md`.

## 2. UI Real-Surface Gates

- [x] 2.1 Add observed/rendered UI inventory data structures and review helper APIs under `flowguard.ui_structure`. Evidence: unit tests for pass/fail inventory coverage.
- [x] 2.2 Require observed buttons, inputs, selects, tables, display fields, status text, native-dialog triggers, and commands to map to `UIControl`, `UIDisplayElement`, `UIVisibleSurfaceItem`, or a scoped blindspot. Evidence: unit tests for unmapped and mapped cases.
- [x] 2.3 Add enabled-control functional chain structures and review helper APIs that bind visible control, UI event, code owner, runtime/local/backend/native function, observed UI update, and evidence reference. Evidence: unit tests rejecting API-only and label-only proof.
- [x] 2.4 Add generic source-baseline interaction semantics structures and review helper APIs for native pickers, external opens, save/custom dialogs, no-handler controls, trigger/confirm/cancel/value/result/error branches, and native/manual boundaries. Evidence: unit tests for pass/fail source-based parity cases.
- [x] 2.5 Integrate the new gates into UI Flow docs, public API exports, and generated UI templates without weakening the compact starter boundary. Evidence: docs/template/API tests.

## 3. Miss, Process, Risk, Closure, And Agent Workflow Gates

- [x] 3.1 Strengthen Model Miss Review guidance and helpers so user-observed UI mismatch after green evidence records previous claim, miss class, same-class UI scan, and same-class evidence. Evidence: model-miss unit tests.
- [x] 3.2 Strengthen plan-detailing and development-process helpers so UI task rows and lifecycle evidence carry evidence type, evidence status, evidence reference, freshness, and scoped boundary. Evidence: plan/process unit tests.
- [x] 3.3 Add final UI done-claim review support to RiskEvidenceLedger/ClosureContract so planned evidence, missing manual signoff, native-dialog blindspots, unmapped visible items, missing functional chains, and missing implementation validation block broad claims. Evidence: risk/closure unit tests.
- [x] 3.4 Strengthen AgentWorkflowRehearsal so multi-agent UI workflows require inventory, source-baseline mapping/alignment, implementation validation, and integration evidence roles before full runnable UI confidence. Evidence: agent-workflow unit tests.

## 4. Skill, Documentation, And Installed Sync

- [x] 4.1 Update repository skill prompts and protocol references for UI Flow, Model Miss, DevelopmentProcessFlow, AgentWorkflowRehearsal, and any affected closure/risk guidance. Evidence: skill-doc tests or focused content checks.
- [x] 4.2 Update public docs, README/API surface, and template text so compact examples cannot be mistaken for full runnable UI evidence. Evidence: docs/template tests.
- [x] 4.3 Synchronize installed Codex skill copies from the repository skill sources. Evidence: SHA256 comparison for repository and installed UI Flow, Model Miss, DevelopmentProcessFlow, and AgentWorkflowRehearsal skill files.
- [x] 4.4 Synchronize the current shadow workspace with the editable Git root without overwriting unrelated peer work. Evidence: `scripts/sync_shadow_workspace.py --source . --target C:\Users\liu_y\Documents\FlowGuard --install --verify --expected-version 0.43.3` copied 1311 files and passed verification.

## 5. Validation And Release Boundary

- [x] 5.1 Run focused tests for UI structure, Model Miss, plan detailing, development process, risk ledger, closure contract, agent workflow, public templates, API surface, and skill docs. Evidence: passing focused test output.
- [x] 5.2 Run project audit and strongest practical regression suite; background runs may start early but only final exit/result artifacts count. Evidence: formal project audit pass, OpenSpec strict pass, self-model pass, and `python -m pytest -q` with 807 passed, 13 warnings, 225 subtests passed.
- [x] 5.3 Verify editable install and shadow workspace imports expose the same FlowGuard version and new APIs. Evidence: both formal and shadow roots import FlowGuard 0.43.3/schema 1.0 and expose the UI inventory, functional-chain, source-baseline, model-miss, closure, and agent-role symbols.
- [x] 5.4 Update adoption logs with executed checks, skipped or timed-out checks, sync status, and safe final claim wording. Evidence: `.flowguard` machine log and human log.
- [x] 5.5 Perform KB postflight and record reusable lessons or misses. Evidence: KB feedback event `7bd61e52-f6de-466a-9eac-648b698a6dfd`.
