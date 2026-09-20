import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from flowguard.prompt_budget import review_prompt_bundles


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills"
SUITE_MAP = ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"
EXPECTED_HEADINGS = (
    "## Fixed public lifecycle",
    "## Model-purpose gate",
    "## Read only what is selected",
    "## Hard boundaries",
    "## Result",
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

    def test_single_public_prompt_has_exact_compact_structure(self):
        members = self.suite["included_skills"]
        self.assertEqual(1, len(members))
        for member in members:
            skill_id = member["name"]
            text = (SKILL_ROOT / skill_id / "SKILL.md").read_text(encoding="utf-8")
            headings = tuple(line for line in text.splitlines() if line.startswith("## "))
            with self.subTest(skill=skill_id):
                self.assertEqual(EXPECTED_HEADINGS, headings)
                self.assertLessEqual(len(text.splitlines()), 80)
                self.assertLessEqual(len(text), 3400)

    def test_openai_prompts_and_contract_sources_match_member_identity(self):
        for member in self.suite["included_skills"]:
            skill_id = member["name"]
            skill = SKILL_ROOT / skill_id
            prompt = (skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
            source = json.loads((skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))
            with self.subTest(skill=skill_id):
                self.assertEqual(skill_id, source["skill_id"])
                self.assertEqual("skillguard.skill_contract.v3", source["schema_version"])
                self.assertEqual(
                    {"route:read", "route:change", "route:release"},
                    {row["route_id"] for row in source["routes"]},
                )
                self.assertIn(f"${skill_id}", prompt)
                self.assertIn("one-or-many protected failures", prompt)
                self.assertIn("Reusable model types are not permanently single-purpose", prompt)
                self.assertIn("Only declared checks may support completion claims", prompt)
                self.assertNotIn("SkillGuard", prompt)
                skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
                references = re.findall(r"`(references/[^`]+)`", skill_text)
                self.assertTrue(references)
                for reference in references:
                    if "<subject>" not in reference:
                        self.assertTrue((skill / reference).is_file(), reference)

    def test_public_skill_has_one_mandatory_instance_purpose_gate(self):
        for member in self.suite["included_skills"]:
            text = (SKILL_ROOT / member["name"] / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=member["name"]):
                self.assertEqual(1, text.count("Model-purpose gate"))
                self.assertIn("task-specific failure(s)", text)
                self.assertIn("native good/bad-per-failure/oracle/current evidence", text)
                self.assertIn("Reusable model types are not permanently single-purpose", text)
                self.assertIn("No mode/fallback", text)
                self.assertIn("Only FlowGuard-declared checks may support completion claims", text)
                self.assertNotIn("SkillGuard", text)
                self.assertNotIn(".skillguard", text)

    def test_internal_modes_and_mta_testmesh_handoff_are_not_parallel_owners(self):
        source = json.loads(
            (SKILL_ROOT / "flowguard" / ".skillguard" / "contract-source.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("skillguard.skill_contract.v3", source["schema_version"])
        self.assertEqual(
            {"route:read", "route:change", "route:release"},
            {row["route_id"] for row in source["routes"]},
        )
        self.assertEqual(
            [],
            [
                path.name
                for path in SKILL_ROOT.iterdir()
                if path.name.startswith("flowguard-")
                and (path / "SKILL.md").is_file()
            ],
        )

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
            self.assertTrue(source["checks"])
            for check in source["checks"]:
                with self.subTest(skill=skill_id, check_id=check["check_id"]):
                    self.assertIn(check["kind"], {"command", "model_assertion"})
                    if check["kind"] == "command":
                        self.assertIsInstance(check["command"], str)

    def test_prompt_bundles_report_enforced_stage_budgets(self):
        report = review_prompt_bundles(ROOT)
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["bundle_count"])
        for bundle in report["bundles"]:
            stages = {stage["stage"]: stage for stage in bundle["stages"]}
            with self.subTest(route=bundle["route_id"]):
                self.assertIn("catalog", stages)
                self.assertIn("preselection", stages)
                self.assertTrue(all(stage["enforced"] for stage in stages.values()))
                self.assertTrue(all(stage["ok"] for stage in stages.values()))
                persistent = bundle["persistent_context"]
                self.assertEqual("persistent_context", persistent["stage"])
                self.assertTrue(persistent["enforced"])
                self.assertTrue(persistent["ok"])
                self.assertGreaterEqual(persistent["headroom_ratio"], 0.10)


if __name__ == "__main__":
    unittest.main()
