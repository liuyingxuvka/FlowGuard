import json
import re
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
                    self.assertLessEqual(len(text), 3400)

    def test_openai_prompts_and_contract_sources_match_member_identity(self):
        for member in self.suite["included_skills"]:
            skill_id = member["name"]
            skill = SKILL_ROOT / skill_id
            prompt = (skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
            source = json.loads((skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))
            with self.subTest(skill=skill_id):
                self.assertEqual(skill_id, source["skill_id"])
                self.assertEqual(member["owner"], source["native_route_owner"])
                self.assertEqual(3, len(source["step_bindings"]))
                self.assertTrue(source["native_check_bindings"])
                self.assertIn(f"${skill_id}", prompt)
                route_label = source["default_route_id"].removeprefix("route:")
                self.assertIn(f"route_id={route_label}", prompt)
                self.assertIn(f"native_owner={source['native_route_owner']}", prompt)
                for field in OUTPUT_FIELDS:
                    self.assertIn(field, prompt)
                self.assertIn("one-or-many protected failures", prompt)
                self.assertIn("reusable model types are not permanently single-purpose", prompt)
                self.assertIn("only declared checks may support completion claims", prompt)
                self.assertNotIn("SkillGuard", prompt)
                skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
                references = re.findall(r"`(references/[^`]+)`", skill_text)
                self.assertTrue(references)
                for reference in references:
                    self.assertTrue((skill / reference).is_file(), reference)

    def test_all_seventeen_skills_have_one_mandatory_instance_purpose_gate(self):
        for member in self.suite["included_skills"]:
            text = (SKILL_ROOT / member["name"] / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=member["name"]):
                self.assertEqual(1, text.count("Model-purpose gate"))
                self.assertIn("task-specific failure(s)", text)
                self.assertIn("native good/bad-per-failure/oracle/current evidence", text)
                self.assertIn("Reusable types are not fixed-purpose", text)
                self.assertIn("no mode/fallback", text)
                self.assertIn("only FlowGuard-declared checks may support completion claims", text)
                self.assertNotIn("SkillGuard", text)
                self.assertNotIn(".skillguard", text)

    def test_delegated_modes_and_mta_testmesh_handoff_are_not_parallel_owners(self):
        for skill_id in ("flowguard-agent-workflow-rehearsal", "flowguard-plan-detailing-compiler"):
            source = json.loads(
                (SKILL_ROOT / skill_id / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
            )
            self.assertEqual("development_process_flow", source["native_route_owner"])
            self.assertIn(
                source["default_route_id"],
                {"route:agent_workflow_rehearsal", "route:plan_detailing_compiler"},
            )
        mta_root = SKILL_ROOT / "flowguard-model-test-alignment"
        mta_text = (mta_root / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("Do not invoke TestMesh", mta_text)
        self.assertIn("hands large evidence to TestMesh", mta_text)
        testmesh_source = json.loads(
            (SKILL_ROOT / "flowguard-test-mesh" / ".skillguard" / "contract-source.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("test_mesh_maintenance", testmesh_source["native_route_owner"])

    def test_every_declared_native_python_surface_is_in_the_public_worktree(self):
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
        pending = subprocess.run(
            [git, "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        review_visible = tracked | {
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in pending.stdout.split(b"\0")
            if item
        }
        for member in self.suite["included_skills"]:
            skill_id = member["name"]
            source = json.loads(
                (SKILL_ROOT / skill_id / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
            )
            checks_by_id = {check["check_id"]: check for check in source["checks"]}
            for binding in source["native_check_bindings"]:
                check = checks_by_id[binding["check_id"]]
                self.assertEqual("command", check["kind"])
                python_paths = tuple(
                    token.replace("\\", "/")
                    for token in (str(check["command"]), *(str(value) for value in check.get("args", ())))
                    if token.endswith(".py") and (token.startswith("tests/") or token.startswith(".flowguard/"))
                )
                with self.subTest(skill=skill_id, check_id=check["check_id"]):
                    self.assertTrue(python_paths)
                    self.assertTrue(
                        set(python_paths) <= review_visible,
                        set(python_paths) - review_visible,
                    )


if __name__ == "__main__":
    unittest.main()
