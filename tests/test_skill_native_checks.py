import json
import tempfile
import unittest
from pathlib import Path

from flowguard.evidence_receipts import list_evidence_receipts, verify_evidence_receipt
from flowguard.skill_native_checks import (
    build_current_native_receipt_context,
    run_native_skill_check,
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def build_fixture(root, *, command="python native_check.py"):
    skill_id = "flowguard-fixture"
    skill = root / ".agents/skills" / skill_id
    (skill / "agents").mkdir(parents=True)
    (skill / ".skillguard").mkdir()
    (root / "flowguard").mkdir()
    (root / "flowguard/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (skill / "SKILL.md").write_text("---\nname: flowguard-fixture\n---\n# Fixture\n", encoding="utf-8")
    (skill / "agents/openai.yaml").write_text("interface:\n  display_name: Fixture\n", encoding="utf-8")
    source = {
        "schema_version": "flowguard.skill_contract_source.v1",
        "skill_id": skill_id,
        "native_checks": {
            "binding_id": "fixture-native",
            "native_check_id": "fixture-check",
            "kind": "pytest",
            "command": command,
        },
    }
    contract = {
        "contract_hash": "FIXTURE-CONTRACT-HASH",
        "native_check_bindings": [{"binding_id": "fixture-native", "command": command}],
        "acceptance_obligations": [
            {
                "obligation_id": "fixture-obligation",
                "required": True,
                "native_check_binding_ids": ["fixture-native"],
            }
        ],
    }
    write_json(skill / ".skillguard/contract-source.json", source)
    write_json(skill / ".skillguard/work-contract.json", contract)
    write_json(skill / ".skillguard/check_manifest.json", {"checks": [{"check_id": "fixture-check"}]})
    write_json(root / ".skillguard/flowguard-suite/suite-map.json", {"included_skills": [{"name": skill_id}]})
    return skill_id


class SkillNativeCheckTests(unittest.TestCase):
    def test_pass_receipt_recomputes_current_context_and_detects_input_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_id = build_fixture(root)
            (root / "native_check.py").write_text("print('pass')\n", encoding="utf-8")

            result = run_native_skill_check(root, skill_id, timeout_seconds=10)
            context = build_current_native_receipt_context(result.receipt, root)
            verified = verify_evidence_receipt(result.receipt, context)

            self.assertTrue(result.ok, result.to_dict())
            self.assertTrue(verified.ok, verified.to_dict())
            self.assertEqual(1, len(list_evidence_receipts(root)))
            self.assertTrue(result.proof_path.is_file())
            self.assertTrue(result.log_path.is_file())
            self.assertNotIn(str(Path.home()), result.receipt.to_json())

            (root / "native_check.py").write_text("print('changed')\n", encoding="utf-8")
            stale = verify_evidence_receipt(
                result.receipt,
                build_current_native_receipt_context(result.receipt, root),
            )
            self.assertFalse(stale.current)
            self.assertIn("input_raw_hash_mismatch", stale.finding_codes)

    def test_failed_native_command_emits_failed_receipt_that_parent_cannot_promote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_id = build_fixture(root)
            (root / "native_check.py").write_text("raise SystemExit(7)\n", encoding="utf-8")

            result = run_native_skill_check(root, skill_id, timeout_seconds=10)
            verified = verify_evidence_receipt(
                result.receipt,
                build_current_native_receipt_context(result.receipt, root),
            )

            self.assertFalse(result.ok)
            self.assertEqual("fail", result.receipt.result_status)
            self.assertEqual(7, result.receipt.exit_code)
            self.assertFalse(verified.eligible)
            self.assertIn("native_check_failed:fixture-native:exit=7", result.receipt.blockers)

    def test_binding_mismatch_blocks_without_manufacturing_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_id = build_fixture(root)
            (root / "native_check.py").write_text("print('would pass')\n", encoding="utf-8")
            contract_path = root / ".agents/skills" / skill_id / ".skillguard/work-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["native_check_bindings"][0]["command"] = "python another.py"
            write_json(contract_path, contract)

            result = run_native_skill_check(root, skill_id, timeout_seconds=10)

            self.assertFalse(result.ok)
            self.assertEqual("blocked", result.receipt.result_status)
            self.assertIn("native_binding_command_mismatch:fixture-native", result.receipt.blockers)


if __name__ == "__main__":
    unittest.main()
