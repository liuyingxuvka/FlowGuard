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
            compiled = json.loads((skill / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill / ".skillguard" / "check-manifest.json").read_text(encoding="utf-8"))
            with self.subTest(skill=skill_id):
                self.assertEqual(skill_id, source["skill_id"])
                self.assertEqual("skillguard.contract_source.v2", source["schema_version"])
                self.assertEqual(skill_id, compiled["skill_id"])
                self.assertEqual(skill_id, manifest["skill_id"])
                self.assertEqual(3, len(source["step_bindings"]))
                self.assertTrue(source["checks"])
                self.assertTrue(source["closure_profiles"])
                self.assertIn(f"${skill_id}", prompt)
                self.assertIn("route_id=", prompt)
                self.assertIn(f"native_owner={member['owner']}", prompt)
                for field in OUTPUT_FIELDS:
                    self.assertIn(field, prompt)
                self.assertTrue((ROOT / source["model_path"]).is_file())
                for implementation_path in source["implementation_paths"]:
                    self.assertTrue((ROOT / implementation_path).exists(), implementation_path)

    def test_delegated_modes_and_mta_testmesh_handoff_are_not_parallel_owners(self):
        for skill_id in ("flowguard-agent-workflow-rehearsal", "flowguard-plan-detailing-compiler"):
            skill_root = SKILL_ROOT / skill_id
            skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            prompt = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("`delegated_mode`", skill_text)
            self.assertIn("native owner `development_process_flow`", skill_text)
            self.assertIn("role=delegated_mode", prompt)
            self.assertIn("native_owner=development_process_flow", prompt)
        mta_root = SKILL_ROOT / "flowguard-model-test-alignment"
        mta_text = (mta_root / "SKILL.md").read_text(encoding="utf-8")
        mta_prompt = (mta_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertNotIn("Do not invoke TestMesh", mta_text)
        self.assertIn("hands large evidence to TestMesh", mta_text)
        self.assertIn("typed TestMesh handoff", mta_prompt)

    def test_every_declared_native_python_surface_is_in_the_public_git_tree(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git is required to verify public native-command distribution")
        repository_probe = subprocess.run(
            [git, "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if repository_probe.returncode != 0:
            self.skipTest("public git-tree distribution check requires a git checkout")
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
            for check in source["checks"]:
                if check["kind"] != "command" or check.get("command") != "python":
                    continue
                python_paths = tuple(
                    token.replace("\\", "/")
                    for token in check.get("args", ())
                    if token.endswith(".py") and (token.startswith("tests/") or token.startswith(".flowguard/"))
                )
                with self.subTest(skill=skill_id, command=(check["command"], *check.get("args", ()))):
                    self.assertTrue(python_paths)
                    self.assertTrue(set(python_paths) <= tracked, set(python_paths) - tracked)


if __name__ == "__main__":
    unittest.main()
