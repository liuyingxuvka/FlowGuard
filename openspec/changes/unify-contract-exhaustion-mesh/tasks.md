## 1. Core Contract Exhaustion API

- [x] 1.1 Add `flowguard/contract_exhaustion.py` with dimensions, mutation cases, oracles, plan, findings, report, review helper, and formatting/export helpers.
- [x] 1.2 Export the new public API from `flowguard/__init__.py` and update route starter/API registry surfaces if present.
- [x] 1.3 Add focused unit tests for ready, scoped, blocked, missing-oracle, unbounded-dimension, and undeclared-model-gap decisions.

## 2. Feeder Integrations

- [x] 2.1 Add StateClosure-to-contract-exhaustion projection for unknown, malformed, and missing-required-field cases.
- [x] 2.2 Add ScenarioMatrix-to-contract-exhaustion projection for repeat, delayed, ABA, stale-state, partial-failure, and terminal-replay challenge scenarios.
- [x] 2.3 Add ObligationFamily/AnalogousDefect seed projection so same-class sibling bad cases become canonical contract mutation cases.
- [x] 2.4 Add ArtifactPayload projection or payload case binding so missing body, missing evidence, wrong path, stale path, and conflicting payload evidence can use canonical case ids.
- [x] 2.5 Add transition and model-mesh closure projections for transition cells, stale child evidence, unconsumed child evidence, and repeat-without-delta cases.

## 3. Consumer Integrations

- [x] 3.1 Update Model-Test Alignment tests/docs or helpers so same-class, payload, and transition evidence can bind to canonical contract-exhaustion case ids.
- [x] 3.2 Update TestMesh tests/docs or helpers so required canonical case ids can be owned by child suites and progress-only evidence remains insufficient.
- [x] 3.3 Update ModelMesh/LayeredBoundaryProof tests/docs or helpers so parent-child finite case ids are consumed as proof requirements.
- [x] 3.4 Update RiskEvidenceLedger tests/docs or helpers so blocked contract-exhaustion reports prevent full confidence.
- [x] 3.5 Add composite handoff acceptance as an independent broad-claim gate so single-point matrix readiness is not misread as whole-chain readiness.

## 4. Skill And Prompt Routing

- [x] 4.1 Add `.agents/skills/flowguard-contract-exhaustion-mesh/SKILL.md` and reference material if needed.
- [x] 4.2 Update model-miss, field-lifecycle, model-test-alignment, test-mesh, model-mesh, model-first, development-process, and architecture-reduction skills to route canonical bad-case generation through ContractExhaustionMesh.
- [x] 4.3 Remove or rewrite old prompt wording that lets hand-written same-class cases or fallback prompt paths count as canonical coverage.

## 5. Documentation And Cleanup

- [x] 5.1 Update API and productized-helper docs to list the new public API and explain feeder/consumer ownership.
- [x] 5.2 Update modeling, scenario sandbox, obligation-family, model-miss, model-test-alignment, test evidence mesh, model mesh, layered proof, risk ledger, and AGENTS snippet docs.
- [x] 5.3 Add architecture-reduction cleanup notes for old same-class generators, fallback aliases, and compatibility-like surfaces.
- [x] 5.4 Update adoption logs/topology where required by project rules.

## 6. Validation And Synchronization

- [x] 6.1 Run focused contract-exhaustion and affected feeder/consumer tests.
- [x] 6.2 Run broader FlowGuard regression checks and `python -m flowguard project-audit --root .`.
- [x] 6.3 Sync repository skill updates to `$CODEX_HOME/skills` and verify installed skill contents.
- [x] 6.4 Check for a local git/source mirror, synchronize if available without reverting other agents, and report if this workspace has no git metadata.
- [x] 6.5 Run final OpenSpec status/validation and record KB postflight.
