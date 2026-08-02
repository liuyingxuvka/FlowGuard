## Context

The authoritative model inventory currently covers many named packages, but the affected understanding/admission path lacks dedicated self-model packages and explicit semantic relations. Some self models repeat synthetic source or test lists rather than pointing to independent inventories and executable owners.

## Goals / Non-Goals

**Goals:**

- Make the upgraded understanding path executable as a self-model.
- Bind affected models to real source, test, runtime, behavior-owner, and dependency identities.
- Make missing edges and state-name drift release-blocking for the affected surface.

**Non-Goals:**

- Claiming every historical FlowGuard model has been semantically re-proved.
- Replacing source code or tests with model declarations.
- Treating global inventory presence as proof of completeness.

## Decisions

### Add two canonical child models and one parent flow

Create `.flowguard/task_coverage_demand` and `.flowguard/model_maturation_loop` as executable model packages. Update the self-maintenance parent to compose demand → maturation → receipt verification → admission → risk → closure with exact public states and fingerprints.

### Record relationships in authoritative topology

Add explicit typed edges for refines, consumes, validates, implements, invokes, and affects. The affected-authority check requires a model owner, primary source owner, evidence owner or declared gap, and runtime entry where one exists.

### Make inventories independently sourced

The behavior ledger points to source inventory components; it does not declare itself as the source inventory. Generated topology is rebuilt only after model, source, test, and result producers settle.

### Extend behavior and test ownership

Add exactly-one primary commitments for demand compilation, receipt publication/verification, admission, confidence, and closure. Alignment entries bind each changed invariant and transition to focused tests plus the parent regression gate.

## Risks / Trade-offs

- [Mechanical topology appears deeper than semantics] → Require named relation types and focused executable obligations, not just node counts.
- [Global source globs stale every model] → Replace shared broad components for the affected path with exact component edges.
- [Parallel work changes baseline] → Work in an isolated worktree and integrate without overwriting peer paths.

## Migration Plan

1. Add child models and focused checks before production code.
2. Update parent composition and state vocabulary.
3. Update behavior, source, topology, and alignment declarations.
4. Run affected model checks, rebuild generated topology after all producers settle, then run one frozen full gate.
