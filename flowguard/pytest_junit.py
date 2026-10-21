"""Stdlib JUnit projection for exact pytest node-id evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
import xml.etree.ElementTree as ET


def pytest_junit_projection(
    path: Path,
    *,
    nodeid_manifest: Path | None = None,
    require_exact_nodeids: bool = False,
) -> dict[str, Any] | None:
    """Read one run-local pytest JUnit report into bounded native evidence.

    The report is produced by pytest itself through ``PYTEST_ADDOPTS`` in
    ``_run_full_child``.  We retain exact testcase identities and skip reasons
    so the parent can project the child's real skips instead of manufacturing
    an empty ``skipped_checks`` list.  JUnit does not standardise node-id
    attributes.  Governed full runs therefore provide an exact node-id
    collection from a run-local recorder; the direct helper keeps its
    historical classname/name fallback unless ``require_exact_nodeids`` is
    requested.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    root_tag = root.tag.rsplit("}", 1)[-1]
    if root_tag not in {"testsuite", "testsuites"}:
        return None
    cases = tuple(root.iter("testcase"))
    recorded_nodeids: tuple[str, ...] = ()
    if nodeid_manifest is not None:
        if nodeid_manifest.is_symlink() or not nodeid_manifest.is_file():
            return None
        try:
            manifest_payload = json.loads(nodeid_manifest.read_text(encoding="utf-8"))
            if not isinstance(manifest_payload, Mapping):
                return None
            raw_nodeids = manifest_payload.get("nodeids")
            if not isinstance(raw_nodeids, list) or not raw_nodeids:
                return None
            recorded_nodeids = tuple(
                item.strip()
                for item in raw_nodeids
                if isinstance(item, str) and item.strip()
            )
            if len(recorded_nodeids) != len(raw_nodeids) or len(set(recorded_nodeids)) != len(recorded_nodeids):
                return None
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
    elif require_exact_nodeids:
        return None
    if not cases:
        try:
            declared_tests = root.attrib.get("tests")
            if declared_tests is not None and int(declared_tests) != 0:
                return None
        except (TypeError, ValueError):
            return None
        # An empty collection is still a meaningful producer result.  Keep the
        # zero counters explicit; the normal pytest exit/status checks decide
        # whether an empty suite is acceptable for the owner.
        return {
            "schema_version": "flowguard.pytest_execution.v1",
            "selected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "node_ids": [],
            "node_statuses": {},
            "optional_metadata_unverified": False,
        }

    passed = failed = errors = skipped = xfailed = xpassed = 0
    skip_details: list[dict[str, Any]] = []
    optional_metadata_unverified = False
    node_ids: set[str] = set()
    ordered_node_ids: list[str] = []
    node_statuses: dict[str, str] = {}
    if recorded_nodeids and len(recorded_nodeids) != len(cases):
        return None
    for index, case in enumerate(cases):
        explicit_node_id = next(
            (
                str(case.attrib.get(name, "")).strip()
                for name in ("nodeid", "node_id", "pytest_nodeid")
                if str(case.attrib.get(name, "")).strip()
            ),
            "",
        )
        classname = str(case.attrib.get("classname", "")).strip()
        name = str(case.attrib.get("name", "")).strip()
        node_id = explicit_node_id
        if not node_id and recorded_nodeids:
            # The recorder's report order is the exact execution order.  No
            # classname/name reconstruction is used for a governed run.
            node_id = recorded_nodeids[index]
        if not node_id and not require_exact_nodeids:
            node_id = f"{classname}::{name}" if classname and name else name or classname
        # A generated placeholder cannot be joined to the static inventory;
        # reject it instead of guessing a node id.
        if not node_id or node_id in node_ids:
            return None
        node_ids.add(node_id)
        ordered_node_ids.append(node_id)
        outcome_children = [
            child
            for child in case
            if child.tag.rsplit("}", 1)[-1] in {"failure", "error", "skipped"}
        ]
        if len(outcome_children) > 1:
            return None
        child = outcome_children[0] if outcome_children else None
        tag = child.tag.rsplit("}", 1)[-1] if child is not None else ""
        child_type = str(child.attrib.get("type", "")) if child is not None else ""
        child_message = str(child.attrib.get("message", "")) if child is not None else ""
        child_text = (child.text or "").strip() if child is not None else ""
        marker_text = " ".join((tag, child_type, child_message, child_text)).lower()
        if tag == "skipped":
            if "xfail" in marker_text:
                xfailed += 1
                node_statuses[node_id] = "xfailed"
            else:
                skipped += 1
                node_statuses[node_id] = "skipped"
                reason = child_message or child_text or "pytest skipped this node"
                required_value = str(child.attrib.get("required", "")).strip().lower() if child is not None else ""
                optional_value = str(child.attrib.get("optional", "")).strip().lower() if child is not None else ""
                # Native pytest has no governed required/optional vocabulary.
                # Preserve an annotation for diagnosis, but mark it
                # unverified: only an independent current TestMesh disposition
                # may waive a required owner case.
                if required_value or optional_value:
                    optional_metadata_unverified = True
                required = not (
                    required_value in {"0", "false", "no", "optional"}
                    or optional_value in {"1", "true", "yes"}
                )
                skip_details.append(
                    {
                        "node_id": node_id,
                        "reason": reason,
                        "required": required,
                        "impact": "pytest node was not executed",
                        "owner_id": "pytest",
                        "claim_boundary": "Pytest child evidence only; broad closure requires zero required skips.",
                    }
                )
        elif tag == "failure":
            if "xpass" in marker_text:
                xpassed += 1
                node_statuses[node_id] = "xpassed"
            else:
                failed += 1
                node_statuses[node_id] = "failed"
        elif tag == "error":
            errors += 1
            node_statuses[node_id] = "error"
        else:
            passed += 1
            node_statuses[node_id] = "passed"

    # Testcase outcomes are concrete evidence. Pytest's aggregate "tests"
    # counter may additionally count subtests, so it cannot be an identity gate.
    return {
        "schema_version": "flowguard.pytest_execution.v1",
        "selected": len(cases),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "skip_details": skip_details,
        "node_ids": ordered_node_ids,
        "node_statuses": node_statuses,
        "optional_metadata_unverified": optional_metadata_unverified,
    }



_pytest_junit_projection = pytest_junit_projection
