# Template text for the code-structure model kit.

from __future__ import annotations

CODE_STRUCTURE_MODEL_TEMPLATE = '''# FlowGuard model: one owner per responsibility, and a module split that keeps its public entrypoints
# (code-structure kit).
#
# State: the module plan reached by named edits. Splitting an existing module is a StructureMeshPlan whose
# target_structure is the CodeStructureRecommendation; for new code with no split, start from a
# CodeStructureRecommendation alone.
# Invariants: review_code_structure_recommendation and review_structure_mesh accept every plan reached.
# Known-bad: PriceOrder gets a second owner; the split drops the public place_order entrypoint.
# Conformance (code facts): every module file, split child and code entrypoint of the target plan exists, and
# with .flowguard/map.json each responsibility's owner file belongs to the map component of that module id
# (or to the parent component when the map has no such component).
# While planning, IMPLEMENTED_BY names today's code; after the edit, update its locations and delete DESIGN_ONLY.
# Fill in: replace every REPLACE_ME path with yours, use your map component ids as module ids, model your
# responsibilities.
# Its components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only to place it elsewhere.
# Then run: python -m flowguard map models code_structure

from dataclasses import replace

from flowguard import (CodeStructureRecommendation, ModuleStructureEvidence, PublicEntrypointEvidence,
                       StructureMeshPlan, StructurePartitionItem, TargetModuleRecommendation, add_target_module,
                       code_structure_code_facts, code_structure_explorer, move_responsibility)

MODEL_ID = "code_structure"
IMPLEMENTED_BY = {"PlaceOrder": "REPLACE_ME/orders.py:place_order",    # the code of each responsibility
                  "PriceOrder": "REPLACE_ME/pricing.py:price_order"}
# DESIGN_ONLY = "<what is planned>"   # while the change is planned; delete after the edit
TESTED_BY = {"structure_mesh_review_accepts": ["REPLACE_ME/test_orders.py:test_place_order"]}
PLACE_ORDER = IMPLEMENTED_BY["PlaceOrder"]                            # the public entrypoint the split keeps


def plan():
    # Before the split: the orders module places and prices orders.
    orders = TargetModuleRecommendation("orders", path="REPLACE_ME/orders.py", owns_function_blocks=("PlaceOrder", "PriceOrder"),
                                        public_entrypoints=(PLACE_ORDER,), rationale="the public facade")
    structure = CodeStructureRecommendation(
        "orders-structure", source_model_id="orders", parent_module_id="orders", target_modules=(orders,),
        function_block_map=(("PlaceOrder", "orders"), ("PriceOrder", "orders")),
        public_entrypoint_map=((PLACE_ORDER, "orders"),), facade_module_id="orders",
        validation_boundaries=("test_place_order",), rationale="pricing moves out of orders")
    return StructureMeshPlan(
        "orders", target_structure=structure,
        partition_items=(StructurePartitionItem("PlaceOrder", owner_module_id="orders"),
                         StructurePartitionItem("PriceOrder", owner_module_id="orders"),
                         StructurePartitionItem(PLACE_ORDER, item_type="entrypoint", owner_module_id="orders")),
        child_modules=(ModuleStructureEvidence("orders", path="REPLACE_ME/orders.py"),),
        public_entrypoints=(PublicEntrypointEvidence("place_order", old_path=PLACE_ORDER, new_path=PLACE_ORDER),))


def split_pricing(plan):
    pricing = TargetModuleRecommendation("pricing", path="REPLACE_ME/pricing.py", rationale="one place computes prices")
    return move_responsibility(add_target_module(plan, pricing), "PriceOrder", "pricing")


def price_order_owned_twice(plan):
    plan = split_pricing(plan)
    structure = plan.target_structure
    return replace(plan, target_structure=replace(
        structure, function_block_map=structure.function_block_map + (("PriceOrder", "orders"),)))


def split_drops_place_order(plan):
    plan = split_pricing(plan)
    return replace(plan, public_entrypoints=(replace(plan.public_entrypoints[0], compatibility_preserved=False),))


EDITS = {"split_pricing": split_pricing, "price_order_owned_twice": price_order_owned_twice,
         "split_drops_place_order": split_drops_place_order}


def build_explorer():
    return code_structure_explorer(plan, EDITS, explore=["split_pricing"])


def broken_variants():
    return {name: code_structure_explorer(plan, EDITS, explore=[name])
            for name in ("price_order_owned_twice", "split_drops_place_order")}


def conformance():
    return code_structure_code_facts(split_pricing(plan()), anchors=IMPLEMENTED_BY, planned="DESIGN_ONLY" in globals())
'''

__all__ = ["CODE_STRUCTURE_MODEL_TEMPLATE"]
