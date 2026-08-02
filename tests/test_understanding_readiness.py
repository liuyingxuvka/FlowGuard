from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import flowguard
from flowguard.__main__ import main
from flowguard.task_coverage_demand import (
    COVERAGE_DISPOSITION_SATISFIED,
    OwnerCoverageResolution,
    TASK_FACT_SOURCE_CURRENT_MODEL,
    TASK_FACT_SOURCE_LIFECYCLE,
    TASK_FACT_SOURCE_PUBLIC_SURFACE,
    TASK_FACT_SOURCE_REQUEST,
    TaskFactSourceSnapshot,
    TaskFacts,
    compile_task_coverage_demand,
    project_owner_resolution_to_demand,
)
from flowguard.understanding_readiness import (
    ADMISSION_BLOCKED,
    ADMISSION_NO_CODE,
    ADMISSION_READY,
    UNDERSTANDING_NOT_RUN,
    UNDERSTANDING_SCOPED_VERIFIED,
    UNDERSTANDING_STALE,
    UNDERSTANDING_VERIFIED,
    USER_CHOICE_DIRECT,
    USER_CHOICE_NO_CODE,
    UnderstandingReadinessInput,
    compose_understanding_status,
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


class UnderstandingReadinessTests(unittest.TestCase):
    def complete_artifacts(self):
        facts = TaskFacts(
            "task:complete",
            "prove one exact current task",
            implementation_requested=True,
            source_snapshots=_complete_source_snapshots(),
        )
        demand = compile_task_coverage_demand(facts)
        basis_fingerprint = demand.fingerprint
        resolutions = []
        for owner in demand.required_owner_ids:
            rows = tuple(
                row for row in demand.rows if row.triggered and row.owner_route == owner
            )
            resolution = OwnerCoverageResolution(
                f"resolution:{owner}",
                demand.task_id,
                demand.demand_id,
                basis_fingerprint,
                owner,
                COVERAGE_DISPOSITION_SATISFIED,
                tuple(
                    coverage_id for row in rows for coverage_id in row.coverage_ids
                ),
                evidence_ids=(f"evidence:{owner}",),
                evidence_fingerprints=("sha256:" + owner.encode().hex().ljust(64, "0")[:64],),
            )
            resolutions.append(resolution)
            demand = project_owner_resolution_to_demand(demand, resolution)

        model_fingerprint = "sha256:" + "b" * 64
        demand_payload = {**demand.to_dict(), "fingerprint": demand.fingerprint}
        maturation = {
            "task_id": facts.task_id,
            "model_id": "model:current",
            "candidate_model_fingerprint": model_fingerprint,
            "coverage_demand_fingerprint": demand.fingerprint,
            "decision": "model_maturation_closed_for_task",
            "confidence": "full",
            "open_gap_fingerprints": [],
            "evidence_id": "evidence:maturation",
            "owner_resolution_ids": [value.resolution_id for value in resolutions],
            "owner_resolution_fingerprints": [
                value.resolution_fingerprint for value in resolutions
            ],
            "owner_resolution_owner_ids": [value.owner_route for value in resolutions],
        }
        verified = {
            **maturation,
            "receipt_id": "receipt:maturation",
            "receipt_fingerprint": "sha256:" + "d" * 64,
            "current": True,
            "eligible_for_full_claim": True,
        }
        return {
            "task_facts": facts.to_dict(),
            "model_identity": {
                "model_id": "model:current",
                "candidate_model_fingerprint": model_fingerprint,
            },
            "coverage_demand": demand_payload,
            "owner_resolutions": tuple(
                {**resolution.to_dict(), "fingerprint": resolution.fingerprint}
                for resolution in resolutions
            ),
            "maturation_report": maturation,
            "receipt_verification": {
                "ok": True,
                "receipt_ref": {
                    "receipt_id": verified["receipt_id"],
                    "receipt_fingerprint": verified["receipt_fingerprint"],
                },
                "receipt_verification": {
                    "receipt_id": verified["receipt_id"],
                    "receipt_fingerprint": verified["receipt_fingerprint"],
                    "current": True,
                    "eligible": True,
                    "status": "pass",
                    "finding_codes": [],
                    "findings": [],
                    "satisfied_obligations": ["task-model-maturation"],
                    "minimum_revalidation": [],
                },
                "verified_maturation": verified,
                "semantic_finding_codes": [],
            },
            "implementation_admission": {
                "ok": True,
                "admission_id": "admission:current",
                "status": "ready",
            },
        }

    def test_complete_exact_artifacts_report_verified_ready(self) -> None:
        status = compose_understanding_status(
            UnderstandingReadinessInput(**self.complete_artifacts())
        )
        self.assertTrue(status.ok)
        self.assertEqual(UNDERSTANDING_VERIFIED, status.understanding_sufficiency)
        self.assertEqual(ADMISSION_READY, status.implementation_admission)
        self.assertEqual([], status.to_dict()["mismatch_fields"])

    def test_direct_user_choice_never_upgrades_missing_understanding(self) -> None:
        status = compose_understanding_status(
            UnderstandingReadinessInput(user_choice=USER_CHOICE_DIRECT)
        )
        self.assertEqual(USER_CHOICE_DIRECT, status.user_choice)
        self.assertEqual(UNDERSTANDING_NOT_RUN, status.understanding_sufficiency)
        self.assertEqual(ADMISSION_BLOCKED, status.implementation_admission)

    def test_no_code_is_independent_of_understanding(self) -> None:
        status = compose_understanding_status(
            UnderstandingReadinessInput(user_choice=USER_CHOICE_NO_CODE)
        )
        self.assertEqual(UNDERSTANDING_NOT_RUN, status.understanding_sufficiency)
        self.assertEqual(ADMISSION_NO_CODE, status.implementation_admission)

    def test_forged_or_stale_model_identity_cannot_pass(self) -> None:
        artifacts = self.complete_artifacts()
        artifacts["model_identity"] = {
            "model_id": "model:changed",
            "candidate_model_fingerprint": "sha256:" + "c" * 64,
        }
        status = compose_understanding_status(UnderstandingReadinessInput(**artifacts))
        self.assertEqual(UNDERSTANDING_STALE, status.understanding_sufficiency)
        self.assertIn(
            "verified_maturation.candidate_model_fingerprint",
            status.mismatch_fields,
        )

    def test_current_scoped_receipt_reports_scoped_verified_not_full(self) -> None:
        artifacts = self.complete_artifacts()
        artifacts["maturation_report"]["confidence"] = "scoped"
        artifacts["receipt_verification"]["ok"] = False
        artifacts["receipt_verification"]["verified_maturation"][
            "confidence"
        ] = "scoped"
        artifacts["receipt_verification"]["verified_maturation"][
            "eligible_for_full_claim"
        ] = False
        artifacts["receipt_verification"]["receipt_verification"].update(
            {"eligible": False, "status": "scoped"}
        )
        artifacts["implementation_admission"]["status"] = "ready_scoped"
        status = compose_understanding_status(UnderstandingReadinessInput(**artifacts))
        self.assertEqual(
            UNDERSTANDING_SCOPED_VERIFIED,
            status.understanding_sufficiency,
        )
        self.assertEqual("ready_scoped", status.implementation_admission)

    def test_caller_forged_ok_boolean_without_verification_material_cannot_pass(self) -> None:
        artifacts = self.complete_artifacts()
        artifacts["receipt_verification"] = {
            "ok": True,
            "verified_maturation": artifacts["receipt_verification"][
                "verified_maturation"
            ],
        }
        status = compose_understanding_status(UnderstandingReadinessInput(**artifacts))
        self.assertNotEqual(UNDERSTANDING_VERIFIED, status.understanding_sufficiency)
        self.assertIn("receipt_verification_material_missing", status.blocker_codes)

    def test_duplicate_owner_resolution_blocks(self) -> None:
        artifacts = self.complete_artifacts()
        artifacts["owner_resolutions"] = (
            *artifacts["owner_resolutions"],
            artifacts["owner_resolutions"][0],
        )
        status = compose_understanding_status(UnderstandingReadinessInput(**artifacts))
        self.assertEqual("blocked", status.understanding_sufficiency)
        self.assertTrue(
            any(code.startswith("duplicate_owner_resolution:") for code in status.blocker_codes)
        )

    def test_maturation_cannot_name_a_foreign_owner_resolution(self) -> None:
        artifacts = self.complete_artifacts()
        artifacts["receipt_verification"]["verified_maturation"][
            "owner_resolution_fingerprints"
        ] = ["sha256:" + "f" * 64]
        status = compose_understanding_status(UnderstandingReadinessInput(**artifacts))
        self.assertEqual(UNDERSTANDING_STALE, status.understanding_sufficiency)
        self.assertIn(
            "verified_maturation.owner_resolution_fingerprints",
            status.mismatch_fields,
        )

    def test_cli_reads_explicit_artifacts_without_writing(self) -> None:
        artifacts = self.complete_artifacts()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = ["model-understanding-status"]
            option_names = {
                "task_facts": "--task-facts",
                "model_identity": "--model-identity",
                "coverage_demand": "--coverage-demand",
                "maturation_report": "--maturation-report",
                "receipt_verification": "--receipt-verification",
                "implementation_admission": "--implementation-admission",
            }
            for key, option in option_names.items():
                path = root / f"{key}.json"
                path.write_text(json.dumps(artifacts[key]), encoding="utf-8")
                arguments.extend((option, str(path)))
            for index, resolution in enumerate(artifacts["owner_resolutions"]):
                path = root / f"resolution-{index}.json"
                path.write_text(json.dumps(resolution), encoding="utf-8")
                arguments.extend(("--owner-resolution", str(path)))
            arguments.append("--json")
            before = sorted(path.name for path in root.iterdir())
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(arguments)
            after = sorted(path.name for path in root.iterdir())
        self.assertEqual(0, exit_code)
        self.assertEqual(before, after)
        payload = json.loads(output.getvalue())
        self.assertEqual(UNDERSTANDING_VERIFIED, payload["understanding_sufficiency"])

    def test_status_api_is_registered_only_under_existing_kernel_route(self) -> None:
        names = {
            "UnderstandingReadinessInput",
            "UnderstandingReadinessStatus",
            "compose_understanding_status",
        }
        self.assertTrue(
            names.issubset(flowguard.FLOWGUARD_ROUTE_API["model_first_function_flow"])
        )
        for route_id, route_names in flowguard.FLOWGUARD_ROUTE_API.items():
            if route_id != "model_first_function_flow":
                self.assertTrue(names.isdisjoint(route_names), route_id)


if __name__ == "__main__":
    unittest.main()
