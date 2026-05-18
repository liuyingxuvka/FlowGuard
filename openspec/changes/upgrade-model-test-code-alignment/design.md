## Context

Model-Test Alignment is the direct review route for checking whether FlowGuard
model obligations have matching ordinary test evidence. The current protocol
already says it is independent from TestMesh, StructureMesh, and ModelMesh, but
its prompt does not fully describe the optional code external contract layer
that can sit between a model obligation and a test.

The upgrade keeps the existing `model_test_alignment` route and does not
create a new skill or mesh. It extends the helper API so protocol guidance,
templates, and executable review behavior all use the same vocabulary.

## Goals / Non-Goals

**Goals:**

- Make Model-Test Alignment cover three possible layers: model obligations,
  optional code external contracts, and ordinary test evidence.
- Keep code external contracts optional: include them when the externally
  visible code surface is in scope, and leave the review as model-to-test only
  when no code contract is in scope.
- Make code-contract findings visible: missing owner contract, duplicate owner,
  unknown references, missing/extra behavior, missing external-contract test
  evidence, internal-path-only tests, and model-code-test binding mismatch.
- Keep the route independent from TestMesh, StructureMesh, and ModelMesh.

**Non-Goals:**

- Do not add a parallel skill or route.
- Do not split tests, create TestMesh parent/child hierarchies, or read
  TestMesh reports.
- Do not refactor code, split modules, create StructureMesh plans, or read
  StructureMesh reports.
- Do not split models, create ModelMesh plans, or read ModelMesh reports.
- Do not change dependencies or the FlowGuard artifact schema version.

## Decisions

1. **Extend the existing route wording instead of adding another route.**
   The Skill route remains `model_test_alignment`. Its trigger now says that a
   direct review may compare model obligations with ordinary tests alone or with
   optional code external contracts in the middle.

2. **Represent code surfaces as review rows, not structure work.**
   A `CodeContract` row records a code surface's externally visible behavior:
   id, path, symbol, surface type, role, implemented model obligations,
   external inputs and outputs, state reads and writes, side effects, error
   paths, and whether the contract is required. This is evidence for alignment,
   not a request to refactor code.

3. **Require tests to prove external contracts when contracts are in scope.**
   When code contracts are listed, test evidence must bind to the relevant code
   contract ids and use an external-contract or mixed assertion scope. A test
   that only checks an internal path remains visible, but it does not prove the
   external contract.

4. **Keep backward compatibility for model-test-only reviews.**
   Existing plans with only `ModelObligation` and `TestEvidence` remain valid.
   `CodeContract` rows are optional, and `require_code_contracts` exists for
   reviews that need to block missing code owners even when no code contracts
   have been listed yet.

5. **Keep mesh boundaries explicit.**
   The protocol continues to say that large or slow validation belongs to
   TestMesh, code/API partition work belongs to StructureMesh, and parent/child
   model evidence belongs to ModelMesh. Model-Test Alignment consumes plain rows
   and does not inspect mesh reports.

## Risks / Trade-offs

- [Risk] Agents may treat optional code contracts as mandatory for every
  review. -> Mitigation: the protocol says to include them only when the
  externally visible code surface is in scope.
- [Risk] Agents may confuse code contracts with StructureMesh. -> Mitigation:
  wording states that code contracts are alignment rows and must not trigger
  refactoring or code splitting by themselves.
- [Risk] Tests may bind only to model obligations and skip the code surface. ->
  Mitigation: when code contracts are present, missing code-contract bindings
  and internal-path-only assertions are explicit findings.
