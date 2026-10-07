from __future__ import annotations

from pathlib import Path

import pytest

from flowguard.model_regressions import (
    PREPARED_MODEL_REGRESSION_PLAN_SCHEMA,
    prepare_model_regression_plan,
    run_manifest_regressions,
)
from tests.test_consumer_current_lifecycle import _consumer_roots, _prepare_parent


def test_prepared_plan_freezes_complete_denominator_and_rows(tmp_path: Path) -> None:
    _target, staging = _consumer_roots(tmp_path)

    plan = prepare_model_regression_plan(
        staging,
        target_id="consumer-fixture",
        base_head="",
        candidate_fingerprint="sha256:" + "a" * 64,
        receipt_dir=staging / "work" / "model-owner-receipts",
    )

    assert plan.to_dict()["schema_version"] == PREPARED_MODEL_REGRESSION_PLAN_SCHEMA
    assert plan.model_denominator == (
        "alpha",
        "alpha_beta_connection",
        "beta",
    )
    assert tuple(row.owner_id for row in plan.rows) == tuple(
        f"model:{model_id}" for model_id in plan.model_denominator
    )
    assert all(row.disposition == "execute" for row in plan.rows)
    assert len(plan.native_binding_denominator) == 3
    assert plan.fingerprint.startswith("sha256:")


def test_prepared_plan_rejects_caller_scope_selection_before_execution(
    tmp_path: Path,
) -> None:
    _target, staging = _consumer_roots(tmp_path)
    plan = prepare_model_regression_plan(
        staging,
        target_id="consumer-fixture",
        candidate_fingerprint="sha256:" + "b" * 64,
        receipt_dir=staging / "work" / "model-owner-receipts",
    )

    with pytest.raises(ValueError, match="cannot be combined"):
        run_manifest_regressions(
            staging,
            tier="fast",
            prepared_plan=plan,
            receipt_dir=staging / "work" / "model-owner-receipts",
        )


def test_affected_exact_current_owner_reuses_without_reducing_denominator(tmp_path: Path):
    _target, staging = _consumer_roots(tmp_path)
    _parent, receipt_root = _prepare_parent(staging)
    plan = prepare_model_regression_plan(
        staging,
        target_id="consumer-fixture",
        affected_ids=("model:alpha", "alpha"),
        receipt_dir=receipt_root,
    )
    assert plan.model_denominator == ("alpha", "alpha_beta_connection", "beta")
    assert len(plan.native_binding_denominator) == 3
    assert all(row.disposition == "reuse_current" for row in plan.rows)
    report = run_manifest_regressions(
        staging, tier="full", prepared_plan=plan, receipt_dir=receipt_root,
        output_dir=staging / "work" / "reuse-affected", require_executed_case_ids=True,
    )
    assert report.ok
    assert sum(row.producer_invocations for row in report.results) == 0


def test_affected_does_not_make_missing_or_policy_incompatible_receipt_reusable(tmp_path: Path):
    _target, staging = _consumer_roots(tmp_path)
    parent, receipt_root = _prepare_parent(staging)
    alpha = next(row for row in parent.results if row.model_id == "alpha")
    Path(alpha.receipt_path).unlink()
    plan = prepare_model_regression_plan(
        staging, affected_ids=("alpha",), receipt_dir=receipt_root,
    )
    rows = {row.owner_id: row for row in plan.rows}
    assert rows["model:alpha"].disposition == "execute"
    assert rows["model:beta"].disposition == "reuse_current"
    changed_policy = prepare_model_regression_plan(
        staging, affected_ids=("alpha",), receipt_dir=receipt_root, timeout=0.01,
    )
    assert all(row.disposition == "execute" for row in changed_policy.rows)
