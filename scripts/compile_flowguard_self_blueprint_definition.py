"""Compile direct-current model-purpose and self-blueprint source identities.

The checked-in manifest and definition own authored behavior semantics.  This
compiler only refreshes the mechanical fingerprints attached to each
already-authored model purpose and owner contract.  Missing, foreign, or
duplicate owners are therefore blockers, not synthesis requests.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
from typing import Any, Mapping, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.model_purpose import (  # noqa: E402
    ModelPurposeClosure,
    build_model_purpose_closure,
    canonical_fingerprint,
)
from flowguard.model_regressions import (  # noqa: E402
    MANIFEST_SCHEMA,
    ModelRegressionEntry,
)
from flowguard.project_manifest import (  # noqa: E402
    ProjectManifestError,
    project_manifest_lock,
)
from flowguard.self_blueprint import (  # noqa: E402
    DEFAULT_SELF_BLUEPRINT_DEFINITION,
    SELF_BLUEPRINT_DEFINITION_SCHEMA,
)
from flowguard.source_identity import CANONICAL_TEXT_SUFFIXES  # noqa: E402


ARTIFACT_TYPE = "flowguard_self_blueprint_definition_compile"
RESULT_SCHEMA = "flowguard.self_blueprint_definition_compile_result.v1"
MANIFEST_PATH = ".flowguard/model-regression-manifest.json"
_MANIFEST_FIELDS = {
    "schema_version",
    "models",
    "governed_input_globs",
    "snapshot_only_input_globs",
    "shared_input_groups",
}
_DEFINITION_FIELDS = {
    "schema_version",
    "blueprint_id",
    "inventory_id",
    "boundary",
    "scan_python_patterns",
    "scoped_out_patterns",
    "bounded_dynamic_prefixes",
    "dynamic_allowances",
    "dynamic_selector_contracts",
    "composite_behavior_contracts",
    "owner_overrides",
    "resource_groups",
    "claim_boundary",
}
_CONTRACT_FIELDS = {"owner_id", "surface_key", "contracts", "source_identity"}
_BEHAVIOR_DIMENSIONS = {
    "input",
    "state",
    "effect",
    "output",
    "completion",
    "semantics",
}
_SOURCE_IDENTITY_FIELDS = (
    "purpose_source_id",
    "purpose_source_owner_id",
    "model_path",
    "model_source_fingerprint",
    "runner_path",
    "runner_source_fingerprint",
    "purpose_declaration_fingerprint",
    "purpose_closure_fingerprint",
)
_PURPOSE_MECHANICAL_FIELDS = (
    "model_sha256",
    "runner_sha256",
    "declaration_fingerprint",
    "closure_fingerprint",
)


class SelfBlueprintDefinitionCompilerError(ValueError):
    """Raised when a direct-current compile cannot safely produce output."""


class SelfBlueprintDefinitionInputDriftError(
    SelfBlueprintDefinitionCompilerError
):
    """Raised when a frozen compiler input changes before closure."""


@dataclass(frozen=True)
class _FrozenInputs:
    root: Path
    manifest_path: Path
    definition_path: Path
    manifest_payload: Mapping[str, Any]
    definition_payload: Mapping[str, Any]
    entries: tuple[ModelRegressionEntry, ...]
    source_bytes: Mapping[Path, bytes]

    @property
    def definition_bytes(self) -> bytes:
        return self.source_bytes[self.definition_path]

    @property
    def manifest_bytes(self) -> bytes:
        return self.source_bytes[self.manifest_path]

    @property
    def fingerprint(self) -> str:
        rows = {
            _display_path(self.root, path): hashlib.sha256(payload).hexdigest()
            for path, payload in sorted(
                self.source_bytes.items(),
                key=lambda item: _display_path(self.root, item[0]),
            )
        }
        return canonical_fingerprint({"inputs": rows})


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _json_object(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SelfBlueprintDefinitionCompilerError(
            f"cannot load current JSON input {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SelfBlueprintDefinitionCompilerError(
            f"current JSON input must be an object: {path}"
        )
    return value


def _repository_file(root: Path, relative_path: str, *, role: str) -> Path:
    if not relative_path or "\\" in relative_path:
        raise SelfBlueprintDefinitionCompilerError(
            f"{role} must use one non-empty repository-relative POSIX path"
        )
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise SelfBlueprintDefinitionCompilerError(
            f"{role} escapes the direct-current repository boundary: {relative_path}"
        )
    path = (root / Path(*pure.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SelfBlueprintDefinitionCompilerError(
            f"{role} escapes the direct-current repository boundary: {relative_path}"
        ) from exc
    if not path.is_file():
        raise SelfBlueprintDefinitionCompilerError(
            f"{role} is missing: {relative_path}"
        )
    return path


def _source_fingerprint(path: Path, payload: bytes) -> str:
    canonical = payload
    if path.suffix.casefold() in CANONICAL_TEXT_SUFFIXES:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode(
                "utf-8"
            )
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _parse_manifest(payload: Mapping[str, Any]) -> tuple[ModelRegressionEntry, ...]:
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise SelfBlueprintDefinitionCompilerError(
            "model-regression manifest schema is not direct-current"
        )
    if set(payload) != _MANIFEST_FIELDS:
        raise SelfBlueprintDefinitionCompilerError(
            "model-regression manifest fields are not exact-current"
        )
    raw_models = payload.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise SelfBlueprintDefinitionCompilerError(
            "model-regression manifest must declare current model owners"
        )
    entries: list[ModelRegressionEntry] = []
    for raw in raw_models:
        if not isinstance(raw, Mapping):
            raise SelfBlueprintDefinitionCompilerError(
                "every model-regression owner must be an object"
            )
        entries.append(ModelRegressionEntry.from_dict(raw))
    owner_ids = [entry.model_id for entry in entries]
    empty = [owner for owner in owner_ids if not owner]
    duplicates = sorted(
        {owner for owner in owner_ids if owner_ids.count(owner) > 1}
    )
    if empty or duplicates:
        raise SelfBlueprintDefinitionCompilerError(
            "model-regression owner inventory is invalid: "
            f"empty={len(empty)} duplicate={','.join(duplicates) or '-'}"
        )
    return tuple(entries)


def _validate_definition(
    payload: Mapping[str, Any],
    entries: Sequence[ModelRegressionEntry],
) -> None:
    if payload.get("schema_version") != SELF_BLUEPRINT_DEFINITION_SCHEMA:
        raise SelfBlueprintDefinitionCompilerError(
            "self-blueprint definition schema is not direct-current"
        )
    if set(payload) != _DEFINITION_FIELDS:
        raise SelfBlueprintDefinitionCompilerError(
            "self-blueprint definition fields are not exact-current"
        )
    if payload.get("dynamic_selector_contracts") != []:
        raise SelfBlueprintDefinitionCompilerError(
            "self-blueprint finite dynamic selector contracts are generated "
            "from current provider observations and cannot be authored"
        )
    raw_contracts = payload.get("composite_behavior_contracts")
    if not isinstance(raw_contracts, list):
        raise SelfBlueprintDefinitionCompilerError(
            "composite_behavior_contracts must be an exact array"
        )

    owner_ids: list[str] = []
    surface_owners: dict[str, str] = {}
    for raw in raw_contracts:
        if not isinstance(raw, Mapping) or set(raw) != _CONTRACT_FIELDS:
            raise SelfBlueprintDefinitionCompilerError(
                "composite behavior contract fields are not exact-current"
            )
        owner = raw.get("owner_id")
        surface = raw.get("surface_key")
        dimensions = raw.get("contracts")
        source = raw.get("source_identity")
        if not isinstance(owner, str) or not owner.strip():
            raise SelfBlueprintDefinitionCompilerError(
                "composite behavior contract owner_id is incomplete"
            )
        if not isinstance(surface, str) or not surface.strip():
            raise SelfBlueprintDefinitionCompilerError(
                f"composite behavior contract surface_key is incomplete: {owner}"
            )
        if not isinstance(dimensions, Mapping) or set(dimensions) != _BEHAVIOR_DIMENSIONS:
            raise SelfBlueprintDefinitionCompilerError(
                f"composite behavior dimensions are not exact-current: {owner}"
            )
        if any(
            not isinstance(value, str) or not value.strip()
            for value in dimensions.values()
        ):
            raise SelfBlueprintDefinitionCompilerError(
                f"composite behavior dimension identity is incomplete: {owner}"
            )
        if not isinstance(source, Mapping) or set(source) != set(_SOURCE_IDENTITY_FIELDS):
            raise SelfBlueprintDefinitionCompilerError(
                f"composite source identity fields are not exact-current: {owner}"
            )
        if any(not isinstance(value, str) for value in source.values()):
            raise SelfBlueprintDefinitionCompilerError(
                f"composite source identity values must be strings: {owner}"
            )
        owner_ids.append(owner)
        if surface in surface_owners:
            if surface_owners[surface] == owner:
                raise SelfBlueprintDefinitionCompilerError(
                    "composite behavior contract owner/surface is duplicate: "
                    f"{owner} -> {surface}"
                )
            raise SelfBlueprintDefinitionCompilerError(
                "composite behavior contract surface is shared across owners: "
                f"{surface} -> {surface_owners[surface]},{owner}"
            )
        surface_owners[surface] = owner

    current_owners = {entry.model_id for entry in entries}
    duplicates = sorted(
        {owner for owner in owner_ids if owner_ids.count(owner) > 1}
    )
    foreign = sorted(set(owner_ids) - current_owners)
    missing = sorted(current_owners - set(owner_ids))
    if duplicates or foreign or missing:
        raise SelfBlueprintDefinitionCompilerError(
            "composite behavior owner inventory is not exact 1-per-current-owner: "
            f"missing={','.join(missing) or '-'} "
            f"foreign={','.join(foreign) or '-'} "
            f"duplicate={','.join(duplicates) or '-'}"
        )


def _entry_source_paths(root: Path, entry: ModelRegressionEntry) -> tuple[Path, Path]:
    expected_model = f".flowguard/{entry.model_id}/model.py"
    expected_runner = f".flowguard/{entry.model_id}/run_checks.py"
    if entry.model_path != expected_model:
        raise SelfBlueprintDefinitionCompilerError(
            f"model owner does not use its direct-current model.py path: {entry.model_id}"
        )
    runner_paths = tuple(token for token in entry.runner if token.endswith(".py"))
    if runner_paths != (expected_runner,):
        raise SelfBlueprintDefinitionCompilerError(
            f"model owner does not use one direct-current run_checks.py path: {entry.model_id}"
        )
    return (
        _repository_file(root, expected_model, role=f"{entry.model_id} model source"),
        _repository_file(root, expected_runner, role=f"{entry.model_id} runner source"),
    )


def _assert_snapshot_current(
    snapshot: _FrozenInputs,
    *,
    expected_bytes: Mapping[Path, bytes] | None = None,
) -> None:
    overrides = dict(expected_bytes or {})
    foreign = set(overrides) - set(snapshot.source_bytes)
    if foreign:
        raise SelfBlueprintDefinitionCompilerError(
            "expected-byte overrides include foreign compiler inputs: "
            + ", ".join(
                sorted(_display_path(snapshot.root, path) for path in foreign)
            )
        )
    changed: list[str] = []
    for path, expected in snapshot.source_bytes.items():
        expected = overrides.get(path, expected)
        try:
            current = path.read_bytes()
        except OSError:
            changed.append(_display_path(snapshot.root, path))
            continue
        if current != expected:
            changed.append(_display_path(snapshot.root, path))
    if changed:
        raise SelfBlueprintDefinitionInputDriftError(
            "frozen compiler inputs changed: " + ", ".join(sorted(changed))
        )


def _freeze_inputs(root: Path) -> _FrozenInputs:
    manifest_path = _repository_file(root, MANIFEST_PATH, role="model manifest")
    definition_path = _repository_file(
        root,
        DEFAULT_SELF_BLUEPRINT_DEFINITION,
        role="self-blueprint definition",
    )
    manifest_bytes = manifest_path.read_bytes()
    definition_bytes = definition_path.read_bytes()
    manifest_payload = _json_object(manifest_bytes, manifest_path)
    definition_payload = _json_object(definition_bytes, definition_path)
    entries = _parse_manifest(manifest_payload)
    _validate_definition(definition_payload, entries)

    source_bytes: dict[Path, bytes] = {
        manifest_path: manifest_bytes,
        definition_path: definition_bytes,
    }
    for entry in entries:
        for path in _entry_source_paths(root, entry):
            if path in source_bytes:
                raise SelfBlueprintDefinitionCompilerError(
                    "current model owners share a mechanical source path: "
                    + _display_path(root, path)
                )
            source_bytes[path] = path.read_bytes()
    snapshot = _FrozenInputs(
        root=root,
        manifest_path=manifest_path,
        definition_path=definition_path,
        manifest_payload=manifest_payload,
        definition_payload=definition_payload,
        entries=entries,
        source_bytes=source_bytes,
    )
    _assert_snapshot_current(snapshot)
    return snapshot


def _rebuilt_purpose(
    snapshot: _FrozenInputs,
    entry: ModelRegressionEntry,
) -> tuple[ModelPurposeClosure, str, str]:
    purpose = entry.purpose_closure
    if purpose is None:
        raise SelfBlueprintDefinitionCompilerError(
            f"current model owner has no purpose closure: {entry.model_id}"
        )
    if purpose.reusable_model_type_id != entry.model_id:
        raise SelfBlueprintDefinitionCompilerError(
            "purpose closure is owned by a foreign model type: "
            f"{entry.model_id} -> {purpose.reusable_model_type_id}"
        )
    model_path, runner_path = _entry_source_paths(snapshot.root, entry)
    model_fingerprint = _source_fingerprint(
        model_path,
        snapshot.source_bytes[model_path],
    )
    runner_fingerprint = _source_fingerprint(
        runner_path,
        snapshot.source_bytes[runner_path],
    )
    rebuilt = build_model_purpose_closure(
        model_instance_id=purpose.model_instance_id,
        reusable_model_type_id=purpose.reusable_model_type_id,
        task_intent_id=purpose.task_intent_id,
        guarded_purpose=purpose.guarded_purpose,
        protected_failure_ids=purpose.protected_failure_ids,
        known_good_case_id=purpose.known_good_case_id,
        failure_bindings=purpose.failure_bindings,
        claim_boundary=purpose.claim_boundary,
        evidence_check_ids=purpose.evidence_check_ids,
        model_sha256=model_fingerprint,
        runner_sha256=runner_fingerprint,
    )
    return rebuilt, entry.model_path, runner_path.relative_to(snapshot.root).as_posix()


def _manifest_authored_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    projection = deepcopy(dict(payload))
    for row in projection["models"]:
        purpose = row.get("purpose_closure")
        if not isinstance(purpose, dict):
            raise SelfBlueprintDefinitionCompilerError(
                "current model owner has no authored purpose closure: "
                f"{row.get('model_id', '')}"
            )
        for field in _PURPOSE_MECHANICAL_FIELDS:
            purpose.pop(field, None)
    return projection


def _compiled_manifest(
    snapshot: _FrozenInputs,
) -> tuple[dict[str, Any], tuple[ModelRegressionEntry, ...], list[dict[str, Any]]]:
    candidate = deepcopy(dict(snapshot.manifest_payload))
    by_owner = {entry.model_id: entry for entry in snapshot.entries}
    diffs: list[dict[str, Any]] = []
    for row in candidate["models"]:
        owner = row["model_id"]
        rebuilt, _, _ = _rebuilt_purpose(snapshot, by_owner[owner])
        current = row["purpose_closure"]
        desired = rebuilt.to_dict()
        changed_fields = [
            field
            for field in _PURPOSE_MECHANICAL_FIELDS
            if current.get(field) != desired[field]
        ]
        if changed_fields:
            diffs.append(
                {
                    "owner_id": owner,
                    "changed_fields": changed_fields,
                    "before": {
                        field: current.get(field) for field in changed_fields
                    },
                    "after": {
                        field: desired[field] for field in changed_fields
                    },
                }
            )
        row["purpose_closure"] = desired

    if _manifest_authored_projection(snapshot.manifest_payload) != (
        _manifest_authored_projection(candidate)
    ):
        raise SelfBlueprintDefinitionCompilerError(
            "compiler attempted to change authored model-manifest semantics"
        )
    entries = _parse_manifest(candidate)
    return candidate, entries, diffs


def _compiled_definition(
    snapshot: _FrozenInputs,
    entries: Sequence[ModelRegressionEntry],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate = deepcopy(dict(snapshot.definition_payload))
    rows = candidate["composite_behavior_contracts"]
    by_owner = {entry.model_id: entry for entry in entries}
    diffs: list[dict[str, Any]] = []
    for row in rows:
        owner = row["owner_id"]
        purpose, model_path, runner_path = _rebuilt_purpose(
            snapshot,
            by_owner[owner],
        )
        desired = {
            "purpose_source_id": (
                f"{MANIFEST_PATH}#model:{owner}:purpose-declaration"
            ),
            "purpose_source_owner_id": f"model-purpose-declaration:{owner}",
            "model_path": model_path,
            "model_source_fingerprint": purpose.model_sha256,
            "runner_path": runner_path,
            "runner_source_fingerprint": purpose.runner_sha256,
            "purpose_declaration_fingerprint": purpose.declaration_fingerprint,
            "purpose_closure_fingerprint": purpose.closure_fingerprint,
        }
        current = row["source_identity"]
        changed_fields = [
            field for field in _SOURCE_IDENTITY_FIELDS if current.get(field) != desired[field]
        ]
        if changed_fields:
            diffs.append(
                {
                    "owner_id": owner,
                    "changed_fields": changed_fields,
                    "before": {field: current.get(field) for field in changed_fields},
                    "after": {field: desired[field] for field in changed_fields},
                }
            )
        row["source_identity"] = desired

    authored_before = deepcopy(dict(snapshot.definition_payload))
    authored_after = deepcopy(candidate)
    for payload in (authored_before, authored_after):
        for row in payload["composite_behavior_contracts"]:
            row.pop("source_identity")
    if authored_before != authored_after:
        raise SelfBlueprintDefinitionCompilerError(
            "compiler attempted to change authored self-blueprint semantics"
        )
    return candidate, diffs


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _rollback_compiled_outputs(
    snapshot: _FrozenInputs,
    *,
    candidates: Mapping[Path, bytes],
    written_paths: Sequence[Path],
    cause: Exception,
) -> None:
    conflicts: list[str] = []
    failed: list[str] = []
    for path in reversed(tuple(written_paths)):
        try:
            current = path.read_bytes()
        except OSError:
            failed.append(_display_path(snapshot.root, path))
            continue
        if current != candidates[path]:
            conflicts.append(_display_path(snapshot.root, path))
            continue
        try:
            _atomic_write(path, snapshot.source_bytes[path])
        except OSError:
            failed.append(_display_path(snapshot.root, path))
            continue
        try:
            restored = path.read_bytes()
        except OSError:
            failed.append(_display_path(snapshot.root, path))
            continue
        if restored != snapshot.source_bytes[path]:
            failed.append(_display_path(snapshot.root, path))

    if conflicts:
        raise SelfBlueprintDefinitionInputDriftError(
            f"{cause}; compiled output changed by another writer after compile: "
            + ", ".join(sorted(conflicts))
        ) from cause
    if failed:
        raise SelfBlueprintDefinitionInputDriftError(
            f"{cause}; compiled output rollback did not restore frozen inputs: "
            + ", ".join(sorted(failed))
        ) from cause
    raise SelfBlueprintDefinitionInputDriftError(
        f"{cause}; compiled outputs were atomically restored"
    ) from cause


def _write_compiled_outputs(
    snapshot: _FrozenInputs,
    *,
    manifest_bytes: bytes,
    definition_bytes: bytes,
    manifest_changed: bool,
    definition_changed: bool,
) -> tuple[bool, bool]:
    candidates = {
        snapshot.manifest_path: manifest_bytes,
        snapshot.definition_path: definition_bytes,
    }
    expected: dict[Path, bytes] = {}
    written_paths: list[Path] = []
    try:
        with project_manifest_lock(snapshot.manifest_path):
            _assert_snapshot_current(snapshot)
            if manifest_changed:
                _atomic_write(snapshot.manifest_path, manifest_bytes)
                written_paths.append(snapshot.manifest_path)
                expected[snapshot.manifest_path] = manifest_bytes
                _assert_snapshot_current(snapshot, expected_bytes=expected)
            if definition_changed:
                _assert_snapshot_current(snapshot, expected_bytes=expected)
                _atomic_write(snapshot.definition_path, definition_bytes)
                written_paths.append(snapshot.definition_path)
                expected[snapshot.definition_path] = definition_bytes
                _assert_snapshot_current(snapshot, expected_bytes=expected)
    except (OSError, ProjectManifestError, SelfBlueprintDefinitionCompilerError) as exc:
        if written_paths:
            _rollback_compiled_outputs(
                snapshot,
                candidates=candidates,
                written_paths=written_paths,
                cause=exc,
            )
        if isinstance(exc, SelfBlueprintDefinitionCompilerError):
            raise
        raise SelfBlueprintDefinitionCompilerError(str(exc)) from exc
    return manifest_changed, definition_changed


def compile_self_blueprint_definition(
    root: str | Path = ".",
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Check or atomically refresh only mechanical purpose/source identities."""

    root_path = Path(root).expanduser().resolve()
    snapshot = _freeze_inputs(root_path)
    candidate_manifest, candidate_entries, purpose_diffs = _compiled_manifest(
        snapshot
    )
    candidate_definition, identity_diffs = _compiled_definition(
        snapshot,
        candidate_entries,
    )
    _assert_snapshot_current(snapshot)
    manifest_changed = candidate_manifest != snapshot.manifest_payload
    definition_changed = candidate_definition != snapshot.definition_payload
    changed = manifest_changed or definition_changed
    candidate_manifest_bytes = _json_bytes(candidate_manifest)
    candidate_definition_bytes = _json_bytes(candidate_definition)
    manifest_wrote = False
    definition_wrote = False

    if write and changed:
        manifest_wrote, definition_wrote = _write_compiled_outputs(
            snapshot,
            manifest_bytes=candidate_manifest_bytes,
            definition_bytes=candidate_definition_bytes,
            manifest_changed=manifest_changed,
            definition_changed=definition_changed,
        )
    wrote = manifest_wrote or definition_wrote
    changed_owner_ids = sorted(
        {row["owner_id"] for row in purpose_diffs + identity_diffs}
    )

    ok = write or not changed
    return {
        "schema_version": RESULT_SCHEMA,
        "artifact_type": ARTIFACT_TYPE,
        "ok": ok,
        "status": "pass" if ok else "blocked",
        "mode": "write" if write else "check",
        "root": str(root_path),
        "manifest_path": str(snapshot.manifest_path),
        "definition_path": str(snapshot.definition_path),
        "input_fingerprint": snapshot.fingerprint,
        "owner_count": len(snapshot.entries),
        "changed": changed,
        "wrote": wrote,
        "manifest_changed": manifest_changed,
        "manifest_wrote": manifest_wrote,
        "definition_changed": definition_changed,
        "definition_wrote": definition_wrote,
        "changed_owner_ids": changed_owner_ids,
        "purpose_fingerprint_diffs": purpose_diffs,
        "source_identity_diffs": identity_diffs,
        "current_manifest_fingerprint": canonical_fingerprint(
            dict(snapshot.manifest_payload)
        ),
        "candidate_manifest_fingerprint": canonical_fingerprint(
            candidate_manifest
        ),
        "current_definition_fingerprint": canonical_fingerprint(
            dict(snapshot.definition_payload)
        ),
        "candidate_definition_fingerprint": canonical_fingerprint(
            candidate_definition
        ),
        "error": (
            "model-purpose or self-blueprint mechanical identities are stale; "
            "use explicit --write"
            if changed and not write
            else ""
        ),
    }


