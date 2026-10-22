"""Keep obsolete receipt gates out of active product and skill surfaces."""
import ast
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_no_receipt_vocabulary_left():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "flowguard", ".agents/skills/flowguard", ".flowguard", "examples", "tests"],
        cwd=ROOT,
    ).decode().split("\0")
    exempt = {"tests/test_product_vocabulary.py", ".agents/skills/flowguard/references/upgrade_from_0_69.md"}
    offenders = []
    for relative in filter(None, paths):
        if relative in exempt:
            continue
        content = (ROOT / relative).read_bytes()
        if relative == "tests/test_behavior_commitment_ledger.py":
            text = content.decode("utf-8")
            legacy = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)
                          and node.name == "test_old_ledger_with_evidence_blocks_still_loads")
            lines = text.splitlines(keepends=True)
            # Only this legacy JSON migration example may name the removed keys.
            content = "".join(lines[:legacy.lineno - 1] + ["\n"] * (legacy.end_lineno - legacy.lineno + 1)
                              + lines[legacy.end_lineno:]).encode("utf-8")
        for match in re.finditer(b"receipt", content, re.IGNORECASE):
            offenders.append(f"{relative}:{content[:match.start()].count(bytes([10])) + 1}")
    assert not offenders, "\n".join(offenders)
