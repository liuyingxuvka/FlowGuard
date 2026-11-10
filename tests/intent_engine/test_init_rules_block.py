"""init replaces the owner's level-one FlowGuard rules block in place.

The owner's repositories carry ``# FlowGuard rules for the project agent`` (a
level-one heading) with commands 4.x no longer has (``status``, ``where``).
4.0 init only knew the level-two block, so it appended a second set of rules.
Only that block is replaced; every other byte of AGENTS.md is kept.
"""
import re

import pytest

from flowguard.intent import cli
from flowguard.intent.config import load_config


OLD_BLOCK = '''# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request. The legacy map, `.flowguard/models/` and the target commands need no upkeep.
'''

# A repository whose own sections follow the block (the WorldGuard layout).
BEFORE_MIDDLE = '# WorldGuard project rules\n\n'
AFTER_MIDDLE = '''
## This repository

The project's test command is `python -m pytest -q`; run all of it before each commit.

One route per function: when a step fails, the error reaches the caller.
'''

# A repository where the block is the last section (the PhysicsGuard layout).
BEFORE_END = '''## PhysicsGuard Core Repository Rules

Policies:

- Use SI internally.

Releases:

- Never skip a number.

'''


def _init(root, text, *, newline='\n'):
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n')
    agents = root / 'AGENTS.md'
    agents.write_bytes(text.replace('\n', newline).encode())
    assert cli.init(load_config(root)) == 0
    return agents.read_bytes().decode()


@pytest.mark.parametrize('before,after', [(BEFORE_MIDDLE, AFTER_MIDDLE), (BEFORE_END, '')])
def test_level_one_owner_block_is_replaced_in_place(tmp_path, capsys, before, after):
    result = _init(tmp_path, before + OLD_BLOCK + after)
    expected = before + cli.PROJECT_RULES + ('\n' + after.lstrip('\n') if after else '')
    assert result == expected
    assert result.count('FlowGuard rules for the project agent') == 1
    assert 'flowguard status' not in result and 'flowguard where' not in result
    again = _init(tmp_path, result)
    assert again == result, 'init is idempotent after the replacement'


def test_block_left_beside_a_4_0_appended_copy_is_removed(tmp_path, capsys):
    damaged = BEFORE_MIDDLE + OLD_BLOCK + AFTER_MIDDLE.rstrip('\n') + '\n\n' + cli.PROJECT_RULES
    result = _init(tmp_path, damaged)
    assert result.count('FlowGuard rules for the project agent') == 1
    assert 'flowguard status' not in result
    # The marked block keeps its place; only the level-one copy is taken out.
    assert result == BEFORE_MIDDLE + AFTER_MIDDLE.lstrip('\n').rstrip('\n') + '\n\n' + cli.PROJECT_RULES


def test_crlf_file_keeps_its_line_endings_outside_the_block(tmp_path, capsys):
    result = _init(tmp_path, BEFORE_MIDDLE + OLD_BLOCK + AFTER_MIDDLE, newline='\r\n')
    expected = (BEFORE_MIDDLE + cli.PROJECT_RULES + '\n' + AFTER_MIDDLE.lstrip('\n')).replace('\n', '\r\n')
    assert result == expected


def test_rule_one_starts_each_task_with_new_task_and_the_block_keeps_three_rules(tmp_path, capsys):
    result = _init(tmp_path, '').lstrip('\n')
    assert result.startswith('<!-- flowguard:start -->\n## FlowGuard rules for the project agent\n\n') \
        and result.endswith('<!-- flowguard:end -->\n'), result
    rules = [line for line in result.splitlines() if line[:1].isdigit()]
    assert [line[:3] for line in rules] == ['1. ', '2. ', '3. '], rules
    # How a task starts: its baseline is recorded, so a commit made during the task does not hide its changes.
    assert rules[0] == ("1. Start each task with `python -m flowguard new-task` (it records the task's baseline; commits "
                        "during the task keep it). Run the project's tests and read the FlowGuard lines; every red and "
                        "lead ends with the next step: do it, and when it says to tell the owner, tell the owner before "
                        "changing the structure."), rules[0]


def test_other_level_one_headings_are_not_touched(tmp_path, capsys):
    text = '# FlowGuard rules for the release manager\n\nKeep this.\n'
    result = _init(tmp_path, text)
    assert result.startswith(text) and result.count('FlowGuard rules for the project agent') == 1


