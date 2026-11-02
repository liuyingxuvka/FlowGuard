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
    elif verb in {"read", "change", "release", "template", "target", "req", "status"}:
        parser = _verb_parser(verb)
    else:
        raise ValueError(f"no documented argument parser for {verb!r}")
    with contextlib.redirect_stderr(io.StringIO()):
        parser.parse_args(rest)


class SkillPackageTests(unittest.TestCase):
    def test_template_rules_skill_and_prompt_teach_the_same_plain_flow(self) -> None:
        from flowguard.templates import adoption_template_files
        rules = next(file.content for file in adoption_template_files() if file.path == 'AGENTS.md')
        numbered = re.findall(r'^\d\. .+$', rules, re.M)
        self.assertEqual(4, len(numbered))
        first = ('1. At the start of a session and after any loss of context, '
                 'run `python -m flowguard status` before anything else.')
        self.assertEqual(first, numbered[0])
        own_first = re.search(r'^1\. .+$', (ROOT / 'AGENTS.md').read_text(), re.M)
        self.assertEqual(first, own_first.group())
        skill = (SKILL / 'SKILL.md').read_text()
        prompt = (SKILL / 'agents/openai.yaml').read_text().split('default_prompt:', 1)[1]
        self.assertLess(prompt.index('python -m flowguard status'), prompt.index('python -m flowguard where'))
        self.assertIn('after any loss of context', prompt)
        self.assertIn('python -m flowguard status', skill.split('## The owner', 1)[0])
        for text in (numbered[1], skill, prompt):
            for word in ('req add <file|-> --id <id>', 'own words'):
                self.assertIn(word, text)
        for text in (numbered[3], skill, prompt):
            for word in ('your own words', 'Request: R<n>'):
                self.assertIn(word, ' '.join(text.split()))

    def test_request_and_status_documented_arguments_use_actual_parsers(self) -> None:
        for command in ('req add <file|-> --id <id>', 'req add - --kind glossary --id Words',
                        'req add <file|-> --id <id> --supersedes <old id>', 'req retire ID --not-owner --note TEXT',
                        'status', 'status --root <root> --json --hook --wait 0'):
            _parse_documented_command_arguments(command)
        for command in ('req add --id R7', 'req retire ID', 'status --not-an-option'):
            with self.assertRaises(SystemExit):
                _parse_documented_command_arguments(command)

    def test_skill_entry_teaches_only_the_plain_flow(self) -> None:
        text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
        headings=re.findall(r'^## ([^\n]+)',text,re.M)
        self.assertEqual(['Start',"The owner's words",'Find code','Change, test, commit','Honesty'],headings)
        for required in ('python -m flowguard status','python -m flowguard req add','python -m flowguard where','python -m pytest -q'):
            self.assertIn(required,text)
        taught = set(re.findall(r'python -m flowguard ([a-z]+)', text))
        self.assertEqual({'status','req','where'}, taught)
        for retired in ('target start','target add','target check','target promote','map confirm','change --run','read --find','PLAN.txt','owner block','commit -F','NEXT'):
            self.assertNotIn(retired,text)

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
        verbs = {"read", "change", "release", "map", "template", "target", "req", "status", "where", "--help", "--version"}
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
                    illustration = command.replace('<file|->', 'FILE')
                    if not command or any(mark in illustration for mark in ("|", "[", "...")):
                        continue                      # illustrative alternatives and optional parts
                    if command.split()[0] not in {"map", "read", "change", "release", "template", "target", "req", "status"}:
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

    def test_adoption_writes_the_rules_into_agents_md_or_prints_them_and_never_a_dangling_include(self) -> None:
        from flowguard.__main__ import main
        from flowguard.templates import adoption_template_files
        self.assertEqual(["AGENTS.md", "CLAUDE.md"], [f.path for f in adoption_template_files()])
        rules = next(f.content for f in adoption_template_files() if f.path == "AGENTS.md")
        self.assertEqual(4, len(re.findall(r"^\d\. ", rules, re.M)))
        self.assertEqual({"status", "req", "where"}, set(re.findall(r"python -m flowguard ([a-z]+)", rules)))
        self.assertNotIn("Copy these", rules)
        commit_rule = next(line for line in rules.splitlines() if line.startswith("4. "))
        for required in ("one commit", "your own words", "Request: R<n>"):
            self.assertIn(required, commit_rule)

        def adopt(root, *extra):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(["template", "adoption", "--write", str(root), *extra]))
            return output.getvalue()

        with tempfile.TemporaryDirectory() as directory:
            fresh, owned, both, odd = (Path(directory) / name for name in ("fresh", "owned", "both", "odd"))
            fresh.mkdir()
            adopt(fresh)  # no AGENTS.md: the rules become AGENTS.md, and CLAUDE.md includes it
            self.assertEqual(rules, (fresh / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual(b"@AGENTS.md\n", (fresh / "CLAUDE.md").read_bytes())
            self.assertFalse((fresh / "docs").exists())

            owned.mkdir()  # the owner's AGENTS.md is never changed, even with --force; the block is printed
            original = "# Existing instructions\r\n保持原文。\r\n".encode()
            (owned / "AGENTS.md").write_bytes(original)
            stamp = (owned / "AGENTS.md").stat().st_mtime_ns
            output = adopt(owned, "--force")
            self.assertEqual(original, (owned / "AGENTS.md").read_bytes())
            self.assertEqual(stamp, (owned / "AGENTS.md").stat().st_mtime_ns)
            self.assertIn(f"kept AGENTS.md (it exists): FlowGuard does not edit it\nadd these lines to "
                          f"{owned / 'AGENTS.md'}, replacing any earlier FlowGuard rules there:\n{rules}", output)
            self.assertEqual(b"@AGENTS.md\n", (owned / "CLAUDE.md").read_bytes())
            self.assertNotIn("wrote " + str(owned / "AGENTS.md"), output)

            both.mkdir()  # no AGENTS.md but an owner CLAUDE.md: write AGENTS.md, keep CLAUDE.md as it is
            (both / "CLAUDE.md").write_bytes(original)
            output = adopt(both, "--force")
            self.assertEqual(rules, (both / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual(original, (both / "CLAUDE.md").read_bytes())
            self.assertIn("kept CLAUDE.md (it exists): make sure it holds the line @AGENTS.md", output)

            (odd / "AGENTS.md").mkdir(parents=True)  # no file to include: no CLAUDE.md, and it says why
            output = adopt(odd)
            self.assertFalse((odd / "CLAUDE.md").exists())
            self.assertIn(f"{odd / 'AGENTS.md'} is not a file", output)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["template", "adoption"]))
        self.assertIn("===== AGENTS.md =====\n" + rules, output.getvalue())
        self.assertIn("===== CLAUDE.md =====\n@AGENTS.md\n", output.getvalue())

    def test_adoption_names_earlier_flowguard_rules_and_never_asks_to_add_rules_already_there(self) -> None:
        """An existing AGENTS.md: earlier FlowGuard rules are named by line to be replaced, rules already there are
        never asked for again, and a file that holds the current rules is reported as complete and left alone."""
        from unittest import mock
        from flowguard.__main__ import main
        from flowguard.templates import adoption_template_files
        rules = next(f.content for f in adoption_template_files() if f.path == "AGENTS.md")
        project = ["## Core Repository Rules", "", "- Use SI internally; never convert silently.",
                   "- CI runs `python -m flowguard map check` on every push.",  # the project's own rule: kept
                   "- Real modules require an explicit request.", ""]
        older = [  # the FlowGuard block of an older release, verbatim from a Guard repository's AGENTS.md
            "<!-- BEGIN FLOWGUARD PROJECT RULES -->",
            "",
            "## FlowGuard map and model maintenance",
            "",
            "1. At the start of a session and after any loss of context, run `python -m flowguard status` before "
                "anything else.",
            "2. Before changing behaviour or structure: store only the owner's request once as received with "
                "`python -m flowguard req add <file|-> --id <id>` (reuse its ID if already stored) and never edit the"
                " stored copy, locate the owner model with `python -m flowguard read --find WORDS` (or a "
                "path:function) and extend it (a separate aspect gets its own model), run `python -m flowguard target"
                ' start "<goal>" --request <id>` and `python -m flowguard target add <model>`, edit the copy in '
                ".flowguard/target/, in .flowguard/target/PLAN.txt, name changed rules that show NO GAP and functions"
                ' the change must reach (`changes: <model>.<rule> by <id> "<quote>"` with a verbatim quote or '
                '`changes: <model>.<rule> because "<reason>"`, and `touch: <path>:<qualified name>`), run `python -m '
                "flowguard target check` until it shows no ERROR and each changed model shows EXPECTED GAP, `moved "
                "rules only`, `no rule change` or NO GAP with a line for every changed rule that shows NO GAP, change"
                " the code, then run `python -m flowguard target promote` and the map confirm it prints, and paste "
                "its owner block, when printed, unchanged into your final message.",
            "3. Open only the affected component's files (`python -m flowguard read --component ID`).",
            "4. After editing, run `python -m flowguard change` and fix errors; for `port changed ... -> verify "
                "X`, run `python -m flowguard target add X` and make X receive the value; open each place a "
                "`consumes`, `produces`, `mentions` or `nothing produces` line names; restore what a `promises: -...`"
                " line lists or give the reason in the commit message; then run the affected tests and models it "
                "selects. Models, tests and code grow together: split a model or a test file that grows too big (map "
                "check warns at the soft limit and refuses at the hard one), keep them in correspondence where it "
                "makes functional sense, and give a reason where a model has no test or no code yet.",
            "5. Re-read each REVIEW component, update its description if behavior changed, then `python -m "
                "flowguard map confirm ID`.",
            "6. At final release, freeze the source and run the full suite and `python -m flowguard release` once"
                " on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.",
            "",
            "Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install "
                'with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different '
                "project).",
            "Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release"
                " alone is no reason to change it or to release this repository.",
            "",
            "<!-- END FLOWGUARD PROJECT RULES -->",
            "", "- Keep adapters future work unless explicitly requested."]

        def adopt(root):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(["template", "adoption", "--write", str(root)]))
            return output.getvalue()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / "AGENTS.md"
            original = "\r\n".join(project + older).encode() + b"\r\n"
            agents.write_bytes(original)
            output = adopt(root)
            self.assertEqual(original, agents.read_bytes())
            self.assertNotIn("to the end", output)
            named = re.findall(r"^  line (\d+): (.*)$", output, re.M)
            self.assertEqual([9, 11, 12, 13, 14, 15, 16], [int(number) for number, _ in named], output)
            self.assertEqual("## FlowGuard map and model maintenance", named[0][1])
            self.assertTrue(named[2][1].startswith("2. Before changing behaviour") and named[2][1].endswith("..."))
            self.assertLessEqual(max(len(text) for _, text in named), 100)
            self.assertIn("kept AGENTS.md (it exists): FlowGuard does not edit it; these lines of it look like "
                          f"earlier FlowGuard rules:\n  line 9: ", output)
            self.assertTrue(output.endswith(f"add these lines to {agents}, replacing any earlier FlowGuard rules "
                                            f"there:\n{rules}"), output)

            # The owner replaces the named lines with the printed rules: the next run changes and prints nothing.
            lines = project + older
            first = int(named[0][0]) - 1
            kept = [line for number, line in enumerate(lines, 1) if number not in {int(n) for n, _ in named}]
            replaced = "\n".join(kept[:first] + rules.splitlines() + kept[first:]) + "\n"
            agents.write_text(replaced, encoding="utf-8")
            stamp = agents.stat().st_mtime_ns
            output = adopt(root)
            self.assertEqual((replaced, stamp), (agents.read_text(encoding="utf-8"), agents.stat().st_mtime_ns))
            self.assertIn(f"kept AGENTS.md: {agents} already holds the current FlowGuard rules; nothing to add", output)
            self.assertNotIn(rules.splitlines()[2], output)
            self.assertNotIn("add these lines", output)

            # Only one current rule is there (rule 1 is unchanged since the older set): it is named, never added twice.
            agents.write_text("\n".join(project + [older[4]]) + "\n", encoding="utf-8")
            output = adopt(root)
            self.assertEqual([("7", older[4][:97] + "...")], re.findall(r"^  line (\d+): (.*)$", output, re.M))
            self.assertIn("replacing any earlier FlowGuard rules there", output)

            real = Path.read_text  # an AGENTS.md that cannot be read: say so and print the rules
            def refuse(path, *arguments, **keywords):
                if path.name == "AGENTS.md":
                    raise PermissionError(13, "Permission denied", str(path))
                return real(path, *arguments, **keywords)
            with mock.patch.object(Path, "read_text", autospec=True, side_effect=refuse):
                output = adopt(root)
            self.assertIn(f"cannot read {agents}: [Errno 13] Permission denied", output)
            self.assertIn(f"replacing any earlier FlowGuard rules there:\n{rules}", output)

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
            [*(_verb_parser(verb) for verb in ('read', 'change', 'release', 'template', 'req', 'status', 'where')),
             target_parser(), map_parser()]))
        source = "\n".join(path.read_text(encoding='utf-8')
            for directory in (ROOT / 'flowguard', ROOT / '.flowguard/models')
            for path in directory.rglob('*.py'))
        routes_path = SKILL / 'references/routes.md'
        routes = routes_path.read_text()
        sections = re.split(r'(?m)(?=^## )', routes)[1:]
        links = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')

        def destination(path, link):
            value = urlsplit(link)
            if value.scheme or value.netloc:
                return None
            target = (path.parent / unquote(value.path)).resolve() if value.path else path
            return target, unquote(value.fragment)

        for section in sections:
            route = section.splitlines()[0][3:]
            files = {routes_path.resolve()}
            for origin, text in [(routes_path, section)]:
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

    def test_route_sections_named_by_findings_exist(self) -> None:
        mapping={0:('routes.md',('New function',)),1:('routes.md',('Split a model',)),2:('routes.md',('Split a test file',)),3:('routes.md',('Interface change',)),4:('routes.md',('Rename or retire a field',)),5:('routes.md',('Add or split a component',)),6:('routes.md',('Remove or merge a node',)),7:('routes.md',('When a green model missed a bug',)),8:('routes.md',('External promise (no silent fallback)',)),9:('node_kinds.md',('UI journey','Validator')),10:('routes.md',('Model before code',))}
        for index,(filename,headings) in mapping.items():
            text=(SKILL/'references'/filename).read_text(encoding='utf-8')
            for heading in headings:self.assertEqual(1,text.splitlines().count('## '+heading),(index,filename,heading))
        for path in SKILL.rglob('*.md'):
            text=path.read_text(encoding='utf-8')
            for retired in ('Add a child** for an independent operation','importers and ancestors are selected too','map impact <file under the failure>'):self.assertNotIn(retired,text,str(path))


