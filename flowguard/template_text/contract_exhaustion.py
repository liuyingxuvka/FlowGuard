"""Public target scaffold for finite ContractExhaustion coverage."""

from __future__ import annotations

CONTRACT_EXHAUSTION_MODEL_TEMPLATE = '''"""FlowGuard model

Purpose: Review a finite denominator, oracle, and shard-owned contract-exhaustion boundary.
Guards against: observed-only coverage, missing oracles, duplicate case IDs, hidden reject cases, and unbounded products.
Use before editing: Update this ContractExhaustion model when a finite dimension, member universe, oracle, or shard changes.
Run: python -m flowguard map models contract_exhaustion
"""

from __future__ import annotations

from flowguard import (
    ContractDimension,
    ContractExhaustionPlan,
    ContractOracle,
    review_contract_exhaustion,
)


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
        source_model_ids=("target-contract-model",),
        claim_scope="routine",
    )


def run_checks():
    good = review_contract_exhaustion(finite_plan())
    bad = review_contract_exhaustion(ContractExhaustionPlan("missing-denominator"))
    return good, bad
'''

CONTRACT_EXHAUSTION_RUN_CHECKS_TEMPLATE = '''"""Run finite ContractExhaustion scaffold checks."""

from model import run_checks


def main() -> int:
    good, bad = run_checks()
    print(good.format_text())
    print()
    print(bad.format_text())
    print()
    return 0 if good.ok and not bad.ok else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
'''

CONTRACT_EXHAUSTION_NOTES_TEMPLATE = """# FlowGuard ContractExhaustion Notes

Declare a finite dimension and its complete member universe before generating
cases.  Every accepted/rejected combination needs a stable case ID and an
oracle; exclusions require proof. Use a shard owner and native result evidence
when executing cases; add handoffs only when those owners are actually needed.  Do not hide a rejected
case behind fallback normalization, and do not claim exhaustive coverage
from observed examples alone.
"""

__all__ = [
    "CONTRACT_EXHAUSTION_MODEL_TEMPLATE",
    "CONTRACT_EXHAUSTION_RUN_CHECKS_TEMPLATE",
    "CONTRACT_EXHAUSTION_NOTES_TEMPLATE",
]