# The AGENTS.md FlowGuard 0.70 wrote into the owner's Planning Tool (shortened; same sections and wording).
TEAM = """Team coding standards live in `.github/copilot-instructions.md`.
This file supplements them only with the FlowGuard workflow.

## Engine and database guard

Use FlowGuard **0.70.14** with Python 3.11 or newer. The only approved installation is:

```text
python -m pip install --user "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.70.14"
```

FlowGuard needs no database. Before every FlowGuard command or unit-test invocation,
clear both `DATABASE_URL` and `CENTRAL_DATABASE_URL`.

"""
WORKFLOW = """## Six-step workflow

1. Start with `python -m flowguard read`. Find ownership with
   `python -m flowguard read --find <file-or-keywords>`.
2. For code-only changes, run the relevant Vitest files, then `python -m flowguard map check`.
3. Use `target start / add / check / promote` for structural changes.

## Owner-authorized current-map exception (2026-10-29)

For this task's complete migration only, the owner explicitly authorized direct current-map changes.
The approved test-launch configuration uses `python -m flowguard_unit_runner`.

"""
LIMITS = """## Project-specific limits

- `.flowguard/models/owners/**` are preserved 0.70.2 models and evidence.
- No agent may run `backend/tests/integration/**`: those tests write real databases.
- Do not run `flowguard change` against a large multi-commit diff.
"""


def test_the_flowguard_0_70_workflow_gives_way_to_the_rules_and_the_project_rules_stay(tmp_path, capsys):
    (tmp_path / 'web').mkdir()
    (tmp_path / 'web/package.json').write_text('{"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n')
    result = _init(tmp_path, TEAM + WORKFLOW + LIMITS)
    out = capsys.readouterr().out
    engine = TEAM.replace('**0.70.14**', f'**{cli.__version__}**').replace(
        'flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.70.14',
        f'flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git@v{cli.__version__}')
    assert result == engine + cli.PROJECT_RULES + '\n' + LIMITS, result       # in the workflow's place
    assert 'flowguard read' not in result and 'current-map' not in result and 'map check' not in result
    assert out.splitlines()[0] == 'Initialized intent sentinel, pytest plugin, CI fragment and three project rules.'
    assert 'AGENTS.md: the FlowGuard 0.70 section "Six-step workflow" is replaced by the project rules block' in out, out
    assert 'AGENTS.md: the FlowGuard 0.70 section "Owner-authorized current-map exception (2026-10-29)" is replaced' in out, out
    assert f'AGENTS.md: the FlowGuard version and install line now name {cli.__version__}' in out, out
    lines = result.splitlines()
    number = next(index for index, line in enumerate(lines, 1) if 'Do not run `flowguard change`' in line)
    # A ban names the command and asks for nothing: the line is listed as naming it, to reword, not deleted.
    assert f'AGENTS.md:{number} names `flowguard change` from FlowGuard 0.70–0.75, which 4.x does not have (' in out, out
    number = next(index for index, line in enumerate(lines, 1) if 'are preserved 0.70.2 models' in line)
    assert f'AGENTS.md:{number} ' not in out, out           # it says what the files are and asks for nothing
    again = _init(tmp_path, result)
    assert again == result, 'init is idempotent after the replacement'


def test_a_sentence_about_0_70_is_not_rewritten_and_the_projects_own_workflow_stays(tmp_path, capsys):
    # Planning Tool: "FlowGuard 0.70.14's native test indexing ... does not parse TypeScript imports" is true of
    # 0.70 and false of this version; rewriting its number would make a false rule. It asks for no 0.70 command,
    # so it is not listed either (round 22 F4).
    said = '- Product tests use TypeScript. FlowGuard 0.70.14\'s native test indexing does not parse TypeScript imports.\n'
    release = '## Release workflow\n\nRun the Makefile target check before tagging; keep the current map tiles.\n\n'
    result = _init(tmp_path, TEAM + WORKFLOW + release + LIMITS + said)
    out = capsys.readouterr().out
    assert said in result and release in result, result        # not rewritten, not deleted
    assert f'Use FlowGuard **{cli.__version__}**' in result and 'Six-step workflow' not in result
    number = result.splitlines().index(said.rstrip('\n')) + 1
    assert f'AGENTS.md:{number} ' not in out, out
    assert 'section "Release workflow"' not in out, out


def test_only_the_pinned_statement_and_the_install_line_change_and_another_bold_0_70_stays(tmp_path, capsys):
    archived = '- Reports written by FlowGuard **0.70.14** stay in `docs/archive/` as they are.\n'
    result = _init(tmp_path, TEAM + WORKFLOW + LIMITS + archived)
    out = capsys.readouterr().out
    assert f'Use FlowGuard **{cli.__version__}**' in result and f'FlowGuard.git@v{cli.__version__}"' in result, result
    assert result.endswith(archived), result                               # byte for byte
    number = result.splitlines().index(archived.rstrip('\n')) + 1
    assert f'AGENTS.md:{number} ' not in out, out         # it says what the archive holds and asks for nothing


