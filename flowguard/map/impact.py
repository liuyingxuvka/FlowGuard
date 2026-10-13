"""Change impact: changed files -> owning components -> dependents -> tests and models to run."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_TEST_COMMAND, glob_match, is_test_file, norm
from .inventory import Inventory
from .mapfile import component_graph, is_stale, owner_index
from .proof import model_id_of


@dataclass
class Impact:
    changed: list[str]
    direct: list[str]
    dependents: list[str]
    unmapped: list[str]
    tests: list[str]
    models: list[str]
    needs_review: list[str]                      # confirmed components whose owned files changed
    test_command: str = DEFAULT_TEST_COMMAND
    total_tests: int = 0
    map_changed: bool = field(default=False)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def changed_files(root: Path, base: str) -> list[str]:
    """Files changed versus BASE (committed or not) plus untracked files."""
    files: set[str] = set()
    for cmd in (["git", "-C", str(root), "diff", "--name-only", base],
                ["git", "-C", str(root), "ls-files", "-o", "--exclude-standard"]):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or f"failed: {' '.join(cmd)}")
        files |= {norm(x) for x in res.stdout.splitlines() if x.strip()}
    return sorted(files)


def compute_impact(root: Path, data: dict, inv: Inventory, changed: list[str], depth: int = 1) -> Impact:
    owner, _ = owner_index(data, inv)
    graph = component_graph(data, inv)
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse[dst].add(src)
    direct = sorted({owner[f] for f in changed if f in owner})
    affected, frontier = set(direct), set(direct)
    for _ in range(depth):
        frontier = {u for c in frontier for u in reverse.get(c, ())} - affected
        affected |= frontier
    by_id = {c["id"]: c for c in data["components"]}
    tests = {f for f in changed if f in inv.tests}
    models = {m for m in changed if m.startswith(".flowguard/models/") and m.endswith(".py")}
    for cid in affected:
        for pat in by_id[cid].get("tests", []):
            tests |= {f for f in inv.files if glob_match(f, pat)}
        models |= set(by_id[cid].get("models", []))
    return Impact(
        changed=changed,
        direct=direct,
        dependents=sorted(affected - set(direct)),
        unmapped=[f for f in changed if f in inv.source and f not in owner and not is_test_file(f)],
        tests=sorted(tests),
        models=sorted(m for m in models if (root / m).is_file()),
        needs_review=[cid for cid in direct if is_stale(root, by_id[cid], inv)],
        test_command=data.get("test_command") or DEFAULT_TEST_COMMAND,
        total_tests=len(inv.tests),
        map_changed=".flowguard/map.json" in changed,
    )


def render_impact(imp: Impact) -> str:
    lines = [f"changed files: {len(imp.changed)}  directly affected: {', '.join(imp.direct) or '-'}",
             f"dependents: {', '.join(imp.dependents) or '-'}"]
    if imp.unmapped:
        lines.append("UNMAPPED changed files (add each to one component's files): " + ", ".join(imp.unmapped))
    lines.append(f"models to run: {', '.join(imp.models) or '-'}")
    lines.append(f"tests to run ({len(imp.tests)} of {imp.total_tests}): " + (" ".join(imp.tests) or "-"))
    if imp.tests:
        lines.append(f"run: {imp.test_command} {' '.join(imp.tests)}")
    if imp.models:
        lines.append("run: python -m flowguard.map models " + " ".join(model_id_of(m) for m in imp.models))
    for cid in imp.needs_review:
        lines.append(f"REVIEW {cid}: its files changed; update its description if behavior changed, then confirm {cid}")
    return "\n".join(lines)
