## 1. OpenSpec And Model Grounding

- [x] 1.1 Confirm the new change is independent from existing active changes
- [x] 1.2 Verify the real FlowGuard package and project adoption record before implementation
- [x] 1.3 Identify existing model/prompt surfaces affected by the new satellite

## 2. Core Package Implementation

- [x] 2.1 Add `flowguard.agent_workflow_rehearsal` data models and review helper
- [x] 2.2 Export the new helper API from the package where appropriate
- [x] 2.3 Add representative positive, scoped, blocked, revision, and over-trigger outcomes

## 3. Executable Rehearsal Model

- [x] 3.1 Add `examples/flowguard_agent_workflow_rehearsal/model.py`
- [x] 3.2 Add `examples/flowguard_agent_workflow_rehearsal/run_review.py`
- [x] 3.3 Cover fresh snapshot, skipped skill, wrong order, weak validation, stale cache, missing rework gate, overbroad claim, and over-trigger hazards

## 4. Codex Skill And Prompt Surfaces

- [x] 4.1 Add `.agents/skills/flowguard-agent-workflow-rehearsal/SKILL.md`
- [x] 4.2 Add the satellite reference protocol and `agents/openai.yaml`
- [x] 4.3 Update `model-first-function-flow` route map without making it a global orchestrator
- [x] 4.4 Update `docs/agents_snippet.md` with direct routing and fresh snapshot rules

## 5. Tests And Validation

- [x] 5.1 Add focused tests for the new package helper and example review
- [x] 5.2 Update skill topology/documentation tests for the new satellite
- [x] 5.3 Run focused model, skill, and OpenSpec checks
- [x] 5.4 Run practical broader regression checks required for confidence

## 6. Synchronization And Adoption Evidence

- [x] 6.1 Sync the new repository skill to the installed Codex skills directory
- [x] 6.2 Verify installed skill surface and local editable package import
- [x] 6.3 Locate the local git source checkout and synchronize the same source set without overwriting unrelated peer work
- [x] 6.4 Record FlowGuard adoption evidence with commands, findings, skipped gaps, and next actions
