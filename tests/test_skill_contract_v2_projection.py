from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from flowguard.skill_contracts import (
    CHECK_MANIFEST_SCHEMA,
    COMPILED_CONTRACT_SCHEMA,
    CONTRACT_SOURCE_SCHEMA,
    compile_skill_suite,
    validate_contract_source,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "flowguard"
AUTHORITY = SKILL / ".skillguard"


class SkillContractCurrentProjectionTests(unittest.TestCase):
    def test_single_source_uses_current_v3_authority_and_three_lifecycles(self) -> None:
        source = json.loads((AUTHORITY / "contract-source.json").read_text(encoding="utf-8"))

        self.assertEqual(CONTRACT_SOURCE_SCHEMA, source["schema_version"])
        self.assertEqual("flowguard", source["skill_id"])
        self.assertEqual("unit:flowguard-suite", source["maintenance_unit_id"])
        self.assertEqual(["flowguard"], source["member_skill_ids"])
        self.assertEqual(
            {"route:read", "route:change", "route:release"},
            {row["route_id"] for row in source["routes"]},
        )
        self.assertFalse(validate_contract_source(source, SKILL))
        self.assertNotIn("depth_profile", source)
        self.assertNotIn("v1_runtime_authority", source)

    def test_legacy_v2_source_is_rejection_only(self) -> None:
        source = json.loads((AUTHORITY / "contract-source.json").read_text(encoding="utf-8"))
        legacy = copy.deepcopy(source)
        legacy["schema_version"] = "skillguard.contract_source.v2"

        findings = validate_contract_source(legacy, SKILL)

        self.assertIn("contract_source_schema_mismatch", findings)
        self.assertTrue(findings)

    def test_generated_v3_contract_and_manifest_match_current_source(self) -> None:
        source = json.loads((AUTHORITY / "contract-source.json").read_text(encoding="utf-8"))
        compiled = json.loads((AUTHORITY / "compiled-contract.json").read_text(encoding="utf-8"))
        manifest = json.loads((AUTHORITY / "check-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(COMPILED_CONTRACT_SCHEMA, compiled["schema_version"])
        self.assertEqual(CHECK_MANIFEST_SCHEMA, manifest["schema_version"])
        self.assertEqual(source["skill_id"], compiled["skill_id"])
        self.assertEqual(source["member_skill_ids"], compiled["member_skill_ids"])
        self.assertEqual(compiled["contract_hash"], manifest["contract_hash"])
        self.assertEqual(
            {"route:read", "route:change", "route:release"},
            {row["route_id"] for row in compiled["routes"]},
        )
        self.assertNotIn(".skillguard", " ".join(compiled["consumer_projection"]["file_paths"]))

    def test_suite_compiler_accepts_only_the_current_member(self) -> None:
        report = compile_skill_suite(ROOT)

        self.assertTrue(report.ok, report.to_json_text())
        self.assertEqual(("flowguard",), report.member_ids)
        self.assertEqual(1, len(report.contract_hashes))


if __name__ == "__main__":
    unittest.main()
