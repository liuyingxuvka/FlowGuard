import json
import unittest
from dataclasses import replace

from flowguard import (
    CodeStructureRecommendation,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
    add_target_module,
    code_structure_code_facts,
    code_structure_explorer,
    move_responsibility,
    review_code_structure_recommendation,
)


def module(module_id: str, **kwargs) -> TargetModuleRecommendation:
    defaults = {
        "rationale": f"{module_id} owns a cohesive model-derived boundary",
        "validation_boundaries": ("focused test",),
    }
    defaults.update(kwargs)
    return TargetModuleRecommendation(module_id, **defaults)


class CodeStructureRecommendationTests(unittest.TestCase):
    def test_complete_recommendation_can_continue(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            source_model_path=".flowguard/checkout/model.py",
            parent_module_id="checkout",
            target_modules=(
                module("orchestrator", owns_function_blocks=("RouteCheckout",)),
                module(
                    "effects",
                    owns_function_blocks=("PersistOrder",),
                    owns_state=("orders",),
                    owns_side_effects=("write_order",),
                    owns_fields=("field:mode",),
                    reads_fields=("field:mode",),
                    writes_fields=("field:mode",),
                ),
            ),
            function_block_map=(
                ("RouteCheckout", "orchestrator"),
                ("PersistOrder", "effects"),
            ),
            state_owner_map=(("orders", "effects"),),
            side_effect_owner_map=(("write_order", "effects"),),
            field_owner_map=(("field:mode", "effects"),),
            field_reader_map=(("field:mode", "effects"),),
            field_writer_map=(("field:mode", "effects"),),
            validation_boundaries=("model scenario replay",),
            rationale="the functional model separates routing from durable effects",
        )

        report = review_code_structure_recommendation(recommendation)

        self.assertTrue(report.ok)
        self.assertEqual(0, report.blocker_count())

    def test_field_reader_writer_maps_require_owner_and_registered_modules(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            parent_module_id="checkout",
            target_modules=(module("effects"),),
            function_block_map=(("PersistOrder", "effects"),),
            field_owner_map=(
                ("field:mode", "effects"),
                ("field:mode", "other"),
            ),
            field_reader_map=(("field:mode", "reader"),),
            field_writer_map=(("field:status", "effects"),),
            validation_boundaries=("model scenario replay",),
            rationale="field ownership should stay visible in the target split",
        )

        report = review_code_structure_recommendation(recommendation)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("duplicate_field_recommendation_owner", codes)
        self.assertIn("field_owner_not_registered", codes)
        self.assertIn("field_reader_not_registered", codes)
        self.assertIn("field_access_without_owner", codes)

    def test_missing_model_source_blocks(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="",
            parent_module_id="checkout",
            target_modules=(module("effects"),),
            function_block_map=(("PersistOrder", "effects"),),
            validation_boundaries=("model scenario replay",),
            rationale="effects own durable writes",
        )

        report = review_code_structure_recommendation(recommendation)

        self.assertFalse(report.ok)
        self.assertIn("missing_source_model", [finding.code for finding in report.findings])

    def test_unregistered_and_duplicate_owners_block(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            parent_module_id="checkout",
            target_modules=(module("effects"),),
            function_block_map=(
                ("PersistOrder", "effects"),
                ("PersistOrder", "other"),
            ),
            state_owner_map=(("orders", "other"),),
            side_effect_owner_map=(("write_order", "other"),),
            validation_boundaries=("model scenario replay",),
            rationale="effects own durable writes",
        )

        report = review_code_structure_recommendation(recommendation)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("function_block_owner_not_registered", codes)
        self.assertIn("duplicate_function_block_owner", codes)
        self.assertIn("state_owner_not_registered", codes)
        self.assertIn("side_effect_owner_not_registered", codes)

    def test_missing_rationale_and_validation_plan_block(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            parent_module_id="checkout",
            target_modules=(TargetModuleRecommendation("effects"),),
            function_block_map=(("PersistOrder", "effects"),),
        )

        report = review_code_structure_recommendation(recommendation)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("missing_validation_plan", codes)
        self.assertIn("missing_structure_rationale", codes)
        self.assertIn("missing_module_rationale", codes)


PLACE = "shop/orders.py:place_order"


