## 1. Closure Model Core

- [x] 1.1 Add and run a small FlowGuard self-model for the mesh closure design before trusting the implementation.
- [x] 1.2 Add mesh closure dataclasses and report formatting in the ModelMesh module.
- [x] 1.3 Implement closure review for root entries, child outputs, unknown references, consumers, terminal dispositions, joins, and out-of-scope rationales.
- [x] 1.4 Add loop/progress visibility for retry or wait-like closure transitions.
- [x] 1.5 Export the new closure APIs from the package public surface.

## 2. ModelMesh Integration

- [x] 2.1 Add an optional closure model field to parent partition maps.
- [x] 2.2 Make parent mesh green confidence consume the closure report when a closure model is declared.
- [x] 2.3 Surface closure blocker decisions distinctly from existing coverage, reattachment, and evidence blockers.

## 3. Tests And Examples

- [x] 3.1 Add green-path tests for complete parent/child closure.
- [x] 3.2 Add hazard tests for missing root entry, unconsumed child output, incomplete join, terminal leak, out-of-scope without rationale, and loop without progress.
- [x] 3.3 Add a parent mesh integration test where all existing mesh checks pass but closure blocks green confidence.
- [x] 3.4 Update the hierarchical ModelMesh example to demonstrate closure metadata.

## 4. Documentation And Skill Sync

- [x] 4.1 Update ModelMesh protocol and hierarchical docs with closure model rules.
- [x] 4.2 Update modeling/API docs, README, changelog, and public templates where the new API is surfaced.
- [x] 4.3 Update installed/repo FlowGuard skill text so agents know parent green confidence requires closure model evidence for whole-flow claims.

## 5. Validation And Workspace Sync

- [x] 5.1 Run focused ModelMesh, loop, workflow, API, template, and skill-doc tests.
- [x] 5.2 Run broader regression and model checks practical for this workspace.
- [x] 5.3 Mirror touched files into the local git checkout without overwriting unrelated dirty files.
- [x] 5.4 Refresh the editable install and verify imports/API from both local workspaces.
- [x] 5.5 Record final status, residual risk, and KB postflight observation.
