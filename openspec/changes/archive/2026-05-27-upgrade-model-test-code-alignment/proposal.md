## Why

Model-Test Alignment currently reads as a direct comparison between FlowGuard
model obligations and ordinary tests, while the existing alignment surface also
needs to account for optional code external contracts. Without explicit prompt
guidance, agents may either miss the code-contract layer or route the work into
TestMesh, StructureMesh, or ModelMesh even though no test split, code split, or
model split is being requested.

## What Changes

- Upgrade the existing `model_test_alignment` Skill/protocol guidance so it can
  compare FlowGuard model obligations, optional code external contracts, and
  ordinary test evidence in one direct review.
- Add required prompt fields and findings for optional `CodeContract` rows,
  including owner bindings, externally visible inputs/outputs, state reads and
  writes, side effects, error paths, and test evidence that proves the external
  contract.
- Preserve the current boundary: Model-Test Alignment is not TestMesh,
  StructureMesh, or ModelMesh; it does not split tests, refactor code, split
  models, or read mesh reports.
- Update the Skill kernel, detailed protocol, modeling protocol, and AGENTS
  snippet so future agents upgrade the existing route instead of adding a
  parallel skill.
- Extend the public helper API, starter template, tests, and docs so
  `CodeContract` rows can be reviewed alongside `ModelObligation` and
  `TestEvidence` rows.

## Capabilities

### New Capabilities
- `model-test-alignment`: Defines the existing Model-Test Alignment route as a
  direct model obligation, optional code external contract, and ordinary test
  evidence comparison.

### Modified Capabilities
- None. No existing OpenSpec capability spec currently exists in
  `openspec/specs/`.

## Impact

- Public helper API and tests:
  `flowguard/model_test_alignment.py`, `flowguard/__init__.py`,
  `flowguard/templates.py`, `flowguard/__main__.py`, and focused unit/template
  tests.
- Skill/docs:
  `.agents/skills/model-first-function-flow/SKILL.md`,
  `.agents/skills/model-first-function-flow/references/model_test_alignment_protocol.md`,
  `docs/modeling_protocol.md`, `docs/agents_snippet.md`,
  `docs/model_test_alignment.md`, `docs/api_surface.md`, `README.md`, and
  `CHANGELOG.md`.
- OpenSpec artifacts under
  `openspec/changes/upgrade-model-test-code-alignment/`.
- No dependency, schema, TestMesh, StructureMesh, or ModelMesh changes.
