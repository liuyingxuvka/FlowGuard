"""Project adoption instructions; existing owner instruction files remain intact."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import NamedTuple


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


OWNER_FILES = ("AGENTS.md", "CLAUDE.md")
EARLIER_RULES_MARKERS = ("<!-- BEGIN FLOWGUARD PROJECT RULES -->", "<!-- END FLOWGUARD PROJECT RULES -->")


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("AGENTS.md", """# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. Store the owner's own words once, as received, with `python -m flowguard req add <file|-> --id <id>`; never a plan, a list or text an AI wrote. Use `--supersedes <old-id>` when new words replace an earlier request. Keep `.flowguard/requests/` unchanged.
3. Locate code with `python -m flowguard where NAME`, change code and its tests together, and run the affected checks; report what actually ran and its result, plus any inherited technical work still open.
4. Commit code and tests together with your own message; add `Request: R<n>` when the change answers that stored request.
5. When state values, actions, conditions, settings or endings change, update the affected feature's flow model before its code: turn affected old and new requested outcomes into explicit `reach`/`progress` promises, even in the first model, and run `python -m flowguard check MODEL`. For code claims, follow the installed `flowguard/flow/HOWTO.md` and bind only the affected actions to real public calls. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path.
"""),
        TemplateFile("CLAUDE.md", "@AGENTS.md\n"),
    )


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
        return number not in inside and bool(numbered.match(line)) and ("-m flowguard" in line or line in template or line.startswith("4. Commit code and tests together") and "Request: R<n>" in line)

    found = tuple((number, line) for number, line in filled if number not in inside and (
        rule(number, line) or line in EARLIER_RULES_MARKERS
        or line.startswith("#") and "flowguard" in line.lower() and number in following and rule(*following[number])))
    held = {line for line in template if numbered.match(line)} <= {line for number, line in filled if number not in inside}
    return AdoptionRulesFound(held, tuple(blocks), found)



def write_template_files(
    root: str | Path,
    files: tuple[TemplateFile, ...],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        target = target_root / file.path
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
    return tuple(written)


__all__ = ["TemplateFile", "adoption_template_files", "write_template_files"]
