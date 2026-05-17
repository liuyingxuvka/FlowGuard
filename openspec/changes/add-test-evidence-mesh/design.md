## Context

FlowGuard's existing hierarchical mesh can model parent/child model evidence.
Test suites need the same treatment, but tests are not models: they have
commands, exit artifacts, selected test counts, skip/timeout states, file
freshness, and routine/release gates. The correct abstraction is therefore a
TestMesh evidence model inside FlowGuard, plus project-local adapters that run
pytest, unittest, Playwright, simulation checks, or shell commands.

## Goals / Non-Goals

**Goals:**

- Treat a test hierarchy as a parent/child evidence mesh.
- Let projects declare which test suite owns each validation partition.
- Detect missing owners, duplicate ownership, stale evidence, hidden skipped
  tests, progress-only background runs, and insufficient evidence tier.
- Keep routine confidence separate from release confidence.
- Provide a starter template and skill guidance for agents.

**Non-Goals:**

- Do not make FlowGuard a general-purpose test runner.
- Do not add pytest, unittest, or CI dependencies.
- Do not auto-discover every project's tests in core.
- Do not replace real test execution; TestMesh validates whether test evidence
  can be trusted.

## Decisions

1. Add TestMesh as a FlowGuard helper/reporting API.
   - Rationale: it is evidence governance, like hierarchical model mesh, not a
     core state-space exploration primitive.

2. Keep project-specific execution outside FlowGuard core.
   - Rationale: every project has different runners and log contracts. FlowGuard
     should model evidence shape and trust rules, not own shell orchestration.

3. Represent test groups as partition items plus suite evidence.
   - Rationale: parents need to know which suite owns a behavior/state area and
     whether the corresponding evidence is current.

4. Make background completion explicit.
   - Rationale: progress output is liveness evidence only. A TestMesh green
     decision requires exit/result evidence when a background run is used.

5. Distinguish routine and release scope.
   - Rationale: fast foreground confidence should not be blocked by release-only
     suites, but release confidence must expose missing full regression evidence.

## Risks / Trade-offs

- [Risk] Projects may treat TestMesh as a substitute for tests. -> Mitigation:
  docs and skill prompts say TestMesh validates evidence trust; real runners
  remain project adapters.
- [Risk] Test partition maps drift. -> Mitigation: include touched path and
  freshness fields, plus explicit stale evidence findings.
- [Risk] The template becomes too narrow. -> Mitigation: keep core dataclasses
  generic and runner-agnostic.

## Migration Plan

1. Add `flowguard.testmesh` helper dataclasses and `review_test_mesh`.
2. Export APIs from `flowguard.__init__`.
3. Add focused unit tests for required bad variants.
4. Add `test-mesh-template` CLI output.
5. Update docs, README, API surface, agents snippet, changelog, and skill
   guidance.
6. Apply the template in FlowPilot as a separate project adapter after the core
   API is validated.
