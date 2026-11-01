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

from flowguard._next.checks import CONFLICT, check_model, reach_line
from flowguard._next.model import load_model

HOWTO = Path(__file__).parents[2] / "flowguard" / "_next" / "HOWTO.md"


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


def test_the_guide_is_one_page():
    assert len(HOWTO.read_text(encoding="utf-8").splitlines()) <= 130


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
        assert imports == [("flowguard._next", "Model, need")]
    assert "machine" not in HOWTO.read_text(encoding="utf-8").lower().replace("a small machine", "")
