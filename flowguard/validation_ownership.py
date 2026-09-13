"""Content-addressed execution ownership for FlowGuard validation.

The module is deliberately independent from OpenSpec providers.  It freezes
native FlowGuard owner inputs, verifies immutable receipts against a freshly
derived current context, and exposes only three execution dispositions:
``execute``, ``reuse_current``, or ``blocked``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import tempfile
import time
import tomllib
from typing import Any, Iterable, Mapping, Sequence

from ._hashing import sha256_bytes as _sha256_bytes
from .observation_metrics import InvocationMetrics
from .evidence_receipts import (
    ChildReceiptRequirement,
    ConsumedChildReceipt,
    EvidenceReceipt,
    InputSnapshot,
    RECEIPT_STATUS_PASS,
    ReceiptVerificationContext,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    list_evidence_receipts,
    list_latest_evidence_receipts,
    load_evidence_receipt,
    save_evidence_receipt,
    snapshot_bytes,
    tokenize_command,
    verify_evidence_receipt,
)
from .source_identity import (
    functional_source_fingerprint,
    functional_source_payload,
    source_file_fingerprint,
)
from .process_supervision import run_supervised_bytes
from .runtime_artifacts import (
    classify_runtime_artifact,
    is_governed_source_in_runtime_cache,
    is_release_excluded_path,
)
from .validation_results import ValidationChildResult


OWNER_EXECUTE = "execute"
OWNER_REUSE_CURRENT = "reuse_current"
OWNER_BLOCKED = "blocked"
OWNER_DISPOSITIONS = (OWNER_EXECUTE, OWNER_REUSE_CURRENT, OWNER_BLOCKED)
OWNER_RECEIPT_SCOPE = "full"
OWNER_RECEIPT_KIND = "validation_owner"
OWNER_RECEIPT_SCHEMA = "flowguard.validation_owner_receipt.v2"
PARENT_CURRENT_SCHEMA = "flowguard.validation_parent_current.v1"
OWNER_PLAN_SCHEMA = "flowguard.validation_owner_plan.v1"
DEFAULT_TERMINATION_POLICY = "terminate_grace_force_kill_confirm_zero_descendants"
VALIDATION_CLAIM_SCOPE_LOCAL = "local_validation"
VALIDATION_CLAIM_SCOPE_RELEASE = "release"
VALIDATION_CLAIM_SCOPES = frozenset(
    {VALIDATION_CLAIM_SCOPE_LOCAL, VALIDATION_CLAIM_SCOPE_RELEASE}
)
NESTED_OWNER_SELECTION_ENV = "FLOWGUARD_SELECTED_OWNER_IDS"
GIT_QUERY_TIMEOUT_SECONDS = 30.0
SOURCE_OBSERVATION_TIMEOUT_SECONDS = 120.0


class GitQueryTimeout(ValueError):
    """Fail-closed timeout for one bounded Git/source observation.

    Git helpers historically returned bytes and raised ``ValueError`` for a
    failed query.  Keep that API shape while carrying a machine-readable code
    and bounded diagnostic fields for callers that need to distinguish a
    per-query timeout from an exhausted observation budget.
    """

    def __init__(
        self,
        *,
        code: str,
        query_category: str,
        elapsed_seconds: float,
        cleanup_confirmed: bool,
        terminal_reason: str,
    ) -> None:
        if code not in {"git_query_timeout", "source_observation_timeout"}:
            raise ValueError(f"unsupported Git timeout code: {code}")
        self.code = code
        self.query_category = query_category
        self.elapsed_seconds = max(0.0, float(elapsed_seconds))
        self.cleanup_confirmed = bool(cleanup_confirmed)
        self.terminal_reason = terminal_reason
        super().__init__(
            f"{code}: query_category={query_category} "
            f"elapsed_seconds={self.elapsed_seconds:.3f} "
            f"cleanup_confirmed={str(self.cleanup_confirmed).lower()} "
            f"terminal_reason={terminal_reason}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "query_category": self.query_category,
            "elapsed_seconds": self.elapsed_seconds,
            "cleanup_confirmed": self.cleanup_confirmed,
            "terminal_reason": self.terminal_reason,
        }


class GitQueryCleanupUnconfirmed(ValueError):
    """A supervised Git child did not prove a zero-descendant terminal state."""

    def __init__(
        self,
        *,
        query_category: str,
        elapsed_seconds: float,
        terminal_reason: str,
    ) -> None:
        self.code = "git_query_cleanup_unconfirmed"
        self.query_category = query_category
        self.elapsed_seconds = max(0.0, float(elapsed_seconds))
        self.cleanup_confirmed = False
        self.terminal_reason = terminal_reason
        super().__init__(
            f"{self.code}: query_category={query_category} "
            f"elapsed_seconds={self.elapsed_seconds:.3f} "
            f"cleanup_confirmed=false terminal_reason={terminal_reason}"
        )


class GitQueryAborted(ValueError):
    """A Git child was cancelled/interrupted after bounded cleanup."""

    def __init__(
        self,
        *,
        query_category: str,
        elapsed_seconds: float,
        terminal_reason: str,
    ) -> None:
        self.code = "git_query_aborted"
        self.query_category = query_category
        self.elapsed_seconds = max(0.0, float(elapsed_seconds))
        self.cleanup_confirmed = True
        self.terminal_reason = terminal_reason
        super().__init__(
            f"{self.code}: query_category={query_category} "
            f"elapsed_seconds={self.elapsed_seconds:.3f} "
            f"cleanup_confirmed=true terminal_reason={terminal_reason}"
        )


@dataclass
class _GitObservationBudget:
    """One invocation-local deadline shared by all Git child queries."""

    timeout_seconds: float = SOURCE_OBSERVATION_TIMEOUT_SECONDS
    started_at: float = field(default_factory=lambda: time.monotonic())

    def __post_init__(self) -> None:
        self.timeout_seconds = float(self.timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("Git observation timeout must be positive")

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.timeout_seconds - self.elapsed_seconds)

    def reserve(self, query_category: str) -> float:
        remaining = self.remaining_seconds
        if remaining <= 0:
            raise GitQueryTimeout(
                code="source_observation_timeout",
                query_category=query_category,
                elapsed_seconds=self.elapsed_seconds,
                cleanup_confirmed=True,
                terminal_reason="observation_deadline_before_launch",
            )
        return min(GIT_QUERY_TIMEOUT_SECONDS, remaining)


_CURRENT_GIT_OBSERVATION: ContextVar[_GitObservationBudget | None] = ContextVar(
    "flowguard_current_git_observation",
    default=None,
)


@contextmanager
def git_observation_budget(
    timeout_seconds: float = SOURCE_OBSERVATION_TIMEOUT_SECONDS,
):
    """Share one finite Git deadline across a read-only observation.

    Nested callers reuse the active budget.  This lets a top-level source or
    release observation bound all of its Git path queries without changing the
    existing bytes-returning helper signatures.
    """

    current = _CURRENT_GIT_OBSERVATION.get()
    if current is not None:
        yield current
        return
    budget = _GitObservationBudget(timeout_seconds)
    token = _CURRENT_GIT_OBSERVATION.set(budget)
    try:
        yield budget
    finally:
        _CURRENT_GIT_OBSERVATION.reset(token)


def _bounded_git_observation(function):
    """Decorate a public observation boundary without duplicating its body."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        with git_observation_budget():
            return function(*args, **kwargs)

    return wrapped

_OUTPUT_PREFIXES = (
    ".flowguard/evidence/",
    ".flowguard/history/",
    ".flowguard/run_artifacts/",
    ".flowguard/models/authority/snapshots/",
    # Authority snapshots/revisions/activation records are immutable
    # control-plane evidence.  They are consumed through the current model
    # authority identity, not treated as ordinary source files on every owner
    # freshness scan.  Keeping them in the source inventory made a broad
    # ``.flowguard/**/*`` observation hash thousands of historical revisions
    # and repeatedly reopen otherwise settled validation cycles.
    ".flowguard/models/authority/revisions/",
    ".flowguard/models/authority/activations/",
    ".flowguard/models/authority/rollbacks/",
    ".flowguard/models/authority/bootstraps/",
    ".flowguard/models/authority/rollback-contracts/",
    ".flowguard/models/authority/boundary-contracts/",
    ".flowguard/structure/reverse-surfaces/",
    ".flowguard/model-system/store/",
    "tmp/",
)
_OUTPUT_SUFFIXES = (
    "/verification-report.json",
    "/result.json",
    "/CURRENT.json",
    ".pyc",
)
_OUTPUT_BASENAMES = {
    ".DS_Store",
    "adoption_log.jsonl",
    "skillguard_progress_ledger.jsonl",
}

# Git pathspec exclusions are kept in the same ownership layer as the
# fallback classifier.  Tracked run objects are just as non-authoritative as
# their untracked siblings; omitting them only from ``--others`` would let a
# staged run artifact refresh a source observation.
_GIT_OUTPUT_EXCLUDES = (
    ":(top,glob,exclude).flowguard/evidence/**",
    ":(top,glob,exclude).flowguard/history/**",
    ":(top,glob,exclude).flowguard/run_artifacts/**",
    ":(top,glob,exclude).flowguard/work/flowguard/**",
    ":(top,glob,exclude).flowguard/models/authority/snapshots/**",
    ":(top,glob,exclude).flowguard/models/authority/revisions/**",
    ":(top,glob,exclude).flowguard/models/authority/activations/**",
    ":(top,glob,exclude).flowguard/models/authority/bootstraps/**",
    ":(top,glob,exclude).flowguard/models/authority/rollbacks/**",
    ":(top,glob,exclude).flowguard/models/authority/rollback-contracts/**",
    ":(top,glob,exclude).flowguard/models/authority/boundary-contracts/**",
    ":(top,glob,exclude).flowguard/models/authority/staging/**",
    ":(top,glob,exclude).flowguard/structure/reverse-surfaces/**",
    ":(top,glob,exclude).flowguard/model-system/store/**",
    ":(top,glob,exclude)work/flowguard/**",
    ":(top,glob,exclude)tmp/**",
)

# A new observation hashes its finite selected source set afresh. File size and
# timestamps cannot prove that source bytes are unchanged on Windows, where a
# rewrite can restore both metadata values. Any reuse must happen through a
# verified immutable ValidationObservation/receipt rather than this helper.

# Validation-owner identity must not include the transient directory selected
# for one execution.  The full coordinator deliberately creates a fresh
# output directory for every invocation; treating that directory as semantic
# input makes the second invocation look like a different owner DAG and
# prevents exact-parent reuse.  Keep this normalization local to the owner
# identity layer so ordinary receipt commands still retain their exact
# execution arguments where they are useful for diagnostics.
_EVIDENCE_OUTPUT_OPTIONS = frozenset(
    {
        "--output-dir",
        "--output-directory",
        "--receipt-dir",
        "--model-receipt-dir",
    }
)
_EVIDENCE_RUN_TOKEN = "<EVIDENCE_RUN>"
_RESOURCE_ONLY_OPTIONS = frozenset(
    {
        "--timeout",
        "--model-timeout",
        "--collect-timeout",
        "--shard-timeout",
        "--run-timeout",
        "--gate-timeout",
    }
)
_RESOURCE_VALUE_TOKEN = "<RESOURCE_POLICY>"


def _canonical_owner_command(
    command: Sequence[str],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    resource_options: Sequence[str] = (),
) -> tuple[str, ...]:
    """Tokenize one owner command while eliding run-scoped output paths."""

    values = list(
        tokenize_command(
            command,
            workspace_root=workspace_root,
        )
    )
    declared_resource_options = frozenset(
        str(item).strip()
        for item in resource_options
        if str(item).strip() in _RESOURCE_ONLY_OPTIONS
    )
    normalized: list[str] = []
    index = 0
    while index < len(values):
        value = values[index]
        if value in declared_resource_options:
            normalized.append(value)
            if index + 1 < len(values):
                normalized.append(_RESOURCE_VALUE_TOKEN)
                index += 2
            else:
                normalized.append(_RESOURCE_VALUE_TOKEN)
                index += 1
            continue
        matched_resource_option = next(
            (
                option
                for option in declared_resource_options
                if value.startswith(option + "=")
            ),
            None,
        )
        if matched_resource_option is not None:
            normalized.append(matched_resource_option + "=" + _RESOURCE_VALUE_TOKEN)
            index += 1
            continue
        if value in _EVIDENCE_OUTPUT_OPTIONS:
            normalized.append(value)
            if index + 1 < len(values):
                normalized.append(_EVIDENCE_RUN_TOKEN)
                index += 2
            else:
                index += 1
            continue
        matched_option = next(
            (
                option
                for option in _EVIDENCE_OUTPUT_OPTIONS
                if value.startswith(option + "=")
            ),
            None,
        )
        normalized.append(
            matched_option + "=" + _EVIDENCE_RUN_TOKEN
            if matched_option is not None
            else value
        )
        index += 1
    return tuple(normalized)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def selected_owner_ids(value: str | Sequence[str] | None = None) -> frozenset[str]:
    """Return the explicit owner selection carried by a parent invocation.

    Nested runners must not rediscover or relaunch an owner that the outer
    plan already selected.  The environment projection is intentionally
    simple and deterministic (comma-separated owner ids); callers may pass a
    sequence directly in tests.  Empty selection means that no parent plan
    has claimed a child and therefore preserves the historical standalone
    runner behaviour.
    """

    raw: Sequence[str] | str | None = value
    if raw is None:
        raw = os.environ.get(NESTED_OWNER_SELECTION_ENV, "")
    if isinstance(raw, str):
        values = raw.replace(";", ",").split(",")
    else:
        values = raw
    return frozenset(
        str(item).strip()
        for item in (values or ())
        if str(item).strip()
    )


def nested_owner_launch_allowed(
    parent_owner_id: str,
    child_owner_id: str,
    *,
    selected: str | Sequence[str] | None = None,
) -> bool:
    """Return whether a nested child may be launched by its aggregate.

    Matching accepts the canonical owner spelling plus the explicit
    ``model:`` projection used by model-regression plans.  This is a bounded
    identity normalization, not fuzzy discovery; any other spelling remains
    unselected and is therefore safe for a standalone parent invocation.
    """

    del parent_owner_id  # retained for a stable, self-documenting API
    child = str(child_owner_id).strip()
    if not child:
        return False
    selected_ids = selected_owner_ids(selected)
    if not selected_ids:
        return True
    candidates = {child}
    if child.startswith("model:"):
        candidates.add(child.removeprefix("model:"))
    else:
        candidates.add(f"model:{child}")
    return not bool(candidates & selected_ids)


def assert_nested_owner_launch_allowed(
    parent_owner_id: str,
    child_owner_id: str,
    *,
    selected: str | Sequence[str] | None = None,
) -> None:
    """Fail closed when an outer plan already owns the child execution."""

    if not nested_owner_launch_allowed(
        parent_owner_id,
        child_owner_id,
        selected=selected,
    ):
        raise ValueError(
            "nested owner is selected by the outer plan; consume its current "
            f"receipt instead of relaunching: parent={parent_owner_id} "
            f"child={child_owner_id}"
        )


def _content_addressed_receipt_id(prefix: str, receipt: EvidenceReceipt) -> str:
    payload = receipt.to_dict()
    payload["receipt_id"] = "<CONTENT_ADDRESS>"
    digest = fingerprint_value(payload).split(":", 1)[1]
    return f"{prefix}:{digest[:32]}"


def assert_validation_owner_receipt_integrity(
    receipt: EvidenceReceipt,
) -> None:
    """Reject a validation-owner receipt whose id is not its exact content address."""

    expected = _content_addressed_receipt_id(
        f"receipt:validation-owner:{receipt.subject_id.removeprefix('validation-owner:')}",
        receipt,
    )
    if receipt.receipt_id != expected:
        raise ValueError(
            f"validation owner receipt content address mismatch: {receipt.receipt_id}"
        )


def _assert_owner_receipt_integrity(receipt: EvidenceReceipt) -> None:
    """Internal spelling retained for existing validation-owner consumers."""

    assert_validation_owner_receipt_integrity(receipt)


def _package_version() -> str:
    try:
        return importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        return "source"


def _receipt_result_status(status: str) -> str:
    return {
        "pass": "pass",
        "fail": "fail",
        "blocked": "blocked",
        "partial": "scoped",
        "invalid_input": "error",
        "timeout": "error",
        "cancelled": "error",
        "internal_error": "error",
    }.get(status, "error")


def _is_evidence_output(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    try:
        if classify_runtime_artifact(normalized) is not None:
            return True
    except ValueError:
        # Unsafe path spellings are never made safe by an output exclusion;
        # the caller's containment/path gate must report them.
        pass
    if any(normalized.startswith(prefix) for prefix in _OUTPUT_PREFIXES):
        return True
    if any(normalized.endswith(suffix) for suffix in _OUTPUT_SUFFIXES):
        return True
    if Path(normalized).name in _OUTPUT_BASENAMES or Path(normalized).name == (
        "release-target.json"
    ):
        return True
    if "/__pycache__/" in f"/{normalized}/":
        return True
    if "/reports/current_" in normalized or "/ai_judgments/current_" in normalized:
        return True
    return False


def _glob_pattern_variants(
    pattern: str,
    *,
    max_depth: int,
) -> tuple[str, ...]:
    """Return Path.glob-compatible recursive variants for candidate matching."""

    pending = [str(pattern).replace("\\", "/")]
    variants: set[str] = set()
    while pending:
        current = pending.pop()
        if current in variants:
            continue
        variants.add(current)
        marker = current.find("**/")
        if marker >= 0:
            prefix = current[:marker]
            suffix = current[marker + 3 :]
            pending.extend(
                prefix + ("*/" * depth) + suffix
                for depth in range(max_depth + 1)
            )
    return tuple(sorted(variants))


def _matches_declared_pattern(relative: str, pattern: str) -> bool:
    # ``PurePath.match`` right-anchors relative patterns, which would make
    # ``flowguard/**/*.py`` also match ``.agents/skills/flowguard/x.py``.
    # Validation manifests are repository-root relative, so anchor both sides
    # under a synthetic root before applying the expanded recursive variants.
    candidate = PurePosixPath("/__flowguard_manifest_root__") / relative
    return any(
        candidate.match(f"/__flowguard_manifest_root__/{variant}")
        for variant in _glob_pattern_variants(
            pattern,
            max_depth=len(candidate.parts),
        )
    )


@_bounded_git_observation
def _git_candidate_paths(
    root: Path,
    patterns: Sequence[str] = (),
) -> tuple[str, ...] | None:
    """List candidates inside the declared input boundary.

    A repository-wide ``git ls-files --others`` is deceptively expensive on a
    long-lived FlowGuard checkout: immutable receipts, run objects, and other
    evidence are deliberately untracked and can number in the thousands.  A
    validation observation already has its exact input patterns, so pass those
    as Git pathspecs and never enumerate unrelated output trees.  When no
    usable pattern is supplied, the tracked index remains the safe bounded
    fallback; callers will not accidentally turn an empty observation into a
    whole-workspace scan.
    """
    normalized_patterns = tuple(
        dict.fromkeys(
            str(item).replace("\\", "/")
            for item in patterns
            if str(item).strip()
            and not str(item).lstrip().startswith(("<", "["))
        )
    )
    # Git's default pathspec treats ``**/`` as one-or-more directories,
    # whereas the declared validation glob (and pathlib) treats it as
    # zero-or-more.  Use Git's explicit glob magic so ``flowguard/**/*.py``
    # includes both ``flowguard/direct.py`` and deeper files while retaining
    # the bounded pathspec traversal.
    git_patterns = tuple(
        pattern
        if pattern.startswith(":(") or not any(token in pattern for token in ("*", "?", "["))
        else f":(glob){pattern}"
        for pattern in normalized_patterns
    )
    try:
        if not normalized_patterns:
            raw = _git_bytes(root, "ls-files", "-z", "--cached")
            return tuple(
                sorted(
                    {
                        item.decode("utf-8").replace("\\", "/")
                        for item in raw.split(b"\0")
                        if item
                        and not _is_evidence_output(
                            item.decode("utf-8").replace("\\", "/")
                        )
                    }
                )
            )

        # ``git ls-files`` does not form a union when ``--cached`` and
        # ``--others`` are supplied together; it returns an empty result on
        # this repository.  Observe the tracked and untracked halves as two
        # bounded pathspec queries, then union their relative paths.  The
        # output-only exclusions remain on the untracked query so a broad
        # selector cannot reopen immutable evidence/history/run trees.
        tracked = _git_bytes_from_pathspec_file(
            root,
            ("ls-files", "-z", "--cached"),
            (*git_patterns, *_GIT_OUTPUT_EXCLUDES),
        )
        untracked = _git_bytes_from_pathspec_file(
            root,
            ("ls-files", "-z", "--others", "--exclude-standard"),
            (
                *git_patterns,
                # Runtime evidence and controlled workspaces are valid to
                # retain during an invocation, but they are never current
                # source inputs.  Excluding them at Git's traversal boundary
                # is materially cheaper than enumerating a large evidence
                # tree and discarding the same paths after the fact.  Keep
                # this list aligned with ``_OUTPUT_PREFIXES`` and the shared
                # runtime-artifact classifier below; real model/runner
                # sources under ``.flowguard/models/owners`` remain visible.
                *_GIT_OUTPUT_EXCLUDES,
            ),
        )
        raw = tracked + untracked
    except (GitQueryTimeout, GitQueryCleanupUnconfirmed, GitQueryAborted):
        # A timeout is a bounded observation failure, not evidence that Git is
        # unavailable.  Propagate it so callers cannot fall back to an
        # unbounded filesystem walk or silently treat the result as empty.
        raise
    except ValueError:
        return None
    return tuple(
        sorted(
            {
                item.decode("utf-8").replace("\\", "/")
                for item in raw.split(b"\0")
                if item
            }
        )
    )


def _fingerprint_manifest_paths(
    root: Path,
    relatives: Iterable[str],
) -> tuple[dict[str, str], ...]:
    """Fingerprint a finite input set with bounded read concurrency.

    Source identities remain the canonical ``source_file_fingerprint`` values;
    only independent file reads are overlapped.  The worker count is capped so
    a large checkout cannot turn a freshness observation into an unbounded I/O
    fan-out, and the returned rows are deterministic regardless of completion
    order.
    """

    selected_values: set[str] = set()
    for value in relatives:
        relative = str(value).replace("\\", "/")
        if not relative:
            continue
        if _is_evidence_output(relative):
            if is_governed_source_in_runtime_cache(relative):
                raise ValueError(
                    "governed source cannot be hidden inside runtime cache: "
                    + relative
                )
            continue
        selected_values.add(relative)
    selected = tuple(sorted(selected_values))

    def fingerprint(relative: str) -> tuple[str, str] | None:
        path = root / relative
        if not path.is_file():
            return None
        return relative, functional_source_fingerprint(root, relative)

    if len(selected) < 16:
        pairs = (fingerprint(relative) for relative in selected)
    else:
        workers = min(8, len(selected))
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="flowguard-input-fingerprint",
        ) as executor:
            pairs = tuple(executor.map(fingerprint, selected))

    rows = {
        relative: value
        for pair in pairs
        if pair is not None
        for relative, value in (pair,)
    }
    return tuple(
        {"path": relative, "sha256": rows[relative]}
        for relative in sorted(rows)
    )


