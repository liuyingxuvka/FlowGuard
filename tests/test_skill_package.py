"""The public skill: one entry, one model tree, real commands and references."""

from __future__ import annotations

import ast
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


def _parse_documented_command_arguments(command: str) -> None:
    """Use the actual parsers; placeholders are one argument, never a skip."""
    import shlex

    from flowguard.__main__ import _verb_parser
    from flowguard.map.cli import build_parser

    # A generic command slot names no operation; choose one real map verb.
    command = re.sub(r"^map\s+<command>(?=\s|$)", "map check", command)
    command = re.sub(r"<[^>]+>", "1", command)
    words = ["1" if re.fullmatch(r"[A-Z][A-Z0-9_]*", word) else word for word in shlex.split(command)]
    if not words:
        raise ValueError("empty command")
    verb, rest = words[0], words[1:]
    if verb == "map":
        parser = build_parser()
    elif verb in {"read", "change", "release", "template", "target", "req"}:
        parser = _verb_parser(verb)
    else:
        raise ValueError(f"no documented argument parser for {verb!r}")
    with contextlib.redirect_stderr(io.StringIO()):
        parser.parse_args(rest)


class SkillPackageTests(unittest.TestCase):
    def test_skill_entry_describes_the_tree(self) -> None:
        text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
        headings=re.findall(r'^## ([^\n]+)',text,re.M)
        self.assertEqual(['Start from the model','The loop','Routes by task','The tree','First map, review and release','Honesty rules'],headings)
        for required in ('python -m flowguard target start','python -m flowguard target check','python -m flowguard target promote','python -m flowguard change --run','python -m flowguard read --find','DISPATCH'):
            self.assertIn(required,text)
        for retired in ('MESH','closure','consumer_model_id','FunctionContract','hazard','packs','budgeted','child_outside_parent','review children','--expect-gap','IGNORES_PARENT','route (a)','in place','model_tests_elsewhere','upgrade.md','runner_model','DESIGN_ONLY'):
            self.assertNotIn(retired,text)
        labels=('- Node: ','- Parent: ','- Known-bad: ','- Real binding: ','- Test binding: ','- Readback: ','- Current vs target: ')
        shared_lines=[(index,line) for index,line in enumerate(text.splitlines()) if line.startswith(labels)]
        self.assertEqual(7,len(shared_lines))
        self.assertEqual(labels,tuple(next(label for label in labels if line.startswith(label)) for _,line in shared_lines))
        start=shared_lines[0][0]
        self.assertEqual(list(range(start,start+7)),[index for index,_ in shared_lines])

    def test_route_sections_are_listed(self) -> None:
        text=(SKILL/'references/routes.md').read_text(encoding='utf-8')
        sections=re.split(r'(?m)(?=^## )',text)[1:]
        self.assertEqual(11,len(sections))

    def test_installation_docs_use_the_owner_github_only(self) -> None:
        for path in (ROOT / "README.md", ROOT / "README.zh-CN.md", SKILL / "SKILL.md"):
            self.assertIn("git+https://github.com/liuyingxuvka/FlowGuard.git", path.read_text(encoding="utf-8"))
        markdown = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=ROOT).decode("utf-8")
        paths = [ROOT / relative for relative in filter(None, markdown.split("\0"))]
        for path in paths:
            self.assertIsNone(re.search(r"\bpip\s+install\s+flowguard(?=\s|$)",
                                        path.read_text(encoding="utf-8"), re.M), path.relative_to(ROOT).as_posix())



    def test_template_names_in_references_exist(self) -> None:
        listed = subprocess.run([sys.executable, "-m", "flowguard", "template", "--list"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.split()
        docs = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        for path in docs:
            for name in re.findall(r"python -m flowguard template ([a-z][a-z-]+)", path.read_text(encoding="utf-8")):
                with self.subTest(document=path.relative_to(SKILL).as_posix(), template=name):
                    self.assertIn(name, listed)

    def test_documented_commands_exist(self) -> None:
        import argparse

        from flowguard.__main__ import template_factories
        from flowguard.map.cli import build_parser
        from flowguard.map.target import build_parser as target_parser

        subs = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
        map_cmds, templates = set(subs.choices), set(template_factories())
        target_cmds = set(next(a for a in target_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices)
        verbs = {"read", "change", "release", "map", "template", "target", "req", "--help", "--version"}
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
        docs = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "AGENTS.md",
                *sorted((ROOT / "docs").glob("*.md")), *sorted(SKILL.rglob("*.md"))]
        problems = []
        for path in docs:
            rel = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for match in re.finditer(r"python -m flowguard ([^`\n]*)", line):
                    command = re.sub(r"(?<=\S)[.,;:)]+$", "", match.group(1).split("#", 1)[0].strip())
                    if not command or any(mark in command for mark in ("|", "[", "...")):
                        continue                      # illustrative alternatives and optional parts
                    if command.split()[0] not in {"map", "read", "change", "release", "template", "target"}:
                        continue                      # top-level flags have no verb argument parser
                    try:
                        _parse_documented_command_arguments(command)
                    except (SystemExit, ValueError):
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

    def test_adoption_generates_six_project_rules_and_claude_md(self) -> None:
        from flowguard.templates import adoption_template_files
        rules = next(f for f in adoption_template_files() if f.path == "docs/flowguard_agents_rules.md")
        self.assertEqual(6, len(re.findall(r"^\d\. ", rules.content, re.M)))
        self.assertIn("python -m flowguard change", rules.content)
        target_rule = next(line for line in rules.content.splitlines() if line.startswith("2. "))
        for command in ('python -m flowguard target start "<goal>"', 'python -m flowguard target check',
                        'python -m flowguard target promote', 'python -m flowguard read --find WORDS'):
            self.assertIn(command, target_rule)
        self.assertIn('extend it',target_rule)
        after_rule=next(line for line in rules.content.splitlines() if line.startswith('4. '))
        for required in ('port changed','consumes','promises:','grow together'):self.assertIn(required,after_rule)
        self.assertFalse(any(f.path == "AGENTS.md" for f in adoption_template_files()))
        self.assertEqual(["docs/flowguard_agents_rules.md", "CLAUDE.md"], [f.path for f in adoption_template_files()])
        self.assertEqual("@AGENTS.md\n", next(f.content for f in adoption_template_files() if f.path == "CLAUDE.md"))
        from flowguard.__main__ import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(["template", "adoption", "--write", directory]))
            claude = root / "CLAUDE.md"
            self.assertEqual(b"@AGENTS.md\n", claude.read_bytes())
            original = "# Existing instructions\r\n保持原文。\r\n".encode()
            claude.write_bytes(original)
            stamp = claude.stat().st_mtime_ns
            (root / "docs/flowguard_agents_rules.md").write_text("replace this generated file", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(["template", "adoption", "--write", directory, "--force"]))
            self.assertEqual(original, claude.read_bytes())
            self.assertEqual(stamp, claude.stat().st_mtime_ns)
            self.assertEqual(rules.content, (root / "docs/flowguard_agents_rules.md").read_text(encoding="utf-8"))
            self.assertIn("kept CLAUDE.md (it exists): make sure it holds the line @AGENTS.md", output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["template", "adoption"]))
        self.assertIn("===== CLAUDE.md =====\n@AGENTS.md\n", output.getvalue())

    def test_installer_copies_the_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = lambda *extra: subprocess.run([sys.executable, "scripts/install_skill.py", "--target", directory, *extra],
                                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, run().returncode)
            check = run("--check")
            self.assertEqual(0, check.returncode, check.stdout)
            skill = Path(directory) / "flowguard" / "SKILL.md"
            self.assertTrue(skill.is_file())
            self.assertFalse((skill.parent / "assets").exists())
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


    def test_route_texts_have_no_repeats_dead_links_or_missing_names(self) -> None:
        import argparse
        from collections import Counter
        from urllib.parse import unquote, urlsplit
        from flowguard.__main__ import _verb_parser
        from flowguard.map.cli import build_parser as map_parser
        from flowguard.map.target import build_parser as target_parser

        def slug(heading):
            return re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")

        def options(parser):
            found = set()
            for action in parser._actions:
                found.update(action.option_strings)
                if isinstance(action, argparse._SubParsersAction):
                    for child in action.choices.values():
                        found.update(options(child))
            return found

        flags = set().union(*(options(parser) for parser in
            [*(_verb_parser(verb) for verb in ('read', 'change', 'release', 'template')),
             target_parser(), map_parser()]))
        source = "\n".join(path.read_text(encoding='utf-8')
            for directory in (ROOT / 'flowguard', ROOT / '.flowguard/models')
            for path in directory.rglob('*.py'))
        entry_path, routes_path = SKILL / 'SKILL.md', SKILL / 'references/routes.md'
        entry, routes = entry_path.read_text(), routes_path.read_text()
        sections = re.split(r'(?m)(?=^## )', routes)[1:]
        table = entry.split('## Routes by task\n', 1)[1].split('\n## ', 1)[0]
        table_rows = [row for row in table.splitlines() if row.startswith('|')][2:]
        links = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')

        def destination(path, link):
            value = urlsplit(link)
            if value.scheme or value.netloc:
                return None
            target = (path.parent / unquote(value.path)).resolve() if value.path else path
            return target, unquote(value.fragment)

        for section in sections:
            route = section.splitlines()[0][3:]
            files = {entry_path.resolve(), routes_path.resolve()}
            for origin, text in [(routes_path, section),
                    *[(entry_path, row) for row in table_rows
                      if any(fragment == slug(route) for link in links.findall(row)
                             if (resolved := destination(entry_path, link))
                             for target, fragment in [resolved])]]:
                for link in links.findall(text):
                    resolved = destination(origin, link)
                    if resolved and resolved[0].is_file():
                        files.add(resolved[0])
            texts = {path: path.read_text(encoding='utf-8') for path in sorted(files)}
            paragraphs = Counter(' '.join(part.split()) for text in texts.values()
                for part in re.split(r'\n\s*\n', text) if len(part.split()) >= 8)
            for paragraph, count in paragraphs.items():
                self.assertEqual(1, count, f'{route}: repeated paragraph: {paragraph}')
            for path, text in texts.items():
                for link in links.findall(text):
                    resolved = destination(path, link)
                    if resolved is None:
                        continue
                    target, fragment = resolved
                    self.assertTrue(target.is_file(), f'{route}: dead link: {link} in {path}')
                    if fragment:
                        headings = re.findall(r'^#+ (.+)$', target.read_text(), re.M)
                        self.assertIn(fragment, [slug(heading) for heading in headings],
                                      f'{route}: missing anchor: {link}')
                for code in re.findall(r'`([^`\n]+)`', text):
                    for flag in re.findall(r'--[a-z0-9][\w-]*', code):
                        self.assertIn(flag, flags, f'{route}: missing option: {code}')
                    if '_' in code and re.fullmatch(r'[a-z_][a-z0-9_]*', code):
                        self.assertTrue(re.search(r'\b' + re.escape(code) + r'\b', source),
                                         f'{route}: missing name: {code}')
                    if code.startswith('references/'):
                        self.assertTrue((SKILL / code.split('#', 1)[0]).is_file(),
                                        f'{route}: missing reference: {code}')
            print(f'route {route}: {sum(len(text) for text in texts.values())} characters')

    def test_skill_has_one_route_table(self) -> None:
        entry=(SKILL/'SKILL.md').read_text(encoding='utf-8')
        self.assertEqual(1,entry.count('## Routes by task'))
        section=entry.split('## Routes by task\n',1)[1].split('\n## ',1)[0]
        rows=[line for line in section.splitlines() if line.startswith('|')][2:]
        expected=('New function','large_model','large_test_file','port changed','Rename or retire a field','Move or split code','Remove a function','Bug a green model missed','External promise','UI journey','Model before code','model_edited_outside_target')
        self.assertEqual(len(expected),len(rows))
        for title,row in zip(expected,rows):self.assertIn(title,row.split('|')[1])
        self.assertEqual(1,entry.count('Models, tests and code grow together'))

    def test_route_rows_point_to_existing_sections(self) -> None:
        entry=(SKILL/'SKILL.md').read_text(encoding='utf-8')
        section=entry.split('## Routes by task\n',1)[1].split('\n## ',1)[0]
        rows=[line for line in section.splitlines() if line.startswith('|')][2:]
        mapping={0:('routes.md',('New function',)),1:('routes.md',('Split a model',)),2:('routes.md',('Split a test file',)),3:('routes.md',('Interface change',)),4:('routes.md',('Rename or retire a field',)),5:('routes.md',('Add or split a component',)),6:('routes.md',('Remove or merge a node',)),7:('routes.md',('When a green model missed a bug',)),8:('routes.md',('External promise (no silent fallback)',)),9:('node_kinds.md',('UI journey','Validator')),10:('routes.md',('Model before code',))}
        for index,(filename,headings) in mapping.items():
            text=(SKILL/'references'/filename).read_text(encoding='utf-8')
            for heading in headings:self.assertEqual(1,text.splitlines().count('## '+heading),(index,filename,heading))
        literals={node.value for path in (ROOT/'flowguard').rglob('*.py') for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
        for row in rows:
            for code in re.findall(r'`([a-z]+(?:_[a-z]+)*(?:_\*)?)`',row.split('|')[1]):
                if "_" not in code:continue
                with self.subTest(code=code):
                    self.assertTrue(any(value.startswith(code[:-1]) for value in literals) if code.endswith('*') else code in literals)
        for path in SKILL.rglob('*.md'):
            text=path.read_text(encoding='utf-8')
            for retired in ('Add a child** for an independent operation','importers and ancestors are selected too','map impact <file under the failure>'):self.assertNotIn(retired,text,str(path))


if __name__ == "__main__":
    unittest.main()
