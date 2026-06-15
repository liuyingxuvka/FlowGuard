## 1. OpenSpec And FlowGuard Model Boundary

- [x] 1.1 Create OpenSpec proposal, design, and specs for real-flow payload evidence.
- [x] 1.2 Verify the real FlowGuard package and project adoption record before code edits.

## 2. Core Implementation

- [x] 2.1 Add an artifact payload execution-proof blocker for current external passing payload evidence without `evidence_ref` or `proof_artifact`.
- [x] 2.2 Keep payload validation backward-compatible for plans without payload contracts or evidence.
- [x] 2.3 Update serialized/report text and finding priority so missing execution proof is visible.

## 3. Guidance, Templates, And Docs

- [x] 3.1 Replace misleading fake file/work-package wording in skill prompts and protocols.
- [x] 3.2 Update Model-Test Alignment docs, API docs, and templates to say synthetic payload cases exercise the real payload surface.
- [x] 3.3 Update DevelopmentProcessFlow, PlanDetailing, TestMesh, AgentWorkflowRehearsal, RiskEvidenceLedger, and kernel guidance for real-surface proof.

## 4. Tests

- [x] 4.1 Add focused tests that reject payload evidence lacking execution proof.
- [x] 4.2 Update passing payload tests and templates to include `evidence_ref` or `proof_artifact`.
- [x] 4.3 Update skill/template coverage tests to check real-surface wording and reject fake-package wording.

## 5. Version And Sync

- [x] 5.1 Bump local package/docs metadata and refresh project adoption records.
- [x] 5.2 Sync current Gate workspace changes to the local source repository.
- [x] 5.3 Sync repository-managed FlowGuard skills to installed Codex skills.

## 6. Validation And Logging

- [x] 6.1 Run OpenSpec validation.
- [x] 6.2 Run focused pytest coverage and broad practical regression.
- [x] 6.3 Verify installed/source/Gate imports and skill content.
- [x] 6.4 Record FlowGuard adoption evidence and KB postflight.