def project_manifest_semantic_payload(path: str | Path) -> dict[str, Any]:
    """Return the functional project-manifest projection.

    The model-authority table is a pointer/binding surface consumed by the
    authority loader, not generic validation-owner source.  Audit display
    fields likewise must not reopen functional work.  Engine/schema and
    behavior-bearing configuration remain in this projection and therefore
    still invalidate owners that actually consume them; the dedicated
    ``flowguard_execution`` resource-policy table does not.
    """

    candidate = Path(path)
    return dict(
        functional_source_payload(
            candidate.parent.parent,
            ".flowguard/project.toml",
        )
    )


def project_manifest_semantic_fingerprint(path: str | Path) -> str:
    """Fingerprint only functional project-manifest content."""

    return functional_source_fingerprint(
        Path(path).parent.parent,
        ".flowguard/project.toml",
    )


def project_manifest_authority_binding_fingerprint(path: str | Path) -> str:
    """Fingerprint the exact authority-pointer binding independently.

    This is a diagnostic/authority input helper.  Generic validation owners
    must use :func:`project_manifest_semantic_fingerprint`; authority readers
    use this binding only together with the pointed content-addressed objects.
    """

    payload = _project_manifest_payload(path)
    binding = payload.get("model_authority", {})
    if not isinstance(binding, Mapping):
        raise ValueError("project manifest model_authority must be a TOML mapping")
    return _sha256_bytes(_canonical_bytes(dict(binding)))


def validation_task_body_fingerprint(path: str | Path) -> str:
    """Fingerprint an OpenSpec task body with checkbox-only progress ignored."""

    candidate = Path(path).resolve()
    parts = candidate.parts
    try:
        marker = next(index for index, item in enumerate(parts) if item == "openspec")
    except StopIteration as exc:
        raise ValueError(f"OpenSpec task body is outside a repository root: {candidate}") from exc
    root = Path(*parts[:marker])
    relative = candidate.relative_to(root).as_posix()
    return functional_source_fingerprint(root, relative)


