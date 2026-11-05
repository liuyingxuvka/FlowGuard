"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path
import re
from typing import NamedTuple


from .template_text.behaviour import BEHAVIOUR_MODEL_TEMPLATE
from .template_text.validator import (
    VALIDATOR_MODEL_TEMPLATE,
)
from .template_text.ui_journey import (
    UI_JOURNEY_MODEL_TEMPLATE,
)


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


# The owner's instructions: written only when missing, never changed, also with --force.
OWNER_FILES = ("AGENTS.md", "CLAUDE.md")


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("AGENTS.md", """# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result, plus any inherited technical work still open.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request. The legacy map, `.flowguard/models/` and the target commands need no upkeep.
5. When a request adds or changes state values, actions, conditions, settings or endings, change the affected feature's flow model before the code: turn affected old and new requested outcomes into explicit `reach`/`progress` promises, even in the first model, and run `python -m flowguard check`. For code claims, follow the installed `flowguard/flow/HOWTO.md` and bind only the affected actions to real public calls. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path.
"""),
        TemplateFile("CLAUDE.md", "@AGENTS.md\n"),
    )


# The markers around the FlowGuard block that earlier releases put into a project's AGENTS.md.
EARLIER_RULES_MARKERS = ("<!-- BEGIN FLOWGUARD PROJECT RULES -->", "<!-- END FLOWGUARD PROJECT RULES -->")


class AdoptionRulesFound(NamedTuple):
    """What an existing AGENTS.md holds of the FlowGuard rules; line numbers count from 1."""

    held: bool  # every current rule line is there, outside any earlier marked block
    blocks: tuple[tuple[int, int], ...]  # first and last line of each earlier marked block, markers included
    lines: tuple[tuple[int, str], ...]  # other lines, outside those blocks, that look like FlowGuard rules


def adoption_rules_in(text: str) -> AdoptionRulesFound:
    """Whether an AGENTS.md text holds every current rule line, and its parts that look like earlier FlowGuard rules.

    An earlier marked block runs from a begin marker to the next end marker; it is named whole, every line inside
    it included, and current rules inside it do not count as held. Outside such blocks a line looks like a rule when
    it is a numbered rule that mentions ``-m flowguard`` (every FlowGuard rule set had that form) or repeats a
    numbered line of the current rules, a marker without its pair, or a heading that names FlowGuard and whose next
    non-blank line is such a numbered rule. A current rule found there is named too, so it is replaced, never added
    twice. The project's own lines, such as a bullet that runs a FlowGuard command in CI or a FlowGuard heading over
    it, are not named."""
    template = next(file.content for file in adoption_template_files() if file.path == "AGENTS.md").splitlines()
    numbered = re.compile(r"\d+\. ")
    lines = [line.strip() for line in text.split("\n")]
    begin, end = EARLIER_RULES_MARKERS
    blocks: list[tuple[int, int]] = []
    start = None
    for number, line in enumerate(lines, 1):
        if line == begin and start is None:
            start = number
        elif line == end and start is not None:
            blocks.append((start, number))
            start = None
    inside = {number for first, last in blocks for number in range(first, last + 1)}
    filled = [(number, line) for number, line in enumerate(lines, 1) if line]
    following = {number: after for (number, _), after in zip(filled, filled[1:])}

    def rule(number: int, line: str) -> bool:
        return number not in inside and bool(numbered.match(line)) and ("-m flowguard" in line or line in template)

    found = tuple((number, line) for number, line in filled if number not in inside and (
        rule(number, line) or line in EARLIER_RULES_MARKERS
        or line.startswith("#") and "flowguard" in line.lower() and number in following and rule(*following[number])))
    held = {line for line in template if numbered.match(line)} <= {line for number, line in filled if number not in inside}
    return AdoptionRulesFound(held, tuple(blocks), found)


def behaviour_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/order_placement.py", BEHAVIOUR_MODEL_TEMPLATE),
    )


