## Context

The existing Model-Test Alignment route accepts explicit `ModelObligation`,
`CodeContract`, and `TestEvidence` rows. That is useful for traceability, but
it still relies on the reviewer to describe what real code and tests prove.
This change adds a conservative Python source-audit layer before the alignment
review. The audit reads real Python source and real Python tests, extracts
observable evidence from AST structure, and labels unsupported or ambiguous
claims before the three-way alignment report is trusted.

The audit layer is an evidence collector and skeptic. It does not replace the
model, execute the production workflow, or prove full runtime semantics.

## Goals / Non-Goals

**Goals:**

- Generate or validate code-contract evidence from real Python source files.
- Generate or validate test-assertion evidence from real Python test files.
- Preserve conservative confidence labels: supported, missing, partial,
  ambiguous, dynamic, or manual-review-required.
- Pass audited evidence into `review_model_test_alignment()` so declared model
  obligations, audited code contracts, and audited test evidence can be
  compared together.
- Make limitations visible in protocol and public docs.

**Non-Goals:**

- Do not build a perfect semantic proof engine for Python.
- Do not infer arbitrary dynamic behavior, monkeypatching, metaprogramming,
  reflection, I/O effects, concurrency, or framework-specific lifecycle
  semantics as proven.
- Do not replace conformance replay, production-facing checks, or manual review
  for complex behavior.
- Do not route this work into TestMesh, StructureMesh, or ModelMesh unless the
  separate mesh trigger is independently present.

## Decisions

1. **Use AST evidence as conservative support, not proof.**
   The audit should parse Python files with the standard `ast` module and
   extract only structure that can be observed statically: definitions, public
   symbols, decorators, imports, calls, raises, returns, yields, assignments,
   context managers, assertions, pytest markers, parametrization, monkeypatch
   usage, and selected fixture references. If a claim depends on control flow or
   runtime values that the audit cannot see, it must produce a partial or
   manual-review finding instead of a green proof.

2. **Separate code-contract evidence from test-assertion evidence.**
   Source audits produce candidate or verified `CodeContract` evidence for
   external surfaces. Test audits produce candidate or verified `TestEvidence`
   rows plus assertion-scope evidence. Keeping these outputs distinct lets
   Model-Test Alignment report whether the model, code surface, and tests are
   talking about the same obligation.

3. **Treat external behavior as the only contract surface.**
   The audit should not give full credit for tests that only inspect private
   helpers or internal paths unless the declared contract is explicitly internal
   for the current review. Public functions, APIs, CLIs, adapters, facades, and
   persisted outputs are the normal contract surfaces.

4. **Prefer explicit bindings over fuzzy inference.**
   The strongest evidence comes from explicit ids in review rows, decorators,
   docstrings/comments when supported, test names, parametrization ids, or
   reviewer-provided maps. Name similarity may suggest candidates, but it must
   not silently create high-confidence model/code/test bindings.

5. **Send all findings into the existing alignment path.**
   The source audit is a feeder layer. It should generate rows and findings
   that `review_model_test_alignment()` can consume or report alongside the
   alignment findings. It is not a new mesh and does not own the final coverage
   claim by itself.

## Risks / Trade-offs

- [Risk] Agents may overclaim AST results as semantic proof. -> Mitigation:
  every protocol and docs update states that source audit is conservative,
  incomplete, and not a conformance substitute.
- [Risk] Dynamic Python patterns hide real behavior. -> Mitigation: dynamic,
  reflective, framework-lifecycle, monkeypatched, or generated behavior is
  marked ambiguous or manual-review-required unless directly evidenced.
- [Risk] Static tests look strong but never run. -> Mitigation: test-assertion
  evidence must still be combined with `TestEvidence.status` and freshness;
  skipped, stale, failed, timeout, not-run, running, or error tests do not count
  as current coverage.
- [Risk] The audit duplicates StructureMesh. -> Mitigation: it observes
  contract support in files; it does not recommend module splits, ownership
  partitions, or refactors.
- [Risk] The audit duplicates conformance replay. -> Mitigation: replay remains
  required when production state, side effects, or trace-level behavior must be
  compared against model traces.
