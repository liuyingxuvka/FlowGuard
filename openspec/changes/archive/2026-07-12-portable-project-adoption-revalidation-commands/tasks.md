## 1. Portable Command Owner

- [x] 1.1 Remove the target-path dependency from `_minimum_revalidation` and emit canonical `--root .` commands for every report and log consumer.

## 2. Regression Evidence

- [x] 2.1 Add focused coverage proving report revalidation commands use `--root .` and do not contain a nested temporary absolute root.
- [x] 2.2 Prove the written Markdown adoption log contains portable next actions and does not contain the temporary target's absolute root.

## 3. Validation

- [x] 3.1 Run the focused project-adoption tests, existing project-adoption FlowGuard model, and strict OpenSpec validation before final verification.
