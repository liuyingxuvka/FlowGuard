from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from flowguard.skill_contracts import (
    CHECK_MANIFEST_FILE,
    COMPILED_CONTRACT_FILE,
    CONTRACT_SOURCE_FILE,
    compile_skill_contract,
    compile_skill_suite,
    validate_contract_source,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL_ID = "flowguard"
SKILL = ROOT / ".agents" / "skills" / SKILL_ID


class CurrentSkillContractParityTests(unittest.TestCase):
    def test_current_source_is_accepted_and_former_fields_are_rejected(self) -> None:
        source = json.loads((SKILL / CONTRACT_SOURCE_FILE).read_text(encoding="utf-8"))
        self.assertFalse(validate_contract_source(source, SKILL))

        former = dict(source)
        former["v1_runtime_authority"] = {"status": "migration-evidence"}
        self.assertIn(
            "unknown_compact_contract_field:v1_runtime_authority",
            validate_contract_source(former, SKILL),
        )

        missing_model_owner = json.loads(json.dumps(source))
        missing_model_owner["obligations"][0]["check_ids"] = ["check:missing"]
        self.assertIn(
            "obligation_check_ids_invalid:0",
            validate_contract_source(missing_model_owner, SKILL),
        )

    def test_repository_member_has_current_five_file_parity(self) -> None:
        compiled, manifest, findings, written = compile_skill_contract(SKILL)
        self.assertFalse(findings)
        self.assertFalse(written)
        self.assertEqual("skillguard.compiled_contract.v3", compiled["schema_version"])
        self.assertEqual("skillguard.check_manifest.v3", manifest["schema_version"])
        self.assertEqual(compiled["contract_hash"], manifest["contract_hash"])

    def test_flowguard_reader_never_writes_an_alternate_authority(self) -> None:
        compiled, manifest, findings, written = compile_skill_contract(SKILL, write=True)
        self.assertFalse(compiled)
        self.assertFalse(manifest)
        self.assertFalse(written)
        self.assertEqual(
            {"official_current_compiler_required"},
            {finding.code for finding in findings},
        )

    def test_binding_change_and_former_residual_both_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            copied_skill = repo / ".agents" / "skills" / SKILL_ID
            copied_skill.parent.mkdir(parents=True)
            shutil.copytree(SKILL, copied_skill)
            suite_map = repo / ".skillguard" / "flowguard-suite" / "suite-map.json"
            suite_map.parent.mkdir(parents=True)
            shutil.copy2(
                ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json",
                suite_map,
            )
            model = repo / ".flowguard" / "models" / "owners" / "development_process_flow" / "model.py"
            model.parent.mkdir(parents=True)
            shutil.copy2(
                ROOT / ".flowguard" / "models" / "owners" / "development_process_flow" / "model.py",
                model,
            )

            source_path = copied_skill / CONTRACT_SOURCE_FILE
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["checks"][0]["expected"]["exit_code"] = 1
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (copied_skill / ".skillguard" / "work-contract.json").write_text(
                "{}\n", encoding="utf-8"
            )

            _, _, findings, _ = compile_skill_contract(copied_skill)
            codes = {finding.code for finding in findings}
            self.assertIn("binding_fingerprint_stale", codes)
            self.assertIn("former_runtime_authority_residual", codes)

    def test_single_current_member_passes_current_parity(self) -> None:
        report = compile_skill_suite(ROOT)
        self.assertTrue(report.ok, report.to_json_text())
        self.assertEqual(("flowguard",), report.member_ids)
        self.assertEqual(1, len(report.contract_hashes))

    def test_current_authority_root_contains_only_current_files(self) -> None:
        current_ids = compile_skill_suite(ROOT).member_ids
        for skill_id in current_ids:
            skill_root = ROOT / ".agents" / "skills" / skill_id
            authority = skill_root / ".skillguard"
            if not authority.is_dir():
                continue
            with self.subTest(skill=skill_root.name):
                current_files = {
                    Path(CONTRACT_SOURCE_FILE).name,
                    Path(COMPILED_CONTRACT_FILE).name,
                    Path(CHECK_MANIFEST_FILE).name,
                    "surface-inventory.json",
                    "surface-semantic-map.json",
                }
                self.assertEqual(
                    current_files,
                    {path.name for path in authority.iterdir() if path.is_file()},
                )
                self.assertTrue(
                    all(path.name == "archive" and path.is_dir() for path in authority.iterdir() if path.is_dir()),
                    f"unexpected non-current authority directories: {sorted(path.name for path in authority.iterdir() if path.is_dir())}",
                )


if __name__ == "__main__":
    unittest.main()
