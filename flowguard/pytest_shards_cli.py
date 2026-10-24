"""Run the full pytest inventory as a finite, exact node-id shard mesh."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping


from flowguard.pytest_shards import (  # noqa: E402
    PARTITION_ALGORITHM,
    aggregate_pytest_projections,
    nodeid_fingerprint,
    normalize_nodeids,
    partition_nodeids,
    validate_partition,
)
from flowguard.map.runner import run_isolated_process
from flowguard.pytest_junit import _pytest_junit_projection  # noqa: E402


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() and path.is_symlink():
        raise RuntimeError(f"refusing to write through symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_object(path: Path) -> Mapping[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    timed_out = False
    with stdout_path.open("w", encoding="utf-8", newline="") as stdout, stderr_path.open(
        "w", encoding="utf-8", newline=""
    ) as stderr:
        try:
            result, timed_out, cleanup_confirmed = run_isolated_process(
                command, cwd=cwd, env=dict(environment), stdout=stdout, stderr=stderr,
                timeout=timeout_seconds,
            )
            exit_code = result.returncode
        except (OSError, ValueError) as exc:
            return {
                "exit_code": 70, "timed_out": False, "cleanup_confirmed": False,
                "launch_error": f"{type(exc).__name__}: {exc}",
                "duration_seconds": time.time() - started,
            }

    return {
        "exit_code": int(exit_code),
        "timed_out": timed_out,
        "cleanup_confirmed": cleanup_confirmed,
        "lingering_killed": bool(getattr(result, "lingering_killed", False)),
        "launch_error": "" if cleanup_confirmed else "cleanup_unconfirmed",
        "duration_seconds": time.time() - started,
    }


def _blocked_payload(
    *,
    output_root: Path,
    reason: str,
    collection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "flowguard.pytest_shard_run.v1",
        "status": "blocked",
        "ok": False,
        "scope": "full",
        "blockers": [reason],
        "shards": [],
        "pytest_execution": {
            "schema_version": "flowguard.pytest_execution.v2",
            "selected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "node_ids": [],
            "optional_metadata_unverified": False,
        },
        "output_root": str(output_root),
    }
    if collection is not None:
        payload["collection"] = dict(collection)
    return payload


def _deadline_remaining(deadline: float) -> float:
    """Return the remaining monotonic budget for one invocation."""

    return max(0.0, float(deadline) - time.monotonic())


def _deadline_blocked_shard_row(
    *,
    shard_id: str,
    shard_nodeids: tuple[str, ...],
    request_path: Path,
    collection_result_path: Path,
    node_manifest_path: Path,
    junit_path: Path,
    shard_dir: Path,
    reason: str,
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    """Record a not-started leaf when the invocation budget is exhausted."""

    row = {
        "shard_id": shard_id,
        "status": "blocked",
        "exit_code": 124,
        "timed_out": False,
        "cleanup_confirmed": True,
        "deadline_exhausted": True,
        "blocker": reason,
        "requested_count": len(shard_nodeids),
        "selected_count": 0,
        "executed_count": 0,
        "projection_count": 0,
        "exact_selection": False,
        "projection": None,
        "request_path": str(request_path),
        "collection_path": str(collection_result_path),
        "node_manifest_path": str(node_manifest_path),
        "junit_path": str(junit_path),
        "stdout_path": str(shard_dir / "stdout.log"),
        "stderr_path": str(shard_dir / "stderr.log"),
    }
    return row, None


def _run_one_shard(
    *,
    root: Path,
    environment: Mapping[str, str],
    shard_index: int,
    shard_nodeids: tuple[str, ...],
    shard_timeout: float,
    deadline: float,
    output_root: Path,
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    """Execute one exact-node leaf under the shared invocation deadline.

    Each leaf owns its request, collection, node-manifest, JUnit, and logs.
    The parent may run these independent leaves concurrently, but this helper
    never retries or re-collects a leaf after its one native invocation.
    """

    shard_id = f"shard-{shard_index + 1:02d}"
    shard_dir = output_root / shard_id
    shard_dir.mkdir(parents=True, exist_ok=True)
    request_path = shard_dir / "requested.json"
    collection_result_path = shard_dir / "collection.json"
    node_manifest_path = shard_dir / "nodeids.json"
    junit_path = shard_dir / "pytest-junit.xml"
    _write_json(
        request_path,
        {
            "schema_version": "flowguard.pytest_shard_request.v1",
            "shard_id": shard_id,
            "nodeids": list(shard_nodeids),
            "inventory_fingerprint": nodeid_fingerprint(shard_nodeids),
        },
    )

    remaining = _deadline_remaining(deadline)
    if remaining <= 0.0:
        return _deadline_blocked_shard_row(
            shard_id=shard_id,
            shard_nodeids=shard_nodeids,
            request_path=request_path,
            collection_result_path=collection_result_path,
            node_manifest_path=node_manifest_path,
            junit_path=junit_path,
            shard_dir=shard_dir,
            reason="pytest invocation absolute deadline exhausted before shard start",
        )

    shard_run = _run_process(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-p",
            "flowguard.pytest_shard_plugin",
            "-p",
            "flowguard.pytest_nodeid_recorder",
            # The finite leaf inventory is passed through the shard request
            # file and FLOWGUARD_PYTEST_SHARD_NODEIDS.  Do not append hundreds
            # of node ids to the Windows command line: that exceeds the
            # platform command-length limit and makes every shard appear to
            # have an unconfirmed cleanup.  The repository-owned plugin
            # performs the exact selection from the immutable request file.
            f"--junit-xml={junit_path.as_posix()}",
        ],
        cwd=root,
        environment={
            **dict(environment),
            "FLOWGUARD_PYTEST_SHARD_NODEIDS": str(request_path),
            "FLOWGUARD_PYTEST_SHARD_COLLECTION": str(collection_result_path),
            "FLOWGUARD_PYTEST_NODEIDS": str(node_manifest_path),
            # The full finite owner needs exact counts and node identity, not
            # an unbounded copy of every exploratory trace.
            "FLOWGUARD_COMPACT_TRACE_STORAGE": "1",
        },
        stdout_path=shard_dir / "stdout.log",
        stderr_path=shard_dir / "stderr.log",
        timeout_seconds=min(float(shard_timeout), remaining),
    )
    shard_collection = _read_object(collection_result_path)
    node_manifest = _read_object(node_manifest_path)
    requested_set = set(shard_nodeids)
    selected_ids = (
        tuple(shard_collection.get("selected_nodeids", ()))
        if shard_collection
        else ()
    )
    executed_ids = tuple(node_manifest.get("nodeids", ())) if node_manifest else ()
    projection = (
        _pytest_junit_projection(
            junit_path,
            nodeid_manifest=node_manifest_path,
            require_exact_nodeids=True,
        )
        if junit_path.is_file()
        else None
    )
    projection_ids = tuple(projection.get("node_ids", ())) if projection else ()
    exact_selection = (
        not (shard_collection or {}).get("selection_error")
        and not (shard_collection or {}).get("unknown_requested_nodeids")
        and set(selected_ids) == requested_set
        and set(executed_ids) == requested_set
        and set(projection_ids) == requested_set
        and len(executed_ids) == len(set(executed_ids))
    )
    parse_ok = projection is not None and exact_selection
    bad_semantics = bool(
        projection
        and (
            int(projection.get("failed", 0) or 0) > 0
            or int(projection.get("errors", 0) or 0) > 0
            or int(projection.get("xpassed", 0) or 0) > 0
        )
    )
    required_skip = bool(
        projection
        and any(
            isinstance(item, Mapping) and item.get("required", True)
            for item in projection.get("skip_details", ())
        )
    )
    if not parse_ok or shard_run["timed_out"] or not shard_run["cleanup_confirmed"]:
        shard_status = "blocked"
    elif shard_run["exit_code"] != 0 or bad_semantics:
        shard_status = "fail"
    elif required_skip:
        shard_status = "partial"
    else:
        shard_status = "pass"
    row = {
        "shard_id": shard_id,
        "status": shard_status,
        "exit_code": shard_run["exit_code"],
        "timed_out": shard_run["timed_out"],
        "cleanup_confirmed": shard_run["cleanup_confirmed"],
        "lingering_killed": shard_run.get("lingering_killed", False),
        "deadline_exhausted": _deadline_remaining(deadline) <= 0.0,
        "requested_count": len(shard_nodeids),
        "selected_count": len(selected_ids),
        "executed_count": len(executed_ids),
        "projection_count": len(projection_ids),
        "exact_selection": exact_selection,
        "projection": dict(projection) if projection else None,
        "request_path": str(request_path),
        "collection_path": str(collection_result_path),
        "node_manifest_path": str(node_manifest_path),
        "junit_path": str(junit_path),
        "stdout_path": str(shard_dir / "stdout.log"),
        "stderr_path": str(shard_dir / "stderr.log"),
    }
    return row, projection if projection is not None and parse_ok else None


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        return 70, _blocked_payload(output_root=root, reason="pytest root is missing or unsafe")
    raw_output = os.environ.get("FLOWGUARD_PYTEST_SHARDS_DIR", "").strip()
    output_root = (
        Path(raw_output).expanduser().resolve()
        if raw_output
        else root / ".flowguard" / "cache" / "pytest-shards" / f"run-{os.getpid()}"
    )
    if output_root.is_symlink():
        return 70, _blocked_payload(output_root=output_root, reason="pytest shard output is a symlink")
    output_root.mkdir(parents=True, exist_ok=True)
    invocation_started = time.monotonic()
    invocation_budget = float(getattr(args, "run_timeout", 3600.0))
    if invocation_budget <= 0.0:
        return 70, _blocked_payload(
            output_root=output_root,
            reason="pytest invocation run-timeout must be positive",
        )
    invocation_deadline = invocation_started + invocation_budget
    environment = dict(os.environ)
    # A shard owner may itself be exercised by a parent pytest process (for
    # example, the closure-regression batch).  Never inherit another owner's
    # recorder/control paths into this run: the child would then look like a
    # collection subprocess to test doubles and could write into the parent's
    # evidence files.  These variables are set deliberately per subprocess
    # below, after this base environment has been sanitized.
    for control_name in (
        "FLOWGUARD_PYTEST_COLLECTION_NODEIDS",
        "FLOWGUARD_PYTEST_SHARD_NODEIDS",
        "FLOWGUARD_PYTEST_SHARD_COLLECTION",
        "FLOWGUARD_PYTEST_NODEIDS",
    ):
        environment.pop(control_name, None)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            # Only the repository-owned shard/recorder plugins are part of the
            # evidence contract.  External auto-loaded plugins can add
            # collection hooks (and scan unrelated workspace artifacts), so
            # disable them for a deterministic bounded inventory.
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": os.pathsep.join(
                item for item in (str(root), environment.get("PYTHONPATH", "")) if item
            ),
        }
    )

    collection_started = time.monotonic()
    collection_path = output_root / "collection.json"
    collection_remaining = _deadline_remaining(invocation_deadline)
    # Monotonic clocks on Windows have finite resolution.  A budget smaller
    # than one clock tick can otherwise round the deadline forward and allow
    # a real collection producer to start even though the caller has already
    # spent the complete invocation budget.
    if invocation_budget < 1e-6 or collection_remaining <= 0.0:
        payload = _blocked_payload(
            output_root=output_root,
            reason="pytest invocation absolute deadline exhausted before collection",
        )
        payload["deadline"] = {
            "budget_seconds": invocation_budget,
            "elapsed_seconds": time.monotonic() - invocation_started,
            "remaining_seconds": 0.0,
        }
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload
    collect_run = _run_process(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "flowguard.pytest_shard_plugin",
        ],
        cwd=root,
        environment={
            **environment,
            "FLOWGUARD_PYTEST_COLLECTION_NODEIDS": str(collection_path),
        },
        stdout_path=output_root / "collection.stdout.log",
        stderr_path=output_root / "collection.stderr.log",
        timeout_seconds=min(float(args.collect_timeout), collection_remaining),
    )
    collection_duration = time.monotonic() - collection_started
    collection = _read_object(collection_path)
    if (
        collection is None
        or collect_run["exit_code"] != 0
        or collect_run["timed_out"]
        or collect_run["cleanup_confirmed"] is not True
        or collection.get("selection_error")
        or collection.get("unknown_requested_nodeids")
    ):
        reason = "pytest collection did not produce a clean terminal inventory"
        if collect_run.get("timed_out"):
            reason = "pytest collection timed out"
        elif collection and collection.get("selection_error"):
            reason = str(collection["selection_error"])
        payload = _blocked_payload(output_root=output_root, reason=reason, collection=collection)
        payload["deadline"] = {
            "budget_seconds": invocation_budget,
            "elapsed_seconds": time.monotonic() - invocation_started,
            "remaining_seconds": _deadline_remaining(invocation_deadline),
        }
        payload["stage_timing"] = {"collection_seconds": collection_duration}
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload

    try:
        collected_nodeids = normalize_nodeids(tuple(collection.get("collected_nodeids", ())))
    except ValueError as exc:
        payload = _blocked_payload(
            output_root=output_root,
            reason=f"pytest collection inventory invalid: {exc}",
            collection=collection,
        )
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload
    if not collected_nodeids:
        payload = _blocked_payload(
            output_root=output_root,
            reason="pytest collection returned no node ids",
            collection=collection,
        )
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload

    nodeids = collected_nodeids
    runnable_nodeids = collected_nodeids

    shards = partition_nodeids(runnable_nodeids, int(args.shards))
    partition_audit = validate_partition(runnable_nodeids, shards)
    if not partition_audit["exact_union"]:
        payload = _blocked_payload(
            output_root=output_root,
            reason="deterministic pytest shard partition is not exact",
            collection=collection,
        )
        payload["partition"] = partition_audit
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload

    shard_stage_started = time.monotonic()
    shard_results: dict[int, tuple[dict[str, Any], Mapping[str, Any] | None]] = {}
    requested_parallelism = int(
        getattr(args, "parallel_shards", len(shards)) or len(shards)
    )
    if requested_parallelism < 1:
        requested_parallelism = 1
    max_parallelism = min(requested_parallelism, len(shards))
    # Shards are independent exact-node leaves.  Start each at most once and
    # collect results by its deterministic index so parallel completion order
    # cannot change the composed evidence.
    pending_shards = [
        (index, tuple(shard_nodeids))
        for index, shard_nodeids in enumerate(shards)
        if index not in shard_results
    ]
    if pending_shards:
        with ThreadPoolExecutor(max_workers=max_parallelism) as executor:
            futures = {
                executor.submit(
                    _run_one_shard,
                    root=root,
                    environment=environment,
                    shard_index=index,
                    shard_nodeids=shard_nodeids,
                    shard_timeout=float(args.shard_timeout),
                    deadline=invocation_deadline,
                    output_root=output_root,
                ): index
                for index, shard_nodeids in pending_shards
            }
            for future, index in futures.items():
                shard_results[index] = future.result()

    shard_rows = [shard_results[index][0] for index in range(len(shards))]
    projections = [
        projection
        for index in range(len(shards))
        if (projection := shard_results[index][1]) is not None
    ]
    shard_duration = time.monotonic() - shard_stage_started

    blockers = [
        f"{row['shard_id']}:{row['status']}"
        for row in shard_rows
        if row["status"] != "pass"
    ]
    aggregation_started = time.monotonic()
    try:
        execution = aggregate_pytest_projections(projections, runnable_nodeids)
        if len(projections) != len(shards):
            raise ValueError("one or more pytest shard projections are unavailable")
    except ValueError as exc:
        execution = {
            "schema_version": "flowguard.pytest_execution.v2",
            "selected": sum(int(row["projection_count"]) for row in shard_rows),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "node_ids": [],
            "optional_metadata_unverified": False,
            "aggregation_error": str(exc),
        }
        blockers.append(f"aggregate:{exc}")
    aggregation_duration = time.monotonic() - aggregation_started
    deadline_expired = _deadline_remaining(invocation_deadline) <= 0.0
    if deadline_expired:
        blockers.append("invocation_absolute_deadline_exhausted")
    status = "pass"
    if any(row["status"] == "blocked" for row in shard_rows):
        status = "blocked"
    elif any(row["status"] == "fail" for row in shard_rows):
        status = "fail"
    elif any(row["status"] == "partial" for row in shard_rows):
        status = "partial"
    if deadline_expired:
        status = "blocked"
    payload = {
        "schema_version": "flowguard.pytest_shard_run.v1",
        "status": status,
        "ok": status == "pass",
        "scope": "full",
        "output_root": str(output_root),
        "collection": dict(collection),
        "collection_run": collect_run,
        "deadline": {
            "budget_seconds": invocation_budget,
            "elapsed_seconds": time.monotonic() - invocation_started,
            "remaining_seconds": _deadline_remaining(invocation_deadline),
            "expired": deadline_expired,
        },
        "stage_timing": {
            "collection_seconds": collection_duration,
            "shards_seconds": shard_duration,
            "aggregation_seconds": aggregation_duration,
        },
        "shard_execution": {
            "requested_parallelism": requested_parallelism,
            "effective_parallelism": max_parallelism,
            "execution_mode": "independent_parallel_leaves",
            "retries": 0,
            "leaf_collections": len(shards),
            "additional_full_collections": 0,
        },
        "planned_count": len(nodeids),
        "executed_count": len(runnable_nodeids),
        "not_run_count": 0,
        "partition": {
            **partition_audit,
            "requested_shard_count": int(args.shards),
            "effective_shard_count": len(shards),
            "algorithm": PARTITION_ALGORITHM,
        },
        "shards": shard_rows,
        "pytest_execution": execution,
        "blockers": blockers,
        "run_id": "pytest-shards:" + nodeid_fingerprint(nodeids).split(":", 1)[1],
    }
    _write_json(output_root / "aggregate.json", payload)
    return (0 if status == "pass" else 1 if status in {"fail", "partial"} else 70), payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    # The collection and all exact-node leaves share one invocation deadline.
    # Leaves are independent and can run concurrently, so the total wall time
    # is bounded by the slowest leaf rather than the sum of four serial caps.
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--collect-timeout", type=float, default=240.0)
    parser.add_argument("--shard-timeout", type=float, default=2400.0)
    parser.add_argument(
        "--run-timeout",
        type=float,
        default=3600.0,
        help="one absolute wall-clock budget for collection, leaves, and aggregation",
    )
    parser.add_argument(
        "--parallel-shards",
        type=int,
        default=4,
        help="maximum number of independent shard leaves running concurrently",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _summary(payload: Mapping[str, Any]) -> str:
    """A few lines for the default output; the full payload needs --json."""
    lines = [f"status: {payload.get('status')}  executed {payload.get('executed_count', 0)}"
             f" of {payload.get('planned_count', 0)}"]
    for shard in payload.get("shards", ()):
        lines.append(f"  {shard.get('shard_id')} {shard.get('status')} exit={shard.get('exit_code')}"
                     f" executed={shard.get('executed_count')}")
    lines += [f"  blocker: {blocker}" for blocker in payload.get("blockers", ())]
    lines.append(f"details: {payload.get('output_root', '')} (full JSON: rerun with --json)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        exit_code, payload = run(args)
    except BaseException as exc:
        payload = _blocked_payload(
            output_root=Path(args.root).expanduser().resolve(),
            reason=f"pytest shard runner internal error: {type(exc).__name__}: {exc}",
        )
        exit_code = 70
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(_summary(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
