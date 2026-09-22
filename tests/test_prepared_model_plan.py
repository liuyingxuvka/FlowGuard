from __future__ import annotations

from pathlib import Path

import pytest

from flowguard.model_regressions import (
    PREPARED_MODEL_REGRESSION_PLAN_SCHEMA,
    prepare_model_regression_plan,
    run_manifest_regressions,
)
from tests.test_consumer_current_lifecycle import _consumer_roots


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
