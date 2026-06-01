# Tasks

## 1. State Closure Helper

- [x] 1.1 Add state closure row types, constants, automatic inference, review
  decision logic, report formatting, and public exports.
- [x] 1.2 Add unit tests for inferred unknown dimensions, explicit safe
  handling, unsafe handling, and side effects before resolution.

## 2. Default Runner and Maintenance Routing

- [x] 2.1 Add an automatic `state_closure` section to
  `run_model_first_checks(...)`.
- [x] 2.2 Add a maintenance scan signal that routes closure gaps to
  `model_maturation_loop`.
- [x] 2.3 Update API surface tests and route registry coverage.

## 3. Models, Docs, and Prompt Guidance

- [x] 3.1 Add a FlowGuard self-model for the state closure gate.
- [x] 3.2 Update modeling protocol, productized helper docs, API docs, README,
  AGENTS snippet, and relevant skill prompt references.
- [x] 3.3 Add OpenSpec requirements and validate the change.

## 4. Validation and Sync

- [x] 4.1 Run focused tests and FlowGuard self-model checks.
- [x] 4.2 Run practical full regression in the background and collect artifacts.
- [x] 4.3 Bump/sync versions, editable install, project adoption records,
  shadow workspace, local git commit, and local git tag.
