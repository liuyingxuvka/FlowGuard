"""Keep obsolete receipt gates out of active product and skill surfaces."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_no_receipt_vocabulary_left():
    # Model ports use receipts for observed parent/child data flow. The retired
    # product was the persisted owner-receipt gate, not this ordinary word.
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "flowguard", ".agents/skills/flowguard", ".flowguard", "examples", "tests"],
        cwd=ROOT,
    ).decode().split("\0")
    exempt = {"tests/test_product_vocabulary.py"}
    offenders = []
    for relative in filter(None, paths):
        if relative in exempt:
            continue
        content = (ROOT / relative).read_bytes()
        for match in re.finditer(rb"owner[-_]receipt|receipt[-_](?:gate|ledger)|(?:gate|ledger)[-_]receipt", content, re.IGNORECASE):
            offenders.append(f"{relative}:{content[:match.start()].count(bytes([10])) + 1}")
    assert not offenders, "\n".join(offenders)


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
    offenders = []
    for relative in sorted(paths):
        if relative == "tests/test_product_vocabulary.py":
            continue
        path = ROOT / relative
        if not path.is_file():
            offenders.append(f"{relative}: tracked file is missing")
            continue
        content = path.read_text(encoding="utf-8")
        matches = list(pattern.finditer(content))
        if matches:
            for match in matches:
                line = content[:match.start()].count("\n") + 1
                offenders.append(f"{relative}:{line}: {match.group()}: obsolete currentness vocabulary")
    assert not offenders, "\n".join(offenders)


def test_public_names_use_one_vocabulary():
    import flowguard

    assert len(flowguard.__all__) <= 300
    forbidden = re.compile(r"EVIDENCE|PROOF|LEDGER|AUTHORIT|CONFIDENCE|CLAIM_SCOPE|CURRENT", re.IGNORECASE)
    offenders = [name for name in flowguard.__all__ if forbidden.search(name)]
    assert not offenders, offenders
    allowed_modules = {
        'flowguard.core',
        'flowguard.workflow',
        'flowguard.explorer',
        'flowguard.report',
        'flowguard.trace',
        'flowguard.replay',
        'flowguard.conformance',
        'flowguard.checks',
        'flowguard.scenario',
        'flowguard.loop',
        'flowguard.export',
        'flowguard.kit',
        'flowguard.templates',
    }
    unexpected = set(flowguard._PUBLIC_API) - allowed_modules
    assert not unexpected, sorted(unexpected)
