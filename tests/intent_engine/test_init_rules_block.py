"""init replaces the owner's level-one FlowGuard rules block in place.

The owner's repositories carry ``# FlowGuard rules for the project agent`` (a
level-one heading) with commands 4.x no longer has (``status``, ``where``).
4.0 init only knew the level-two block, so it appended a second set of rules.
Only that block is replaced; every other byte of AGENTS.md is kept.
"""
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


def test_other_level_one_headings_are_not_touched(tmp_path, capsys):
    text = '# FlowGuard rules for the release manager\n\nKeep this.\n'
    result = _init(tmp_path, text)
    assert result.startswith(text) and result.count('FlowGuard rules for the project agent') == 1
