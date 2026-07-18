from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.distribution_sync import OWNERSHIP_MANIFEST_NAME, OWNERSHIP_SCHEMA
from flowguard.skill_suite import (
    FLOWGUARD_EXPECTED_MEMBER_COUNT,
    FLOWGUARD_EXPECTED_SATELLITE_COUNT,
    FLOWGUARD_KERNEL_ROLE,
    FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
    FLOWGUARD_SATELLITE_ROLE,
    FLOWGUARD_SUITE_MAP,
    MODEL_PURPOSE_PROMPT_MARKERS,
    MODEL_PURPOSE_SKILL_MARKERS,
    validate_skill_suite,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SkillSuiteInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        canonical = json.loads((REPOSITORY_ROOT / FLOWGUARD_SUITE_MAP).read_text(encoding="utf-8"))
        self.map_data = canonical
        self._write_map()
        self._write_complete_members()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_map(self) -> None:
        path = self.root / FLOWGUARD_SUITE_MAP
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.map_data, indent=2), encoding="utf-8")

    def _write_complete_members(self) -> None:
        for member in self.map_data["included_skills"]:
            skill_dir = self.root / member["path"]
            for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES:
                path = skill_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative == "SKILL.md":
                    content = "\n".join((f"---\nname: {member['name']}\n---", *MODEL_PURPOSE_SKILL_MARKERS))
                elif relative == "agents/openai.yaml":
                    content = "\n".join(MODEL_PURPOSE_PROMPT_MARKERS)
                else:
                    content = f"fixture for {member['name']} {relative}"
                path.write_text(content + "\n", encoding="utf-8")

    def _write_ownership_manifest(
        self,
        *,
        member_ids: list[str] | None = None,
        schema_version: str = OWNERSHIP_SCHEMA,
    ) -> None:
        ids = member_ids or [member["name"] for member in self.map_data["included_skills"]]
        # An installer ownership manifest changes this fixture from author
        # source into a consumer distribution. Mirror the real projection:
        # retain only consumer files, remove author-side control state, and
        # add the compiler-owned release marker.
        for member in self.map_data["included_skills"]:
            skill_dir = self.root / member["path"]
            shutil.rmtree(skill_dir / ".skillguard", ignore_errors=True)
            (skill_dir / "consumer-release.json").write_text(
                json.dumps(
                    {
                        "artifact_type": "flowguard_consumer_skill_release",
                        "schema_version": "consumer.skill_distribution.current",
                        "skill_id": member["name"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        path = self.root / ".agents" / "skills" / OWNERSHIP_MANIFEST_NAME
        path.write_text(
            json.dumps(
                {
                    "artifact_type": "flowguard_skill_distribution_ownership",
                    "schema_version": schema_version,
                    "member_ids": ids,
                    "files": [
                        {"relative_path": f"{member_id}/SKILL.md"}
                        for member_id in ids
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_extra_skill(self, skill_id: str) -> None:
        path = self.root / ".agents" / "skills" / skill_id / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {skill_id}\n---\n", encoding="utf-8")

    def _codes(self) -> set[str]:
        return {finding.code for finding in validate_skill_suite(self.root).findings}

    def test_complete_inventory_has_one_kernel_and_fourteen_satellites(self) -> None:
        report = validate_skill_suite(self.root)
        self.assertTrue(report.ok, report.to_json_text())
        self.assertEqual(FLOWGUARD_EXPECTED_MEMBER_COUNT, len(report.declared_member_ids))
        self.assertEqual(FLOWGUARD_EXPECTED_MEMBER_COUNT, len(report.discovered_member_ids))
        self.assertEqual(1, sum(member.role == FLOWGUARD_KERNEL_ROLE for member in report.members))
        self.assertEqual(
            FLOWGUARD_EXPECTED_SATELLITE_COUNT,
            sum(member.role == FLOWGUARD_SATELLITE_ROLE for member in report.members),
        )
        self.assertEqual(64, len(report.inventory_hash))
        self.assertEqual(64, len(report.semantic_hash))

    def test_omitted_behavior_ledger_stays_visible_as_extra_discovered_member(self) -> None:
        self.map_data["included_skills"] = [
            member
            for member in self.map_data["included_skills"]
            if member["name"] != "flowguard-behavior-commitment-ledger"
        ]
        self._write_map()
        report = validate_skill_suite(self.root)
        rows = {(finding.code, finding.member_id) for finding in report.findings}
        self.assertIn(("extra_discovered_member", "flowguard-behavior-commitment-ledger"), rows)
        self.assertIn("invalid_suite_cardinality", self._codes())

    def test_undeclared_skill_directory_fails_reverse_discovery(self) -> None:
        extra = self.root / ".agents" / "skills" / "flowguard-unregistered" / "SKILL.md"
        extra.parent.mkdir(parents=True)
        extra.write_text("# undeclared\n", encoding="utf-8")
        report = validate_skill_suite(self.root)
        self.assertIn(
            ("extra_discovered_member", "flowguard-unregistered"),
            {(finding.code, finding.member_id) for finding in report.findings},
        )

    def test_owned_mixed_root_reports_unrelated_skills_separately(self) -> None:
        self._write_ownership_manifest()
        self._write_extra_skill("skillguard")
        self._write_extra_skill("skillguard-global-router")

        report = validate_skill_suite(self.root)
        payload = report.to_dict()

        self.assertTrue(report.ok, report.to_json_text())
        self.assertEqual(FLOWGUARD_EXPECTED_MEMBER_COUNT, len(report.discovered_member_ids))
        self.assertEqual(
            ("skillguard", "skillguard-global-router"),
            report.co_located_skill_ids,
        )
        self.assertEqual(2, payload["co_located_skill_count"])
        self.assertIn("not validated as part of FlowGuard", payload["claim_boundary"])

    def test_unowned_or_invalidly_owned_foreign_skill_remains_strict_extra(self) -> None:
        self._write_extra_skill("skillguard")
        report_without_manifest = validate_skill_suite(self.root)
        self.assertIn(
            ("extra_discovered_member", "skillguard"),
            {(finding.code, finding.member_id) for finding in report_without_manifest.findings},
        )

        self._write_ownership_manifest(
            member_ids=[member["name"] for member in self.map_data["included_skills"][:-1]]
        )
        report_with_incomplete_manifest = validate_skill_suite(self.root)
        self.assertIn(
            ("extra_discovered_member", "skillguard"),
            {(finding.code, finding.member_id) for finding in report_with_incomplete_manifest.findings},
        )

    def test_owned_mixed_root_still_rejects_reserved_flowguard_extra(self) -> None:
        self._write_ownership_manifest()
        self._write_extra_skill("skillguard")
        self._write_extra_skill("flowguard-unregistered")

        report = validate_skill_suite(self.root)

        self.assertFalse(report.ok)
        self.assertEqual(("skillguard",), report.co_located_skill_ids)
        self.assertIn(
            ("extra_discovered_member", "flowguard-unregistered"),
            {(finding.code, finding.member_id) for finding in report.findings},
        )

    def test_owned_mixed_root_does_not_hide_missing_canonical_member(self) -> None:
        self._write_ownership_manifest()
        self._write_extra_skill("skillguard")
        missing = self.map_data["included_skills"][1]["name"]
        shutil.rmtree(self.root / ".agents" / "skills" / missing)

        report = validate_skill_suite(self.root)

        self.assertFalse(report.ok)
        self.assertEqual(("skillguard",), report.co_located_skill_ids)
        self.assertIn(
            ("missing_declared_member", missing),
            {(finding.code, finding.member_id) for finding in report.findings},
        )

    def test_missing_declared_directory_fails_forward_discovery(self) -> None:
        missing = self.map_data["included_skills"][1]["name"]
        shutil.rmtree(self.root / ".agents" / "skills" / missing)
        report = validate_skill_suite(self.root)
        self.assertIn(
            ("missing_declared_member", missing),
            {(finding.code, finding.member_id) for finding in report.findings},
        )

    def test_duplicate_id_is_rejected(self) -> None:
        self.map_data["included_skills"].append(dict(self.map_data["included_skills"][0]))
        self._write_map()
        self.assertIn("duplicate_member", self._codes())

    def test_missing_control_root_does_not_remove_member(self) -> None:
        skill_id = "flowguard-behavior-commitment-ledger"
        shutil.rmtree(self.root / ".agents" / "skills" / skill_id / ".skillguard")
        report = validate_skill_suite(self.root)
        member = next(row for row in report.members if row.skill_id == skill_id)
        self.assertTrue(member.discovered)
        self.assertFalse(member.control_root_present)
        self.assertIn(
            ("missing_control_root", skill_id),
            {(finding.code, finding.member_id) for finding in report.findings},
        )

    def test_second_private_literal_inventory_is_rejected(self) -> None:
        private = self.root / "scripts" / "private_inventory.py"
        private.parent.mkdir(parents=True)
        names = [member["name"] for member in self.map_data["included_skills"][:4]]
        private.write_text(f"MEMBERS = {names!r}\n", encoding="utf-8")
        report = validate_skill_suite(self.root)
        self.assertIn("private_suite_inventory_detected", {finding.code for finding in report.findings})

    def test_current_repository_declares_all_skill_directories(self) -> None:
        report = validate_skill_suite(REPOSITORY_ROOT, check_private_inventories=False)
        self.assertEqual(FLOWGUARD_EXPECTED_MEMBER_COUNT, len(report.declared_member_ids))
        self.assertEqual(set(report.declared_member_ids), set(report.discovered_member_ids))
        self.assertIn("flowguard-behavior-commitment-ledger", report.declared_member_ids)

    def test_inventory_scripts_project_the_same_inventory(self) -> None:
        suite = subprocess.run(
            [sys.executable, "scripts/verify_skill_suite_markers.py", "--root", ".", "--json"],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        readiness = subprocess.run(
            [
                sys.executable,
                "scripts/verify_guard_simulation_readiness.py",
                "--root",
                ".",
                "--json",
            ],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        suite_payload = json.loads(suite.stdout)
        readiness_payload = json.loads(readiness.stdout)
        self.assertEqual(suite_payload["inventory_hash"], readiness_payload["inventory_hash"])
        self.assertEqual(suite_payload["declared_member_ids"], readiness_payload["member_ids"])
        self.assertEqual(FLOWGUARD_EXPECTED_MEMBER_COUNT, len(readiness_payload["member_ids"]))


if __name__ == "__main__":
    unittest.main()
