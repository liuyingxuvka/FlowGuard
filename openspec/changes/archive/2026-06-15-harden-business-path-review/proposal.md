## Why

FlowGuard can already prove local workflow traces and topology hazards, but a
green model can still hide business-path problems: two paths may do the same
business job, conflict for the same input, remain reachable only as dead legacy
surface, or leave only one genuinely useful path. This change strengthens the
existing workflow without creating a new route family.

## What Changes

- Add business-path identity metadata to model topology, similarity, and
  runtime path evidence so each important path can name its intent, trigger,
  terminal result, state writes, side effects, equivalents, exclusions, and
  legacy disposition.
- Extend model-topology hazard review to infer anchored duplicate, conflicting,
  unproven, and legacy-disposition business-path hazards.
- Extend model similarity consolidation to compare business-path identity
  across sibling models and adapter/shared-kernel candidates.
- Extend runtime path evidence to bind real-code observations to the expected
  business path, not only to a runtime node id.
- Extend maintenance scan routing so unresolved business-path hazards reopen
  existing owner routes such as Model Maturation, Model-Test Alignment,
  Architecture Reduction, Risk Evidence Ledger, or Model Similarity.
- Update model-first prompts, route prompt templates, public templates, docs,
  and API exports so future models capture path identity by default.
- Add focused tests and template checks for known-bad duplicate, conflict,
  dead/unproven, wrong-runtime-path, and old/new path disposition cases.

## Capabilities

### New Capabilities

None. Business-path review is implemented as cross-cutting metadata and checks
inside existing FlowGuard routes, not as a new workflow family.

### Modified Capabilities

- `model-first-function-flow`: Require important model paths to capture
  business intent, trigger, terminal, state writes, side effects, equivalence,
  exclusivity, and old/new disposition when path semantics affect confidence.
- `model-similarity-consolidation`: Include business-path identity in relation
  classification, evidence, maintenance groups, and duplicate/false-friend
  guidance.
- `runtime-path-evidence`: Require runtime observations to bind to expected
  business-path identity when a claim depends on external real-code paths.
- `maintenance-scan-router`: Route unresolved duplicate/conflict/unproven
  business-path signals to existing owner routes.
- `risk-evidence-ledger`: Allow final confidence rows to require current
  business-path hazard evidence through existing topology and runtime gates.

## Impact

- Affected package modules: `flowguard/topology_hazard.py`,
  `flowguard/model_similarity.py`, `flowguard/runtime_path.py`,
  `flowguard/maintenance_scan.py`, `flowguard/runner.py`,
  `flowguard/plan.py`, `flowguard/__init__.py`, and template exports.
- Affected documentation and prompts: model-first skill guidance, topology
  hazard prompt/protocol, route docs, API surface docs, AGENTS snippet, and
  public template text.
- Affected tests: topology hazard, model similarity, runtime path evidence,
  maintenance scan, runner/API surface, and public template tests.
- No external dependencies and no new standalone FlowGuard route.