def _blocked_result(root: Path, *, write: bool, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "artifact_type": ARTIFACT_TYPE,
        "ok": False,
        "status": "blocked",
        "mode": "write" if write else "check",
        "root": str(root),
        "manifest_path": str(root / MANIFEST_PATH),
        "definition_path": str(root / DEFAULT_SELF_BLUEPRINT_DEFINITION),
        "input_fingerprint": "",
        "owner_count": 0,
        "changed": False,
        "wrote": False,
        "manifest_changed": False,
        "manifest_wrote": False,
        "definition_changed": False,
        "definition_wrote": False,
        "changed_owner_ids": [],
        "purpose_fingerprint_diffs": [],
        "source_identity_diffs": [],
        "current_manifest_fingerprint": "",
        "candidate_manifest_fingerprint": "",
        "current_definition_fingerprint": "",
        "candidate_definition_fingerprint": "",
        "error": f"{type(error).__name__}: {error}",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "check direct-current FlowGuard model-purpose and self-blueprint "
            "mechanical identities; write only with explicit --write"
        )
    )
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "atomically refresh manifest purpose fingerprints first, then "
            "self-blueprint source identities"
        ),
    )
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    try:
        result = compile_self_blueprint_definition(root, write=args.write)
    except (OSError, TypeError, SelfBlueprintDefinitionCompilerError) as exc:
        result = _blocked_result(root, write=args.write, error=exc)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