# The Planning Tool's AGENTS.md as 4.2's init left it: a note that explains the legacy files, an instruction to no one.
PT_LEGACY_NOTE = """- Legacy FlowGuard 0.70 files: `.flowguard/models/**`, `.flowguard/map.json`,
  `.flowguard/owner_ledger.*`, `.flowguard/verification/**`, `.flowguard/README.md`,
  `flowguard_unit_runner.py` and `tests/flowguard/**` belong to the earlier 0.70.x
  workflow (map, targets, models, the native-binding launcher). FlowGuard 4.x does not
  read them and they need no upkeep: leave them unchanged. `tests/flowguard/` needs the
  removed 0.70 API, so pytest ignores it (`pyproject.toml`).
"""


def test_only_lines_that_ask_for_a_0_70_command_are_listed_and_a_note_on_the_legacy_files_is_not(tmp_path, capsys):
    # Round 22 F4: 4.2 listed the Planning Tool's note above ("still names FlowGuard 0.70 ... reword or delete it"),
    # though it only says which files are 0.70's and asks nothing; rewording it would lose the explanation.
    asks = ['- After every edit run `python -m flowguard map check` and fix what it reports.',
            '- Find code with `python -m flowguard where NAME` before you change it.',
            '- Install it with `pip install git+https://example.invalid/FlowGuard.git@v0.70.9`.']     # not init\'s own form
    result = _init(tmp_path, '## Project-specific limits\n\n' + PT_LEGACY_NOTE + '\n'.join(asks) + '\n')
    out = capsys.readouterr().out
    lines = result.splitlines()
    assert PT_LEGACY_NOTE in result, result                       # kept byte for byte
    for line in PT_LEGACY_NOTE.splitlines():
        assert f'AGENTS.md:{lines.index(line) + 1} ' not in out, out
    for line, asked in zip(asks, ('`python -m flowguard map check` from FlowGuard 0.70–0.75',
                                  '`python -m flowguard where` from FlowGuard 0.71–1.4',
                                  '`@v0.70.9` from FlowGuard 0.70')):
        assert f'AGENTS.md:{lines.index(line) + 1} names {asked}, which 4.x does not have (' in out, out


# Fragments of the owner's four AGENTS.md files around their FlowGuard block: a release rule that says "a FlowGuard
# release alone" and asks for no command, and two CI rules that name commands of FlowGuard 0.70.
RELEASE_RULE = ('- Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with '
                '`python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project). Raise '
                'that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is '
                'no reason to change it or to release this repository.\n')
WORLD_CI = ("The project's test command is `python -m pytest -q`; the whole suite takes seconds, so run all of it before "
            'each commit. CI runs it again on Python 3.11 and 3.13, plus `python -m flowguard map check --root . --strict`, '
            '`python -m flowguard release` and the skill install check.\n')
LOGIC_CI = ('- Run the affected tests while developing. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction '
            'and travel regressions, `python -m flowguard map check`, `python -m flowguard release`, and an installed '
            'skill byte check on every push and pull request.\n')
OWNER_FILES = {
    'worldguard': ('# WorldGuard project rules\n\n' + OLD_BLOCK + '\n## This repository\n\n' + RELEASE_RULE[2:] + '\n'
                   + WORLD_CI, WORLD_CI),
    'researchguard': ('# ResearchGuard maintenance\n\nReleases:\n\n' + RELEASE_RULE + '\n' + OLD_BLOCK, None),
    'logicwriting': ('# LogicWriting repository instructions\n\n## Validation\n\n' + LOGIC_CI + '\n' + RELEASE_RULE + '\n'
                     + OLD_BLOCK, LOGIC_CI),
    'physicsguard': ('## PhysicsGuard Core Repository Rules\n\nReleases:\n\n' + RELEASE_RULE + '\n' + OLD_BLOCK, None),
}


@pytest.mark.parametrize('name', sorted(OWNER_FILES))
def test_init_lists_lines_of_the_file_it_wrote_and_none_of_the_block_it_replaced(tmp_path, capsys, name):
    # Round 22 F4 review: 4.2.1's first fix listed the replaced block's `python -m flowguard status` and `where` lines
    # as still asking for them, numbered as lines of the new rules block; following it would delete FlowGuard's rules.
    text, ci = OWNER_FILES[name]
    result = _init(tmp_path, text)
    out = capsys.readouterr().out
    lines = result.splitlines()
    listed = dict(re.findall(r'^AGENTS\.md:(\d+) (.*)$', out, re.M))
    assert 'flowguard status' not in out and 'flowguard where' not in out, out
    assert list(listed) == ([str(lines.index(ci.rstrip('\n')) + 1)] if ci else []), out
    if ci:
        assert next(iter(listed.values())).startswith(
            'names `python -m flowguard map check` from FlowGuard 0.70–0.75 and `python -m flowguard release` from '
            'FlowGuard 0.70–1.4, which 4.x does not have ('), out


