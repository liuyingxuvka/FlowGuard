from __future__ import annotations

import json
from pathlib import Path
import unittest

from flowguard.skill_contracts import compile_skill_suite


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"
KERNEL = SKILLS / "flowguard"
DOMAINS = KERNEL / "references" / "domains"


class PortableSkillGuidanceTests(unittest.TestCase):
    def test_kernel_owns_current_portable_projection_without_serializing_python(self):
        skill = (KERNEL / "SKILL.md").read_text(encoding="utf-8")
        reference = (
            KERNEL / "references" / "modeling_core_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("references/route_index.md", skill)
        self.assertIn("references/domains/<subject>/", skill)
        self.assertIn("flowguard.portable_model.v1", reference)
        self.assertIn("never attempt to serialize an", reference)
        self.assertIn("arbitrary callable", reference)
        self.assertIn("There is no alternate reader or prose fallback", reference)

    def test_mesh_consumes_explicit_refinement_instead_of_reimplementing_checker(self):
        skill = (DOMAINS / "model-mesh" / "protocol.md").read_text(encoding="utf-8")
        reference = (
            DOMAINS / "model-mesh" / "references" / "model_mesh_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("flowguard.portable_refinement.v1", skill)
        self.assertIn("do not build a second mesh-owned interpreter", reference)

    def test_topology_consumes_same_identity_and_executable_temporal_receipt(self):
        skill = (
            DOMAINS / "model-topology-hazard-review" / "protocol.md"
        ).read_text(encoding="utf-8")
        reference = (
            DOMAINS
            / "model-topology-hazard-review"
            / "references"
            / "topology_hazard_protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("canonical checker report for the exact model fingerprint", reference)
        self.assertIn("Weak fairness may exclude", reference)
        self.assertIn("canonical checker report", reference)

    def test_contract_sources_track_portable_runtime_as_affected_input(self):
        contract_paths = {"flowguard": KERNEL / ".skillguard" / "contract-source.json"}
        for skill_id, contract_path in contract_paths.items():
            payload = json.loads(
                contract_path.read_text(encoding="utf-8")
            )
            if skill_id == "flowguard":
                self.assertEqual(["flowguard"], payload["member_skill_ids"])
                self.assertIn(
                    "references/domains/model-mesh/protocol.md",
                    payload["consumer_projection"]["file_paths"],
                )

    def test_generated_skill_contracts_are_current(self):
        report = compile_skill_suite(ROOT, write=False)
        self.assertTrue(report.ok, report.to_json_text())


if __name__ == "__main__":
    unittest.main()
