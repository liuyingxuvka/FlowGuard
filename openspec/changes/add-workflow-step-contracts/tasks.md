## 1. Core Step Contract API

- [x] 1.1 Add `flowguard.step_contracts` with contract dataclasses, receipt metadata helpers, trace review, invariant compilation, process projection, alignment projection, and conformance rule helpers.
- [x] 1.2 Export the public step-contract API from `flowguard.__init__`.

## 2. Runner And Plan Integration

- [x] 2.1 Add `step_contracts` to `FlowGuardCheckPlan` serialization and text output.
- [x] 2.2 Integrate compiled step-contract invariants and a `workflow_step_contracts` summary section into `run_model_first_checks(...)`.

## 3. Route Integration

- [x] 3.1 Ensure projected DevelopmentProcessFlow validation requirements can be reviewed by existing process helpers.
- [x] 3.2 Ensure projected Model-Test Alignment obligations can be reviewed by existing alignment helpers.
- [x] 3.3 Add conformance replay metadata checks for expected versus observed step-contract receipts.

## 4. Docs And Templates

- [x] 4.1 Add documentation and a public template command for workflow step contracts.
- [x] 4.2 Update README and public template coverage so users can discover the new path.

## 5. Validation And Sync

- [x] 5.1 Add focused tests for good traces, skipped steps, stale receipts, claim gates, runner integration, DPF projection, MTA projection, and conformance metadata mismatch.
- [x] 5.2 Run targeted tests and the strongest practical model/test regression set.
- [x] 5.3 Bump version, refresh editable install, verify import metadata, and sync the git source workspace with the shadow workspace without reverting peer changes.
