"""The public skill: one entry, one short protocol per capability, real commands only."""

from __future__ import annotations

import re
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "flowguard"
CAPABILITIES = (
    "existing-model", "behavior-commitment", "architecture-reduction", "code-structure",
    "contract-exhaustion", "development-process", "field-lifecycle", "model-mesh", "model-miss",
    "model-test", "topology-hazard", "structure-mesh", "test-mesh", "ui-flow",
)
SECTIONS = ("## Use when", "## Do not use when", "## Inputs", "## Steps", "## What blocks", "## Done when", "## Limits")


class SkillPackageTests(unittest.TestCase):
    def test_entry_lists_every_capability_once(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in CAPABILITIES:
            self.assertEqual(1, len(re.findall(rf"^\| {re.escape(name)} \|", text, re.M)), name)

    def test_every_capability_has_a_short_complete_protocol(self) -> None:
        for name in CAPABILITIES:
            path = SKILL / "references" / "domains" / name / "protocol.md"
            with self.subTest(name=name):
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(text.splitlines()), 130)
                for section in SECTIONS:
                    self.assertIn(section, text)

    def test_template_names_in_protocols_exist(self) -> None:
        listed = subprocess.run([sys.executable, "-m", "flowguard", "template", "--list"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.split()
        for path in (SKILL / "references" / "domains").glob("*/protocol.md"):
            for name in re.findall(r"python -m flowguard template ([a-z][a-z-]+)", path.read_text(encoding="utf-8")):
                with self.subTest(protocol=path.parent.name, template=name):
                    self.assertIn(name, listed)

    def test_documented_commands_exist(self) -> None:
        import argparse

        from flowguard.__main__ import template_factories
        from flowguard.map.cli import build_parser

        subs = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
        map_cmds, templates = set(subs.choices), set(template_factories())
        verbs = {"read", "change", "release", "map", "template", "--help", "--version"}
        docs = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "AGENTS.md",
                *sorted((ROOT / "docs").glob("*.md")), *sorted(SKILL.rglob("*.md"))]
        problems = []
        for path in docs:
            rel = path.relative_to(ROOT).as_posix()
            if rel == "docs/flowguard_self_review.md":      # historical record, labelled as such
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for verb, arg in re.findall(r"python -m flowguard ([\w-]+)(?: ([a-z][\w-]*))?", line):
                    if verb not in verbs or (verb == "map" and arg and arg not in map_cmds) \
                            or (verb == "template" and arg and arg not in templates):
                        problems.append(f"{rel}:{number}: python -m flowguard {verb} {arg}".rstrip())
                for cmd in re.findall(r"python -m flowguard\.map ([a-z][\w-]*)", line):
                    if cmd not in map_cmds:
                        problems.append(f"{rel}:{number}: python -m flowguard.map {cmd}")
                if re.search(r"python -m flowguard template [\w-]+ --output", line) or "unittest discover" in line:
                    problems.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual([], problems)

    def test_installer_expands_literal_environment_variable_and_rejects_unset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, FLOWGUARD_SKILL_TEST_TARGET=directory)
            command = [sys.executable, "scripts/install_skill.py", "--target",
                       "$FLOWGUARD_SKILL_TEST_TARGET/skills", "--dry-run"]
            good = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(0, good.returncode, good.stderr)
            self.assertIn(str(Path(directory) / "skills" / "flowguard"), good.stdout)
            env.pop("FLOWGUARD_SKILL_TEST_TARGET")
            bad = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(0, bad.returncode)
            self.assertIn("environment variable is unset", bad.stderr)

    def test_adoption_generates_six_project_rules_without_editing_agent_instructions(self) -> None:
        from flowguard.templates import adoption_template_files
        rules = next(f for f in adoption_template_files() if f.path == "docs/flowguard_agents_rules.md")
        self.assertEqual(6, len(re.findall(r"^\d\. ", rules.content, re.M)))
        self.assertIn("python -m flowguard change", rules.content)
        self.assertFalse(any(f.path in ("AGENTS.md", "CLAUDE.md") for f in adoption_template_files()))

    def test_installer_copies_the_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = lambda *extra: subprocess.run([sys.executable, "scripts/install_skill.py", "--target", directory, *extra],
                                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, run().returncode)
            check = run("--check")
            self.assertEqual(0, check.returncode, check.stdout)
            self.assertTrue((Path(directory) / "flowguard" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
