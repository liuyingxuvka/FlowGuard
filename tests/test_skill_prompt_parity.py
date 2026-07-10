import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills"
SUITE_MAP = ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"
EXPECTED_HEADINGS = (
    "## Purpose",
    "## Entrypoint Scope",
    "## Local Material Routing",
    "## Entrypoint Acceptance Map",
    "## Use When",
    "## Do Not Use When",
    "## Required Workflow",
    "## Hard Gates",
    "## Output Requirements",
    "## SkillGuard Maintenance",
)
OUTPUT_FIELDS = (
    "evidence",
    "failures",
    "blockers",
    "skipped_checks",
    "residual_risk",
    "claim_boundary",
    "typed_next_actions",
)


class SkillPromptParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(SUITE_MAP.read_text(encoding="utf-8"))

    def test_all_seventeen_prompts_have_exact_compact_structure(self):
        members = self.suite["included_skills"]
        self.assertEqual(17, len(members))
        for member in members:
            skill_id = member["name"]
            text = (SKILL_ROOT / skill_id / "SKILL.md").read_text(encoding="utf-8")
            headings = tuple(line for line in text.splitlines() if line.startswith("## "))
            with self.subTest(skill=skill_id):
                self.assertEqual(EXPECTED_HEADINGS, headings)
                if member["role"] == "kernel_router":
                    self.assertLessEqual(len(text.splitlines()), 120)
                else:
                    self.assertLessEqual(len(text.splitlines()), 60)
                    self.assertLessEqual(len(text), 3000)

    def test_openai_prompts_and_contract_sources_match_member_identity(self):
        for member in self.suite["included_skills"]:
            skill_id = member["name"]
            skill = SKILL_ROOT / skill_id
            prompt = (skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
            source = json.loads((skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))
            with self.subTest(skill=skill_id):
                self.assertEqual(skill_id, source["skill_id"])
                self.assertEqual(member["owner"], source["native_owner"])
                self.assertEqual(5, len(source["workflow"]))
                self.assertTrue(source["native_checks"])
                self.assertEqual(list(OUTPUT_FIELDS), source["output_fields"])
                self.assertIn(f"${skill_id}", prompt)
                self.assertIn(f"route_id={source['route_id']}", prompt)
                self.assertIn(f"native_owner={source['native_owner']}", prompt)
                for field in OUTPUT_FIELDS:
                    self.assertIn(field, prompt)
                for reference in source["direct_references"]:
                    self.assertTrue((skill / reference).is_file(), reference)

    def test_delegated_modes_and_mta_testmesh_handoff_are_not_parallel_owners(self):
        for skill_id in ("flowguard-agent-workflow-rehearsal", "flowguard-plan-detailing-compiler"):
            source = json.loads(
                (SKILL_ROOT / skill_id / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
            )
            self.assertEqual("delegated_mode", source["route_role"])
            self.assertEqual("development_process_flow", source["native_owner"])
        mta_root = SKILL_ROOT / "flowguard-model-test-alignment"
        mta_text = (mta_root / "SKILL.md").read_text(encoding="utf-8")
        mta_source = json.loads((mta_root / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))
        self.assertNotIn("Do not invoke TestMesh", mta_text)
        self.assertIn(
            "flowguard-test-mesh",
            {item["target_id"] for item in mta_source["downstream_targets"]},
        )

    def test_every_declared_native_python_surface_is_in_the_public_git_tree(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git is required to verify public native-command distribution")
        completed = subprocess.run(
            [git, "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        )
        tracked = {
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in completed.stdout.split(b"\0")
            if item
        }
        for member in self.suite["included_skills"]:
            skill_id = member["name"]
            source = json.loads(
                (SKILL_ROOT / skill_id / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
            )
            for check in source["native_checks"]:
                python_paths = tuple(
                    token.replace("\\", "/")
                    for token in check["command"].split()
                    if token.endswith(".py") and (token.startswith("tests/") or token.startswith(".flowguard/"))
                )
                with self.subTest(skill=skill_id, command=check["command"]):
                    self.assertTrue(python_paths)
                    self.assertTrue(set(python_paths) <= tracked, set(python_paths) - tracked)


if __name__ == "__main__":
    unittest.main()
