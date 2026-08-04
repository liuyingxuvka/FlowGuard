import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from flowguard.model_regressions import (
    ModelRegressionEntry,
    _shard_safety_proof_dir,
)
from flowguard.shard_safety import CONTRACT_SCHEMA, prove_model_shard_safety


class ModelShardSafetyProofTests(unittest.TestCase):
    def _repository(self, *, mutate_shared: bool = False) -> tuple[tempfile.TemporaryDirectory, Path, ModelRegressionEntry]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        model_dir = root / ".flowguard" / "sample"
        model_dir.mkdir(parents=True)
        model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
        mutation = (
            "(root / 'shared.txt').write_text('changed', encoding='utf-8')"
            if mutate_shared
            else ""
        )
        model_dir.joinpath("run_checks.py").write_text(
            textwrap.dedent(
                f"""
                import json
                import os
                from pathlib import Path

                root = Path(__file__).resolve().parents[2]
                output = Path(os.environ["FLOWGUARD_OUTPUT_DIR"])
                output.mkdir(parents=True, exist_ok=True)
                {mutation}
                payload = {{
                    "ok": True,
                    "evidence_generation_ok": True,
                    "canonical_contract_chain_ok": True,
                    "evidence_runs": [{{"run_id": "owner", "ok": True, "exit_code": 0}}],
                    "child_results": {{"owner": True}},
                    "reports": {{"test_mesh": {{"ok": True, "decision": "pass", "findings": []}}}},
                }}
                (output / "result.json").write_text(json.dumps(payload), encoding="utf-8")
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        root.joinpath("shared.txt").write_text("original", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        entry = ModelRegressionEntry.from_dict(
            {
                "model_id": "sample",
                "model_path": ".flowguard/sample/model.py",
                "runner": ["{python}", ".flowguard/sample/run_checks.py"],
                "tier": "full",
                "timeout_seconds": 30,
                "shard_safe": True,
                "mutation_policy": "isolated_output",
                "input_globs": [
                    ".flowguard/sample/model.py",
                    ".flowguard/sample/run_checks.py",
                ],
                "shard_safety_proof": {
                    "schema_version": CONTRACT_SCHEMA,
                    "proof_id": "proof:sample",
                    "parallel_copies": 2,
                    "output_isolation": "FLOWGUARD_OUTPUT_DIR",
                    "shared_mutation_policy": "zero_repository_mutation",
                    "required_checks": [
                        "serial_parallel_semantic_equivalence",
                        "disjoint_artifact_ownership",
                        "stable_input_inventory",
                        "zero_repository_mutation",
                    ],
                },
            }
        )
        return temporary, root, entry

    def test_serial_parallel_equivalence_and_isolation_pass(self):
        temporary, root, entry = self._repository()
        self.addCleanup(temporary.cleanup)
        receipt = prove_model_shard_safety(root, entry, output_dir=root.parent / f"{root.name}-proof")
        self.assertTrue(receipt["ok"], receipt)
        self.assertTrue(all(receipt["checks"].values()))
        self.assertEqual([], receipt["repository_mutations"])
        self.assertEqual([], receipt["overlapping_artifact_paths"])
        self.assertEqual(3, len(receipt["runs"]))

    def test_shared_repository_mutation_fails_proof(self):
        temporary, root, entry = self._repository(mutate_shared=True)
        self.addCleanup(temporary.cleanup)
        receipt = prove_model_shard_safety(root, entry, output_dir=root.parent / f"{root.name}-proof")
        self.assertFalse(receipt["ok"])
        self.assertFalse(receipt["checks"]["zero_repository_mutation"])
        self.assertEqual(["shared.txt"], receipt["repository_mutations"])

    def test_internal_proof_directory_is_short_and_keeps_identity_in_receipt(self):
        output_root = Path("C:/evidence") / ("readable-release-run-" * 6)
        model_id = "harden_ui_content_visibility_validation"

        proof_dir = _shard_safety_proof_dir(output_root, model_id)

        self.assertEqual("shard-safety", proof_dir.parent.name)
        self.assertRegex(proof_dir.name, r"^p-[0-9a-f]{16}$")
        self.assertNotIn(model_id, proof_dir.as_posix())
        self.assertLessEqual(len(proof_dir.name), 18)


if __name__ == "__main__":
    unittest.main()
