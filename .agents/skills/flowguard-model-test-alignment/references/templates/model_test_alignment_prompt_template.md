# Model-Test Alignment Prompt Template

```text
Build a FlowGuard Model-Test Alignment review for this repository.

Treat the FlowGuard model as the obligation source and ordinary tests as
evidence. If an externally visible code surface is in scope, include optional
code external contracts as plain alignment rows between the model obligations
and tests. Do not invoke TestMesh, StructureMesh, ModelMesh, split tests, split
code, split models, or read mesh reports.
List each model obligation, optional code contract, and current test evidence.

Model obligations:
- id:
- type:
- required:
- required test kinds:
- shared evidence allowed:
- shared implementation allowed:
- external inputs/outputs:
- state reads/writes:
- side effects:
- error paths:
- exact external contract:
- description:

Code external contracts (optional; include only when in scope):
- id:
- path/symbol/surface type:
- role:
- implements obligation ids:
- required:
- external inputs/outputs:
- state reads/writes:
- side effects:
- error paths:

Code boundary conformance (optional; include when a code surface must be closed):
- boundary id:
- code contract id:
- model obligation id:
- allowed input cases:
- rejected input cases:
- allowed outputs/state writes/side effects/error paths:
- exact boundary:
- observations:

Test evidence:
- id:
- test name/path/command:
- status:
- current or stale:
- test kind:
- covered obligation ids:
- covered code contract ids:
- assertion scope:
- overclaiming:
- model-miss closure role:
- source-audit notes:

If real Python source or tests are available, first perform a conservative AST
audit of code contracts and test assertions. Use it to generate or check the
CodeContract and TestEvidence rows, but do not treat it as a perfect semantic
proof or a conformance replay substitute.

For post-runtime model-miss repairs, mark observed-regression and same-class
generalized evidence separately. Do not let the observed regression substitute
for same-class closure evidence.

Flag missing model-obligation coverage, missing or mismatched code external
contracts, boundary observations that accept forbidden inputs or emit
undeclared behavior, missing external-contract test evidence, orphan tests,
orphan code contracts, unknown references, duplicate same-kind test claims,
duplicate code contract owners, internal-path-only tests, model-code-test
binding mismatches, happy-path-only coverage for risky obligations, stale or
non-passing evidence, partial source-audit support, dynamic or ambiguous
source-audit findings, manual-review-required findings, and overclaimed model
confidence.
```
