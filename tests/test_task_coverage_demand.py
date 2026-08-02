from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from flowguard.__main__ import main
from flowguard.task_coverage_demand import (
    COVERAGE_DISPOSITION_BLOCKED,
    COVERAGE_DISPOSITION_SATISFIED,
    COVERAGE_TIER_DEEP,
    COVERAGE_TIER_ORDINARY,
    COVERAGE_TIER_RELEASE,
    COVERAGE_TIER_STANDARD,
    MODEL_MESH_TOPOLOGY_TRIGGERS,
    TaskFacts,
    compile_task_coverage_demand,
    resolve_coverage_demand_row,
)


class TaskCoverageDemandTests(unittest.TestCase):
    def test_cli_derives_demand_from_frozen_task_facts(self) -> None:
        with TemporaryDirectory() as directory:
            facts_path = Path(directory) / "task-facts.json"
            facts_path.write_text(
                json.dumps(
                    TaskFacts(
                        "task:cli",
                        "change and release one public command",
                        change_kinds=("public_api",),
                        implementation_requested=True,
                        release_requested=True,
                    ).to_dict()
                ),
                encoding="utf-8",
            )
            exit_code = main(
                ["task-coverage-demand", "--facts", str(facts_path), "--json"]
            )
        self.assertEqual(0, exit_code)

    def test_compilation_is_deterministic_and_caller_additions_are_monotonic(self) -> None:
        facts = TaskFacts(
            "task:api",
            "change one public command",
            change_kinds=("public_api",),
            caller_requested_owner_ids=("custom_owner",),
        )
        first = compile_task_coverage_demand(facts)
        second = compile_task_coverage_demand(facts)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertIn("behavior_commitment_ledger", first.required_owner_ids)
        self.assertIn("custom_owner", first.required_owner_ids)
        self.assertIn("existing_model_preflight", first.required_owner_ids)
        self.assertIn("model_first_function_flow", first.required_owner_ids)

    def test_small_read_only_task_stays_ordinary_with_visible_not_triggered_rows(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts("task:read", "inspect one model", read_only=True)
        )
        self.assertEqual(COVERAGE_TIER_ORDINARY, demand.presentation_tier)
        self.assertTrue(any(not row.triggered for row in demand.rows))
        self.assertTrue(all(row.reason for row in demand.rows if not row.triggered))

    def test_implementation_ui_mesh_and_release_raise_monotonically(self) -> None:
        standard = compile_task_coverage_demand(
            TaskFacts("task:code", "change code", implementation_requested=True)
        )
        deep = compile_task_coverage_demand(
            TaskFacts(
                "task:ui",
                "change UI flow",
                implementation_requested=True,
                change_kinds=("ui",),
                topology_signal_ids=(next(iter(MODEL_MESH_TOPOLOGY_TRIGGERS)),),
            )
        )
        release = compile_task_coverage_demand(
            TaskFacts("task:release", "release", implementation_requested=True, release_requested=True)
        )
        self.assertEqual(COVERAGE_TIER_STANDARD, standard.presentation_tier)
        self.assertEqual(COVERAGE_TIER_DEEP, deep.presentation_tier)
        self.assertEqual(COVERAGE_TIER_RELEASE, release.presentation_tier)
        self.assertTrue(set(standard.required_owner_ids).issubset(set(release.required_owner_ids)))

    def test_unrelated_model_count_does_not_trigger_model_mesh(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:one-model",
                "bounded model change",
                related_model_ids=("model:a", "model:b", "model:c"),
            )
        )
        mesh = next(row for row in demand.rows if row.owner_route == "model_mesh")
        self.assertFalse(mesh.triggered)

    def test_demand_closes_only_after_every_triggered_row_has_evidence(self) -> None:
        demand = compile_task_coverage_demand(TaskFacts("task:close", "non-trivial task"))
        self.assertFalse(demand.closed)
        for row in tuple(demand.rows):
            if row.triggered:
                demand = resolve_coverage_demand_row(
                    demand,
                    row.demand_id,
                    COVERAGE_DISPOSITION_SATISFIED,
                    reason="current owner evidence verified",
                    evidence_ids=(f"evidence:{row.owner_route}",),
                    evidence_fingerprints=(f"sha256:{row.owner_route}",),
                )
        self.assertTrue(demand.closed)
        self.assertEqual((), demand.unresolved_owner_ids)

    def test_blocked_disposition_requires_a_blocker_and_never_closes(self) -> None:
        demand = compile_task_coverage_demand(TaskFacts("task:block", "non-trivial task"))
        row = next(item for item in demand.rows if item.triggered)
        with self.assertRaises(ValueError):
            resolve_coverage_demand_row(
                demand,
                row.demand_id,
                COVERAGE_DISPOSITION_BLOCKED,
                reason="blocked",
            )
        blocked = resolve_coverage_demand_row(
            demand,
            row.demand_id,
            COVERAGE_DISPOSITION_BLOCKED,
            reason="owner unavailable",
            blocker_codes=("owner_unavailable",),
        )
        self.assertFalse(blocked.closed)
        self.assertIn(row.owner_route, blocked.blocked_owner_ids)


if __name__ == "__main__":
    unittest.main()
