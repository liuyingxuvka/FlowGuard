## 1. OpenSpec And Protocol

- [x] 1.1 Create the OpenSpec proposal, design, and capability spec for conservative contract-audit evidence.
- [x] 1.2 Update the Model-Test Alignment protocol to describe audited source/test evidence and its limits.
- [x] 1.3 Update public docs and agent snippets within the allowed documentation scope.

## 2. Implementation

- [x] 2.1 Add Python AST source audit helpers that produce conservative code-contract evidence candidates and findings.
- [x] 2.2 Add Python AST test audit helpers that produce conservative test-assertion evidence candidates and findings.
- [x] 2.3 Integrate audited evidence with Model-Test Alignment through source-audit review helpers without changing TestMesh, StructureMesh, or ModelMesh routes.
- [x] 2.4 Add focused tests for supported, missing, partial, internal-path-only, and missing-assert evidence cases.

## 3. Validation

- [x] 3.1 Run `openspec validate add-contract-audit-evidence --strict` or the equivalent explicit change validation command.
- [x] 3.2 Run focused unit/template/docs checks and record adoption evidence.
