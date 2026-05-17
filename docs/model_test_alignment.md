# Model-Test Alignment

Model-Test Alignment checks whether a FlowGuard model's explicit obligations
and ordinary test evidence cover the same behavioral surface.

It is intentionally small:

```text
ModelObligation rows + TestEvidence rows
  -> review_model_test_alignment(...)
  -> missing evidence, orphan tests, duplicate claims, stale evidence, and
     missing required test kinds
```

It does not split tests, split source code, run pytest, or read TestMesh,
StructureMesh, or ModelMesh reports.

## Basic Use

```python
from flowguard import (
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    review_model_test_alignment,
)

plan = ModelTestAlignmentPlan(
    model_id="checkout_model",
    obligations=(
        ModelObligation(
            "reject_duplicate_order",
            obligation_type="hazard",
            required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
        ),
    ),
    test_evidence=(
        TestEvidence(
            "test_reject_duplicate_order",
            test_name="test_reject_duplicate_order",
            path="tests/test_checkout.py",
            result_status="passed",
            test_kind=TEST_KIND_FAILURE_PATH,
            covered_obligations=("reject_duplicate_order",),
        ),
    ),
)

report = review_model_test_alignment(plan)
print(report.format_text())
```

## Findings

The report keeps these gaps visible:

- `missing_test_evidence`: a required model obligation has no current passing
  test evidence.
- `missing_required_test_kind`: an obligation requires a path kind that is not
  covered.
- `orphan_test_evidence`: a test is not bound to any model obligation.
- `unknown_obligation_reference`: a test references an obligation the model
  does not declare.
- `duplicate_test_evidence_owner`: multiple current passing tests claim the
  same obligation and kind without explicit shared intent.
- `stale_test_evidence`: passing evidence is stale and cannot support current
  coverage.
- `test_evidence_not_passing`: skipped, failed, timeout, not-run, running, or
  error evidence is visible but not coverage.
- `test_overclaims_model_confidence`: a test claims broader model confidence
  than its obligation bindings prove.

## Template

Generate a starter review:

```powershell
python -m flowguard model-test-alignment-template --output .
python .flowguard/model_test_alignment/run_checks.py
```

Use TestMesh separately only when a large or slow validation flow needs
parent/child suite ownership. Use StructureMesh separately only when source
structure is being split.
