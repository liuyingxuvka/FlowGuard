import unittest

import flowguard.canonical_relation as relation_handoff
from flowguard.canonical_relation import (
    CanonicalRelation,
    CanonicalRelationHandoff,
    RELATION_FALSE_FRIEND,
    RELATION_SHARED_MECHANISM,
    normalize_canonical_relation_handoff,
)


def _relation(
    relation_id: str = "relation:checkout-shared-kernel",
    relation_type: str = RELATION_SHARED_MECHANISM,
) -> CanonicalRelation:
    return CanonicalRelation(
        relation_id=relation_id,
        relation_type=relation_type,
        source_endpoint_kind="model",
        source_endpoint_id="checkout-simple",
        target_endpoint_kind="model",
        target_endpoint_id="checkout-retry",
        source_ids=("observed-model:snapshot-7", "bcl:checkout"),
        typed_commitment_relation_refs=("commitment-relation:checkout-owns-submit",),
        metadata={"owner": "checkout"},
    )


class CanonicalRelationHandoffTests(unittest.TestCase):
    def test_keeps_only_exact_current_relation_inputs(self):
        relation = _relation()
        handoff = CanonicalRelationHandoff(
            relations=(relation,),
            relation_group_ids=("relation-group:checkout",),
            affected_model_ids=("checkout-retry",),
            code_obligation_ids=("code-obligation:checkout-kernel",),
            test_obligation_ids=("test-obligation:checkout-family",),
        )

        self.assertEqual((relation.relation_id,), handoff.relation_ids)
        self.assertEqual(
            (relation.relation_id,),
            handoff.relation_ids_of_type(RELATION_SHARED_MECHANISM),
        )
        self.assertEqual(
            ("commitment-relation:checkout-owns-submit",),
            handoff.typed_commitment_relation_refs,
        )
        self.assertEqual(
            {
                "relation_id": relation.relation_id,
                "relation_type": RELATION_SHARED_MECHANISM,
                "source_endpoint_kind": "model",
                "source_endpoint_id": "checkout-simple",
                "target_endpoint_kind": "model",
                "target_endpoint_id": "checkout-retry",
                "source_ids": ["observed-model:snapshot-7", "bcl:checkout"],
                "typed_commitment_relation_refs": [
                    "commitment-relation:checkout-owns-submit"
                ],
                "metadata": {"owner": "checkout"},
            },
            handoff.to_dict()["relations"][0],
        )

    def test_normalizes_the_one_current_mapping_shape(self):
        handoff = normalize_canonical_relation_handoff(
            {
                "relations": (
                    {
                        "relation_id": "relation:cache-false-friend",
                        "relation_type": RELATION_FALSE_FRIEND,
                        "source_endpoint_kind": "model",
                        "source_endpoint_id": "cache-refresh",
                        "target_endpoint_kind": "model",
                        "target_endpoint_id": "cache-report",
                        "source_ids": ("observed-model:snapshot-9",),
                    },
                ),
                "gap_ids": ("gap:missing-owner",),
                "evidence_current": False,
            }
        )

        self.assertIsInstance(handoff, CanonicalRelationHandoff)
        self.assertEqual(("relation:cache-false-friend",), handoff.relation_ids)
        self.assertEqual(("gap:missing-owner",), handoff.gap_ids)
        self.assertFalse(handoff.evidence_current)

    def test_rejects_relation_without_exact_source_identity(self):
        with self.assertRaisesRegex(ValueError, "at least one exact source identity"):
            CanonicalRelation(
                relation_id="relation:missing-source",
                relation_type=RELATION_SHARED_MECHANISM,
                source_endpoint_kind="model",
                source_endpoint_id="checkout-simple",
                target_endpoint_kind="model",
                target_endpoint_id="checkout-retry",
                source_ids=(),
            )

    def test_rejects_unsupported_or_ambiguous_relation_identity(self):
        with self.assertRaisesRegex(ValueError, "unsupported canonical relation type"):
            _relation(relation_type="looks_similar")
        with self.assertRaisesRegex(ValueError, "endpoints must be distinct"):
            CanonicalRelation(
                relation_id="relation:self",
                relation_type=RELATION_SHARED_MECHANISM,
                source_endpoint_kind="model",
                source_endpoint_id="checkout",
                target_endpoint_kind="model",
                target_endpoint_id="checkout",
                source_ids=("observed-model:snapshot-7",),
            )
        with self.assertRaisesRegex(TypeError, "must be a string"):
            CanonicalRelation(
                relation_id=7,  # type: ignore[arg-type]
                relation_type=RELATION_SHARED_MECHANISM,
                source_endpoint_kind="model",
                source_endpoint_id="checkout-simple",
                target_endpoint_kind="model",
                target_endpoint_id="checkout-retry",
                source_ids=("observed-model:snapshot-7",),
            )

    def test_rejects_duplicate_relation_and_source_ids(self):
        relation = _relation()
        with self.assertRaisesRegex(ValueError, "duplicate relation_id"):
            CanonicalRelationHandoff(relations=(relation, relation))
        with self.assertRaisesRegex(ValueError, "duplicate canonical identities"):
            CanonicalRelation(
                relation_id="relation:duplicate-sources",
                relation_type=RELATION_SHARED_MECHANISM,
                source_endpoint_kind="model",
                source_endpoint_id="checkout-simple",
                target_endpoint_kind="model",
                target_endpoint_id="checkout-retry",
                source_ids=("snapshot:7", "snapshot:7"),
            )

    def test_old_standalone_handoff_shape_has_no_compatibility_reader(self):
        with self.assertRaises(TypeError):
            normalize_canonical_relation_handoff(
                {
                    "relation_ids": ("relation:legacy",),
                    "maintenance_group_ids": ("maintenance:legacy",),
                }
            )

    def test_standalone_similarity_engine_symbols_are_retired(self):
        retired_symbols = {
            "ModelSignature",
            "ModelSimilarityPlan",
            "ModelSimilarityReport",
            "SimilarityHandoff",
            "model_similarity_plan_for_changed_member",
            "normalize_similarity_handoff",
            "review_model_similarity_consolidation",
        }

        self.assertTrue(retired_symbols.isdisjoint(vars(relation_handoff)))
        self.assertEqual(
            {
                "CANONICAL_RELATION_TYPES",
                "CanonicalRelation",
                "CanonicalRelationHandoff",
                "RELATION_ADAPTER_ONLY",
                "RELATION_AFFECTED_SIBLING",
                "RELATION_DUPLICATE_BOUNDARY",
                "RELATION_FALSE_FRIEND",
                "RELATION_SAME_INTENT",
                "RELATION_SHARED_MECHANISM",
                "RELATION_SHARED_OWNER",
                "normalize_canonical_relation_handoff",
            },
            set(relation_handoff.__all__),
        )


if __name__ == "__main__":
    unittest.main()