def ui_journey_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/ui_journey.py", UI_JOURNEY_MODEL_TEMPLATE),
    )


def validator_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/validator.py", VALIDATOR_MODEL_TEMPLATE),
    )



def cases_template_files() -> tuple[TemplateFile, ...]:
    """A named case table, real replay and matching bound tests."""
    return (
        TemplateFile(
            ".flowguard/models/cases.py",
            '''"""Compare each named input case with its expected result on the real function."""
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "cases"
PARENT = "REPLACE_ME"
IMPLEMENTED_BY = {"Convert": "REPLACE_ME/api.py:convert"}
TESTED_BY = {"case_output_matches": ["REPLACE_ME/tests/test_cases.py:test_cases"]}
CASES = (("zero", 0, 0), ("positive", 2, 4), ("negative", -3, -6))

@dataclass(frozen=True)
class State:
    name: str = ""
    actual: int = 0
    expected: int = 0

class CaseStep:
    name = "Convert"
    reads = ()
    writes = ("name", "actual", "expected")

    def __init__(self, bad=False):
        self.bad = bad

    def apply(self, case, state):
        name, value, expected = case
        actual = expected + 1 if self.bad else expected
        return (FunctionResult(actual, State(name, actual, expected), label=name),)

RULES = (Invariant("case_output_matches", "each case produces its expected result",
                   lambda state, trace: state.actual == state.expected),)

def _explorer(bad=False):
    return Explorer(Workflow((CaseStep(bad),)), (State(),), CASES,
                    invariants=RULES, max_sequence_length=1, progress_steps=0)

def build_explorer():
    return _explorer()

def broken_variants():
    return {"wrong_output": _explorer(True)}

def conformance():
    from REPLACE_ME.api import convert
    facts = []
    for name, value, expected in CASES:
        actual = convert(value)
        facts.append(Fact(name, actual == expected, repr(actual)))
    return CodeFactsReport(tuple(facts))
''',
        ),
        TemplateFile(
            "REPLACE_ME/tests/test_cases.py",
            '''"""Bind the same named cases to the real conversion function."""
import pytest
from REPLACE_ME.api import convert

@pytest.mark.parametrize("name,value,expected", (("zero", 0, 0), ("positive", 2, 4), ("negative", -3, -6)))
def test_cases(name, value, expected):
    assert convert(value) == expected
''',
        ),
    )


def write_template_files(
    root: str | Path,
    files: tuple[TemplateFile, ...],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        staged = (target_root / ".flowguard/target").is_dir() and file.path.startswith(".flowguard/models/")
        relative = file.path.replace(".flowguard/models/", ".flowguard/target/models/", 1) if staged else file.path
        target = target_root / relative
        protected = file.path in OWNER_FILES
        if "@AGENTS.md" in file.content.splitlines() and not (target_root / "AGENTS.md").is_file():
            continue  # an include of a file that is not there would include nothing
        if not protected and target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if protected:
            # An existing AGENTS.md or CLAUDE.md keeps the owner's instructions, even with --force. "Existing" is
            # anything at the path: a file, a directory or a link, also a dangling one. Ask for that directly:
            # opening a directory for an exclusive create raises FileExistsError on POSIX but PermissionError on
            # Windows, so the error type cannot decide it.
            if os.path.lexists(target):
                continue
            with target.open("xb") as stream:
                stream.write(file.content.encode("utf-8"))
        else:
            target.write_text(file.content, encoding="utf-8")
        written.append(target)
    if any(p.parent == target_root / ".flowguard/models" for p in written) and (target_root / ".flowguard/map.json").is_file():
        from .map.mapfile import load_map, model_digests, save_map
        data = load_map(target_root)
        data["model_digests"] = model_digests(target_root)
        save_map(target_root, data)
    return tuple(written)


__all__ = [
    "TemplateFile",
    "adoption_template_files",
    "behaviour_template_files",
    "cases_template_files",
    "validator_template_files",
    "ui_journey_template_files",
    "write_template_files",
]