def _split_plan():
    """Before the split: the orders module places and prices orders."""
    structure = CodeStructureRecommendation(
        "orders-structure", source_model_id="orders", parent_module_id="orders",
        target_modules=(module("orders", path="shop/orders.py", owns_function_blocks=("PlaceOrder", "PriceOrder"),
                               public_entrypoints=(PLACE,)),),
        function_block_map=(("PlaceOrder", "orders"), ("PriceOrder", "orders")),
        public_entrypoint_map=((PLACE, "orders"),), facade_module_id="orders",
        validation_boundaries=("test_place_order",), rationale="pricing moves out of orders")
    return StructureMeshPlan(
        "orders", target_structure=structure,
        partition_items=(StructurePartitionItem("PlaceOrder", owner_module_id="orders"),
                         StructurePartitionItem("PriceOrder", owner_module_id="orders"),
                         StructurePartitionItem(PLACE, item_type="entrypoint", owner_module_id="orders")),
        child_modules=(ModuleStructureEvidence("orders", path="shop/orders.py"),),
        public_entrypoints=(PublicEntrypointEvidence("place_order", old_path=PLACE, new_path=PLACE),))


def _split_pricing(plan):
    return move_responsibility(add_target_module(plan, module("pricing", path="shop/pricing.py")), "PriceOrder", "pricing")


_SPLIT_EDITS = {
    "split_pricing": _split_pricing,
    "price_owned_twice": lambda plan: replace(_split_pricing(plan), target_structure=replace(
        _split_pricing(plan).target_structure,
        function_block_map=_split_pricing(plan).target_structure.function_block_map + (("PriceOrder", "orders"),))),
    "drop_place_order": lambda plan: replace(_split_pricing(plan), public_entrypoints=(
        replace(plan.public_entrypoints[0], compatibility_preserved=False),)),
}


def test_code_structure_kit_explores_a_split_with_both_reviews_as_invariants():
    assert code_structure_explorer(_split_plan, _SPLIT_EDITS, explore=["split_pricing"]).explore().ok
    split = _split_pricing(_split_plan())
    assert split.target_structure.function_block_owners()["PriceOrder"] == "pricing"
    assert [item.owner_module_id for item in split.partition_items if item.item_id == "PriceOrder"] == ["pricing"]
    assert [child.module_id for child in split.child_modules] == ["orders", "pricing"]
    twice = code_structure_explorer(_split_plan, _SPLIT_EDITS, explore=["price_owned_twice"]).explore()
    assert {v.invariant_name for v in twice.violations} == {"code_structure_review_accepts",
                                                            "structure_mesh_review_accepts"}
    assert "duplicate_function_block_owner" in twice.violations[0].message
    dropped = code_structure_explorer(_split_plan, _SPLIT_EDITS, explore=["drop_place_order"]).explore()
    assert {v.invariant_name for v in dropped.violations} == {"structure_mesh_review_accepts"}
    assert "entrypoint_removed" in dropped.violations[0].message
    no_split = code_structure_explorer(lambda: _split_plan().target_structure, {"keep": lambda plan: plan})
    assert [invariant.name for invariant in no_split.invariants] == ["code_structure_review_accepts"]


def test_code_structure_code_facts_compare_the_plan_with_the_code_and_the_map(tmp_path):
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop/orders.py").write_text("def place_order(order):\n    return order\n", encoding="utf-8")
    (tmp_path / "shop/pricing.py").write_text("def price_order(order):\n    return 1\n", encoding="utf-8")
    target = _split_pricing(_split_plan())
    anchors = {"PriceOrder": "shop/pricing.py:price_order"}
    assert code_structure_code_facts(target, anchors=anchors, root=tmp_path).ok        # no map: files only
    (tmp_path / ".flowguard").mkdir()
    components = [{"id": "orders", "status": "draft", "files": ["shop/orders.py"]},
                  {"id": "pricing", "status": "draft", "files": ["shop/pricing.py"]}]
    (tmp_path / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": components}),
                                                  encoding="utf-8")
    report = code_structure_code_facts(target, anchors=anchors, root=tmp_path)
    assert report.ok and "PriceOrder: owner file shop/pricing.py belongs to map component pricing" in \
        [fact.name for fact in report.facts]
    components[1]["id"] = "billing"                       # no component 'pricing': the parent 'orders' must own it
    (tmp_path / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": components}),
                                                  encoding="utf-8")
    text = code_structure_code_facts(target, root=tmp_path).format_text()
    assert "- PriceOrder: owner file shop/pricing.py belongs to map component orders: shop/pricing.py belongs to billing" in text
    (tmp_path / "shop/pricing.py").rename(tmp_path / "shop/prices.py")
    text = code_structure_code_facts(target, anchors=anchors, root=tmp_path).format_text()
    assert "- module pricing exists at shop/pricing.py: shop/pricing.py does not exist" in text
    assert "- anchor shop/pricing.py:price_order exists: anchor file missing: shop/pricing.py" in text


if __name__ == "__main__":
    unittest.main()
