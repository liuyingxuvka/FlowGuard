"""Bounded, explicit lifecycle primitives for retained FlowGuard evidence.

Validation owns evidence production.  This module owns storage identity,
reachability, quarantine, and purge mechanics; it never decides whether a
target-owned check passed.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


OBJECT_SCHEMA = "flowguard.evidence_object.v1"
RUN_SCHEMA = "flowguard.evidence_run.v1"
HEAD_SCHEMA = "flowguard.evidence_current_head.v1"
PINS_SCHEMA = "flowguard.evidence_pins.v1"
AUDIT_SCHEMA = "flowguard.evidence_audit.v1"
GC_PLAN_SCHEMA = "flowguard.evidence_gc_plan.v1"
GC_RECEIPT_SCHEMA = "flowguard.evidence_gc_receipt.v1"
TAIL_CHAR_LIMIT = 4000


class EvidenceLifecycleError(ValueError):
    """Raised when evidence identity or lifecycle authority is invalid."""


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _extended_windows_path(path: Path) -> str:
    value = str(path.resolve())
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value.lstrip("\\")
    return "\\\\?\\" + value


def _remove_tree_exact(path: Path) -> None:
    """Remove one already-contained tree, including Windows paths over MAX_PATH."""

    shutil.rmtree(_extended_windows_path(path))


def write_json_atomic(path: str | Path, payload: Mapping[str, Any]) -> None:
    _atomic_write(Path(path), json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def fingerprint_payload(payload: Mapping[str, Any] | None) -> str:
    return _sha256_bytes(_canonical_bytes(dict(payload or {})))


def _gzip_deterministic(data: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(data)
    return buffer.getvalue()


def store_text_object(
    run_dir: str | Path,
    text: str,
    *,
    media_type: str = "text/plain; charset=utf-8",
    tail_chars: int = TAIL_CHAR_LIMIT,
) -> dict[str, Any]:
    """Store one complete UTF-8 stream once and return its bounded descriptor."""

    run_path = Path(run_dir).resolve()
    logical = text.encode("utf-8")
    logical_sha = _sha256_bytes(logical)
    compressed = _gzip_deterministic(logical)
    digest = logical_sha.removeprefix("sha256:")
    object_path = run_path / "objects" / "sha256" / f"{digest}.txt.gz"
    if object_path.is_file():
        if object_path.read_bytes() != compressed:
            raise EvidenceLifecycleError(f"stored object conflicts with logical identity: {logical_sha}")
    else:
        _atomic_write(object_path, compressed)
    return {
        "schema_version": OBJECT_SCHEMA,
        "logical_sha256": logical_sha,
        "logical_bytes": len(logical),
        "storage_sha256": _sha256_bytes(compressed),
        "storage_bytes": len(compressed),
        "compression": "gzip",
        "encoding": "utf-8",
        "media_type": media_type,
        "object_path": object_path.relative_to(run_path).as_posix(),
        "diagnostic_tail": text[-max(0, tail_chars) :] if tail_chars else "",
        "diagnostic_truncated": len(text) > max(0, tail_chars),
    }


def resolve_object_path(run_dir: str | Path, descriptor: Mapping[str, Any]) -> Path:
    run_path = Path(run_dir).resolve()
    candidate = (run_path / str(descriptor.get("object_path", ""))).resolve()
    if run_path != candidate and run_path not in candidate.parents:
        raise EvidenceLifecycleError("evidence object escapes its run directory")
    return candidate


def verify_text_object(run_dir: str | Path, descriptor: Mapping[str, Any]) -> bool:
    try:
        path = resolve_object_path(run_dir, descriptor)
        stored = path.read_bytes()
        if _sha256_bytes(stored) != descriptor.get("storage_sha256"):
            return False
        logical = gzip.decompress(stored)
        return (
            _sha256_bytes(logical) == descriptor.get("logical_sha256")
            and len(logical) == descriptor.get("logical_bytes")
            and len(stored) == descriptor.get("storage_bytes")
        )
    except (OSError, EOFError, gzip.BadGzipFile, EvidenceLifecycleError):
        return False


def default_run_directory(root: str | Path, scope: str) -> Path:
    base = Path(root).resolve() / ".flowguard" / "evidence" / scope
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return base / f"{stamp}-{uuid.uuid4().hex[:8]}"


def ensure_new_run_directory(run_dir: str | Path) -> Path:
    """Create one empty run directory and reject accidental evidence reuse."""

    run_path = Path(run_dir).resolve()
    if run_path.exists() and any(run_path.iterdir()):
        raise EvidenceLifecycleError(f"evidence run directory is not empty: {run_path}")
    run_path.mkdir(parents=True, exist_ok=True)
    return run_path


def publish_run(
    run_dir: str | Path,
    *,
    kind: str,
    status: str,
    result_path: str | Path,
    started_at_epoch: float = 0.0,
    finished_at_epoch: float | None = None,
    update_head: bool = True,
) -> dict[str, Any]:
    """Publish an immutable run manifest, then atomically advance its scope head."""

    run_path = Path(run_dir).resolve()
    result = Path(result_path).resolve()
    if run_path not in result.parents:
        raise EvidenceLifecycleError("terminal result must be inside the evidence run")
    if not result.is_file():
        raise EvidenceLifecycleError(f"terminal result is missing: {result}")
    result_sha = _sha256_file(result)
    manifest_body = {
        "schema_version": RUN_SCHEMA,
        "kind": str(kind),
        "status": str(status),
        "terminal": True,
        "started_at_epoch": float(started_at_epoch),
        "finished_at_epoch": float(finished_at_epoch if finished_at_epoch is not None else time.time()),
        "result_path": result.relative_to(run_path).as_posix(),
        "result_sha256": result_sha,
        "claim_boundary": "This manifest identifies one retained terminal run; target-owned result semantics remain in the referenced result.",
    }
    run_id = _sha256_bytes(_canonical_bytes(manifest_body))
    manifest = {**manifest_body, "run_id": run_id}
    manifest_path = run_path / "evidence-run.json"
    if manifest_path.exists():
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
        if current != manifest:
            raise EvidenceLifecycleError("immutable evidence-run manifest already exists with different content")
    else:
        write_json_atomic(manifest_path, manifest)
    manifest_sha = _sha256_file(manifest_path)
    if update_head:
        scope_root = run_path.parent
        head = {
            "schema_version": HEAD_SCHEMA,
            "scope": scope_root.name,
            "run_path": run_path.relative_to(scope_root).as_posix(),
            "run_id": run_id,
            "manifest_sha256": manifest_sha,
            "result_sha256": result_sha,
            "status": str(status),
            "updated_at_epoch": time.time(),
        }
        write_json_atomic(scope_root / "CURRENT.json", head)
    return {**manifest, "manifest_path": str(manifest_path), "manifest_sha256": manifest_sha}


def _path_within(root: Path, value: Path) -> bool:
    resolved = value.resolve()
    return resolved == root or root in resolved.parents


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceLifecycleError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise EvidenceLifecycleError(f"expected JSON object: {path}")
    return value


def _directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _directory_fingerprint(path: Path) -> str:
    rows: list[tuple[str, int, str]] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        rows.append((relative, item.stat().st_size, _sha256_file(item)))
    return _sha256_bytes(_canonical_bytes({"files": rows}))


def _head_targets(root: Path) -> tuple[dict[str, Any], set[Path], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    targets: set[Path] = set()
    findings: list[dict[str, str]] = []
    for path in sorted(root.rglob("CURRENT.json")):
        if ".quarantine" in path.parts:
            continue
        try:
            payload = _load_json(path)
            if payload.get("schema_version") != HEAD_SCHEMA:
                raise EvidenceLifecycleError("unsupported current-head schema")
            target = (path.parent / str(payload.get("run_path", ""))).resolve()
            if not _path_within(root, target):
                raise EvidenceLifecycleError("current-head target escapes evidence root")
            manifest_path = target / "evidence-run.json"
            if _sha256_file(manifest_path) != payload.get("manifest_sha256"):
                raise EvidenceLifecycleError("current-head manifest fingerprint mismatch")
            manifest = _load_json(manifest_path)
            result_path = target / str(manifest.get("result_path", ""))
            if _sha256_file(result_path) != payload.get("result_sha256"):
                raise EvidenceLifecycleError("current-head result fingerprint mismatch")
            targets.add(target)
            rows.append({"head_path": path.relative_to(root).as_posix(), "target_path": target.relative_to(root).as_posix(), **dict(payload)})
        except (EvidenceLifecycleError, OSError) as exc:
            findings.append({"code": "invalid_current_head", "path": path.relative_to(root).as_posix(), "message": str(exc)})
    return tuple(rows), targets, findings


def _pin_targets(root: Path) -> tuple[dict[str, Any], set[Path], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    targets: set[Path] = set()
    findings: list[dict[str, str]] = []
    for path in sorted(root.rglob("PINS.json")):
        if ".quarantine" in path.parts:
            continue
        try:
            payload = _load_json(path)
            if payload.get("schema_version") != PINS_SCHEMA:
                raise EvidenceLifecycleError("unsupported pins schema")
            pins = payload.get("pins", ())
            if not isinstance(pins, Sequence) or isinstance(pins, (str, bytes)):
                raise EvidenceLifecycleError("pins must be a list")
            for pin in pins:
                if not isinstance(pin, Mapping):
                    raise EvidenceLifecycleError("pin must be an object")
                target = (path.parent / str(pin.get("run_path", ""))).resolve()
                if not _path_within(root, target):
                    raise EvidenceLifecycleError("pin target escapes evidence root")
                manifest = _load_json(target / "evidence-run.json")
                if manifest.get("run_id") != pin.get("run_id"):
                    raise EvidenceLifecycleError("pin run identity mismatch")
                targets.add(target)
                rows.append({"pins_path": path.relative_to(root).as_posix(), "target_path": target.relative_to(root).as_posix(), **dict(pin)})
        except (EvidenceLifecycleError, OSError) as exc:
            findings.append({"code": "invalid_pin", "path": path.relative_to(root).as_posix(), "message": str(exc)})
    return tuple(rows), targets, findings


def _unmanaged_partition_roots(root: Path, managed_dirs: set[Path]) -> list[Path]:
    """Partition every non-managed evidence directory into disjoint legacy roots."""

    roots: list[Path] = []

    def visit(candidate: Path) -> None:
        resolved = candidate.resolve()
        if candidate.name == ".quarantine":
            return
        if resolved in managed_dirs or any(parent in managed_dirs for parent in resolved.parents):
            return
        if any(resolved in managed.parents for managed in managed_dirs):
            for child in sorted(candidate.iterdir()):
                if child.is_dir():
                    visit(child)
            return
        roots.append(resolved)

    for child in sorted(root.iterdir()):
        if child.is_dir():
            visit(child)
    return roots


def audit_evidence(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.exists():
        return {
            "schema_version": AUDIT_SCHEMA,
            "status": "pass",
            "root": str(root_path),
            "runs": [],
            "heads": [],
            "pins": [],
            "findings": [],
            "counts": {"current": 0, "pinned": 0, "collectible": 0, "legacy_unmanaged": 0, "invalid": 0, "quarantined": 0},
            "logical_bytes": 0,
            "stored_bytes": 0,
        }
    heads, head_targets, findings = _head_targets(root_path)
    pins, pin_targets, pin_findings = _pin_targets(root_path)
    findings.extend(pin_findings)
    rows: list[dict[str, Any]] = []
    managed_dirs: set[Path] = set()
    for manifest_path in sorted(root_path.rglob("evidence-run.json")):
        if ".quarantine" in manifest_path.parts:
            continue
        run_path = manifest_path.parent.resolve()
        managed_dirs.add(run_path)
        classification = "collectible"
        valid = True
        message = ""
        try:
            manifest = _load_json(manifest_path)
            if manifest.get("schema_version") != RUN_SCHEMA or not manifest.get("terminal"):
                raise EvidenceLifecycleError("invalid or non-terminal run manifest")
            result = run_path / str(manifest.get("result_path", ""))
            if _sha256_file(result) != manifest.get("result_sha256"):
                raise EvidenceLifecycleError("run result fingerprint mismatch")
            if run_path in head_targets:
                classification = "current"
            elif run_path in pin_targets:
                classification = "pinned"
        except (EvidenceLifecycleError, OSError) as exc:
            manifest = {}
            valid = False
            classification = "invalid"
            message = str(exc)
            findings.append({"code": "invalid_run", "path": run_path.relative_to(root_path).as_posix(), "message": message})
        rows.append(
            {
                "path": run_path.relative_to(root_path).as_posix(),
                "classification": classification,
                "valid": valid,
                "run_id": str(manifest.get("run_id", "")),
                "kind": str(manifest.get("kind", "")),
                "status": str(manifest.get("status", "")),
                "finished_at_epoch": float(manifest.get("finished_at_epoch", 0.0) or 0.0),
                "stored_bytes": _directory_size(run_path),
                "fingerprint": _directory_fingerprint(run_path),
                "message": message,
            }
        )
    for run_path in _unmanaged_partition_roots(root_path, managed_dirs):
        rows.append(
            {
                "path": run_path.relative_to(root_path).as_posix(),
                "classification": "legacy_unmanaged",
                "valid": True,
                "run_id": "",
                "kind": "legacy",
                "status": "historical",
                "finished_at_epoch": run_path.stat().st_mtime,
                "stored_bytes": _directory_size(run_path),
                "fingerprint": _directory_fingerprint(run_path),
                "message": "Lifecycle-unmanaged evidence is historical by default; preserve it explicitly when another current authority still binds it.",
            }
        )
    quarantined = 0
    quarantine_root = root_path / ".quarantine"
    if quarantine_root.is_dir():
        quarantined = sum(1 for path in quarantine_root.iterdir() if path.is_dir() and path.name != "receipts")
    counts = {name: sum(row["classification"] == name for row in rows) for name in ("current", "pinned", "collectible", "legacy_unmanaged", "invalid")}
    counts["quarantined"] = quarantined
    stored = 0
    for item in root_path.rglob("*"):
        if ".quarantine" in item.parts:
            continue
        try:
            if item.is_file():
                stored += item.stat().st_size
        except OSError:
            continue
    object_logical: dict[str, int] = {}
    for descriptor_path in root_path.rglob("result.json"):
        if ".quarantine" in descriptor_path.parts:
            continue
        try:
            payload = _load_json(descriptor_path)
        except EvidenceLifecycleError:
            continue
        for key in ("stdout", "stderr"):
            descriptor = payload.get(key)
            if isinstance(descriptor, Mapping) and descriptor.get("schema_version") == OBJECT_SCHEMA:
                object_logical[str(descriptor.get("logical_sha256", ""))] = int(descriptor.get("logical_bytes", 0) or 0)
    classified_roots = _without_descendant_candidates(rows)
    classified_paths = [(root_path / str(row["path"])).resolve() for row in classified_roots]
    control_paths = {
        (root_path / str(row["head_path"])).resolve() for row in heads
    } | {
        (root_path / str(row["pins_path"])).resolve() for row in pins
    }
    classified_stored = sum(_directory_size(path) for path in classified_paths)
    control_stored = sum(
        path.stat().st_size
        for path in control_paths
        if path.is_file() and not any(root == path or root in path.parents for root in classified_paths)
    )
    unclassified = max(0, stored - classified_stored - control_stored)
    result = {
        "schema_version": AUDIT_SCHEMA,
        "status": "pass" if not findings else "blocked",
        "root": str(root_path),
        "runs": sorted(rows, key=lambda item: item["path"]),
        "heads": list(heads),
        "pins": list(pins),
        "findings": findings,
        "counts": counts,
        "logical_bytes": sum(object_logical.values()),
        "stored_bytes": stored,
        "classified_stored_bytes": classified_stored,
        "control_stored_bytes": control_stored,
        "unclassified_bytes": unclassified,
        "claim_boundary": "Audit classifies retained evidence identity and reachability; it does not reinterpret target-owned validation results.",
    }
    result["audit_fingerprint"] = _sha256_bytes(_canonical_bytes({key: result[key] for key in ("runs", "heads", "pins", "findings")}))
    return result


def _without_descendant_candidates(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    ordered = sorted(rows, key=lambda item: (len(Path(str(item["path"])).parts), str(item["path"])))
    selected: list[Mapping[str, Any]] = []
    selected_paths: list[Path] = []
    for row in ordered:
        path = Path(str(row["path"]))
        if any(parent == path or parent in path.parents for parent in selected_paths):
            continue
        selected.append(row)
        selected_paths.append(path)
    return selected


def plan_evidence_gc(
    root: str | Path,
    *,
    keep: int = 2,
    include_legacy: bool = False,
    preserve_paths: Sequence[str] = (),
) -> dict[str, Any]:
    if keep < 0:
        raise EvidenceLifecycleError("keep must be non-negative")
    audit = audit_evidence(root)
    if audit.get("findings"):
        raise EvidenceLifecycleError("evidence audit has blockers; repair them before GC planning")
    by_path = {str(row["path"]): row for row in audit["runs"]}
    preserved: list[Mapping[str, Any]] = []
    for value in dict.fromkeys(str(item).replace("\\", "/").strip("/") for item in preserve_paths):
        candidate = (Path(root).resolve() / value).resolve()
        if not value or not _path_within(Path(root).resolve(), candidate) or candidate == Path(root).resolve():
            raise EvidenceLifecycleError(f"unsafe preserved evidence path: {value}")
        row = by_path.get(value)
        if row is None:
            raise EvidenceLifecycleError(f"preserved evidence path is not one audited run root: {value}")
        preserved.append(row)
    preserved_names = {str(row["path"]) for row in preserved}
    eligible = [
        row for row in audit["runs"]
        if row["classification"] == "collectible" and str(row["path"]) not in preserved_names
    ]
    if include_legacy:
        eligible.extend(
            row for row in audit["runs"]
            if row["classification"] == "legacy_unmanaged" and str(row["path"]) not in preserved_names
        )
    eligible.sort(key=lambda item: (float(item.get("finished_at_epoch", 0.0)), str(item["path"])), reverse=True)
    retained = eligible[:keep]
    candidates = _without_descendant_candidates(eligible[keep:])
    body = {
        "schema_version": GC_PLAN_SCHEMA,
        "root": str(Path(root).resolve()),
        "audit_fingerprint": audit["audit_fingerprint"],
        "keep": keep,
        "include_legacy": include_legacy,
        "preserved_paths": sorted(preserved_names),
        "retained_paths": [str(item["path"]) for item in retained],
        "candidates": [
            {
                "path": str(item["path"]),
                "classification": str(item["classification"]),
                "fingerprint": str(item["fingerprint"]),
                "stored_bytes": int(item["stored_bytes"]),
            }
            for item in candidates
        ],
        "head_bindings": audit["heads"],
        "pin_bindings": audit["pins"],
        "claim_boundary": "This plan is read-only and authorizes no move or deletion until exact identities are revalidated.",
    }
    return {**body, "plan_id": _sha256_bytes(_canonical_bytes(body))}


def _load_plan(plan: str | Path | Mapping[str, Any]) -> Mapping[str, Any]:
    payload = _load_json(Path(plan)) if isinstance(plan, (str, Path)) else dict(plan)
    if payload.get("schema_version") != GC_PLAN_SCHEMA:
        raise EvidenceLifecycleError("unsupported evidence GC plan schema")
    body = {key: value for key, value in payload.items() if key != "plan_id"}
    if _sha256_bytes(_canonical_bytes(body)) != payload.get("plan_id"):
        raise EvidenceLifecycleError("evidence GC plan fingerprint mismatch")
    return payload


def apply_evidence_gc(root: str | Path, plan: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    payload = _load_plan(plan)
    if Path(str(payload.get("root", ""))).resolve() != root_path:
        raise EvidenceLifecycleError("evidence GC plan root mismatch")
    current = plan_evidence_gc(
        root_path,
        keep=int(payload.get("keep", 0)),
        include_legacy=bool(payload.get("include_legacy")),
        preserve_paths=tuple(str(item) for item in payload.get("preserved_paths", ())),
    )
    if current.get("plan_id") != payload.get("plan_id"):
        raise EvidenceLifecycleError("evidence GC plan is stale")
    quarantine_id = str(payload["plan_id"]).removeprefix("sha256:")
    quarantine = root_path / ".quarantine" / quarantine_id
    if quarantine.exists():
        raise EvidenceLifecycleError("evidence quarantine already exists")
    operations: list[tuple[Path, Path, Mapping[str, Any]]] = []
    # Verify every move before changing the first path so that one late bad
    # candidate cannot leave an otherwise valid plan half-applied.
    for row in payload.get("candidates", ()):
        source = (root_path / str(row["path"])).resolve()
        if not _path_within(root_path, source) or source == root_path or ".quarantine" in source.parts:
            raise EvidenceLifecycleError("unsafe evidence GC candidate")
        if not source.is_dir() or _directory_fingerprint(source) != row.get("fingerprint"):
            raise EvidenceLifecycleError(f"evidence candidate changed: {row['path']}")
        destination = (quarantine / "runs" / str(row["path"])).resolve()
        if not _path_within(quarantine, destination) or destination.exists():
            raise EvidenceLifecycleError(f"unsafe evidence quarantine destination: {row['path']}")
        operations.append((source, destination, row))
    moved: list[dict[str, str]] = []
    try:
        for source, destination, row in operations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append({"from": str(row["path"]), "to": destination.relative_to(root_path).as_posix()})
        receipt = {
            "schema_version": GC_RECEIPT_SCHEMA,
            "action": "quarantine",
            "status": "pass",
            "plan_id": payload["plan_id"],
            "quarantine_id": quarantine_id,
            "moved": moved,
            "stored_bytes": sum(int(item.get("stored_bytes", 0)) for item in payload.get("candidates", ())),
            "created_at_epoch": time.time(),
            "claim_boundary": "Only exact unreachable candidates from the current frozen plan were moved; no evidence was deleted.",
        }
        write_json_atomic(quarantine / "quarantine-receipt.json", receipt)
    except Exception:
        for row in reversed(moved):
            source = (root_path / row["to"]).resolve()
            destination = (root_path / row["from"]).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.exists() and not destination.exists():
                shutil.move(str(source), str(destination))
        if quarantine.exists():
            _remove_tree_exact(quarantine)
        raise
    return receipt


def restore_evidence_quarantine(root: str | Path, quarantine_id: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    quarantine = (root_path / ".quarantine" / quarantine_id).resolve()
    if not _path_within(root_path / ".quarantine", quarantine) or not quarantine.is_dir():
        raise EvidenceLifecycleError("unknown evidence quarantine")
    receipt = _load_json(quarantine / "quarantine-receipt.json")
    operations: list[tuple[Path, Path, str]] = []
    for row in receipt.get("moved", ()):
        source = (root_path / str(row["to"])).resolve()
        destination = (root_path / str(row["from"])).resolve()
        if not _path_within(quarantine, source) or not source.is_dir():
            raise EvidenceLifecycleError(f"restore source is invalid: {row['to']}")
        if not _path_within(root_path, destination) or destination == root_path or destination.exists():
            raise EvidenceLifecycleError(f"restore destination already exists or is unsafe: {row['from']}")
        operations.append((source, destination, str(row["from"])))
    restored: list[str] = []
    result = {
        "schema_version": GC_RECEIPT_SCHEMA,
        "action": "restore",
        "status": "pass",
        "quarantine_id": quarantine_id,
        "restored": restored,
        "created_at_epoch": time.time(),
        "claim_boundary": "The exact quarantine was restored without changing evidence contents.",
    }
    receipt_path = root_path / ".quarantine" / "receipts" / f"restore-{quarantine_id}.json"
    try:
        for source, destination, relative in operations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            restored.append(relative)
        result["restored"] = restored
        write_json_atomic(receipt_path, result)
        _remove_tree_exact(quarantine)
    except Exception:
        if receipt_path.exists():
            receipt_path.unlink()
        for source, destination, _relative in reversed(operations[: len(restored)]):
            source.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not source.exists():
                shutil.move(str(destination), str(source))
        raise
    return result


def purge_evidence_quarantine(root: str | Path, quarantine_id: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    quarantine_root = (root_path / ".quarantine").resolve()
    quarantine = (quarantine_root / quarantine_id).resolve()
    if quarantine.parent != quarantine_root or not quarantine.is_dir() or quarantine.name == "receipts":
        raise EvidenceLifecycleError("purge target is not one exact evidence quarantine")
    audit = audit_evidence(root_path)
    if audit.get("findings"):
        raise EvidenceLifecycleError("current or pinned evidence replay failed; purge blocked")
    receipt = _load_json(quarantine / "quarantine-receipt.json")
    remaining_bytes = _directory_size(quarantine)
    planned_bytes = int(receipt.get("stored_bytes", remaining_bytes) or remaining_bytes)
    result = {
        "schema_version": GC_RECEIPT_SCHEMA,
        "action": "purge",
        "status": "pass",
        "quarantine_id": quarantine_id,
        "plan_id": receipt.get("plan_id", ""),
        "deleted_bytes": planned_bytes,
        "deleted_in_this_attempt_bytes": remaining_bytes,
        "partial_prior_attempt_detected": remaining_bytes != planned_bytes,
        "head_replay_fingerprint": audit.get("audit_fingerprint", ""),
        "created_at_epoch": time.time(),
        "claim_boundary": "Only the named quarantine was deleted after current and pinned evidence replay remained valid.",
    }
    receipt_root = quarantine_root / "receipts"
    pending_path = receipt_root / f"purge-pending-{quarantine_id}.json"
    final_path = receipt_root / f"purge-{quarantine_id}.json"
    write_json_atomic(
        pending_path,
        {
            **result,
            "status": "pending",
            "claim_boundary": "A destructive purge was authorized but has no success claim until the exact quarantine is absent.",
        },
    )
    _remove_tree_exact(quarantine)
    write_json_atomic(final_path, result)
    pending_path.unlink()
    return result


__all__ = [
    "AUDIT_SCHEMA",
    "EvidenceLifecycleError",
    "GC_PLAN_SCHEMA",
    "HEAD_SCHEMA",
    "OBJECT_SCHEMA",
    "PINS_SCHEMA",
    "RUN_SCHEMA",
    "apply_evidence_gc",
    "audit_evidence",
    "default_run_directory",
    "ensure_new_run_directory",
    "fingerprint_payload",
    "plan_evidence_gc",
    "publish_run",
    "purge_evidence_quarantine",
    "resolve_object_path",
    "restore_evidence_quarantine",
    "store_text_object",
    "verify_text_object",
    "write_json_atomic",
]
