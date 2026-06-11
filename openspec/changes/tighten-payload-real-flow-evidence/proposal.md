## Why

FlowGuard 0.42.0 added artifact payload contracts so synthetic files and AI
work-package cases could validate payload-bearing flows. The wording and tests
still let agents treat those synthetic cases as standalone fake packages rather
than as inputs that exercise the real import/export/save/load/generate path.

## What Changes

- Require artifact payload evidence to prove the real user-visible payload
  surface, not just a declared payload case row.
- Block current external payload evidence that lacks an execution proof such as
  an evidence reference, proof artifact, runtime path observation, or explicit
  owner-code-contract execution binding.
- Replace misleading "fake file/work-package" wording with "synthetic payload
  cases for the real payload surface" in skills, templates, and docs.
- Update template and skill tests so future prompt changes preserve this
  boundary.
- Sync repository, Gate workspace, and installed Codex skill surfaces after the
  change is implemented.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-test-alignment`: Artifact payload validation must require real-flow
  execution proof before payload evidence can support alignment confidence.
- `flowguard-codex-skill-satellites`: Installed and repository skill guidance
  must describe synthetic payload cases as inputs to real surfaces, not
  standalone fake package paths.
- `development-process-flow`: Payload freshness language must track real
  payload surfaces and validation prompts, not fake package artifacts.
- `plan-detailing-compiler`: Plans that touch files or work packages must name
  the real payload surface, cases, and proof boundary.
- `test-evidence-mesh`: Large payload matrices may own case execution evidence,
  while Model-Test Alignment still decides whether real-flow behavior satisfies
  the contract.
- `risk-evidence-ledger`: Final confidence must consume current real-flow
  payload proof or a scoped blindspot.

## Impact

Affected surfaces include `flowguard.model_test_alignment`, generated
Model-Test Alignment templates, route protocols, Codex skill prompts, public
docs, API docs, tests, OpenSpec artifacts, local installed skills, and the
local source/Gate workspace synchronization process.
