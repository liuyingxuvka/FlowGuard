"""FG-811 HOWTO: every code block of the one-page guide runs, and what it says the check
prints is what the engine finds.

The guide's text blocks show `check` output: a verdict line (the output contract of the
check command, rendered here from the engine's findings by the same rules) followed by the
reach line or the conflict with its path. When the `check` command lands, its own output
is compared with the same blocks.
"""
from __future__ import annotations

import re
from pathlib import Path

from flowguard.flow.checks import CONFLICT, check_model, reach_line
from flowguard.flow.model import load_model

HOWTO = Path(__file__).parents[2] / "flowguard" / "flow" / "HOWTO.md"


def blocks(kind):
    return re.findall(rf"```{kind}\n(.*?)```", HOWTO.read_text(encoding="utf-8"), re.S)


def verdict(report):
    """The first line of the output contract for one model, from its findings."""
    conflicts = [f for f in report.findings if f.cls == CONFLICT]
    warnings = [f for f in report.findings if f.cls == "warning"]
    if conflicts:
        n = len(conflicts)
        return f"{n} new conflict{'s' if n != 1 else ''}; complete"
    return "clean, complete" + (f"; {len(warnings)} model warnings" if warnings else "")


def test_every_code_block_is_a_working_model(project):
    models = blocks("python")
    assert models
    for n, code in enumerate(models):
        path = project.flow(f"block{n}", code)
        report = check_model(load_model(path, project.root))
        assert report.graph.complete


def test_the_stated_outputs_are_what_the_check_finds(project):
    [model] = [b for b in blocks("python") if "MODEL = m" in b]
    clean_text, broken_text = blocks("text")
    path = project.flow("parcels", model)
    report = check_model(load_model(path, project.root))
    first, line = clean_text.strip().splitlines()
    assert first == verdict(report)
    assert line == reach_line(report.reach)

    project.flow("parcels", "\n".join(l for l in model.splitlines() if '"the locker is full"' not in l) + "\n")
    report = check_model(load_model(path, project.root))
    first, headline, path_line = broken_text.strip().splitlines()
    assert first == verdict(report)
    [f] = [f for f in report.findings if f.cls == CONFLICT]
    assert headline == f"NEW {f.kind} {f.model}: {f.subject}"
    assert path_line.strip() == f"path ({len(f.path)} steps): " + " ; ".join(f.path)


def test_the_guide_uses_only_the_public_names():
    for code in blocks("python"):
        imports = re.findall(r"^from (\S+) import (.+)$", code, re.M)
        assert imports == [("flowguard.flow", "Model, need")]
    assert "machine" not in HOWTO.read_text(encoding="utf-8").lower().replace("a small machine", "")


def test_the_guide_says_how_requests_are_stored_and_what_to_commit():
    """A7: the one page an AI reads names `req add` (never a hand-written request file), says
    to commit conflicts.json, and that release checks the flow models without a legacy map."""
    text = HOWTO.read_text(encoding="utf-8")
    assert "python -m flowguard req add <file> --id R10" in text
    assert "never write a file in `.flowguard/requests/` by hand" in text
    assert "`.flowguard/conflicts.json`: commit that file with the change" in text
    assert "`python -m flowguard release` runs `check --full`" in text and "no legacy map" in text


def test_the_guide_explains_what_blocks_and_which_check_runs_deliberate_breaks():
    text = " ".join(HOWTO.read_text(encoding="utf-8").split())
    assert "Only `check --full`" in text and "ordinary `check` does not run these deliberate breaks" in text
    assert "CI blocks them only if it runs release" in text
    assert "Without a hook that runs the check, a commit is not blocked" in text
    assert "not a required three-file split" in text
    assert "Dead ends and never-happens behavior must be fixed in code" in text
