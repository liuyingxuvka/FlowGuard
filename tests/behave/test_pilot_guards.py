"""Keep the unpublished pilot separate from the shipped product surface."""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_pilot_not_exported():
    code = (
        "import sys, flowguard; "
        "assert 'flowguard.behave' not in sys.modules; "
        "assert 'behave' not in flowguard.__all__; "
        "assert 'flowguard.behave' not in flowguard._PUBLIC_API"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_pilot_not_in_verbs():
    from flowguard.__main__ import VERB_PURPOSE

    assert set(VERB_PURPOSE) == {
        "read", "status", "change", "release", "template", "target", "req", "map",
    }


def test_pilot_not_documented():
    paths = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
    for directory in (ROOT / ".agents/skills/flowguard", ROOT / "docs"):
        paths.extend(path for path in directory.rglob("*") if path.is_file())
    offenders = []
    for path in sorted(paths):
        for number, line in enumerate(path.read_bytes().splitlines(), 1):
            if b"flowguard.behave" in line or b"behave/" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: pilot documentation")
    assert not offenders, "\n".join(offenders)


def test_pilot_has_no_subject_names():
    pattern = re.compile(
        r"\b(?:inspect|inspection|counter|bring|workshop|tool|member|rent|rental|"
        r"branch|hold|plus|maintenance)\b", re.IGNORECASE,
    )
    paths = list((ROOT / "flowguard/behave").rglob("*.py"))
    paths.extend(ROOT / "flowguard/map" / name for name in ("derived.py", "textrules.py"))
    offenders = []
    for path in sorted(path for path in paths if path.is_file()):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in pattern.finditer(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {match.group()}")
    assert not offenders, "\n".join(offenders)
