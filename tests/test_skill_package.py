"""The public skill: one entry, one short protocol per capability, real commands only."""

from __future__ import annotations

import contextlib
import io
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
    "behavior-commitment", "architecture-reduction", "code-structure",
    "contract-exhaustion", "field-lifecycle", "model-mesh",
    "model-test", "topology-hazard", "test-mesh", "ui-flow",
)
SECTIONS = ("## Use when", "## Do not use when", "## Inputs", "## Steps", "## What blocks", "## Done when", "## Limits")


class SkillPackageTests(unittest.TestCase):
    def test_skill_entry_is_short_and_describes_the_tree(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 100)
        self.assertEqual(1, text.splitlines().count("## The tree"))
        for retired in ("## Binding", "L0 ", "L1:", "L2", "keep runners"):
            self.assertNotIn(retired, text)
        for name in CAPABILITIES:
            with self.subTest(protocol=name):
                lines = (SKILL / "references" / "domains" / name / "protocol.md").read_text(encoding="utf-8").splitlines()
                self.assertTrue(any(line.startswith("Tree operation:") for line in lines[:3]))

    def test_model_recipes_have_short_grow_and_split_sections(self) -> None:
        text = (SKILL / "references" / "model_recipes.md").read_text(encoding="utf-8")
        for title in ("Grow a model", "Split a model"):
            heading = "## " + title
            self.assertEqual(1, text.splitlines().count(heading))
            section = text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]
            self.assertLessEqual(len(section.splitlines()), 30)
        self.assertNotIn("names the component that owns the files next to it",
                         (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_installation_docs_use_the_owner_github_only(self) -> None:
        for path in (ROOT / "README.md", ROOT / "README.zh-CN.md", SKILL / "SKILL.md"):
            self.assertIn("git+https://github.com/liuyingxuvka/FlowGuard.git", path.read_text(encoding="utf-8"))
        markdown = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=ROOT).decode("utf-8")
        for relative in filter(None, markdown.split("\0")):
            self.assertIsNone(re.search(r"\bpip\s+install\s+flowguard(?=\s|$)",
                                        (ROOT / relative).read_text(encoding="utf-8"), re.M), relative)

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
        from flowguard.map.target import build_parser as target_parser

        subs = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
        map_cmds, templates = set(subs.choices), set(template_factories())
        target_cmds = set(next(a for a in target_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices)
        verbs = {"read", "change", "release", "map", "template", "target", "--help", "--version"}
        docs = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "AGENTS.md",
                *sorted((ROOT / "docs").glob("*.md")), *sorted(SKILL.rglob("*.md"))]
        problems = []
        for path in docs:
            rel = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for verb, arg in re.findall(r"python -m flowguard ([\w-]+)(?: ([a-z][\w-]*))?", line):
                    if verb not in verbs or (verb == "map" and arg and arg not in map_cmds) \
                            or (verb == "template" and arg and arg not in templates):
                        problems.append(f"{rel}:{number}: python -m flowguard {verb} {arg}".rstrip())
                    if verb == "target" and arg and arg not in target_cmds:
                        problems.append(f"{rel}:{number}: python -m flowguard target {arg}")
                for cmd in re.findall(r"python -m flowguard\.map ([a-z][\w-]*)", line):
                    if cmd not in map_cmds:
                        problems.append(f"{rel}:{number}: python -m flowguard.map {cmd}")
                if re.search(r"python -m flowguard template [\w-]+ --output", line) or "unittest discover" in line:
                    problems.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual([], problems)

    def test_documented_command_arguments_parse(self) -> None:
        import shlex

        from flowguard.__main__ import _verb_parser
        from flowguard.map.cli import build_parser

        docs = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "AGENTS.md",
                *sorted((ROOT / "docs").glob("*.md")), *sorted(SKILL.rglob("*.md"))]
        problems = []
        for path in docs:
            rel = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for match in re.finditer(r"python -m flowguard ([^`\n]*)", line):
                    command = re.sub(r"(?<=\S)[.,;:)]+$", "", match.group(1).split("#", 1)[0].strip())
                    if not command or any(mark in command for mark in ("|", "[", "<", "...")):
                        continue                      # alternatives, optional parts and placeholders
                    words = ["1" if re.fullmatch(r"[A-Z][A-Z0-9_]*", word) else word for word in shlex.split(command)]
                    verb, rest = words[0], words[1:]
                    if verb == "map" and rest:
                        parser = build_parser()
                    elif verb in {"read", "change", "release", "template", "target"}:
                        parser = _verb_parser(verb)
                    else:
                        continue
                    try:
                        with contextlib.redirect_stderr(io.StringIO()):
                            parser.parse_args(rest)
                    except SystemExit:
                        problems.append(f"{rel}:{number}: python -m flowguard {command}")
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
        self.assertEqual(["docs/flowguard_agents_rules.md"], [f.path for f in adoption_template_files()])

    def test_installer_copies_the_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = lambda *extra: subprocess.run([sys.executable, "scripts/install_skill.py", "--target", directory, *extra],
                                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, run().returncode)
            check = run("--check")
            self.assertEqual(0, check.returncode, check.stdout)
            skill = Path(directory) / "flowguard" / "SKILL.md"
            self.assertTrue(skill.is_file())
            original = skill.read_bytes()
            stat = skill.stat()
            skill.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            os.utime(skill, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertEqual(stat.st_size, skill.stat().st_size)
            self.assertEqual(stat.st_mtime_ns, skill.stat().st_mtime_ns)
            changed = run("--check")
            self.assertEqual(1, changed.returncode, changed.stdout)
            self.assertIn("differs: SKILL.md", changed.stdout)
            skill.write_bytes(original)
            os.utime(skill, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            cache = skill.parent / "__pycache__"
            cache.mkdir(exist_ok=True)
            (cache / "ignored.pyc").write_bytes(b"ignored")
            self.assertEqual(0, run("--check").returncode)


if __name__ == "__main__":
    unittest.main()
