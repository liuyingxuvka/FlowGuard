from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "openspec" / "specs"
AUTHORITY = ROOT / "flowguard" / "consumer-suite-authority.json"
CHECKER_PATH = ROOT / "scripts" / "check_openspec_semantic_sync.py"

RETIRED_PACKAGE_MEMBERS = {
    "model-first-function-flow",
    "flowguard-plan-detailing-compiler",
    "flowguard-agent-workflow-rehearsal",
    "flowguard-development-process-simulator",
}
RETIRED_HELPER_SKILL_IDS = RETIRED_PACKAGE_MEMBERS - {"model-first-function-flow"}

RESTORED_REQUIREMENTS = {
    "development-process-flow": {"Process Evidence Excludes AutoSplit Metrics"},
    "flowguard-api-registry": {"API Registry Reflects Thin Breaking Schema"},
    "flowguard-evidence-field-structure": {
        "Field Schemas Remove Duplicate Input Concepts",
        "Historical Fields Stay In Dedicated Routes",
    },
    "plan-intake-claims": {
        "Plan Intake Uses One Evidence Id Shape",
        "Strict Adapter Fixture Fields Are Test-Owned",
    },
    "risk-evidence-ledger": {
        "Risk Rows Use Compact Gate Lists",
        "Removed Risk Row Fields Are Not Accepted",
    },
    "plan-detailing-compiler": {"Plans bind payload cases to real surfaces"},
    "test-evidence-mesh": {"TestMesh preserves payload execution proof"},
    "flowguard-skill-suite-distribution": {"Consumer prohibition scan"},
    "project-adoption-version-gate": {"Ordinary project zero-write behavior"},
}


def _load_checker():
    name = "test_current_spec_authority_checker"
    spec = importlib.util.spec_from_file_location(name, CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _spec_text(capability: str) -> str:
    return (SPEC_ROOT / capability / "spec.md").read_text(encoding="utf-8")


def _requirement_names(capability: str) -> set[str]:
    return {
        block.name
        for block in CHECKER.parse_main_spec(_spec_text(capability)).blocks
    }


class CurrentSpecAuthorityTests(unittest.TestCase):
    def test_package_authority_owns_exact_fifteen_public_members(self) -> None:
        authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
        members = authority["member_ids"]

        self.assertEqual(15, len(members))
        self.assertEqual(15, len(set(members)))
        self.assertEqual("flowguard", members[0])
        self.assertEqual(1, sum(member == "flowguard" for member in members))
        self.assertTrue(all(member == "flowguard" or member.startswith("flowguard-") for member in members))
        self.assertTrue(RETIRED_PACKAGE_MEMBERS.isdisjoint(members))
        self.assertEqual(
            "projection:consumer-distribution",
            authority["projection_id"],
        )

    def test_package_authority_version_matches_package_version(self) -> None:
        authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
        package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            package["project"]["version"],
            authority["flowguard_version"],
        )

    def test_current_specs_have_no_superseded_count_or_release_literal(self) -> None:
        stale = re.compile(
            r"\bseventeen\b|\bsixteen\b|16/17|17/17|0\.64\.0",
            re.IGNORECASE,
        )
        findings: list[str] = []
        for path in sorted(SPEC_ROOT.glob("*/spec.md")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if stale.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{number}: {line}")

        self.assertEqual([], findings)

    def test_retired_public_helper_ids_have_no_positive_route_authority(self) -> None:
        positive = re.compile(
            r"remains directly invokable|may invoke (?:that|the) skill directly|"
            r"SHALL provide `flowguard-(?:plan-detailing|agent-workflow)|"
            r"installed skills? (?:include|contains?) .*flowguard-(?:plan-detailing|agent-workflow)",
            re.IGNORECASE | re.DOTALL,
        )
        findings: list[str] = []
        for path in sorted(SPEC_ROOT.glob("*/spec.md")):
            content = path.read_text(encoding="utf-8")
            for block in CHECKER.parse_main_spec(content).blocks:
                if any(retired in block.raw for retired in RETIRED_HELPER_SKILL_IDS):
                    if positive.search(block.raw):
                        findings.append(f"{path.parent.name}: {block.name}")
                    self.assertRegex(
                        block.raw,
                        r"retired|MUST NOT|SHALL NOT",
                        f"{path.parent.name}: {block.name}",
                    )
        kernel = _spec_text("flowguard-skill-kernel")
        self.assertNotIn(
            ".agents/skills/model-first-function-flow/SKILL.md",
            kernel,
        )
        model_first_public = re.compile(
            r"`model-first-function-flow`\s+Skill|"
            r"model-first-function-flow\s+skill|"
            r"`model-first-function-flow`\s+remains the (?:correct|canonical) "
            r"(?:entrypoint|Skill Kernel)",
            re.IGNORECASE,
        )
        public_findings = []
        for path in sorted(SPEC_ROOT.glob("*/spec.md")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if model_first_public.search(line):
                    public_findings.append(
                        f"{path.relative_to(ROOT)}:{number}: {line}"
                    )

        self.assertEqual([], findings)
        self.assertEqual([], public_findings)

    def test_restored_requirements_exist_exactly_once(self) -> None:
        for capability, required in RESTORED_REQUIREMENTS.items():
            with self.subTest(capability=capability):
                names = _requirement_names(capability)
                self.assertTrue(required.issubset(names), required - names)
                self.assertEqual(
                    len(names),
                    len(CHECKER.parse_main_spec(_spec_text(capability)).blocks),
                )

    def test_removed_field_shapes_have_no_compatibility_success(self) -> None:
        content = _spec_text("flowguard-evidence-field-structure")
        self.assertNotRegex(content, r"remain compatible|conversion helpers")
        self.assertRegex(content, r"MUST (?:NOT .*convert|be rejected)")
        self.assertIn("rejects it", content)
        self.assertIn("no compatibility\n  success path", content)

    def test_payload_requirements_demand_real_execution_proof(self) -> None:
        plan = _spec_text("plan-detailing-compiler")
        mesh = _spec_text("test-evidence-mesh")
        alignment = _spec_text("model-test-alignment")

        self.assertIn("### Requirement: Plans bind payload cases to real surfaces", plan)
        self.assertRegex(
            plan,
            r"(?is)real payload surface.*synthetic.*alone.*completion evidence",
        )
        self.assertIn("### Requirement: TestMesh preserves payload execution proof", mesh)
        self.assertRegex(
            mesh,
            r"(?is)real-surface execution proof.*does not treat.*synthetic",
        )
        self.assertIn(
            "#### Scenario: Payload evidence lacks real execution proof",
            alignment,
        )
        self.assertRegex(
            alignment,
            r"(?is)producer receipt.*result artifact.*execution-proof\s+blocker",
        )


if __name__ == "__main__":
    unittest.main()
