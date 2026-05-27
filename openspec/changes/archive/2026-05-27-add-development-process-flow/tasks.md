## 1. OpenSpec And FlowGuard Preflight

- [x] 1.1 Create the `add-development-process-flow` OpenSpec change.
- [x] 1.2 Write proposal, design, and capability spec artifacts.
- [x] 1.3 Add a FlowGuard rollout model for the development lifecycle route.
- [x] 1.4 Run the rollout model and OpenSpec strict validation before implementation claims.

## 2. Public Helper API

- [x] 2.1 Add `flowguard/development_process_flow.py` with artifact, action, evidence, requirement, recommendation, finding, report, and review APIs.
- [x] 2.2 Implement freshness, ordering, evidence status, routine/release, and minimum revalidation checks.
- [x] 2.3 Export the new public API through `flowguard/__init__.py` and API grouping constants.

## 3. Templates And CLI

- [x] 3.1 Add public development-process-flow template content and template writer function.
- [x] 3.2 Add the `development-process-flow-template` CLI command.
- [x] 3.3 Ensure generated templates execute and include Risk Purpose Header guidance.

## 4. Skill And Documentation

- [x] 4.1 Add the `development_process_flow` sibling route to the Skill Kernel.
- [x] 4.2 Create the detailed development-process-flow reference protocol.
- [x] 4.3 Update modeling protocol, agents snippet, API surface, productized helpers, README, changelog, and public docs.
- [x] 4.4 Preserve sibling-not-supervisor wording wherever the route references evidence from other routes.

## 5. Tests And Validation

- [x] 5.1 Add focused unit tests for happy path, stale evidence, verifier changes, upstream propagation, missing validation pairs, failed/progress-only evidence, and routine/release scope.
- [x] 5.2 Update public template, API surface, and Skill doc tests.
- [x] 5.3 Run targeted tests, OpenSpec validation, template execution, full test discovery, and git diff checks.

## 6. Synchronization And Closure

- [x] 6.1 Sync the implemented source set into the local git checkout.
- [x] 6.2 Verify the local editable install/import path and version from both workspaces.
- [x] 6.3 Review git status/diff in the git checkout and record adoption/Kb postflight evidence.
