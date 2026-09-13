"""Prepare one finite completion-cycle repair link from real owner evidence.

This command is deliberately a consumer-only boundary.  It does not execute
an owner, refresh a model, install a projection, or mutate the completion
ledger.  It accepts a current completion-run manifest, resolves the previous
epoch only through the canonical ledger address, and admits repair evidence
only when every referenced validation-owner receipt and proof is independently
current for the manifest's repository state.

The output is the existing typed repair group and link consumed by the full
runner.  A caller-authored row is never treated as evidence by itself: the
receipt id, receipt fingerprint, owner current, proof binding, supervised
execution, and cleanup marker are all checked before the link producer is
called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.completion_epoch import (  # noqa: E402
    CompletionRepairAdmissionGroup,
    CompletionEpochPlan,
    CompletionEpochTerminalLedger,
    produce_completion_repair_link,
)
from flowguard.completion_run_manifest import (  # noqa: E402
    CompletionRunManifestError,
    load_manifest,
)
from flowguard.evidence_receipts import (  # noqa: E402
    EvidenceReceipt,
    RECEIPT_STATUS_PASS,
    ReceiptValidationError,
    fingerprint_value,
    load_evidence_receipt,
    receipt_path,
    verify_evidence_receipt,
)
from flowguard.validation_ownership import (  # noqa: E402
    OWNER_RECEIPT_SCOPE,
    assert_validation_owner_receipt_integrity,
    build_owner_current,
    find_reusable_owner_receipt,
    owner_receipt_dependency_bindings,
)
from scripts import check_flowguard_skill_suite as suite_command  # noqa: E402


_ROW_FIELDS = frozenset(
    {
        "artifact_fingerprint",
        "cleanup_confirmed",
        "input_fingerprint",
        "producer_invocations",
        "receipt_fingerprint",
        "receipt_id",
        "status",
    }
)
_SHA256 = "sha256:"


class CompletionRepairPreparationError(ValueError):
    """The supplied repair inputs cannot support a typed repair link."""


def _sha256_bytes(data: bytes) -> str:
    return _SHA256 + hashlib.sha256(data).hexdigest()


def _load_targeted_regression_evidence(
    value: Mapping[str, Any] | str | Path,
    root: Path,
) -> dict[str, Any]:
    """Load the narrow source-bound artifact used for repair admission."""

    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        path = Path(value).expanduser().resolve()
        if root not in path.parents or path.is_symlink() or not path.is_file():
            raise CompletionRepairPreparationError(
                "repair regression evidence must be a non-symlink file inside the repository"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CompletionRepairPreparationError(
                f"repair regression evidence is unreadable: {path}"
            ) from exc
    if not isinstance(payload, Mapping):
        raise CompletionRepairPreparationError("repair regression evidence must be an object")
    scope = str(payload.get("scope", "")).strip().lower()
    if scope not in {"patch_regression", "targeted_patch_regression"}:
        raise CompletionRepairPreparationError(
            "repair regression evidence scope must be patch_regression"
        )
    if "status" not in payload or str(payload.get("status", "")).strip().lower() not in {
        "pass",
        "passed",
        "success",
    }:
        raise CompletionRepairPreparationError("repair regression evidence is not a pass")
    if payload.get("exit_code", 0) != 0:
        raise CompletionRepairPreparationError("repair regression evidence exit_code is not zero")
    if payload.get("cleanup_confirmed", True) is not True:
        raise CompletionRepairPreparationError("repair regression evidence cleanup is not confirmed")
    if payload.get("skipped", False) is True:
        raise CompletionRepairPreparationError("repair regression evidence is skipped")
    if payload.get("tested_input_manifest", payload.get("input_fingerprint")) in (
        None,
        "",
        [],
        {},
    ):
        raise CompletionRepairPreparationError(
            "repair regression evidence is not bound to tested inputs"
        )
    return {str(key): item for key, item in payload.items()}


def prepare_completion_repair_admission(
    *,
    root: str | Path,
    previous_epoch_id: str,
    current_plan: CompletionEpochPlan,
    repair_regression_evidence: Mapping[str, Any] | str | Path,
    output_dir: str | Path,
    observation: Any | None = None,
    owner_plan: Any | None = None,
) -> dict[str, Any]:
    """Build one canonical repair admission without reserving an attempt.

    This is the new A05 core.  It consumes a frozen, unlinked current plan and
    an independently produced narrow regression artifact; it does not require
    a current completion manifest or any failed-owner full-pass receipt.  The
    returned repaired plan is still unclaimed and no terminal ledger or cycle
    reservation is written.
    """

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise CompletionRepairPreparationError(
            f"repository root is not a directory: {root_path}"
        )
    if not isinstance(current_plan, CompletionEpochPlan):
        raise CompletionRepairPreparationError("current_plan must be a CompletionEpochPlan")
    if current_plan.attempt_index != 0 or current_plan.full_producer_attempts != 0:
        raise CompletionRepairPreparationError(
            "repair admission requires an unclaimed current plan"
        )
    loaded = CompletionEpochTerminalLedger.load_for_epoch_id(previous_epoch_id, root_path)
    if loaded.is_absent:
        raise CompletionRepairPreparationError("completion repair predecessor ledger is missing")
    if loaded.is_invalid or loaded.ledger is None:
        raise CompletionRepairPreparationError(
            "completion repair predecessor ledger is invalid: "
            + (loaded.error or loaded.status)
        )
    previous_ledger = loaded.ledger
    previous_plan, previous_error = suite_command._reconstruct_previous_completion_plan(
        previous_ledger
    )
    if previous_error or previous_plan is None:
        raise CompletionRepairPreparationError(
            previous_error or "completion repair predecessor plan is unavailable"
        )
    bound = CompletionEpochTerminalLedger.load_for_plan(previous_plan, root_path)
    if not bound.is_valid or bound.ledger is None:
        raise CompletionRepairPreparationError(
            "completion repair predecessor ledger binding is invalid: "
            + (bound.error or bound.status)
        )
    regression = _load_targeted_regression_evidence(repair_regression_evidence, root_path)
    declared_owner_ids = regression.get("failed_owner_ids", regression.get("owner_ids"))
    failed_owner_ids = set(previous_ledger.terminal_action_ids) - set(
        previous_ledger.completed_terminal_action_ids
    )
    if declared_owner_ids is not None:
        if not isinstance(declared_owner_ids, (list, tuple)) or set(
            str(item).strip() for item in declared_owner_ids
        ) != failed_owner_ids:
            raise CompletionRepairPreparationError(
                "repair regression evidence failed-owner set does not match predecessor ledger"
            )
    tested_manifest = regression.get("tested_input_manifest")
    if isinstance(tested_manifest, Mapping):
        for field_name in (
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
            "owner_dag_fingerprint",
            "model_authority_fingerprint",
            "test_inventory_fingerprint",
        ):
            if field_name in tested_manifest and str(tested_manifest[field_name]) != str(
                getattr(current_plan, field_name)
            ):
                raise CompletionRepairPreparationError(
                    f"repair regression evidence current-input mismatch: {field_name}"
                )
    output_path = Path(output_dir).expanduser().resolve()
    if root_path not in output_path.parents and output_path != root_path:
        raise CompletionRepairPreparationError("repair admission output must remain inside repository")
    output_path.mkdir(parents=True, exist_ok=True)
    link_path = output_path / "repair-link.json"
    try:
        link = produce_completion_repair_link(
            previous_plan=previous_plan,
            current_plan=current_plan,
            previous_ledger=previous_ledger,
            repair_evidence={},
            repository_root=root_path,
            link_output_path=link_path,
            targeted_regression_evidence=regression,
        )
        repaired = CompletionEpochPlan.for_repair(
            previous_plan,
            source_observation_fingerprint=current_plan.source_observation_fingerprint,
            release_tree_fingerprint=current_plan.release_tree_fingerprint,
            toolchain_environment_fingerprint=current_plan.toolchain_environment_fingerprint,
            owner_dag_fingerprint=current_plan.owner_dag_fingerprint,
            model_authority_fingerprint=current_plan.model_authority_fingerprint,
            model_authority_head_fingerprint=current_plan.model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=current_plan.model_authority_snapshot_fingerprint,
            test_inventory_fingerprint=current_plan.test_inventory_fingerprint,
            required_terminal_action_ids=current_plan.required_terminal_action_ids,
            remaining_governed_write_ids=current_plan.remaining_governed_write_ids,
            repair_link=link,
        )
    except (TypeError, ValueError, KeyError, OverflowError, OSError) as exc:
        raise CompletionRepairPreparationError(
            f"typed completion repair admission was rejected: {type(exc).__name__}: {exc}"
        ) from exc
    blockers = repaired.validate_repair(previous_plan, previous_ledger)
    if blockers:
        raise CompletionRepairPreparationError(
            "completion repair admission blocked: " + ",".join(blockers)
        )
    group_path = CompletionRepairAdmissionGroup.path_for(root_path, link.repair_group_id)
    return {
        "status": "pass",
        "previous_ledger": previous_ledger,
        "previous_plan": previous_plan,
        "current_plan": current_plan,
        "repaired_plan": repaired,
        "repair_link": link,
        "repair_link_path": link_path,
        "repair_group_path": group_path,
        "producer_invocations": 0,
        "observation": observation,
        "owner_plan": owner_plan,
    }


def _is_sha256(value: Any) -> bool:
    text = str(value).strip()
    return len(text) == 71 and text.startswith(_SHA256) and all(
        character in "0123456789abcdef" for character in text[7:]
    )


def _repo_path(
    root: Path,
    value: str | Path,
    *,
    label: str,
    must_exist: bool = False,
    directory: bool = False,
) -> Path:
    """Resolve one path while rejecting links and repository escape."""

    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise CompletionRepairPreparationError(
            f"{label} must not be a symlink: {raw}"
        )
    candidate = raw.resolve()
    if candidate == root or root not in candidate.parents:
        raise CompletionRepairPreparationError(
            f"{label} must remain inside repository root: {candidate}"
        )
    relative = candidate.relative_to(root)
    cursor = root
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise CompletionRepairPreparationError(
                f"{label} contains a symlink component: {cursor}"
            )
    if must_exist and not candidate.exists():
        raise CompletionRepairPreparationError(
            f"{label} does not exist: {candidate}"
        )
    if directory and candidate.exists() and not candidate.is_dir():
        raise CompletionRepairPreparationError(
            f"{label} is not a directory: {candidate}"
        )
    return candidate


def _read_object(path: Path, *, label: str) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CompletionRepairPreparationError(
            f"{label} must be a real JSON file: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionRepairPreparationError(
            f"{label} cannot be read: {path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise CompletionRepairPreparationError(f"{label} must be a JSON object")
    return payload


def _manifest_plan(payload: Mapping[str, Any]) -> CompletionEpochPlan:
    plan = payload.get("plan")
    if not isinstance(plan, Mapping):
        raise CompletionRepairPreparationError(
            "completion run manifest plan is missing"
        )
    required = {
        "epoch_id",
        "completion_cycle_id",
        "completion_objective_fingerprint",
        "source_observation_fingerprint",
        "release_tree_fingerprint",
        "toolchain_environment_fingerprint",
        "owner_dag_fingerprint",
        "model_authority_fingerprint",
        "test_inventory_fingerprint",
        "required_terminal_action_ids",
        "remaining_governed_write_ids",
        "repair_link_fingerprint",
    }
    missing = sorted(name for name in required if name not in plan)
    if missing:
        raise CompletionRepairPreparationError(
            "completion run manifest plan is incomplete: " + ", ".join(missing)
        )
    if str(plan.get("repair_link_fingerprint", "")).strip():
        raise CompletionRepairPreparationError(
            "current repair input manifest must describe an unlinked attempt-0 plan"
        )
    remaining = plan.get("remaining_governed_write_ids", ())
    if not isinstance(remaining, (list, tuple)):
        raise CompletionRepairPreparationError(
            "current completion manifest governed-write projection is malformed"
        )
    if list(remaining):
        raise CompletionRepairPreparationError(
            "current repair input plan still has governed writes"
        )
    try:
        current = CompletionEpochPlan.freeze(
            source_observation_fingerprint=str(
                plan["source_observation_fingerprint"]
            ),
            release_tree_fingerprint=str(plan["release_tree_fingerprint"]),
            toolchain_environment_fingerprint=str(
                plan["toolchain_environment_fingerprint"]
            ),
            owner_dag_fingerprint=str(plan["owner_dag_fingerprint"]),
            model_authority_fingerprint=str(plan["model_authority_fingerprint"]),
            test_inventory_fingerprint=str(plan["test_inventory_fingerprint"]),
            completion_objective_fingerprint=str(
                plan["completion_objective_fingerprint"]
            ),
            required_terminal_action_ids=tuple(
                str(item) for item in plan["required_terminal_action_ids"]
            ),
            remaining_governed_write_ids=(),
            completion_cycle_id=str(plan["completion_cycle_id"]),
            attempt_index=0,
        )
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise CompletionRepairPreparationError(
            f"current completion plan is invalid: {type(exc).__name__}: {exc}"
        ) from exc
    if current.epoch_id != str(plan["epoch_id"]):
        raise CompletionRepairPreparationError(
            "current completion manifest epoch identity mismatch"
        )
    return current


def _suite_args(payload: Mapping[str, Any], root: Path) -> argparse.Namespace:
    invocation = payload.get("invocation")
    if not isinstance(invocation, Mapping):
        raise CompletionRepairPreparationError(
            "completion run manifest invocation is missing"
        )
    required = {
        "root",
        "completion_objective_change",
        "receipt_dir",
        "model_receipt_dir",
        "formal_root",
        "shadow_root",
        "installed_root",
        "model_jobs",
        "model_timeout",
        "gate_timeout",
        "require_executed_evidence",
        "skillguard",
        "completion_repair_link",
    }
    missing = sorted(name for name in required if name not in invocation)
    if missing:
        raise CompletionRepairPreparationError(
            "completion run manifest invocation is incomplete: "
            + ", ".join(missing)
        )
    manifest_root = Path(str(invocation.get("root", ""))).expanduser().resolve()
    if manifest_root != root:
        raise CompletionRepairPreparationError(
            "completion run manifest root does not match --root"
        )
    if str(invocation.get("completion_repair_link", "") or "").strip():
        raise CompletionRepairPreparationError(
            "current completion manifest invocation must not already contain a repair link"
        )
    output_dir = root / ".flowguard" / "work" / "completion-repair-preparation"
    return argparse.Namespace(
        root=str(root),
        completion_objective_change=str(
            invocation.get("completion_objective_change", "") or ""
        ),
        formal_root=str(invocation.get("formal_root", "") or "") or None,
        shadow_root=str(invocation.get("shadow_root", "") or "") or None,
        installed_root=str(invocation.get("installed_root", "") or "") or None,
        receipt_dir=str(invocation.get("receipt_dir", "") or "") or None,
        model_receipt_dir=str(invocation.get("model_receipt_dir", "") or "") or None,
        output_dir=str(output_dir),
        model_jobs=int(invocation.get("model_jobs", 1) or 1),
        model_timeout=invocation.get("model_timeout"),
        gate_timeout=float(invocation.get("gate_timeout", 900.0) or 900.0),
        require_executed_evidence=bool(
            invocation.get("require_executed_evidence", False)
        ),
        skillguard=str(invocation.get("skillguard", "all") or "all"),
    )


def _load_previous_ledger(
    root: Path,
    previous_epoch_id: str,
) -> tuple[CompletionEpochPlan, CompletionEpochTerminalLedger, Path]:
    loaded = CompletionEpochTerminalLedger.load_for_epoch_id(
        previous_epoch_id,
        root,
    )
    if not loaded.is_valid or loaded.ledger is None:
        raise CompletionRepairPreparationError(
            "canonical previous completion ledger is not valid: "
            + (loaded.error or loaded.status)
        )
    ledger = loaded.ledger
    previous, error = suite_command._reconstruct_previous_completion_plan(ledger)
    if previous is None:
        raise CompletionRepairPreparationError(error)
    bound = CompletionEpochTerminalLedger.load_for_plan(previous, root)
    if not bound.is_valid or bound.ledger is None:
        raise CompletionRepairPreparationError(
            "canonical previous completion ledger failed exact plan binding: "
            + (bound.error or bound.status)
        )
    if bound.ledger.fingerprint != ledger.fingerprint:
        raise CompletionRepairPreparationError(
            "canonical previous completion ledger changed during preparation"
        )
    return previous, ledger, Path(loaded.path)


def _validate_rows(
    evidence: Mapping[str, Any],
    *,
    failed_owner_ids: Sequence[str],
) -> None:
    if not isinstance(evidence, Mapping):
        raise CompletionRepairPreparationError(
            "repair evidence must be an object keyed by failed owner id"
        )
    expected = tuple(sorted(str(item) for item in failed_owner_ids))
    actual = tuple(sorted(str(item).strip() for item in evidence))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if extra:
            detail.append("extra=" + ",".join(extra))
        raise CompletionRepairPreparationError(
            "repair evidence does not cover failed owners exactly"
            + (" (" + "; ".join(detail) + ")" if detail else "")
        )
    for owner_id in expected:
        raw = evidence.get(owner_id)
        if not isinstance(raw, Mapping):
            raise CompletionRepairPreparationError(
                f"repair evidence row must be an object: {owner_id}"
            )
        keys = {str(key) for key in raw}
        if keys != _ROW_FIELDS:
            missing = sorted(_ROW_FIELDS - keys)
            unknown = sorted(keys - _ROW_FIELDS)
            detail = []
            if missing:
                detail.append("missing=" + ",".join(missing))
            if unknown:
                detail.append("unknown=" + ",".join(unknown))
            raise CompletionRepairPreparationError(
                f"repair evidence row fields are not exact: {owner_id}"
                + (" (" + "; ".join(detail) + ")" if detail else "")
            )
        if raw.get("status") != "pass":
            raise CompletionRepairPreparationError(
                f"repair evidence row is not pass: {owner_id}"
            )
        if raw.get("producer_invocations") != 1 or isinstance(
            raw.get("producer_invocations"), bool
        ):
            raise CompletionRepairPreparationError(
                f"repair evidence row must declare one producer invocation: {owner_id}"
            )
        if raw.get("cleanup_confirmed") is not True:
            raise CompletionRepairPreparationError(
                f"repair evidence cleanup is not confirmed: {owner_id}"
            )
        for field_name in (
            "artifact_fingerprint",
            "input_fingerprint",
            "receipt_fingerprint",
        ):
            if not _is_sha256(raw.get(field_name, "")):
                raise CompletionRepairPreparationError(
                    f"repair evidence {field_name} is not canonical: {owner_id}"
                )
        if not isinstance(raw.get("receipt_id"), str) or not str(
            raw["receipt_id"]
        ).strip():
            raise CompletionRepairPreparationError(
                f"repair evidence receipt_id is required: {owner_id}"
            )


def _proof_payload(
    receipt: EvidenceReceipt,
    receipt_root: Path,
    *,
    owner_id: str,
) -> Mapping[str, Any]:
    relative = str(receipt.metadata.get("proof_relpath", "")).strip()
    if not relative:
        raise CompletionRepairPreparationError(
            f"owner receipt has no proof binding: {owner_id}"
        )
    candidate = Path(relative)
    if candidate.is_absolute():
        raise CompletionRepairPreparationError(
            f"owner receipt proof path is absolute: {owner_id}"
        )
    proof_path = _repo_path(
        receipt_root,
        receipt_root / candidate,
        label=f"proof for {owner_id}",
        must_exist=True,
    )
    if proof_path.is_symlink():
        raise CompletionRepairPreparationError(
            f"owner receipt proof must not be a symlink: {proof_path}"
        )
    try:
        proof_bytes = proof_path.read_bytes()
    except OSError as exc:
        raise CompletionRepairPreparationError(
            f"owner receipt proof cannot be read: {proof_path}: {exc}"
        ) from exc
    actual_fingerprint = _sha256_bytes(proof_bytes)
    if actual_fingerprint != receipt.proof_artifact_fingerprint:
        raise CompletionRepairPreparationError(
            f"owner receipt proof fingerprint mismatch: {owner_id}"
        )
    payload = _read_object(proof_path, label=f"owner receipt proof for {owner_id}")
    if str(payload.get("owner_id", "")).strip() != owner_id:
        raise CompletionRepairPreparationError(
            f"owner receipt proof owner mismatch: {owner_id}"
        )
    if str(payload.get("owner_identity", "")).strip() != str(
        receipt.metadata.get("owner_identity", "")
    ).strip():
        raise CompletionRepairPreparationError(
            f"owner receipt proof identity mismatch: {owner_id}"
        )
    return payload


def _supervised_cleanup(
    proof: Mapping[str, Any],
    *,
    owner_id: str,
) -> bool:
    # The publication kind is stored at the outer proof boundary by the owner
    # receipt producer.  Keep this explicit so an aggregate or nonpass proof
    # cannot be presented as one producer invocation.
    if proof.get("publication_kind") != "supervised_producer":
        return False
    child = proof.get("child")
    if not isinstance(child, Mapping) or str(child.get("status", "")) != "pass":
        return False
    payload = child.get("payload")
    if not isinstance(payload, Mapping):
        return False
    supervised = payload.get("supervised_execution")
    if not isinstance(supervised, Mapping):
        return False
    if supervised.get("cleanup_confirmed") is not True:
        return False
    if supervised.get("timed_out") or supervised.get("cancelled") or supervised.get(
        "interrupted"
    ):
        return False
    if supervised.get("exit_code") != 0:
        return False
    return True


def _artifact_fingerprints(
    value: Any,
    *,
    key: str = "",
) -> set[str]:
    """Collect producer-declared artifact identities from proof payload."""

    result: set[str] = set()
    if isinstance(value, Mapping):
        for name, item in value.items():
            name_text = str(name)
            result.update(_artifact_fingerprints(item, key=name_text))
        return result
    if isinstance(value, (list, tuple)):
        for item in value:
            result.update(_artifact_fingerprints(item, key=key))
        return result
    if (
        "artifact_fingerprint" in key
        or key in {"result_fingerprint", "proof_artifact_fingerprint"}
    ) and _is_sha256(value):
        result.add(str(value).strip())
    return result


def _load_receipt(
    root: Path,
    receipt_root: Path,
    *,
    owner_id: str,
    receipt_id: str,
    expected_fingerprint: str,
) -> EvidenceReceipt:
    try:
        target = receipt_path(
            receipt_id,
            root,
            output_directory=receipt_root,
        )
    except (TypeError, ValueError, ReceiptValidationError) as exc:
        raise CompletionRepairPreparationError(
            f"repair evidence receipt id is invalid for {owner_id}: {exc}"
        ) from exc
    if target.is_symlink() or not target.is_file():
        raise CompletionRepairPreparationError(
            f"repair evidence receipt is not a canonical file for {owner_id}: {target}"
        )
    try:
        receipt = load_evidence_receipt(
            receipt_id,
            root,
            output_directory=receipt_root,
        )
    except (OSError, TypeError, ValueError, ReceiptValidationError) as exc:
        raise CompletionRepairPreparationError(
            f"repair evidence receipt cannot be loaded for {owner_id}: {exc}"
        ) from exc
    if receipt.receipt_id != receipt_id or receipt.fingerprint != expected_fingerprint:
        raise CompletionRepairPreparationError(
            f"repair evidence receipt identity/fingerprint mismatch: {owner_id}"
        )
    if receipt.subject_id != f"validation-owner:{owner_id}":
        raise CompletionRepairPreparationError(
            f"repair evidence receipt subject mismatch: {owner_id}"
        )
    return receipt


def _verify_owner_receipt(
    *,
    root: Path,
    receipt_root: Path,
    owner_id: str,
    receipt: EvidenceReceipt,
    contracts: Sequence[Any],
    by_owner: Mapping[str, Any],
    cache: dict[str, tuple[EvidenceReceipt, Any]],
    stack: tuple[str, ...] = (),
) -> tuple[EvidenceReceipt, Any]:
    if owner_id in cache:
        return cache[owner_id]
    if owner_id in stack:
        raise CompletionRepairPreparationError(
            "validation owner receipt dependency cycle: "
            + " -> ".join((*stack, owner_id))
        )
    contract = by_owner.get(owner_id)
    if contract is None:
        raise CompletionRepairPreparationError(
            f"repair evidence owner is not in the current full owner graph: {owner_id}"
        )
    current = build_owner_current(root, contract, all_contracts=contracts)
    assert_validation_owner_receipt_integrity(receipt)
    if (
        receipt.subject_kind != "validation_owner"
        or receipt.producer_id != f"validation-owner:{owner_id}"
        or receipt.claim_scope != OWNER_RECEIPT_SCOPE
        or receipt.result_status != RECEIPT_STATUS_PASS
        or receipt.exit_code != 0
        or receipt.skipped_checks
        or receipt.blockers
        or receipt.metadata.get("publication_kind") != "supervised_producer"
        or receipt.metadata.get("owner_identity") != current.owner_identity
    ):
        raise CompletionRepairPreparationError(
            f"repair evidence receipt is not one supervised current pass: {owner_id}"
        )
    proof = _proof_payload(receipt, receipt_root, owner_id=owner_id)
    if not _supervised_cleanup(proof, owner_id=owner_id):
        raise CompletionRepairPreparationError(
            f"repair evidence proof lacks one confirmed supervised cleanup: {owner_id}"
        )

    dependencies: dict[str, EvidenceReceipt] = {}
    for dependency_id, dependency_receipt_id, dependency_fingerprint in (
        owner_receipt_dependency_bindings(receipt, receipt_root)
    ):
        if dependency_id not in contract.dependency_owner_ids:
            raise CompletionRepairPreparationError(
                f"repair evidence has a foreign dependency binding: {owner_id}"
            )
        dependency = _load_receipt(
            root,
            receipt_root,
            owner_id=dependency_id,
            receipt_id=dependency_receipt_id,
            expected_fingerprint=dependency_fingerprint,
        )
        verified_dependency, _ = _verify_owner_receipt(
            root=root,
            receipt_root=receipt_root,
            owner_id=dependency_id,
            receipt=dependency,
            contracts=contracts,
            by_owner=by_owner,
            cache=cache,
            stack=(*stack, owner_id),
        )
        dependencies[dependency_id] = verified_dependency
    if set(dependencies) != set(contract.dependency_owner_ids):
        raise CompletionRepairPreparationError(
            f"repair evidence dependency set is incomplete: {owner_id}"
        )

    children: list[EvidenceReceipt] = []
    child_results: list[Any] = []
    for requirement in receipt.required_child_receipts:
        child_owner = str(requirement.subject_id).removeprefix("validation-owner:")
        child = _load_receipt(
            root,
            receipt_root,
            owner_id=child_owner,
            receipt_id=requirement.receipt_id,
            expected_fingerprint=requirement.expected_receipt_fingerprint,
        )
        verified_child, child_result = _verify_owner_receipt(
            root=root,
            receipt_root=receipt_root,
            owner_id=child_owner,
            receipt=child,
            contracts=contracts,
            by_owner=by_owner,
            cache=cache,
            stack=(*stack, owner_id),
        )
        children.append(verified_child)
        child_results.append(child_result)

    if children:
        # Current completion owners are supervised leaves.  Keep aggregate
        # support fail-closed: a repair row cannot claim a composition proof
        # as one producer invocation unless a separate aggregate contract is
        # explicitly added in the owner graph.
        raise CompletionRepairPreparationError(
            f"repair evidence owner is an aggregate, not a supervised leaf: {owner_id}"
        )
    selected, verification = find_reusable_owner_receipt(
        current,
        root,
        receipt_root,
        receipt_inventory=(receipt,),
        dependency_receipts=dependencies,
    )
    if selected is None or verification is None or not verification.ok:
        findings = (
            ",".join(verification.finding_codes)
            if verification is not None
            else "missing_verification"
        )
        raise CompletionRepairPreparationError(
            f"repair evidence owner is not independently current: {owner_id}: {findings}"
        )
    cache[owner_id] = (selected, verification)
    return selected, verification


def prepare_completion_repair(
    *,
    root: str | Path,
    previous_epoch_id: str,
    current_manifest_path: str | Path,
    repair_evidence_path: str | Path,
    repair_group_output_path: str | Path,
    repair_link_output_path: str | Path,
) -> dict[str, Any]:
    """Validate evidence and produce one typed repair link."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise CompletionRepairPreparationError(
            f"repository root is not a directory: {root_path}"
        )
    manifest_path = _repo_path(
        root_path,
        current_manifest_path,
        label="current completion manifest",
        must_exist=True,
    )
    evidence_path = _repo_path(
        root_path,
        repair_evidence_path,
        label="repair evidence",
        must_exist=True,
    )
    group_path = _repo_path(
        root_path,
        repair_group_output_path,
        label="repair group output",
    )
    link_path = _repo_path(
        root_path,
        repair_link_output_path,
        label="repair link output",
    )
    try:
        manifest = load_manifest(manifest_path)
    except (CompletionRunManifestError, OSError, ValueError) as exc:
        raise CompletionRepairPreparationError(
            f"current completion manifest is invalid: {exc}"
        ) from exc
    current = _manifest_plan(manifest)
    args = _suite_args(manifest, root_path)
    receipt_dir_value = str(manifest["invocation"].get("receipt_dir", "")).strip()
    if not receipt_dir_value:
        raise CompletionRepairPreparationError(
            "current completion manifest has no outer receipt_dir"
        )
    receipt_root = _repo_path(
        root_path,
        receipt_dir_value,
        label="outer validation receipt_dir",
        must_exist=True,
        directory=True,
    )
    previous, ledger, ledger_path = _load_previous_ledger(
        root_path,
        str(previous_epoch_id),
    )
    if current.completion_cycle_id != previous.completion_cycle_id:
        raise CompletionRepairPreparationError(
            "current and previous completion plans are not in one cycle"
        )
    failed_owner_ids = tuple(
        sorted(
            set(previous.required_terminal_action_ids)
            - set(ledger.completed_terminal_action_ids)
        )
    )
    if not failed_owner_ids:
        raise CompletionRepairPreparationError(
            "canonical aborted ledger has no failed owner to repair"
        )
    evidence = _read_object(evidence_path, label="repair evidence")
    _validate_rows(evidence, failed_owner_ids=failed_owner_ids)

    try:
        specs = suite_command._full_child_specs(args, root_path)
        contracts = suite_command._owner_contracts(specs)
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise CompletionRepairPreparationError(
            f"current full owner graph could not be rebuilt: {type(exc).__name__}: {exc}"
        ) from exc
    by_owner = {contract.owner_id: contract for contract in contracts}
    missing_contracts = sorted(set(failed_owner_ids) - set(by_owner))
    if missing_contracts:
        raise CompletionRepairPreparationError(
            "failed owner ids are not in the current full owner graph: "
            + ", ".join(missing_contracts)
        )
    cache: dict[str, tuple[EvidenceReceipt, Any]] = {}
    canonical_rows: dict[str, Any] = {}
    for owner_id in failed_owner_ids:
        raw = evidence[owner_id]
        receipt = _load_receipt(
            root_path,
            receipt_root,
            owner_id=owner_id,
            receipt_id=str(raw["receipt_id"]).strip(),
            expected_fingerprint=str(raw["receipt_fingerprint"]).strip(),
        )
        selected, _verification = _verify_owner_receipt(
            root=root_path,
            receipt_root=receipt_root,
            owner_id=owner_id,
            receipt=receipt,
            contracts=contracts,
            by_owner=by_owner,
            cache=cache,
        )
        expected_input = fingerprint_value(
            [snapshot.to_dict() for snapshot in selected.input_snapshots]
        )
        if str(raw["input_fingerprint"]).strip() != expected_input:
            raise CompletionRepairPreparationError(
                f"repair evidence input fingerprint mismatch: {owner_id}"
            )
        proof = _proof_payload(selected, receipt_root, owner_id=owner_id)
        allowed_artifacts = {
            selected.proof_artifact_fingerprint,
            selected.result_fingerprint,
            *_artifact_fingerprints(proof),
        }
        if str(raw["artifact_fingerprint"]).strip() not in allowed_artifacts:
            raise CompletionRepairPreparationError(
                f"repair evidence artifact fingerprint is not producer-declared: {owner_id}"
            )
        canonical_rows[owner_id] = dict(raw)

    try:
        link = produce_completion_repair_link(
            previous_plan=previous,
            current_plan=current,
            previous_ledger=ledger,
            repair_evidence=canonical_rows,
            repair_group_output_path=group_path,
            link_output_path=link_path,
            repository_root=root_path,
        )
    except (TypeError, ValueError, OSError, KeyError, OverflowError) as exc:
        raise CompletionRepairPreparationError(
            f"typed completion repair link was rejected: {type(exc).__name__}: {exc}"
        ) from exc
    return {
        "status": "pass",
        "previous_epoch_id": previous.epoch_id,
        "previous_ledger_fingerprint": ledger.fingerprint,
        "previous_ledger_path": str(ledger_path),
        "current_epoch_id": current.epoch_id,
        "completion_cycle_id": current.completion_cycle_id,
        "failed_owner_ids": list(failed_owner_ids),
        "repair_group_id": link.repair_group_id,
        "repair_receipt_fingerprint": link.repair_receipt_fingerprint,
        "repair_link_fingerprint": link.fingerprint,
        "repair_group_path": str(
            CompletionRepairAdmissionGroup.path_for(root_path, link.repair_group_id)
        ),
        "repair_group_compatibility_path": str(group_path),
        "repair_link_path": str(link_path),
        "producer_invocations": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--previous-epoch-id", required=True)
    parser.add_argument("--current-manifest", required=True)
    parser.add_argument("--repair-evidence", required=True)
    parser.add_argument("--repair-group-output", required=True)
    parser.add_argument("--repair-link-output", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = prepare_completion_repair(
            root=args.root,
            previous_epoch_id=args.previous_epoch_id,
            current_manifest_path=args.current_manifest,
            repair_evidence_path=args.repair_evidence,
            repair_group_output_path=args.repair_group_output,
            repair_link_output_path=args.repair_link_output,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print("status: pass")
            print(f"repair_link: {result['repair_link_path']}")
        return 0
    except (CompletionRepairPreparationError, OSError, ValueError) as exc:
        result = {
            "status": "blocked",
            "error": f"{type(exc).__name__}: {exc}",
            "producer_invocations": 0,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print("status: blocked")
            print(f"error: {result['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CompletionRepairPreparationError",
    "main",
    "prepare_completion_repair",
    "prepare_completion_repair_admission",
]