@_bounded_git_observation
def resolve_input_manifest(
    root: str | Path,
    patterns: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Resolve declared patterns to a deterministic content manifest."""

    root_path = Path(root).resolve()
    rows: dict[str, str] = {}
    unique_patterns = tuple(
        dict.fromkeys(str(item) for item in patterns if str(item))
    )
    candidates = _git_candidate_paths(root_path, unique_patterns)
    if candidates is not None:
        candidate_set = set(candidates)
        literal_patterns = tuple(
            pattern
            for pattern in unique_patterns
            if not any(token in pattern for token in ("*", "?", "["))
        )
        wildcard_patterns = tuple(
            pattern for pattern in unique_patterns if pattern not in literal_patterns
        )
        selected = {
            pattern.replace("\\", "/")
            for pattern in literal_patterns
            if pattern.replace("\\", "/") in candidate_set
        }
        if wildcard_patterns:
            selected.update(
                relative
                for relative in candidates
                if any(
                    _matches_declared_pattern(relative, pattern)
                    for pattern in wildcard_patterns
                )
            )
        return _fingerprint_manifest_paths(root_path, selected)

    for pattern in unique_patterns:
        for path in root_path.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"validation input escapes repository: {path}"
                ) from exc
            if _is_evidence_output(relative):
                if is_governed_source_in_runtime_cache(relative):
                    raise ValueError(
                        "governed source cannot be hidden inside runtime cache: "
                        + relative
                    )
                continue
            rows[relative] = str(resolved)
    return _fingerprint_manifest_paths(
        root_path,
        (
            relative
            for relative, path in rows.items()
            if path
        ),
    )


def filter_resolved_input_manifest(
    manifest: Sequence[Mapping[str, str]],
    patterns: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Filter one resolved repository manifest with canonical match semantics.

    The function performs no filesystem or Git access.  It is strictly an
    invocation-local projection of a current observation, not a cache or a
    validation result that can be reused by another invocation.
    """

    unique_patterns = tuple(
        dict.fromkeys(str(item) for item in patterns if str(item))
    )
    manifest_by_path: dict[str, str] = {}
    for item in manifest:
        relative = str(item.get("path", "")).replace("\\", "/")
        fingerprint = str(item.get("sha256", ""))
        if not relative or not fingerprint:
            raise ValueError("resolved input manifest row is incomplete")
        if relative in manifest_by_path and manifest_by_path[relative] != fingerprint:
            raise ValueError("resolved input manifest contains conflicting rows")
        manifest_by_path[relative] = fingerprint
    literal_patterns = tuple(
        pattern.replace("\\", "/")
        for pattern in unique_patterns
        if not any(token in pattern for token in ("*", "?", "["))
    )
    wildcard_patterns = tuple(
        pattern
        for pattern in unique_patterns
        if any(token in pattern for token in ("*", "?", "["))
    )
    rows = {
        relative: manifest_by_path[relative]
        for relative in literal_patterns
        if relative in manifest_by_path
    }
    if wildcard_patterns:
        for relative, fingerprint in manifest_by_path.items():
            if any(
                _matches_declared_pattern(relative, pattern)
                for pattern in wildcard_patterns
            ):
                rows[relative] = fingerprint
    return tuple(
        {"path": relative, "sha256": rows[relative]}
        for relative in sorted(rows)
    )


@_bounded_git_observation
def validation_input_manifest(root: str | Path) -> tuple[dict[str, str], ...]:
    """Return validation-governed inputs, excluding runtime evidence output."""

    patterns = (
        "flowguard/**/*",
        "scripts/**/*",
        "tests/**/*",
        "examples/**/*",
        "docs/**/*",
        "openspec/**/*",
        ".agents/skills/**/*",
        ".skillguard/**/*",
        ".flowguard/**/*",
        "pyproject.toml",
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "ROADMAP.md",
        "AGENTS.md",
        "LICENSE",
    )
    rows = list(
        _validation_input_manifest_from_observation(
            resolve_input_manifest(root, patterns)
        )
    )
    return tuple(rows)


def _validation_input_manifest_from_observation(
    manifest: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    """Project the validation input set without touching the filesystem."""

    patterns = (
        "flowguard/**/*",
        "scripts/**/*",
        "tests/**/*",
        "examples/**/*",
        "docs/**/*",
        "openspec/**/*",
        ".agents/skills/**/*",
        ".skillguard/**/*",
        ".flowguard/**/*",
        "pyproject.toml",
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "ROADMAP.md",
        "AGENTS.md",
        "LICENSE",
    )
    rows = list(filter_resolved_input_manifest(manifest, patterns))
    rows = [
        row
        for row in rows
        if not (
            row["path"].startswith("openspec/changes/")
            and row["path"].endswith("/verification-report.json")
        )
    ]
    return tuple(rows)


def governed_source_manifest(root: str | Path) -> tuple[dict[str, str], ...]:
    """Deprecated-name-free internal alias for the validation input manifest."""

    return validation_input_manifest(root)


def _git_bytes(root: Path, *arguments: str) -> bytes:
    """Run one lock-free, byte-preserving Git query under finite deadlines."""

    return _run_git_bytes_query(root, None, arguments)


def _git_query_category(arguments: Sequence[str]) -> str:
    """Return a short non-sensitive operation category for diagnostics."""

    for item in arguments:
        value = str(item)
        if value and not value.startswith("-"):
            return value
    return "unknown"


def _run_git_bytes_query(
    root: Path,
    input_bytes: bytes | None,
    arguments: Sequence[str],
) -> bytes:
    """Execute one Git child through the shared process-tree supervisor."""

    query_category = _git_query_category(arguments)
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    budget = _CURRENT_GIT_OBSERVATION.get()
    timeout_seconds = (
        budget.reserve(query_category)
        if budget is not None
        else GIT_QUERY_TIMEOUT_SECONDS
    )
    started = time.monotonic()
    try:
        completed = run_supervised_bytes(
            ("git", *arguments),
            cwd=root,
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds,
            grace_seconds=3.0,
            environment=environment,
        )
    except OSError as exc:
        # Git absence or an ordinary launch failure retains the existing
        # ValueError boundary.  _git_candidate_paths may use its bounded
        # direct-filesystem fallback for this class of failure; timeouts never
        # enter that fallback.
        raise ValueError(
            f"git {query_category} launch failed: {type(exc).__name__}: {exc}"
        ) from exc
    elapsed = max(0.0, time.monotonic() - started)
    if completed.timed_out:
        code = "git_query_timeout"
        if budget is not None and budget.remaining_seconds <= 0:
            code = "source_observation_timeout"
        raise GitQueryTimeout(
            code=code,
            query_category=query_category,
            elapsed_seconds=elapsed,
            cleanup_confirmed=completed.cleanup_confirmed,
            terminal_reason=completed.terminal_reason,
        )
    if bool(getattr(completed, "cancelled", False)) or bool(
        getattr(completed, "interrupted", False)
    ):
        raise GitQueryAborted(
            query_category=query_category,
            elapsed_seconds=elapsed,
            terminal_reason=completed.terminal_reason,
        )
    if not completed.cleanup_confirmed:
        raise GitQueryCleanupUnconfirmed(
            query_category=query_category,
            elapsed_seconds=elapsed,
            terminal_reason=completed.terminal_reason,
        )
    if completed.exit_code != 0:
        stderr = completed.stderr
        if isinstance(stderr, bytes):
            message = stderr.decode("utf-8", errors="replace").strip()
        else:
            message = stderr.strip()
        raise ValueError(f"git {query_category} failed: {message}")
    stdout = completed.stdout
    if not isinstance(stdout, bytes):
        raise ValueError("git query returned non-byte stdout")
    return stdout


def _git_bytes_with_input(root: Path, input_bytes: bytes, *arguments: str) -> bytes:
    """Run one lock-free Git query with bounded stdin.

    ``release_tree_manifest`` can have hundreds of changed worktree files.  A
    separate ``git hash-object`` process for every path makes readiness scale
    with process-launch latency instead of file bytes.  Keep the same checked
    error boundary as :func:`_git_bytes`, but allow one command to consume a
    finite path list through stdin.
    """

    if not isinstance(input_bytes, bytes):
        raise TypeError("git query input must be bytes")
    return _run_git_bytes_query(root, input_bytes, arguments)


def _git_bytes_from_pathspec_file(
    root: Path,
    arguments: Sequence[str],
    pathspecs: Sequence[str],
) -> bytes:
    """Run a bounded Git query over command-line-safe pathspec batches.

    ``git ls-files`` on the supported Windows Git builds does not implement
    ``--pathspec-from-file``.  A large owner plan can nevertheless contain
    hundreds of literal source paths, which exceeds the platform command-line
    limit if passed in one request.  Partitioning the exact pathspec list into
    conservative batches keeps the matching semantics while avoiding both the
    command-length failure and a repository-wide fallback walk.
    """

    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    del environment  # _git_bytes owns the identical lock-free environment.
    batches: list[tuple[str, ...]] = []
    current: list[str] = []
    current_size = 0
    # Leave ample headroom below CreateProcess' Windows command-line limit for
    # the executable path and fixed arguments.  Pathspecs in this project are
    # short, so this normally creates only a handful of Git calls.
    max_batch_bytes = 7000
    for item in pathspecs:
        value = str(item)
        item_size = len(value.encode("utf-8", errors="surrogateescape")) + 1
        if item_size > max_batch_bytes:
            raise ValueError("git pathspec exceeds the bounded command-line limit")
        if current and current_size + item_size > max_batch_bytes:
            batches.append(tuple(current))
            current = []
            current_size = 0
        current.append(value)
        current_size += item_size
    if current:
        batches.append(tuple(current))
    if not batches:
        return b""
    return b"".join(
        _git_bytes(root, *arguments, "--", *batch)
        for batch in batches
    )


def _git_blob_id(data: bytes, object_format: str) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if object_format == "sha256":
        return hashlib.sha256(payload).hexdigest()
    if object_format == "sha1":
        return hashlib.sha1(payload).hexdigest()
    raise ValueError(f"unsupported Git object format: {object_format}")


def _git_worktree_blob_id(
    root: Path,
    relative: str,
    *,
    mode: str,
    object_format: str,
) -> str:
    """Hash prospective content with the same clean filters Git will commit."""

    path = root / relative
    if mode == "120000":
        return _git_blob_id(
            os.readlink(path).encode("utf-8"),
            object_format,
        )
    return _git_bytes(
        root,
        "hash-object",
        f"--path={relative}",
        "--",
        relative,
    ).decode("ascii").strip()


def _git_worktree_blob_ids(
    root: Path,
    relatives: Sequence[str],
    *,
    object_format: str,
) -> dict[str, str]:
    """Hash regular worktree paths in one Git process.

    Git's ``--stdin-paths`` mode preserves the path-aware clean-filter
    behavior used by the previous per-file ``--path`` calls while avoiding a
    process launch for every changed file.  Paths containing newlines cannot
    be represented by that interface safely, so they retain the old exact
    one-file path.  The output is required to be one digest per requested
    path; any mismatch is a fail-closed error rather than a partial map.
    """

    normalized = tuple(str(item) for item in relatives)
    if not normalized:
        return {}
    if any("\n" in item or "\r" in item for item in normalized):
        return {
            item: _git_worktree_blob_id(
                root,
                item,
                mode="100644",
                object_format=object_format,
            )
            for item in normalized
        }
    raw = _git_bytes_with_input(
        root,
        ("\n".join(normalized) + "\n").encode("utf-8"),
        "hash-object",
        "--stdin-paths",
    )
    digests = tuple(line.decode("ascii").strip() for line in raw.splitlines() if line)
    expected_length = 64 if object_format == "sha256" else 40 if object_format == "sha1" else 0
    if not expected_length or len(digests) != len(normalized):
        raise ValueError("git hash-object returned an incomplete worktree path map")
    if any(len(digest) != expected_length or any(char not in "0123456789abcdef" for char in digest) for digest in digests):
        raise ValueError("git hash-object returned an invalid worktree blob id")
    return dict(zip(normalized, digests, strict=True))


def model_authority_release_paths(root: Path) -> tuple[str, ...]:
    """Return the public files needed to replay the current authority head."""

    manifest_path = root / ".flowguard" / "project.toml"
    if not manifest_path.is_file():
        return ()
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    authority = manifest.get("model_authority")
    if authority is None:
        return ()
    if not isinstance(authority, Mapping):
        raise ValueError("model_authority must be a TOML table")

    observed_fingerprint = str(
        authority.get("observed_snapshot_fingerprint", "")
    )
    observed_path = str(authority.get("observed_snapshot_path", "")).replace(
        "\\", "/"
    )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", observed_fingerprint):
        raise ValueError("model authority observed snapshot fingerprint is invalid")
    observed_digest = observed_fingerprint.split(":", 1)[1]
    expected_observed_path = (
        f".flowguard/models/authority/snapshots/{observed_digest}.json"
    )
    if observed_path != expected_observed_path:
        raise ValueError(
            "model authority observed snapshot path is not content addressed"
        )

    try:
        generation = int(authority.get("generation", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("model authority generation is invalid") from exc
    accepted = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    activation = str(
        authority.get("activation_receipt_fingerprint", "")
    )
    previous = str(authority.get("previous_snapshot_fingerprint", ""))
    for field_name, value in (
        ("accepted revision", accepted),
        ("activation receipt", activation),
    ):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError(f"model authority {field_name} fingerprint is invalid")
    if previous and not re.fullmatch(r"sha256:[0-9a-f]{64}", previous):
        raise ValueError("model authority previous snapshot fingerprint is invalid")

    snapshot_file = root / expected_observed_path
    try:
        snapshot_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("model authority observed snapshot is unreadable") from exc
    if not isinstance(snapshot_payload, Mapping):
        raise ValueError("model authority observed snapshot must be a JSON object")
    model_instances = snapshot_payload.get("model_instances")
    if not isinstance(model_instances, list):
        raise ValueError(
            "model authority observed snapshot model_instances must be an array"
        )

    paths = [expected_observed_path]
    for model_index, model_instance in enumerate(model_instances):
        if not isinstance(model_instance, Mapping):
            raise ValueError(
                f"model authority model_instances[{model_index}] must be an object"
            )
        inputs = model_instance.get("inputs")
        if not isinstance(inputs, list):
            raise ValueError(
                "model authority input inventory must be an array: "
                f"model_instances[{model_index}]"
            )
        for field_name in ("model_path", "runner_path"):
            declared_path = str(model_instance.get(field_name, "")).replace(
                "\\", "/"
            )
            if not declared_path:
                continue
            try:
                working_classification = classify_runtime_artifact(declared_path)
            except ValueError as exc:
                raise ValueError(
                    "model authority model path is unsafe: "
                    f"model_instances[{model_index}].{field_name}"
                ) from exc
            if (
                working_classification is None
                and not declared_path.startswith(".flowguard/")
            ):
                # Some older typed snapshots store a project-relative control
                # plane path without the explicit ``.flowguard/`` prefix.
                # Apply the same canonical authority boundary before building
                # a release projection; omission must not make staging
                # material look publishable.
                working_classification = classify_runtime_artifact(
                    f".flowguard/{declared_path}"
                )
            if working_classification is not None:
                raise ValueError(
                    "model authority model path points to non-authority working material: "
                    f"{declared_path} ({working_classification.kind})"
                )
            paths.append(declared_path)
        for input_index, input_row in enumerate(inputs):
            if not isinstance(input_row, Mapping):
                raise ValueError(
                    "model authority input row must be an object: "
                    f"model_instances[{model_index}].inputs[{input_index}]"
                )
            relative = str(input_row.get("path", "")).replace("\\", "/")
            relative_path = Path(relative)
            if (
                not relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
            ):
                raise ValueError(
                    "model authority input path is invalid: "
                    f"model_instances[{model_index}].inputs[{input_index}]"
                )
            try:
                working_classification = classify_runtime_artifact(relative)
            except ValueError as exc:
                raise ValueError(
                    "model authority input path is unsafe: "
                    f"model_instances[{model_index}].inputs[{input_index}]"
                ) from exc
            if (
                working_classification is None
                and not relative.startswith(".flowguard/")
            ):
                working_classification = classify_runtime_artifact(
                    f".flowguard/{relative}"
                )
            if working_classification is not None:
                raise ValueError(
                    "model authority input path points to non-authority working material: "
                    f"{relative} ({working_classification.kind})"
                )
            paths.append(relative)
    if previous:
        paths.append(
            ".flowguard/models/authority/snapshots/"
            + previous.split(":", 1)[1]
            + ".json"
        )
    if generation == 1:
        if accepted != activation:
            raise ValueError(
                "bootstrap model authority must bind one bootstrap fingerprint"
            )
        paths.append(
            ".flowguard/models/authority/bootstraps/"
            + accepted.split(":", 1)[1]
            + ".json"
        )
    elif generation > 1:
        paths.extend(
            (
            ".flowguard/models/authority/revisions/"
                + accepted.split(":", 1)[1]
                + ".json",
            ".flowguard/models/authority/activations/"
                + activation.split(":", 1)[1]
                + ".json",
            )
        )
    else:
        raise ValueError("model authority generation must be positive")
    return tuple(dict.fromkeys(paths))


@_bounded_git_observation
def release_tree_manifest(
    root: str | Path,
    *,
    revision: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Return exact prospective-worktree or committed Git tree identities."""

    root_path = Path(root).resolve()
    if revision is not None:
        raw = _git_bytes(
            root_path,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            revision,
        )
        rows: list[dict[str, str]] = []
        for item in raw.split(b"\0"):
            if not item:
                continue
            header, encoded_path = item.split(b"\t", 1)
            mode, object_type, object_id = header.decode("ascii").split()
            relative = encoded_path.decode("utf-8")
            # Committed release projections never carry working caches,
            # staging candidates, or opaque evidence/history payloads.  The
            # source tree remains untouched; this is only a projection rule.
            if is_release_excluded_path(relative):
                continue
            if object_type not in {"blob", "commit"}:
                raise ValueError(
                    f"unsupported Git tree object type: {object_type}"
                )
            rows.append(
                {
                    "path": relative,
                    "mode": mode,
                    "blob_id": object_id,
                }
            )
        return tuple(sorted(rows, key=lambda item: item["path"]))

    object_format = _git_bytes(
        root_path,
        "rev-parse",
        "--show-object-format",
    ).decode("ascii").strip()
    index_rows: dict[str, tuple[str, str]] = {}
    for item in _git_bytes(root_path, "ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        header, encoded_path = item.split(b"\t", 1)
        mode, object_id, stage = header.decode("ascii").split()
        path = encoded_path.decode("utf-8")
        if stage != "0":
            raise ValueError(f"release tree has an unresolved index stage: {path}")
        index_rows[path] = (mode, object_id)
    worktree_changed_paths = {
        item.decode("utf-8")
        for item in _git_bytes(
            root_path,
            "diff-files",
            "--name-only",
            "-z",
        ).split(b"\0")
        if item
    }
    required_authority_paths = model_authority_release_paths(root_path)
    missing_authority_paths = tuple(
        path for path in required_authority_paths if path not in index_rows
    )
    if missing_authority_paths:
        raise ValueError(
            "required public model authority paths are not tracked: "
            + ", ".join(missing_authority_paths)
        )
    candidates = tuple(
        item.decode("utf-8")
        for item in _git_bytes(
            root_path,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ).split(b"\0")
        if item
    )
    rows = []
    batch_hash_paths: list[str] = []
    for relative in sorted(set(candidates)):
        if is_release_excluded_path(relative) and relative in index_rows:
            raise ValueError(
                "release tree explicitly contains non-release working artifact: "
                + relative
            )
        if relative not in index_rows and _is_evidence_output(relative):
            continue
        path = root_path / relative
        mode, index_object_id = index_rows.get(relative, ("100644", ""))
        if mode == "160000":
            if not index_object_id:
                raise ValueError(f"untracked submodule entry is unsupported: {relative}")
            blob_id = index_object_id
        elif relative in index_rows and relative not in worktree_changed_paths:
            blob_id = index_object_id
        else:
            if not path.exists():
                raise ValueError(f"release tree path is deleted or missing: {relative}")
            if mode != "120000" and not path.is_file():
                raise ValueError(f"release tree entry is not a file: {relative}")
            if mode == "120000":
                blob_id = _git_worktree_blob_id(
                    root_path,
                    relative,
                    mode=mode,
                    object_format=object_format,
                )
            else:
                # Defer regular-file hashing so all changed worktree paths
                # share one path-aware Git process.  Symlinks retain their
                # direct target hashing because ``--stdin-paths`` cannot
                # represent link targets as file content.
                blob_id = ""
                batch_hash_paths.append(relative)
        rows.append({"path": relative, "mode": mode, "blob_id": blob_id})
    if batch_hash_paths:
        batch_hashes = _git_worktree_blob_ids(
            root_path,
            batch_hash_paths,
            object_format=object_format,
        )
        rows = [
            {
                **row,
                "blob_id": batch_hashes[row["path"]]
                if not row["blob_id"]
                else row["blob_id"],
            }
            for row in rows
        ]
    return tuple(rows)


def manifest_fingerprint(manifest: Sequence[Mapping[str, str]]) -> str:
    return _sha256_bytes(_canonical_bytes([dict(item) for item in manifest]))


@dataclass(frozen=True)
class ValidationOwnerContract:
    owner_id: str
    command: tuple[str, ...]
    input_patterns: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    projected_inputs: tuple[tuple[str, str], ...] = ()
    dependency_owner_ids: tuple[str, ...] = ()
    resource_keys: tuple[str, ...] = ()
    resource_argv_options: tuple[str, ...] = ()
    toolchain_selectors: tuple[str, ...] = ("python_implementation", "python_version", "flowguard_version")
    environment_selectors: tuple[str, ...] = ("platform_system", "platform_machine")
    external_component_bindings: tuple[tuple[str, str], ...] = ()
    work_context_artifact_roles: tuple[str, ...] = ()
    termination_policy: str = DEFAULT_TERMINATION_POLICY
    required: bool = True

    def __post_init__(self) -> None:
        raw_resource_options = tuple(
            str(item).strip()
            for item in self.resource_argv_options
            if str(item).strip()
        )
        unknown_resource_options = sorted(
            set(raw_resource_options) - set(_RESOURCE_ONLY_OPTIONS)
        )
        if unknown_resource_options:
            raise ValueError(
                "validation owner resource_argv_options contain unsupported options: "
                + ", ".join(unknown_resource_options)
            )
        object.__setattr__(
            self,
            "resource_argv_options",
            tuple(sorted(set(raw_resource_options))),
        )
        for field_name in (
            "dependency_owner_ids",
            "resource_keys",
            "resource_argv_options",
            "toolchain_selectors",
            "environment_selectors",
            "work_context_artifact_roles",
        ):
            values = tuple(sorted({str(item).strip() for item in getattr(self, field_name) if str(item).strip()}))
            object.__setattr__(self, field_name, values)
        external = tuple(
            sorted(
                (str(component_id).strip(), str(fingerprint).strip())
                for component_id, fingerprint in self.external_component_bindings
            )
        )
        if len({item[0] for item in external}) != len(external):
            raise ValueError("external component ids must be unique within one owner")
        if any(
            not component_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
            for component_id, fingerprint in external
        ):
            raise ValueError(
                "external component bindings require a component id and canonical sha256 fingerprint"
            )
        object.__setattr__(self, "external_component_bindings", external)
        projected = tuple(
            sorted(
                (str(component_id), str(fingerprint))
                for component_id, fingerprint in self.projected_inputs
            )
        )
        if len({item[0] for item in projected}) != len(projected):
            raise ValueError("projected input component ids must be unique")
        if any(
            not component_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
            for component_id, fingerprint in projected
        ):
            raise ValueError(
                "projected inputs require a component id and canonical sha256 fingerprint"
            )
        object.__setattr__(self, "projected_inputs", projected)
        object.__setattr__(self, "termination_policy", str(self.termination_policy).strip())
        if self.owner_id in self.dependency_owner_ids:
            raise ValueError("validation owner cannot depend on itself")
        if not self.termination_policy:
            raise ValueError("validation owner termination policy is required")
        if (
            not self.owner_id
            or not self.command
            or (not self.input_patterns and not projected)
            or not self.obligation_ids
        ):
            raise ValueError(
                "owner id, command, input patterns or projections, and obligations are required"
            )

    def functional_dict(
        self,
        *,
        command: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Return only the product/validation semantics of this owner.

        Resource labels and termination policy are execution supervision
        metadata.  They remain in the explicit contract serialization for
        scheduling and safety diagnostics, but never participate in the
        functional contract hash or owner identity.
        """

        return {
            "owner_id": self.owner_id,
            "command": list(command if command is not None else self.command),
            "input_patterns": list(self.input_patterns),
            "obligation_ids": list(self.obligation_ids),
            "projected_inputs": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in self.projected_inputs
            ],
            "dependency_owner_ids": list(self.dependency_owner_ids),
            "toolchain_selectors": list(self.toolchain_selectors),
            "environment_selectors": list(self.environment_selectors),
            "external_component_bindings": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in self.external_component_bindings
            ],
            "work_context_artifact_roles": list(self.work_context_artifact_roles),
            "required": self.required,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.functional_dict(),
            "resource_keys": list(self.resource_keys),
            "resource_argv_options": list(self.resource_argv_options),
            "termination_policy": self.termination_policy,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ValidationOwnerContract":
        allowed = {
            "owner_id",
            "command",
            "input_patterns",
            "obligation_ids",
            "projected_inputs",
            "dependency_owner_ids",
            "resource_keys",
            "resource_argv_options",
            "toolchain_selectors",
            "environment_selectors",
            "external_component_bindings",
            "work_context_artifact_roles",
            "termination_policy",
            "required",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                "validation owner contract fields are not current: "
                + ", ".join(unknown)
            )
        return cls(
            owner_id=str(value.get("owner_id", "")),
            command=tuple(str(item) for item in value.get("command", ())),
            input_patterns=tuple(str(item) for item in value.get("input_patterns", ())),
            obligation_ids=tuple(str(item) for item in value.get("obligation_ids", ())),
            projected_inputs=tuple(
                (
                    str(item.get("component_id", "")),
                    str(item.get("fingerprint", "")),
                )
                for item in value.get("projected_inputs", ())
                if isinstance(item, Mapping)
            ),
            dependency_owner_ids=tuple(
                str(item) for item in value.get("dependency_owner_ids", ())
            ),
            resource_keys=tuple(str(item) for item in value.get("resource_keys", ())),
            resource_argv_options=tuple(
                str(item) for item in value.get("resource_argv_options", ())
            ),
            toolchain_selectors=tuple(
                str(item) for item in value.get(
                    "toolchain_selectors",
                    ("python_implementation", "python_version", "flowguard_version"),
                )
            ),
            environment_selectors=tuple(
                str(item) for item in value.get(
                    "environment_selectors",
                    ("platform_system", "platform_machine"),
                )
            ),
            external_component_bindings=tuple(
                (
                    str(item.get("component_id", "")),
                    str(item.get("fingerprint", "")),
                )
                for item in value.get("external_component_bindings", ())
                if isinstance(item, Mapping)
            ),
            work_context_artifact_roles=tuple(
                str(item) for item in value.get("work_context_artifact_roles", ())
            ),
            termination_policy=str(
                value.get("termination_policy", DEFAULT_TERMINATION_POLICY)
            ),
            required=bool(value.get("required", True)),
        )


@dataclass(frozen=True)
class ValidationOwnerCurrent:
    contract: ValidationOwnerContract
    input_manifest: tuple[Mapping[str, str], ...]
    input_snapshot: InputSnapshot
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    environment_metadata: Mapping[str, str]
    environment_fingerprint: str
    command: tuple[str, ...]
    owner_identity: str


@dataclass(frozen=True)
class ValidationOwnerPlanRow:
    owner_id: str
    disposition: str
    owner_identity: str
    reason: str
    receipt_id: str = ""
    receipt_fingerprint: str = ""
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.disposition not in OWNER_DISPOSITIONS:
            raise ValueError(f"unsupported owner disposition: {self.disposition}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "disposition": self.disposition,
            "owner_identity": self.owner_identity,
            "reason": self.reason,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class ValidationOwnerObservation:
    """One immutable, invocation-local view of owner inputs and evidence.

    The observation is deliberately not persisted.  It lets a bounded caller
    reuse one repository scan and one canonical receipt-store read while every
    owner keeps its own contract, current identity, receipt, and native
    verification result.
    """

    contracts: tuple[ValidationOwnerContract, ...]
    repository_input_manifest: tuple[Mapping[str, str], ...]
    receipt_inventory_identities: tuple[tuple[str, str, str], ...]
    rows: tuple[ValidationOwnerPlanRow, ...]
    owner_currents: tuple[ValidationOwnerCurrent, ...]
    reusable_receipts: tuple[EvidenceReceipt, ...]
    reusable_verifications: tuple[ReceiptVerificationResult, ...]
    observation_fingerprint: str
    observation_patterns: tuple[str, ...] = ()
    observation_seconds: float = 0.0
    receipt_inventory_mode: str = "all"
    metrics: Mapping[str, object] = field(default_factory=dict)

    @property
    def current_by_owner(self) -> Mapping[str, ValidationOwnerCurrent]:
        return {item.contract.owner_id: item for item in self.owner_currents}

    @property
    def receipt_by_owner(self) -> Mapping[str, EvidenceReceipt]:
        return {
            item.subject_id.removeprefix("validation-owner:"): item
            for item in self.reusable_receipts
        }

    @property
    def verification_by_owner(self) -> Mapping[str, ReceiptVerificationResult]:
        receipts = self.receipt_by_owner
        results = {item.receipt_id: item for item in self.reusable_verifications}
        return {
            owner_id: results[receipt.receipt_id]
            for owner_id, receipt in receipts.items()
        }

    @property
    def repository_input_manifest_fingerprint(self) -> str:
        return manifest_fingerprint(self.repository_input_manifest)

    @property
    def source_observation_fingerprint(self) -> str:
        """Return the source-only identity for a completion epoch.

        ``observation_fingerprint`` intentionally includes the receipt
        inventory and owner dispositions: those values are needed to decide
        whether an owner can be reused and to detect receipt-store drift
        during publication.  They are output/state evidence, however, and
        must not become a new semantic source epoch merely because the
        preceding producer wrote its validation-owner receipts.

        The completion gate therefore consumes this narrower projection.  It
        binds the declared observation selectors, source manifest, and the
        independently derived owner identities, while deliberately excluding
        receipt ids/fingerprints, rows, and reusable-receipt projections.
        Receipt inventory remains available through the full observation for
        stale checks and owner disposition decisions.
        """

        payload = {
            "schema": "flowguard.validation_owner_source_observation.v1",
            "observation_patterns": list(self.observation_patterns),
            "repository_input_manifest_fingerprint": (
                self.repository_input_manifest_fingerprint
            ),
            "owner_identities": {
                owner_id: current.owner_identity
                for owner_id, current in sorted(self.current_by_owner.items())
            },
        }
        return fingerprint_value(payload)


@dataclass(frozen=True)
class ValidationObservationFreshness:
    """Visible final freshness boundary for one transient observation."""

    status: str
    initial_observation_fingerprint: str
    final_observation_fingerprint: str = ""
    findings: tuple[str, ...] = ()
    observation_seconds: float = 0.0
    owner_currents: tuple[ValidationOwnerCurrent, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "pass" and not self.findings

    @property
    def current_by_owner(self) -> Mapping[str, ValidationOwnerCurrent]:
        return {item.contract.owner_id: item for item in self.owner_currents}

    @classmethod
    def not_run(
        cls,
        observation: ValidationOwnerObservation,
    ) -> "ValidationObservationFreshness":
        return cls(
            status="not_run",
            initial_observation_fingerprint=(
                observation.observation_fingerprint
            ),
        )


def topological_owner_contracts(
    contracts: Sequence[ValidationOwnerContract],
) -> tuple[ValidationOwnerContract, ...]:
    """Validate and deterministically order one complete owner DAG."""

    by_id = {item.owner_id: item for item in contracts}
    if len(by_id) != len(contracts):
        raise ValueError("validation owner ids must be unique")
    if any(not owner_id for owner_id in by_id):
        raise ValueError("validation owner ids must be non-empty")
    for contract in contracts:
        unknown = sorted(set(contract.dependency_owner_ids) - set(by_id))
        if unknown:
            raise ValueError(
                f"validation owner {contract.owner_id} has unknown dependencies: "
                + ", ".join(unknown)
            )

    ordered: list[ValidationOwnerContract] = []
    pending = set(by_id)
    while pending:
        ready = sorted(
            owner_id
            for owner_id in pending
            if set(by_id[owner_id].dependency_owner_ids).isdisjoint(pending)
        )
        if not ready:
            raise ValueError(
                "validation owner dependency cycle: " + ", ".join(sorted(pending))
            )
        for owner_id in ready:
            ordered.append(by_id[owner_id])
            pending.remove(owner_id)

    ancestors: dict[str, set[str]] = {}
    for contract in ordered:
        closure = set(contract.dependency_owner_ids)
        for dependency_id in contract.dependency_owner_ids:
            closure.update(ancestors[dependency_id])
        ancestors[contract.owner_id] = closure
    resource_owners: dict[str, list[str]] = {}
    for contract in ordered:
        for resource_key in contract.resource_keys:
            resource_owners.setdefault(resource_key, []).append(contract.owner_id)
    for resource_key, owner_ids in sorted(resource_owners.items()):
        for index, left in enumerate(owner_ids):
            for right in owner_ids[index + 1 :]:
                if left not in ancestors[right] and right not in ancestors[left]:
                    raise ValueError(
                        "validation resource conflict is not dependency ordered: "
                        f"{resource_key} ({left}, {right})"
                    )
    return tuple(ordered)


@dataclass(frozen=True)
class ValidationOwnerPlan:
    contracts: tuple[ValidationOwnerContract, ...]
    rows: tuple[ValidationOwnerPlanRow, ...]
    owner_currents: Mapping[str, ValidationOwnerCurrent]
    reusable_receipts: Mapping[str, EvidenceReceipt]
    validation_input_manifest: tuple[Mapping[str, str], ...]
    validation_input_manifest_fingerprint: str
    release_tree_manifest: tuple[Mapping[str, str], ...]
    release_tree_manifest_fingerprint: str
    plan_fingerprint: str
    claim_scope: str = VALIDATION_CLAIM_SCOPE_RELEASE

    @property
    def blocked(self) -> bool:
        return any(item.disposition == OWNER_BLOCKED for item in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OWNER_PLAN_SCHEMA,
            "contracts": [item.to_dict() for item in self.contracts],
            "rows": [item.to_dict() for item in self.rows],
            "owner_identities": {
                owner_id: current.owner_identity
                for owner_id, current in sorted(self.owner_currents.items())
            },
            "validation_input_manifest_fingerprint": self.validation_input_manifest_fingerprint,
            "release_tree_manifest_fingerprint": self.release_tree_manifest_fingerprint,
            "claim_scope": self.claim_scope,
            "plan_fingerprint": self.plan_fingerprint,
            "blocked": self.blocked,
        }


@dataclass(frozen=True)
class ValidationParentCurrent:
    owner_plan: ValidationOwnerPlan
    validation_snapshot: InputSnapshot
    release_tree_snapshot: InputSnapshot
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    environment_metadata: Mapping[str, str]
    environment_fingerprint: str
    parent_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PARENT_CURRENT_SCHEMA,
            "owner_plan": self.owner_plan.to_dict(),
            "validation_snapshot": self.validation_snapshot.to_dict(),
            "release_tree_snapshot": self.release_tree_snapshot.to_dict(),
            "contract_hash": self.contract_hash,
            "check_manifest_hash": self.check_manifest_hash,
            "suite_map_hash": self.suite_map_hash,
            "environment_metadata": dict(self.environment_metadata),
            "environment_fingerprint": self.environment_fingerprint,
            "parent_identity": self.parent_identity,
        }


def build_owner_current(
    root: str | Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
) -> ValidationOwnerCurrent:
    return _build_owner_current(
        Path(root).resolve(),
        contract,
        all_contracts=all_contracts,
        resolved_input_manifest=None,
    )


def _build_owner_current(
    root: Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    resolved_input_manifest: Sequence[Mapping[str, str]] | None,
) -> ValidationOwnerCurrent:
    """Build one owner against a direct or invocation-local input observation."""

    root_path = Path(root).resolve()
    resolved_inputs = (
        resolve_input_manifest(root_path, contract.input_patterns)
        if resolved_input_manifest is None
        else filter_resolved_input_manifest(
            resolved_input_manifest,
            contract.input_patterns,
        )
    )
    manifest = tuple(
        sorted(
            (
                *resolved_inputs,
                *(
                    {
                        "path": f"<projection:{component_id}>",
                        "sha256": fingerprint,
                    }
                    for component_id, fingerprint in contract.projected_inputs
                ),
                *(
                    {
                        "path": f"<external:{component_id}>",
                        "sha256": fingerprint,
                    }
                    for component_id, fingerprint in contract.external_component_bindings
                ),
            ),
            key=lambda item: item["path"],
        )
    )
    tokenized_command = _canonical_owner_command(
        contract.command,
        workspace_root=root_path,
        resource_options=contract.resource_argv_options,
    )
    canonical_contract = contract.functional_dict(command=tokenized_command)
    contract_hash = fingerprint_value(canonical_contract)
    check_manifest_hash = fingerprint_value(
        {
            "owner_id": contract.owner_id,
            "command": list(tokenized_command),
            "obligations": list(contract.obligation_ids),
        }
    )
    suite_map_hash = fingerprint_value(
        {
            "owner_id": contract.owner_id,
            "patterns": list(contract.input_patterns),
            "projected_inputs": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in contract.projected_inputs
            ],
            "obligations": list(contract.obligation_ids),
        }
    )
    input_snapshot = snapshot_bytes(
        f"input:validation-owner:{contract.owner_id}",
        _canonical_bytes([dict(item) for item in manifest]),
        path_token=f"<WORKSPACE>/<OWNER_INPUT:{contract.owner_id}>",
        obligation_ids=contract.obligation_ids,
    )
    observed_environment = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "flowguard_version": _package_version(),
    }
    selected_keys = tuple(
        sorted(set(contract.toolchain_selectors + contract.environment_selectors))
    )
    unknown_selectors = sorted(set(selected_keys) - set(observed_environment))
    if unknown_selectors:
        raise ValueError(
            f"validation owner {contract.owner_id} has unknown environment selectors: "
            + ", ".join(unknown_selectors)
        )
    environment = build_environment_fingerprint(
        {key: observed_environment[key] for key in selected_keys}
    )
    owner_identity = fingerprint_value(
        {
            "schema": OWNER_RECEIPT_SCHEMA,
            "owner_id": contract.owner_id,
            "command": tokenized_command,
            "input_snapshot": input_snapshot.to_dict(),
            "contract_hash": contract_hash,
            "check_manifest_hash": check_manifest_hash,
            "suite_map_hash": suite_map_hash,
            "environment_fingerprint": environment.fingerprint,
            "obligations": list(contract.obligation_ids),
            "dependencies": list(contract.dependency_owner_ids),
        }
    )
    return ValidationOwnerCurrent(
        contract=contract,
        input_manifest=manifest,
        input_snapshot=input_snapshot,
        contract_hash=contract_hash,
        check_manifest_hash=check_manifest_hash,
        suite_map_hash=suite_map_hash,
        environment_metadata=environment.metadata,
        environment_fingerprint=environment.fingerprint,
        command=tokenized_command,
        owner_identity=owner_identity,
    )


def _proof_path(receipt_root: Path, receipt: EvidenceReceipt) -> Path | None:
    relative = str(receipt.metadata.get("proof_relpath", ""))
    if not relative:
        return None
    candidate = (receipt_root / relative).resolve()
    if receipt_root.resolve() not in candidate.parents:
        return None
    return candidate


def dependency_receipt_bindings(
    receipts: Mapping[str, EvidenceReceipt],
) -> tuple[tuple[str, str, str], ...]:
    """Project dependency receipts into a deterministic typed binding.

    Dependency receipt identities are evidence inputs to a consuming owner's
    reuse decision, not source inputs to its completion epoch.  Keep the
    projection deliberately small and content-addressed: owner id, receipt
    id, and receipt fingerprint.  The tuple form is stable for hashing and
    comparison while callers may serialize it as a list of objects.
    """

    return tuple(
        sorted(
            (
                str(owner_id),
                str(receipt.receipt_id),
                str(receipt.fingerprint),
            )
            for owner_id, receipt in receipts.items()
        )
    )


def owner_receipt_dependency_bindings(
    receipt: EvidenceReceipt,
    receipt_root: str | Path,
) -> tuple[tuple[str, str, str], ...]:
    """Read one owner's producer-declared dependency receipt projection.

    The projection lives inside the immutable owner proof payload so it is
    covered by both the proof fingerprint and the content-addressed receipt
    id.  Missing, malformed, or unreadable projections fail closed as an
    empty binding; a consumer with declared dependencies therefore cannot
    reuse an unbound historical receipt.
    """

    proof_path = _proof_path(Path(receipt_root).resolve(), receipt)
    if proof_path is None or not proof_path.is_file():
        return ()
    try:
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        child = payload.get("child", {})
        child_payload = child.get("payload", {}) if isinstance(child, Mapping) else {}
        raw_bindings = (
            child_payload.get("dependency_receipt_bindings", ())
            if isinstance(child_payload, Mapping)
            else ()
        )
        if not isinstance(raw_bindings, (list, tuple)):
            return ()
        bindings: list[tuple[str, str, str]] = []
        for item in raw_bindings:
            if not isinstance(item, Mapping):
                return ()
            owner_id = str(item.get("owner_id", "")).strip()
            receipt_id = str(item.get("receipt_id", "")).strip()
            fingerprint = str(item.get("receipt_fingerprint", "")).strip()
            if not owner_id or not receipt_id or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", fingerprint
            ):
                return ()
            bindings.append((owner_id, receipt_id, fingerprint))
        return tuple(sorted(bindings))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return ()


def build_owner_receipt_context(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    receipt_root: str | Path,
) -> ReceiptVerificationContext | None:
    proof_path = _proof_path(Path(receipt_root).resolve(), receipt)
    if proof_path is None or not proof_path.is_file():
        return None
    proof_fingerprint = _sha256_bytes(proof_path.read_bytes())
    return _owner_receipt_context_for_proof(
        current,
        receipt,
        proof_fingerprint,
    )


# Model-regression owner receipts contain two kinds of identity.  The owner
# receipt itself is content addressed, so a rerun that writes its evidence to a
# different retained run directory necessarily gets a different receipt and
# proof fingerprint.  The model result nested in the proof, however, carries
# the stable semantic result fingerprints that determine whether the rerun
# actually changed the model evidence.  Keep the path-bearing fields out of a
# duplicate comparison so equivalent reruns can converge on one usable
# receipt, while genuinely different model results remain fail-closed.
_MODEL_RECEIPT_VOLATILE_FIELDS = frozenset(
    {
        "artifact_paths",
        "native_case_result_artifact_path",
        "receipt_path",
        "seconds",
        "stderr_path",
        "stdout_path",
    }
)


def _normalize_model_receipt_result(value: Any, *, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {
            str(name): _normalize_model_receipt_result(item, key=str(name))
            for name, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(name) not in _MODEL_RECEIPT_VOLATILE_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [
            _normalize_model_receipt_result(item, key=key)
            for item in value
        ]
    return value


def _model_receipt_duplicate_identity(
    receipt: EvidenceReceipt,
    receipt_root: Path,
    repository_root: Path,
) -> tuple[str, int] | None:
    """Return semantic identity and artifact quality for one model receipt.

    This helper is intentionally restricted to model-regression owner proofs.
    It never turns an unreadable proof into reusable evidence: ``None`` keeps
    the ordinary ambiguity/error path.  ``quality`` is a deterministic tie
    breaker that prefers a duplicate whose declared native artifact still
    exists and matches its content fingerprint over a duplicate left in a
    temporary directory that has already been removed.
    """

    if not receipt.subject_id.startswith("validation-owner:model:"):
        return None
    proof_path = _proof_path(receipt_root, receipt)
    if proof_path is None or not proof_path.is_file():
        return None
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(proof, Mapping):
        return None
    child = proof.get("child")
    if not isinstance(child, Mapping):
        return None
    payload = child.get("payload")
    if not isinstance(payload, Mapping):
        return None
    model_result = payload.get("model_result")
    if not isinstance(model_result, Mapping):
        return None
    normalized = _normalize_model_receipt_result(model_result)
    semantic_key = fingerprint_value(normalized)

    native_path_text = str(model_result.get("native_case_result_artifact_path", ""))
    native_fingerprint = str(
        model_result.get("native_case_result_artifact_fingerprint", "")
    )
    quality = 0
    if native_path_text:
        native_path = Path(native_path_text)
        if not native_path.is_absolute():
            native_path = repository_root / native_path
        try:
            if native_path.is_file() and native_fingerprint:
                quality = int(
                    _sha256_bytes(native_path.read_bytes()) == native_fingerprint
                )
        except OSError:
            quality = 0
    return semantic_key, quality


def _owner_receipt_context_for_proof(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    proof_fingerprint: str,
) -> ReceiptVerificationContext:
    return ReceiptVerificationContext(
        input_snapshots={current.input_snapshot.artifact_id: current.input_snapshot},
        contract_hash=current.contract_hash,
        check_manifest_hash=current.check_manifest_hash,
        suite_map_hash=current.suite_map_hash,
        producer_id=f"validation-owner:{current.contract.owner_id}",
        producer_version=_package_version(),
        environment_fingerprint=current.environment_fingerprint,
        proof_artifact_fingerprint=proof_fingerprint,
        result_fingerprint=proof_fingerprint,
        command=current.command,
        working_directory_token="<WORKSPACE>",
        proof_artifact_id=f"proof:validation-owner:{current.contract.owner_id}",
        required_obligation_ids=current.contract.obligation_ids,
        eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
    )


def find_reusable_owner_receipt(
    current: ValidationOwnerCurrent,
    root: str | Path,
    receipt_root: str | Path,
    *,
    receipt_inventory: Sequence[EvidenceReceipt] | None = None,
    child_receipts: Sequence[EvidenceReceipt] | None = None,
    child_verification_results: Sequence[ReceiptVerificationResult] | None = None,
    dependency_receipts: Mapping[str, EvidenceReceipt] | None = None,
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    """Find one independently verified exact-current owner receipt.

    Ordinary leaf owners use their direct proof context.  Aggregate owners
    may declare exact child receipts; callers that own that composition pass
    the frozen child receipts and their independently derived verification
    results so the candidate is checked against the same parent/child contract
    that publication will use.  Omitting either child argument intentionally
    keeps aggregate receipts in the ordinary stale/missing-child path instead
    of silently accepting an uncomposed parent.
    """

    if (child_receipts is None) != (child_verification_results is None):
        raise ValueError(
            "owner receipt reuse requires both child receipts and child verifications"
        )
    expected_dependency_bindings = (
        dependency_receipt_bindings(dependency_receipts)
        if dependency_receipts is not None
        else None
    )
    if expected_dependency_bindings is not None and set(dependency_receipts) != set(
        current.contract.dependency_owner_ids
    ):
        # A consumer may reuse only when every declared dependency has an
        # exact terminal receipt from the same observation.  In particular,
        # a dependency scheduled for execution in this invocation makes the
        # historical consumer receipt ineligible instead of allowing a
        # pass/fail-only dependency edge to preserve it.
        return None, None
    subject_id = f"validation-owner:{current.contract.owner_id}"
    inventory = (
        tuple(receipt_inventory)
        if receipt_inventory is not None
        else list_evidence_receipts(root, output_directory=receipt_root)
    )
    candidates = [
        item
        for item in inventory
        if item.subject_id == subject_id
    ]
    candidates.sort(key=lambda item: item.finished_at, reverse=True)
    last_result: ReceiptVerificationResult | None = None
    exact_current: list[EvidenceReceipt] = []
    for receipt in candidates:
        assert_validation_owner_receipt_integrity(receipt)
        # Historical owner receipts can number in the thousands.  Their
        # proof paths may point at old or externalized run directories, so
        # opening every proof just to discover that its frozen owner identity
        # is stale turns one observation into an unbounded I/O walk.  These
        # fields are already present in the immutable receipt and are exactly
        # the values the verifier compares against the current owner context;
        # reject a structurally stale candidate before touching its proof.
        if (
            receipt.metadata.get("owner_identity") != current.owner_identity
            or receipt.contract_hash != current.contract_hash
            or receipt.check_manifest_hash != current.check_manifest_hash
            or receipt.suite_map_hash != current.suite_map_hash
            or receipt.environment_fingerprint != current.environment_fingerprint
            or receipt.producer_id != f"validation-owner:{current.contract.owner_id}"
            or receipt.producer_version != _package_version()
            or receipt.claim_scope != OWNER_RECEIPT_SCOPE
            or receipt.command != current.command
            or receipt.working_directory_token != "<WORKSPACE>"
            or receipt.proof_artifact_id
            != f"proof:validation-owner:{current.contract.owner_id}"
            or len(receipt.input_snapshots) != 1
            or receipt.input_snapshots[0] != current.input_snapshot
            or receipt.covered_obligations != current.contract.obligation_ids
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.skipped_checks
            or receipt.blockers
        ):
            continue
        if (
            expected_dependency_bindings is not None
            and owner_receipt_dependency_bindings(receipt, receipt_root)
            != expected_dependency_bindings
        ):
            continue
        if child_receipts is None:
            context = build_owner_receipt_context(current, receipt, receipt_root)
        else:
            context = build_child_bound_owner_receipt_context(
                current,
                receipt,
                root,
                receipt_root,
                child_receipts=child_receipts,
                child_verification_results=child_verification_results or (),
            )
        result = verify_evidence_receipt(receipt, context)
        last_result = result
        if result.ok:
            exact_current.append(receipt)
            continue
        finding_codes = {finding.code for finding in result.findings}
        if finding_codes & {
            "proof_artifact_fingerprint_mismatch",
            "result_fingerprint_mismatch",
            "invalid_receipt",
        }:
            raise ValueError(
                "validation owner receipt or proof failed integrity verification"
            )
    if len(exact_current) > 1:
        # A model runner may be invoked more than once before the parent has
        # consumed the first result.  Each invocation can legitimately retain
        # its own evidence directory, producing distinct content-addressed
        # owner receipts even though the semantic model result is identical.
        # Converge only that narrowly-defined duplicate case.  If the model
        # payloads differ, preserve the fail-closed ambiguity boundary so a
        # parent can never silently choose between competing evidence.
        duplicate_groups: dict[str, list[tuple[int, EvidenceReceipt]]] = {}
        repository_root = Path(root).resolve()
        receipt_root_path = Path(receipt_root).resolve()
        for candidate in exact_current:
            duplicate = _model_receipt_duplicate_identity(
                candidate,
                receipt_root_path,
                repository_root,
            )
            if duplicate is None:
                duplicate_groups = {}
                break
            semantic_key, quality = duplicate
            duplicate_groups.setdefault(semantic_key, []).append(
                (quality, candidate)
            )
        if len(duplicate_groups) == 1:
            selected = max(
                next(iter(duplicate_groups.values())),
                key=lambda item: (
                    item[0],
                    item[1].finished_at,
                    item[1].receipt_id,
                ),
            )[1]
            context = build_owner_receipt_context(current, selected, receipt_root)
            verification = verify_evidence_receipt(selected, context)
            if verification.ok:
                return selected, verification
        raise ValueError(
            f"ambiguous exact-current receipts for {current.contract.owner_id}"
        )
    if exact_current:
        selected = exact_current[0]
        context = build_owner_receipt_context(current, selected, receipt_root)
        return selected, verify_evidence_receipt(selected, context)
    return None, last_result


def _receipt_inventory_identities(
    receipts: Sequence[EvidenceReceipt],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                item.subject_id,
                item.receipt_id,
                item.fingerprint,
            )
            for item in receipts
        )
    )


def _governed_owner_input_manifest(
    currents: Iterable[ValidationOwnerCurrent],
) -> tuple[Mapping[str, str], ...]:
    rows: dict[str, str] = {}
    for current in currents:
        for item in current.input_manifest:
            path = str(item["path"])
            if path.startswith("<projection:") or path.startswith("<external:"):
                continue
            fingerprint = str(item["sha256"])
            previous = rows.get(path)
            if previous is not None and previous != fingerprint:
                raise ValueError(
                    f"validation owners disagree on input identity: {path}"
                )
            rows[path] = fingerprint
    return tuple(
        {"path": path, "sha256": rows[path]}
        for path in sorted(rows)
    )


def _owner_observation_patterns(
    contracts: Sequence[ValidationOwnerContract],
) -> tuple[str, ...]:
    """Return the exact source selectors owned by one observation.

    An owner observation must not walk or hash an entire repository merely to
    discover whether an unrelated file changed.  The contracts already
    declare the complete freshness boundary, so the one shared filesystem
    observation is the union of those selectors.  An empty union is valid for
    a projection-only contract and intentionally observes no source files.
    """

    return tuple(
        dict.fromkeys(
            pattern
            for contract in contracts
            for pattern in contract.input_patterns
            if str(pattern)
        )
    )


def _validation_owner_observation(
    root: Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: Path,
    repository_input_manifest: Sequence[Mapping[str, str]],
    observation_patterns: Sequence[str],
    receipt_inventory: Sequence[EvidenceReceipt],
    started_at: float,
    prefer_latest_model_receipt: bool = False,
    metrics: InvocationMetrics | None = None,
) -> ValidationOwnerObservation:
    ordered_contracts = topological_owner_contracts(contracts)
    selection_inventory = tuple(receipt_inventory)
    if prefer_latest_model_receipt:
        # Keep the complete inventory for the observation/freshness
        # fingerprint, but give model-owner reuse one newest candidate per
        # owner. Historical receipts remain visible to the mutation guard;
        # they simply cannot create a duplicate semantic choice during this
        # bounded model repair.
        latest_model_receipts: dict[str, EvidenceReceipt] = {}
        filtered_inventory: list[EvidenceReceipt] = []
        for receipt in selection_inventory:
            subject_id = receipt.subject_id
            if not subject_id.startswith("validation-owner:model:"):
                filtered_inventory.append(receipt)
                continue
            previous = latest_model_receipts.get(subject_id)
            if previous is None or (
                receipt.finished_at,
                receipt.receipt_id,
            ) > (
                previous.finished_at,
                previous.receipt_id,
            ):
                latest_model_receipts[subject_id] = receipt
        selection_inventory = tuple(
            (*filtered_inventory, *latest_model_receipts.values())
        )
    currents: dict[str, ValidationOwnerCurrent] = {}
    reusable: dict[str, EvidenceReceipt] = {}
    verifications: dict[str, ReceiptVerificationResult] = {}
    rows: list[ValidationOwnerPlanRow] = []
    for contract in ordered_contracts:
        try:
            if metrics is not None:
                metrics.inc("owner_current_builds")
            current = _build_owner_current(
                root,
                contract,
                all_contracts=ordered_contracts,
                resolved_input_manifest=repository_input_manifest,
            )
            currents[contract.owner_id] = current
            dependency_receipts = (
                {
                    dependency_id: reusable[dependency_id]
                    for dependency_id in contract.dependency_owner_ids
                    if dependency_id in reusable
                }
                if contract.dependency_owner_ids
                else None
            )
            receipt, result = find_reusable_owner_receipt(
                current,
                root,
                receipt_root,
                receipt_inventory=selection_inventory,
                dependency_receipts=dependency_receipts,
            )
        except (OSError, ValueError) as exc:
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_BLOCKED,
                    "",
                    str(exc),
                )
            )
            continue
        if receipt is not None:
            if result is None or not result.ok:
                raise ValueError(
                    "exact-current validation owner receipt lacks its native "
                    f"verification: {contract.owner_id}"
                )
            reusable[contract.owner_id] = receipt
            verifications[contract.owner_id] = result
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_REUSE_CURRENT,
                    current.owner_identity,
                    "independently verified exact-current terminal receipt",
                    receipt.receipt_id,
                    receipt.fingerprint,
                )
            )
        else:
            findings = tuple(
                finding.code
                for finding in (result.findings if result is not None else ())
            )
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_EXECUTE,
                    current.owner_identity,
                    "no exact-current terminal-success receipt",
                    findings=findings,
                )
            )
    receipt_identities = _receipt_inventory_identities(receipt_inventory)
    payload = {
        "schema": "flowguard.validation_owner_observation.v1",
        "contracts": [item.to_dict() for item in ordered_contracts],
        "repository_input_manifest_fingerprint": manifest_fingerprint(
            repository_input_manifest
        ),
        "receipt_inventory_identities": [list(item) for item in receipt_identities],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "rows": [item.to_dict() for item in rows],
        "reusable_receipts": [
            {
                "owner_id": owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
                "verification": verifications[owner_id].to_dict(),
            }
            for owner_id, receipt in sorted(reusable.items())
        ],
    }
    return ValidationOwnerObservation(
        contracts=ordered_contracts,
        repository_input_manifest=tuple(
            dict(item) for item in repository_input_manifest
        ),
        observation_patterns=tuple(observation_patterns),
        receipt_inventory_identities=receipt_identities,
        rows=tuple(rows),
        owner_currents=tuple(
            currents[contract.owner_id]
            for contract in ordered_contracts
            if contract.owner_id in currents
        ),
        reusable_receipts=tuple(
            reusable[owner_id] for owner_id in sorted(reusable)
        ),
        reusable_verifications=tuple(
            verifications[owner_id] for owner_id in sorted(verifications)
        ),
        observation_fingerprint=fingerprint_value(payload),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
        receipt_inventory_mode=(
            "latest_model" if prefer_latest_model_receipt else "all"
        ),
        metrics=(metrics.snapshot() if metrics is not None else {}),
    )


