from __future__ import annotations

import json
from pathlib import Path
import unittest

from flowguard.skill_contracts import compile_skill_suite


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"


class PortableSkillGuidanceTests(unittest.TestCase):
    def test_kernel_owns_current_portable_projection_without_serializing_python(self):
        skill = (SKILLS / "flowguard" / "SKILL.md").read_text(encoding="utf-8")
        reference = (
            SKILLS / "flowguard" / "references" / "modeling_core_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("flowguard.portable_model.v1", skill)
        self.assertIn("do not serialize arbitrary Python", skill)
        self.assertIn("There is no alternate reader or prose fallback", reference)

    def test_mesh_consumes_explicit_refinement_instead_of_reimplementing_checker(self):
        skill = (SKILLS / "flowguard-model-mesh" / "SKILL.md").read_text(encoding="utf-8")
        reference = (
            SKILLS / "flowguard-model-mesh" / "references" / "model_mesh_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("flowguard.portable_refinement.v1", skill)
        self.assertIn("do not build a second mesh-owned interpreter", reference)

    def test_topology_consumes_same_identity_and_executable_temporal_receipt(self):
        skill = (
            SKILLS / "flowguard-model-topology-hazard-review" / "SKILL.md"
        ).read_text(encoding="utf-8")
        reference = (
            SKILLS
            / "flowguard-model-topology-hazard-review"
            / "references"
            / "topology_hazard_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("same graph", skill)
        self.assertIn("Weak fairness may exclude", reference)
        self.assertIn("canonical checker report", reference)

    def test_contract_sources_track_portable_runtime_as_affected_input(self):
        for skill_id in (
            "flowguard",
            "flowguard-model-mesh",
            "flowguard-model-topology-hazard-review",
        ):
            payload = json.loads(
                (SKILLS / skill_id / ".skillguard" / "contract-source.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("flowguard/portable_model.py", payload["implementation_paths"])
            self.assertIn("flowguard/portable_checker.py", payload["implementation_paths"])

    def test_generated_skill_contracts_are_current(self):
        report = compile_skill_suite(ROOT, write=False)
        self.assertTrue(report.ok, report.to_json_text())


if __name__ == "__main__":
    unittest.main()
