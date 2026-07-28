## Why

FlowGuard already has several partial bad-case generators: state closure,
scenario challenge patterns, analogous defect scans, payload cases, transition
coverage cells, and model-mesh retry/reattachment hazards. These paths can
drift because each route names, expands, and proves "same-class" or boundary
cases in its own language.

This change introduces one canonical finite contract-exhaustion path so a
declared model, field, payload, evidence, transition, parent/child, or
same-class boundary expands into stable bad-case ids with explicit expected
runtime responses. The goal is a clean route, not another compatibility layer.

## What Changes

- Add `ContractExhaustionMesh` as the canonical bad-case generation layer for
  declared finite FlowGuard contract boundaries.
- Add public API objects for contract dimensions, mutation cases, oracles,
  plans, reports, findings, and feeder conversions.
- Convert existing state-closure, scenario-matrix, obligation-family,
  artifact-payload, transition-coverage, and model-mesh closure case sources
  into feeders or consumers of canonical `ContractMutationCase` ids.
- Keep BugFamily, ModelMissReview, Model-Test Alignment, TestMesh, ModelMesh,
  LayeredBoundaryProof, ArchitectureReduction, and RiskEvidenceLedger as their
  existing owners for classification, validation, closure, reduction, and final
  confidence.
- Require every generated case to have an oracle. Missing oracles, unbounded
  dimensions, and undeclared similarity become blockers or scoped confidence,
  not implicit passes.
- **BREAKING**: Route prompts, docs, and helpers may no longer treat hand-written
  same-class bad cases as canonical coverage when a contract-exhaustion case is
  required.
- **BREAKING**: No fallback path may preserve old same-class generators,
  fallback prompt wording, old field aliases, or compatibility-like wrappers as
  parallel canonical case-generation routes.
- Add tests proving the new route catches broken cases and that old case
  sources are projected into the canonical matrix instead of bypassing it.
- Update installed and repository skill copies so agents route future same-class
  and finite boundary exhaustion through the same path.

## Capabilities

### New Capabilities
- `contract-exhaustion-mesh`: Canonical finite bad-case generation from declared
  model, field, payload, evidence, transition, parent/child, and same-class
  bug-family boundaries.

### Modified Capabilities
- `adversarial-scenario-synthesis`: Scenario challenge patterns become feeders
  into contract-exhaustion cases instead of a competing proactive bug-discovery
  authority.
- `field-lifecycle-mesh`: Behavior-bearing and old/replaced fields can project
  required mutation cases into contract exhaustion.
- `model-test-alignment`: Same-class, payload, transition, and boundary
  evidence can bind to canonical contract-exhaustion case ids.
- `obligation-family-parity-provenance`: Family bad-case seeds and analogous
  defect scans provide family inputs but no longer own canonical bad-case
  expansion.
- `post-runtime-model-miss-review`: Model-miss repair must upgrade the model
  rule and route same-class bad-case generation through contract exhaustion.
- `test-evidence-mesh`: Required transition, payload, and contract-exhaustion
  case ids can become child-suite evidence obligations.
- `hierarchical-model-mesh`: Parent/child stale evidence, missing reattachment,
  and retry/no-delta closure hazards can feed contract-exhaustion cases.
- `layered-boundary-proof`: Leaf boundary proof can consume canonical finite
  case ids as leaf matrix evidence requirements.
- `risk-evidence-ledger`: Final risk rows can require current
  ContractExhaustionMesh evidence and block full confidence on missing oracles
  or model gaps.
- `architecture-reduction`: Old same-class generators, fallback prompt paths,
  aliases, and wrappers are cleanup candidates unless proven to be current
  public contracts or safety classifiers.
- `development-process-flow`: Contract-exhaustion reports and verifier
  artifacts become freshness-sensitive lifecycle evidence.
- `flowguard-codex-skill-satellites`: Add the thin
  `flowguard-contract-exhaustion-mesh` satellite skill and update sibling skill
  routing language.

## Impact

- Affected package modules include new `flowguard/contract_exhaustion.py`,
  public exports in `flowguard/__init__.py`, and feeder integrations in
  `state_closure`, `scenario_matrix`, `obligation_family`,
  `model_test_alignment`, `transition_coverage`, and model-mesh/closure helper
  surfaces as needed.
- Affected tests include new contract-exhaustion unit tests plus targeted
  updates for state closure, scenario matrix, obligation family, payload
  validation, transition coverage, test mesh, model mesh, and risk ledger.
- Affected documentation includes the modeling protocol, productized helpers,
  API surface, scenario sandbox, obligation-family parity, model-miss review,
  model-test alignment, test evidence mesh, model mesh, layered proof, risk
  ledger, and AGENTS snippet.
- Affected installed skills include the new repository skill and the synced
  `$CODEX_HOME/skills` copy.
- No new runtime dependency is expected.
