## Why

Model-Test Alignment can already compare declared `ModelObligation`,
`CodeContract`, and `TestEvidence` rows, but those rows are still mostly
hand-authored. Agents need a conservative next layer that audits real Python
source and real Python tests to see whether the declared external contracts are
supported by observable code and assertions.

## What Changes

- Add a conservative source-audit evidence capability for Python projects.
- Define how AST-based code audits can generate or verify code-contract
  evidence for real functions, classes, methods, CLIs, adapters, and persisted
  outputs.
- Define how AST-based test audits can generate or verify test-assertion
  evidence for real Python tests and their external-contract assertions.
- Feed audited evidence into the existing Model-Test Alignment review so model,
  code, and test claims are compared in one three-way report.
- Preserve strict boundaries: the audit is not a perfect semantic prover, does
  not replace conformance replay, and must mark complex, dynamic, or ambiguous
  behavior for manual review.

## Capabilities

### New Capabilities

- `contract-audit-evidence`: Defines conservative Python source/test audit
  evidence that can support or challenge declared code contracts and test
  evidence before Model-Test Alignment compares them with model obligations.

### Modified Capabilities

- None. No existing OpenSpec capability spec currently exists in
  `openspec/specs/`.

## Impact

- OpenSpec artifacts under
  `openspec/changes/add-contract-audit-evidence/`.
- Protocol and public docs:
  `.agents/skills/model-first-function-flow/references/model_test_alignment_protocol.md`,
  `docs/model_test_alignment.md`, `docs/api_surface.md`,
  `docs/agents_snippet.md`, and `docs/modeling_protocol.md`.
- Future implementation surface is expected to include Python AST auditing
  helpers that produce conservative `CodeContract` and `TestEvidence`
  candidates plus manual-review findings. No dependency or schema-version
  change is required by this proposal.
