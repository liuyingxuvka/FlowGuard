import json
import re
import shlex
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "validation_and_distribution.md"
CONCEPT = ROOT / "docs" / "concept.md"
SUITE_MAP = ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"

TABLE_MARKERS = {
    "english": ("<!-- FLOWGUARD SKILL TABLE EN START -->", "<!-- FLOWGUARD SKILL TABLE EN END -->"),
    "chinese": ("<!-- FLOWGUARD SKILL TABLE ZH START -->", "<!-- FLOWGUARD SKILL TABLE ZH END -->"),
}

DOCUMENTED_SCRIPTS = {
    "scripts/run_flowguard_model_regressions.py",
    "scripts/install_flowguard_skills.py",
    "scripts/check_flowguard_skill_suite.py",
    "scripts/verify_flowguard_release.py",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _table_skill_ids(text: str, start: str, end: str) -> tuple[str, ...]:
    block = text.split(start, 1)[1].split(end, 1)[0]
    return tuple(re.findall(r"^\| `([^`]+)` \|", block, flags=re.MULTILINE))


def _documented_commands() -> tuple[tuple[Path, str, tuple[str, ...]], ...]:
    commands = []
    for path in (README, GUIDE):
        for line in _read(path).splitlines():
            stripped = line.strip()
            if not stripped.startswith("python scripts/"):
                continue
            tokens = tuple(shlex.split(stripped, posix=True))
            if len(tokens) >= 2 and tokens[1] in DOCUMENTED_SCRIPTS:
                commands.append((path, stripped, tokens))
    return tuple(commands)


class DocumentationCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = _read(README)
        cls.guide = _read(GUIDE)
        cls.concept = _read(CONCEPT)
        cls.suite = json.loads(_read(SUITE_MAP))

    def test_english_and_chinese_tables_match_canonical_seventeen_member_inventory(self):
        canonical = tuple(item["name"] for item in self.suite["included_skills"])
        self.assertEqual(17, len(canonical))
        self.assertEqual(len(canonical), len(set(canonical)))

        for language, (start, end) in TABLE_MARKERS.items():
            with self.subTest(language=language):
                documented = _table_skill_ids(self.readme, start, end)
                self.assertEqual(17, len(documented))
                self.assertEqual(set(canonical), set(documented))
                self.assertEqual(len(documented), len(set(documented)))
                self.assertIn("flowguard-behavior-commitment-ledger", documented)

        self.assertIn("Behavior Commitment Ledger", self.readme)

    def test_product_positioning_and_three_layers_are_bilingual(self):
        exact_positioning = "AI-agent skill suite powered by an executable check engine"
        self.assertIn(exact_positioning, self.readme)
        self.assertIn(exact_positioning, self.concept)
        self.assertIn("由可执行检查引擎驱动的 AI-agent 技能套件", self.readme)

        for phrase in (
            "Prompt and contract structure",
            "Native evidence receipt",
            "Self-governance parent closure",
            "提示词与合同结构",
            "原生证据回执",
            "自治理父闭环",
        ):
            self.assertIn(phrase, self.guide)

    def test_readme_version_matches_package_metadata_without_hardcoding_release(self):
        metadata = tomllib.loads(_read(ROOT / "pyproject.toml"))
        package_version = metadata["project"]["version"]
        match = re.search(r"^\| `v([^`]+)` \| `1\.0` \|", self.readme, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(package_version, match.group(1))

    def test_release_verification_commands_are_documented_bilingually(self):
        command = "python scripts/verify_flowguard_release.py --root . --phase local --json"
        self.assertIn("## Release Closure", self.guide)
        self.assertIn("### 发布闭环", self.guide)
        self.assertGreaterEqual(self.guide.count(command), 2)
        self.assertIn("--phase published", self.guide)

    def test_documented_script_options_exist_on_the_real_cli(self):
        commands = _documented_commands()
        self.assertGreaterEqual(len(commands), 20)
        help_options = {}

        for script in DOCUMENTED_SCRIPTS:
            completed = subprocess.run(
                [sys.executable, str(ROOT / script), "--help"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            help_options[script] = set(re.findall(r"--[a-z][a-z0-9-]*", completed.stdout))

        for path, line, tokens in commands:
            script = tokens[1]
            with self.subTest(path=path.name, command=line):
                documented_options = {token for token in tokens[2:] if token.startswith("--")}
                self.assertLessEqual(documented_options, help_options[script])

                if script == "scripts/run_flowguard_model_regressions.py" and "--tier" in tokens:
                    tier = tokens[tokens.index("--tier") + 1]
                    self.assertIn(tier, {"fast", "focused", "full"})
                if script == "scripts/install_flowguard_skills.py":
                    action = tokens[2]
                    self.assertIn(action, {"install", "check", "parity", "uninstall"})
                    if action in {"check", "parity"}:
                        self.assertNotIn("--dry-run", tokens)

    def test_validation_examples_cover_tiers_outputs_progress_install_and_claim_boundaries(self):
        combined = f"{self.readme}\n{self.guide}"
        for phrase in (
            "--tier fast",
            "--tier focused",
            "--tier full",
            "--json",
            "--full",
            "START",
            "DONE",
            "report.json",
            "install --source .",
            "check --source .",
            "parity --source .",
            "uninstall --codex-home",
            "--dry-run",
            ".flowguard/evidence/skill-suite",
            ".flowguard/evidence/model-regressions/",
            "claim boundary",
        ):
            self.assertIn(phrase, combined)

        self.assertIn("Progress proves liveness only", self.guide)
        self.assertIn("Distribution pass", self.guide)
        self.assertIn("does not prove", self.guide)


if __name__ == "__main__":
    unittest.main()
