## Context

FlowGuard has strong route-specific validation surfaces: UI Flow Structure owns
UI state/control journeys, Model-Test Alignment owns model/code/test binding,
TestMesh owns large validation hierarchies, DevelopmentProcessFlow owns
freshness, and RiskEvidenceLedger owns final confidence. The missing piece is a
clear cross-route contract for evidence that comes from user-visible actions or
external payloads.

Today a runnable UI claim can require click-through evidence, but the top-level
guidance is weaker than the detailed protocol. File import/export and AI
work-package checks are even more scattered: they appear as test evidence,
fixtures, source-audit notes, or freshness concerns, not as a named payload
contract that final claims can consume.

## Goals / Non-Goals

**Goals:**

- Make UI action completion explicit: every reachable actionable control/event
  needs real run evidence, pure-UI classification, or a scoped blindspot.
- Add artifact payload contracts and evidence to Model-Test Alignment for
  files, import/export, round trips, and AI work packages.
- Let large payload matrices flow through TestMesh child-suite ownership.
- Make DevelopmentProcessFlow stale old evidence when payload schemas, UI
  action maps, prompts, installed skills, or verifier artifacts change.
- Teach the same boundary in installed Codex skills, generated templates, docs,
  OpenSpec specs, and API surface docs.
- Keep manual review conditional: required when automation cannot inspect the
  real boundary, not for every ordinary task.

**Non-Goals:**

- Do not introduce a new satellite skill in this change.
- Do not make manual review mandatory for trivial or fully automated checks.
- Do not build a parser or validator for every file format.
- Do not make TestMesh decide semantic model coverage; Model-Test Alignment
  remains the semantic owner.
- Do not claim exhaustive security validation from representative payload packs.

## Decisions

1. **Use a cross-route gate plus route-local owners.**
   `validation-evidence-gates` defines the shared claim boundary. UI evidence
   remains in UI Flow Structure, payload semantics remain in Model-Test
   Alignment, hierarchy remains in TestMesh, freshness remains in
   DevelopmentProcessFlow, and final broad confidence remains in
   RiskEvidenceLedger.

2. **Add payload contracts inside Model-Test Alignment.**
   Artifact payloads are external contract evidence, not a new route. The new
   helper layer should resemble code-boundary conformance: a contract declares
   expected payload cases and effects, evidence reports observed results, and
   the review blocks missing, stale, non-passing, or mismatched evidence.

3. **Use representative packs, not universal enumeration.**
   A payload pack must name the representative cases that matter for the claim:
   valid minimum, empty/missing, malformed, unknown-field, old-version,
   round-trip, large, and boundary/security cases when in scope. Claims remain
   scoped when the pack intentionally omits cases.

4. **Make manual evidence structured.**
   Manual checks count only when they name the UI/payload boundary, steps,
   result, evidence reference, current revision, and validation boundary. Prose
   without those fields remains a scoped note.

5. **Version and sync as evidence-sensitive artifacts.**
   Skill guidance, generated templates, OpenSpec artifacts, local installed
   skills, editable install state, package version, and any git/shadow
   workspace sync are process artifacts. Later writes stale earlier evidence.

## Risks / Trade-offs

- [Risk] Agents may treat payload packs as exhaustive correctness. ->
  Mitigation: docs and reports state that packs are representative evidence and
  must name scoped omissions.
- [Risk] The API grows too broad. -> Mitigation: keep payload review as a
  compact helper in Model-Test Alignment and use TestMesh only for hierarchy.
- [Risk] Manual review becomes noisy. -> Mitigation: make manual review a
  conditional fallback for boundaries automation cannot observe.
- [Risk] Prompt updates diverge between repository and installed skills. ->
  Mitigation: sync installed skills and verify content before claiming active
  installed behavior.

## Migration Plan

1. Add OpenSpec specs and a FlowGuard rollout model for the new gate behavior.
2. Add payload contract/evidence helper classes and Model-Test Alignment
   integration.
3. Update TestMesh, DevelopmentProcessFlow, PlanDetailing, RiskEvidenceLedger,
   and UI guidance to consume or preserve the new evidence ids.
4. Update templates, docs, AGENTS adoption snippets, and installed skills.
5. Run focused tests, template execution tests, FlowGuard rollout checks,
   OpenSpec validation, package import/version checks, editable install sync,
   and source-repo/git sync where a real git repository exists.

## Open Questions

- If no local git repository is available for the active workspace, sync should
  target the nearest real FlowGuard source mirror and report any unsynced
  workspace explicitly.
