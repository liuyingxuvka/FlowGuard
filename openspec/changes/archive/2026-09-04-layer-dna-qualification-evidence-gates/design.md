## Context

The existing target-system qualifier already normalizes static, semantic,
code-binding, and test-binding statuses, while the target readiness ledger
already carries per-layer `executed_evidence_status`. The defect is at the
claim projection: `qualified` is currently derived only from static binding
statuses, and implementation admission intentionally remains usable for
pre-code/static planning even when execution is `not_run`.

The behavior readiness report already validates coverage execution rows and
keeps `execution_complete` separate from static `complete`. This change adds a
stable execution-evidence fingerprint over those native rows and makes the
target DNA qualifier consume the canonical ledger's execution layer.

## Goals / Non-Goals

**Goals:**

- Keep static blueprint readiness and implementation admission available for
  their existing narrow boundaries.
- Add a typed execution layer to `TargetSystemDnaQualification`.
- Make `qualified` mean all required layers, including exact passed execution
  evidence, are current.
- Preserve typed non-pass execution gaps and reject self-authored status
  projections during deserialization.
- Give behavior readiness consumers one deterministic execution-evidence
  fingerprint without executing work.

**Non-Goals:**

- Do not launch tests, providers, browsers, installers, or target processes.
- Do not redesign the model authority, current pointer, or receipt store.
- Do not change `BlueprintReadinessLedger.implementation_admitted`; that is a
  pre-code/static admission fact and must remain distinct from broad DNA
  qualification.
- Do not make static reports depend on runtime execution evidence.

## Decisions

1. **Use the canonical readiness ledger as the default execution source.**
   The qualifier will derive execution status and an exact status/evidence
   fingerprint from the report ledger. Optional explicit values remain
   available for provider callers that already own a native execution receipt,
   but empty or contradictory values cannot grant qualification.

2. **Split `static_ready` from `qualified`.** `static_ready` means the four
   existing binding layers are current. `qualified` additionally requires
   `execution_status=passed` and a non-empty execution evidence fingerprint.
   The aggregate status is `static_ready` for the former and `qualified` for
   the latter; all other cases remain `blocked` with reasons.

3. **Make fingerprints part of the currentness gate.** A status string such as
   `current` or `passed` without its corresponding evidence fingerprint is a
   missing/incomplete layer, not a passing claim.

4. **Version the qualification wire shape directly.** The new execution
   fields are required in the current schema; old payloads are not read
   through a compatibility fallback. Callers must regenerate the current
   qualification projection.

5. **Keep behavior execution identity separate from the full report identity.**
   `BehaviorBlueprintReport.execution_evidence_fingerprint` hashes only the
   exact execution dispositions and their native evidence identities, so
   static source changes cannot be mistaken for a passed execution receipt.

## Risks / Trade-offs

- [Risk] Existing callers that treated current static bindings as broad DNA
  qualification will now see `static_ready`. → Preserve the static properties
  and provide explicit reasons so callers can narrow their claim or supply
  current execution evidence.
- [Risk] Historical serialized qualification payloads become stale. → Use the
  direct current schema and expose a regeneration disposition; do not add a
  legacy reader.
- [Risk] A fingerprint over already-owned execution rows is not itself a test
  runner. → Keep the claim boundary explicit: the native execution owner must
  produce terminal evidence before the fingerprint can authorize qualification.

## Migration Plan

1. Add the current schema fields and execution fingerprint property.
2. Update focused qualification and behavior-readiness tests.
3. Re-run only the affected tests and OpenSpec validation.
4. Rebuild current qualification evidence under one frozen source identity
   before any release or installation claim.