@_bounded_git_observation
def observe_validation_owners(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
    additional_input_patterns: Sequence[str] = (),
    receipt_ids: Sequence[str] = (),
    prefer_latest_model_receipt: bool = False,
    metrics: InvocationMetrics | None = None,
) -> ValidationOwnerObservation:
    """Capture one strict owner observation for a bounded invocation."""

    started_at = time.perf_counter()
    ordered_contracts = topological_owner_contracts(contracts)
    root_path = Path(root).resolve()
    # Resolve and fingerprint the repository once for this planning invocation,
    # then project each owner's exact patterns from that single observation.
    # This is deliberately invocation-local: another plan resolves again so
    # source drift remains visible instead of becoming a cross-run cache hit.
    if metrics is not None:
        metrics.inc("source_manifest_builds")
    observation_patterns = tuple(
        dict.fromkeys(
            (
                *_owner_observation_patterns(ordered_contracts),
                *(str(item) for item in additional_input_patterns if str(item)),
            )
        )
    )
    repository_input_manifest = resolve_input_manifest(root_path, observation_patterns)
    # One planning pass observes one immutable receipt-store snapshot.  Loading
    # the complete store independently for every owner is both redundant and,
    # on long-lived repositories, quadratic in the owner count.  Final receipt
    # currentness is still verified per owner and later publication phases
    # re-read the store under their own freshness boundary.
    if metrics is not None:
        metrics.inc("receipt_directory_scans")
    subject_ids = tuple(
        f"validation-owner:{contract.owner_id}" for contract in ordered_contracts
    )
    if prefer_latest_model_receipt:
        if receipt_ids:
            raise ValueError(
                "latest model receipt selection cannot be combined with explicit receipt ids"
            )
        receipt_inventory = list_latest_evidence_receipts(
            root,
            output_directory=receipt_root,
            subject_ids=subject_ids,
        )
    else:
        receipt_inventory = list_evidence_receipts(
            root,
            output_directory=receipt_root,
            subject_ids=subject_ids,
            receipt_ids=receipt_ids,
        )
    return _validation_owner_observation(
        root_path,
        ordered_contracts,
        receipt_root=Path(receipt_root).resolve(),
        repository_input_manifest=repository_input_manifest,
        observation_patterns=observation_patterns,
        receipt_inventory=receipt_inventory,
        started_at=started_at,
        prefer_latest_model_receipt=prefer_latest_model_receipt,
        metrics=metrics,
    )


@_bounded_git_observation
def plan_validation_owners(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
    metrics: InvocationMetrics | None = None,
) -> tuple[
    tuple[ValidationOwnerPlanRow, ...],
    Mapping[str, ValidationOwnerCurrent],
    Mapping[str, EvidenceReceipt],
]:
    """Compatibility-free tuple projection of one explicit observation."""

    observation = observe_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
        metrics=metrics,
    )
    return (
        observation.rows,
        observation.current_by_owner,
        observation.receipt_by_owner,
    )


def refresh_validation_owner_observation_receipts(
    observation: ValidationOwnerObservation,
    root: str | Path,
    receipt_root: str | Path,
    supplied_receipts: Sequence[EvidenceReceipt],
) -> ValidationOwnerObservation:
    """Reconcile expected producer outputs without rescanning repository source.

    A model run may publish receipts after its source observation was frozen.
    This bounded refresh reads the canonical receipt store once, reuses native
    verifications for unchanged subjects, and verifies only newly supplied
    owner receipts against the already frozen current contexts.
    """

    started_at = time.perf_counter()
    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    supplied_by_owner: dict[str, EvidenceReceipt] = {}
    for receipt in supplied_receipts:
        _assert_owner_receipt_integrity(receipt)
        owner_id = receipt.subject_id.removeprefix("validation-owner:")
        if owner_id in supplied_by_owner:
            raise ValueError("supplied validation owner receipts must be unique")
        supplied_by_owner[owner_id] = receipt
    expected_owners = tuple(item.owner_id for item in observation.contracts)
    if set(supplied_by_owner) != set(expected_owners):
        raise ValueError(
            "supplied receipts do not exactly cover the frozen owner observation"
        )

    refresh_subject_ids = tuple(
        f"validation-owner:{contract.owner_id}"
        for contract in observation.contracts
    )
    inventory = (
        list_latest_evidence_receipts(
            root_path,
            output_directory=receipt_root_path,
            subject_ids=refresh_subject_ids,
        )
        if observation.receipt_inventory_mode == "latest_model"
        else list_evidence_receipts(
            root_path,
            output_directory=receipt_root_path,
            subject_ids=refresh_subject_ids,
        )
    )
    inventory_by_subject: dict[str, tuple[EvidenceReceipt, ...]] = {}
    for receipt in inventory:
        inventory_by_subject.setdefault(receipt.subject_id, []).append(receipt)
    initial_receipts = observation.receipt_by_owner
    initial_results = observation.verification_by_owner
    currents = observation.current_by_owner
    rows: list[ValidationOwnerPlanRow] = []
    reusable: dict[str, EvidenceReceipt] = {}
    verifications: dict[str, ReceiptVerificationResult] = {}
    for contract in observation.contracts:
        owner_id = contract.owner_id
        supplied = supplied_by_owner[owner_id]
        subject_id = f"validation-owner:{owner_id}"
        subject_inventory = tuple(inventory_by_subject.get(subject_id, ()))
        canonical = tuple(
            item
            for item in subject_inventory
            if item.receipt_id == supplied.receipt_id
            and item.fingerprint == supplied.fingerprint
        )
        if len(canonical) != 1:
            raise ValueError(
                f"supplied owner receipt is not canonical current: {owner_id}"
            )
        initial = initial_receipts.get(owner_id)
        dependency_receipts = (
            {
                dependency_id: supplied_by_owner[dependency_id]
                for dependency_id in contract.dependency_owner_ids
                if dependency_id in supplied_by_owner
            }
            if contract.dependency_owner_ids
            else None
        )
        if (
            not contract.dependency_owner_ids
            and initial is not None
            and (
                initial.receipt_id == supplied.receipt_id
                and initial.fingerprint == supplied.fingerprint
            )
        ):
            result = initial_results[owner_id]
        else:
            selected, result = find_reusable_owner_receipt(
                currents[owner_id],
                root_path,
                receipt_root_path,
                receipt_inventory=inventory,
                dependency_receipts=dependency_receipts,
            )
            if (
                selected is None
                or result is None
                or not result.ok
                or selected.receipt_id != supplied.receipt_id
                or selected.fingerprint != supplied.fingerprint
            ):
                raise ValueError(
                    f"new owner receipt failed exact-current verification: {owner_id}"
                )
        reusable[owner_id] = supplied
        verifications[owner_id] = result
        rows.append(
            ValidationOwnerPlanRow(
                owner_id,
                OWNER_REUSE_CURRENT,
                currents[owner_id].owner_identity,
                "independently verified exact-current terminal receipt",
                supplied.receipt_id,
                supplied.fingerprint,
            )
        )

    receipt_identities = _receipt_inventory_identities(inventory)
    payload = {
        "schema": "flowguard.validation_owner_observation.v1",
        "contracts": [item.to_dict() for item in observation.contracts],
        "repository_input_manifest_fingerprint": (
            observation.repository_input_manifest_fingerprint
        ),
        "receipt_inventory_identities": [list(item) for item in receipt_identities],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "rows": [item.to_dict() for item in rows],
        "reusable_receipts": [
            {
                "owner_id": owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
                "verification": verifications[owner_id].to_dict(),
            }
            for owner_id, receipt in sorted(reusable.items())
        ],
    }
    return ValidationOwnerObservation(
        contracts=observation.contracts,
        repository_input_manifest=observation.repository_input_manifest,
        observation_patterns=observation.observation_patterns,
        receipt_inventory_identities=receipt_identities,
        rows=tuple(rows),
        owner_currents=observation.owner_currents,
        reusable_receipts=tuple(
            reusable[owner_id] for owner_id in sorted(reusable)
        ),
        reusable_verifications=tuple(
            verifications[owner_id] for owner_id in sorted(verifications)
        ),
        observation_fingerprint=fingerprint_value(payload),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
        receipt_inventory_mode=observation.receipt_inventory_mode,
    )


