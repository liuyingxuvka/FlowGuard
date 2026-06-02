## Design

FlowGuard full confidence now treats three-way binding as the default contract:

```text
ModelObligation -> CodeContract -> TestEvidence
```

Every required model obligation must have exactly one owner code contract unless
the obligation explicitly allows shared implementation. Every current passing
test evidence row that covers a required model obligation must also cover a
code contract that implements that same obligation. Every required owner code
contract must have current passing external-contract test evidence.

Scoped gaps remain possible as findings, but they are not compatibility modes
and they do not produce a full green result.

## Core Changes

### Model-Test Alignment

- Remove the Model-Test Alignment `require_code_contracts` control surface from
  full-confidence semantics. Required code contracts are no longer a mode; they
  are the default contract.
- Add a three-way binding index that cross-checks:
  - required model obligation ids;
  - owner code contract ids;
  - test evidence covered obligation ids;
  - test evidence covered code contract ids.
- Report blockers when a test covers a model obligation but:
  - no code contract is named;
  - the named code contract does not exist;
  - the named code contract does not implement that obligation;
  - the evidence is internal-path-only.

### Transition Coverage

- Add `code_contract_id` and `runtime_node_id` to `TransitionCoverageCell`.
  Required transition cells that omit an owner code contract become binding
  gaps in Model-Test Alignment, not green rows.
- Preserve transition projection to `ModelObligation`, and add projection to
  owner `CodeContract` rows when a cell declares its owner.

### Risk Evidence Ledger

- Remove the plan-level `require_code_contracts` control surface. Required
  in-scope risk rows need model obligations, owner code contracts, and current
  proof evidence by default.

### Reporting

Add lightweight binding rows to the alignment report so humans can see the
locking state directly:

```text
model_obligation_id | code_contract_id | test_evidence_id | status | gaps
```

## Skills and Docs

Update route guidance so agents no longer describe code contracts as optional
for full confidence. The new wording should be short: default full confidence
requires model, code, and test links. Missing links are blockers or scoped
gaps, not green paths.

## Validation

Regression tests must include both green three-way cases and known-bad cases:
model with no code, model/test without code, code/test without model, mismatched
model/code ids, transition cells without code, and internal-only tests.
