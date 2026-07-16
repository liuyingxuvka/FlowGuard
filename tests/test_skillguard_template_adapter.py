import unittest

from flowguard.skillguard_template_adapter import (
    BASE_ROUTE_ID,
    PROJECTION_SCHEMA,
    build_skillguard_template_projection,
)
from flowguard.template_packs import _digest


class SkillGuardTemplateAdapterTests(unittest.TestCase):
    def projection(self, route_id=BASE_ROUTE_ID):
        return build_skillguard_template_projection(
            target_id="target:flowguard-test",
            route_id=route_id,
            request_fingerprint=_digest({"request": route_id}),
        )

    def test_base_projection_has_exact_candidate_accounting(self):
        projection = self.projection()
        self.assertEqual(PROJECTION_SCHEMA, projection["schema_version"])
        template_ids = {row["template_id"] for row in projection["catalog"]["templates"]}
        result_ids = {row["template_id"] for row in projection["applicability_results"]}
        self.assertEqual(template_ids, result_ids)
        eligible = {row["template_id"] for row in projection["applicability_results"] if row["eligible"]}
        self.assertEqual({projection["catalog"]["base_template_id"]}, eligible)
        self.assertTrue(
            any(
                row["template_id"].startswith("flowguard.risk.")
                for row in projection["catalog"]["templates"]
            )
        )

    def test_exact_native_route_selects_one_domain_template_plus_base_availability(self):
        base = self.projection()
        route_id = next(
            row["route_ids"][0]
            for row in base["catalog"]["templates"]
            if not row["is_validated_base"]
        )
        projection = self.projection(route_id)
        eligible = [row["template_id"] for row in projection["applicability_results"] if row["eligible"]]
        self.assertEqual(2, len(eligible))
        self.assertIn(projection["catalog"]["base_template_id"], eligible)
        domain = [
            row["template_id"]
            for row in projection["catalog"]["templates"]
            if route_id in row["route_ids"]
        ]
        self.assertEqual(1, len(domain))
        self.assertIn(domain[0], eligible)

    def test_unknown_route_and_bad_fingerprint_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown FlowGuard template route"):
            self.projection("route:flowguard-template:not-declared")
        with self.assertRaisesRegex(ValueError, "request_fingerprint"):
            build_skillguard_template_projection(
                target_id="target:flowguard-test",
                route_id=BASE_ROUTE_ID,
                request_fingerprint="stale",
            )


if __name__ == "__main__":
    unittest.main()
