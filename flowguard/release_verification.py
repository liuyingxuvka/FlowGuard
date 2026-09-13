"""Receipt-bound local, tag, and published release verification for FlowGuard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import importlib.metadata
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import Any, Callable, Mapping, Sequence

from .completion_epoch import (
    COMPLETION_CLAIM_SCOPE_RELEASE,
    normalize_completion_claim_scope,
)
from .evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    receipt_path,
)
from .validation_ownership import (
    _owner_observation_patterns,
    _validation_input_manifest_from_observation,
    ValidationOwnerContract,
    manifest_fingerprint,
    model_authority_release_paths,
    release_tree_manifest,
    resolve_input_manifest,
    verify_parent_receipt,
)


RELEASE_VERIFICATION_SCHEMA = "flowguard.release_verification.v2"
RELEASE_PHASE_LOCAL_CANDIDATE = "local-candidate"
RELEASE_PHASE_TAG = "tag"
RELEASE_PHASE_PUBLISHED = "published"
RELEASE_PHASES = (
    RELEASE_PHASE_LOCAL_CANDIDATE,
    RELEASE_PHASE_TAG,
    RELEASE_PHASE_PUBLISHED,
)

VALIDATION_PARENT_SUBJECT_ID = "validation-parent:full"
VALIDATION_PARENT_SUBJECT_KIND = "validation_parent"
VALIDATION_INPUT_SNAPSHOT_ID = (
    "input:validation-parent:validation-input-manifest"
)
RELEASE_TREE_SNAPSHOT_ID = "input:validation-parent:release-tree-manifest"


@dataclass(frozen=True)
class ReleaseCheck:
    check_id: str
    status: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ReleaseTarget:
    """Target-owned release identity consumed by the common verifier.

    FlowGuard's package/version is deliberately not part of this identity.
    A target may be FlowGuard itself, but the verifier has no self-repository
    fast path: all repositories provide this same descriptor.
    """

    target_id: str
    version: str
    tag: str
    repository: str = ""
    default_branch: str = ""
    distribution_kind: str = "source_only"
    required_source_paths: tuple[str, ...] = ()
    required_check_ids: tuple[str, ...] = ()
    assets: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", str(self.target_id).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(self, "tag", str(self.tag).strip())
        object.__setattr__(self, "repository", str(self.repository).strip())
        object.__setattr__(self, "default_branch", str(self.default_branch).strip())
        object.__setattr__(self, "distribution_kind", str(self.distribution_kind).strip())
        object.__setattr__(self, "required_source_paths", tuple(dict.fromkeys(str(p).replace("\\", "/") for p in self.required_source_paths)))
        object.__setattr__(self, "required_check_ids", tuple(dict.fromkeys(str(p) for p in self.required_check_ids)))
        normalized_assets: list[tuple[str, str]] = []
        for item in self.assets:
            if isinstance(item, Mapping):
                path = str(item.get("path", ""))
                digest = str(item.get("sha256", ""))
            else:
                path, digest = item
                path, digest = str(path), str(digest)
            normalized_assets.append((path.replace("\\", "/"), digest))
        object.__setattr__(self, "assets", tuple(dict.fromkeys(normalized_assets)))
        if not self.target_id or not self.version or not self.tag:
            raise ValueError("release target requires target_id, version, and tag")
        if self.distribution_kind not in {"source_only", "source_and_assets"}:
            raise ValueError("release target distribution_kind is invalid")
        if not self.tag.startswith("v") or self.tag[1:] != self.version:
            raise ValueError("release target tag must be v-prefixed version")
        for path in (*self.required_source_paths, *(path for path, _ in self.assets)):
            if not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError(f"release target path must be relative: {path}")
        if self.distribution_kind == "source_only" and self.assets:
            raise ValueError("source_only release target cannot declare assets")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReleaseTarget":
        assets = value.get("assets", ())
        if not isinstance(assets, Sequence) or isinstance(assets, (str, bytes)):
            raise ValueError("release target assets must be an array")
        return cls(
            target_id=str(value.get("target_id", "")),
            version=str(value.get("version", "")),
            tag=str(value.get("tag", "")),
            repository=str(value.get("repository", "")),
            default_branch=str(value.get("default_branch", "")),
            distribution_kind=str(value.get("distribution_kind", "source_only")),
            required_source_paths=tuple(value.get("required_source_paths", ())),
            required_check_ids=tuple(value.get("required_check_ids", ())),
            assets=tuple(assets),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "ReleaseTarget":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("release target JSON must be an object")
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "version": self.version,
            "tag": self.tag,
            "repository": self.repository,
            "default_branch": self.default_branch,
            "distribution_kind": self.distribution_kind,
            "required_source_paths": list(self.required_source_paths),
            "required_check_ids": list(self.required_check_ids),
            "assets": [{"path": path, "sha256": digest} for path, digest in self.assets],
        }


@dataclass(frozen=True)
class ReleaseVerificationReceipt:
    phase: str
    version: str
    tag: str
    checks: tuple[ReleaseCheck, ...]
    parent_receipt_id: str = ""
    parent_receipt_fingerprint: str = ""
    validation_input_manifest_fingerprint: str = ""
    release_tree_manifest_fingerprint: str = ""
    commit: str = ""
    upstream_receipt_ids: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    release_url: str = ""
    target_id: str = ""
    target_fingerprint: str = ""
    claim_boundary: str = ""
    # Release verification is a distinct claim boundary.  The functional
    # parent it consumes may be local_validation (or the legacy full parent),
    # but this receipt itself must never be serialized as a local claim.
    claim_scope: str = COMPLETION_CLAIM_SCOPE_RELEASE

    def __post_init__(self) -> None:
        if self.phase not in RELEASE_PHASES:
            raise ValueError(f"unsupported release verification phase: {self.phase}")
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(
            self,
            "upstream_receipt_ids",
            tuple(dict.fromkeys(str(item) for item in self.upstream_receipt_ids if item)),
        )
        object.__setattr__(
            self,
            "artifact_paths",
            tuple(dict.fromkeys(str(item) for item in self.artifact_paths if item)),
        )
        object.__setattr__(
            self,
            "claim_scope",
            normalize_completion_claim_scope(self.claim_scope),
        )
        if self.claim_scope != COMPLETION_CLAIM_SCOPE_RELEASE:
            raise ValueError(
                "release verification receipts must use the release claim scope"
            )
        if not self.claim_boundary:
            object.__setattr__(self, "claim_boundary", _phase_claim_boundary(self.phase))

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(check.ok for check in self.checks)

    @property
    def status(self) -> str:
        return "pass" if self.ok else "blocked"

    @property
    def receipt_fingerprint(self) -> str:
        return fingerprint_value(
            {
                "schema_version": RELEASE_VERIFICATION_SCHEMA,
                "phase": self.phase,
                "version": self.version,
                "tag": self.tag,
                "commit": self.commit,
                "parent_receipt_id": self.parent_receipt_id,
                "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
                "validation_input_manifest_fingerprint": (
                    self.validation_input_manifest_fingerprint
                ),
                "release_tree_manifest_fingerprint": (
                    self.release_tree_manifest_fingerprint
                ),
                "upstream_receipt_ids": list(self.upstream_receipt_ids),
                "checks": [check.to_dict() for check in self.checks],
                "release_url": self.release_url,
                "target_id": self.target_id,
                "target_fingerprint": self.target_fingerprint,
                "claim_scope": self.claim_scope,
            }
        )

    @property
    def receipt_id(self) -> str:
        digest = self.receipt_fingerprint.split(":", 1)[1]
        return f"receipt:release-verification:{self.phase}:{digest[:32]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_release_verification_receipt",
            "schema_version": RELEASE_VERIFICATION_SCHEMA,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "phase": self.phase,
            "version": self.version,
            "tag": self.tag,
            "commit": self.commit,
            "status": self.status,
            "ok": self.ok,
            "parent_receipt_id": self.parent_receipt_id,
            "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
            "validation_input_manifest_fingerprint": (
                self.validation_input_manifest_fingerprint
            ),
            "release_tree_manifest_fingerprint": (
                self.release_tree_manifest_fingerprint
            ),
            "upstream_receipt_ids": list(self.upstream_receipt_ids),
            "checks": [check.to_dict() for check in self.checks],
            "blockers": [check.check_id for check in self.checks if not check.ok],
            "artifact_paths": list(self.artifact_paths),
            "release_url": self.release_url,
            "target_id": self.target_id,
            "target_fingerprint": self.target_fingerprint,
            "claim_boundary": self.claim_boundary,
            "claim_scope": self.claim_scope,
        }

    def format_text(self) -> str:
        lines = [
            "=== FlowGuard release verification receipt ===",
            f"phase: {self.phase}",
            f"version: {self.version}",
            f"tag: {self.tag}",
            f"commit: {self.commit or '<not-bound>'}",
            f"status: {self.status}",
            f"receipt_id: {self.receipt_id}",
            f"claim_scope: {self.claim_scope}",
        ]
        lines.extend(
            f"- {check.check_id}: {check.status} - {check.message}"
            for check in self.checks
        )
        if self.release_url:
            lines.append(f"release_url: {self.release_url}")
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


def release_target_fingerprint(target: ReleaseTarget) -> str:
    return fingerprint_value(target.to_dict())


def load_release_verification_receipt(path: str | Path) -> ReleaseVerificationReceipt:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("release verification receipt must be a JSON object")
    checks = tuple(
        ReleaseCheck(
            check_id=str(item.get("check_id", "")),
            status=str(item.get("status", "")),
            message=str(item.get("message", "")),
            details=dict(item.get("details", {})),
        )
        for item in value.get("checks", ())
        if isinstance(item, Mapping)
    )
    receipt = ReleaseVerificationReceipt(
        phase=str(value.get("phase", "")),
        version=str(value.get("version", "")),
        tag=str(value.get("tag", "")),
        commit=str(value.get("commit", "")),
        checks=checks,
        parent_receipt_id=str(value.get("parent_receipt_id", "")),
        parent_receipt_fingerprint=str(value.get("parent_receipt_fingerprint", "")),
        validation_input_manifest_fingerprint=str(value.get("validation_input_manifest_fingerprint", "")),
        release_tree_manifest_fingerprint=str(value.get("release_tree_manifest_fingerprint", "")),
        upstream_receipt_ids=tuple(value.get("upstream_receipt_ids", ())),
        artifact_paths=tuple(value.get("artifact_paths", ())),
        release_url=str(value.get("release_url", "")),
        claim_boundary=str(value.get("claim_boundary", "")),
        target_id=str(value.get("target_id", "")),
        target_fingerprint=str(value.get("target_fingerprint", "")),
        claim_scope=str(value.get("claim_scope", COMPLETION_CLAIM_SCOPE_RELEASE)),
    )
    supplied = str(value.get("receipt_fingerprint", ""))
    if supplied and supplied != receipt.receipt_fingerprint:
        raise ValueError("release verification receipt fingerprint is stale")
    if str(value.get("receipt_id", "")) and value["receipt_id"] != receipt.receipt_id:
        raise ValueError("release verification receipt id is stale")
    if value.get("ok") is True and not receipt.ok:
        raise ValueError("release verification receipt falsely claims pass")
    return receipt


def save_release_verification_receipt(receipt: ReleaseVerificationReceipt, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return target


def replace_release_receipt_checks(
    receipt: ReleaseVerificationReceipt,
    extra_checks: Sequence[ReleaseCheck],
) -> ReleaseVerificationReceipt:
    # Keep this helper sequence-shaped.  Callers that add one check commonly
    # pass a single ``ReleaseCheck``; accepting that value here avoids a
    # second producer/rebuild path while preserving the immutable receipt.
    if isinstance(extra_checks, ReleaseCheck):
        additions = (extra_checks,)
    else:
        additions = tuple(extra_checks)
    return replace(receipt, checks=tuple(receipt.checks) + additions)


@dataclass(frozen=True)
class _ParentBinding:
    receipt: EvidenceReceipt | None
    verification: ReceiptVerificationResult | None
    checks: tuple[ReleaseCheck, ...]
    validation_input_manifest_fingerprint: str = ""
    release_tree_manifest_fingerprint: str = ""
    artifact_paths: tuple[str, ...] = ()


CommandRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def _phase_claim_boundary(phase: str) -> str:
    if phase == RELEASE_PHASE_LOCAL_CANDIDATE:
        return (
            "Local-candidate verification independently verifies one exact full "
            "validation parent receipt and its frozen ValidationInputManifest and "
            "ReleaseTreeManifest. It starts no validation producer and proves no "
            "commit, tag, push, or publication."
        )
    if phase == RELEASE_PHASE_TAG:
        return (
            "Tag verification adds proof that the local immutable tag resolves to "
            "a committed tree matching the parent receipt's ReleaseTreeManifest. "
            "It starts no validation producer and proves no remote publication."
        )
    return (
        "Published verification adds the peeled remote tag, exact release commit, "
        "and a published non-draft non-prerelease GitHub Release with zero uploaded "
        "assets. It performs identity comparison only and starts no validation "
        "producer."
    )


def _command_runner(
    command: Sequence[str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    invocation = [executable or command[0], *command[1:]]
    try:
        return subprocess.run(
            invocation,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return subprocess.CompletedProcess(
            invocation,
            127,
            stdout="",
            stderr=str(error),
        )


def _check(check_id: str, ok: bool, message: str, **details: Any) -> ReleaseCheck:
    return ReleaseCheck(
        check_id,
        "pass" if ok else "blocked",
        message,
        details,
    )


def _project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _package_archives(root: Path, version: str) -> tuple[Path, ...]:
    dist = root / "dist"
    return tuple(sorted(dist.glob(f"flowguard-{version}*.whl"))) + tuple(
        sorted(dist.glob(f"flowguard-{version}.tar.gz"))
    )


def _parent_artifact_paths(
    parent_reference: EvidenceReceipt | str | Path,
    parent: EvidenceReceipt | None,
    root: Path,
    receipt_root: Path,
) -> tuple[str, ...]:
    paths: list[str] = []
    if not isinstance(parent_reference, EvidenceReceipt):
        candidate = Path(parent_reference)
        if candidate.is_file():
            paths.append(str(candidate.resolve()))
    if parent is None:
        return tuple(paths)
    canonical_path = receipt_path(
        parent.receipt_id,
        root,
        output_directory=receipt_root,
    )
    if canonical_path.is_file():
        paths.append(str(canonical_path.resolve()))
    proof_relative = str(parent.metadata.get("proof_relpath", ""))
    if proof_relative:
        proof_path = (receipt_root / proof_relative).resolve()
        if receipt_root == proof_path.parent or receipt_root in proof_path.parents:
            if proof_path.is_file():
                paths.append(str(proof_path))
    return tuple(dict.fromkeys(paths))


def _load_parent_binding(
    root: Path,
    *,
    parent_receipt: EvidenceReceipt | str | Path,
    receipt_root: Path,
    require_release_tree: bool = True,
) -> _ParentBinding:
    parent: EvidenceReceipt | None = None
    verification: ReceiptVerificationResult | None = None
    load_error = ""
    try:
        parent = (
            parent_receipt
            if isinstance(parent_receipt, EvidenceReceipt)
            else load_evidence_receipt(
                parent_receipt,
                root,
                output_directory=receipt_root,
            )
        )
        verification = verify_parent_receipt(
            parent,
            root,
            receipt_root,
            release_tree_current=require_release_tree,
        )
    except (OSError, TypeError, ValueError) as error:
        load_error = f"{type(error).__name__}: {error}"

    artifacts = _parent_artifact_paths(
        parent_receipt,
        parent,
        root,
        receipt_root,
    )
    if parent is None:
        checks = (
            _check(
                "release.parent_receipt_exact",
                False,
                "an exact canonical validation-parent receipt is required",
                error=load_error,
            ),
            _check(
                "release.validation_input_manifest_binding",
                False,
                "the parent must bind ValidationInputManifest",
            ),
            _check(
                "release.release_tree_manifest_binding",
                not require_release_tree,
                "the parent must bind ReleaseTreeManifest"
                if require_release_tree
                else "release tree is bound by the candidate, not the functional parent",
            ),
        )
        return _ParentBinding(None, None, checks, artifact_paths=artifacts)

    snapshots = {item.artifact_id: item for item in parent.input_snapshots}
    validation_snapshot = snapshots.get(VALIDATION_INPUT_SNAPSHOT_ID)
    release_tree_snapshot = snapshots.get(RELEASE_TREE_SNAPSHOT_ID)
    validation_fingerprint = str(
        parent.metadata.get("validation_input_manifest_fingerprint", "")
    )
    release_tree_fingerprint = str(
        parent.metadata.get("release_tree_manifest_fingerprint", "")
    )
    try:
        proof_relative = str(parent.metadata.get("proof_relpath", ""))
        proof_path = (receipt_root / proof_relative).resolve()
        if (
            not proof_relative
            or not proof_path.is_file()
            or not (receipt_root == proof_path.parent or receipt_root in proof_path.parents)
        ):
            raise ValueError("parent proof is missing")
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        contracts = tuple(
            ValidationOwnerContract.from_dict(item)
            for item in proof.get("contracts", ())
            if isinstance(item, Mapping)
        )
        if not contracts:
            raise ValueError("parent proof has no owner contracts")
        current_validation_manifest = _validation_input_manifest_from_observation(
            resolve_input_manifest(
                root,
                _owner_observation_patterns(contracts),
            )
        )
        current_validation_fingerprint = manifest_fingerprint(
            current_validation_manifest
        )
        current_release_tree_fingerprint = manifest_fingerprint(
            release_tree_manifest(root)
        )
        manifest_error = ""
    except (OSError, TypeError, ValueError) as error:
        current_validation_fingerprint = ""
        current_release_tree_fingerprint = ""
        manifest_error = f"{type(error).__name__}: {error}"

    subject_ok = (
        parent.subject_id == VALIDATION_PARENT_SUBJECT_ID
        and parent.subject_kind == VALIDATION_PARENT_SUBJECT_KIND
        # A release verifier consumes the functional parent; it does not
        # require that parent to have already been relabelled as release.
        # ReleaseTreeManifest binding below remains mandatory, so a
        # local_validation parent cannot become a release pass by relabelling.
        and parent.claim_scope in {"full", "local_validation", "release"}
        and parent.result_status == "pass"
        and parent.exit_code == 0
        and not parent.blockers
        and not parent.skipped_checks
    )
    exact_ok = bool(verification and verification.ok and subject_ok)
    validation_binding_ok = bool(
        validation_fingerprint
        and validation_snapshot is not None
        and validation_snapshot.raw_sha256 == validation_fingerprint
        and current_validation_fingerprint == validation_fingerprint
    )
    release_tree_binding_ok = bool(
        release_tree_fingerprint
        and release_tree_snapshot is not None
        and release_tree_snapshot.raw_sha256 == release_tree_fingerprint
        and current_release_tree_fingerprint == release_tree_fingerprint
    )
    if not require_release_tree:
        release_tree_binding_ok = True
    checks = (
        _check(
            "release.parent_receipt_exact",
            exact_ok,
            "the exact full parent and every required child independently verify",
            receipt_id=parent.receipt_id,
            receipt_fingerprint=parent.fingerprint,
            subject_id=parent.subject_id,
            verification=verification.to_dict() if verification else {},
            parent_claim_scope=parent.claim_scope,
            error=load_error,
        ),
        _check(
            "release.validation_input_manifest_binding",
            validation_binding_ok,
            "the parent receipt binds the current ValidationInputManifest",
            expected=validation_fingerprint,
            current=current_validation_fingerprint,
            snapshot_raw_sha256=(
                validation_snapshot.raw_sha256 if validation_snapshot else ""
            ),
            error=manifest_error,
        ),
        _check(
            "release.release_tree_manifest_binding",
            release_tree_binding_ok,
            "the parent receipt binds the exact prospective ReleaseTreeManifest"
            if require_release_tree
            else "release tree binding is deferred to the candidate receipt",
            expected=release_tree_fingerprint,
            current=current_release_tree_fingerprint,
            snapshot_raw_sha256=(
                release_tree_snapshot.raw_sha256 if release_tree_snapshot else ""
            ),
            error=manifest_error,
        ),
    )
    return _ParentBinding(
        parent,
        verification,
        checks,
        validation_fingerprint,
        release_tree_fingerprint,
        artifacts,
    )


def _local_candidate_checks(
    root: Path,
    *,
    selected_version: str,
    installed_version: str | None,
    schema_version: str | None,
    source_path: str | Path | None,
) -> tuple[ReleaseCheck, ...]:
    manifest_flowguard: Mapping[str, Any] = {}
    project_version = ""
    manifest_version = ""
    readme = ""
    changelog = ""
    version_error = ""
    try:
        manifest_path = root / ".flowguard" / "project.toml"
        with manifest_path.open("rb") as handle:
            manifest = tomllib.load(handle)
        flowguard_section = manifest["flowguard"]
        if not isinstance(flowguard_section, Mapping):
            raise TypeError(".flowguard/project.toml [flowguard] must be a table")
        manifest_flowguard = flowguard_section
        manifest_version = str(
            manifest_flowguard.get("adopted_package_version")
            or manifest_flowguard.get("package_version")
            or ""
        )
        readme = (root / "README.md").read_text(encoding="utf-8")
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        project_version = _project_version(root)
    except (OSError, KeyError, TypeError, ValueError) as error:
        version_error = f"{type(error).__name__}: {error}"
    version_ok = bool(selected_version) and not version_error and (
        project_version == selected_version
        and manifest_version == selected_version
        and selected_version in readme
        and (
            f"[{selected_version}]" in changelog
            or re.search(
                rf"(?m)^##\s+v?{re.escape(selected_version)}(?:\s|$)",
                changelog,
            )
            is not None
        )
    )

    resolved_source: Path | None = None
    install_error = ""
    try:
        if installed_version is None:
            installed_version = importlib.metadata.version("flowguard")
        if schema_version is None or source_path is None:
            import flowguard

            schema_version = schema_version or str(flowguard.SCHEMA_VERSION)
            source_path = source_path or str(Path(flowguard.__file__).resolve())
        resolved_source = Path(source_path).resolve()
    except (ImportError, OSError, TypeError, ValueError) as error:
        install_error = f"{type(error).__name__}: {error}"
    expected_schema = str(manifest_flowguard.get("schema_version") or "")
    install_ok = bool(resolved_source) and not install_error and (
        installed_version == selected_version
        and schema_version == expected_schema
        and resolved_source.is_relative_to(root)
    )
    archive_error = ""
    try:
        package_archives = _package_archives(root, selected_version)
    except OSError as error:
        package_archives = ()
        archive_error = f"{type(error).__name__}: {error}"

    return (
        _check(
            "release.version_alignment",
            version_ok,
            "package, project record, README, and changelog versions align",
            project_version=project_version,
            manifest_version=manifest_version,
            error=version_error,
        ),
        _check(
            "release.editable_install",
            install_ok,
            "the active package matches the release version, schema, and source root",
            installed_version=installed_version,
            schema_version=schema_version,
            source_path=str(resolved_source) if resolved_source else "",
            error=install_error or version_error,
        ),
        _check(
            "release.source_only_authority",
            not package_archives and not archive_error,
            "the source tag is the sole release authority and no version-matching package archive is present",
            package_archives=[path.name for path in package_archives],
            error=archive_error,
        ),
    )


def _target_candidate_checks(
    root: Path,
    *,
    target: ReleaseTarget,
    parent: EvidenceReceipt | None,
) -> tuple[ReleaseCheck, ...]:
    """Validate only the explicit target contract, not FlowGuard metadata."""

    required_paths: list[str] = []
    missing_paths: list[str] = []
    for relative in target.required_source_paths:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            missing_paths.append(relative)
            continue
        required_paths.append(relative)
        if not candidate.is_file():
            missing_paths.append(relative)
    source_ok = not missing_paths

    covered = set(parent.covered_obligations) if parent is not None else set()
    required_checks_ok = all(item in covered for item in target.required_check_ids)

    asset_results: list[dict[str, str]] = []
    assets_ok = target.distribution_kind == "source_only" or bool(target.assets)
    if target.distribution_kind == "source_and_assets":
        for relative, expected_digest in target.assets:
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                assets_ok = False
                asset_results.append({"path": relative, "status": "outside-root"})
                continue
            if not candidate.is_file():
                assets_ok = False
                asset_results.append({"path": relative, "status": "missing"})
                continue
            actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            digest_ok = not expected_digest or actual_digest == expected_digest
            assets_ok = assets_ok and digest_ok
            asset_results.append(
                {
                    "path": relative,
                    "status": "pass" if digest_ok else "digest-mismatch",
                    "expected": expected_digest,
                    "actual": actual_digest,
                }
            )

    return (
        _check(
            "release.target_identity",
            bool(target.target_id and target.version and target.tag),
            "the explicit target descriptor supplies the release identity",
            target_id=target.target_id,
            version=target.version,
            tag=target.tag,
            repository=target.repository,
            default_branch=target.default_branch,
            distribution_kind=target.distribution_kind,
        ),
        _check(
            "release.target_source_paths",
            source_ok,
            "all target-declared release source paths exist inside the target root",
            required_paths=required_paths,
            missing_paths=missing_paths,
        ),
        _check(
            "release.target_required_checks",
            required_checks_ok,
            "the functional parent covers every target-declared release check",
            required_check_ids=list(target.required_check_ids),
            covered_obligations=sorted(covered),
        ),
        _check(
            "release.target_assets",
            assets_ok,
            "target distribution assets match the explicit source/assets policy",
            distribution_kind=target.distribution_kind,
            assets=asset_results,
        ),
    )


def _model_authority_git_reachability_check(root: Path) -> ReleaseCheck:
    try:
        required_paths = model_authority_release_paths(root)
        extraction_error = ""
    except (OSError, KeyError, TypeError, ValueError) as error:
        required_paths = ()
        extraction_error = f"{type(error).__name__}: {error}"
    if extraction_error:
        return _check(
            "release.model_authority_git_reachability",
            False,
            "the selected observed model authority must expose a valid input closure",
            required_paths=[],
            missing_paths=[],
            error=extraction_error,
        )
    if not required_paths:
        return _check(
            "release.model_authority_git_reachability",
            True,
            "the project declares no observed model-authority input closure",
            required_paths=[],
            missing_paths=[],
            error="",
        )

    tracked_result = _command_runner(
        ("git", "ls-files", "-z"),
        root,
    )
    tracked_paths = {
        path.replace("\\", "/")
        for path in tracked_result.stdout.split("\0")
        if path
    }
    missing_paths = tuple(
        path for path in required_paths if path not in tracked_paths
    )
    git_error = (
        tracked_result.stderr.strip()
        if tracked_result.returncode != 0
        else ""
    )
    return _check(
        "release.model_authority_git_reachability",
        tracked_result.returncode == 0 and not missing_paths,
        "the selected observed snapshot and every resolved input are Git-tracked",
        required_paths=list(required_paths),
        missing_paths=list(missing_paths),
        error=git_error,
    )


def verify_local_candidate(
    root: str | Path,
    *,
    parent_receipt: EvidenceReceipt | str | Path,
    receipt_root: str | Path,
    version: str | None = None,
    installed_version: str | None = None,
    schema_version: str | None = None,
    source_path: str | Path | None = None,
    target: ReleaseTarget | Mapping[str, Any] | None = None,
) -> ReleaseVerificationReceipt:
    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    target_obj = (
        target
        if isinstance(target, ReleaseTarget)
        else ReleaseTarget.from_dict(target)
        if isinstance(target, Mapping)
        else None
    )
    version_error = ""
    try:
        selected_version = (target_obj.version if target_obj else None) or version or _project_version(root_path)
    except (OSError, KeyError, TypeError, ValueError) as error:
        selected_version = version or ""
        version_error = f"{type(error).__name__}: {error}"
    tag = target_obj.tag if target_obj else (f"v{selected_version}" if selected_version else "")
    binding = _load_parent_binding(
        root_path,
        parent_receipt=parent_receipt,
        receipt_root=receipt_root_path,
        require_release_tree=target_obj is None,
    )
    if target_obj is None:
        checks = binding.checks + _local_candidate_checks(
            root_path,
            selected_version=selected_version,
            installed_version=installed_version,
            schema_version=schema_version,
            source_path=source_path,
        ) + (_model_authority_git_reachability_check(root_path),)
    else:
        checks = binding.checks + _target_candidate_checks(
            root_path,
            target=target_obj,
            parent=binding.receipt,
        )
        if version and version != target_obj.version:
            checks += (_check("release.target_version_argument", False, "--version disagrees with target descriptor", expected=target_obj.version, actual=version),)
        if target_obj.repository:
            # Repository is checked again at the published phase; recording it
            # here keeps the candidate self-describing without consulting Git.
            checks += (_check("release.target_repository_declared", True, "target repository is explicitly declared", repository=target_obj.repository),)
        try:
            candidate_tree = manifest_fingerprint(release_tree_manifest(root_path))
        except (OSError, TypeError, ValueError) as error:
            candidate_tree = ""
            checks += (_check("release.candidate_tree_manifest", False, "candidate tree could not be captured", error=f"{type(error).__name__}: {error}"),)
        else:
            checks += (_check("release.candidate_tree_manifest", bool(candidate_tree), "candidate binds the prospective release tree", fingerprint=candidate_tree),)
    if version_error:
        checks = checks + (
            _check(
                "release.project_version_input",
                False,
                "the project version metadata must be readable",
                error=version_error,
            ),
        )
    parent_id = binding.receipt.receipt_id if binding.receipt else ""
    parent_fingerprint = binding.receipt.fingerprint if binding.receipt else ""
    return ReleaseVerificationReceipt(
        phase=RELEASE_PHASE_LOCAL_CANDIDATE,
        version=selected_version,
        tag=tag,
        checks=checks,
        parent_receipt_id=parent_id,
        parent_receipt_fingerprint=parent_fingerprint,
        validation_input_manifest_fingerprint=(
            binding.validation_input_manifest_fingerprint
        ),
        release_tree_manifest_fingerprint=(
            binding.release_tree_manifest_fingerprint
            or next((check.details.get("fingerprint", "") for check in checks if check.check_id == "release.candidate_tree_manifest"), "")
        ),
        upstream_receipt_ids=(parent_id,) if parent_id else (),
        artifact_paths=binding.artifact_paths,
        target_id=target_obj.target_id if target_obj else "",
        target_fingerprint=release_target_fingerprint(target_obj) if target_obj else "",
    )


def verify_tagged_release(
    root: str | Path,
    *,
    parent_receipt: EvidenceReceipt | str | Path,
    receipt_root: str | Path,
    version: str | None = None,
    installed_version: str | None = None,
    schema_version: str | None = None,
    source_path: str | Path | None = None,
    target: ReleaseTarget | Mapping[str, Any] | None = None,
    candidate_receipt: str | Path | ReleaseVerificationReceipt | None = None,
    command_runner: CommandRunner = _command_runner,
) -> ReleaseVerificationReceipt:
    root_path = Path(root).resolve()
    target_obj = (
        target
        if isinstance(target, ReleaseTarget)
        else ReleaseTarget.from_dict(target)
        if isinstance(target, Mapping)
        else None
    )
    supplied_candidate_receipt_id = ""
    if candidate_receipt is not None:
        local = (
            candidate_receipt
            if isinstance(candidate_receipt, ReleaseVerificationReceipt)
            else load_release_verification_receipt(candidate_receipt)
        )
        supplied_candidate_receipt_id = local.receipt_id
        candidate_ok = (
            local.phase == RELEASE_PHASE_LOCAL_CANDIDATE
            and local.ok
            and (target_obj is None or local.target_fingerprint == release_target_fingerprint(target_obj))
            and (target_obj is None or local.target_id == target_obj.target_id)
            and (version is None or local.version == version)
        )
        local = replace_release_receipt_checks(
            local,
            (_check("release.candidate_receipt_exact", candidate_ok, "the supplied local candidate receipt is immutable and matches the requested target", candidate_receipt=str(candidate_receipt))),
        )
    else:
        local = verify_local_candidate(
            root_path,
            parent_receipt=parent_receipt,
            receipt_root=receipt_root,
            version=version,
            installed_version=installed_version,
            schema_version=schema_version,
            source_path=source_path,
            target=target_obj,
        )
    tag_ref = f"refs/tags/{local.tag}"
    local_tag_object = command_runner(
        (
            "git",
            "show-ref",
            "--verify",
            "--hash",
            tag_ref,
        ),
        root_path,
    )
    tag_object = (
        local_tag_object.stdout.strip()
        if local_tag_object.returncode == 0
        else ""
    )
    local_tag = command_runner(
        (
            "git",
            "rev-list",
            "-n",
            "1",
            tag_ref,
        ),
        root_path,
    )
    commit = (
        local_tag.stdout.strip()
        if tag_object and local_tag.returncode == 0
        else ""
    )
    committed_tree_fingerprint = ""
    tree_error = ""
    if commit:
        try:
            committed_tree_fingerprint = manifest_fingerprint(
                release_tree_manifest(root_path, revision=commit)
            )
        except (OSError, TypeError, ValueError) as error:
            tree_error = f"{type(error).__name__}: {error}"
    checks = local.checks + (
        _check(
            "release.local_tag_commit",
            bool(tag_object) and bool(commit),
            "the exact local tag ref resolves to one committed release tree",
            tag_ref=tag_ref,
            tag_object=tag_object,
            commit=commit,
            show_ref_stderr=local_tag_object.stderr.strip(),
            resolve_stderr=local_tag.stderr.strip(),
        ),
        _check(
            "release.committed_tree_manifest",
            bool(commit)
            and bool(local.release_tree_manifest_fingerprint)
            and committed_tree_fingerprint
            == local.release_tree_manifest_fingerprint,
            "the committed tree matches the immutable candidate release tree",
            expected=local.release_tree_manifest_fingerprint,
            committed=committed_tree_fingerprint,
            error=tree_error,
        ),
    )
    return ReleaseVerificationReceipt(
        phase=RELEASE_PHASE_TAG,
        version=local.version,
        tag=local.tag,
        commit=commit,
        checks=checks,
        parent_receipt_id=local.parent_receipt_id,
        parent_receipt_fingerprint=local.parent_receipt_fingerprint,
        validation_input_manifest_fingerprint=(
            local.validation_input_manifest_fingerprint
        ),
        release_tree_manifest_fingerprint=(
            local.release_tree_manifest_fingerprint
        ),
        # Keep the upstream edge pointed at the immutable candidate artifact,
        # not at the derived tag receipt after the phase-local check is added.
        upstream_receipt_ids=(supplied_candidate_receipt_id or local.receipt_id,),
        artifact_paths=local.artifact_paths,
        target_id=local.target_id,
        target_fingerprint=local.target_fingerprint,
    )


def _parse_github_repository(remote_url: str) -> str:
    match = re.search(
        r"github\.com[/:]([^/\s]+/[^/\s]+?)(?:\.git)?$",
        remote_url.strip(),
    )
    return match.group(1) if match else ""


def _remote_tag_commit(output: str, tag: str) -> tuple[str, dict[str, str]]:
    refs: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            refs[fields[1]] = fields[0]
    tag_ref = f"refs/tags/{tag}"
    return refs.get(f"{tag_ref}^{{}}", ""), refs


def verify_published_release(
    root: str | Path,
    *,
    parent_receipt: EvidenceReceipt | str | Path,
    receipt_root: str | Path,
    version: str | None = None,
    repository: str | None = None,
    installed_version: str | None = None,
    schema_version: str | None = None,
    source_path: str | Path | None = None,
    target: ReleaseTarget | Mapping[str, Any] | None = None,
    candidate_receipt: str | Path | ReleaseVerificationReceipt | None = None,
    command_runner: CommandRunner = _command_runner,
) -> ReleaseVerificationReceipt:
    root_path = Path(root).resolve()
    target_obj = (
        target
        if isinstance(target, ReleaseTarget)
        else ReleaseTarget.from_dict(target)
        if isinstance(target, Mapping)
        else None
    )
    tagged = verify_tagged_release(
        root_path,
        parent_receipt=parent_receipt,
        receipt_root=receipt_root,
        version=version,
        installed_version=installed_version,
        schema_version=schema_version,
        source_path=source_path,
        target=target_obj,
        candidate_receipt=candidate_receipt,
        command_runner=command_runner,
    )

    remote_result = command_runner(
        ("git", "remote", "get-url", "origin"),
        root_path,
    )
    detected_repository = (
        _parse_github_repository(remote_result.stdout)
        if remote_result.returncode == 0
        else ""
    )
    selected_repository = repository or (target_obj.repository if target_obj else "") or detected_repository
    repository_ok = bool(selected_repository) and (
        not (repository or (target_obj.repository if target_obj else ""))
        or selected_repository == detected_repository
    )

    tag_ref = f"refs/tags/{tagged.tag}"
    peeled_ref = f"{tag_ref}^{{}}"
    remote_tag = command_runner(
        (
            "git",
            "ls-remote",
            "--tags",
            "origin",
            f"{tag_ref}*",
        ),
        root_path,
    )
    remote_commit, remote_refs = _remote_tag_commit(
        remote_tag.stdout,
        tagged.tag,
    )
    remote_tag_ok = (
        remote_tag.returncode == 0
        and bool(remote_refs.get(tag_ref))
        and bool(remote_refs.get(peeled_ref))
        and bool(tagged.commit)
        and remote_commit == tagged.commit
    )

    release_view = command_runner(
        (
            "gh",
            "release",
            "view",
            tagged.tag,
            "--repo",
            selected_repository,
            "--json",
            "tagName,isDraft,isPrerelease,url,targetCommitish,assets,publishedAt",
        ),
        root_path,
    )
    release_payload: dict[str, Any] = {}
    if release_view.returncode == 0:
        try:
            loaded = json.loads(release_view.stdout)
            if isinstance(loaded, dict):
                release_payload = loaded
        except json.JSONDecodeError:
            release_payload = {}
    assets = release_payload.get("assets")
    asset_names = (
        tuple(
            sorted(
                str(asset.get("name"))
                for asset in assets
                if isinstance(asset, Mapping) and asset.get("name")
            )
        )
        if isinstance(assets, list)
        else ()
    )
    target_commitish = str(release_payload.get("targetCommitish") or "")
    release_ok = (
        release_view.returncode == 0
        and release_payload.get("tagName") == tagged.tag
        and release_payload.get("isDraft") is False
        and release_payload.get("isPrerelease") is False
        and bool(release_payload.get("publishedAt"))
        and isinstance(assets, list)
        and not assets
        and target_commitish in {tagged.tag, tagged.commit}
        and bool(tagged.commit)
    )

    checks = tagged.checks + (
        _check(
            "release.github_repository",
            repository_ok,
            "the configured origin resolves to the expected GitHub repository",
            repository=selected_repository,
            origin=remote_result.stdout.strip(),
        ),
        _check(
            "release.remote_peeled_tag",
            remote_tag_ok,
            "the peeled remote tag resolves to the exact local release commit",
            local_commit=tagged.commit,
            remote_commit=remote_commit,
            remote_refs=remote_refs,
            stderr=remote_tag.stderr.strip(),
        ),
        _check(
            "release.github_release",
            release_ok,
            "the GitHub Release is published, final, source-only, and bound to the release commit",
            assets=list(asset_names),
            is_draft=release_payload.get("isDraft"),
            is_prerelease=release_payload.get("isPrerelease"),
            published_at=release_payload.get("publishedAt"),
            target_commitish=target_commitish,
            tag_name=release_payload.get("tagName"),
        ),
    )
    return ReleaseVerificationReceipt(
        phase=RELEASE_PHASE_PUBLISHED,
        version=tagged.version,
        tag=tagged.tag,
        commit=tagged.commit,
        checks=checks,
        parent_receipt_id=tagged.parent_receipt_id,
        parent_receipt_fingerprint=tagged.parent_receipt_fingerprint,
        validation_input_manifest_fingerprint=(
            tagged.validation_input_manifest_fingerprint
        ),
        release_tree_manifest_fingerprint=(
            tagged.release_tree_manifest_fingerprint
        ),
        upstream_receipt_ids=(tagged.receipt_id,),
        artifact_paths=tagged.artifact_paths,
        release_url=str(release_payload.get("url") or ""),
        target_id=tagged.target_id,
        target_fingerprint=tagged.target_fingerprint,
    )


__all__ = [
    "RELEASE_PHASE_LOCAL_CANDIDATE",
    "RELEASE_PHASE_PUBLISHED",
    "RELEASE_PHASE_TAG",
    "RELEASE_PHASES",
    "RELEASE_VERIFICATION_SCHEMA",
    "ReleaseCheck",
    "ReleaseTarget",
    "ReleaseVerificationReceipt",
    "load_release_verification_receipt",
    "release_target_fingerprint",
    "save_release_verification_receipt",
    "verify_local_candidate",
    "verify_published_release",
    "verify_tagged_release",
]
