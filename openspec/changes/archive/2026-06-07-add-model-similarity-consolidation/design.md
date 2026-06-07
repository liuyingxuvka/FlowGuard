## Context

FlowGuard currently has strong route-specific review helpers:
Existing Model Preflight finds current ownership before new work, ModelMesh
checks parent/child and sibling evidence, Architecture Reduction identifies
behavior-preserving code contraction, Code Structure Recommendation derives
target modules from functional models, and Model-Test Alignment compares model
obligations with code and tests. The missing layer is a proactive comparison
step across models. Without it, agents can create parallel models, tests, or
code paths that are actually same-workflow variants, symmetric flows, shared
kernels, or duplicate boundaries.

The capability introduces a reviewable model-to-model relation layer. It does
not parse arbitrary source code or rewrite production code. It consumes
structured model signatures supplied by agents or templates and produces typed
relations, maintenance groups, change-impact obligations, consolidation
recommendations, and downstream route handoffs.

## Goals / Non-Goals

**Goals:**

- Represent stable model signatures for comparison across FlowGuard models.
- Classify model relations with typed, explainable categories rather than a
  single opaque similarity score.
- Recommend reuse, family variant modeling, shared-kernel extraction,
  Architecture Reduction, ModelMesh review, Code Structure Recommendation,
  Model-Test Alignment, or manual review.
- Keep unresolved evidence gaps, stale evidence, and false-friend warnings
  visible so the report cannot overclaim safe consolidation.
- Form maintenance groups so a change to one similar workflow can name the
  sibling models, code paths, test paths, shared tests, variant tests, and
  shared-kernel or adapter obligations that must be checked.
- Integrate with Existing Model Preflight before new boundaries are created.
- Provide public API exports, CLI/template support, docs, tests, and an
  executable FlowGuard self-model.

**Non-Goals:**

- Automatically merge models.
- Automatically rewrite production code.
- Infer perfect semantics from raw source text.
- Replace ModelMesh, Architecture Reduction, Code Structure Recommendation,
  StructureMesh, Model-Test Alignment, or conformance replay.
- Treat matching names as sufficient proof of similarity.

## Decisions

1. **Use structured signatures rather than text similarity.**

   Model comparison is based on model ids, workflow family, variant id,
   FunctionBlocks, inputs, outputs, state ownership, state reads, side effects,
   invariants, failure modes, contracts, public entrypoints, child models,
   code paths, test paths, public behaviors, shared-kernel ids, adapter ids,
   maintenance tags, change refs, and evidence freshness. This keeps the
   review auditable and avoids false confidence from source-code or
   natural-language name similarity.

   Alternative considered: automatic AST or embedding similarity. This is
   deferred because it can be useful as a discovery aid but is not reliable
   enough to serve as FlowGuard evidence without structured ownership fields.

2. **Classify relation types explicitly.**

   The report uses relation types such as `same_workflow`,
   `same_family_variant`, `symmetric_flow`, `shared_kernel_candidate`,
   `duplicate_boundary`, `overlapping_ownership`, `parent_child_candidate`,
   `sibling_overlap`, `adapter_only_difference`, `evidence_duplicate`,
   `false_friend`, `unrelated`, and `manual_review`. Each relation records
   matched elements, different elements, risks, recommendation, required route,
   and required evidence.

   Alternative considered: only emit numeric scores. Numeric scores are useful
   as metadata, but they do not tell a downstream route what to do.

3. **Make recommendations route handoffs, not implementation authority.**

   A similarity relation can recommend Architecture Reduction or Code Structure
   Recommendation, but it cannot by itself prove that code can be changed. If
   public entrypoints, side effects, or compatibility surfaces are affected,
   downstream StructureMesh, conformance replay, Model-Test Alignment, and Risk
   Evidence Ledger rows still own the completion claim.

4. **Make maintenance groups part of the same report.**

   Pairwise relations are still the raw evidence, but agents need a practical
   maintenance answer: if A changed, should B and C be reviewed too? The report
   therefore derives connected maintenance groups from non-blocked similarity
   relations and emits sibling review obligations, shared behavior tests,
   variant-specific tests, and code-structure obligations. This remains inside
   Model Similarity Consolidation rather than becoming a separate audit route.

5. **Integrate first with Existing Model Preflight.**

   Preflight is where agents decide whether to reuse, extend, add a child
   model, or create a new boundary. Adding optional similarity evidence there
   catches duplicate model boundaries earlier than Architecture Reduction,
   which is more naturally used once a contraction candidate already exists.

6. **Keep false friends first-class.**

   Models can have similar names or shared helper terms while owning different
   state, side effects, invariants, or contracts. False-friend relations should
   explicitly tell agents to keep boundaries separate and record the reason.

7. **Ship a conservative template and self-model.**

   The template demonstrates same workflow, family variant, shared kernel,
   duplicate boundary, adapter-only difference, evidence gap, false friend,
   maintenance group, changed-sibling review, shared-test, and variant-test
   cases. The `.flowguard/model_similarity_consolidation` model makes the
   route executable and guards against overclaiming.

## Risks / Trade-offs

- **Risk: similarity advice is treated as proof.** → Mitigation: reports carry
  downstream route requirements and block full confidence when required
  evidence is missing or stale.
- **Risk: false positives encourage harmful consolidation.** → Mitigation:
  relation rows include risk-if-merged, risk-if-kept-separate, different
  elements, and `false_friend` classification.
- **Risk: route integration adds too much ceremony.** → Mitigation: similarity
  evidence is optional unless a preflight or claim explicitly relies on it;
  unresolved gaps are scoped rather than universal blockers.
- **Risk: broad comparisons get expensive.** → Mitigation: initial API accepts
  explicit comparison pairs and small inventories; large project-wide scans can
  later use ModelMesh or budgeted evidence conventions.
- **Risk: code structure recommendations duplicate Architecture Reduction.** →
  Mitigation: similarity identifies relation provenance; Architecture
  Reduction owns code contraction readiness, while Code Structure
  Recommendation owns target module derivation before code changes.
