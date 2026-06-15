## 1. Formal self-runner

- [x] 1.1 Add a reusable formal workflow-suite runner that builds
  `FlowGuardCheckPlan` with Risk Intent, minimum model contract, template reuse,
  template harvest closure, and current known-bad proof rows.
- [x] 1.2 Add tests proving the helper fails when a bad workflow is not caught
  and passes when correct and known-bad cases align.

## 2. Self-model runner cleanup

- [x] 2.1 Replace current `.flowguard/*/run_checks.py` direct `Explorer(...)`
  calls with the formal runner helper.
- [x] 2.2 Update README or prompt examples that still present direct
  `Explorer(...)` as the user-facing model entry.

## 3. Validation and maintenance closure

- [x] 3.1 Validate the OpenSpec change and all specs.
- [x] 3.2 Run adoption audit, focused formal-runner tests, self-model
  regressions, and practical unit regression.
- [x] 3.3 Sync package version, local editable install, installed FlowGuard
  skills, shadow workspace, and local git evidence.
- [x] 3.4 Archive completed OpenSpec changes after validation when no unchecked
  tasks remain.
