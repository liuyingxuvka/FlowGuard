## 1. OpenSpec And Model

- [x] 1.1 Record proposal, design, spec, and tasks for plan-intake and claim hardening.
- [x] 1.2 Model the upgrade route and map the helper boundaries to existing FlowGuard routes.

## 2. Core API

- [x] 2.1 Add plan-intake completeness dataclasses, report type, and review helper.
- [x] 2.2 Add evidence-adapter conformance dataclasses, report type, and review helper.
- [x] 2.3 Add false-negative backpropagation dataclasses, report type, and review helper.
- [x] 2.4 Add plan mutation review dataclasses, report type, and review helper.
- [x] 2.5 Add typed FlowGuard claim-chain dataclasses, report type, and review helper.
- [x] 2.6 Export the helper APIs through `flowguard.__init__`, `__all__`, and API surface groups.

## 3. Docs And Skills

- [x] 3.1 Add public API/protocol docs explaining when these helpers are required.
- [x] 3.2 Update model-first skill guidance so repeated issues route to plan intake,
      adapter conformance, false-negative backpropagation, mutation review, and
      typed claim-chain checks before broad confidence claims.
- [x] 3.3 Update release notes and package version.

## 4. Validation

- [x] 4.1 Add focused tests for green paths and known-bad omissions.
- [x] 4.2 Run OpenSpec validation for the change.
- [x] 4.3 Run focused package tests.
- [x] 4.4 Run broader/background regression checks and inspect final artifacts.

## 5. Sync

- [x] 5.1 Sync the local editable installation.
- [x] 5.2 Verify installed import path/version and schema version.
- [x] 5.3 Commit local git changes without reverting parallel work.
- [x] 5.4 Run KB postflight and record reusable lessons if any.
