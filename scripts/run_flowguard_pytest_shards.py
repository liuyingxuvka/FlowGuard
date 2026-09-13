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


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.pytest_shards import (  # noqa: E402
    PARTITION_ALGORITHM,
    aggregate_pytest_projections,
    nodeid_fingerprint,
    normalize_nodeids,
    partition_nodeids,
    validate_partition,
)
from flowguard.symlink_capability import (  # noqa: E402
    CAPABILITY_PATH_ESCAPE_POSIX,
    CAPABILITY_PATH_ESCAPE_WINDOWS,
    SYMLINK_CAPABILITY_BLOCKER,
    capability_satisfies,
    probe_symlink_capability,
)
from scripts.check_flowguard_skill_suite import _pytest_junit_projection  # noqa: E402


def _probe_symlink_capability() -> dict[str, Any]:
    """Observe filesystem-link capability for the path-sensitive node subset.

    The runner collects first and invokes this probe only when the collection
    explicitly declares a path capability.  It deliberately uses a private
    scratch directory and verifies both the link bit and, on Windows, the
    reparse-point attribute; an MSYS text-link file therefore cannot satisfy a
    Windows reparse requirement.
    """

    return probe_symlink_capability()


def partition_nodeids_by_capability(
    nodeids: tuple[str, ...] | list[str],
    node_capabilities: Mapping[str, Any],
    probe: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Partition collected ids into runnable and typed not-run sets.

    Nodes without an explicit capability are ordinary core nodes.  Capability
    names are never inferred from a filename; an unknown name is a closed
    blocker for that node.  The returned rows are display-safe JSON values and
    keep the full planned denominator separate from the executable subset.
    """

    normalized = normalize_nodeids(tuple(nodeids))
    if not isinstance(node_capabilities, Mapping):
        raise ValueError("pytest collection has no node capability mapping")
    runnable: list[str] = []
    blocked: list[str] = []
    blocked_reasons: dict[str, list[str]] = {}
    required: set[str] = set()
    for nodeid in normalized:
        raw_required = node_capabilities.get(nodeid, ())
        if isinstance(raw_required, str) or not isinstance(raw_required, (list, tuple)):
            blocked.append(nodeid)
            blocked_reasons[nodeid] = ["capability_metadata_invalid"]
            continue
        capabilities = tuple(
            str(item).strip()
            for item in raw_required
            if isinstance(item, str) and str(item).strip()
        )
        if len(capabilities) != len(raw_required):
            blocked.append(nodeid)
            blocked_reasons[nodeid] = ["capability_metadata_invalid"]
            continue
        required.update(capabilities)
        unmet: list[str] = []
        for capability in capabilities:
            if capability not in {
                CAPABILITY_PATH_ESCAPE_POSIX,
                CAPABILITY_PATH_ESCAPE_WINDOWS,
            }:
                unmet.append(f"unknown_capability:{capability}")
            elif probe is None or not capability_satisfies(probe, capability):
                unmet.append(
                    f"{capability}:{str((probe or {}).get('failure_code') or SYMLINK_CAPABILITY_BLOCKER)}"
                )
        if unmet:
            blocked.append(nodeid)
            blocked_reasons[nodeid] = unmet
        else:
            runnable.append(nodeid)
    return {
        "planned_nodeids": list(normalized),
        "runnable_nodeids": runnable,
        "blocked_nodeids": blocked,
        "blocked_reasons": blocked_reasons,
        "required_capabilities": sorted(required),
        "planned_count": len(normalized),
        "runnable_count": len(runnable),
        "not_run_count": len(blocked),
    }


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
    process: subprocess.Popen[str] | None = None
    with stdout_path.open("w", encoding="utf-8", newline="") as stdout, stderr_path.open(
        "w", encoding="utf-8", newline=""
    ) as stderr:
        kwargs: dict[str, Any] = {
            "cwd": cwd,
            "env": dict(environment),
            "stdout": stdout,
            "stderr": stderr,
            "text": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **kwargs)
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Kill the process tree before killing only the direct child.
                # A pytest case can launch a native model runner of its own;
                # killing the parent first makes Windows report it as exited
                # and skips taskkill, leaving that grandchild running outside
                # the bounded owner.  The tree kill is therefore deliberately
                # attempted even when the direct process has already changed
                # state, with process.kill() retained as a portable fallback.
                if os.name == "nt":
                    try:
                        subprocess.run(
                            ("taskkill", "/PID", str(process.pid), "/T", "/F"),
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except OSError:
                        pass
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    process.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    pass
                exit_code = 124
        except (OSError, ValueError) as exc:
            return {
                "exit_code": 70,
                "timed_out": False,
                "cleanup_confirmed": False,
                "launch_error": f"{type(exc).__name__}: {exc}",
                "duration_seconds": time.time() - started,
            }
    cleanup_confirmed = process is not None and process.poll() is not None
    return {
        "exit_code": int(exit_code),
        "timed_out": timed_out,
        "cleanup_confirmed": cleanup_confirmed,
        "launch_error": "" if cleanup_confirmed else "cleanup_unconfirmed",
        "duration_seconds": time.time() - started,
    }


def _blocked_payload(
    *,
    output_root: Path,
    reason: str,
    collection: Mapping[str, Any] | None = None,
    symlink_probe: Mapping[str, Any] | None = None,
    capability_partition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "flowguard.pytest_shard_run.v1",
        "status": "blocked",
        "ok": False,
        "claim_scope": "full",
        "claim_boundary": (
            "The pytest owner is finite and exact-node-id based, but this run "
            "did not produce a complete terminal shard observation."
        ),
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
    if symlink_probe is not None:
        payload["symlink_probe"] = dict(symlink_probe)
    if capability_partition is not None:
        payload["capability_partition"] = dict(capability_partition)
    return payload


def _core_scope_partition(
    nodeids: tuple[str, ...],
    node_capabilities: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a scoped core-only partition without probing platform links.

    Core mode is an explicit local qualification lane.  It executes only
    collected nodes that declare no platform capability and records every
    excluded path-sensitive node and its declared requirements.  The omitted
    denominator stays visible, so this result can never be mistaken for the
    required full platform qualification.
    """

    runnable: list[str] = []
    excluded: list[str] = []
    excluded_reasons: dict[str, list[str]] = {}
    for nodeid in nodeids:
        raw_required = node_capabilities.get(nodeid, ())
        if isinstance(raw_required, str) or not isinstance(raw_required, (list, tuple)):
            excluded.append(nodeid)
            excluded_reasons[nodeid] = ["capability_metadata_invalid"]
            continue
        capabilities = tuple(
            str(item).strip()
            for item in raw_required
            if isinstance(item, str) and str(item).strip()
        )
        if len(capabilities) != len(raw_required):
            excluded.append(nodeid)
            excluded_reasons[nodeid] = ["capability_metadata_invalid"]
        elif capabilities:
            excluded.append(nodeid)
            excluded_reasons[nodeid] = [
                "core_scope_excluded:" + capability for capability in capabilities
            ]
        else:
            runnable.append(nodeid)
    return {
        "claim_scope": "scoped-core",
        "source_planned_nodeids": list(nodeids),
        "planned_nodeids": runnable,
        "runnable_nodeids": runnable,
        "blocked_nodeids": [],
        "blocked_reasons": {},
        "excluded_nodeids": excluded,
        "excluded_reasons": excluded_reasons,
        "required_capabilities": [],
        "source_planned_count": len(nodeids),
        "planned_count": len(runnable),
        "runnable_count": len(runnable),
        "not_run_count": 0,
        "excluded_count": len(excluded),
    }


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


def _resume_one_shard(
    *,
    resume_root: Path,
    shard_id: str,
    shard_nodeids: tuple[str, ...],
    prior_row: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], Mapping[str, Any] | None] | None:
    """Reuse one exact terminal shard from an explicitly supplied run.

    Resumption is deliberately opt-in and exact.  The prior request must
    name the same shard inventory, and its immutable collection/node-manifest
    and JUnit projection must still prove that every requested node ran.  A
    blocked, incomplete, or mismatched shard is returned to the one native
    invocation path; this helper never retries a leaf or guesses from counts.
    """

    # Only an immutable terminal *pass* can be reused.  A failed or partial
    # shard has concrete artefacts, but those artefacts are evidence of an
    # unsuccessful producer and must return to the one native invocation
    # path.  Treating them as reusable would make a final parent appear to
    # resume successfully while never rerunning the failed tests.
    if prior_row is None or prior_row.get("status") != "pass":
        return None
    if prior_row.get("exact_selection") is not True:
        return None
    shard_dir = resume_root / shard_id
    request_path = shard_dir / "requested.json"
    collection_path = shard_dir / "collection.json"
    node_manifest_path = shard_dir / "nodeids.json"
    junit_path = shard_dir / "pytest-junit.xml"
    request = _read_object(request_path)
    expected_fingerprint = nodeid_fingerprint(shard_nodeids)
    if request is None:
        return None
    if (
        request.get("schema_version") != "flowguard.pytest_shard_request.v1"
        or request.get("shard_id") != shard_id
        or tuple(request.get("nodeids", ())) != tuple(shard_nodeids)
        or request.get("inventory_fingerprint") != expected_fingerprint
    ):
        return None
    collection = _read_object(collection_path)
    node_manifest = _read_object(node_manifest_path)
    if collection is None or node_manifest is None or junit_path.is_symlink() or not junit_path.is_file():
        return None
    selected_ids = tuple(collection.get("selected_nodeids", ()))
    executed_ids = tuple(node_manifest.get("nodeids", ()))
    projection = _pytest_junit_projection(
        junit_path,
        nodeid_manifest=node_manifest_path,
        require_exact_nodeids=True,
    )
    projection_ids = tuple(projection.get("node_ids", ())) if projection else ()
    if (
        projection is None
        or set(selected_ids) != set(shard_nodeids)
        or set(executed_ids) != set(shard_nodeids)
        or set(projection_ids) != set(shard_nodeids)
        or len(executed_ids) != len(set(executed_ids))
    ):
        return None
    row = dict(prior_row)
    row.update(
        {
            "request_path": str(request_path),
            "collection_path": str(collection_path),
            "node_manifest_path": str(node_manifest_path),
            "junit_path": str(junit_path),
            "reused": True,
            "resume_source": str(resume_root),
        }
    )
    return row, projection


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
        else root / "work" / "flowguard" / "pytest-shards" / f"run-{os.getpid()}"
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
    if collection_remaining <= 0.0:
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

    raw_capabilities = collection.get("node_capabilities")
    raw_capability_errors = collection.get("capability_errors", {})
    if not isinstance(raw_capabilities, Mapping) or not isinstance(
        raw_capability_errors, Mapping
    ):
        payload = _blocked_payload(
            output_root=output_root,
            reason="pytest collection has no valid capability metadata",
            collection=collection,
        )
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload
    capability_errors = {
        str(nodeid): str(reason)
        for nodeid, reason in raw_capability_errors.items()
        if str(nodeid).strip() and str(reason).strip()
    }
    missing_capability_rows = sorted(
        nodeid for nodeid in collected_nodeids if nodeid not in raw_capabilities
    )
    if capability_errors or missing_capability_rows:
        reasons = {
            **capability_errors,
            **{
                nodeid: "capability_metadata_missing"
                for nodeid in missing_capability_rows
            },
        }
        capability_partition = {
            "planned_nodeids": list(collected_nodeids),
            "runnable_nodeids": [],
            "blocked_nodeids": list(nodeids),
            "blocked_reasons": reasons,
            "required_capabilities": [],
            "planned_count": len(collected_nodeids),
            "runnable_count": 0,
            "not_run_count": len(collected_nodeids),
        }
        payload = _blocked_payload(
            output_root=output_root,
            reason="pytest collection capability metadata is invalid",
            collection=collection,
            capability_partition=capability_partition,
        )
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload

    capability_scope = str(getattr(args, "capability_scope", "full") or "full").strip()
    if capability_scope == "core":
        capability_partition = _core_scope_partition(collected_nodeids, raw_capabilities)
        nodeids = tuple(capability_partition["runnable_nodeids"])
        symlink_probe = None
    else:
        nodeids = collected_nodeids
        required_capabilities = {
            str(capability).strip()
            for values in raw_capabilities.values()
            if isinstance(values, (list, tuple))
            for capability in values
            if isinstance(capability, str) and capability.strip()
        }
        symlink_probe = (
            _probe_symlink_capability() if required_capabilities else None
        )
        try:
            capability_partition = partition_nodeids_by_capability(
                nodeids,
                raw_capabilities,
                symlink_probe,
            )
        except ValueError as exc:
            payload = _blocked_payload(
                output_root=output_root,
                reason=f"pytest capability partition is invalid: {exc}",
                collection=collection,
                symlink_probe=symlink_probe,
            )
            _write_json(output_root / "aggregate.json", payload)
            return 70, payload

    runnable_nodeids = tuple(capability_partition["runnable_nodeids"])
    blocked_nodeids = tuple(capability_partition["blocked_nodeids"])
    if not runnable_nodeids:
        payload = _blocked_payload(
            output_root=output_root,
            reason=(
                SYMLINK_CAPABILITY_BLOCKER
                if blocked_nodeids
                else "pytest capability partition returned no runnable node ids"
            ),
            collection=collection,
            symlink_probe=symlink_probe,
            capability_partition=capability_partition,
        )
        payload["planned_count"] = len(nodeids)
        payload["executed_count"] = 0
        payload["not_run_count"] = len(blocked_nodeids)
        _write_json(output_root / "aggregate.json", payload)
        return 70, payload

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
    resume_root_value = str(getattr(args, "resume_output", "") or "").strip()
    resume_root = Path(resume_root_value).expanduser().resolve() if resume_root_value else None
    prior_rows: dict[str, Mapping[str, Any]] = {}
    resumed_count = 0
    resume_disposition = ""
    if resume_root is not None:
        if resume_root.is_symlink() or not resume_root.is_dir():
            payload = _blocked_payload(
                output_root=output_root,
                reason="explicit pytest resume output is missing or unsafe",
                collection=collection,
                capability_partition=capability_partition,
            )
            _write_json(output_root / "aggregate.json", payload)
            return 70, payload
        prior_aggregate = _read_object(resume_root / "aggregate.json")
        prior_partition = (
            prior_aggregate.get("partition", {})
            if prior_aggregate is not None
            else {}
        )
        if (
            not isinstance(prior_partition, Mapping)
            or prior_partition.get("inventory_fingerprint")
            != nodeid_fingerprint(runnable_nodeids)
            or int(prior_partition.get("effective_shard_count", 0) or 0)
            != len(shards)
        ):
            # A source change can legitimately alter the exact collected
            # inventory (for example, adding one regression test).  The old
            # run is then not reusable, but it is not a reason to block the
            # current finite invocation: discard the stale resume inventory
            # and execute the current shards once through the native path.
            resume_disposition = "discarded_mismatched_inventory"
            resume_root = None
        else:
            for raw_row in prior_aggregate.get("shards", ()) if prior_aggregate else ():
                if isinstance(raw_row, Mapping) and str(raw_row.get("shard_id", "")).strip():
                    prior_rows[str(raw_row["shard_id"])] = raw_row
            for index, shard_nodeids in enumerate(shards):
                shard_id = f"shard-{index + 1:02d}"
                resumed = _resume_one_shard(
                    resume_root=resume_root,
                    shard_id=shard_id,
                    shard_nodeids=tuple(shard_nodeids),
                    prior_row=prior_rows.get(shard_id),
                )
                if resumed is not None:
                    shard_results[index] = resumed
                    resumed_count += 1
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
    if blocked_nodeids:
        status = "blocked"
    if deadline_expired:
        status = "blocked"
    payload = {
        "schema_version": "flowguard.pytest_shard_run.v1",
        "status": status,
        "ok": status == "pass",
        "claim_scope": "scoped-core" if capability_scope == "core" else "full",
        "claim_boundary": (
            "This owner executes one exact collected pytest inventory through a "
            "fixed finite node-id partition. It does not prove tests outside "
            "that collection or external release/install parity."
        ),
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
            "resumed_shards": resumed_count,
            "resume_source": str(resume_root) if resume_root is not None else "",
            "resume_disposition": resume_disposition,
            "leaf_collections": len(shards),
            "additional_full_collections": 0,
        },
        "capability_partition": capability_partition,
        "symlink_probe": dict(symlink_probe) if symlink_probe is not None else None,
        "planned_count": len(nodeids),
        "executed_count": len(runnable_nodeids),
        "not_run_count": len(blocked_nodeids),
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
    parser.add_argument(
        "--capability-scope",
        choices=("core", "full"),
        default="full",
        help=(
            "qualify only non-platform core nodes, or require every collected "
            "platform capability (default: full)"
        ),
    )
    parser.add_argument(
        "--resume-output",
        default="",
        help=(
            "explicit prior pytest-shards directory whose exact terminal "
            "shards may be reused; incomplete or mismatched leaves run once"
        ),
    )
    parser.add_argument("--json", action="store_true")
    return parser


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
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
