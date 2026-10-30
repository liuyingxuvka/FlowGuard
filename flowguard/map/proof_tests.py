"""Execute bound Python test items and check their individual native reach."""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING
from .common import child_pytest_environment, parse_test_anchor, child_import_path
from .mapfile import MapError, load_map, read_model_contract, resolve_model_path

if TYPE_CHECKING:
    from .proof import ModelResult


def _run_bound_tests(
    root: Path,
    path: Path,
    result: ModelResult,
    *,
    timeout: int,
    statuses: dict[str, str] | None = None,
    view=None,
    _fail,
    _project_missing,
    run_isolated_process,
) -> None:
    """Run a model's unique bound Python nodes once, then judge every actual item independently."""
    started = time.monotonic()
    ran_tests = False
    try:
        physical = resolve_model_path(
            root, path.relative_to(root).as_posix(), view=view
        )
        if physical is None:
            raise FileNotFoundError(f"model {path} is absent from the target view")
        contract = read_model_contract(physical)
        bindings = [
            (invariant, anchor)
            for invariant, anchors in contract.get("TESTED_BY", {}).items()
            for anchor in anchors
        ]
        if statuses is not None:
            statuses.update({anchor: "not_run" for _, anchor in bindings})
        if not bindings:
            return
        anchors = list(contract.get("IMPLEMENTED_BY", {}).values())
        if not anchors:
            result.warnings.append(
                "TESTED_BY reach not checked: no IMPLEMENTED_BY anchors"
            )
            return
        nodes, exact_items = {}, set()
        for invariant, anchor in bindings:
            rel, _, symbol = anchor.partition(":")
            if not rel.endswith(".py"):
                result.warnings.append(
                    f"TESTED_BY {anchor} is not a Python test: reach not checked"
                )
                continue
            try:
                rel, symbol, suffix = parse_test_anchor(anchor)
            except ValueError as exc:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(result, f"tested_by_failed {invariant} -> {anchor}: {exc}")
                continue
            from .testtree import resolve_test_anchor

            match = resolve_test_anchor(root / rel, symbol)
            if match is None:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(
                    result,
                    f"tested_by_failed {invariant} -> {anchor}: test symbol is missing, ambiguous or unreadable",
                )
                continue
            nodes[anchor] = rel + "::" + "::".join(match.split(".")) + suffix
            if suffix:
                exact_items.add(anchor)
        if not nodes:
            return
        env = child_pytest_environment(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        try:
            data = view.data if view is not None else load_map(root)
        except MapError:
            data = {}
        env["PYTHONPATH"] = os.pathsep.join(child_import_path(root, data))
        with tempfile.TemporaryDirectory(prefix="flowguard-tested-by-") as folder:
            request, output = (
                Path(folder) / "request.json",
                Path(folder) / "result.json",
            )
            request.write_text(
                json.dumps(
                    {
                        "anchors": anchors,
                        "nodes": sorted(set(nodes.values())),
                        **({"view": view.to_payload()} if view is not None else {}),
                    }
                ),
                encoding="utf-8",
            )
            ran_tests = True
            proc, timed_out, cleaned = run_isolated_process(
                [
                    sys.executable,
                    "-m",
                    "flowguard.map.testreach",
                    str(root),
                    str(request),
                    str(output),
                ],
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            if timed_out or not cleaned or not output.is_file():
                raise RuntimeError(
                    f"TESTED_BY process exit={proc.returncode}; timeout={timed_out}; cleanup_confirmed={cleaned}; "
                    + (proc.stderr or proc.stdout)[-1000:]
                )
            payload = json.loads(output.read_text(encoding="utf-8"))
        diagnostic = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-2000:]
        if payload.get("error") or not payload.get("complete"):
            raise RuntimeError(
                payload.get("error") or "TESTED_BY result was incomplete"
            )
        imports = payload.get("import_errors", [])
        external = [
            item
            for item in imports
            if item["type"] != "ModuleNotFoundError"
            or not _project_missing(root, item.get("name"), view=view)
        ]
        if external:
            raise RuntimeError(
                "TESTED_BY dependency/import error: "
                + "; ".join(
                    f"{item['type']} {item.get('name')!r} during {item['phase']} at {item['nodeid']}: {item['message']}"
                    for item in external
                )
                + "\n"
                + diagnostic
            )
        known_failure = False
        for invariant, anchor in bindings:
            if anchor not in nodes:
                continue
            selector = nodes[anchor]
            items = [
                item
                for item in payload["items"]
                if item["nodeid"] == selector
                or (
                    anchor not in exact_items
                    and item["nodeid"].startswith(selector + "[")
                )
            ]
            failed = [
                item["nodeid"]
                for item in items
                if item["failed"] or not item["entered"] or not item["call_passed"]
            ]
            if not items or failed:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(
                    result,
                    f"tested_by_failed {invariant} -> {anchor}: {', '.join(failed) or 'test was not collected/executed'}",
                )
                known_failure = True
                continue
            missed = [
                item["nodeid"]
                for item in items
                if not (set(item["consulted"]) & set(anchors))
            ]
            if statuses is not None:
                statuses[anchor] = "misses_anchor" if missed else "passed"
            if missed:
                _fail(
                    result,
                    f"tested_by_misses_anchor {invariant} -> {anchor}: the test ran but called or read none of IMPLEMENTED_BY; "
                    + ", ".join(missed),
                )
        if proc.returncode != 0:
            if known_failure:
                problem = "TESTED_BY pytest output: " + diagnostic
                result.problems.append(problem)
                result.code_gaps.append(problem)
            else:
                _fail(
                    result,
                    f"TESTED_BY pytest process exited {proc.returncode}: " + diagnostic,
                )
    except Exception as exc:
        result.status = "error"
        result.problems.append(f"TESTED_BY environment/execution error: {exc}")
    finally:
        if ran_tests:
            result.test_seconds = round(time.monotonic() - started, 3)
