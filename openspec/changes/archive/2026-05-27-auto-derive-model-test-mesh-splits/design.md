## Context

Existing FlowGuard pieces already solve later stages:

- budgeted model groups can shard a large reachable model without claiming
  incomplete shards are OK;
- ModelMesh can review parent/child model splits and target split derivation;
- TestMesh can review parent/child validation evidence and target split
  derivation;
- DevelopmentProcessFlow can route `model_too_thick` and `test_too_thick`
  failures to ModelMesh/TestMesh;
- Risk Evidence Ledger can gate final confidence on named evidence.

The missing bridge is an executable diagnostic that turns evidence metrics into
the route decision before an agent claims done.

## Goals / Non-Goals

**Goals:**

- Add a lightweight helper that identifies model/test split triggers from
  structured metrics.
- Keep the helper route-neutral: it recommends ModelMesh/TestMesh and can
  generate target derivation stubs, but it does not run child models or tests.
- Let DevelopmentProcessFlow and Risk Evidence Ledger consume the result as a
  gate.
- Preserve ordinary small models and short tests as direct evidence.

**Non-Goals:**

- Do not implement source-code parsing, pytest discovery, or automatic child
  test execution.
- Do not replace ModelMesh, TestMesh, Model-Test Alignment, or budgeted graph
  execution.
- Do not split production code; StructureMesh remains the code split route.
- Do not force every FlowGuard use to create a mesh.

## Decisions

1. **Add an auto split helper instead of expanding every route.**
   A new helper reviews `AutoSplitCandidate` rows with policy thresholds. This
   keeps the trigger logic shared by DevelopmentProcessFlow, ModelMesh, TestMesh,
   templates, and future adapters.

2. **Use conservative default thresholds.**
   Model evidence above 10,000 states, incomplete budgeted runs, pending states,
   broad parent evidence, progress-only background output, or separable model
   areas require ModelMesh review. Validation evidence above duration/test-count
   thresholds, release-only direct evidence for routine confidence, progress-only
   background output, or broad validation coverage requires TestMesh review.

3. **Generate split derivation only when enough structure exists.**
   If a candidate includes suggested child ids and covered partition ids, the
   helper emits `ModelTargetSplitDerivation` or `TestTargetSplitDerivation`.
   Otherwise it blocks with a missing target derivation finding rather than
   inventing children.

4. **Treat direct evidence as compatibility evidence after split is required.**
   Once the diagnostic requires a split, the original large model or test command
   can remain as a broad parent/compatibility gate, but parent confidence must
   consume current child evidence through ModelMesh/TestMesh.

5. **Make the final confidence path explicit.**
   DevelopmentProcessFlow reports `model_mesh_split_required` or
   `test_mesh_split_required` before done/release claims; Risk Evidence Ledger
   requires current split gate status before full confidence.

## Risks / Trade-offs

- [Risk] False positives could force unnecessary mesh work. -> Mitigation:
  thresholds are configurable and small/short evidence remains direct.
- [Risk] Agents may treat generated stubs as completed child proof. ->
  Mitigation: generated target derivations are recommendations only; ModelMesh
  and TestMesh still require current child evidence.
- [Risk] Auto split becomes another top-level skill. -> Mitigation: frame it as
  helper evidence consumed by existing FlowGuard routes, not a new Codex skill.
- [Risk] Background progress is mistaken for completion. -> Mitigation:
  progress-only is a split/incomplete signal and cannot satisfy final confidence.
