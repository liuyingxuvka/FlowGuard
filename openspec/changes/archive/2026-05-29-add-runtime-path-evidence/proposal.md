## Why

FlowGuard can already model expected traces, align tests to obligations, and
review parent/child model evidence, but real code and tests can still execute a
different workflow from the model while only producing ordinary pass/fail
evidence. Runtime path evidence closes that gap by making real runs emit
structured workflow-node observations that can be compared with model
obligations, leaf matrices, and parent mesh handoffs.

## What Changes

- Add a first-class runtime path evidence layer for structured real-code node
  observations, observed run paths, expected node contracts, and path alignment
  reports.
- Require lowest-level leaf model code boundaries to provide runtime node
  evidence when parent or production confidence depends on real code behavior.
- Let Model-Test Alignment consume runtime path observations alongside model
  obligations, code contracts, boundary observations, and test evidence.
- Let ModelMesh and layered boundary proof consume child runtime path evidence
  without inlining every child model's internal graph.
- Let Runtime Gateway Adoption and Closure Contract bind critical state writes
  and final confidence to current runtime path evidence.
- Add templates, docs, CLI surface, public API exports, tests, and skill
  guidance so future agents collect path evidence instead of relying on ad hoc
  logs or prose.

## Capabilities

### New Capabilities
- `runtime-path-evidence`: Structured runtime node contracts, observations,
  run paths, expected-vs-observed path alignment, leaf model bindings, proof
  artifacts, and report findings.

### Modified Capabilities
- `model-test-alignment`: Model/test/code alignment can require runtime path
  observations for in-scope model obligations and code contracts.
- `hierarchical-model-mesh`: Parent/child model confidence can consume child
  runtime path evidence ids and block stale or unreattached child paths.
- `layered-boundary-proof`: Leaf boundary matrices can require runtime path
  evidence for finite `Input x State -> Set(Output x State)` cells.
- `runtime-gateway-adoption`: Runtime gateway write observations can bind to
  runtime node ids so critical writes are linked to modeled path evidence.
- `flowguard-closure-contract`: Broad completion or production confidence can
  require current runtime path alignment evidence.
- `workflow-step-contracts`: Step contract metadata can map completed workflow
  steps to runtime node contracts and observations.

## Impact

- New module and public helper APIs under `flowguard/runtime_path.py`.
- Updates to existing helper APIs in model-test alignment, hierarchy,
  layered proof, runtime gateway, closure contract, templates, and CLI.
- New and updated OpenSpec specs, docs, `.agents/skills` guidance, and tests.
- No external dependency is introduced; the feature remains standard-library
  only and evidence rows are plain serializable Python dataclasses.
