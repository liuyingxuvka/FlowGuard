"""Single atomic write boundary for ``.flowguard/project.toml``."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterator


class ProjectManifestError(RuntimeError):
    """Raised when project-manifest ownership or compare-and-swap fails."""


def manifest_text_fingerprint(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def read_manifest_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise ProjectManifestError(f"cannot read project manifest: {exc}") from exc


@contextmanager
def project_manifest_lock(path: str | Path) -> Iterator[Path]:
    manifest_path = Path(path).resolve()
    lock_path = manifest_path.with_suffix(manifest_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"pid": os.getpid(), "manifest": str(manifest_path)},
        ensure_ascii=False,
        sort_keys=True,
    )
    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        )
    except FileExistsError as exc:
        raise ProjectManifestError(
            f"project manifest is locked: {lock_path}"
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield lock_path
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_project_manifest(
    path: str | Path,
    text: str,
    *,
    expected_fingerprint: str,
) -> str:
    """Replace the manifest only if the frozen input still owns the path."""

    manifest_path = Path(path).resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        current_fingerprint = manifest_text_fingerprint(current_text)
        if current_fingerprint != expected_fingerprint:
            raise ProjectManifestError(
                "project manifest changed after planning; rebuild from the new authority head"
            )
        replace_project_manifest_locked(manifest_path, normalized)
    return manifest_text_fingerprint(normalized)


def replace_project_manifest_locked(
    path: str | Path,
    text: str,
) -> str:
    """Replace manifest bytes while the caller owns ``project_manifest_lock``."""

    manifest_path = Path(path).resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=manifest_path.name + ".",
        suffix=".tmp",
        dir=manifest_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(normalized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, manifest_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return manifest_text_fingerprint(normalized)


__all__ = [
    "ProjectManifestError",
    "atomic_write_project_manifest",
    "manifest_text_fingerprint",
    "project_manifest_lock",
    "read_manifest_text",
    "replace_project_manifest_locked",
]
