## 1. Qualification contract

- [x] 1.1 Version the current provider-neutral DNA qualification payload and add explicit execution status, execution evidence fingerprint, static-ready projection, and broad-qualified projection.
- [x] 1.2 Derive execution status and fingerprint from the canonical readiness ledger by default; normalize missing, stale, failed, blocked, skipped, running, and unknown values without fallback success.
- [x] 1.3 Require non-empty current fingerprints for every layer that contributes to a broad qualified claim, while retaining static-only readiness for its declared boundary.
- [x] 1.4 Update serialization/deserialization and aggregate status validation so caller-authored `qualified`, `static_ready`, or status fields cannot disagree with native derivation.

## 2. Behavior readiness identity

- [x] 2.1 Add a deterministic execution-evidence fingerprint to `BehaviorBlueprintReport` over exact execution dispositions and native evidence identities.
- [x] 2.2 Preserve the distinction between static `complete`, execution `passed`, and execution `not_run`/non-pass statuses in the report and normalized projection.
- [x] 2.3 Add focused tests for empty execution rows, passed rows, stale/missing receipts, and stable execution fingerprint changes.

## 3. Acceptance and verification

- [x] 3.1 Update provider-neutral qualification tests for static-ready versus broad-qualified results, including missing-fingerprint and non-pass execution cases.
- [x] 3.2 Run focused target-system, provider-neutral, software-readiness, and serialization tests; record exact command and result identities.
- [x] 3.3 Validate this OpenSpec change and leave project-audit/full/release validation outside this bounded work package when current authority is stale or blocked.
