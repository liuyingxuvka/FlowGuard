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
    OwnerCoverageResolution,
    TASK_FACT_DISPOSITION_OMITTED,
    TASK_FACT_DISPOSITION_UNKNOWN,
    TASK_FACT_SOURCE_CURRENT_MODEL,
    TASK_FACT_SOURCE_LIFECYCLE,
    TASK_FACT_SOURCE_PUBLIC_SURFACE,
    TASK_FACT_SOURCE_REQUEST,
    TaskFactObservation,
    TaskFactSourceSnapshot,
    TaskFacts,
    compile_task_coverage_demand,
    project_owner_resolution_to_demand,
    resolve_coverage_demand_row,
)


def _complete_source_snapshots() -> tuple[TaskFactSourceSnapshot, ...]:
    return tuple(
        TaskFactSourceSnapshot(
            source_plane,
            f"artifact:{source_plane}",
            "sha256:" + source_plane.encode("utf-8").hex().ljust(64, "0")[:64],
        )
        for source_plane in (
            TASK_FACT_SOURCE_REQUEST,
            TASK_FACT_SOURCE_CURRENT_MODEL,
            TASK_FACT_SOURCE_PUBLIC_SURFACE,
            TASK_FACT_SOURCE_LIFECYCLE,
        )
    )


class TaskCoverageDemandTests(unittest.TestCase):
    def test_missing_independent_source_plane_blocks_the_denominator(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:missing-source-plane",
                "inspect an existing command",
                source_snapshots=_complete_source_snapshots()[:-1],
            )
        )

        self.assertIn(
            "task_fact_source_not_observed:lifecycle",
            demand.fact_diagnostic_codes,
        )
        row = next(
            row
            for row in demand.rows
            if row.demand_id == "demand:task-fact-source:lifecycle"
        )
        self.assertEqual(COVERAGE_DISPOSITION_BLOCKED, row.disposition)
        with self.assertRaisesRegex(ValueError, "demand recompilation"):
            resolve_coverage_demand_row(
                demand,
                row.demand_id,
                COVERAGE_DISPOSITION_SATISFIED,
                reason="caller tried to fill a missing source after compilation",
                evidence_ids=("evidence:forged",),
                evidence_fingerprints=("sha256:" + "f" * 64,),
            )

    def test_complete_source_snapshots_are_bound_into_the_demand(self) -> None:
        facts = TaskFacts(
            "task:complete-source-planes",
            "inspect an existing command",
            source_snapshots=_complete_source_snapshots(),
        )
        demand = compile_task_coverage_demand(facts)

        self.assertEqual(4, len(demand.source_snapshots))
        self.assertFalse(
            any(code.startswith("task_fact_source_") for code in demand.fact_diagnostic_codes)
        )

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
        mesh = next(
            row for row in demand.rows if row.owner_route == "model_mesh_maintenance"
        )
        self.assertFalse(mesh.triggered)

    def test_omitted_independent_fact_remains_in_denominator_and_blocks(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:omitted",
                "caller omitted one observed public command",
                fact_observations=(
                    TaskFactObservation(
                        "command:model-understanding-status",
                        TASK_FACT_SOURCE_PUBLIC_SURFACE,
                        TASK_FACT_DISPOSITION_OMITTED,
                        reason="the command exists in the public surface but is absent from the caller inventory",
                    ),
                ),
            )
        )
        row = next(
            row
            for row in demand.rows
            if row.coverage_ids == ("task-fact:command:model-understanding-status",)
        )
        self.assertEqual(COVERAGE_DISPOSITION_BLOCKED, row.disposition)
        self.assertIn(
            "task_fact_omitted:command:model-understanding-status",
            demand.fact_diagnostic_codes,
        )
        self.assertFalse(demand.closed)

    def test_unknown_fact_with_current_owner_creates_explicit_demand(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:unknown",
                "resolve an unknown current-model fact",
                fact_observations=(
                    TaskFactObservation(
                        "model:semantic-parent",
                        TASK_FACT_SOURCE_CURRENT_MODEL,
                        TASK_FACT_DISPOSITION_UNKNOWN,
                        owner_route="model_mesh_maintenance",
                    ),
                ),
            )
        )
        row = next(
            row
            for row in demand.rows
            if row.coverage_ids == ("task-fact:model:semantic-parent",)
        )
        self.assertEqual("model_mesh_maintenance", row.owner_route)
        self.assertEqual("unresolved", row.disposition)

    def test_retired_model_mesh_owner_is_rejected_without_alias(self) -> None:
        with self.assertRaisesRegex(ValueError, "retired public route identity"):
            compile_task_coverage_demand(
                TaskFacts(
                    "task:retired",
                    "reject a retired owner",
                    caller_requested_owner_ids=("model_mesh",),
                )
            )

    def test_one_owner_resolution_projects_to_all_of_its_rows(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:release-owner",
                "release through one process owner result",
                implementation_requested=True,
                release_requested=True,
            )
        )
        owned_rows = tuple(
            row
            for row in demand.rows
            if row.triggered and row.owner_route == "development_process_flow"
        )
        self.assertGreater(len(owned_rows), 1)
        resolution = OwnerCoverageResolution(
            "resolution:process",
            demand.task_id,
            demand.demand_id,
            demand.fingerprint,
            "development_process_flow",
            COVERAGE_DISPOSITION_SATISFIED,
            tuple(
                coverage_id
                for row in owned_rows
                for coverage_id in row.coverage_ids
            ),
            evidence_ids=("evidence:process",),
            evidence_fingerprints=("sha256:" + "a" * 64,),
        )
        projected = project_owner_resolution_to_demand(demand, resolution)
        projected_rows = tuple(
            row
            for row in projected.rows
            if row.triggered and row.owner_route == "development_process_flow"
        )
        self.assertTrue(
            all(row.disposition == COVERAGE_DISPOSITION_SATISFIED for row in projected_rows)
        )
        self.assertEqual(demand.fingerprint, projected.resolution_basis_fingerprint)

    def test_demand_closes_only_after_every_triggered_row_has_evidence(self) -> None:
        demand = compile_task_coverage_demand(
            TaskFacts(
                "task:close",
                "non-trivial task",
                source_snapshots=_complete_source_snapshots(),
            )
        )
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
