"""Template text for FlowGuard code structure recommendation route."""

from __future__ import annotations

CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Recommend an implementation structure from a FlowGuard functional model before production code is written.
Guards against: monolithic implementation plans, unclear state ownership, mixed side effects, missing facades, and test boundaries that do not map back to the model.
Use before editing: Ask for this recommendation when a model-first feature needs a code architecture plan before implementation.
Run: python .flowguard/code_structure_recommendation/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


def recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "checkout-target-structure",
        source_model_id="checkout-functional-model",
        source_model_path=".flowguard/checkout/model.py",
        parent_module_id="checkout",
        target_modules=(
            TargetModuleRecommendation(
                "orchestrator",
                path="checkout/orchestrator.py",
                owns_function_blocks=("RouteCheckout",),
                validation_boundaries=("route scenario test",),
                rationale="The orchestrator owns ordering only and does not own durable state.",
            ),
            TargetModuleRecommendation(
                "state",
                path="checkout/state.py",
                owns_state=("orders", "attempts"),
                validation_boundaries=("state shape test",),
                rationale="State and type definitions stay separate from transition logic.",
            ),
            TargetModuleRecommendation(
                "effects",
                path="checkout/effects.py",
                owns_function_blocks=("PersistOrder",),
                owns_side_effects=("write_order",),
                validation_boundaries=("effect idempotency replay",),
                rationale="Durable writes are isolated behind an adapter boundary.",
            ),
        ),
        function_block_map=(
            ("RouteCheckout", "orchestrator"),
            ("PersistOrder", "effects"),
        ),
        state_owner_map=(("orders", "state"), ("attempts", "state")),
        side_effect_owner_map=(("write_order", "effects"),),
        validation_boundaries=("route scenario test", "state shape test", "effect idempotency replay"),
        rationale="The functional model separates ordering, abstract state, and durable side effects.",
    )


def broken_recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "checkout-broken-structure",
        source_model_id="",
        parent_module_id="checkout",
        target_modules=(TargetModuleRecommendation("checkout"),),
        function_block_map=(),
    )


def run_checks():
    return (
        review_code_structure_recommendation(recommendation()),
        review_code_structure_recommendation(broken_recommendation()),
    )
'''

CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE = '''"""Run the Code Structure Recommendation template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    recommendation, broken = run_checks()
    print(recommendation.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if recommendation.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE = """# FlowGuard Code Structure Recommendation Notes

Use this scaffold when a user or agent wants a recommended code architecture
before writing production code.

## What This Route Produces

- the FlowGuard functional model used as source evidence;
- recommended target modules and paths;
- FunctionBlock-to-module ownership;
- state, config, and side-effect owner maps;
- public entrypoint or facade plans when relevant;
- validation boundaries that keep the recommendation tied to executable model
  evidence.

This route recommends structure. It does not write production code and does not
replace StructureMesh. StructureMesh uses model-derived target structure when an
existing large script or module is being split.
"""

__all__ = [
    'CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE',
    'CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE',
    'CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE',
]