# Round 22 F4 review: one line per case, with what init names, or None for a line that asks for no earlier command.
# The releases are the git tags' (`cli.ERAS`).
BATTERY = {
    '- Before editing, run flowguard read and follow its owner list.': '`flowguard read` from FlowGuard 0.70–0.75',
    '- After each change run map check and fix what it reports.': '`map check` from FlowGuard 0.70–0.75',
    '- Use `target start` before a structural change.': '`target start` from FlowGuard 0.70–0.75',
    '- This project requires FlowGuard 0.70.14 or newer.': '`requires FlowGuard 0.70.14` from FlowGuard 0.70',
    '- Run the tests with `python flowguard_unit_runner.py tests/`.': '`python flowguard_unit_runner.py` from FlowGuard 0.70',
    '- On Windows run `py -m flowguard read --find x`.': '`py -m flowguard read` from FlowGuard 0.70–0.75',
    '- Or run `python.exe -m flowguard change` there.': '`python.exe -m flowguard change` from FlowGuard 0.70–0.75',
    '- Run `python3.11 -m flowguard read` first.': '`python3.11 -m flowguard read` from FlowGuard 0.70–0.75',
    '- Follow the current-map exception above for migrations.': '`current-map exception` from FlowGuard 0.70',
    '- Run `.venv/bin/python -m flowguard status` first.': '`python -m flowguard status` from FlowGuard 0.71–1.4',
    '- Start with python -m flowguard to see the brief.': None,
    '- Run python -m flowguard before each task, then pytest.': None,
    "- The block `FlowGuard rules for the project agent` is FlowGuard's own.": None,
    '- Run `python -m flowguard check --static` and `python -m flowguard new-task`.': None,
    '- Reports written by FlowGuard **0.70.14** stay in docs/archive/.': None,
    # Second review: the 1.x commands decide and draft (4.x drafts with `anchor draft` and `model draft`), and four
    # lines 4.2.0 listed: map check in any case, a required version in two more spellings, a capitalized command.
    '- Record the decision with `python -m flowguard decide ID --owner R3`.': '`python -m flowguard decide` from FlowGuard 0.75–1.4',
    '- Draft it with `python -m flowguard draft pkg/orders.py:Order`.': '`python -m flowguard draft` from FlowGuard 1.2–1.4',
    '- Draft an anchor with `python -m flowguard anchor draft pkg/orders.py:accept`.': None,
    '- Map check must pass before merge.': '`Map check` from FlowGuard 0.70–0.75',
    '- FlowGuard 0.70.14 is required.': '`FlowGuard 0.70.14 is required` from FlowGuard 0.70',
    '- FlowGuard 0.70.x is required for the native bindings.': '`FlowGuard 0.70.x is required` from FlowGuard 0.70',
    '- Install it with `pip install "flowguard==0.70.14"`.': '`flowguard==0.70.14` from FlowGuard 0.70',
    '- Run `FlowGuard read` first.': '`FlowGuard read` from FlowGuard 0.70–0.75',
    # Prose after the name: release, where and status are commands only after a launcher or a backquote.
    '- After each flowguard release, read the changelog.': None,
    '- Ask the flowguard where the owner lives.': None,
    '- Look at the flowguard status line in CI.': None,
    # Accepted: 0.70's AGENTS.md wrote `map check` bare, so a map check in prose is listed too; the note only asks
    # to reword the line.
    '- Run the site map check before deploying the docs.': '`map check` from FlowGuard 0.70–0.75',
}


def test_a_line_naming_commands_of_two_releases_names_each_with_its_own(tmp_path, capsys):
    line = '- CI runs `python -m flowguard map check` and `python -m flowguard status` and `python -m flowguard release`.'
    result = _init(tmp_path, '## Project-specific limits\n\n' + line + '\n')
    number = result.splitlines().index(line) + 1
    assert (f'AGENTS.md:{number} names `python -m flowguard map check` from FlowGuard 0.70–0.75 and '
            '`python -m flowguard status` from FlowGuard 0.71–1.4 and `python -m flowguard release` from FlowGuard '
            '0.70–1.4, which 4.x does not have (') in capsys.readouterr().out


def test_init_names_each_earlier_command_in_full_and_no_word_that_only_follows_flowguard(tmp_path, capsys):
    result = _init(tmp_path, '## Project-specific limits\n\n' + '\n'.join(BATTERY) + '\n')
    out = capsys.readouterr().out
    lines = result.splitlines()
    for line, named in BATTERY.items():
        number = lines.index(line) + 1
        if named:
            assert f'AGENTS.md:{number} names {named}, which 4.x does not have (' in out, (line, out)
        else:
            assert f'AGENTS.md:{number} ' not in out, (line, out)