def assert_validation_owner_observation_fresh(
    observation: ValidationOwnerObservation,
    root: str | Path,
    receipt_root: str | Path,
    *,
    additional_receipt_subject_ids: Sequence[str] = (),
    receipt_ids: Sequence[str] = (),
) -> ValidationObservationFreshness:
    """Make one fresh identity comparison without repeating native verifiers.

    ``receipt_ids`` is an optional exact inventory boundary for observations
    that were intentionally created from a declared receipt set (for example
    a model parent that names one immutable child per model).  Without this
    boundary the normal subject-scoped lookup also sees historical attempts
    for the same subject; that is correct for a broad owner observation, but
    would make a bounded parent observation appear stale every time an
    unrelated aggregate receipt is published.
    """

    started_at = time.perf_counter()
    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    current_manifest = resolve_input_manifest(
        root_path,
        observation.observation_patterns
        or _owner_observation_patterns(observation.contracts),
    )
    findings: list[str] = []

    current_owner_ids: dict[str, str] = {}
    current_owner_rows: list[ValidationOwnerCurrent] = []
    for contract in observation.contracts:
        current = _build_owner_current(
            root_path,
            contract,
            all_contracts=observation.contracts,
            resolved_input_manifest=current_manifest,
        )
        current_owner_ids[contract.owner_id] = current.owner_identity
        current_owner_rows.append(current)
    current_governed_manifest = _governed_owner_input_manifest(
        current_owner_rows
    )
    if manifest_fingerprint(current_manifest) != (
        observation.repository_input_manifest_fingerprint
    ):
        findings.append("repository_input_manifest_changed")
    expected_owner_ids = {
        owner_id: current.owner_identity
        for owner_id, current in observation.current_by_owner.items()
    }
    if current_owner_ids != expected_owner_ids:
        findings.append("validation_owner_context_changed")

    owner_subject_ids = {
        f"validation-owner:{contract.owner_id}"
        for contract in observation.contracts
    }
    baseline_subject_ids = {
        item[0] for item in observation.receipt_inventory_identities
    }
    subject_ids = set(owner_subject_ids)
    subject_ids.update(
        str(item).strip()
        for item in additional_receipt_subject_ids
        if str(item).strip() and str(item).strip() in baseline_subject_ids
    )
    if receipt_ids:
        inventory = list_evidence_receipts(
            root_path,
            output_directory=receipt_root_path,
            subject_ids=tuple(subject_ids),
            receipt_ids=tuple(
                sorted({str(item).strip() for item in receipt_ids if str(item).strip()})
            ),
        )
    elif observation.receipt_inventory_mode == "latest_model":
        inventory = list_latest_evidence_receipts(
            root_path,
            output_directory=receipt_root_path,
            subject_ids=tuple(subject_ids),
        )
    else:
        inventory = list_evidence_receipts(
            root_path,
            output_directory=receipt_root_path,
            subject_ids=tuple(subject_ids),
        )
    expected_receipts = tuple(
        item
        for item in observation.receipt_inventory_identities
        if item[0] in subject_ids
    )
    current_receipts = tuple(
        item
        for item in _receipt_inventory_identities(inventory)
        if item[0] in subject_ids
    )
    if current_receipts != expected_receipts:
        findings.append("validation_receipt_inventory_changed")

    final_payload = {
        "schema": "flowguard.validation_owner_freshness.v1",
        "initial_observation_fingerprint": observation.observation_fingerprint,
        "repository_input_manifest_fingerprint": manifest_fingerprint(
            current_manifest
        ),
        "owner_identities": current_owner_ids,
        "receipt_inventory_identities": [list(item) for item in current_receipts],
        "receipt_subject_ids": sorted(subject_ids),
        "findings": findings,
    }
    result = ValidationObservationFreshness(
        status="pass" if not findings else "blocked",
        initial_observation_fingerprint=observation.observation_fingerprint,
        final_observation_fingerprint=fingerprint_value(final_payload),
        findings=tuple(findings),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
        owner_currents=tuple(current_owner_rows),
    )
    if not result.ok:
        raise ValueError(
            "frozen validation owner observation changed before publication: "
            + ", ".join(result.findings)
        )
    return result


def assert_validation_owner_observation_receipts_fresh(
    source_observation: ValidationOwnerObservation,
    publication_observation: ValidationOwnerObservation,
    source_freshness: ValidationObservationFreshness,
    root: str | Path,
    receipt_root: str | Path,
    *,
    additional_receipt_subject_ids: Sequence[str] = (),
) -> ValidationObservationFreshness:
    """Complete one final boundary after batched leaf publication.

    The source observation is made once after all native producers terminate
    and before any new validation-owner leaf is published.  Publication then
    consumes those exact fresh owner contexts.  This function performs only
    the receipt-store half of the final comparison, so adding N leaf receipts
    cannot trigger N source-current rebuilds or a third repository scan.
    """

    started_at = time.perf_counter()
    if (
        not source_freshness.ok
        or source_freshness.initial_observation_fingerprint
        != source_observation.observation_fingerprint
    ):
        raise ValueError(
            "receipt freshness requires the matching passed source observation"
        )
    if (
        publication_observation.contracts != source_observation.contracts
        or publication_observation.repository_input_manifest
        != source_observation.repository_input_manifest
        or publication_observation.owner_currents
        != source_observation.owner_currents
    ):
        raise ValueError(
            "publication observation changed the frozen source or owner contexts"
        )
    final_currents = source_freshness.current_by_owner
    expected_currents = publication_observation.current_by_owner
    if (
        set(final_currents) != set(expected_currents)
        or any(
            final_currents[owner_id].owner_identity
            != expected_currents[owner_id].owner_identity
            for owner_id in expected_currents
        )
    ):
        raise ValueError(
            "final source observation does not own the publication contexts"
        )

    owner_subject_ids = {
        f"validation-owner:{contract.owner_id}"
        for contract in publication_observation.contracts
    }
    baseline_subject_ids = {
        item[0] for item in publication_observation.receipt_inventory_identities
    }
    subject_ids = set(owner_subject_ids)
    # An optional parent subject is tracked only when it was part of the
    # frozen inventory.  A pre-existing historical parent must not make a
    # scoped owner publication appear stale merely because the initial
    # observation intentionally loaded owner subjects only.
    subject_ids.update(
        str(item).strip()
        for item in additional_receipt_subject_ids
        if str(item).strip() and str(item).strip() in baseline_subject_ids
    )
    if publication_observation.receipt_inventory_mode == "latest_model":
        inventory = list_latest_evidence_receipts(
            Path(root).resolve(),
            output_directory=Path(receipt_root).resolve(),
            subject_ids=tuple(subject_ids),
        )
    else:
        inventory = list_evidence_receipts(
            Path(root).resolve(),
            output_directory=Path(receipt_root).resolve(),
            subject_ids=tuple(subject_ids),
        )
    expected_receipts = tuple(
        item
        for item in publication_observation.receipt_inventory_identities
        if item[0] in subject_ids
    )
    current_receipts = tuple(
        item
        for item in _receipt_inventory_identities(inventory)
        if item[0] in subject_ids
    )
    findings: list[str] = []
    if current_receipts != expected_receipts:
        findings.append("validation_receipt_inventory_changed")
    final_payload = {
        "schema": "flowguard.validation_owner_publication_freshness.v1",
        "source_observation_fingerprint": (
            source_observation.observation_fingerprint
        ),
        "source_freshness_fingerprint": (
            source_freshness.final_observation_fingerprint
        ),
        "publication_observation_fingerprint": (
            publication_observation.observation_fingerprint
        ),
        "receipt_inventory_identities": [list(item) for item in current_receipts],
        "receipt_subject_ids": sorted(subject_ids),
        "findings": findings,
    }
    result = ValidationObservationFreshness(
        status="pass" if not findings else "blocked",
        initial_observation_fingerprint=(
            publication_observation.observation_fingerprint
        ),
        final_observation_fingerprint=fingerprint_value(final_payload),
        findings=tuple(findings),
        observation_seconds=(
            source_freshness.observation_seconds
            + max(0.0, time.perf_counter() - started_at)
        ),
        owner_currents=source_freshness.owner_currents,
    )
    if not result.ok:
        raise ValueError(
            "validation receipt inventory changed before parent publication: "
            + ", ".join(result.findings)
        )
    return result


def build_owner_current_from_observation(
    root: str | Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    observation: ValidationOwnerObservation,
) -> ValidationOwnerCurrent:
    """Project another exact owner from the same frozen repository view."""

    return _build_owner_current(
        Path(root).resolve(),
        contract,
        all_contracts=all_contracts,
        resolved_input_manifest=observation.repository_input_manifest,
    )


@_bounded_git_observation
def build_validation_owner_plan(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
    required_external_components: Mapping[str, str] | None = None,
    metrics: InvocationMetrics | None = None,
    observation: ValidationOwnerObservation | None = None,
    claim_scope: str = VALIDATION_CLAIM_SCOPE_RELEASE,
) -> ValidationOwnerPlan:
    """Freeze the full owner DAG and both broad input manifests before execution."""

    if claim_scope not in VALIDATION_CLAIM_SCOPES:
        raise ValueError(
            "validation owner plan claim_scope must be local_validation or release"
        )

    root_path = Path(root).resolve()
    ordered_contracts = topological_owner_contracts(contracts)
    component_owners: dict[str, list[tuple[str, str]]] = {}
    for contract in ordered_contracts:
        for component_id, fingerprint in contract.external_component_bindings:
            component_owners.setdefault(component_id, []).append(
                (contract.owner_id, fingerprint)
            )
    conflicting_components = sorted(
        component_id
        for component_id, bindings in component_owners.items()
        if len({fingerprint for _owner_id, fingerprint in bindings}) != 1
    )
    if conflicting_components:
        raise ValueError(
            "external component consumers disagree on identity: "
            + ", ".join(conflicting_components)
        )
    required_components = {
        str(component_id): str(fingerprint)
        for component_id, fingerprint in (required_external_components or {}).items()
    }
    missing_components = sorted(set(required_components) - set(component_owners))
    extra_components = sorted(set(component_owners) - set(required_components))
    mismatched_components = sorted(
        component_id
        for component_id in set(required_components) & set(component_owners)
        if required_components[component_id] != component_owners[component_id][0][1]
    )
    if required_external_components is not None and (
        missing_components or extra_components or mismatched_components
    ):
        raise ValueError(
            "external component mapping is not exact: "
            f"missing={missing_components}, extra={extra_components}, "
            f"mismatched={mismatched_components}"
        )
    if observation is None:
        observation = observe_validation_owners(
            root_path,
            ordered_contracts,
            receipt_root=receipt_root,
            metrics=metrics,
        )
    elif observation.contracts != ordered_contracts:
        raise ValueError(
            "supplied validation owner observation does not match owner plan contracts"
        )
    rows = observation.rows
    currents = observation.current_by_owner
    reusable = observation.receipt_by_owner
    validation_manifest = _validation_input_manifest_from_observation(
        observation.repository_input_manifest
    )
    if metrics is not None:
        metrics.inc("validation_manifest_projections")
    if claim_scope == VALIDATION_CLAIM_SCOPE_RELEASE:
        tree_manifest = release_tree_manifest(root_path)
        if metrics is not None:
            metrics.inc("release_tree_manifest_builds")
    else:
        # A local functional parent deliberately has no release claim.  Keep
        # the exact release projection available to the explicit release
        # verifier, but do not make ordinary local completion stale when a
        # packaging/report/task file changes after the functional proof.
        tree_manifest = ()
    payload = {
        "schema_version": OWNER_PLAN_SCHEMA,
        "contracts": [
            {
                **item.to_dict(),
                "command": list(
                    _canonical_owner_command(
                        item.command,
                        workspace_root=root_path,
                    )
                ),
            }
            for item in ordered_contracts
        ],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "validation_input_manifest_fingerprint": manifest_fingerprint(
            validation_manifest
        ),
        "release_tree_manifest_fingerprint": manifest_fingerprint(tree_manifest),
        "claim_scope": claim_scope,
    }
    return ValidationOwnerPlan(
        contracts=ordered_contracts,
        rows=rows,
        owner_currents=currents,
        reusable_receipts=reusable,
        validation_input_manifest=validation_manifest,
        validation_input_manifest_fingerprint=payload[
            "validation_input_manifest_fingerprint"
        ],
        release_tree_manifest=tree_manifest,
        release_tree_manifest_fingerprint=payload[
            "release_tree_manifest_fingerprint"
        ],
        plan_fingerprint=fingerprint_value(payload),
        claim_scope=claim_scope,
    )


@_bounded_git_observation
def build_validation_parent_current(
    root: str | Path,
    owner_plan: ValidationOwnerPlan,
    *,
    frozen_validation_manifest: Sequence[Mapping[str, str]] | None = None,
    frozen_release_tree_manifest: Sequence[Mapping[str, str]] | None = None,
    metrics: InvocationMetrics | None = None,
) -> ValidationParentCurrent:
    """Derive one immutable parent identity from a previously frozen owner plan.

    Callers that already hold the frozen manifests may pass them explicitly;
    that projection performs no additional filesystem/Git observation.  The
    default path retains the strict freshness check for standalone callers.
    """

    root_path = Path(root).resolve()
    if owner_plan.blocked:
        raise ValueError("blocked validation owner plan cannot become parent current")
    if frozen_validation_manifest is None:
        # Re-observe exactly the source selectors frozen by this owner plan.
        # The plan intentionally uses the union of declared owner patterns;
        # rebuilding the historical broad repository manifest here would both
        # waste a second walk/hash pass and compare a different denominator.
        current_validation = _validation_input_manifest_from_observation(
            resolve_input_manifest(
                root_path,
                _owner_observation_patterns(owner_plan.contracts),
            )
        )
        if metrics is not None:
            metrics.inc("validation_manifest_rebuilds")
    else:
        current_validation = tuple(dict(item) for item in frozen_validation_manifest)
    if owner_plan.claim_scope == VALIDATION_CLAIM_SCOPE_RELEASE:
        if frozen_release_tree_manifest is None:
            current_tree = release_tree_manifest(root_path)
            if metrics is not None:
                metrics.inc("release_tree_manifest_rebuilds")
        else:
            current_tree = tuple(dict(item) for item in frozen_release_tree_manifest)
    else:
        # Local functional validation has no release-tree claim.  Ignore a
        # caller-supplied release projection rather than silently widening the
        # local parent boundary.
        current_tree = ()
    if (
        manifest_fingerprint(current_validation)
        != owner_plan.validation_input_manifest_fingerprint
        or manifest_fingerprint(current_tree)
        != owner_plan.release_tree_manifest_fingerprint
    ):
        raise ValueError("validation inputs changed after owner-plan freeze")
    obligations = tuple(
        obligation
        for contract in owner_plan.contracts
        for obligation in contract.obligation_ids
    )
    validation_snapshot = snapshot_bytes(
        "input:validation-parent:validation-input-manifest",
        _canonical_bytes([dict(item) for item in owner_plan.validation_input_manifest]),
        path_token="<WORKSPACE>/<VALIDATION_INPUT_MANIFEST>",
        obligation_ids=obligations,
    )
    tree_snapshot = snapshot_bytes(
        "input:validation-parent:release-tree-manifest",
        _canonical_bytes([dict(item) for item in owner_plan.release_tree_manifest]),
        path_token="<WORKSPACE>/<RELEASE_TREE_MANIFEST>",
        obligation_ids=obligations,
    )
    canonical_contracts = [
        {
            **item.to_dict(),
            "command": list(
                _canonical_owner_command(
                    item.command,
                    workspace_root=root_path,
                )
            ),
        }
        for item in owner_plan.contracts
    ]
    contract_hash = fingerprint_value(
        {"schema": OWNER_RECEIPT_SCHEMA, "owner": "validation-parent:full"}
    )
    check_manifest_hash = fingerprint_value(canonical_contracts)
    suite_map_hash = fingerprint_value(
        {
            item.owner_id: list(item.obligation_ids)
            for item in owner_plan.contracts
        }
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _package_version(),
        }
    )
    parent_identity = fingerprint_value(
        {
            "schema_version": PARENT_CURRENT_SCHEMA,
            "plan_fingerprint": owner_plan.plan_fingerprint,
            "validation_snapshot": validation_snapshot.to_dict(),
            "release_tree_snapshot": tree_snapshot.to_dict(),
            "contract_hash": contract_hash,
            "check_manifest_hash": check_manifest_hash,
            "suite_map_hash": suite_map_hash,
            "environment_fingerprint": environment.fingerprint,
        }
    )
    return ValidationParentCurrent(
        owner_plan=owner_plan,
        validation_snapshot=validation_snapshot,
        release_tree_snapshot=tree_snapshot,
        contract_hash=contract_hash,
        check_manifest_hash=check_manifest_hash,
        suite_map_hash=suite_map_hash,
        environment_metadata=environment.metadata,
        environment_fingerprint=environment.fingerprint,
        parent_identity=parent_identity,
    )


@dataclass(frozen=True)
class _PreparedOwnerReceipt:
    receipt: EvidenceReceipt
    proof_path: Path
    proof_bytes: bytes


