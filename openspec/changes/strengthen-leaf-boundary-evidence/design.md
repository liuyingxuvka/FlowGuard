## Context

The current FlowGuard model hierarchy can express parent coverage, child
disjointness, reattachment, and leaf boundary matrices. The remaining problem
is authority: the same parent model obligation can receive several tests that
all look like primary `edge_path` proof. The existing duplicate-evidence guard
detects overlap, but it does not make the next action explicit enough.

The desired behavior is stricter:

- a parent obligation has one primary edge proof for the parent handoff;
- separate code boundaries become child obligations or leaf matrix cells;
- a leaf matrix proves every finite `Input x State` cell;
- supporting evidence cannot replace primary proof.

## Goals / Non-Goals

**Goals:**
- Make primary evidence responsibility explicit in `TestEvidence`.
- Convert duplicate primary `edge_path` evidence into a split-required
  decision.
- Require leaf matrices to match declared input/state Cartesian axes when axes
  are supplied.
- Check missing observed outputs, next states, state writes, side effects, and
  error paths, not only extra behavior.
- Let TestMesh require leaf matrix-cell validation evidence without expanding
  every child test internals into the parent gate.
- Let Existing Model Preflight surface unknown layered proof status before a
  downstream route claims coverage.

**Non-Goals:**
- Do not remove the existing duplicate evidence guard for non-edge evidence.
- Do not make Model-Test Alignment split models by itself.
- Do not execute tests inside layered proof or TestMesh helpers.
- Do not force infinite or too-large leaves to brute-force; they must split
  further or remain scoped.

## Decisions

1. **Evidence roles are additive.**
   Existing `TestEvidence` defaults remain primary coverage so current callers
   keep the same behavior. New roles allow callers to mark leaf matrix cells and
   supporting evidence explicitly.

2. **Primary edge duplicates are model-shape findings.**
   Multiple current primary `edge_path` proofs for one obligation produce
   `obligation_too_coarse_for_primary_evidence` and the decision
   `child_model_split_required`.

3. **Supporting evidence must point somewhere.**
   A supporting contract proof or leaf matrix-cell proof needs a target id. A
   role label without a child obligation, code contract, or matrix cell is not
   enough.

4. **Leaf matrix axes are authoritative when present.**
   When `input_cases` and `state_cases` are supplied, FlowGuard computes the
   expected Cartesian cell ids and compares them with the declared and observed
   cells.

5. **TestMesh owns validation visibility, not semantics.**
   TestMesh records which child suite/script covers which leaf matrix cell and
   whether final pass artifacts exist. Layered proof still owns the semantic
   parent/child/leaf proof chain.

## Risks / Trade-offs

- **Risk:** Existing callers with many same-kind tests may see stronger
  blockers when they mark or imply primary `edge_path` evidence.  
  **Mitigation:** Non-primary leaf matrix-cell evidence can coexist under the
  leaf; parent obligations should be split when several code boundaries want
  primary responsibility.

- **Risk:** More fields increase API surface.  
  **Mitigation:** Keep defaults backward compatible and standard-library only.

- **Risk:** Agents may overuse scoped exemptions.  
  **Mitigation:** Keep too-large or incomplete leaf matrices as blockers unless
  the caller explicitly allows scoped exemptions and records rationale.
