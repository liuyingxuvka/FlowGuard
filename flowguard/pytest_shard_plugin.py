"""Pytest collection selector/receipt plugin used by the finite shard runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .symlink_capability import SYMLINK_CAPABILITY_IDS


CAPABILITY_MARKER = "flowguard_capability"


def _item_capabilities(item: Any) -> tuple[tuple[str, ...], str]:
    """Read explicit capability markers without guessing from node names."""

    values: list[str] = []
    for marker in item.iter_markers(name=CAPABILITY_MARKER):
        if len(marker.args) != 1 or not isinstance(marker.args[0], str):
            return (), "capability_marker_requires_one_string"
        capability = marker.args[0].strip()
        if capability not in SYMLINK_CAPABILITY_IDS:
            return (), f"unknown_capability:{capability}"
        values.append(capability)
    return tuple(sorted(set(values))), ""


def pytest_configure(config: Any) -> None:
    config.addinivalue_line(
        "markers",
        "flowguard_capability(name): declare a platform capability required by a node",
    )


def _safe_target(raw: str) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    target = Path(text).expanduser().resolve()
    if target.is_symlink():
        return None
    return target


def _read_requested(path: Path | None) -> tuple[tuple[str, ...], str]:
    if path is None:
        return (), ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return (), f"selection_manifest_invalid:{type(exc).__name__}"
    if not isinstance(payload, Mapping) or not isinstance(payload.get("nodeids"), list):
        return (), "selection_manifest_invalid_shape"
    raw = payload["nodeids"]
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        return (), "selection_manifest_contains_empty_id"
    values = tuple(item.strip() for item in raw)
    if len(set(values)) != len(values):
        return (), "selection_manifest_contains_duplicate_id"
    return values, ""


def _write(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        return
    if path.exists() and path.is_symlink():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def pytest_collection_modifyitems(session: Any, config: Any, items: list[Any]) -> None:
    collected = tuple(
        str(getattr(item, "nodeid", "")).strip()
        for item in items
        if str(getattr(item, "nodeid", "")).strip()
    )
    selection_path = _safe_target(os.environ.get("FLOWGUARD_PYTEST_SHARD_NODEIDS", ""))
    requested, selection_error = _read_requested(selection_path)
    selected = collected
    unknown: tuple[str, ...] = ()
    if selection_path is not None and not selection_error:
        requested_set = set(requested)
        collected_set = set(collected)
        unknown = tuple(sorted(requested_set - collected_set))
        selected = tuple(nodeid for nodeid in collected if nodeid in requested_set)
        deselected = [item for item in items if str(getattr(item, "nodeid", "")).strip() not in requested_set]
        if deselected:
            config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item not in deselected]
    node_capabilities: dict[str, list[str]] = {}
    capability_errors: dict[str, str] = {}
    for item in items:
        nodeid = str(getattr(item, "nodeid", "")).strip()
        if not nodeid:
            continue
        capabilities, error = _item_capabilities(item)
        node_capabilities[nodeid] = list(capabilities)
        if error:
            capability_errors[nodeid] = error
    config._flowguard_collection_payload = {
        "schema_version": "flowguard.pytest_collection.v1",
        "collected_nodeids": list(collected),
        "selected_nodeids": list(selected),
        "requested_nodeids": list(requested),
        "unknown_requested_nodeids": list(unknown),
        "selection_error": selection_error,
        "node_capabilities": node_capabilities,
        "capability_errors": capability_errors,
        "exit_status": None,
    }


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    payload = dict(
        getattr(
            session.config,
            "_flowguard_collection_payload",
            {
                "schema_version": "flowguard.pytest_collection.v1",
                "collected_nodeids": [],
                "selected_nodeids": [],
                "requested_nodeids": [],
                "unknown_requested_nodeids": [],
                "selection_error": "collection_hook_not_called",
                "node_capabilities": {},
                "capability_errors": {},
            },
        )
    )
    payload["exit_status"] = int(exitstatus)
    collect_target = _safe_target(
        os.environ.get("FLOWGUARD_PYTEST_COLLECTION_NODEIDS", "")
    )
    shard_target = _safe_target(
        os.environ.get("FLOWGUARD_PYTEST_SHARD_COLLECTION", "")
    )
    _write(collect_target or shard_target, payload)


__all__ = ["pytest_collection_modifyitems", "pytest_sessionfinish"]
