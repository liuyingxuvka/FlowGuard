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
    command_parts = command.split()
    check = {
        "check_id": "fixture-check",
        "kind": "command",
        "command": command_parts[0],
        "args": command_parts[1:],
    }
    source = {
        "schema_version": "skillguard.contract_source.v2",
        "skill_id": skill_id,
        "native_route_owner": "fixture-owner",
        "native_check_bindings": [
            {
                "authority": "target-native",
                "check_id": "fixture-check",
                "owner_id": "fixture-owner",
            }
        ],
        "checks": [check],
    }
    contract = {
        "schema_version": "skillguard.compiled_contract.v2",
        "skill_id": skill_id,
        "contract_hash": "FIXTURE-CONTRACT-HASH",
        "obligations": [
            {
                "obligation_id": "fixture-obligation",
                "required": True,
                "required_check_ids": ["fixture-check"],
            }
        ],
    }
    write_json(skill / ".skillguard/contract-source.json", source)
    write_json(skill / ".skillguard/compiled-contract.json", contract)
    write_json(
        skill / ".skillguard/check-manifest.json",
        {
            "schema_version": "skillguard.check_manifest.v2",
            "skill_id": skill_id,
            "contract_hash": "FIXTURE-CONTRACT-HASH",
            "checks": [check],
        },
    )
    write_json(
        root / ".skillguard/flowguard-suite/suite-map.json",
        {
            "schema_version": "skillguard.suite_map.v1",
            "suite_name": "flowguard-agent-skill-suite",
            "included_skills": [{"name": skill_id}],
        },
    )
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
            self.assertIn("native_check_failed:fixture-check:exit=7", result.receipt.blockers)

    def test_binding_mismatch_blocks_without_manufacturing_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_id = build_fixture(root)
            (root / "native_check.py").write_text("print('would pass')\n", encoding="utf-8")
            source_path = root / ".agents/skills" / skill_id / ".skillguard/contract-source.json"
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["checks"][0]["args"] = ["another.py"]
            write_json(source_path, source)

            result = run_native_skill_check(root, skill_id, timeout_seconds=10)

            self.assertFalse(result.ok)
            self.assertEqual("blocked", result.receipt.result_status)
            self.assertIn("native_binding_manifest_mismatch:fixture-check", result.receipt.blockers)


if __name__ == "__main__":
    unittest.main()