if __name__ == "__main__":
    unittest.main()


def test_the_five_minute_start_teaches_only_the_new_flow():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "README.zh-CN.md"):
        text = (root / name).read_text(encoding="utf-8")
        start = text.split("## Five-minute start" if name == "README.md" else "## 五分钟上手", 1)[1].split("\n## ", 1)[0]
        steps = [line.split("#", 1)[0].strip() for line in start.split("cd your-project", 1)[1].split("```", 1)[0].splitlines()
                 if line.strip()]
        assert [step.split()[:4] for step in steps] == [
            ["python", "-m", "flowguard", "status"], ["python", "-m", "flowguard", "req"],
            ["python", "-m", "flowguard", "where"], ["python", "-m", "pytest", "-q"], ["git", "add", "-A", "&&"]], (name, steps)
        assert "Request: R1" in steps[-1], steps
        assert not re.search(r"flowguard (map|target)\b", start.split("```")[1]), (name, start)


def test_legacy_procedure_pages_say_so_at_the_top_and_the_skill_needs_none_of_them():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    skill = root / ".agents/skills/flowguard"
    pages = [root / "docs/concept.md", *(skill / "references" / name for name in
             ("architecture_review.md", "first_map.md", "map_format.md", "model_recipes.md", "node_kinds.md", "routes.md"))]
    for page in pages:
        head = "\n".join(page.read_text(encoding="utf-8").split("\n\n")[1:2])
        assert head.startswith("> **Legacy, not required.**"), (page, head)
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "references/" not in text and "concept.md" not in text
