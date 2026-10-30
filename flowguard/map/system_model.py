"""The built-in map root: real architecture, generated bad changes and code consistency."""

from __future__ import annotations

import time

from .check import run_check
from .lint import reachable, architecture_findings, architecture_variants
from .mapfile import component_graph


def run_system_model(root, data, inv, *, view=None):
    """Run every time in-process; no user model imports, result cache or record."""
    from .proof import ModelResult

    started = time.monotonic()
    result = ModelResult(model="system", file=".flowguard/map.json",
                         rules=["dependency_cycle", "duplicate_owner", "layer_violation"])
    graph = component_graph(data, inv)
    result.problems.extend(f"{f.code} {f.component}: {f.message}"
                           for f in architecture_findings(data, graph, root=root, inv=inv) if f.level == "error")
    generated = 0
    for name, changed_data, changed_graph in architecture_variants(data, graph, root=root):
        generated += 1
        result.known_bad.append(str(name))
        if not any(f.level == "error" for f in architecture_findings(changed_data, changed_graph, root=root)):
            result.problems.append(f"generated known-bad variant '{name}' passed: the architecture rules do not catch it")
    result.known_bad.sort()
    consistency = run_check(root, data, inv, view=view)
    # Architecture rules (duplicate_owner included) are reported above, once.
    errors = [f for f in consistency if f.level == "error" and f.code != "duplicate_owner"]
    if errors:
        result.problems.append("the map does not match the code:\n" + "\n".join(
            f"{f.code} {f.component}: {f.message}" for f in errors[:5]))
    unbound = sum(f.code == "test_unbound" for f in consistency)
    if unbound:
        result.warnings.append(f"{unbound} test file(s) belong to no component")
    if not data.get("layers"):
        result.warnings.append('no layers in the map: the layer rule cannot be checked; add "layers"')
    if not generated:
        result.warnings.append("no known-bad variants could be generated")
    if result.problems:
        result.status = "fail"
    result.seconds = round(time.monotonic() - started, 3)
    return result
