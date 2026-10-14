"""Public target scaffold for finite ContractExhaustion coverage."""

from __future__ import annotations

CONTRACT_EXHAUSTION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review a finite denominator, oracle, and shard-owned contract-exhaustion boundary.
Guards against: observed-only coverage, missing oracles, duplicate case IDs, hidden reject cases, and unbounded products.
Use before editing: Update this ContractExhaustion model when a finite dimension, member universe, oracle, or shard changes.
Run: python .flowguard/verification/owners/contract_exhaustion/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    ContractDimension,
    ContractExhaustionPlan,
    ContractOracle,
    review_contract_exhaustion,
)


REQUIRED_NEGATIVE_CASES = (
    ("missing_denominator", "exhaustion_missing_denominator"),
    ("missing_oracle", "exhaustion_missing_oracle"),
    ("unbounded_cartesian", "exhaustion_unbounded_product"),
    ("missing_member", "exhaustion_missing_member"),
    ("duplicate_case_id", "exhaustion_duplicate_case_id"),
    ("stale_universe", "exhaustion_stale_universe"),
    ("hidden_fallback_reject", "exhaustion_hidden_reject_case"),
    ("unbounded_ui_exception", "exhaustion_unbounded_ui_surface"),
)


def negative_case_matrix() -> tuple[tuple[str, str], ...]:
    """Target-owned finite bad cases that must be replaced with live fixtures."""

    return REQUIRED_NEGATIVE_CASES


def finite_plan() -> ContractExhaustionPlan:
    return ContractExhaustionPlan(
        "target-contract-exhaustion",
        dimensions=(
            ContractDimension(
                "request-shape",
                "input",
                source_route="request-boundary",
                owner_model_id="target-contract-model",
                values=("valid", "missing", "malformed"),
                mutation_types=("missing_required_field", "malformed_input"),
                currentness_rule="member universe changes require a fresh inventory revision",
            ),
        ),
        oracles=(
            ContractOracle(
                "oracle:request-shape",
                expected_status="blocked",
                expected_message_fields=("error_code",),
                forbidden_downstream_steps=("commit_side_effect",),
            ),
        ),
        required_route_ids=("contract_exhaustion_mesh", "model_test_alignment", "test_mesh"),
        source_model_ids=("target-contract-model",),
        claim_scope="routine",
    )


def run_checks():
    good = review_contract_exhaustion(finite_plan())
    bad = review_contract_exhaustion(ContractExhaustionPlan("missing-denominator"))
    case_ids = tuple(case_id for case_id, _error in negative_case_matrix())
    case_review = len(case_ids) == len(set(case_ids)) and all(error for _case, error in negative_case_matrix())
    return good, bad, case_review
'''

CONTRACT_EXHAUSTION_RUN_CHECKS_TEMPLATE = '''"""Run finite ContractExhaustion scaffold checks."""

from model import run_checks


def main() -> int:
    good, bad, case_review = run_checks()
    print(good.format_text())
    print()
    print(bad.format_text())
    print()
    print("contract-exhaustion negative-case matrix: " + ("PASS" if case_review else "BLOCKED"))
    return 0 if good.ok and not bad.ok and case_review else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
'''

CONTRACT_EXHAUSTION_NOTES_TEMPLATE = """# FlowGuard ContractExhaustion Notes

Declare a finite dimension and its complete member universe before generating
cases.  Every accepted/rejected combination needs a stable case ID and an
oracle; exclusions require proof.  Keep shard owner, receipt, Model-Test
Alignment, TestMesh, and ModelMesh handoffs explicit.  Do not hide a rejected
case behind fallback normalization, and do not claim exhaustive coverage
from observed examples alone.
"""

__all__ = [
    "CONTRACT_EXHAUSTION_MODEL_TEMPLATE",
    "CONTRACT_EXHAUSTION_RUN_CHECKS_TEMPLATE",
    "CONTRACT_EXHAUSTION_NOTES_TEMPLATE",
    "REQUIRED_NEGATIVE_CASES",
    "negative_case_matrix",
]
