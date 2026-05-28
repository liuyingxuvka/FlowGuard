## 1. Closure Review Core

- [x] 1.1 Add `flowguard.closure_contract` with data classes for trace mapping, artifact invalidation, model quality, same-class miss closure, gateway inventory closure, evidence report summaries, findings, plans, and reports.
- [x] 1.2 Implement `review_flowguard_closure_contract()` decisions for full, scoped, and blocked confidence.
- [x] 1.3 Export the closure contract API from `flowguard.__init__` and CLI/API documentation.

## 2. Existing Gate Integration

- [x] 2.1 Add runtime trace model-mapping checks that classify unmapped in-scope traces as model-miss boundaries.
- [x] 2.2 Add artifact invalidation checks for stale model, test, gateway, code-boundary, and ledger evidence.
- [x] 2.3 Add model-quality checks for hidden state, missing side effects, ambiguous ownership, helper-only proof, missing public boundary, and parent/child evidence gaps.
- [x] 2.4 Add same-class model-miss closure checks requiring observed failure and current same-class proof.
- [x] 2.5 Add runtime gateway inventory closure checks for inventory source evidence, gateway evidence, and path-owner conflicts.
- [x] 2.6 Require current Risk Evidence Ledger support for full confidence.

## 3. Tests And Templates

- [x] 3.1 Add unit tests for green closure, unmapped runtime trace, stale artifact evidence, unresolved model-quality signal, missing same-class proof, gateway inventory gaps, and scoped risk ledger behavior.
- [x] 3.2 Add or update public template coverage for closure contract review.
- [x] 3.3 Update API surface tests so the new helper is visible as a public reporting helper.

## 4. Documentation And Validation

- [x] 4.1 Update docs to explain the executable closure contract and how it composes existing FlowGuard routes.
- [x] 4.2 Run OpenSpec validation for this change.
- [x] 4.3 Run focused tests and full FlowGuard regression.
- [x] 4.4 Sync the local editable install and verify imported version/API.
- [x] 4.5 Commit only the scoped FlowGuard changes, preserving peer-agent changes.