def _prepare_owner_receipt(
    current: ValidationOwnerCurrent,
    child: ValidationChildResult,
    receipt_root: str | Path,
    *,
    started_at: str,
    finished_at: str,
    publication_kind: str,
) -> _PreparedOwnerReceipt:
    if publication_kind not in {"supervised_producer", "nonpass_record"}:
        raise ValueError("unsupported validation owner publication kind")
    if child.status == RECEIPT_STATUS_PASS and publication_kind != "supervised_producer":
        raise ValueError(
            "passing validation owner receipts require the supervised producer"
        )
    if publication_kind == "supervised_producer" and child.status != RECEIPT_STATUS_PASS:
        raise ValueError("supervised pass publication requires a passing child result")
    receipt_root_path = Path(receipt_root).resolve()
    proof_payload = {
        "schema_version": OWNER_RECEIPT_SCHEMA,
        "publication_kind": publication_kind,
        "owner_id": current.contract.owner_id,
        "owner_identity": current.owner_identity,
        "child": {
            "child_id": child.child_id,
            "status": child.status,
            "summary": child.summary,
            "nested_receipt_id": child.receipt_id,
            "claim_boundary": child.claim_boundary,
            "payload": dict(child.payload),
        },
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_name = proof_fingerprint.split(":", 1)[1] + ".json"
    proof_path = proof_dir / proof_name
    receipt = EvidenceReceipt(
        receipt_id=(
            f"receipt:validation-owner:{current.contract.owner_id}:"
            + "0" * 32
        ),
        subject_id=f"validation-owner:{current.contract.owner_id}",
        subject_kind=OWNER_RECEIPT_KIND,
        producer_id=f"validation-owner:{current.contract.owner_id}",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=current.command,
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0 if child.status == RECEIPT_STATUS_PASS else 1,
        environment_fingerprint=current.environment_fingerprint,
        environment_metadata=current.environment_metadata,
        contract_hash=current.contract_hash,
        check_manifest_hash=current.check_manifest_hash,
        suite_map_hash=current.suite_map_hash,
        input_snapshots=(current.input_snapshot,),
        proof_artifact_id=f"proof:validation-owner:{current.contract.owner_id}",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=_receipt_result_status(child.status),
        result_fingerprint=proof_fingerprint,
        covered_obligations=current.contract.obligation_ids,
        blockers=() if child.status == RECEIPT_STATUS_PASS else (f"owner_status:{child.status}",),
        claim_boundary=child.claim_boundary or "One native validation owner result.",
        metadata={
            "owner_identity": current.owner_identity,
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "publication_kind": publication_kind,
        },
    )
    receipt = replace(
        receipt,
        receipt_id=_content_addressed_receipt_id(
            f"receipt:validation-owner:{current.contract.owner_id}",
            receipt,
        ),
    )
    return _PreparedOwnerReceipt(receipt, proof_path, proof_bytes)


def _verify_prepared_owner_receipt(
    current: ValidationOwnerCurrent,
    prepared: _PreparedOwnerReceipt,
) -> ReceiptVerificationResult:
    return verify_evidence_receipt(
        prepared.receipt,
        _owner_receipt_context_for_proof(
            current,
            prepared.receipt,
            _sha256_bytes(prepared.proof_bytes),
        ),
    )


def _publish_content_addressed_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("content-addressed validation proof collision")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ValueError("content-addressed validation proof collision")
    finally:
        temporary.unlink(missing_ok=True)


def _publish_prepared_owner_receipt(
    prepared: _PreparedOwnerReceipt,
    root: str | Path,
    receipt_root: str | Path,
) -> EvidenceReceipt:
    """Publish a fully prepared result; an interruption can leave only a proof."""

    _publish_content_addressed_bytes(prepared.proof_path, prepared.proof_bytes)
    save_evidence_receipt(
        prepared.receipt,
        root,
        output_directory=Path(receipt_root).resolve(),
    )
    return prepared.receipt


def record_validation_owner_nonpass(
    current: ValidationOwnerCurrent,
    child: ValidationChildResult,
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    finished_at: str,
    source_freshness: ValidationObservationFreshness | None = None,
) -> EvidenceReceipt:
    """Record a fail/blocked/not-run owner result without a success path."""

    if child.status == RECEIPT_STATUS_PASS:
        raise ValueError(
            "record_validation_owner_nonpass cannot publish a passing receipt"
        )
    root_path = Path(root).resolve()
    if source_freshness is None:
        refreshed = build_owner_current(
            root_path,
            current.contract,
            all_contracts=tuple(all_contracts),
        )
    else:
        if not source_freshness.ok:
            raise ValueError(
                "validation owner nonpass publication requires fresh source observation"
            )
        refreshed = source_freshness.current_by_owner.get(current.contract.owner_id)
        if refreshed is None:
            raise ValueError(
                "validation owner nonpass publication is missing observed owner current"
            )
    if refreshed.owner_identity != current.owner_identity:
        raise ValueError("validation owner inputs changed before nonpass publication")
    prepared = _prepare_owner_receipt(
        refreshed,
        child,
        receipt_root,
        started_at=started_at,
        finished_at=finished_at,
        publication_kind="nonpass_record",
    )
    return _publish_prepared_owner_receipt(
        prepared,
        root_path,
        receipt_root,
    )


def build_child_bound_owner_receipt_context(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    root: str | Path,
    receipt_root: str | Path,
    *,
    child_receipts: Sequence[EvidenceReceipt],
    child_verification_results: Sequence[ReceiptVerificationResult],
    receipt_store_receipt_ids: Sequence[str] = (),
) -> ReceiptVerificationContext:
    """Build currentness context for an owner receipt that composes real children."""

    base = build_owner_receipt_context(current, receipt, receipt_root)
    if base is None:
        raise ValueError(
            f"owner proof is missing for child-bound receipt {receipt.receipt_id}"
        )
    children_by_id = {item.receipt_id: item for item in child_receipts}
    if len(children_by_id) != len(child_receipts):
        raise ValueError("child-bound owner receipt children must be unique")
    results_by_id = {item.receipt_id: item for item in child_verification_results}
    if len(results_by_id) != len(child_verification_results):
        raise ValueError(
            "child-bound owner receipt verification results must be unique"
        )
    if set(results_by_id) != set(children_by_id):
        raise ValueError(
            "child-bound owner receipt requires one verification per child"
        )
    return replace(
        base,
        child_receipts=children_by_id,
        child_verification_results=results_by_id,
        receipt_store_repository_root=str(Path(root).resolve()),
        receipt_store_output_directory=str(Path(receipt_root).resolve()),
        receipt_store_subject_ids=(
            receipt.subject_id,
            *tuple(sorted({child.subject_id for child in child_receipts})),
        ),
        receipt_store_receipt_ids=tuple(
            sorted(
                {
                    str(item).strip()
                    for item in receipt_store_receipt_ids
                    if str(item).strip()
                }
            )
        ),
    )


@dataclass(frozen=True)
class _DerivedExactChildReceipt:
    contract: ValidationOwnerContract
    current: ValidationOwnerCurrent
    receipt: EvidenceReceipt
    verification: ReceiptVerificationResult


def _refresh_child_bound_owner_current(
    current: ValidationOwnerCurrent,
    root: Path,
    all_contracts: Sequence[ValidationOwnerContract],
) -> ValidationOwnerCurrent:
    universe = topological_owner_contracts(all_contracts)
    matching = tuple(
        contract
        for contract in universe
        if contract.owner_id == current.contract.owner_id
    )
    if len(matching) != 1 or matching[0] != current.contract:
        raise ValueError(
            "child-bound owner contract universe does not exactly own the aggregate"
        )
    refreshed = build_owner_current(
        root,
        matching[0],
        all_contracts=universe,
    )
    if refreshed.owner_identity != current.owner_identity:
        raise ValueError("child-bound owner inputs changed before publication")
    return refreshed


def _derive_exact_current_child_receipts(
    root: Path,
    receipt_root: Path,
    child_receipts: Sequence[EvidenceReceipt],
    child_contracts: Sequence[ValidationOwnerContract],
) -> tuple[_DerivedExactChildReceipt, ...]:
    """Rebuild child currentness from exact contracts and the canonical store."""

    ordered_contracts = topological_owner_contracts(child_contracts)
    if not ordered_contracts:
        raise ValueError("child-bound owner receipt requires child contracts")
    supplied_by_subject: dict[str, EvidenceReceipt] = {}
    for child in child_receipts:
        assert_validation_owner_receipt_integrity(child)
        if child.subject_id in supplied_by_subject:
            raise ValueError(
                "child-bound owner receipt child subjects must be unique"
            )
        supplied_by_subject[child.subject_id] = child
    expected_subjects = {
        f"validation-owner:{contract.owner_id}" for contract in ordered_contracts
    }
    if set(supplied_by_subject) != expected_subjects:
        raise ValueError(
            "child-bound owner receipt subjects do not exactly match child contracts"
        )

    # The caller supplies the immutable children from an already verified
    # parent/authority boundary.  Address those exact receipt files instead of
    # rescanning the append-only historical store by subject for every child.
    # Ordinary plan_validation_owners callers keep their broad subject-scoped
    # audit because they do not have this frozen identity set.
    try:
        observation = observe_validation_owners(
            root,
            ordered_contracts,
            receipt_root=receipt_root,
            receipt_ids=tuple(item.receipt_id for item in child_receipts),
        )
    except ValueError as exc:
        # Keep the public child-boundary diagnostic stable when one declared
        # immutable child path is missing: an exact-ID lookup must fail closed,
        # but callers should still see the same "not exact-current" boundary
        # rather than a low-level filename error.
        raise ValueError(
            "child-bound owner child evidence is not exact-current: " + str(exc)
        ) from exc
    rows = observation.rows
    currents = observation.current_by_owner
    reusable = observation.receipt_by_owner
    noncurrent = tuple(
        f"{row.owner_id} ({row.reason})"
        for row in rows
        if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ValueError(
            "child-bound owner child evidence is not exact-current: "
            + ", ".join(noncurrent)
        )

    derived: list[_DerivedExactChildReceipt] = []
    for contract in ordered_contracts:
        subject_id = f"validation-owner:{contract.owner_id}"
        supplied = supplied_by_subject[subject_id]
        canonical = reusable[contract.owner_id]
        current = currents[contract.owner_id]
        if (
            supplied.receipt_id != canonical.receipt_id
            or supplied.fingerprint != canonical.fingerprint
        ):
            raise ValueError(
                f"child-bound owner receipt is not canonical current: {contract.owner_id}"
            )
        assert_validation_owner_receipt_integrity(canonical)
        if canonical.required_child_receipts or canonical.consumed_child_receipts:
            raise ValueError(
                "child-bound owner composition accepts exact terminal leaf receipts only"
            )
        if (
            canonical.subject_id != subject_id
            or canonical.subject_kind != OWNER_RECEIPT_KIND
            or canonical.producer_id != subject_id
            or canonical.claim_scope != OWNER_RECEIPT_SCOPE
            or canonical.result_status != RECEIPT_STATUS_PASS
            or canonical.exit_code != 0
            or canonical.skipped_checks
            or canonical.blockers
            or canonical.covered_obligations != contract.obligation_ids
            or str(canonical.metadata.get("publication_kind", ""))
            != "supervised_producer"
            or str(canonical.metadata.get("owner_identity", ""))
            != current.owner_identity
        ):
            raise ValueError(
                f"child-bound owner child is not one exact supervised leaf: {contract.owner_id}"
            )
        context = build_owner_receipt_context(current, canonical, receipt_root)
        verification = verify_evidence_receipt(canonical, context)
        if not verification.ok:
            raise ValueError(
                f"child-bound owner child failed fresh verification: {contract.owner_id}"
            )
        if set(verification.satisfied_obligations) != set(contract.obligation_ids):
            raise ValueError(
                f"child-bound owner child obligation mismatch: {contract.owner_id}"
            )
        derived.append(
            _DerivedExactChildReceipt(
                contract=contract,
                current=current,
                receipt=canonical,
                verification=verification,
            )
        )
    return tuple(sorted(derived, key=lambda item: item.receipt.receipt_id))


def _derived_exact_child_identity(
    children: Sequence[_DerivedExactChildReceipt],
) -> tuple[tuple[str, str, str, str, Mapping[str, Any]], ...]:
    return tuple(
        (
            item.contract.owner_id,
            item.current.owner_identity,
            item.receipt.receipt_id,
            item.receipt.fingerprint,
            item.verification.to_dict(),
        )
        for item in children
    )


def _save_child_bound_owner_receipt_from_derived(
    publication_current: ValidationOwnerCurrent,
    publication_children: Sequence[_DerivedExactChildReceipt],
    root_path: Path,
    receipt_root_path: Path,
    *,
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    root_path = Path(root_path).resolve()
    receipt_root_path = Path(receipt_root_path).resolve()
    ordered_children = tuple(item.receipt for item in publication_children)
    child_ids = tuple(item.receipt_id for item in ordered_children)

    proof_payload = {
        "schema_version": "flowguard.child_bound_validation_owner_proof.v1",
        "owner_id": publication_current.contract.owner_id,
        "owner_identity": publication_current.owner_identity,
        "covered_obligations": list(publication_current.contract.obligation_ids),
        "children": [
            {
                "receipt_id": child.receipt_id,
                "receipt_fingerprint": child.fingerprint,
                "subject_id": child.subject_id,
                "covered_obligations": list(child.covered_obligations),
            }
            for child in ordered_children
        ],
        "evidence_context": dict(evidence_context),
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_path = proof_dir / (
        "owner-aggregate-" + proof_fingerprint.split(":", 1)[1] + ".json"
    )

    receipt = EvidenceReceipt(
        receipt_id=(
            f"receipt:validation-owner:{publication_current.contract.owner_id}:"
            + "0" * 32
        ),
        subject_id=f"validation-owner:{publication_current.contract.owner_id}",
        subject_kind=OWNER_RECEIPT_KIND,
        producer_id=f"validation-owner:{publication_current.contract.owner_id}",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=publication_current.command,
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0,
        environment_fingerprint=publication_current.environment_fingerprint,
        environment_metadata=publication_current.environment_metadata,
        contract_hash=publication_current.contract_hash,
        check_manifest_hash=publication_current.check_manifest_hash,
        suite_map_hash=publication_current.suite_map_hash,
        input_snapshots=(publication_current.input_snapshot,),
        proof_artifact_id=(
            f"proof:validation-owner:{publication_current.contract.owner_id}"
        ),
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=proof_fingerprint,
        covered_obligations=publication_current.contract.obligation_ids,
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                receipt_id=child.receipt_id,
                subject_id=child.subject_id,
                obligation_ids=child.covered_obligations,
                eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
                expected_receipt_fingerprint=child.fingerprint,
            )
            for child in ordered_children
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(child.receipt_id, child.fingerprint)
            for child in ordered_children
        ),
        claim_boundary=claim_boundary,
        metadata={
            "owner_identity": publication_current.owner_identity,
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "child_receipt_ids": list(child_ids),
        },
    )
    receipt = replace(
        receipt,
        receipt_id=_content_addressed_receipt_id(
            f"receipt:validation-owner:{publication_current.contract.owner_id}",
            receipt,
        ),
    )

    _publish_content_addressed_bytes(proof_path, proof_bytes)
    save_evidence_receipt(
        receipt,
        root_path,
        output_directory=receipt_root_path,
    )

    context = build_child_bound_owner_receipt_context(
        publication_current,
        receipt,
        root_path,
        receipt_root_path,
        child_receipts=tuple(item.receipt for item in publication_children),
        child_verification_results=tuple(
            item.verification for item in publication_children
        ),
        receipt_store_receipt_ids=(receipt.receipt_id, *child_ids),
    )
    verification = verify_evidence_receipt(receipt, context)
    if not verification.ok:
        raise ValueError(
            "saved child-bound validation owner failed immediate verification: "
            + ", ".join(item.code for item in verification.findings)
        )
    return receipt, verification


def save_child_bound_owner_receipt(
    current: ValidationOwnerCurrent,
    child_receipts: Sequence[EvidenceReceipt],
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    child_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    """Persist one aggregate through an independently fresh direct invocation."""

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    publication_current = _refresh_child_bound_owner_current(
        current,
        root_path,
        all_contracts,
    )
    publication_children = _derive_exact_current_child_receipts(
        root_path,
        receipt_root_path,
        child_receipts,
        child_contracts,
    )
    receipt, verification = _save_child_bound_owner_receipt_from_derived(
        publication_current,
        publication_children,
        root_path,
        receipt_root_path,
        started_at=started_at,
        finished_at=finished_at,
        evidence_context=evidence_context,
        claim_boundary=claim_boundary,
    )
    final_current = _refresh_child_bound_owner_current(
        current,
        root_path,
        all_contracts,
    )
    final_children = _derive_exact_current_child_receipts(
        root_path,
        receipt_root_path,
        child_receipts,
        child_contracts,
    )
    if (
        final_current.owner_identity != publication_current.owner_identity
        or _derived_exact_child_identity(final_children)
        != _derived_exact_child_identity(publication_children)
    ):
        raise ValueError(
            "child-bound owner or children changed during atomic publication"
        )
    return receipt, verification


def save_child_bound_owner_receipt_from_observation(
    current: ValidationOwnerCurrent,
    child_owner_ids: Sequence[str],
    root: str | Path,
    receipt_root: str | Path,
    *,
    observation: ValidationOwnerObservation,
    freshness: ValidationObservationFreshness,
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    """Publish one aggregate from a passed invocation-local freshness boundary."""

    if (
        not freshness.ok
        or freshness.initial_observation_fingerprint
        != observation.observation_fingerprint
    ):
        raise ValueError(
            "child-bound observation publication requires a matching final freshness pass"
        )
    owner_ids = tuple(sorted({str(item) for item in child_owner_ids if str(item)}))
    if not owner_ids:
        raise ValueError("child-bound observation publication requires children")
    currents = observation.current_by_owner
    receipts = observation.receipt_by_owner
    verifications = observation.verification_by_owner
    if any(
        owner_id not in currents
        or owner_id not in receipts
        or owner_id not in verifications
        for owner_id in owner_ids
    ):
        raise ValueError(
            "child-bound observation does not contain every exact child owner"
        )
    derived: list[_DerivedExactChildReceipt] = []
    for owner_id in owner_ids:
        contract = currents[owner_id].contract
        receipt = receipts[owner_id]
        verification = verifications[owner_id]
        _assert_owner_receipt_integrity(receipt)
        if (
            not verification.ok
            or verification.receipt_id != receipt.receipt_id
            or receipt.subject_id != f"validation-owner:{owner_id}"
            or receipt.subject_kind != OWNER_RECEIPT_KIND
            or receipt.producer_id != receipt.subject_id
            or receipt.claim_scope != OWNER_RECEIPT_SCOPE
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.skipped_checks
            or receipt.blockers
            or receipt.covered_obligations != contract.obligation_ids
            or receipt.required_child_receipts
            or receipt.consumed_child_receipts
            or str(receipt.metadata.get("publication_kind", ""))
            != "supervised_producer"
            or str(receipt.metadata.get("owner_identity", ""))
            != currents[owner_id].owner_identity
        ):
            raise ValueError(
                f"observation child is not one exact supervised leaf: {owner_id}"
            )
        derived.append(
            _DerivedExactChildReceipt(
                contract=contract,
                current=currents[owner_id],
                receipt=receipt,
                verification=verification,
            )
        )
    return _save_child_bound_owner_receipt_from_derived(
        current,
        tuple(sorted(derived, key=lambda item: item.receipt.receipt_id)),
        Path(root).resolve(),
        Path(receipt_root).resolve(),
        started_at=started_at,
        finished_at=finished_at,
        evidence_context=evidence_context,
        claim_boundary=claim_boundary,
    )


def child_from_owner_receipt(
    receipt: EvidenceReceipt,
    receipt_root: str | Path,
) -> ValidationChildResult:
    proof_path = _proof_path(Path(receipt_root).resolve(), receipt)
    if proof_path is None or not proof_path.is_file():
        raise ValueError(f"owner proof is missing for {receipt.receipt_id}")
    payload = json.loads(proof_path.read_text(encoding="utf-8"))
    child = payload.get("child", {})
    if not isinstance(child, Mapping):
        raise ValueError("validation owner proof child is invalid")
    return ValidationChildResult(
        child_id=str(child.get("child_id", "")),
        status=str(child.get("status", "")),
        summary=str(child.get("summary", "")),
        receipt_id=receipt.receipt_id,
        artifact_paths=(str(proof_path),),
        claim_boundary=str(child.get("claim_boundary", "")),
        payload={
            **dict(child.get("payload", {})),
            "execution_disposition": OWNER_REUSE_CURRENT,
            "owner_receipt_fingerprint": receipt.fingerprint,
            "nested_receipt_id": str(child.get("nested_receipt_id", "")),
        },
    )


def save_parent_receipt(
    root: str | Path,
    receipt_root: str | Path,
    *,
    parent_current: ValidationParentCurrent,
    child_receipts: Sequence[EvidenceReceipt],
    status: str,
    started_at: str,
    finished_at: str,
    source_freshness: ValidationObservationFreshness | None = None,
) -> EvidenceReceipt:
    """Persist one parent composition over exact independently owned children."""

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    owner_plan = parent_current.owner_plan
    contracts = owner_plan.contracts
    if source_freshness is not None:
        if not source_freshness.ok:
            raise ValueError("parent publication requires a passed source freshness comparison")
        expected_currents = owner_plan.owner_currents
        observed_currents = source_freshness.current_by_owner
        if set(observed_currents) != set(expected_currents):
            raise ValueError("parent publication source observation does not cover the frozen owner plan")
        if any(
            observed_currents[owner_id].owner_identity != current.owner_identity
            for owner_id, current in expected_currents.items()
        ):
            raise ValueError("parent publication source observation changed before composition")
    if (
        build_validation_parent_current(
            root_path,
            owner_plan,
            frozen_validation_manifest=owner_plan.validation_input_manifest,
            frozen_release_tree_manifest=owner_plan.release_tree_manifest,
        ).parent_identity
        != parent_current.parent_identity
    ):
        raise ValueError("validation parent current changed before composition")
    by_subject = {item.subject_id: item for item in child_receipts}
    if len(by_subject) != len(child_receipts):
        raise ValueError("parent child subjects must be unique")
    required_receipts: list[tuple[ValidationOwnerContract, EvidenceReceipt]] = []
    for contract in contracts:
        receipt = by_subject.get(f"validation-owner:{contract.owner_id}")
        if receipt is None:
            raise ValueError(f"parent receipt is missing owner receipt: {contract.owner_id}")
        current = owner_plan.owner_currents.get(contract.owner_id)
        if current is None:
            raise ValueError(f"parent owner current is missing: {contract.owner_id}")
        context = build_owner_receipt_context(current, receipt, receipt_root_path)
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ValueError(
                f"parent child receipt is not exact-current: {contract.owner_id}"
            )
        required_receipts.append((contract, receipt))
    validation_fingerprint = owner_plan.validation_input_manifest_fingerprint
    validation_snapshot = parent_current.validation_snapshot
    tree_fingerprint = owner_plan.release_tree_manifest_fingerprint
    tree_snapshot = parent_current.release_tree_snapshot
    canonical_contracts = [
        {
            **item.to_dict(),
            "command": list(
                _canonical_owner_command(
                    item.command,
                    workspace_root=root_path,
                )
            ),
        }
        for item in contracts
    ]
    proof_payload = {
        "schema_version": "flowguard.validation_parent_proof.v3",
        "parent_identity": parent_current.parent_identity,
        "owner_plan_fingerprint": owner_plan.plan_fingerprint,
        "claim_scope": owner_plan.claim_scope,
        "validation_input_manifest_fingerprint": validation_fingerprint,
        "release_tree_manifest_fingerprint": tree_fingerprint,
        "contracts": canonical_contracts,
        "owner_plan": [item.to_dict() for item in owner_plan.rows],
        "children": [
            {
                "owner_id": contract.owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
            }
            for contract, receipt in required_receipts
        ],
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / (
        "parent-" + proof_fingerprint.split(":", 1)[1] + ".json"
    )
    if proof_path.exists() and proof_path.read_bytes() != proof_bytes:
        raise ValueError("content-addressed parent proof collision")
    if not proof_path.exists():
        proof_path.write_bytes(proof_bytes)
    receipt_id = (
        "receipt:validation-parent:full:"
        + fingerprint_value(
            {
                "proof_fingerprint": proof_fingerprint,
                "status": status,
                "finished_at": finished_at,
            }
        ).split(":", 1)[1][:24]
    )
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id="validation-parent:full",
        subject_kind="validation_parent",
        producer_id="validation-parent:full",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--scope", "full"),
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0 if status == RECEIPT_STATUS_PASS else 1,
        environment_fingerprint=parent_current.environment_fingerprint,
        environment_metadata=parent_current.environment_metadata,
        contract_hash=parent_current.contract_hash,
        check_manifest_hash=parent_current.check_manifest_hash,
        suite_map_hash=parent_current.suite_map_hash,
        input_snapshots=(validation_snapshot, tree_snapshot),
        proof_artifact_id="proof:validation-parent:full",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=_receipt_result_status(status),
        result_fingerprint=proof_fingerprint,
        covered_obligations=tuple(
            obligation
            for contract in contracts
            for obligation in contract.obligation_ids
        ),
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                receipt_id=receipt.receipt_id,
                subject_id=receipt.subject_id,
                obligation_ids=contract.obligation_ids,
                eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
                expected_receipt_fingerprint=receipt.fingerprint,
            )
            for contract, receipt in required_receipts
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(receipt.receipt_id, receipt.fingerprint)
            for _contract, receipt in required_receipts
        ),
        blockers=() if status == RECEIPT_STATUS_PASS else (f"parent_status:{status}",),
        claim_boundary=(
            "This parent composes exact-current native validation-owner receipts "
            "for one frozen validation-input manifest; the exact release-tree "
            "manifest is included only for an explicit release claim."
        ),
        metadata={
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "parent_identity": parent_current.parent_identity,
            "owner_plan_fingerprint": owner_plan.plan_fingerprint,
            "claim_scope": owner_plan.claim_scope,
            "validation_input_manifest_fingerprint": validation_fingerprint,
            "release_tree_manifest_fingerprint": tree_fingerprint,
        },
    )
    save_evidence_receipt(receipt, root_path, output_directory=receipt_root_path)
    _write_parent_receipt_index(
        parent_current.parent_identity,
        receipt,
        receipt_root_path,
    )
    verification = verify_parent_receipt(
        receipt,
        root_path,
        receipt_root_path,
        parent_current=parent_current,
        integrity_only=True,
    )
    if not verification.ok:
        raise ValueError(
            "saved validation parent failed immediate verification: "
            + ", ".join(item.code for item in verification.findings)
        )
    return receipt


def _verify_parent_receipt_integrity_only(
    parent: EvidenceReceipt,
    root_path: Path,
    receipt_root_path: Path,
    parent_current: ValidationParentCurrent,
) -> ReceiptVerificationResult:
    """Verify a just-published parent without rereading governed source.

    ``save_parent_receipt`` has already compared the live source against the
    frozen parent current before writing.  This post-save path therefore only
    checks the immutable proof, receipt, and child objects.  Calling the broad
    currentness resolver here would make a successful parent stale merely
    because its output files were written and would reintroduce the per-owner
    scan loop this module is intended to prevent.
    """

    proof_path = _proof_path(receipt_root_path, parent)
    if proof_path is None or not proof_path.is_file():
        return verify_evidence_receipt(parent, None)
    owner_plan = parent_current.owner_plan
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        contracts = topological_owner_contracts(
            tuple(
                ValidationOwnerContract.from_dict(item)
                for item in proof.get("contracts", ())
            )
        )
        # Parent proofs serialize canonical/tokenized commands, while the
        # invocation's frozen owner plan may retain the concrete command paths
        # used to launch producers.  Compare the proof against that same
        # canonical projection before using the invocation-local owner
        # currents below.
        canonical_owner_contracts = tuple(
            replace(
                contract,
                command=_canonical_owner_command(
                    contract.command,
                    workspace_root=root_path,
                ),
            )
            for contract in owner_plan.contracts
        )
        if contracts != canonical_owner_contracts:
            return verify_evidence_receipt(parent, None)
        if (
            str(proof.get("parent_identity", ""))
            != parent_current.parent_identity
            or str(proof.get("owner_plan_fingerprint", ""))
            != owner_plan.plan_fingerprint
            or str(proof.get("claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE))
            != owner_plan.claim_scope
            or str(parent.metadata.get("claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE))
            != owner_plan.claim_scope
            or str(parent.metadata.get("parent_identity", ""))
            != parent_current.parent_identity
        ):
            return verify_evidence_receipt(parent, None)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return verify_evidence_receipt(parent, None)

    child_receipts: dict[str, EvidenceReceipt] = {}
    child_results: dict[str, ReceiptVerificationResult] = {}
    contracts_by_subject = {
        f"validation-owner:{contract.owner_id}": contract
        for contract in contracts
    }
    for requirement in parent.required_child_receipts:
        try:
            child = load_evidence_receipt(
                requirement.receipt_id,
                root_path,
                output_directory=receipt_root_path,
            )
            contract = contracts_by_subject.get(child.subject_id)
            if contract is None:
                return verify_evidence_receipt(parent, None)
            current = owner_plan.owner_currents.get(contract.owner_id)
            if current is None:
                return verify_evidence_receipt(parent, None)
            child_context = build_owner_receipt_context(
                current,
                child,
                receipt_root_path,
            )
            child_result = verify_evidence_receipt(child, child_context)
        except (OSError, ValueError, TypeError):
            return verify_evidence_receipt(parent, None)
        child_receipts[child.receipt_id] = child
        child_results[child.receipt_id] = child_result

    proof_fingerprint = _sha256_bytes(proof_path.read_bytes())
    context = ReceiptVerificationContext(
        input_snapshots={
            parent_current.validation_snapshot.artifact_id: parent_current.validation_snapshot,
            parent_current.release_tree_snapshot.artifact_id: parent_current.release_tree_snapshot,
        },
        contract_hash=parent_current.contract_hash,
        check_manifest_hash=parent_current.check_manifest_hash,
        suite_map_hash=parent_current.suite_map_hash,
        producer_id="validation-parent:full",
        producer_version=_package_version(),
        environment_fingerprint=parent_current.environment_fingerprint,
        proof_artifact_fingerprint=proof_fingerprint,
        result_fingerprint=proof_fingerprint,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--scope", "full"),
        working_directory_token="<WORKSPACE>",
        proof_artifact_id="proof:validation-parent:full",
        required_obligation_ids=parent.covered_obligations,
        eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
        child_receipts=child_receipts,
        child_verification_results=child_results,
        receipt_store_repository_root=str(root_path),
        receipt_store_output_directory=str(receipt_root_path),
    )
    return verify_evidence_receipt(parent, context)


def verify_parent_receipt(
    receipt: EvidenceReceipt | str,
    root: str | Path,
    receipt_root: str | Path,
    *,
    parent_current: ValidationParentCurrent | None = None,
    integrity_only: bool = False,
    release_tree_current: bool = True,
) -> ReceiptVerificationResult:
    """Independently verify a parent plus every exact child receipt.

    Pass ``integrity_only=True`` together with the already frozen
    ``parent_current`` immediately after publication to verify only immutable
    artifacts.  The default retains the standalone live-currentness verifier
    for callers resolving historical receipts outside a publication boundary.
    ``release_tree_current=False`` keeps the functional owner inputs current
    while deferring the release-tree projection to a target-neutral candidate.
    """

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    parent = (
        load_evidence_receipt(receipt, root_path, output_directory=receipt_root_path)
        if isinstance(receipt, str)
        else receipt
    )
    if integrity_only:
        if parent_current is None:
            raise ValueError("integrity-only parent verification requires parent_current")
        return _verify_parent_receipt_integrity_only(
            parent,
            root_path,
            receipt_root_path,
            parent_current,
        )
    proof_path = _proof_path(receipt_root_path, parent)
    if proof_path is None or not proof_path.is_file():
        return verify_evidence_receipt(parent, None)
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        claim_scope = str(
            proof.get("claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE)
        ).strip().lower()
        if claim_scope not in VALIDATION_CLAIM_SCOPES:
            return verify_evidence_receipt(parent, None)
        contracts = tuple(
            ValidationOwnerContract.from_dict(item)
            for item in proof.get("contracts", ())
        )
        contracts = topological_owner_contracts(contracts)
        plan_rows = tuple(
            ValidationOwnerPlanRow(
                owner_id=str(item.get("owner_id", "")),
                disposition=str(item.get("disposition", "")),
                owner_identity=str(item.get("owner_identity", "")),
                reason=str(item.get("reason", "")),
                receipt_id=str(item.get("receipt_id", "")),
                receipt_fingerprint=str(item.get("receipt_fingerprint", "")),
                findings=tuple(str(value) for value in item.get("findings", ())),
            )
            for item in proof.get("owner_plan", ())
            if isinstance(item, Mapping)
        )
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return verify_evidence_receipt(parent, None)
    # Resolve the frozen union once and project every owner from that same
    # observation.  The standalone verifier is a read-only consumer; it must
    # not re-walk each owner's patterns and then repeat the walk while
    # reconstructing the parent plan.
    try:
        validation_manifest = _validation_input_manifest_from_observation(
            resolve_input_manifest(
                root_path,
                _owner_observation_patterns(contracts),
            )
        )
        currents = {
            contract.owner_id: _build_owner_current(
                root_path,
                contract,
                all_contracts=contracts,
                resolved_input_manifest=validation_manifest,
            )
            for contract in contracts
        }
    except (OSError, ValueError, TypeError):
        return verify_evidence_receipt(parent, None)
    child_receipts: dict[str, EvidenceReceipt] = {}
    child_results: dict[str, ReceiptVerificationResult] = {}
    for requirement in parent.required_child_receipts:
        try:
            child = load_evidence_receipt(
                requirement.receipt_id,
                root_path,
                output_directory=receipt_root_path,
            )
        except (OSError, ValueError):
            continue
        contract = next(
            (
                item
                for item in contracts
                if f"validation-owner:{item.owner_id}" == child.subject_id
            ),
            None,
        )
        if contract is None:
            continue
        try:
            current = currents.get(contract.owner_id)
            if current is None:
                continue
            child_context = build_owner_receipt_context(
                current,
                child,
                receipt_root_path,
            )
            child_result = verify_evidence_receipt(child, child_context)
        except (OSError, ValueError):
            continue
        child_receipts[child.receipt_id] = child
        child_results[child.receipt_id] = child_result
    validation_snapshot = snapshot_bytes(
        "input:validation-parent:validation-input-manifest",
        _canonical_bytes([dict(item) for item in validation_manifest]),
        path_token="<WORKSPACE>/<VALIDATION_INPUT_MANIFEST>",
        obligation_ids=parent.covered_obligations,
    )
    functional_only_release = (
        claim_scope == VALIDATION_CLAIM_SCOPE_RELEASE
        and not release_tree_current
    )
    stored_tree_fingerprint = str(
        parent.metadata.get("release_tree_manifest_fingerprint", "")
    )
    stored_tree_snapshot = next(
        (
            item
            for item in parent.input_snapshots
            if item.artifact_id == "input:validation-parent:release-tree-manifest"
        ),
        None,
    )
    if functional_only_release:
        # Do not walk/hash the target's current release tree here.  The
        # target-neutral candidate binds that projection; this parent check
        # proves only the functional owner DAG and its declared inputs.
        tree_manifest: tuple[Mapping[str, str], ...] = ()
        tree_fingerprint = stored_tree_fingerprint
        tree_snapshot = stored_tree_snapshot
        if tree_snapshot is None or not tree_fingerprint:
            return verify_evidence_receipt(parent, None)
    else:
        tree_manifest = (
            release_tree_manifest(root_path)
            if claim_scope == VALIDATION_CLAIM_SCOPE_RELEASE
            else ()
        )
        tree_fingerprint = manifest_fingerprint(tree_manifest)
        tree_snapshot = snapshot_bytes(
            "input:validation-parent:release-tree-manifest",
            _canonical_bytes([dict(item) for item in tree_manifest]),
            path_token="<WORKSPACE>/<RELEASE_TREE_MANIFEST>",
            obligation_ids=parent.covered_obligations,
        )
    try:
        validation_fingerprint = manifest_fingerprint(validation_manifest)
        plan_payload = {
            "schema_version": OWNER_PLAN_SCHEMA,
            "contracts": [
                {
                    **item.to_dict(),
                    "command": list(
                        _canonical_owner_command(
                            item.command,
                            workspace_root=root_path,
                        )
                    ),
                }
                for item in contracts
            ],
            "owner_identities": {
                owner_id: current.owner_identity
                for owner_id, current in sorted(currents.items())
            },
            "validation_input_manifest_fingerprint": validation_fingerprint,
            "release_tree_manifest_fingerprint": tree_fingerprint,
            "claim_scope": claim_scope,
        }
        owner_plan = ValidationOwnerPlan(
            contracts=contracts,
            rows=plan_rows,
            owner_currents=currents,
            reusable_receipts={},
            validation_input_manifest=validation_manifest,
            validation_input_manifest_fingerprint=validation_fingerprint,
            release_tree_manifest=tree_manifest,
            release_tree_manifest_fingerprint=tree_fingerprint,
            plan_fingerprint=fingerprint_value(plan_payload),
            claim_scope=claim_scope,
        )
        parent_current = (
            None
            if functional_only_release
            else build_validation_parent_current(root_path, owner_plan)
        )
    except (OSError, ValueError):
        return verify_evidence_receipt(parent, None)
    if functional_only_release:
        # The parent identity includes its historical release tree.  Compare
        # that immutable identity internally, but do not derive a new one from
        # an external target's current tree.  The validation-input fingerprint
        # still comes from the live owner observation and catches functional
        # changes.
        if (
            not str(parent.metadata.get("parent_identity", ""))
            or str(proof.get("parent_identity", ""))
            != str(parent.metadata.get("parent_identity", ""))
            or str(proof.get("owner_plan_fingerprint", ""))
            != owner_plan.plan_fingerprint
            or str(parent.metadata.get("claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE))
            != owner_plan.claim_scope
            or validation_fingerprint
            != str(parent.metadata.get("validation_input_manifest_fingerprint", ""))
            or validation_snapshot.raw_sha256
            != str(parent.metadata.get("validation_input_manifest_fingerprint", ""))
            or tree_snapshot.raw_sha256 != stored_tree_fingerprint
        ):
            return verify_evidence_receipt(parent, None)
        contract_hash = fingerprint_value(
            {"schema": OWNER_RECEIPT_SCHEMA, "owner": "validation-parent:full"}
        )
        canonical_contracts = [
            {
                **item.to_dict(),
                "command": list(
                    _canonical_owner_command(
                        item.command,
                        workspace_root=root_path,
                    )
                ),
            }
            for item in contracts
        ]
        check_manifest_hash = fingerprint_value(canonical_contracts)
        suite_map_hash = fingerprint_value(
            {
                item.owner_id: list(item.obligation_ids)
                for item in contracts
            }
        )
        environment = build_environment_fingerprint(
            {
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
                "platform_system": platform.system(),
                "platform_machine": platform.machine(),
                "flowguard_version": _package_version(),
            }
        )
        context_contract_hash = contract_hash
        context_check_manifest_hash = check_manifest_hash
        context_suite_map_hash = suite_map_hash
        context_environment_fingerprint = environment.fingerprint
    else:
        assert parent_current is not None
        if (
            str(parent.metadata.get("parent_identity", ""))
            != parent_current.parent_identity
            or str(proof.get("parent_identity", "")) != parent_current.parent_identity
            or str(proof.get("owner_plan_fingerprint", ""))
            != owner_plan.plan_fingerprint
            or str(parent.metadata.get("claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE))
            != owner_plan.claim_scope
        ):
            return verify_evidence_receipt(parent, None)
        context_contract_hash = parent_current.contract_hash
        context_check_manifest_hash = parent_current.check_manifest_hash
        context_suite_map_hash = parent_current.suite_map_hash
        context_environment_fingerprint = parent_current.environment_fingerprint
    proof_fingerprint = _sha256_bytes(proof_path.read_bytes())
    context = ReceiptVerificationContext(
        input_snapshots={
            validation_snapshot.artifact_id: validation_snapshot,
            tree_snapshot.artifact_id: tree_snapshot,
        },
        contract_hash=context_contract_hash,
        check_manifest_hash=context_check_manifest_hash,
        suite_map_hash=context_suite_map_hash,
        producer_id="validation-parent:full",
        producer_version=_package_version(),
        environment_fingerprint=context_environment_fingerprint,
        proof_artifact_fingerprint=proof_fingerprint,
        result_fingerprint=proof_fingerprint,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--scope", "full"),
        working_directory_token="<WORKSPACE>",
        proof_artifact_id="proof:validation-parent:full",
        required_obligation_ids=parent.covered_obligations,
        eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
        child_receipts=child_receipts,
        child_verification_results=child_results,
        receipt_store_repository_root=str(root_path),
        receipt_store_output_directory=str(receipt_root_path),
    )
    return verify_evidence_receipt(parent, context)


def _parent_receipt_index_path(
    parent_identity: str,
    receipt_root: Path,
) -> Path:
    """Return one sidecar index path for a parent identity.

    The index lives below a nested directory so the canonical top-level
    receipt inventory never mistakes it for an EvidenceReceipt.  Its name is
    derived from the requested identity and its content is checked before it
    is used as a lookup hint.
    """

    identity = str(parent_identity).strip()
    if not identity:
        raise ValueError("parent identity is required for receipt index")
    digest = fingerprint_value({"parent_identity": identity}).split(":", 1)[1]
    return receipt_root / "indexes" / f"parent-{digest}.json"


def _write_parent_receipt_index(
    parent_identity: str,
    receipt: EvidenceReceipt,
    receipt_root: Path,
) -> Path:
    """Publish a validated parent lookup hint without changing source inputs."""

    path = _parent_receipt_index_path(parent_identity, receipt_root)
    payload = {
        "schema_version": "flowguard.validation_parent_index.v1",
        "subject_id": "validation-parent:full",
        "parent_identity": str(parent_identity),
        "receipt_id": receipt.receipt_id,
        "receipt_fingerprint": receipt.fingerprint,
    }
    content = _canonical_bytes(payload) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("validation parent index content collision")
        return path
    temporary = path.with_name(f".{path.name}.tmp")
    # This path is output-only and content-addressed by parent identity.  A
    # normal replacement is sufficient for a single-owner save; an existing
    # different file remains a hard failure rather than being overwritten.
    temporary.write_bytes(content)
    try:
        try:
            temporary.rename(path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ValueError("validation parent index content collision")
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _read_parent_receipt_index(
    parent_identity: str,
    receipt_root: Path,
) -> Mapping[str, str] | None:
    path = _parent_receipt_index_path(parent_identity, receipt_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if (
        payload.get("schema_version") != "flowguard.validation_parent_index.v1"
        or payload.get("subject_id") != "validation-parent:full"
        or str(payload.get("parent_identity", "")) != str(parent_identity)
    ):
        return None
    receipt_id = str(payload.get("receipt_id", "")).strip()
    receipt_fingerprint = str(payload.get("receipt_fingerprint", "")).strip()
    if not receipt_id or not receipt_fingerprint:
        return None
    return {
        "receipt_id": receipt_id,
        "receipt_fingerprint": receipt_fingerprint,
    }


def _bounded_parent_receipt_candidates(
    root: Path,
    receipt_root: Path,
    parent_identity: str,
    *,
    limit: int = 32,
) -> list[EvidenceReceipt]:
    """Probe at most ``limit`` recent top-level receipt files as a legacy hint."""

    if not receipt_root.is_dir():
        return []
    files = sorted(
        (
            path
            for path in receipt_root.glob("*.json")
            if path.name != "CURRENT.json"
        ),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )[: max(0, int(limit))]
    candidates: list[EvidenceReceipt] = []
    for path in files:
        try:
            candidate = load_evidence_receipt(path, root)
        except (OSError, ValueError):
            continue
        if (
            candidate.subject_id == "validation-parent:full"
            and str(candidate.metadata.get("parent_identity", "")) == parent_identity
        ):
            candidates.append(candidate)
    return candidates


def find_reusable_parent_receipt(
    parent_current: ValidationParentCurrent,
    root: str | Path,
    receipt_root: str | Path,
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    """Resolve an exact-current full parent before considering child execution.

    The normal path reads one content-addressed parent index for the requested
    identity.  A bounded filename fallback is retained for stores created by
    older producers, but it never parses an unbounded receipt history.
    """

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    indexed = _read_parent_receipt_index(
        parent_current.parent_identity,
        receipt_root_path,
    )
    candidates: list[EvidenceReceipt] = []
    if indexed is not None:
        try:
            candidate = load_evidence_receipt(
                indexed["receipt_id"],
                root_path,
                output_directory=receipt_root_path,
            )
            if (
                candidate.subject_id == "validation-parent:full"
                and candidate.fingerprint == indexed["receipt_fingerprint"]
                and str(candidate.metadata.get("parent_identity", ""))
                == parent_current.parent_identity
            ):
                candidates.append(candidate)
        except (OSError, ValueError):
            # A stale or malformed pointer is not authority.  Use only the
            # bounded compatibility probe below, then block if it cannot find
            # an exact current candidate.
            candidates = []
    if not candidates:
        candidates = _bounded_parent_receipt_candidates(
            root_path,
            receipt_root_path,
            parent_current.parent_identity,
        )
    candidates.sort(key=lambda item: item.finished_at, reverse=True)
    verified: list[tuple[EvidenceReceipt, ReceiptVerificationResult]] = []
    last_result: ReceiptVerificationResult | None = None
    for candidate in candidates:
        # The caller has already frozen and observed this exact parent current
        # for the invocation.  Reuse therefore performs immutable
        # proof/child/pointer verification against that snapshot instead of
        # rebuilding every owner current and rescanning source once per leaf.
        result = verify_parent_receipt(
            candidate,
            root,
            receipt_root,
            parent_current=parent_current,
            integrity_only=True,
        )
        last_result = result
        if result.ok:
            verified.append((candidate, result))
    if len(verified) > 1:
        raise ValueError("ambiguous exact-current validation parent receipts")
    return verified[0] if verified else (None, last_result)


def _affected_relative_path(value: Any) -> str:
    from pathlib import PurePosixPath

    text = str(value).strip().replace("\\", "/")
    candidate = PurePosixPath(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("affected changed paths must be repository-relative")
    normalized = candidate.as_posix()
    if normalized != text:
        raise ValueError("affected changed paths must be normalized")
    return normalized


def _resolve_affected_source_path(root_path: Path, relative: str) -> Path:
    """Resolve one changed path without crossing a symlink/reparse boundary."""

    candidate = root_path / relative
    # ``resolve`` follows links, so use it only after checking every existing
    # component with lstat.  A changed-path map is an authority input; letting
    # it point outside the repository would make the resulting fingerprint
    # non-reproducible and would break the path -> component -> owner join.
    current = root_path
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            stat_result = current.lstat()
        except FileNotFoundError:
            break
        if current.is_symlink() or bool(
            getattr(stat_result, "st_file_attributes", 0) & 0x0400
        ):
            raise ValueError(f"affected changed path crosses a reparse point: {relative}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(
            f"affected changed path escapes repository root: {relative}"
        ) from exc
    return resolved


def _affected_declared_ids(value: Any, *, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{context} must be an array")
    values = tuple(str(item).strip() for item in value)
    if any(not item for item in values):
        raise ValueError(f"{context} contains an empty id")
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{context} must be sorted and duplicate-free")
    return values


def _affected_component_rows(
    component_bindings: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...]:
    """Normalize an explicitly authored path/component/owner map.

    The map is deliberately data-only.  It may be supplied as a list of rows,
    ``{component_id: row}``, or ``{path: row}``; no owner is inferred from a
    filename once an explicit map is present.
    """

    if component_bindings is None:
        return ()
    values: list[dict[str, Any]] = []
    if isinstance(component_bindings, Mapping):
        if "components" in component_bindings:
            raw = component_bindings["components"]
            if not isinstance(raw, (list, tuple)):
                raise ValueError("affected component bindings.components must be an array")
            values = [dict(item) for item in raw if isinstance(item, Mapping)]
            if len(values) != len(raw):
                raise ValueError("affected component binding rows must be objects")
        else:
            for key, item in component_bindings.items():
                if not isinstance(item, Mapping):
                    raise ValueError("affected component binding rows must be objects")
                row = dict(item)
                if "component_id" not in row:
                    row["component_id"] = str(key)
                # A path-keyed map is a convenient exact input form.
                if "paths" not in row and "path" not in row and "/" in str(key):
                    row["paths"] = [str(key)]
                values.append(row)
    elif isinstance(component_bindings, (list, tuple)):
        values = [dict(item) for item in component_bindings if isinstance(item, Mapping)]
        if len(values) != len(component_bindings):
            raise ValueError("affected component binding rows must be objects")
    else:
        raise ValueError("affected component bindings must be an object or array")
    normalized: list[dict[str, Any]] = []
    seen_components: set[str] = set()
    for index, row in enumerate(values):
        component_id = str(row.get("component_id", "")).strip()
        owner_value = row.get("direct_owner_id", row.get("owner_id", ""))
        if isinstance(owner_value, (list, tuple)):
            owners = tuple(str(item).strip() for item in owner_value if str(item).strip())
        else:
            owners = (str(owner_value).strip(),) if str(owner_value).strip() else ()
        raw_paths = row.get("paths", row.get("path", ()))
        if isinstance(raw_paths, str):
            raw_paths = (raw_paths,)
        if not isinstance(raw_paths, (list, tuple)):
            raise ValueError(f"affected component row {index} paths must be an array")
        paths = tuple(sorted({_affected_relative_path(item) for item in raw_paths}))
        if not component_id or not paths:
            raise ValueError(f"affected component row {index} requires id and paths")
        if component_id in seen_components:
            raise ValueError(f"duplicate affected component id: {component_id}")
        seen_components.add(component_id)
        fingerprint = str(row.get("fingerprint", "")).strip()
        if fingerprint and not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint):
            raise ValueError(f"affected component row {index} fingerprint is invalid")
        model_ids = _affected_declared_ids(
            row.get("model_obligation_ids", ()),
            context=f"affected component row {index} model_obligation_ids",
        )
        test_ids = _affected_declared_ids(
            row.get("test_owner_ids", ()),
            context=f"affected component row {index} test_owner_ids",
        )
        evidence_ids = _affected_declared_ids(
            row.get("evidence_owner_ids", ()),
            context=f"affected component row {index} evidence_owner_ids",
        )
        normalized.append(
            {
                "component_id": component_id,
                "paths": paths,
                "owners": owners,
                "fingerprint": fingerprint,
                "model_obligation_ids": model_ids,
                "test_owner_ids": test_ids,
                "evidence_owner_ids": evidence_ids,
            }
        )
    return tuple(sorted(normalized, key=lambda item: item["component_id"]))


def _affected_edge_rows(value: Any, *, context: str) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raw = value.items()
        rows = [(str(source), str(target)) for source, target in raw]
    elif isinstance(value, (list, tuple)):
        rows = []
        for item in value:
            if isinstance(item, Mapping):
                source = item.get("source", item.get("source_owner_id", ""))
                target = item.get("target", item.get("target_owner_id", ""))
                rows.append((str(source), str(target)))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                rows.append((str(item[0]), str(item[1])))
            else:
                raise ValueError(f"{context} rows must be source/target pairs")
    else:
        raise ValueError(f"{context} must be an object or array")
    result = tuple(sorted({(source.strip(), target.strip()) for source, target in rows}))
    if any(not source or not target for source, target in result):
        raise ValueError(f"{context} contains an empty owner id")
    return result


def _affected_receipt_root(root: Path, receipt_root: str | Path | None) -> Path:
    """Resolve the canonical validation-owner receipt store for an impact plan.

    Affected planning is allowed to *read* an explicitly selected receipt, but
    it must use the same canonical store as the full validation owner plan.
    Keeping this default here prevents a caller from accidentally treating a
    scratch/output directory (or a consumer installation) as receipt
    authority.  The optional argument is primarily useful to tests and to
    callers that already froze the owner store for the invocation.
    """

    if receipt_root is None:
        return (root / ".flowguard" / "evidence" / "validation-owners").resolve()
    return Path(receipt_root).expanduser().resolve()


def verify_affected_owner_receipt(
    root: str | Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    receipt_id: str,
    receipt_fingerprint: str,
    receipt_root: str | Path | None = None,
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    """Independently verify one supplied affected-owner receipt.

    The affected impact JSON is a selector, not an evidence authority.  A
    receipt id/hash pair is therefore only a hint until the canonical file is
    loaded and the native owner verifier compares its subject, owner current,
    obligation set, command, input snapshot, toolchain, environment, proof,
    terminal status, and eligibility.  Missing, foreign, stale, malformed, or
    otherwise non-current candidates return ``(None, result)`` so the caller
    can safely execute a valid producer instead of manufacturing a successful
    ``reuse_current`` row.

    This helper deliberately does not scan the receipt directory.  Addressing
    the one declared content id bounds affected planning and prevents a
    caller-injected historical/foreign receipt from being selected by a broad
    inventory lookup.
    """

    root_path = Path(root).resolve()
    store = _affected_receipt_root(root_path, receipt_root)
    receipt_id = str(receipt_id).strip()
    receipt_fingerprint = str(receipt_fingerprint).strip()
    if (
        not receipt_id
        or not receipt_fingerprint
        or any(character in receipt_id for character in ("/", "\\"))
        or Path(receipt_id).is_absolute()
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt_fingerprint)
    ):
        return None, None

    try:
        candidate = load_evidence_receipt(
            receipt_id,
            root_path,
            output_directory=store,
        )
    except (OSError, TypeError, ValueError):
        return None, None

    # The pair in an impact plan must identify the exact immutable bytes.  A
    # syntactically valid hash is not enough, and a receipt loaded from a
    # canonical filename is not enough when the supplied hash was copied or
    # relabelled by a caller.
    if candidate.fingerprint != receipt_fingerprint:
        return None, None
    expected_subject = f"validation-owner:{contract.owner_id}"
    if candidate.subject_id != expected_subject:
        return None, None

    try:
        current = build_owner_current(
            root_path,
            contract,
            all_contracts=tuple(all_contracts),
        )
        selected, result = find_reusable_owner_receipt(
            current,
            root_path,
            store,
            receipt_inventory=(candidate,),
        )
    except (OSError, TypeError, ValueError):
        return None, None
    if (
        selected is None
        or result is None
        or not result.current
        or not result.eligible
        or result.status != RECEIPT_STATUS_PASS
        or selected.receipt_id != receipt_id
        or selected.fingerprint != receipt_fingerprint
    ):
        return None, result
    return selected, result


def build_affected_impact_plan(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    changed_paths: Sequence[str],
    component_bindings: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    parent_edges: Sequence[tuple[str, str]] = (),
    cross_boundary_edges: Sequence[tuple[str, str]] = (),
    sibling_edges: Sequence[tuple[str, str]] = (),
    owner_dispositions: Mapping[str, str] | None = None,
    owner_identities: Mapping[str, str] | None = None,
    owner_receipts: Mapping[str, Mapping[str, str] | Sequence[str]] | None = None,
    receipt_root: str | Path | None = None,
) -> Any:
    """Build one exact current affected-impact receipt.

    This is a bounded selector, not a second validation runner.  Every changed
    path must resolve to one current component and exactly one direct owner;
    closure propagation follows only declared dependency, parent, cross-boundary
    and explicitly named sibling edges.  Missing/ambiguous mappings return a
    blocked receipt, so callers can report the reason without starting a
    producer.
    """

    from .affected_blueprint_reader import AffectedImpactOwner, AffectedImpactPlan

    root_path = Path(root).resolve()
    ordered_contracts = topological_owner_contracts(contracts)
    by_owner = {item.owner_id: item for item in ordered_contracts}
    blockers: list[str] = []
    normalized_paths: list[str] = []
    for item in changed_paths:
        try:
            normalized_paths.append(_affected_relative_path(item))
        except ValueError as exc:
            blockers.append(f"invalid_changed_path:{str(item).strip()}:{exc}")
    paths = tuple(sorted(set(normalized_paths)))
    if not paths:
        blockers.append("changed_paths_missing")

    try:
        rows = list(_affected_component_rows(component_bindings))
    except ValueError as exc:
        rows = []
        blockers.append(f"component_binding_invalid:{exc}")
    if paths:
        # Fill only genuinely missing path rows from the declared owner
        # patterns.  This makes a partial component map complete without
        # overriding explicit rows; a broad or overlapping contract remains
        # ambiguous and must be authored in the map rather than widening the
        # closure or falling back to a full run.
        mapped_paths = {
            path
            for row in rows
            for path in row["paths"]
        }
        for path in paths:
            if path in mapped_paths:
                continue
            matches = tuple(
                contract.owner_id
                for contract in ordered_contracts
                if any(_matches_declared_pattern(path, pattern) for pattern in contract.input_patterns)
            )
            if len(matches) == 1:
                rows.append(
                    {
                        "component_id": f"path:{path}",
                        "paths": (path,),
                        "owners": matches,
                        "fingerprint": "",
                        "model_obligation_ids": (),
                        "test_owner_ids": (),
                        "evidence_owner_ids": (),
                    }
                )
                mapped_paths.add(path)
            elif not matches:
                blockers.append(f"unmapped_path:{path}")
            else:
                blockers.append(f"ambiguous_path_owner:{path}:{','.join(sorted(matches))}")
    path_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for path in row["paths"]:
            path_rows.setdefault(path, []).append(row)
    for path in paths:
        candidates = path_rows.get(path, [])
        if not candidates:
            blockers.append(f"unmapped_path:{path}")
        elif len(candidates) != 1:
            blockers.append(f"ambiguous_path_component:{path}")
        elif len(candidates[0]["owners"]) != 1:
            blockers.append(
                f"ambiguous_component_owner:{candidates[0]['component_id']}"
            )

    component_file_fingerprints: dict[str, dict[str, str]] = {}
    component_explicit_fingerprints: dict[str, str] = {}
    direct_owners: set[str] = set()
    component_metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        owners = row["owners"]
        if len(owners) != 1:
            continue
        owner_id = owners[0]
        if owner_id not in by_owner:
            blockers.append(f"unknown_direct_owner:{owner_id}")
            continue
        selected_paths = tuple(path for path in row["paths"] if path in paths)
        if not selected_paths:
            blockers.append(f"component_not_changed:{row['component_id']}")
            continue
        if row["fingerprint"]:
            component_explicit_fingerprints[row["component_id"]] = row["fingerprint"]
        for path in selected_paths:
            try:
                file_path = _resolve_affected_source_path(root_path, path)
            except ValueError as exc:
                blockers.append(str(exc))
                continue
            if not file_path.is_file():
                blockers.append(f"changed_path_missing:{path}")
                continue
            fingerprint = source_file_fingerprint(file_path)
            component_file_fingerprints.setdefault(row["component_id"], {})[path] = fingerprint
            direct_owners.add(owner_id)
            metadata = component_metadata.setdefault(
                row["component_id"],
                {"model": set(), "test": set(), "evidence": set(), "owner": owner_id},
            )
            metadata["model"].update(row["model_obligation_ids"])
            metadata["test"].update(row["test_owner_ids"])
            metadata["evidence"].update(row["evidence_owner_ids"])

    # A component is a single current identity.  Multiple changed paths in the
    # same component are represented by one deterministic component fingerprint
    # over the complete path/fingerprint set, avoiding a false conflict merely
    # because two files belong to one component.
    dedup_components: dict[str, str] = {}
    for component_id, path_fingerprints in sorted(component_file_fingerprints.items()):
        explicit = component_explicit_fingerprints.get(component_id, "")
        if explicit:
            dedup_components[component_id] = explicit
        else:
            dedup_components[component_id] = fingerprint_value(
                {
                    "component_id": component_id,
                    "paths": [
                        {"path": path, "fingerprint": fingerprint}
                        for path, fingerprint in sorted(path_fingerprints.items())
                    ],
                }
            )

    for component_id in sorted(set(component_explicit_fingerprints) - set(component_file_fingerprints)):
        blockers.append(f"component_fingerprint_without_changed_file:{component_id}")

    known_owners = set(by_owner)
    edge_sets = {
        "parent": list(_affected_edge_rows(parent_edges, context="parent_edges")),
        "cross": list(_affected_edge_rows(cross_boundary_edges, context="cross_boundary_edges")),
        "sibling": list(_affected_edge_rows(sibling_edges, context="sibling_edges")),
    }
    # Validation owner dependencies are explicit owner edges.  A changed
    # dependency invalidates its consumer; unrelated owners remain untouched.
    dependency_edges = [
        (dependency_id, contract.owner_id)
        for contract in ordered_contracts
        for dependency_id in contract.dependency_owner_ids
    ]
    edge_sets["dependency"] = dependency_edges
    all_edges = tuple(sorted(set(edge for values in edge_sets.values() for edge in values)))
    for source, target in all_edges:
        if source not in known_owners or target not in known_owners:
            blockers.append(f"unknown_impact_edge:{source}->{target}")

    affected = set(direct_owners)
    pending = list(sorted(direct_owners))
    while pending:
        source = pending.pop(0)
        for edge_kind, edges in edge_sets.items():
            for left, right in edges:
                if left == source and right not in affected:
                    affected.add(right)
                    pending.append(right)
    required_parents = set()
    required_siblings = set()
    for left, right in edge_sets["parent"] + edge_sets["cross"]:
        if left in affected and right in affected:
            required_parents.add(right)
    for left, right in edge_sets["sibling"]:
        if left in affected and right in affected:
            required_siblings.add(right)

    dispositions = {str(key): str(value).strip() for key, value in (owner_dispositions or {}).items()}
    identities = {str(key): str(value).strip() for key, value in (owner_identities or {}).items()}
    receipts = owner_receipts or {}
    unknown_disposition_ids = sorted(set(dispositions) - affected)
    blockers.extend(f"unknown_owner_disposition:{item}" for item in unknown_disposition_ids)
    blockers.extend(
        f"unknown_owner_identity:{item}"
        for item in sorted(set(identities) - affected)
    )
    blockers.extend(
        f"unknown_owner_receipt:{item}"
        for item in sorted(set(receipts) - affected)
    )
    owner_rows: list[AffectedImpactOwner] = []
    model_ids: set[str] = set()
    test_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for owner_id in sorted(affected):
        contract = by_owner[owner_id]
        owner_model = set(contract.obligation_ids)
        owner_test = {owner_id}
        owner_evidence = {owner_id}
        for component_id, metadata in component_metadata.items():
            if metadata["owner"] == owner_id:
                owner_model.update(metadata["model"])
                owner_test.update(metadata["test"])
                owner_evidence.update(metadata["evidence"])
        model_ids.update(owner_model)
        test_ids.update(owner_test)
        evidence_ids.update(owner_evidence)
        disposition = dispositions.get(owner_id, OWNER_EXECUTE)
        if disposition not in (OWNER_EXECUTE, OWNER_REUSE_CURRENT, OWNER_BLOCKED):
            blockers.append(f"invalid_owner_disposition:{owner_id}:{disposition}")
            disposition = OWNER_BLOCKED
        # Affected plans are current selectors.  Their owner identity must be
        # derived from the same native owner-current builder used by full
        # validation, rather than being a caller-authored hash.  If the
        # identity cannot be observed safely, the owner is blocked before a
        # producer can be selected.
        current: ValidationOwnerCurrent | None = None
        try:
            current = build_owner_current(
                root_path,
                contract,
                all_contracts=ordered_contracts,
            )
        except (OSError, TypeError, ValueError) as exc:
            blockers.append(f"owner_current_invalid:{owner_id}:{exc}")
            disposition = OWNER_BLOCKED
        owner_identity = current.owner_identity if current is not None else ""
        supplied_identity = identities.get(owner_id, "")
        if supplied_identity and not re.fullmatch(r"sha256:[0-9a-f]{64}", supplied_identity):
            blockers.append(f"owner_identity_invalid:{owner_id}")
            disposition = OWNER_BLOCKED
        elif supplied_identity and owner_identity and supplied_identity != owner_identity:
            blockers.append(f"owner_identity_mismatch:{owner_id}")
            disposition = OWNER_BLOCKED
        if not owner_identity:
            owner_identity = fingerprint_value(
                {
                    "owner_id": owner_id,
                    "contract": contract.to_dict(),
                    "component_ids": sorted(
                        component_id
                        for component_id, metadata in component_metadata.items()
                        if metadata["owner"] == owner_id
                    ),
                }
            )
        receipt_id = ""
        receipt_fingerprint = ""
        receipt = receipts.get(owner_id)
        if receipt is not None:
            if isinstance(receipt, Mapping):
                receipt_id = str(receipt.get("receipt_id", "")).strip()
                receipt_fingerprint = str(receipt.get("receipt_fingerprint", receipt.get("fingerprint", ""))).strip()
            elif isinstance(receipt, (list, tuple)) and len(receipt) == 2:
                receipt_id, receipt_fingerprint = (str(item).strip() for item in receipt)
            else:
                blockers.append(f"owner_receipt_invalid:{owner_id}")
        if disposition == OWNER_REUSE_CURRENT:
            selected, verification = (None, None)
            if current is not None and receipt_id and receipt_fingerprint:
                selected, verification = verify_affected_owner_receipt(
                    root_path,
                    contract,
                    all_contracts=ordered_contracts,
                    receipt_id=receipt_id,
                    receipt_fingerprint=receipt_fingerprint,
                    receipt_root=receipt_root,
                )
            if (
                selected is not None
                and verification is not None
                and verification.current
                and verification.eligible
                and verification.status == RECEIPT_STATUS_PASS
            ):
                # Use the loaded immutable values, not the caller's spelling,
                # in the resulting plan.  The helper already compared both
                # values, but this keeps the projection deterministic.
                receipt_id = selected.receipt_id
                receipt_fingerprint = selected.fingerprint
            else:
                # A valid producer is available for every well-formed
                # ValidationOwnerContract.  Missing/stale/foreign/tampered
                # evidence therefore invalidates reuse only; it must not be
                # converted into a synthetic success row.  A later runner
                # executes this owner and publishes a fresh canonical receipt.
                disposition = (
                    OWNER_EXECUTE if current is not None else OWNER_BLOCKED
                )
                receipt_id = ""
                receipt_fingerprint = ""
        elif receipt_fingerprint and not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt_fingerprint):
            blockers.append(f"owner_receipt_fingerprint_invalid:{owner_id}")
            receipt_fingerprint = ""
        if disposition != OWNER_REUSE_CURRENT:
            # Receipt metadata is meaningful only for an independently
            # verified reuse row.  Do not let an execute/blocked row carry a
            # stale or caller-authored id that a later consumer might mistake
            # for evidence.
            receipt_id = ""
            receipt_fingerprint = ""
        if disposition == OWNER_BLOCKED:
            blockers.append(f"owner_blocked:{owner_id}")
        owner_rows.append(
            AffectedImpactOwner(
                owner_id=owner_id,
                disposition=disposition,
                model_obligation_ids=tuple(sorted(owner_model)),
                test_owner_ids=tuple(sorted(owner_test)),
                evidence_owner_ids=tuple(sorted(owner_evidence)),
                required_parent_owner_ids=tuple(sorted(required_parents.intersection(affected))),
                required_sibling_owner_ids=tuple(sorted(required_siblings.intersection(affected))),
                owner_identity=owner_identity,
                receipt_id=receipt_id,
                receipt_fingerprint=receipt_fingerprint,
            )
        )
    source_identity = {
        "changed_paths": list(paths),
        "changed_components": sorted(dedup_components.items()),
    }
    source_fingerprint = fingerprint_value(source_identity)
    model_fingerprint = fingerprint_value({"ids": sorted(model_ids)})
    test_fingerprint = fingerprint_value({"ids": sorted(test_ids)})
    owner_fingerprint = fingerprint_value(
        {"rows": [item.to_dict() for item in owner_rows]}
    )
    # Any malformed row is a producer-time blocker; retain a deterministic
    # receipt so the caller can see why no owner was started.
    blockers = tuple(sorted(set(blockers)))
    return AffectedImpactPlan(
        changed_paths=paths,
        changed_components=tuple(sorted(dedup_components.items())),
        affected_member_ids=tuple(sorted(affected)),
        affected_model_obligation_ids=tuple(sorted(model_ids)),
        affected_test_owner_ids=tuple(sorted(test_ids)),
        affected_evidence_owner_ids=tuple(sorted(evidence_ids)),
        required_parent_dependencies=tuple(sorted(required_parents)),
        required_sibling_dependencies=tuple(sorted(required_siblings)),
        unknown_impact_blockers=blockers,
        source_fingerprint=source_fingerprint,
        model_fingerprint=model_fingerprint,
        test_fingerprint=test_fingerprint,
        owner_fingerprint=owner_fingerprint,
        owner_rows=tuple(owner_rows),
        status="blocked" if blockers else "pass",
    )


def validate_affected_impact_plan(
    value: Mapping[str, Any] | Any,
    *,
    selected_member_ids: Sequence[str] = (),
) -> Any:
    """Load one current impact receipt and enforce an exact ``--member`` join."""

    from .affected_blueprint_reader import AffectedImpactPlan

    plan = value if isinstance(value, AffectedImpactPlan) else AffectedImpactPlan.from_dict(value)
    if selected_member_ids:
        selected = tuple(sorted({str(item).strip() for item in selected_member_ids if str(item).strip()}))
        if selected != plan.affected_member_ids:
            raise ValueError(
                "selected affected members do not exactly match the machine impact plan"
            )
    if not plan.ok:
        raise ValueError(
            "affected impact plan is not executable: "
            + ", ".join(plan.unknown_impact_blockers)
        )
    return plan


__all__ = [
    "build_affected_impact_plan",
    "GIT_QUERY_TIMEOUT_SECONDS",
    "SOURCE_OBSERVATION_TIMEOUT_SECONDS",
    "VALIDATION_CLAIM_SCOPE_LOCAL",
    "VALIDATION_CLAIM_SCOPE_RELEASE",
    "VALIDATION_CLAIM_SCOPES",
    "GitQueryAborted",
    "GitQueryCleanupUnconfirmed",
    "GitQueryTimeout",
    "OWNER_BLOCKED",
    "OWNER_DISPOSITIONS",
    "OWNER_EXECUTE",
    "OWNER_REUSE_CURRENT",
    "NESTED_OWNER_SELECTION_ENV",
    "ValidationOwnerContract",
    "ValidationOwnerCurrent",
    "ValidationOwnerObservation",
    "ValidationObservationFreshness",
    "ValidationOwnerPlan",
    "ValidationOwnerPlanRow",
    "ValidationParentCurrent",
    "assert_validation_owner_receipt_integrity",
    "assert_nested_owner_launch_allowed",
    "assert_validation_owner_observation_fresh",
    "assert_validation_owner_observation_receipts_fresh",
    "build_child_bound_owner_receipt_context",
    "build_owner_current",
    "build_owner_receipt_context",
    "build_validation_owner_plan",
    "build_validation_parent_current",
    "child_from_owner_receipt",
    "dependency_receipt_bindings",
    "find_reusable_parent_receipt",
    "find_reusable_owner_receipt",
    "filter_resolved_input_manifest",
    "governed_source_manifest",
    "git_observation_budget",
    "manifest_fingerprint",
    "project_manifest_authority_binding_fingerprint",
    "project_manifest_semantic_fingerprint",
    "project_manifest_semantic_payload",
    "nested_owner_launch_allowed",
    "model_authority_release_paths",
    "observe_validation_owners",
    "owner_receipt_dependency_bindings",
    "plan_validation_owners",
    "release_tree_manifest",
    "resolve_input_manifest",
    "validation_task_body_fingerprint",
    "selected_owner_ids",
    "record_validation_owner_nonpass",
    "refresh_validation_owner_observation_receipts",
    "save_child_bound_owner_receipt",
    "save_child_bound_owner_receipt_from_observation",
    "save_parent_receipt",
    "topological_owner_contracts",
    "validate_affected_impact_plan",
    "verify_affected_owner_receipt",
    "validation_input_manifest",
    "verify_parent_receipt",
]
