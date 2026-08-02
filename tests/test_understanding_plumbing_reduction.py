import unittest

from flowguard import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


class UnderstandingPlumbingReductionTests(unittest.TestCase):
    def test_model_derived_target_structure_has_one_owner_per_stage(self):
        modules = (
            TargetModuleRecommendation(
                "route_identity",
                path="flowguard/route_topology.py",
                owns_function_blocks=("ResolvePublicOwner",),
                validation_boundaries=("route and API parity tests",),
                rationale="one descriptor owns route, skill, coverage, and admission identity",
            ),
            TargetModuleRecommendation(
                "coverage_demand",
                path="flowguard/task_coverage_demand.py",
                owns_function_blocks=("CompileTaskCoverageDemand", "ResolveOwnerCoverage"),
                validation_boundaries=("task fact and owner-resolution tests",),
                rationale="one immutable resolution is the only owner result",
            ),
            TargetModuleRecommendation(
                "maturation",
                path="flowguard/model_maturation.py",
                owns_function_blocks=("ReviewModelMaturation",),
                validation_boundaries=("maturation and receipt identity tests",),
                rationale="maturation consumes rather than recreates owner resolutions",
            ),
            TargetModuleRecommendation(
                "readiness_view",
                path="flowguard/understanding_readiness.py",
                owns_function_blocks=("ComposeUnderstandingStatus",),
                public_entrypoints=("compose_understanding_status", "model-understanding-status"),
                validation_boundaries=("read-only status and CLI side-effect tests",),
                rationale="the status facade only projects the three independent axes",
            ),
            TargetModuleRecommendation(
                "closure_integrity",
                path="flowguard/closure_contract.py",
                owns_function_blocks=("ReviewClosureIntegrity",),
                validation_boundaries=("closure identity and terminal-pair tests",),
                rationale="closure checks exact material and projects the upstream terminal decision",
            ),
        )
        recommendation = CodeStructureRecommendation(
            "flowguard-understanding-plumbing-v1",
            source_model_id="flowguard-self-understanding-semantic-mesh",
            source_model_path=".flowguard/model_mesh_closure_model/model.py",
            parent_module_id="flowguard-understanding",
            target_modules=modules,
            function_block_map=(
                ("ResolvePublicOwner", "route_identity"),
                ("CompileTaskCoverageDemand", "coverage_demand"),
                ("ResolveOwnerCoverage", "coverage_demand"),
                ("ReviewModelMaturation", "maturation"),
                ("ComposeUnderstandingStatus", "readiness_view"),
                ("ReviewClosureIntegrity", "closure_integrity"),
            ),
            public_entrypoint_map=(
                ("compose_understanding_status", "readiness_view"),
                ("model-understanding-status", "readiness_view"),
            ),
            validation_boundaries=(
                "public route/API facade parity",
                "owner resolution identity continuity",
                "receipt verification",
                "read-only status side-effect boundary",
                "closure terminal-pair projection",
            ),
            rationale="the target keeps one semantic owner at each stage and no parallel success path",
        )

        report = review_code_structure_recommendation(recommendation)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(0, report.blocker_count())


if __name__ == "__main__":
    unittest.main()
