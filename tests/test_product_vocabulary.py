"""Keep obsolete receipt gates out of active product and skill surfaces."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_no_receipt_vocabulary_left():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "flowguard", ".agents/skills/flowguard", ".flowguard", "examples", "tests"],
        cwd=ROOT,
    ).decode().split("\0")
    exempt = {"tests/test_product_vocabulary.py", ".agents/skills/flowguard/references/upgrade.md"}
    offenders = []
    for relative in filter(None, paths):
        if relative in exempt:
            continue
        content = (ROOT / relative).read_bytes()
        for match in re.finditer(b"receipt", content, re.IGNORECASE):
            offenders.append(f"{relative}:{content[:match.start()].count(bytes([10])) + 1}")
    assert not offenders, "\n".join(offenders)


PENDING = {
}


def test_no_self_reported_currentness_left():
    paths = set(filter(None, subprocess.check_output(
        ["git", "ls-files", "-z", "--", "flowguard", ".agents/skills/flowguard", ".flowguard", "examples", "tests", "docs"],
        cwd=ROOT,
    ).decode().split("\0")))
    names = (
        "evidence_current",
        "has_current_pass",
        "evidence_state",
        "owner_evidence_current",
        "evidence_currentness_id",
        "currentness_id",
        "parity_evidence_current",
        "behavior_parity_current",
        "delegation_evidence_current",
        "relation_provenance_current",
        "inventory_current",
        "owner_model_current",
        "current_revision",
        "proof_status",
        "freshness_state",
        "model_sync_state",
        "result_status",
    )
    pattern = re.compile(r"\b(?:" + "|".join(names) + r")\b|\brow\.current\b")
    matched = set()
    offenders = []
    for relative in sorted(paths):
        if relative == "tests/test_product_vocabulary.py":
            continue
        path = ROOT / relative
        if not path.is_file():
            if relative not in PENDING:
                offenders.append(f"{relative}: tracked file is missing")
            continue
        content = path.read_text(encoding="utf-8")
        matches = list(pattern.finditer(content))
        if matches:
            matched.add(relative)
            if relative not in PENDING:
                for match in matches:
                    line = content[:match.start()].count("\n") + 1
                    offenders.append(f"{relative}:{line}: {match.group()}: no retirement action in PENDING")
    for relative, action in sorted(PENDING.items()):
        if relative not in paths or not (ROOT / relative).is_file() or relative not in matched:
            offenders.append(f"{relative}: {action}: no longer tracked, present and matching; remove from PENDING")
    assert not offenders, "\n".join(offenders)
