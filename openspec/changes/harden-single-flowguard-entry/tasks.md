## 1. Formal Entry Data Model

- [x] 1.1 Add structured known-bad proof records and review reports.
- [x] 1.2 Harden `RiskIntent` validation for protected error classes, completion evidence, known-bad cases, and template reuse/no-match fields.
- [x] 1.3 Harden `MinimumModelContract` review so formal claims block on missing teeth.
- [x] 1.4 Extend `FlowGuardCheckPlan` serialization, formatting, and coercion with known-bad proof evidence and formal-entry mode.

## 2. Runner And Reporting

- [x] 2.1 Add known-bad proof and formal-entry sections to `run_model_first_checks(...)`.
- [x] 2.2 Ensure missing proof blocks and unexpectedly passing known-bad cases fail the formal summary.
- [x] 2.3 Update model audit and summary/ledger output so direct-Explorer-only or incomplete formal entries cannot be overclaimed.

## 3. Public Entry Contraction

- [x] 3.1 Remove `Explorer` from `AGENT_DEFAULT_API` and add the formal entry helper names.
- [x] 3.2 Update API surface tests while preserving unrelated concurrent exports already in the worktree.
- [x] 3.3 Update docs that currently describe `Explorer` as the direct/default/minimum FlowGuard path.

## 4. Templates And Skills

- [x] 4.1 Update the project template to use the formal check plan and known-bad proof gate.
- [x] 4.2 Update the risk-intent check-plan template to include structured known-bad proof rows.
- [x] 4.3 Update risk-template-library template/docs to separate known-bad declarations from executable model-instance proof.
- [x] 4.4 Update the installed/repository model-first Skill guidance and model template assets to remove direct-entry/fallback wording.

## 5. Tests And Migration Inventory

- [x] 5.1 Add or update unit tests for missing proof, passing known-bad proof failure, stale/skipped proof blocking, and protected-class mismatch.
- [x] 5.2 Update runner, risk plan, public template, API surface, and audit tests for the hard entry semantics.
- [x] 5.3 Add an inventory/audit check that reports direct-Explorer-only model scripts as upgrade-required.

## 6. Validation And Sync

- [x] 6.1 Run OpenSpec strict validation for this change and all changes.
- [x] 6.2 Run focused pytest/unittest suites for risk templates, plans, runner, audit, templates, and API surface.
- [x] 6.3 Run FlowGuard model regression scripts and broad test suites with long checks in background artifacts.
- [x] 6.4 Sync editable local install, installed FlowGuard skills, shadow workspace, and Git worktree version metadata.
- [x] 6.5 Record FlowGuard adoption evidence and KB postflight before final response.
