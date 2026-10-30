"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("docs/flowguard_agents_rules.md", """# FlowGuard rules for the project agent

Copy these six rules into the project's AGENTS.md (the project's CLAUDE.md holds the one line @AGENTS.md):

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. Before changing behaviour or structure: store only the owner's request once as received with `python -m flowguard req add <file|-> --id <id>` (reuse its ID if already stored) and never edit the stored copy, locate the owner model with `python -m flowguard read --find WORDS` (or a path:function) and extend it (a separate aspect gets its own model), run `python -m flowguard target start "<goal>" --request <id>` and `python -m flowguard target add <model>`, edit the copy in .flowguard/target/, in .flowguard/target/PLAN.txt, name changed rules that show NO GAP and functions the change must reach (`changes: <model>.<rule> by <id> "<quote>"` with a verbatim quote or `changes: <model>.<rule> because "<reason>"`, and `touch: <path>:<qualified name>`), run `python -m flowguard target check` until it shows no ERROR and each changed model shows EXPECTED GAP, `moved rules only`, `no rule change` or NO GAP with a line for every changed rule that shows NO GAP, change the code, then run `python -m flowguard target promote` and the map confirm it prints, and paste its owner block, when printed, unchanged into your final message.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change` and fix errors; for `port changed ... -> verify X`, run `python -m flowguard target add X` and make X receive the value; open each place a `consumes`, `produces`, `mentions` or `nothing produces` line names; restore what a `promises: -...` line lists or give the reason in the commit message; then run the affected tests and models it selects. Models, tests and code grow together: split a model or a test file that grows too big (map check warns at the soft limit and refuses at the hard one), keep them in correspondence where it makes functional sense, and give a reason where a model has no test or no code yet.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.
"""),
        TemplateFile("CLAUDE.md", "@AGENTS.md\n"),
    )




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
        protected = file.path == "CLAUDE.md"
        if protected and (target.exists() or target.is_symlink()):
            continue
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if protected:
            try:
                with target.open("xb") as stream:
                    stream.write(file.content.encode("utf-8"))
            except FileExistsError:
                continue
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
