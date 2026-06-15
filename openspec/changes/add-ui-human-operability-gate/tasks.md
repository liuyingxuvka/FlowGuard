## 1. OpenSpec And FlowGuard Model Setup

- [x] 1.1 Validate the change strictly and keep proposal, design, specs, and tasks aligned. Evidence: `openspec validate --strict`.
- [x] 1.2 Add a FlowGuard self-model for user task coverage and human-operability gates. Evidence: model runner rejects known-bad UI confusion cases.
- [x] 1.3 Record adoption/process evidence for touched artifacts, validation, sync, and claim boundaries. Evidence: local adoption logs.

## 2. Core UI Human-Operability APIs

- [x] 2.1 Add user task coverage models and review rules under `flowguard.ui_structure`. Evidence: unit tests for uncovered features, missing task flows, orphan primary controls, and missing task-to-UI links.
- [x] 2.2 Add region semantic, affordance, action grammar, dialog/window, keyboard/focus, and walkthrough models. Evidence: unit tests for role mismatch, duplicate primary actions, dialog return gaps, focus gaps, and confused walkthroughs.
- [x] 2.3 Add aggregate `review_ui_human_operability(...)` and public report/finding exports. Evidence: API surface tests and pass/fail review tests.

## 3. Downstream Gates

- [x] 3.1 Extend Model Miss Review for human-operability UI miss classes. Evidence: model-miss tests.
- [x] 3.2 Extend PlanDetailing and DevelopmentProcessFlow with human-operability evidence kinds and freshness rules. Evidence: plan/process tests.
- [x] 3.3 Extend RiskEvidenceLedger and ClosureContract with human-operability gates before broad UI done/release confidence. Evidence: risk/closure tests.
- [x] 3.4 Extend AgentWorkflowRehearsal with a `ui_human_operability` role for multi-agent UI work. Evidence: agent-workflow tests.

## 4. Skills, Templates, Docs, And Version

- [x] 4.1 Update UI Flow skill prompts/protocols to require user task coverage, affordance, action grammar, dialog/window, keyboard/focus, and walkthrough evidence.
- [x] 4.2 Update public docs, API docs, templates, and README/changelog/version records.
- [x] 4.3 Synchronize installed Codex skill copies from repository sources. Evidence: installed file comparison.

## 5. Validation, Sync, And Git

- [x] 5.1 Run focused tests for UI structure, Model Miss, plan/process, risk, closure, agent workflow, public templates, API surface, and skill docs.
- [x] 5.2 Run project audit and strongest practical regression suite. Evidence: final command status.
- [x] 5.3 Verify editable install, formal repository, and shadow workspace expose the same FlowGuard version and new APIs.
- [x] 5.4 Synchronize local install, formal repo, shadow workspace, and local git without reverting unrelated peer work.
- [x] 5.5 Perform KB postflight and record reusable lessons or misses. Evidence: KB event id or explicit no-signal note.
