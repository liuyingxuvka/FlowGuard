## 1. OpenSpec And FlowGuard Model Setup

- [x] 1.1 Validate the OpenSpec change artifacts under `add-runtime-path-evidence`.
- [x] 1.2 Add a FlowGuard rollout model for runtime path evidence and run its checks before production helper changes.
- [x] 1.3 Record the runtime path evidence risk purpose and expected broken variants in the rollout model.

## 2. Runtime Path Evidence Core

- [x] 2.1 Add `flowguard/runtime_path.py` with runtime node contracts, observations, path runs, alignment plans, findings, reports, and recorder APIs.
- [x] 2.2 Add serialization, model-identifying progress formatting, proof artifact checks, exact path checks, ordering checks, and behavior-boundary checks.
- [x] 2.3 Export the new APIs through `flowguard/__init__.py` under modeling helpers without expanding the core API.
- [x] 2.4 Add focused unit tests for successful path alignment and missing, extra, stale, non-passing, order, binding, and proof artifact gaps.

## 3. Existing Helper Integration

- [x] 3.1 Integrate runtime path contracts and observations into Model-Test Alignment.
- [x] 3.2 Integrate runtime path evidence ids into layered boundary proof leaf matrix cells.
- [x] 3.3 Integrate child runtime path evidence ids into hierarchical ModelMesh child evidence and reattachment.
- [x] 3.4 Integrate runtime node bindings into Runtime Gateway Adoption write observations.
- [x] 3.5 Integrate runtime path alignment reports into FlowGuard Closure Contract.
- [x] 3.6 Add workflow step contract metadata for runtime node ids.

## 4. Templates, CLI, Docs, And Skills

- [x] 4.1 Add a runtime path evidence template and CLI template command.
- [x] 4.2 Update docs for runtime path evidence, model-test alignment, hierarchical mesh, layered proof, runtime gateway adoption, closure contract, workflow step contracts, and API surface.
- [x] 4.3 Update `.agents/skills` and `docs/agents_snippet.md` guidance so agents require runtime path evidence for leaf code boundaries and broad parent/runtime confidence.
- [x] 4.4 Add or update public template and skill documentation tests.

## 5. Validation And Synchronization

- [x] 5.1 Run OpenSpec strict validation for the change.
- [x] 5.2 Run focused FlowGuard tests for runtime path evidence and all touched helper integrations.
- [x] 5.3 Run template execution tests and skill documentation tests.
- [x] 5.4 Run broad regression, using background execution where practical and collecting final exit/output artifacts before claiming completion.
- [x] 5.5 Sync the finished workspace changes to the local git source repository without reverting peer-agent work.
- [x] 5.6 Refresh local editable install/version checks and verify imports from both the source repository and shadow workspace.
- [x] 5.7 Record FlowGuard adoption evidence and KB postflight observations.
