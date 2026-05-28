## Overview

Add an ordinary FlowGuard helper route, not a product-specific checker. The helper describes a reusable pattern:

```text
same-class family + required mechanisms + allowed provenance + current evidence
-> family parity decision
```

The intended result is that a project cannot prove one sibling route and then claim the whole family is green unless every required member has current evidence for the same mechanism.

## Data Model

New `flowguard.obligation_family` module:

- `ObligationFamilyMember`: one sibling member, such as a route, packet kind, API variant, UI branch, adapter, or process stage.
- `ObligationFamily`: the family id, required members, shared mechanism ids, and acceptable provenance values.
- `ObligationFamilyEvidence`: proof that one member implements one mechanism from a specific source, such as durable reconciliation, runtime observation, controller receipt folding, manual event, or test injection.
- `ObligationFamilyParityFinding`: one missing, stale, wrong-provenance, or overbroad claim finding.
- `ObligationFamilyCoverageCell`: matrix row for member x mechanism coverage.
- `ObligationFamilyParityReport`: final decision, confidence, findings, and coverage matrix.
- `FamilyBadCaseSeed` and `DerivedFamilyBadCase`: utility types for turning an observed miss into same-class sibling bad cases.
- `AnalogousDefectCandidate`: one same-shape bug location found after an observed miss, with scan radius, disposition, reason, and evidence ids.
- `AnalogousDefectScanReport`: final decision, confidence, findings, generated sibling cases, and all candidate dispositions for the analogous defect scan.

## Review Rules

`review_obligation_family_parity(...)` should:

- require every non-exempt member to have current passing evidence for every required mechanism;
- reject evidence with provenance outside the family/member allowed provenance set;
- keep stale, skipped, failed, not-run, running, progress-only, or unknown evidence visible;
- treat unknown family, member, mechanism, or duplicate ids as findings;
- return full confidence only when every required cell is covered by current passing evidence with acceptable provenance;
- return scoped confidence for warnings when scoped confidence is allowed;
- return blocked confidence when any required cell is missing or invalid.

## Existing Route Integration

Model-Test Alignment:

- Add optional family plan fields to `ModelTestAlignmentPlan`.
- When present, run the family parity helper and translate its findings into alignment findings.
- Family blockers should block the alignment report.

Risk Evidence Ledger:

- Add optional family gate fields to `RiskEvidenceRow`.
- If a row requires a family gate, missing, stale, blocked, or scoped family confidence affects the final ledger decision the same way existing defect-family/model-split/test-split gates do.

Model-Miss Review:

- Do not create a new skill route.
- Use `derive_same_class_bad_cases(...)` as the executable helper for producing sibling bad cases before closure evidence is claimed.
- Use `review_analogous_defect_scan(...)` to require a same-shape risk-radius check after an observed miss. The first radius is mandatory same-family members; wider related surfaces may be marked should-scan or record-only and dispositioned as covered, repair-now, model-upgrade, separate-change, or excluded with a reason.

Risk Evidence Ledger:

- A risk row can require both the family parity gate and the analogous defect scan to be current before full confidence is granted.
- Blocked scans block final confidence; scoped scans downgrade the final claim unless scoped confidence is disabled.

## Non-Goals

- Do not add FlowPilot-specific names to FlowGuard.
- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, Risk Evidence Ledger, or Recurring Model-Miss gates.
- Do not make broad family coverage mandatory for every tiny model. The gate is activated when callers declare an obligation family or require a family gate.
- Do not treat manual or injected evidence as invalid in all contexts. It is invalid only when the declared mechanism requires a different provenance.

## Validation

- Focused unit tests for family parity pass/fail, wrong provenance, same-class bad-case derivation, Model-Test Alignment integration, and Risk Evidence Ledger integration.
- API surface tests for public exports.
- Documentation tests if existing doc checks cover the new text.
- Full local pytest/unittest where practical before release.
