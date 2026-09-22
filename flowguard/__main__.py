"""Thin command wrappers for flowguard's existing Python APIs."""

from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import mmap
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .adoption import ADOPTION_STATUSES
from .schema import SCHEMA_VERSION


MODEL_REVISION_INTENT_BOOTSTRAP_INPUT_SCHEMA = (
    "flowguard.model_revision_intent_bootstrap_input.v1"
)


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json_loads(value: str) -> object:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=lambda item: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number: {item}")
        ),
    )


class _JsonObjectStoreLocator:
    """Read one member from a content-addressed JSON object store.

    Affected blueprint reads are intentionally closure-first.  The index is
    small and is parsed eagerly, but the shard/object stores can contain the
    whole target blueprint.  This locator memory-maps the store and scans only
    the top-level member envelopes; it materializes JSON for the exact member
    requested by the reader and never builds a Python mapping for unrelated
    members.  The lexical index is built once per invocation. Requested
    members may be read in any order after that pass without rewinding and
    rescanning the store. Only the exact requested value is materialized;
    unrelated values remain represented by byte offsets.
    """

    def __init__(self, path: Path, context: str) -> None:
        self.path = path
        self.context = context
        self._handle = None
        self._mapping = None
        self._started = False
        self._offsets: dict[str, tuple[int, int]] | None = None
        self._cache: dict[str, object] = {}

    def _open(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            if self.path.is_symlink():
                raise ValueError(f"{self.context} must not be a symlink")
            self._handle = self.path.open("rb")
            self._mapping = mmap.mmap(self._handle.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError) as exc:
            # A failed open must not leave a half-open locator behind.  The
            # previous cursor implementation used ``_finished`` here; the
            # bounded offset index no longer has that state, and retaining a
            # stale ``_started`` flag would make a later retry silently use a
            # missing mapping.  Close any partially-created handle and reset
            # only invocation-local state before surfacing the typed error.
            mapping = self._mapping
            handle = self._handle
            self._mapping = None
            self._handle = None
            self._started = False
            self._offsets = None
            self._cache.clear()
            if mapping is not None:
                mapping.close()
            if handle is not None:
                handle.close()
            raise ValueError(f"cannot open {self.context}: {exc}") from exc

    @staticmethod
    def _whitespace(byte: int) -> bool:
        return byte in (9, 10, 13, 32)

    def _skip_whitespace(self, position: int) -> int:
        assert self._mapping is not None
        size = len(self._mapping)
        while position < size and self._whitespace(self._mapping[position]):
            position += 1
        return position

    def _scan_string_end(self, start: int) -> int:
        """Return the exclusive end of a JSON string beginning at *start*."""

        assert self._mapping is not None
        if start >= len(self._mapping) or self._mapping[start] != ord('"'):
            raise ValueError(f"{self.context} contains a non-string object key")
        index = start + 1
        escaped = False
        while index < len(self._mapping):
            byte = self._mapping[index]
            if escaped:
                escaped = False
            elif byte == ord('\\'):
                escaped = True
            elif byte == ord('"'):
                return index + 1
            elif byte < 0x20:
                raise ValueError(f"{self.context} contains a control byte in a key")
            index += 1
        raise ValueError(f"{self.context} contains an unterminated JSON string")

    def _scan_value_end(self, start: int) -> int:
        """Find one complete JSON value without materializing it."""

        assert self._mapping is not None
        start = self._skip_whitespace(start)
        if start >= len(self._mapping):
            raise ValueError(f"{self.context} ends before an object value")
        first = self._mapping[start]
        if first == ord('"'):
            return self._scan_string_end(start)
        if first in (ord('{'), ord('[')):
            stack = [first]
            index = start + 1
            escaped = False
            in_string = False
            while index < len(self._mapping):
                byte = self._mapping[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif byte == ord('\\'):
                        escaped = True
                    elif byte == ord('"'):
                        in_string = False
                    elif byte < 0x20:
                        raise ValueError(
                            f"{self.context} contains a control byte in a value"
                        )
                else:
                    if byte == ord('"'):
                        in_string = True
                    elif byte in (ord('{'), ord('[')):
                        stack.append(byte)
                    elif byte in (ord('}'), ord(']')):
                        expected = ord('}') if stack[-1] == ord('{') else ord(']')
                        if byte != expected:
                            raise ValueError(
                                f"{self.context} contains mismatched JSON delimiters"
                            )
                        stack.pop()
                        if not stack:
                            return index + 1
                index += 1
            raise ValueError(f"{self.context} contains an unterminated JSON value")

        # Primitive values have no nested delimiters.  The target value is
        # validated by _strict_json_loads below; for unrelated values this
        # bounded scan avoids constructing an object that the affected walk
        # does not consume.
        index = start
        while index < len(self._mapping) and self._mapping[index] not in (
            ord(','),
            ord('}'),
        ) and not self._whitespace(self._mapping[index]):
            index += 1
        if index == start:
            raise ValueError(f"{self.context} contains an empty JSON value")
        return index

    def _decode_slice(self, start: int, end: int) -> object:
        assert self._mapping is not None
        try:
            raw = bytes(self._mapping[start:end]).decode("utf-8")
            return _strict_json_loads(raw)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid JSON in {self.context}: {exc}") from exc

    def _build_index(self) -> None:
        """Validate and index all top-level members in one lexical pass."""

        if self._offsets is not None:
            return
        self._open()
        assert self._mapping is not None
        position = self._skip_whitespace(0)
        if position >= len(self._mapping) or self._mapping[position] != ord('{'):
            raise ValueError(f"{self.context} must be a JSON object")
        position += 1
        offsets: dict[str, tuple[int, int]] = {}
        while True:
            position = self._skip_whitespace(position)
            if position >= len(self._mapping):
                raise ValueError(f"{self.context} ends before its closing brace")
            if self._mapping[position] == ord('}'):
                position += 1
                if self._skip_whitespace(position) != len(self._mapping):
                    raise ValueError(f"{self.context} has trailing JSON data")
                self._offsets = offsets
                return
            key_start = position
            key_end = self._scan_string_end(key_start)
            decoded_key = self._decode_slice(key_start, key_end)
            if not isinstance(decoded_key, str):
                raise ValueError(f"{self.context} contains a non-string object key")
            if decoded_key in offsets:
                raise ValueError(
                    f"{self.context} contains duplicate object key: {decoded_key}"
                )
            position = self._skip_whitespace(key_end)
            if position >= len(self._mapping) or self._mapping[position] != ord(':'):
                raise ValueError(f"{self.context} is missing ':' after {decoded_key}")
            value_start = self._skip_whitespace(position + 1)
            value_end = self._scan_value_end(value_start)
            separator_position = self._skip_whitespace(value_end)
            if separator_position >= len(self._mapping):
                raise ValueError(f"{self.context} ends before its next separator")
            separator = self._mapping[separator_position]
            if separator not in (ord(','), ord('}')):
                raise ValueError(f"{self.context} has an invalid object separator")
            offsets[decoded_key] = (value_start, value_end)
            position = separator_position + 1
            if separator == ord('}'):
                if self._skip_whitespace(position) != len(self._mapping):
                    raise ValueError(f"{self.context} has trailing JSON data")
                self._offsets = offsets
                return

    def load(self, object_id: str) -> object:
        key = str(object_id)
        if key in self._cache:
            return self._cache[key]
        self._build_index()
        assert self._offsets is not None
        offsets = self._offsets.get(key)
        if offsets is None:
            raise KeyError(key)
        value = self._decode_slice(*offsets)
        self._cache[key] = value
        return value

    def close(self) -> None:
        mapping = self._mapping
        handle = self._handle
        self._mapping = None
        self._handle = None
        self._started = False
        self._offsets = None
        self._cache.clear()
        if mapping is not None:
            mapping.close()
        if handle is not None:
            handle.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort interpreter cleanup
        try:
            self.close()
        except Exception:
            pass


def _parse_json_mapping_arg(value: str, option_name: str) -> dict[str, object]:
    try:
        payload = _strict_json_loads(value)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"{option_name} must be a JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{option_name} must be a JSON object.")
    return payload


def _run_benchmark() -> int:
    from examples.problem_corpus.executable import review_executable_corpus

    report = review_executable_corpus()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_coverage() -> int:
    from examples.problem_corpus.coverage_audit import review_benchmark_coverage

    report = review_benchmark_coverage()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_hardening() -> int:
    from examples.problem_corpus.hardening import review_benchmark_hardening

    report = review_benchmark_hardening()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_loop_review() -> int:
    from examples.looping_workflow.model import run_loop_review

    report = run_loop_review()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_scenario_review() -> int:
    from flowguard.review import review_scenarios
    from examples.job_matching.scenarios import all_job_matching_scenarios

    report = review_scenarios(all_job_matching_scenarios())
    print(report.format_text(max_counterexamples=1))
    return 0 if report.ok else 1


def _run_conformance() -> int:
    from examples.problem_corpus.conformance_seeds import review_conformance_seeds

    report = review_conformance_seeds()
    print(report.format_text())
    return 0 if report.ok else 1


def _run_self_review() -> int:
    from examples.flowguard_self_review.model import run_self_review

    report = run_self_review()
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


def _run_self_conformance() -> int:
    from examples.flowguard_self_review.conformance import (
        generate_self_review_representative_traces,
        replay_self_review_trace,
    )
    from examples.flowguard_self_review.orchestrator import (
        BrokenNoConformanceOrchestrator,
        BrokenToolchainSubstituteOrchestrator,
        CorrectFlowguardOrchestrator,
    )

    traces = generate_self_review_representative_traces()
    conformance_trace = next(
        trace
        for trace in traces
        if trace.has_label("checks_passed") and "flowguard-conformance" in repr(trace.external_inputs)
    )
    toolchain_trace = next(trace for trace in traces if trace.has_label("toolchain_missing"))
    correct_reports = [replay_self_review_trace(trace, CorrectFlowguardOrchestrator()) for trace in traces]
    broken_reports = [
        replay_self_review_trace(conformance_trace, BrokenNoConformanceOrchestrator()),
        replay_self_review_trace(toolchain_trace, BrokenToolchainSubstituteOrchestrator()),
    ]
    print("=== flowguard self-review conformance ===")
    print(f"representative_traces: {len(traces)}")
    print(f"correct_status: {'OK' if all(report.ok for report in correct_reports) else 'VIOLATION'}")
    for report in broken_reports:
        print()
        print(report.format_text(max_examples=1))
    return 0 if all(report.ok for report in correct_reports) and all(not report.ok for report in broken_reports) else 1


def _run_schema_version() -> int:
    print(SCHEMA_VERSION)
    return 0


def _read_json_object(path: str | Path) -> dict[str, object]:
    try:
        payload = _strict_json_loads(
            Path(path).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON artifact must be an object: {path}")
    return payload


def _resolve_initial_input_path(
    value: object,
    *,
    staging_root: Path,
    field_name: str,
    required: bool = True,
) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"initial input requires {field_name}")
        return None
    path = Path(raw)
    resolved = (staging_root / path).resolve() if not path.is_absolute() else path.resolve()
    if staging_root not in resolved.parents:
        raise ValueError(f"initial input {field_name} must remain inside staging root")
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"initial input {field_name} is missing or symlinked: {resolved}")
    return resolved


def _resolve_initial_input_directory(
    value: object,
    *,
    staging_root: Path,
    field_name: str,
) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    resolved = (staging_root / path).resolve() if not path.is_absolute() else path.resolve()
    if staging_root not in resolved.parents:
        raise ValueError(f"initial input {field_name} must remain inside staging root")
    if resolved.is_symlink():
        raise ValueError(f"initial input {field_name} must not be a symlink")
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"initial input {field_name} is not a directory: {resolved}")
    return resolved


def _run_initial_current_model_authority(args: argparse.Namespace) -> int:
    """Run the bounded first-adoption transaction in a private staging root."""

    from .model_authority import AcceptedBoundaryContract
    from .model_authority_store import (
        bootstrap_initial_current_model_authority,
    )

    payload = _read_json_object(args.initial_input)
    required = {
        "schema",
        "model_parent_receipt",
        "intent_bootstrap_input",
        "revision_set_id",
        "task_id",
        "claim_boundary",
    }
    optional = {
        "snapshot_id",
        "evidence_fingerprint",
        "receipt_root",
        "boundary_contract",
        "native_owner_evidence",
        "path_quality_material",
        "no_declared_intent_rationale_id",
        "no_declared_intent_evidence_fingerprints",
        "no_declared_intent_rationale",
        "decision_reason",
    }
    missing = sorted(required - set(payload))
    unknown = sorted(set(payload) - required - optional)
    if missing or unknown:
        raise ValueError(
            "initial current input fields are not current: "
            f"missing={missing}, unknown={unknown}"
        )
    if payload["schema"] != "flowguard.model_initial_current_input.v1":
        raise ValueError("initial current input schema is not current")
    staging_root = Path(args.staging_root).resolve()
    root = Path(args.root).resolve()
    if staging_root == root:
        raise ValueError("initial current staging root must be isolated from target root")
    if staging_root.is_symlink() or not staging_root.is_dir():
        raise ValueError(
            "initial current staging root must be an existing non-symlink directory"
        )
    snapshot_id = str(payload.get("snapshot_id") or args.snapshot_id)
    evidence_fingerprint = str(
        payload.get("evidence_fingerprint") or args.evidence_fingerprint or ""
    )
    if not evidence_fingerprint:
        raise ValueError("initial current input requires evidence_fingerprint")
    def path_value(name: str, *, required: bool = True) -> Path | None:
        return _resolve_initial_input_path(
            payload.get(name),
            staging_root=staging_root,
            field_name=name,
            required=required,
        )

    parent_path = path_value("model_parent_receipt")
    intent_path = path_value("intent_bootstrap_input")
    boundary_path = path_value("boundary_contract", required=False)
    native_path = path_value("native_owner_evidence", required=False)
    path_quality_path = path_value("path_quality_material", required=False)
    boundary_contract = (
        AcceptedBoundaryContract.from_dict(_read_json_object(boundary_path))
        if boundary_path is not None
        else None
    )
    intent_payload = _read_json_object(intent_path)
    expected_intent_fields = {
        "schema",
        "receipt_id",
        "rationale",
        "claim_boundary",
        "current_design_contributions",
        "legacy_entry_dispositions",
    }
    if set(intent_payload) != expected_intent_fields:
        raise ValueError("intent_bootstrap_input fields are not exact")
    if intent_payload["schema"] != MODEL_REVISION_INTENT_BOOTSTRAP_INPUT_SCHEMA:
        raise ValueError("intent bootstrap input schema is not current")
    from .model_intent import ModelIntentContribution
    from .model_intent_authority import (
        LegacyIntentBootstrapDisposition,
        build_current_intent_bootstrap_receipt,
    )
    current_design = tuple(
        ModelIntentContribution.from_dict(item)
        for item in intent_payload["current_design_contributions"]
    )
    legacy_dispositions = tuple(
        LegacyIntentBootstrapDisposition.from_dict(item)
        for item in intent_payload["legacy_entry_dispositions"]
    )
    native_contracts = native_receipts = native_verifications = ()
    if native_path is not None:
        (
            native_contracts,
            native_receipts,
            native_verifications,
        ) = _load_native_owner_evidence(native_path)
    from .model_path_quality import PathQualityResult, PathQualitySubject
    path_subjects = path_results = ()
    if path_quality_path is not None:
        quality_payload = _read_json_object(path_quality_path)
        if set(quality_payload) != {"subjects", "results"}:
            raise ValueError("path_quality_material fields are not exact")
        path_subjects = tuple(
            PathQualitySubject.from_dict(item) for item in quality_payload["subjects"]
        )
        path_results = tuple(
            PathQualityResult.from_dict(item) for item in quality_payload["results"]
        )
    no_intent_evidence = tuple(
        (str(key), str(value))
        for key, value in dict(
            payload.get("no_declared_intent_evidence_fingerprints") or {}
        ).items()
    )
    report = bootstrap_initial_current_model_authority(
        root,
        staging_root=staging_root,
        expected_absent_manifest_fingerprint=(
            args.expected_absent_manifest_fingerprint
        ),
        snapshot_id=snapshot_id,
        bootstrap_evidence_fingerprint=evidence_fingerprint,
        model_parent_receipt=parent_path,
        receipt_root=_resolve_initial_input_directory(
            payload.get("receipt_root") or args.receipt_root,
            staging_root=staging_root,
            field_name="receipt_root",
        ),
        revision_set_id=str(payload["revision_set_id"]),
        task_id=str(payload["task_id"]),
        current_design_intent_contributions=current_design,
        legacy_entry_dispositions=legacy_dispositions,
        intent_receipt_id=str(intent_payload["receipt_id"]),
        intent_rationale=str(intent_payload["rationale"]),
        intent_claim_boundary=str(intent_payload["claim_boundary"]),
        native_owner_contracts=native_contracts,
        native_owner_receipts=native_receipts,
        native_owner_verification_results=native_verifications,
        accepted_boundary_contract=boundary_contract,
        path_quality_subjects=path_subjects,
        path_quality_results=path_results,
        no_declared_intent_rationale_id=str(
            payload.get("no_declared_intent_rationale_id") or ""
        ),
        no_declared_intent_evidence_fingerprints=no_intent_evidence,
        no_declared_intent_rationale=str(
            payload.get("no_declared_intent_rationale") or ""
        ),
        decision_reason=str(
            payload.get("decision_reason") or payload["claim_boundary"]
        ),
    )
    _emit_payload(report, as_json=args.json)
    return 0


def _strict_json_object(
    value: object,
    *,
    fields: set[str],
    context: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a JSON object")
    actual = {str(key) for key in value}
    missing = sorted(fields - actual)
    unknown = sorted(actual - fields)
    if missing or unknown:
        raise ValueError(
            f"{context} fields are not current: missing={missing}, unknown={unknown}"
        )
    return {str(key): item for key, item in value.items()}


def _strict_json_array(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a JSON array")
    return value


def _load_native_owner_evidence(
    path: str | Path,
) -> tuple[tuple[object, ...], tuple[object, ...], tuple[object, ...]]:
    """Load one exact leaf-owner evidence aggregate without deriving evidence."""

    from .evidence_receipts import (
        EvidenceReceipt,
        ReceiptFinding,
        ReceiptVerificationResult,
    )
    from .validation_ownership import ValidationOwnerContract

    payload = _strict_json_object(
        _read_json_object(path),
        fields={"contracts", "receipts", "verification_results"},
        context="native owner evidence",
    )

    contract_fields = {
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
    component_fields = {"component_id", "fingerprint"}
    contracts = []
    for index, raw_contract in enumerate(
        _strict_json_array(payload["contracts"], context="native owner contracts")
    ):
        contract = _strict_json_object(
            raw_contract,
            fields=contract_fields,
            context=f"native owner contract[{index}]",
        )
        for name in (
            "command",
            "input_patterns",
            "obligation_ids",
            "dependency_owner_ids",
            "resource_keys",
            "resource_argv_options",
            "toolchain_selectors",
            "environment_selectors",
            "work_context_artifact_roles",
        ):
            _strict_json_array(
                contract[name], context=f"native owner contract[{index}].{name}"
            )
        for name in ("projected_inputs", "external_component_bindings"):
            for component_index, raw_component in enumerate(
                _strict_json_array(
                    contract[name],
                    context=f"native owner contract[{index}].{name}",
                )
            ):
                _strict_json_object(
                    raw_component,
                    fields=component_fields,
                    context=(
                        f"native owner contract[{index}].{name}"
                        f"[{component_index}]"
                    ),
                )
        if not isinstance(contract["required"], bool):
            raise ValueError(
                f"native owner contract[{index}].required must be a JSON boolean"
            )
        contracts.append(ValidationOwnerContract.from_dict(contract))

    receipt_fields = {
        "schema_version",
        "receipt_id",
        "subject_id",
        "subject_kind",
        "producer_id",
        "producer_version",
        "claim_scope",
        "command",
        "working_directory_token",
        "started_at",
        "finished_at",
        "exit_code",
        "environment_fingerprint",
        "environment_metadata",
        "contract_hash",
        "check_manifest_hash",
        "suite_map_hash",
        "input_snapshots",
        "proof_artifact_id",
        "proof_artifact_fingerprint",
        "result_status",
        "result_fingerprint",
        "covered_obligations",
        "required_child_receipts",
        "consumed_child_receipts",
        "supersedes_receipt_ids",
        "skipped_checks",
        "blockers",
        "claim_boundary",
        "metadata",
    }
    input_snapshot_fields = {
        "artifact_id",
        "path_token",
        "hash_policy",
        "exists",
        "raw_sha256",
        "semantic_sha256",
        "obligation_ids",
    }
    child_requirement_fields = {
        "receipt_id",
        "subject_id",
        "obligation_ids",
        "eligible_claim_scopes",
        "expected_receipt_fingerprint",
    }
    consumed_child_fields = {"receipt_id", "receipt_fingerprint"}
    receipts = []
    for index, raw_receipt in enumerate(
        _strict_json_array(payload["receipts"], context="native owner receipts")
    ):
        receipt = _strict_json_object(
            raw_receipt,
            fields=receipt_fields,
            context=f"native owner receipt[{index}]",
        )
        for name in (
            "command",
            "input_snapshots",
            "covered_obligations",
            "required_child_receipts",
            "consumed_child_receipts",
            "supersedes_receipt_ids",
            "skipped_checks",
            "blockers",
        ):
            _strict_json_array(
                receipt[name], context=f"native owner receipt[{index}].{name}"
            )
        if not isinstance(receipt["environment_metadata"], Mapping):
            raise ValueError(
                f"native owner receipt[{index}].environment_metadata must be a JSON object"
            )
        if not isinstance(receipt["metadata"], Mapping):
            raise ValueError(
                f"native owner receipt[{index}].metadata must be a JSON object"
            )
        for nested_index, raw_snapshot in enumerate(receipt["input_snapshots"]):
            snapshot = _strict_json_object(
                raw_snapshot,
                fields=input_snapshot_fields,
                context=f"native owner receipt[{index}].input_snapshots[{nested_index}]",
            )
            _strict_json_array(
                snapshot["obligation_ids"],
                context=(
                    f"native owner receipt[{index}].input_snapshots"
                    f"[{nested_index}].obligation_ids"
                ),
            )
        for nested_index, raw_requirement in enumerate(
            receipt["required_child_receipts"]
        ):
            requirement = _strict_json_object(
                raw_requirement,
                fields=child_requirement_fields,
                context=(
                    f"native owner receipt[{index}].required_child_receipts"
                    f"[{nested_index}]"
                ),
            )
            _strict_json_array(
                requirement["obligation_ids"],
                context=(
                    f"native owner receipt[{index}].required_child_receipts"
                    f"[{nested_index}].obligation_ids"
                ),
            )
            _strict_json_array(
                requirement["eligible_claim_scopes"],
                context=(
                    f"native owner receipt[{index}].required_child_receipts"
                    f"[{nested_index}].eligible_claim_scopes"
                ),
            )
        for nested_index, raw_consumed in enumerate(
            receipt["consumed_child_receipts"]
        ):
            _strict_json_object(
                raw_consumed,
                fields=consumed_child_fields,
                context=(
                    f"native owner receipt[{index}].consumed_child_receipts"
                    f"[{nested_index}]"
                ),
            )
        receipts.append(EvidenceReceipt.from_dict(receipt))

    verification_fields = {
        "receipt_id",
        "receipt_fingerprint",
        "current",
        "eligible",
        "status",
        "finding_codes",
        "findings",
        "satisfied_obligations",
        "minimum_revalidation",
    }
    finding_fields = {"code", "message", "artifact_id", "details"}
    verifications = []
    for index, raw_result in enumerate(
        _strict_json_array(
            payload["verification_results"],
            context="native owner verification results",
        )
    ):
        result = _strict_json_object(
            raw_result,
            fields=verification_fields,
            context=f"native owner verification result[{index}]",
        )
        for name in (
            "finding_codes",
            "findings",
            "satisfied_obligations",
            "minimum_revalidation",
        ):
            _strict_json_array(
                result[name],
                context=f"native owner verification result[{index}].{name}",
            )
        if not isinstance(result["current"], bool) or not isinstance(
            result["eligible"], bool
        ):
            raise ValueError(
                f"native owner verification result[{index}] current and eligible must be JSON booleans"
            )
        finding_rows = []
        for finding_index, raw_finding in enumerate(result["findings"]):
            finding = _strict_json_object(
                raw_finding,
                fields=finding_fields,
                context=(
                    f"native owner verification result[{index}].findings"
                    f"[{finding_index}]"
                ),
            )
            if not isinstance(finding["details"], Mapping):
                raise ValueError(
                    f"native owner verification result[{index}].findings"
                    f"[{finding_index}].details must be a JSON object"
                )
            finding_rows.append(
                ReceiptFinding(
                    code=str(finding["code"]),
                    message=str(finding["message"]),
                    artifact_id=str(finding["artifact_id"]),
                    details=finding["details"],
                )
            )
        findings = tuple(finding_rows)
        finding_codes = [finding.code for finding in findings]
        if result["finding_codes"] != finding_codes:
            raise ValueError(
                f"native owner verification result[{index}] finding_codes do not match findings"
            )
        verifications.append(
            ReceiptVerificationResult(
                receipt_id=str(result["receipt_id"]),
                receipt_fingerprint=str(result["receipt_fingerprint"]),
                current=result["current"],
                eligible=result["eligible"],
                status=str(result["status"]),
                findings=findings,
                satisfied_obligations=tuple(
                    str(item) for item in result["satisfied_obligations"]
                ),
                minimum_revalidation=tuple(
                    str(item) for item in result["minimum_revalidation"]
                ),
            )
        )
    return tuple(contracts), tuple(receipts), tuple(verifications)


def _emit_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


@dataclass(frozen=True)
class FileTemplateCommand:
    name: str
    help_text: str
    template_name: str
    factory_name: str


FILE_TEMPLATE_COMMANDS: tuple[FileTemplateCommand, ...] = (
    FileTemplateCommand(
        "project-template",
        "Print or write the basic FlowGuard project model template.",
        "project",
        "project_template_files",
    ),
    FileTemplateCommand(
        "project-adoption-template",
        "Print or write the FlowGuard target-project AGENTS/manifest adoption template.",
        "project_adoption",
        "project_adoption_template_files",
    ),
    FileTemplateCommand(
        "work-context-template",
        "Print or write a provider-neutral read-only WorkContext example.",
        "work_context",
        "work_context_template_files",
    ),
    FileTemplateCommand(
        "risk-intent-template",
        "Print or write the Risk Intent + CheckPlan template.",
        "risk_intent_check_plan",
        "risk_intent_template_files",
    ),
    FileTemplateCommand(
        "risk-template-library-template",
        "Print or write the public/local risk template library scaffold.",
        "risk_template_library",
        "risk_template_library_template_files",
    ),
    FileTemplateCommand(
        "plan-detailing-template",
        "Print or write the rough-plan to detailed FlowGuard plan template.",
        "plan_detailing",
        "plan_detailing_template_files",
    ),
    FileTemplateCommand(
        "primary-path-authority-template",
        "Print or write the Primary Path Authority no-fallback route template.",
        "primary_path_authority",
        "primary_path_authority_template_files",
    ),
    FileTemplateCommand(
        "behavior-commitment-ledger-template",
        "Print or write the Behavior Commitment Ledger full behavior inventory template.",
        "behavior_commitment_ledger",
        "behavior_commitment_ledger_template_files",
    ),
    FileTemplateCommand(
        "model-miss-template",
        "Print or write the bug-repair/model-miss review template.",
        "model_miss_review",
        "model_miss_review_template_files",
    ),
    FileTemplateCommand(
        "model-miss-full-template",
        "Print or write the full bug-repair/model-miss review template.",
        "model_miss_review_full",
        "model_miss_review_full_template_files",
    ),
    FileTemplateCommand(
        "model-test-alignment-template",
        "Print or write the model/test/code contract, code-boundary, and source-audit alignment template.",
        "model_test_alignment",
        "model_test_alignment_template_files",
    ),
    FileTemplateCommand(
        "model-test-alignment-full-template",
        "Print or write the full model/test/code contract, code-boundary, and source-audit alignment template.",
        "model_test_alignment_full",
        "model_test_alignment_full_template_files",
    ),
    FileTemplateCommand(
        "runtime-path-evidence-template",
        "Print or write the runtime path evidence model/code node alignment template.",
        "runtime_path_evidence",
        "runtime_path_evidence_template_files",
    ),
    FileTemplateCommand(
        "code-structure-recommendation-template",
        "Print or write the code structure recommendation template.",
        "code_structure_recommendation",
        "code_structure_recommendation_template_files",
    ),
    FileTemplateCommand(
        "ui-flow-structure-template",
        "Print or write the UI interaction flow and structure derivation template.",
        "ui_flow_structure",
        "ui_flow_structure_template_files",
    ),
    FileTemplateCommand(
        "ui-flow-structure-full-template",
        "Print or write the full UI interaction flow and structure derivation template.",
        "ui_flow_structure_full",
        "ui_flow_structure_full_template_files",
    ),
    FileTemplateCommand(
        "development-process-flow-template",
        "Print or write the DevelopmentProcessFlow lifecycle freshness template.",
        "development_process_flow",
        "development_process_flow_template_files",
    ),
    FileTemplateCommand(
        "workflow-step-contracts-template",
        "Print or write the workflow step contracts receipt-gate template.",
        "workflow_step_contracts",
        "workflow_step_contracts_template_files",
    ),
    FileTemplateCommand(
        "existing-model-preflight-template",
        "Print or write the existing FlowGuard model preflight template.",
        "existing_model_preflight",
        "existing_model_preflight_template_files",
    ),
    FileTemplateCommand(
        "field-lifecycle-template",
        "Print or write the FieldLifecycleMesh field coverage and replacement disposition template.",
        "field_lifecycle",
        "field_lifecycle_template_files",
    ),
    FileTemplateCommand(
        "risk-evidence-ledger-template",
        "Print or write the risk evidence ledger final confidence template.",
        "risk_evidence_ledger",
        "risk_evidence_ledger_template_files",
    ),
    FileTemplateCommand(
        "layered-boundary-proof-template",
        "Print or write the layered parent/child/leaf boundary proof template.",
        "layered_boundary_proof",
        "layered_boundary_proof_template_files",
    ),
    FileTemplateCommand(
        "closure-contract-template",
        "Print or write the FlowGuard closure contract final confidence template.",
        "closure_contract",
        "closure_contract_template_files",
    ),
    FileTemplateCommand(
        "test-mesh-template",
        "Print or write the TestMesh validation hierarchy template.",
        "test_mesh",
        "test_mesh_template_files",
    ),
    FileTemplateCommand(
        "model-mesh-template",
        "Print or write the ModelMesh parent/child topology closure template.",
        "model_mesh",
        "model_mesh_template_files",
    ),
    FileTemplateCommand(
        "contract-exhaustion-template",
        "Print or write the finite ContractExhaustion denominator/oracle template.",
        "contract_exhaustion",
        "contract_exhaustion_template_files",
    ),
    FileTemplateCommand(
        "reverse-surface-closure-template",
        "Print or write the reverse implementation-surface closure authoring template.",
        "reverse_surface_closure",
        "reverse_surface_closure_template_files",
    ),
    FileTemplateCommand(
        "structure-mesh-template",
        "Print or write the StructureMesh refactor hierarchy template.",
        "structure_mesh",
        "structure_mesh_template_files",
    ),
    FileTemplateCommand(
        "maintenance-template",
        "Print or write the optional multi-role maintenance workflow template.",
        "maintenance_workflow",
        "maintenance_workflow_template_files",
    ),
    FileTemplateCommand(
        "topology-hazard-template",
        "Print or write the model-topology hazard review template.",
        "model_topology_hazard_review",
        "topology_hazard_template_files",
    ),
)


def _blueprint_error_payload(code: str, exc: Exception) -> dict[str, object]:
    return {
        "ok": False,
        "status": "invalid",
        "findings": [
            {
                "code": code,
                "message": str(exc),
                "member_ids": [],
                "severity": "blocked",
            }
        ],
    }


def _run_flowguard_self_blueprint_check_command(args: argparse.Namespace) -> int:
    """Build and qualify FlowGuard's current self-blueprint without writing it."""

    from .blueprint_compact_projection import (
        BlueprintCompactProjection,
        compact_reduction_candidate_detail,
    )
    from .self_blueprint import FlowGuardSelfBlueprintError, build_flowguard_self_blueprint
    from .self_architecture_reduction import (
        build_flowguard_self_architecture_reduction_review,
    )

    try:
        require_executed_evidence = bool(
            getattr(args, "require_executed_evidence", False)
        )
        build_kwargs = (
            {"require_executed_evidence": True}
            if require_executed_evidence
            else {}
        )
        model_receipt_dir = str(
            getattr(args, "model_receipt_dir", "") or ""
        ).strip()
        if model_receipt_dir:
            build_kwargs["model_receipt_dir"] = model_receipt_dir
        if getattr(args, "include_architecture_reduction", False):
            bundle, reduction_report = build_flowguard_self_architecture_reduction_review(
                args.root,
                **build_kwargs,
            )
        else:
            bundle = build_flowguard_self_blueprint(args.root, **build_kwargs)
            reduction_report = None
    except (FlowGuardSelfBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("flowguard_self_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    if args.compact:
        payload = BlueprintCompactProjection.self_qualification(bundle)
    else:
        payload = bundle.to_dict()
        payload["self_blueprint_fingerprint"] = bundle.manifest.fingerprint
    if reduction_report is not None:
        payload["composed_self_maintenance_review"] = True
        payload["architecture_reduction_review"] = (
            BlueprintCompactProjection.reduction(reduction_report)
            if args.compact
            else reduction_report.to_dict()
        )
        payload["composed_claim_boundary"] = (
            "Both bounded reviews consume one exact in-memory self-blueprint; "
            "no cache or target-system artifact is written."
        )
        candidate_id = str(getattr(args, "candidate_id", "") or "").strip()
        if candidate_id:
            try:
                payload["architecture_reduction_candidate_detail"] = (
                    compact_reduction_candidate_detail(reduction_report, candidate_id)
                    if args.compact
                    else next(
                        row
                        for row in reduction_report.candidates
                        if row.candidate_id == candidate_id
                    ).to_dict()
                )
            except (StopIteration, ValueError) as exc:
                _emit_payload(
                    _blueprint_error_payload(
                        "flowguard_self_reduction_candidate_invalid", exc
                    ),
                    as_json=args.json,
                )
                return 2
    cleanup_release_ready_required = bool(
        getattr(args, "require_cleanup_release_ready", False)
    )
    cleanup_release_ready = bool(
        reduction_report is not None
        and getattr(reduction_report, "cleanup_release_ready", False)
    )
    if cleanup_release_ready_required:
        payload["cleanup_release_ready_required"] = True
        payload["cleanup_release_ready_gate"] = (
            "pass" if cleanup_release_ready else "blocked"
        )
    _emit_payload(payload, as_json=args.json)
    return (
        0
        if (
            bundle.ok
            and (reduction_report is None or reduction_report.ok)
            and (not cleanup_release_ready_required or cleanup_release_ready)
        )
        else 1
    )


_COMPACT_OPERATIONS = ("read", "change", "release")


def _compact_help() -> int:
    print(
        "usage: python -m flowguard {read,change,release} --root ROOT "
        "[--request REQUEST] [--json]"
    )
    print("operations: read (side-effect free), change (declared scope), release (accepted evidence)")
    print("legacy profiles and command names are rejected; no fallback route is available")
    return 0


def _compact_parse(operation: str, argv: list[str]) -> dict[str, Any]:
    allowed = {"--root", "--request", "--expected-current", "--json"}
    values: dict[str, Any] = {"json": False}
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--json":
            values["json"] = True
            index += 1
            continue
        if item not in allowed:
            raise ValueError(f"unsupported argument: {item}")
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            raise ValueError(f"missing value for {item}")
        values[item[2:].replace("-", "_")] = argv[index + 1]
        index += 2
    if "root" not in values:
        raise ValueError("--root is required")
    if "request" not in values:
        raise ValueError("--request is required")
    root = Path(str(values["root"])).resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    values["root"] = root
    return values


def _compact_endpoint(value: Any) -> dict[str, str]:
    data = value if isinstance(value, Mapping) else {}
    return {
        "kind": str(data.get("endpoint_kind", "")),
        "id": str(data.get("endpoint_id", "")),
        "fingerprint": str(data.get("fingerprint", "")),
    }


def _compact_read_map(closure: Any) -> dict[str, object]:
    models: list[dict[str, object]] = []
    for row in closure.selected_models:
        inputs = row.get("inputs", ()) if isinstance(row, Mapping) else ()
        input_paths = sorted(
            {
                str(item.get("path", "")).replace("\\", "/")
                for item in inputs
                if isinstance(item, Mapping) and str(item.get("path", ""))
            }
        )
        models.append(
            {
                "model_id": str(row.get("logical_model_id", "")),
                "model_path": str(row.get("model_path", "")).replace("\\", "/"),
                "runner_path": str(row.get("runner_path", "")).replace("\\", "/"),
                "input_paths": input_paths,
            }
        )

    intents = [
        {
            "source_ref": str(row.get("source_ref", "")),
            "source_fingerprint": str(row.get("source_fingerprint", "")),
            "logical_model_id": str(row.get("logical_model_id", "")),
        }
        for row in closure.selected_intent_refs
    ]
    relation_rows: list[tuple[dict[str, str], dict[str, str], str, str]] = []
    boundaries: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in closure.relations:
        source = _compact_endpoint(row.get("source", {}))
        target = _compact_endpoint(row.get("target", {}))
        relation_rows.append(
            (
                source,
                target,
                str(row.get("kind", "")),
                str(row.get("relation_id", "")),
            )
        )
        for endpoint in (source, target):
            if endpoint["kind"] != "model_instance":
                key = (endpoint["kind"], endpoint["id"], endpoint["fingerprint"])
                boundaries[key] = endpoint
    duplicate_keys: dict[tuple[str, str, str], int] = {}
    for source, target, kind, _relation_id in relation_rows:
        key = (kind, source["id"], target["id"])
        duplicate_keys[key] = duplicate_keys.get(key, 0) + 1
    relations: list[dict[str, object]] = []
    for source, target, kind, relation_id in relation_rows:
        compact = {
            "source": source,
            "target": target,
            "kind": kind,
            "fingerprint": "",
        }
        # Most edges are unique by endpoint and kind, so omit an otherwise
        # redundant identifier.  When multiple semantic edges share that
        # compact shape, retain the current relation id so the map remains
        # readable and consumers can distinguish them without restoring the
        # full evidence payload.
        key = (kind, source["id"], target["id"])
        if duplicate_keys.get(key, 0) > 1 and relation_id:
            compact["relation_id"] = relation_id
        relations.append(compact)
    return {
        "models": models,
        "intents": intents,
        "relations": relations,
        "boundary_nodes": [boundaries[key] for key in sorted(boundaries)],
    }


def _read_cursor_token(
    head_fingerprint: str,
    scope: tuple[str, ...],
    model_index: int,
    input_offset: int,
    intent_offset: int = 0,
    relation_offset: int = 0,
    boundary_offset: int = 0,
) -> str:
    payload = {
        "head": head_fingerprint,
        "scope": list(scope),
        "model_index": model_index,
        "input_offset": input_offset,
        "intent_offset": intent_offset,
        "relation_offset": relation_offset,
        "boundary_offset": boundary_offset,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _read_cursor_position(
    token: Any,
    *,
    head_fingerprint: str,
    scope: tuple[str, ...],
    model_count: int,
) -> tuple[int, int]:
    if not isinstance(token, str) or not token:
        raise ValueError("read cursor must be a non-empty string")
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = _strict_json_loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError("read cursor is invalid") from exc
    if not isinstance(payload, Mapping) or set(payload) != {
        "head",
        "scope",
        "model_index",
        "input_offset",
        "intent_offset",
        "relation_offset",
        "boundary_offset",
    }:
        raise ValueError("read cursor shape is not exact-current")
    payload_scope = payload["scope"]
    if not isinstance(payload_scope, list) or any(
        not isinstance(item, str) for item in payload_scope
    ):
        raise ValueError("read cursor scope is invalid")
    if payload["head"] != head_fingerprint or tuple(payload_scope) != scope:
        raise ValueError("read cursor is bound to another authority head or scope")
    model_index = payload["model_index"]
    input_offset = payload["input_offset"]
    intent_offset = payload["intent_offset"]
    relation_offset = payload["relation_offset"]
    boundary_offset = payload["boundary_offset"]
    if (
        not isinstance(model_index, int)
        or isinstance(model_index, bool)
        or not isinstance(input_offset, int)
        or isinstance(input_offset, bool)
        or not isinstance(intent_offset, int)
        or isinstance(intent_offset, bool)
        or not isinstance(relation_offset, int)
        or isinstance(relation_offset, bool)
        or not isinstance(boundary_offset, int)
        or isinstance(boundary_offset, bool)
        or model_index < 0
        or model_index >= model_count
        or input_offset < 0
        or intent_offset < 0
        or relation_offset < 0
        or boundary_offset < 0
    ):
        raise ValueError("read cursor position is invalid")
    return model_index, input_offset, intent_offset, relation_offset, boundary_offset


def _bounded_read_page(
    base_payload: Mapping[str, Any],
    compact_map: Mapping[str, Any],
    *,
    head_fingerprint: str,
    scope: tuple[str, ...],
    cursor: Any,
) -> dict[str, Any]:
    """Return one deterministic read page whose emitted JSON is <= 8192 bytes."""

    models = tuple(item for item in compact_map.get("models", ()) if isinstance(item, Mapping))
    intents = tuple(item for item in compact_map.get("intents", ()) if isinstance(item, Mapping))
    relations = tuple(item for item in compact_map.get("relations", ()) if isinstance(item, Mapping))
    boundary_nodes = tuple(item for item in compact_map.get("boundary_nodes", ()) if isinstance(item, Mapping))
    start_model, start_offset = (0, 0)
    start_intent, start_relation, start_boundary = (0, 0, 0)
    if cursor is not None:
        (
            start_model,
            start_offset,
            start_intent,
            start_relation,
            start_boundary,
        ) = _read_cursor_position(
            cursor,
            head_fingerprint=head_fingerprint,
            scope=scope,
            model_count=max(1, len(models)),
        )

    page_rows: list[dict[str, Any]] = []
    page_intents: list[dict[str, Any]] = []
    page_relations: list[dict[str, Any]] = []
    page_boundaries: list[dict[str, Any]] = []
    current_model = start_model
    current_offset = start_offset
    current_intent = start_intent
    current_relation = start_relation
    current_boundary = start_boundary

    def candidate(next_pos: tuple[int, int, int, int, int] | None, record_count: int) -> dict[str, Any]:
        next_cursor = (
            None
            if next_pos is None
            else _read_cursor_token(head_fingerprint, scope, *next_pos)
        )
        return {
            **dict(base_payload),
            "map": {
                "models": page_rows,
                "intents": page_intents,
                "relations": page_relations,
                "boundary_nodes": page_boundaries,
            },
            "page": {
                "model_index": start_model,
                "input_offset": start_offset,
                "intent_offset": start_intent,
                "relation_offset": start_relation,
                "boundary_offset": start_boundary,
                "record_count": record_count,
            },
            "next_cursor": next_cursor,
        }

    def encoded_size(next_pos: tuple[int, int, int, int, int] | None, count: int) -> int:
        return len(json.dumps(candidate(next_pos, count), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1

    record_count = 0
    # Context rows are paged before model rows.  This keeps a large relation or
    # intent map bounded without repeating it on every model page.
    for values, target, offset_name in (
        (intents, page_intents, "intent"),
        (relations, page_relations, "relation"),
        (boundary_nodes, page_boundaries, "boundary"),
    ):
        offset = {"intent": current_intent, "relation": current_relation, "boundary": current_boundary}[offset_name]
        while offset < len(values):
            target.append(dict(values[offset]))
            next_offsets = {
                "intent": current_intent,
                "relation": current_relation,
                "boundary": current_boundary,
            }
            next_offsets[offset_name] = offset + 1
            following = (current_model, current_offset, next_offsets["intent"], next_offsets["relation"], next_offsets["boundary"])
            if encoded_size(following, record_count + 1) > 8192:
                target.pop()
                if not target:
                    raise ValueError("one read context record cannot fit within 8192 UTF-8 bytes")
                next_position = (current_model, current_offset, current_intent, current_relation, current_boundary)
                result = candidate(next_position, record_count)
                if len(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1 > 8192:
                    raise ValueError("read page metadata exceeds 8192 UTF-8 bytes")
                return result
            record_count += 1
            offset += 1
            if offset_name == "intent":
                current_intent = offset
            elif offset_name == "relation":
                current_relation = offset
            else:
                current_boundary = offset

    while current_model < len(models):
        original = dict(models[current_model])
        input_paths = list(original.get("input_paths", ()))
        if input_paths:
            if current_offset >= len(input_paths):
                current_model += 1
                current_offset = 0
                continue
            remaining = input_paths[current_offset:]
            accepted_chunk: list[str] = []
            for item in remaining:
                trial_chunk = accepted_chunk + [item]
                page_rows.append({**original, "input_paths": trial_chunk})
                following = (
                    (current_model, current_offset + len(trial_chunk), current_intent, current_relation, current_boundary)
                    if current_offset + len(trial_chunk) < len(input_paths)
                    else (
                        (current_model + 1, 0, current_intent, current_relation, current_boundary)
                        if current_model + 1 < len(models)
                        else None
                    )
                )
                too_large = encoded_size(following, record_count + 1) > 8192
                page_rows.pop()
                if too_large:
                    break
                accepted_chunk.append(item)
            if not accepted_chunk:
                raise ValueError("one read model record cannot fit within 8192 UTF-8 bytes")
            page_rows.append({**original, "input_paths": accepted_chunk})
            record_count += 1
            consumed = len(accepted_chunk)
            if current_offset + consumed < len(input_paths):
                next_position = (current_model, current_offset + consumed, current_intent, current_relation, current_boundary)
                break
            current_model += 1
            current_offset = 0
            next_position = (current_model, 0, current_intent, current_relation, current_boundary) if current_model < len(models) else None
            continue
        page_rows.append({**original, "input_paths": []})
        following = (
            (current_model + 1, 0, current_intent, current_relation, current_boundary) if current_model + 1 < len(models) else None
        )
        if encoded_size(following, record_count + 1) > 8192:
            page_rows.pop()
            if not page_rows:
                raise ValueError("one read model record cannot fit within 8192 UTF-8 bytes")
            next_position = (current_model, 0, current_intent, current_relation, current_boundary)
            break
        record_count += 1
        current_model += 1
        next_position = (current_model, 0, current_intent, current_relation, current_boundary) if current_model < len(models) else None

    result = candidate(next_position if 'next_position' in locals() else None, record_count)
    if len(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1 > 8192:
        raise ValueError("read page metadata exceeds 8192 UTF-8 bytes")
    return result


def _read_operation(root: Path, request: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    from .model_authority import ModelAuthorityError
    from .model_authority_store import (
        _load_bound_read_projection,
        load_observed_model_head,
        read_selected_model_projection,
    )

    expected_fields = {"operation", "target_id", "scope"}
    request_fields = set(request)
    if request_fields != expected_fields and request_fields != expected_fields | {"cursor"}:
        raise ValueError(
            "read request fields are not exact-current: "
            f"missing={sorted(expected_fields - set(request))}, "
            f"unexpected={sorted(set(request) - expected_fields)}"
        )
    if request["operation"] != "read":
        raise ValueError("read request operation must be 'read'")
    if "expected_current" in values:
        raise ValueError("read does not accept --expected-current")
    target_id = request["target_id"]
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("read request target_id must be a non-empty string")
    scope = request["scope"]
    if not isinstance(scope, list) or not scope:
        raise ValueError("read request scope must be a non-empty model ID array")
    if any(not isinstance(item, str) or not item.strip() for item in scope):
        raise ValueError("read request scope entries must be non-empty strings")
    if len(scope) != len(set(scope)):
        raise ValueError("read request scope contains duplicate model IDs")
    cursor = request.get("cursor")

    try:
        head = load_observed_model_head(root)
    except ModelAuthorityError as exc:
        if str(exc) == "project manifest has no model_authority section":
            return {
                "operation": "read",
                "status": "blocked",
                "reason": "current_model_missing",
                "current_authority": "missing",
                "target_id": target_id,
                "requested_model_ids": list(scope),
                "selected_model_ids": [],
                "as_of": {"authority_status": "missing", "reason": "no_observed_model_authority"},
                "authority_integrity": "missing",
                "selected_source_currentness": "not_selected",
                "execution_evidence_status": "not_run",
                "required_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "producer_count": 0,
                "write_count": 0,
                "map": {},
                "stale_obligations": [],
                "blockers": ["current_model_missing"],
                "claim_boundary": "No observed model authority exists; read did not create or repair one.",
            }
        raise
    if target_id != head.system_id:
        raise ValueError("read request target_id does not match current authority")

    try:
        projection = _load_bound_read_projection(root, head)
    except (ModelAuthorityError, OSError, ValueError) as exc:
        return {
            "operation": "read",
            "status": "blocked",
            "reason": "read_projection_unavailable",
            "target_id": target_id,
            "requested_model_ids": list(scope),
            "selected_model_ids": [],
            "as_of": {"authority_head_fingerprint": head.fingerprint},
            "authority_integrity": "blocked",
            "selected_source_currentness": "unavailable",
            "execution_evidence_status": "not_run",
            "required_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "producer_count": 0,
            "write_count": 0,
            "map": {},
            "stale_obligations": [],
            "blockers": ["read_projection_unavailable"],
            "error": str(exc),
            "claim_boundary": "The current head is not bound to a valid selected-read projection; no fallback or repair was attempted.",
        }
    index = projection["index"]
    indexed_models = index.get("models") if isinstance(index, Mapping) else None
    known_model_ids = set(indexed_models) if isinstance(indexed_models, Mapping) else set()
    unknown_model_ids = sorted(set(scope) - known_model_ids)
    if unknown_model_ids:
        raise ValueError(f"read request scope contains unknown model IDs: {unknown_model_ids}")
    closure = read_selected_model_projection(
        root,
        head=head,
        projection=projection,
        selected_model_ids=tuple(scope),
    )
    if not closure.ok:
        return {
            "operation": "read",
            "status": "blocked",
            "reason": "read_projection_invalid",
            "target_id": target_id,
            "requested_model_ids": list(scope),
            "selected_model_ids": list(closure.selected_model_ids),
            "as_of": dict(closure.as_of),
            "authority_integrity": closure.authority_integrity,
            "selected_source_currentness": closure.selected_source_currentness,
            "execution_evidence_status": "not_run",
            "required_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "producer_count": 0,
            "write_count": 0,
            "map": {},
            "stale_obligations": list(closure.stale_obligations),
            "blockers": ["read_projection_invalid"],
            "findings": list(closure.findings),
            "claim_boundary": "The selected projection or source currentness is invalid; read did not execute or repair anything.",
        }
    base_payload: dict[str, Any] = {
        "operation": "read",
        "status": "pass",
        "target_id": target_id,
        "requested_model_ids": list(scope),
        "selected_model_ids": list(closure.selected_model_ids),
        "as_of": dict(closure.as_of),
        "authority_integrity": closure.authority_integrity,
        "selected_source_currentness": closure.selected_source_currentness,
        "execution_evidence_status": "not_run",
        "required_count": 0,
        "run_count": 0,
        "reused_count": 0,
        "producer_count": 0,
        "write_count": 0,
        "stale_obligations": list(closure.stale_obligations),
        "blockers": [],
        "claim_boundary": "This is an as-of read of the selected accepted projection. It does not execute, accept, install, or publish.",
    }
    try:
        return _bounded_read_page(
            base_payload,
            _compact_read_map(closure),
            head_fingerprint=head.fingerprint,
            scope=tuple(scope),
            cursor=cursor,
        )
    except ValueError as exc:
        return {
            **base_payload,
            "status": "blocked",
            "reason": "read_page_invalid",
            "map": {},
            "blockers": ["read_page_invalid"],
            "error": str(exc),
        }


def _root_file_reference(
    root: Path,
    value: Any,
    *,
    context: str,
) -> tuple[Path, bytes]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{context} must contain exactly path and sha256")
    relative = value["path"]
    digest = value["sha256"]
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"{context}.path must be a non-empty string")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{context}.sha256 must be 64 lowercase hex characters")
    candidate = Path(relative)
    path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{context}.path must remain under --root") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{context}.path must be an existing ordinary file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"{context}.sha256 does not match file bytes")
    return path, raw


def _native_path_quality_material(
    parent: Any,
    candidate: Any,
    *,
    required_model_ids: tuple[str, ...],
    currentness_id: str,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Project executed native case evidence into exact path-quality material."""

    from .model_path_quality import (
        PathQualitySubject,
        canonical_fingerprint,
        derive_retained_elements,
        lightweight_path_review,
        normalized_model_facts_fingerprint,
    )

    instances = {item.logical_model_id: item for item in candidate.model_instances}
    results = {item.model_id: item for item in parent.results}
    subjects: list[Any] = []
    reviews: list[Any] = []
    for model_id in required_model_ids:
        instance = instances.get(model_id)
        run = results.get(model_id)
        if instance is None or run is None or not run.ok or not run.native_case_results:
            raise ValueError(
                f"path-quality owner did not produce native case evidence: {model_id}"
            )
        cases = tuple(run.native_case_results)
        native_result_path = Path(str(run.native_case_result_artifact_path)).resolve()
        if native_result_path.is_symlink() or not native_result_path.is_file():
            raise ValueError(
                f"path-quality native result artifact is missing: {model_id}"
            )
        native_result_bytes = native_result_path.read_bytes()
        native_result_fingerprint = "sha256:" + hashlib.sha256(native_result_bytes).hexdigest()
        if native_result_fingerprint != run.native_case_result_artifact_fingerprint:
            raise ValueError(
                f"path-quality native result artifact fingerprint is stale: {model_id}"
            )
        source_path = (
            native_result_path
            if native_result_path.name == "native-source.json"
            else native_result_path.with_name("native-source.json")
        )
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError(
                f"path-quality native source artifact is missing: {model_id}"
            )
        source_bytes = source_path.read_bytes()
        source_fingerprint = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
        try:
            source_payload = _strict_json_loads(source_bytes.decode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"path-quality native source artifact is unreadable: {model_id}"
            ) from exc
        if not isinstance(source_payload, Mapping):
            raise ValueError(f"path-quality native source artifact is not an object: {model_id}")
        report_payload = source_payload.get("report")
        report_rows = report_payload.get("results") if isinstance(report_payload, Mapping) else None
        if not isinstance(report_rows, list) or not report_rows:
            raise ValueError(
                f"path-quality native source has no executed report graph: {model_id}"
            )
        raw_rows: dict[str, Mapping[str, Any]] = {}
        for raw_row in report_rows:
            if not isinstance(raw_row, Mapping):
                raise ValueError(f"path-quality native report row is not an object: {model_id}")
            scenario_name = raw_row.get("scenario_name")
            if not isinstance(scenario_name, str) or not scenario_name.strip():
                raise ValueError(f"path-quality native report row has no scenario name: {model_id}")
            if scenario_name in raw_rows:
                raise ValueError(
                    f"path-quality native report has duplicate scenario: {scenario_name}"
                )
            raw_rows[scenario_name] = raw_row

        states: dict[str, dict[str, Any]] = {}
        transitions: dict[str, dict[str, Any]] = {}
        fields: dict[str, dict[str, Any]] = {}
        function_blocks: dict[str, dict[str, Any]] = {}
        outputs: dict[str, dict[str, Any]] = {}
        validations: dict[str, dict[str, Any]] = {}
        initial_state_ids: set[str] = set()
        terminal_state_ids: set[str] = set()

        def state_id(case_id: str, value: Any) -> str:
            return f"state:{case_id}:{canonical_fingerprint(value).split(':', 1)[1]}"

        def add_state(case_id: str, value: Any, *, initial: bool = False, terminal: bool = False) -> str:
            if value is None:
                raise ValueError(f"path-quality native trace has no state: {case_id}")
            identifier = state_id(case_id, value)
            row = states.setdefault(
                identifier,
                {"id": identifier, "initial": False, "terminal": False, "behaviorally_relevant": True},
            )
            row["initial"] = bool(row["initial"] or initial)
            row["terminal"] = bool(row["terminal"] or terminal)
            if initial:
                initial_state_ids.add(identifier)
            if terminal:
                terminal_state_ids.add(identifier)
            raw_fields = value.get("fields") if isinstance(value, Mapping) else None
            if isinstance(raw_fields, Mapping):
                for name in raw_fields:
                    field_id = f"field:{case_id}:{name}"
                    fields[field_id] = {"id": field_id}
            return identifier

        expected_scenario_names: set[str] = set()
        for row in cases:
            if row.child_case_ids:
                continue
            native_prefix = f"native-scenario:{model_id}:"
            case_prefix = f"case:{model_id}:"
            if row.source_case_id.startswith(native_prefix):
                scenario_name = row.source_case_id.removeprefix(native_prefix)
            elif row.source_case_id.startswith(case_prefix):
                scenario_name = row.source_case_id.removeprefix(case_prefix)
            else:
                raise ValueError(
                    f"path-quality native row identity is not current: {row.source_case_id}"
                )
            if scenario_name in expected_scenario_names:
                raise ValueError(
                    f"path-quality native report denominator has duplicate leaf: {row.source_case_id}"
                )
            expected_scenario_names.add(scenario_name)
        if set(raw_rows) != expected_scenario_names:
            raise ValueError(
                f"path-quality native report denominator mismatch: {model_id}"
            )
        for row in cases:
            if row.child_case_ids:
                continue
            native_prefix = f"native-scenario:{model_id}:"
            case_prefix = f"case:{model_id}:"
            if row.source_case_id.startswith(native_prefix):
                scenario_name = row.source_case_id.removeprefix(native_prefix)
            elif row.source_case_id.startswith(case_prefix):
                scenario_name = row.source_case_id.removeprefix(case_prefix)
            else:
                raise ValueError(
                    f"path-quality native row identity is not current: {row.source_case_id}"
                )
            raw_row = raw_rows.get(scenario_name)
            if raw_row is None:
                raise ValueError(
                    f"path-quality native report row missing: {row.source_case_id}"
                )
            if row.result_artifact_fingerprint != source_fingerprint:
                raise ValueError(
                    f"path-quality native source fingerprint is not bound by row: {row.source_case_id}"
                )
            scenario_run = raw_row.get("scenario_run")
            traces = scenario_run.get("traces") if isinstance(scenario_run, Mapping) else None
            final_states = scenario_run.get("final_states") if isinstance(scenario_run, Mapping) else None
            if not isinstance(traces, list) or not traces or not isinstance(final_states, list) or not final_states:
                raise ValueError(
                    f"path-quality native row has no real executed graph: {row.source_case_id}"
                )
            for trace_index, trace in enumerate(traces):
                if not isinstance(trace, Mapping):
                    raise ValueError(f"path-quality native trace is not an object: {row.source_case_id}")
                previous = add_state(
                    row.source_case_id,
                    trace.get("initial_state"),
                    initial=True,
                )
                steps = trace.get("steps")
                if not isinstance(steps, list):
                    raise ValueError(f"path-quality native trace steps are not an array: {row.source_case_id}")
                for step_index, step in enumerate(steps):
                    if not isinstance(step, Mapping):
                        raise ValueError(f"path-quality native trace step is not an object: {row.source_case_id}")
                    old = step.get("old_state", trace.get("initial_state") if step_index == 0 else None)
                    new = step.get("new_state")
                    if new is None:
                        raise ValueError(f"path-quality native trace step has no new state: {row.source_case_id}")
                    source_state = add_state(row.source_case_id, old)
                    target_state = add_state(row.source_case_id, new)
                    output_value = step.get("function_output")
                    output_ids: tuple[str, ...] = ()
                    if output_value is not None:
                        output_id = f"output:{row.source_case_id}:{step_index}:{canonical_fingerprint(output_value).split(':', 1)[1]}"
                        # A native trace's function output is an observed
                        # terminal value unless the report explicitly models
                        # a downstream consumer.  Marking it terminal keeps
                        # the graph honest: the value is retained as a leaf
                        # observation and is not falsely reported as an
                        # unconsumed intermediate output.
                        outputs[output_id] = {"id": output_id, "terminal": True}
                        output_ids = (output_id,)
                    function_name = str(step.get("function_name") or "native-step")
                    block_id = f"function:{row.source_case_id}:{trace_index}:{step_index}:{function_name}"
                    function_blocks[block_id] = {
                        "id": block_id,
                        "outputs": output_ids,
                    }
                    transition_id = f"transition:{row.source_case_id}:{trace_index}:{step_index}"
                    transitions[transition_id] = {
                        "id": transition_id,
                        "source": source_state,
                        "target": target_state,
                        "trigger": str(step.get("label") or function_name),
                        "guard": "native-observed",
                        "outputs": output_ids,
                    }
                    previous = target_state
                final_state = trace.get("final_state")
                if final_state is not None:
                    final_id = add_state(row.source_case_id, final_state, terminal=True)
                    if final_id != previous:
                        transition_id = f"transition:{row.source_case_id}:{trace_index}:final"
                        transitions[transition_id] = {
                            "id": transition_id,
                            "source": previous,
                            "target": final_id,
                            "trigger": "native-final-state",
                            "guard": "native-observed",
                        }
            for final_state in final_states:
                add_state(row.source_case_id, final_state, terminal=True)
            for validation_index, oracle in enumerate(row.oracle_results):
                validation_id = f"validation:{row.source_case_id}:{validation_index}"
                validations[validation_id] = {
                    "id": validation_id,
                    "obligation_id": f"obligation:{row.source_case_id}:{validation_index}",
                    "oracle_id": str(oracle["oracle_member_id"]),
                    "subject_fingerprint": source_fingerprint,
                    "evidence_boundary_id": f"boundary:{model_id}",
                }
        facts = {
            "states": tuple(states.values()),
            "transitions": tuple(transitions.values()),
            "fields": tuple(fields.values()),
            "function_blocks": tuple(function_blocks.values()),
            "outputs": tuple(outputs.values()),
            "validations": tuple(validations.values()),
            "owners": (
                {
                    "id": f"owner:{model_id}",
                    "intent_id": f"intent:{model_id}",
                    "boundary_id": f"boundary:{model_id}",
                    "current": True,
                },
            ),
            "initial_state_ids": tuple(sorted(initial_state_ids)),
            "terminal_state_ids": tuple(sorted(terminal_state_ids)),
        }
        retained = tuple(derive_retained_elements(facts))
        obligations = tuple(
            sorted(f"obligation:{element_id}" for element_id, _kind in retained)
        )
        evidence_fingerprint = run.native_case_result_artifact_fingerprint
        subject = PathQualitySubject(
            model_id=model_id,
            boundary_id=f"boundary:{model_id}",
            model_fingerprint=instance.fingerprint,
            normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts),
            retained_element_inventory_fingerprint=canonical_fingerprint(dict(retained)),
            purpose_fingerprint=instance.purpose_closure_fingerprint,
            intent_fingerprint=canonical_fingerprint(
                {"model_id": model_id, "candidate": candidate.fingerprint}
            ),
            obligation_fingerprint=canonical_fingerprint(list(obligations)),
            provider_fingerprint=canonical_fingerprint(
                {"owner_id": f"model:{model_id}", "runner": instance.runner_sha256}
            ),
            dependency_fingerprint=instance.input_inventory_fingerprint,
            code_fingerprint=canonical_fingerprint(
                {row.path: row.sha256 for row in instance.inputs}
            ),
            test_fingerprint=instance.runner_sha256,
            oracle_fingerprint=canonical_fingerprint(
                [row.oracle_fingerprint for row in cases]
            ),
            evidence_fingerprint=evidence_fingerprint,
            currentness_id=currentness_id,
        )
        review = lightweight_path_review(
            subject,
            facts,
        )
        if not review.current or review.unresolved_ids:
            raise ValueError(f"path-quality review is not current and closed: {model_id}")
        subjects.append(subject)
        reviews.append(review)
    return tuple(subjects), tuple(reviews)


def _release_leaf_blockers(
    revision: Any,
    required_model_ids: tuple[str, ...],
    *,
    root: Path | None = None,
    receipt_root: Path | None = None,
    leaf_receipts: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[str, ...]:
    """Require one accepted leaf reference for every released model.

    The accepted revision keeps native owner leaves in
    ``completed_evidence_refs``. A release must consume that exact completed
    projection; required (pending) refs or the parent aggregate are not a
    substitute. This gate performs no producer execution and never turns a
    missing or invalid leaf into a pass. When ``root`` and ``receipt_root``
    are supplied, the accepted ref is also opened from the canonical immutable
    store and its model child proof and native result artifact are checked.
    The small duck-typed form remains available to projection-only callers.
    """

    completed = tuple(getattr(revision, "completed_evidence_refs", ()) or ())
    blockers: list[str] = []
    if not completed:
        return tuple(
            f"release.native_leaf_missing:model:{model_id}"
            for model_id in required_model_ids
        )
    seen_receipt_ids: set[str] = set()
    seen_receipt_fingerprints: set[str] = set()
    for item in completed:
        receipt_id = str(getattr(item, "receipt_id", ""))
        receipt_fingerprint = str(getattr(item, "receipt_fingerprint", ""))
        if receipt_id in seen_receipt_ids:
            blockers.append(f"release.native_leaf_duplicate_receipt:{receipt_id}")
        if receipt_fingerprint in seen_receipt_fingerprints:
            blockers.append(
                f"release.native_leaf_duplicate_fingerprint:{receipt_fingerprint}"
            )
        seen_receipt_ids.add(receipt_id)
        seen_receipt_fingerprints.add(receipt_fingerprint)

    for model_id in required_model_ids:
        model_blockers: list[str] = []
        if leaf_receipts is not None and model_id in leaf_receipts:
            receipt_ref, receipt_fingerprint = leaf_receipts[model_id]
            if root is not None and receipt_root is not None:
                model_blockers.extend(
                    _release_direct_leaf_artifact_blockers(
                        root,
                        receipt_root,
                        receipt_ref,
                        receipt_fingerprint,
                        model_id=model_id,
                    )
                )
            else:
                model_blockers.append(
                    f"release.native_leaf_override_without_store:model:{model_id}"
                )
            blockers.extend(model_blockers)
            continue
        affected_id = f"model_instance:model:{model_id}"
        matches = tuple(
            item
            for item in completed
            if affected_id in tuple(getattr(item, "covered_affected_ids", ()) or ())
        )
        if not matches:
            blockers.append(f"release.native_leaf_missing:{affected_id}")
            continue
        if len(matches) != 1:
            blockers.append(f"release.native_leaf_ambiguous:{affected_id}")
            continue
        item = matches[0]
        if (
            str(getattr(item, "status", "")) != "pass"
            or getattr(item, "current", False) is not True
            or getattr(item, "eligible", False) is not True
        ):
            model_blockers.append(f"release.native_leaf_not_current:{affected_id}")
        if not str(getattr(item, "receipt_id", "")).strip():
            model_blockers.append(f"release.native_leaf_receipt_id_missing:{affected_id}")
        if not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(getattr(item, "receipt_fingerprint", "")),
        ):
            model_blockers.append(
                f"release.native_leaf_receipt_fingerprint_invalid:{affected_id}"
            )
        if root is not None and receipt_root is not None and not model_blockers:
            model_blockers.extend(
                _release_leaf_artifact_blockers(
                    root,
                    receipt_root,
                    item,
                    model_id=model_id,
                )
            )
        blockers.extend(model_blockers)
    return tuple(dict.fromkeys(blockers))


def _release_leaf_artifact_blockers(
    root: Path,
    receipt_root: Path,
    ref: Any,
    *,
    model_id: str,
) -> tuple[str, ...]:
    """Re-read one accepted leaf's canonical receipt and native artifact.

    Revision evidence is a compact identity projection. Release qualification
    must still read immutable receipt bytes and the direct model child proof;
    an accepted ref alone cannot make a deleted, foreign, or tampered native
    artifact current. This helper performs no producer execution.
    """

    from .evidence_receipts import load_evidence_receipt

    blockers: list[str] = []
    receipt_id = str(getattr(ref, "receipt_id", ""))
    expected_fingerprint = str(getattr(ref, "receipt_fingerprint", ""))
    try:
        aggregate = load_evidence_receipt(
            receipt_id,
            root,
            output_directory=receipt_root,
        )
    except (OSError, TypeError, ValueError) as exc:
        return (
            f"release.native_leaf_receipt_unreadable:{model_id}:{type(exc).__name__}",
        )
    if aggregate.fingerprint != expected_fingerprint:
        blockers.append(f"release.native_leaf_receipt_hash_mismatch:model:{model_id}")
    if (
        aggregate.result_status != "pass"
        or aggregate.exit_code != 0
        or aggregate.skipped_checks
        or aggregate.blockers
    ):
        blockers.append(f"release.native_leaf_receipt_not_terminal:model:{model_id}")
    if aggregate.subject_kind != "validation_owner" or aggregate.producer_id != aggregate.subject_id:
        blockers.append(f"release.native_leaf_receipt_foreign_owner:model:{model_id}")

    expected_subject = f"validation-owner:model:{model_id}"
    children = tuple(
        item
        for item in aggregate.required_child_receipts
        if item.subject_id == expected_subject
    )
    if len(children) != 1:
        blockers.append(f"release.native_leaf_child_missing_or_ambiguous:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    child_requirement = children[0]
    try:
        child = load_evidence_receipt(
            child_requirement.receipt_id,
            root,
            output_directory=receipt_root,
        )
    except (OSError, TypeError, ValueError) as exc:
        blockers.append(
            f"release.native_leaf_child_unreadable:{model_id}:{type(exc).__name__}"
        )
        return tuple(dict.fromkeys(blockers))
    if child.fingerprint != child_requirement.expected_receipt_fingerprint:
        blockers.append(f"release.native_leaf_child_hash_mismatch:model:{model_id}")
    if (
        child.subject_id != expected_subject
        or child.subject_kind != "validation_owner"
        or child.producer_id != expected_subject
        or child.result_status != "pass"
        or child.exit_code != 0
        or child.required_child_receipts
        or child.consumed_child_receipts
        or child.skipped_checks
        or child.blockers
        or str(child.metadata.get("publication_kind", "")) != "supervised_producer"
    ):
        blockers.append(f"release.native_leaf_child_not_direct_pass:model:{model_id}")

    proof_relpath = str(child.metadata.get("proof_relpath", "")).strip()
    if not proof_relpath:
        blockers.append(f"release.native_leaf_proof_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    proof_path = (receipt_root / proof_relpath).resolve()
    try:
        proof_path.relative_to(receipt_root.resolve())
    except ValueError:
        blockers.append(f"release.native_leaf_proof_foreign_path:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    if proof_path.is_symlink() or not proof_path.is_file():
        blockers.append(f"release.native_leaf_proof_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    try:
        proof_bytes = proof_path.read_bytes()
        proof_fingerprint = "sha256:" + hashlib.sha256(proof_bytes).hexdigest()
        if proof_fingerprint != child.proof_artifact_fingerprint:
            blockers.append(f"release.native_leaf_proof_hash_mismatch:model:{model_id}")
        proof_payload = _strict_json_loads(proof_bytes.decode("utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
        blockers.append(f"release.native_leaf_proof_unreadable:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    if not isinstance(proof_payload, Mapping):
        blockers.append(f"release.native_leaf_proof_invalid:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    model_result = _release_model_result_from_proof(proof_payload, model_id=model_id)
    if model_result is None:
        blockers.append(f"release.native_leaf_model_result_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    native_path_value = str(model_result.get("native_case_result_artifact_path", "")).strip()
    native_fingerprint = str(model_result.get("native_case_result_artifact_fingerprint", "")).strip()
    if not native_path_value or not native_fingerprint:
        blockers.append(f"release.native_leaf_native_artifact_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    native_path = Path(native_path_value).expanduser()
    if not native_path.is_absolute():
        native_path = (root / native_path).resolve()
    else:
        native_path = native_path.resolve()
    if native_path.is_symlink() or not native_path.is_file():
        blockers.append(f"release.native_leaf_native_artifact_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    try:
        native_digest = "sha256:" + hashlib.sha256(native_path.read_bytes()).hexdigest()
    except OSError:
        blockers.append(f"release.native_leaf_native_artifact_unreadable:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    if native_digest != native_fingerprint:
        blockers.append(f"release.native_leaf_native_artifact_hash_mismatch:model:{model_id}")
    return tuple(dict.fromkeys(blockers))


def _release_direct_leaf_artifact_blockers(
    root: Path,
    receipt_root: Path,
    receipt_ref: str,
    expected_fingerprint: str,
    *,
    model_id: str,
) -> tuple[str, ...]:
    """Validate a freshly executed direct model receipt for one missing leaf."""

    from .evidence_receipts import load_evidence_receipt

    blockers: list[str] = []
    try:
        child = load_evidence_receipt(
            receipt_ref,
            root,
            output_directory=receipt_root,
        )
    except (OSError, TypeError, ValueError) as exc:
        return (
            f"release.native_leaf_child_unreadable:{model_id}:{type(exc).__name__}",
        )
    expected_subject = f"validation-owner:model:{model_id}"
    if child.fingerprint != expected_fingerprint:
        blockers.append(f"release.native_leaf_child_hash_mismatch:model:{model_id}")
    if (
        child.subject_id != expected_subject
        or child.subject_kind != "validation_owner"
        or child.producer_id != expected_subject
        or child.result_status != "pass"
        or child.exit_code != 0
        or child.required_child_receipts
        or child.consumed_child_receipts
        or child.skipped_checks
        or child.blockers
        or str(child.metadata.get("publication_kind", "")) != "supervised_producer"
    ):
        blockers.append(f"release.native_leaf_child_not_direct_pass:model:{model_id}")

    proof_relpath = str(child.metadata.get("proof_relpath", "")).strip()
    if not proof_relpath:
        blockers.append(f"release.native_leaf_proof_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    proof_path = (receipt_root / proof_relpath).resolve()
    try:
        proof_path.relative_to(receipt_root.resolve())
    except ValueError:
        blockers.append(f"release.native_leaf_proof_foreign_path:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    if proof_path.is_symlink() or not proof_path.is_file():
        blockers.append(f"release.native_leaf_proof_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    try:
        proof_bytes = proof_path.read_bytes()
        proof_fingerprint = "sha256:" + hashlib.sha256(proof_bytes).hexdigest()
        if proof_fingerprint != child.proof_artifact_fingerprint:
            blockers.append(f"release.native_leaf_proof_hash_mismatch:model:{model_id}")
        proof_payload = _strict_json_loads(proof_bytes.decode("utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
        blockers.append(f"release.native_leaf_proof_unreadable:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    model_result = _release_model_result_from_proof(proof_payload, model_id=model_id)
    if model_result is None:
        blockers.append(f"release.native_leaf_model_result_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    native_path_value = str(model_result.get("native_case_result_artifact_path", "")).strip()
    native_fingerprint = str(model_result.get("native_case_result_artifact_fingerprint", "")).strip()
    if not native_path_value or not native_fingerprint:
        blockers.append(f"release.native_leaf_native_artifact_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    native_path = Path(native_path_value).expanduser()
    if not native_path.is_absolute():
        native_path = (root / native_path).resolve()
    else:
        native_path = native_path.resolve()
    if native_path.is_symlink() or not native_path.is_file():
        blockers.append(f"release.native_leaf_native_artifact_missing:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    try:
        native_digest = "sha256:" + hashlib.sha256(native_path.read_bytes()).hexdigest()
    except OSError:
        blockers.append(f"release.native_leaf_native_artifact_unreadable:model:{model_id}")
        return tuple(dict.fromkeys(blockers))
    if native_digest != native_fingerprint:
        blockers.append(f"release.native_leaf_native_artifact_hash_mismatch:model:{model_id}")
    return tuple(dict.fromkeys(blockers))


def _release_model_result_from_proof(
    proof_payload: Mapping[str, Any],
    *,
    model_id: str,
) -> Mapping[str, Any] | None:
    """Read the producer-owned model result from the current leaf proof shape.

    ``publish_supervised_validation_owner_result`` serializes the caller's
    evidence context under ``child.payload`` in the immutable owner proof.
    Release qualification must follow that exact schema.  In particular, it
    must not accept an ad-hoc top-level ``evidence_context`` copy or search
    recursively for a similarly named object, because either would allow a
    non-owner field to stand in for producer evidence.
    """

    if proof_payload.get("schema_version") != "flowguard.validation_owner_receipt.v2":
        return None
    child = proof_payload.get("child")
    if not isinstance(child, Mapping):
        return None
    if child.get("status") != "pass":
        return None
    payload = child.get("payload")
    if not isinstance(payload, Mapping):
        return None
    model_result = payload.get("model_result")
    if not isinstance(model_result, Mapping):
        return None
    if model_result.get("model_id") != model_id:
        return None
    return model_result


def _release_missing_leaf_ids(
    revision: Any,
    required_model_ids: tuple[str, ...],
    *,
    root: Path,
    receipt_root: Path,
) -> tuple[str, ...]:
    """Return only absent leaves that may be repaired by one owner run.

    A missing content-addressed receipt or direct model child is repairable.
    A present receipt with a bad fingerprint, foreign owner, or malformed proof
    is an invalid leaf and remains a hard release blocker.
    """

    from .evidence_receipts import load_evidence_receipt, receipt_path

    completed = tuple(getattr(revision, "completed_evidence_refs", ()) or ())
    missing: list[str] = []
    for model_id in required_model_ids:
        affected_id = f"model_instance:model:{model_id}"
        matches = tuple(
            item
            for item in completed
            if affected_id in tuple(getattr(item, "covered_affected_ids", ()) or ())
        )
        if not matches:
            missing.append(model_id)
            continue
        if len(matches) != 1:
            continue
        ref = matches[0]
        expected_receipt_path = receipt_path(
            str(getattr(ref, "receipt_id", "")),
            root,
            output_directory=receipt_root,
        )
        if not expected_receipt_path.is_file() or expected_receipt_path.is_symlink():
            missing.append(model_id)
            continue
        try:
            aggregate = load_evidence_receipt(
                str(getattr(ref, "receipt_id", "")),
                root,
                output_directory=receipt_root,
            )
        except (OSError, TypeError, ValueError):
            continue
        expected_subject = f"validation-owner:model:{model_id}"
        child_requirements = tuple(
            item
            for item in aggregate.required_child_receipts
            if item.subject_id == expected_subject
        )
        if len(child_requirements) != 1:
            if not child_requirements:
                missing.append(model_id)
            continue
        child_path = receipt_path(
            child_requirements[0].receipt_id,
            root,
            output_directory=receipt_root,
        )
        if not child_path.is_file() or child_path.is_symlink():
            missing.append(model_id)
    return tuple(sorted(set(missing)))


def _change_current_operation(
    root: Path,
    request: Mapping[str, Any],
    *,
    request_sha256: str,
) -> dict[str, Any]:
    from .model_authority import (
        ModelAuthorityError,
        ModelRevisionSet,
        load_model_system_snapshot,
    )
    from .model_authority_store import (
        activate_model_revision_set,
        load_current_model_authority_state,
        load_observed_model_system,
    )
    from .model_intent import ModelIntentContribution, ModelIntentDisposition
    from .model_intent_authority import EffectiveIntentTransition
    from .model_regressions import (
        prepare_model_regression_plan,
        run_manifest_regressions,
    )
    from .model_revision_builder import build_current_model_revision
    from .model_revision_owner_evidence import produce_model_revision_owner_evidence
    from .model_revision_plan import preview_current_model_revision
    from .model_revision_set import RevisionRemovalDisposition
    from .model_system_inventory import build_manifest_model_system_snapshot

    expected_current = request["expected_current"]
    if not isinstance(expected_current, str) or not expected_current.strip():
        raise ValueError("current change expected_current must be a non-empty fingerprint")
    head, base = load_observed_model_system(root)
    if head.fingerprint != expected_current:
        raise ValueError("current change expected_current does not match current head")
    if request["target_id"] != head.system_id:
        raise ValueError("current change target_id does not match current authority")

    if request["revision_input"] is None:
        # A null preparation is a read-only no-op request.  Preview the live
        # candidate first, then consume only the accepted selected projection;
        # no preparation directory, owner, receipt, or CAS write is allowed on
        # this path.
        plan = preview_current_model_revision(root, snapshot_id=base.snapshot_id)
        if not plan.ok:
            return {
                "operation": "change",
                "status": "blocked",
                "reason": "current_change_preview_blocked",
                "target_id": head.system_id,
                "bootstrap": False,
                "required_count": len(plan.candidate_model_ids),
                "producer_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "write_count": 0,
                "authority_write_count": 0,
                "head": head.to_dict(),
                "blockers": [
                    f"revision_preview:{item.code}" for item in plan.blockers
                ] or ["revision_preview:blocked"],
                "error": "; ".join(item.message for item in plan.blockers),
                "claim_boundary": (
                    "The null-preparation change was read-only; the current "
                    "candidate preview was blocked and no producer or write ran."
                ),
            }
        if plan.change_present:
            raise ValueError(
                "revision_preparation_required: live candidate differs from current authority"
            )
        from .model_authority_store import (
            _load_bound_read_projection,
            read_selected_model_projection,
        )
        try:
            projection = _load_bound_read_projection(root, head)
            index = projection["index"]
            indexed_models = index.get("models") if isinstance(index, Mapping) else None
            known_model_ids = set(indexed_models) if isinstance(indexed_models, Mapping) else set()
            unknown_scope = sorted(set(request["scope"]) - known_model_ids)
            if unknown_scope:
                raise ValueError(f"current no-op scope contains unknown model IDs: {unknown_scope}")
            closure = read_selected_model_projection(
                root,
                head=head,
                projection=projection,
                selected_model_ids=tuple(request["scope"]),
            )
        except (ModelAuthorityError, OSError, TypeError, ValueError) as exc:
            return {
                "operation": "change",
                "status": "blocked",
                "reason": "current_read_projection_unavailable",
                "target_id": head.system_id,
                "bootstrap": False,
                "required_count": len(plan.candidate_model_ids),
                "producer_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "write_count": 0,
                "authority_write_count": 0,
                "head": head.to_dict(),
                "blockers": ["current_read_projection_unavailable"],
                "error": str(exc),
                "claim_boundary": (
                    "The null-preparation change did not repair an invalid "
                    "projection and did not start a producer or move authority."
                ),
            }
        if not closure.ok or closure.selected_source_currentness != "current":
            return {
                "operation": "change",
                "status": "blocked",
                "reason": "current_read_projection_not_current",
                "target_id": head.system_id,
                "bootstrap": False,
                "required_count": len(plan.candidate_model_ids),
                "producer_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "write_count": 0,
                "authority_write_count": 0,
                "head": head.to_dict(),
                "selected_model_ids": list(closure.selected_model_ids),
                "stale_obligations": list(closure.stale_obligations),
                "blockers": ["current_read_projection_not_current"],
                "claim_boundary": (
                    "The null-preparation change requires a valid current selected "
                    "projection; no producer or authority write ran."
                ),
            }
        return {
            "operation": "change",
            "status": "pass",
            "reason": "no_change",
            "target_id": head.system_id,
            "bootstrap": False,
            "required_count": len(plan.candidate_model_ids),
            "producer_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "write_count": 0,
            "authority_write_count": 0,
            "head": head.to_dict(),
            "selected_model_ids": list(closure.selected_model_ids),
            "current_revision_fingerprint": head.accepted_revision_set_fingerprint,
            "stale_obligations": list(closure.stale_obligations),
            "blockers": [],
            "claim_boundary": (
                "The live candidate equals the accepted authority and its selected "
                "projection is current. No producer, preparation, or authority write ran."
            ),
        }

    _preparation_path, preparation_raw = _root_file_reference(
        root, request["revision_input"], context="revision_input"
    )
    preparation = _strict_json_loads(preparation_raw.decode("utf-8"))
    fields = {
        "schema", "target_id", "base_head_fingerprint", "snapshot_id",
        "revision_set_id", "task_id", "decision_reason",
        "intent_contributions", "intent_dispositions", "effective_intent_transitions",
        "removal_dispositions", "current_design_intent_contributions",
        "accepted_boundary_contract_ref",
        "bootstrap_staging_root",
    }
    if not isinstance(preparation, Mapping) or set(preparation) != fields:
        actual = set(preparation) if isinstance(preparation, Mapping) else set()
        raise ValueError(
            "revision preparation fields are not exact-current: "
            f"missing={sorted(fields - actual)}, unexpected={sorted(actual - fields)}"
        )
    if preparation["schema"] != "flowguard.revision_preparation.v1":
        raise ValueError("revision preparation schema is not current")
    if preparation["target_id"] != head.system_id:
        raise ValueError("revision preparation target_id does not match current authority")
    if preparation["base_head_fingerprint"] != head.fingerprint:
        raise ValueError("revision preparation base_head_fingerprint is stale")
    if preparation["bootstrap_staging_root"] is not None:
        raise ValueError("current change bootstrap_staging_root must be null")
    if preparation["current_design_intent_contributions"]:
        raise ValueError("current change cannot provide bootstrap design contributions")
    if preparation["accepted_boundary_contract_ref"] is not None:
        raise ValueError("current minimal change does not accept a boundary contract reference")
    for field in ("snapshot_id", "revision_set_id", "task_id", "decision_reason"):
        if not isinstance(preparation[field], str) or not preparation[field].strip():
            raise ValueError(f"revision preparation {field} must be non-empty")
    for field in (
        "intent_contributions", "intent_dispositions", "effective_intent_transitions",
        "removal_dispositions", "current_design_intent_contributions",
    ):
        if not isinstance(preparation[field], list):
            raise ValueError(f"revision preparation {field} must be an array")

    contributions = tuple(
        ModelIntentContribution.from_dict(row) for row in preparation["intent_contributions"]
    )
    dispositions = tuple(
        ModelIntentDisposition.from_dict(row) for row in preparation["intent_dispositions"]
    )
    transitions = tuple(
        EffectiveIntentTransition.from_dict(row)
        for row in preparation["effective_intent_transitions"]
    )
    removals = tuple(
        RevisionRemovalDisposition.from_dict(row)
        for row in preparation["removal_dispositions"]
    )
    plan = preview_current_model_revision(
        root, snapshot_id=str(preparation["snapshot_id"])
    )
    if not plan.ok or not plan.change_present or plan.snapshot_diff is None:
        raise ValueError("current change preview is blocked or contains no change")
    if plan.observed_head_fingerprint != head.fingerprint:
        raise ValueError("current change preview does not match expected current head")
    preview_candidate = build_manifest_model_system_snapshot(
        root,
        snapshot_id=str(preparation["snapshot_id"]),
        system_id=base.system_id,
        subject_lane=base.subject_lane,
        lifecycle=base.lifecycle,
    )
    current_state = load_current_model_authority_state(
        root,
        head=head,
        snapshot=base,
        reverify_current_sources=False,
    )
    known_scope_ids = {
        *(item.logical_model_id for item in preview_candidate.model_instances),
        *(relation.relation_id for relation in preview_candidate.relations),
        *(
            endpoint.endpoint_id
            for relation in preview_candidate.relations
            for endpoint in (relation.source, relation.target)
        ),
    }
    if current_state.accepted_revision is not None:
        known_scope_ids.update(
            item.contribution_id
            for item in current_state.accepted_revision.current_effective_intent_view.active_contributions
        )
    unknown_scope = sorted(set(request["scope"]) - known_scope_ids)
    if unknown_scope:
        raise ValueError(f"current change scope contains unknown IDs: {unknown_scope}")
    required_quality_ids = tuple(
        sorted(
            member.member_id
            for member in plan.snapshot_diff.members
            if member.operation in {"add", "replace"}
        )
    )
    receipt_root = root / ".flowguard" / "evidence" / "model-owner-receipts"
    output_root = root / "work" / f"change-{request_sha256[:12]}"
    receipt_root.mkdir(parents=True, exist_ok=True)
    try:
        prepared_plan = prepare_model_regression_plan(
            root,
            target_id=head.system_id,
            base_head=head.fingerprint,
            candidate_fingerprint=preview_candidate.fingerprint,
            affected_ids=required_quality_ids,
            receipt_dir=receipt_root,
            require_executed_case_ids=True,
        )
        parent = run_manifest_regressions(
            root,
            tier="full",
            jobs=1,
            output_dir=output_root / "model-parent",
            receipt_dir=receipt_root,
            require_executed_case_ids=True,
            prepared_plan=prepared_plan,
        )
    except (OSError, TypeError, ValueError) as exc:
        completed_leaf_artifacts = tuple(
            (output_root / "model-parent").glob("*/native-case-results.json")
        )
        run_count = len(completed_leaf_artifacts)
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_failed_or_source_drifted",
            "target_id": head.system_id,
            "bootstrap": False,
            "required_count": len(plan.candidate_model_ids),
            "producer_count": run_count,
            "run_count": run_count,
            "reused_count": max(0, len(plan.candidate_model_ids) - run_count),
            "write_count": 0,
            "affected_model_ids": list(required_quality_ids),
            "head": head.to_dict(),
            "blockers": ["owner_execution_failed_or_source_drifted"],
            "error": str(exc),
            "claim_boundary": (
                "Owner execution or final source freshness failed; no model authority head was moved."
            ),
        }
    if parent.status != "pass" or not parent.parent_receipt_path:
        run_count = sum(
            item.execution_disposition == "execute" for item in parent.results
        )
        reused_count = sum(
            item.execution_disposition == "reuse_current" for item in parent.results
        )
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_failed_or_source_drifted",
            "target_id": head.system_id,
            "bootstrap": False,
            "required_count": len(parent.selected_model_ids),
            "producer_count": run_count,
            "run_count": run_count,
            "reused_count": reused_count,
            "write_count": 0,
            "affected_model_ids": list(required_quality_ids),
            "head": head.to_dict(),
            "blockers": ["owner_execution_failed_or_source_drifted"],
            "claim_boundary": (
                "Owner execution or final source freshness failed; no model authority head was moved."
            ),
        }
    run_count = sum(item.execution_disposition == "execute" for item in parent.results)
    reused_count = sum(item.execution_disposition == "reuse_current" for item in parent.results)
    def _post_execution_failure(exc: Exception) -> dict[str, Any]:
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_or_acceptance_failed",
            "target_id": head.system_id,
            "bootstrap": False,
            "required_count": len(parent.selected_model_ids),
            "producer_count": run_count,
            "run_count": run_count,
            "reused_count": reused_count,
            "write_count": 0,
            "authority_write_count": 0,
            "cleanup_status": "not_verified",
            "affected_model_ids": list(required_quality_ids),
            "head": head.to_dict(),
            "blockers": ["owner_execution_or_acceptance_failed"],
            "error": str(exc),
            "claim_boundary": (
                "At least one owner had already run; the downstream evidence, "
                "revision, or CAS acceptance failed and the authority head was unchanged."
            ),
        }

    try:
        owner_report = produce_model_revision_owner_evidence(
            root,
            model_parent_receipt=parent.parent_receipt_path,
            snapshot_id=str(preparation["snapshot_id"]),
            receipt_root=receipt_root,
            output_path=output_root / "native-owner-evidence.json",
        )
        candidate = build_manifest_model_system_snapshot(
            root,
            snapshot_id=str(preparation["snapshot_id"]),
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        subjects, quality_results = _native_path_quality_material(
            parent,
            candidate,
            required_model_ids=required_quality_ids,
            currentness_id=candidate.fingerprint,
        )
        built = build_current_model_revision(
            root,
            model_parent_receipt=parent.parent_receipt_path,
            receipt_root=receipt_root,
            output_root=output_root / "authority",
            revision_set_id=str(preparation["revision_set_id"]),
            task_id=str(preparation["task_id"]),
            snapshot_id=str(preparation["snapshot_id"]),
            removal_dispositions=removals,
            intent_contributions=contributions,
            intent_dispositions=dispositions,
            effective_intent_transitions=transitions,
            native_owner_contracts=owner_report.bundle.contracts,
            native_owner_receipts=owner_report.bundle.receipts,
            native_owner_verification_results=owner_report.bundle.verification_results,
            path_quality_subjects=subjects,
            path_quality_results=quality_results,
            decision_reason=str(preparation["decision_reason"]),
        )
        if built.status != "pass":
            raise ValueError("current change revision build did not pass")
        final_candidate = load_model_system_snapshot(built.candidate_snapshot_path)
        revision = ModelRevisionSet.from_dict(
            _strict_json_loads(Path(built.revision_set_path).read_text(encoding="utf-8"))
        )
        next_head, _activation = activate_model_revision_set(
            root,
            final_candidate,
            revision,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        return _post_execution_failure(exc)
    return {
        "operation": "change", "status": "pass", "target_id": head.system_id,
        "bootstrap": False, "required_count": len(parent.selected_model_ids),
        "run_count": run_count, "reused_count": reused_count, "write_count": 1,
        "authority_write_count": 1,
        "affected_model_ids": list(required_quality_ids), "head": next_head.to_dict(),
        "current_revision_fingerprint": revision.fingerprint, "blockers": [],
        "claim_boundary": "One exact accepted current revision was built and activated by CAS.",
    }


def _change_operation(
    root: Path,
    request: Mapping[str, Any],
    values: Mapping[str, Any],
    *,
    request_sha256: str,
) -> dict[str, Any]:
    """Execute one strict bootstrap or existing-current change transaction."""

    from .evidence_receipts import fingerprint_value
    from .model_authority_store import bootstrap_initial_current_model_authority
    from .model_intent import ModelIntentContribution
    from .model_regressions import (
        prepare_model_regression_plan,
        run_manifest_regressions,
    )
    from .model_system_inventory import build_manifest_model_system_snapshot
    from .project_manifest import manifest_text_fingerprint

    request_fields = {
        "operation",
        "target_id",
        "scope",
        "expected_current",
        "bootstrap",
        "revision_input",
    }
    if set(request) != request_fields:
        raise ValueError(
            "change request fields are not exact-current: "
            f"missing={sorted(request_fields - set(request))}, "
            f"unexpected={sorted(set(request) - request_fields)}"
        )
    if request["operation"] != "change":
        raise ValueError("change request operation must be 'change'")
    if "expected_current" in values:
        raise ValueError("change expected current belongs in the request JSON")
    target_id = request["target_id"]
    scope = request["scope"]
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("change target_id must be a non-empty string")
    if (
        not isinstance(scope, list)
        or not scope
        or any(not isinstance(item, str) or not item.strip() for item in scope)
        or len(scope) != len(set(scope))
    ):
        raise ValueError("change scope must be a non-empty unique model ID array")
    if type(request["bootstrap"]) is not bool:
        raise ValueError("change bootstrap must be a boolean")
    if request["bootstrap"] is False:
        return _change_current_operation(
            root,
            request,
            request_sha256=request_sha256,
        )
    if request["expected_current"] is not None:
        raise ValueError("bootstrap change expected_current must be null")

    _preparation_path, preparation_raw = _root_file_reference(
        root,
        request["revision_input"],
        context="revision_input",
    )
    preparation = _strict_json_loads(preparation_raw.decode("utf-8"))
    preparation_fields = {
        "schema",
        "target_id",
        "base_head_fingerprint",
        "snapshot_id",
        "revision_set_id",
        "task_id",
        "decision_reason",
        "intent_contributions",
        "intent_dispositions",
        "effective_intent_transitions",
        "removal_dispositions",
        "current_design_intent_contributions",
        "accepted_boundary_contract_ref",
        "bootstrap_staging_root",
    }
    if not isinstance(preparation, Mapping) or set(preparation) != preparation_fields:
        actual = set(preparation) if isinstance(preparation, Mapping) else set()
        raise ValueError(
            "revision preparation fields are not exact-current: "
            f"missing={sorted(preparation_fields - actual)}, "
            f"unexpected={sorted(actual - preparation_fields)}"
        )
    if preparation["schema"] != "flowguard.revision_preparation.v1":
        raise ValueError("revision preparation schema is not current")
    if preparation["target_id"] != target_id:
        raise ValueError("revision preparation target_id does not match request")
    if preparation["base_head_fingerprint"] is not None:
        raise ValueError("bootstrap preparation base_head_fingerprint must be null")
    for field in (
        "snapshot_id",
        "revision_set_id",
        "task_id",
        "decision_reason",
    ):
        if not isinstance(preparation[field], str) or not preparation[field].strip():
            raise ValueError(f"revision preparation {field} must be non-empty")
    for field in (
        "intent_contributions",
        "intent_dispositions",
        "effective_intent_transitions",
        "removal_dispositions",
        "current_design_intent_contributions",
    ):
        if not isinstance(preparation[field], list):
            raise ValueError(f"revision preparation {field} must be an array")
    if any(
        preparation[field]
        for field in (
            "intent_contributions",
            "intent_dispositions",
            "effective_intent_transitions",
            "removal_dispositions",
        )
    ):
        raise ValueError("bootstrap preparation cannot contain current-revision transitions")
    if preparation["accepted_boundary_contract_ref"] is not None:
        raise ValueError("minimal bootstrap does not accept a boundary contract reference")
    design = tuple(
        ModelIntentContribution.from_dict(item)
        for item in preparation["current_design_intent_contributions"]
    )
    if not design:
        raise ValueError("bootstrap requires current design intent contributions")

    staging_value = preparation["bootstrap_staging_root"]
    if not isinstance(staging_value, str) or not staging_value.strip():
        raise ValueError("bootstrap_staging_root must be a non-empty ROOT-relative path")
    staging_path = (root / staging_value).resolve()
    bootstrap_root = (root / ".flowguard" / "work" / "bootstrap").resolve()
    try:
        relative_staging = staging_path.relative_to(bootstrap_root)
    except ValueError as exc:
        raise ValueError("bootstrap_staging_root must remain under .flowguard/work/bootstrap") from exc
    if len(relative_staging.parts) != 1:
        raise ValueError("bootstrap_staging_root must name one isolated request directory")
    if staging_path.is_symlink() or not staging_path.is_dir():
        raise ValueError("bootstrap_staging_root must be an existing non-symlink directory")

    manifest_path = root / ".flowguard" / "project.toml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    if "[model_authority]" in manifest_text:
        raise ValueError("bootstrap target already has current model authority")
    candidate = build_manifest_model_system_snapshot(
        staging_path,
        snapshot_id=str(preparation["snapshot_id"]),
        system_id=str(target_id),
    )
    if candidate.system_id != target_id:
        raise ValueError("change target_id does not match candidate system_id")
    known_model_ids = {item.logical_model_id for item in candidate.model_instances}
    unknown_scope = sorted(set(scope) - known_model_ids)
    if unknown_scope:
        raise ValueError(f"change scope contains unknown model IDs: {unknown_scope}")

    receipt_root = root / ".flowguard" / "evidence" / "model-owner-receipts"
    # Keep the private request directory below the Windows MAX_PATH budget;
    # the full request identity remains bound into every receipt/plan.
    output_root = root / "work" / f"change-{request_sha256[:12]}"
    receipt_root.mkdir(parents=True, exist_ok=True)
    try:
        prepared_plan = prepare_model_regression_plan(
            staging_path,
            target_id=target_id,
            base_head="",
            candidate_fingerprint=candidate.fingerprint,
            affected_ids=tuple(item.logical_model_id for item in candidate.model_instances),
            receipt_dir=receipt_root,
            require_executed_case_ids=True,
        )
        parent = run_manifest_regressions(
            staging_path,
            tier="full",
            jobs=1,
            output_dir=output_root / "model-parent",
            receipt_dir=receipt_root,
            require_executed_case_ids=True,
            prepared_plan=prepared_plan,
        )
    except (OSError, TypeError, ValueError) as exc:
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_failed_or_source_drifted",
            "target_id": target_id,
            "bootstrap": True,
            "required_count": len(candidate.model_instances),
            "producer_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "write_count": 0,
            "head": None,
            "blockers": ["owner_execution_failed_or_source_drifted"],
            "error": str(exc),
            "claim_boundary": (
                "Bootstrap owner execution or source freshness failed; no "
                "observed model authority head was created."
            ),
        }
    if parent.status != "pass" or not parent.parent_receipt_path:
        run_count = sum(
            item.execution_disposition == "execute" for item in parent.results
        )
        reused_count = sum(
            item.execution_disposition == "reuse_current" for item in parent.results
        )
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_failed_or_source_drifted",
            "target_id": target_id,
            "bootstrap": True,
            "required_count": len(parent.selected_model_ids),
            "producer_count": run_count,
            "run_count": run_count,
            "reused_count": reused_count,
            "write_count": 0,
            "head": None,
            "blockers": ["owner_execution_failed_or_source_drifted"],
            "claim_boundary": (
                "Bootstrap owner execution or source freshness failed; no "
                "observed model authority head was created."
            ),
        }
    run_count = sum(item.execution_disposition == "execute" for item in parent.results)
    reused_count = sum(item.execution_disposition == "reuse_current" for item in parent.results)
    try:
        result = bootstrap_initial_current_model_authority(
            root,
            staging_root=staging_path,
            expected_absent_manifest_fingerprint=manifest_text_fingerprint(manifest_text),
            snapshot_id=str(preparation["snapshot_id"]),
            bootstrap_evidence_fingerprint=fingerprint_value(
                {
                    "parent": parent.parent_receipt_fingerprint,
                    "candidate": candidate.fingerprint,
                    "preparation": f"sha256:{hashlib.sha256(preparation_raw).hexdigest()}",
                }
            ),
            model_parent_receipt=parent.parent_receipt_path,
            receipt_root=receipt_root,
            revision_set_id=str(preparation["revision_set_id"]),
            task_id=str(preparation["task_id"]),
            system_id=str(target_id),
            current_design_intent_contributions=design,
            intent_receipt_id=f"intent:{preparation['revision_set_id']}",
            intent_rationale=str(preparation["decision_reason"]),
            intent_claim_boundary=str(preparation["decision_reason"]),
            decision_reason=str(preparation["decision_reason"]),
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        return {
            "operation": "change",
            "status": "blocked",
            "reason": "owner_execution_or_acceptance_failed",
            "target_id": target_id,
            "bootstrap": True,
            "required_count": len(parent.selected_model_ids),
            "producer_count": run_count,
            "run_count": run_count,
            "reused_count": reused_count,
            "write_count": 0,
            "authority_write_count": 0,
            "cleanup_status": "not_verified",
            "head": None,
            "blockers": ["owner_execution_or_acceptance_failed"],
            "error": str(exc),
            "claim_boundary": (
                "At least one bootstrap owner had already run; acceptance failed "
                "and no observed authority head was accepted."
            ),
        }
    return {
        "operation": "change",
        "status": "pass",
        "target_id": target_id,
        "bootstrap": True,
        "required_count": len(parent.selected_model_ids),
        "run_count": run_count,
        "reused_count": reused_count,
        "write_count": 1,
        "authority_write_count": 1,
        "head": result["head"],
        "current_revision_fingerprint": result["current_revision_fingerprint"],
        "blockers": [],
        "claim_boundary": result["claim_boundary"],
    }


def _release_operation(
    root: Path,
    request: Mapping[str, Any],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    """Qualify one exact accepted current source and optional local artifact."""

    from .evidence_lifecycle import write_json_atomic
    from .model_authority import ModelAuthorityError
    from .model_authority_store import (
        load_current_model_authority_state,
        load_observed_model_system,
        read_selected_model_closure,
    )
    from .release_verification import verify_declared_artifact
    from .model_regressions import (
        prepare_model_regression_plan,
        run_manifest_regressions,
    )

    request_fields = {
        "operation",
        "target_id",
        "scope",
        "expected_current",
        "release_contract",
        "artifact",
    }
    if set(request) != request_fields:
        raise ValueError(
            "release request fields are not exact-current: "
            f"missing={sorted(request_fields - set(request))}, "
            f"unexpected={sorted(set(request) - request_fields)}"
        )
    if request["operation"] != "release":
        raise ValueError("release request operation must be 'release'")
    if "expected_current" in values:
        raise ValueError("release expected current belongs in the request JSON")
    target_id = request["target_id"]
    expected_current = request["expected_current"]
    scope = request["scope"]
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("release target_id must be a non-empty string")
    if not isinstance(expected_current, str) or not expected_current.strip():
        raise ValueError("release expected_current must be a non-empty head fingerprint")
    if (
        not isinstance(scope, list)
        or not scope
        or any(not isinstance(item, str) or not item.strip() for item in scope)
        or len(scope) != len(set(scope))
    ):
        raise ValueError("release scope must be a non-empty unique model ID array")

    _contract_path, contract_raw = _root_file_reference(
        root,
        request["release_contract"],
        context="release_contract",
    )
    contract = _strict_json_loads(contract_raw.decode("utf-8"))
    contract_fields = {
        "schema",
        "target_id",
        "required_model_ids",
        "required_check_ids",
        "required_source_paths",
        "artifact_members",
    }
    if not isinstance(contract, Mapping) or set(contract) != contract_fields:
        actual = set(contract) if isinstance(contract, Mapping) else set()
        raise ValueError(
            "release contract fields are not exact-current: "
            f"missing={sorted(contract_fields - actual)}, "
            f"unexpected={sorted(actual - contract_fields)}"
        )
    if contract["schema"] != "flowguard.release_contract.v1":
        raise ValueError("release contract schema is not current")
    if contract["target_id"] != target_id:
        raise ValueError("release contract target_id does not match request")
    for field in ("required_model_ids", "required_check_ids", "required_source_paths"):
        rows = contract[field]
        if (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(item, str) or not item.strip() for item in rows)
            or len(rows) != len(set(rows))
        ):
            raise ValueError(f"release contract {field} must be a non-empty unique string array")
    artifact_members = contract["artifact_members"]
    if not isinstance(artifact_members, list):
        raise ValueError("release contract artifact_members must be an array")
    if not set(contract["required_model_ids"]).issubset(scope):
        raise ValueError("release scope does not cover every required model")

    # Artifact byte admission happens before any source/evidence producer can
    # be considered.  The public release operation never publishes or tags.
    artifact = request["artifact"]
    artifact_checks = ()
    if artifact is not None:
        if not isinstance(artifact, Mapping):
            raise ValueError("release artifact must be null or an object")
        artifact_checks = verify_declared_artifact(root, artifact, artifact_members)
        if not artifact_checks or not all(item.ok for item in artifact_checks):
            return {
                "operation": "release",
                "status": "blocked",
                "reason": "artifact_invalid",
                "target_id": target_id,
                "producer_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "write_count": 0,
                "artifact_status": "blocked",
                "checks": [item.to_dict() for item in artifact_checks],
                "blockers": [item.check_id for item in artifact_checks if not item.ok],
                "claim_scope": "local_qualification",
            }
    elif artifact_members:
        raise ValueError("source-only release contract cannot declare artifact_members")

    try:
        head, snapshot = load_observed_model_system(root)
        if head.fingerprint != expected_current:
            raise ValueError("release expected_current does not match current head")
        if head.system_id != target_id:
            raise ValueError("release target_id does not match current authority")
        state = load_current_model_authority_state(
            root,
            head=head,
            snapshot=snapshot,
            reverify_current_sources=True,
        )
        selected = read_selected_model_closure(
            root,
            selected_model_ids=tuple(contract["required_model_ids"]),
            authority_state=state,
        )
        if selected.selected_source_currentness != "current":
            raise ModelAuthorityError(
                "required release model source differs from accepted current authority"
            )
    except ModelAuthorityError as exc:
        return {
            "operation": "release",
            "status": "blocked",
            "reason": "source_requires_change",
            "target_id": target_id,
            "producer_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "write_count": 0,
            "artifact_status": "pass" if artifact is not None else "not_run",
            "blockers": ["source_requires_change"],
            "error": str(exc),
            "claim_scope": "local_qualification",
        }
    revision = state.accepted_revision
    if revision is None or revision.status != "accepted":
        raise ValueError("release requires one accepted current revision")
    receipt_root = root / ".flowguard" / "evidence" / "model-owner-receipts"
    current_model_ids = {item.logical_model_id for item in snapshot.model_instances}
    missing_models = sorted(set(contract["required_model_ids"]) - current_model_ids)
    if missing_models:
        raise ValueError(f"release contract references non-current models: {missing_models}")
    accepted_check_ids = {
        obligation
        for evidence in revision.required_evidence_refs
        for obligation in evidence.obligation_ids
    }
    missing_checks = sorted(set(contract["required_check_ids"]) - accepted_check_ids)
    if missing_checks:
        raise ValueError(f"release contract checks are not accepted obligations: {missing_checks}")
    required_model_ids = tuple(contract["required_model_ids"])
    missing_leaf_ids = _release_missing_leaf_ids(
        revision,
        required_model_ids,
        root=root,
        receipt_root=receipt_root,
    )
    leaf_blockers = _release_leaf_blockers(
        revision,
        required_model_ids,
        root=root,
        receipt_root=receipt_root,
    )
    # A genuinely absent receipt/child can be repaired by its one model owner.
    # Any present-but-invalid identity remains a hard blocker and therefore
    # never gets overwritten by a fresh run.
    repairable_prefixes = (
        "release.native_leaf_missing:",
        "release.native_leaf_receipt_unreadable:",
        "release.native_leaf_child_missing_or_ambiguous:",
        "release.native_leaf_child_unreadable:",
    )
    nonrepairable_leaf_blockers = tuple(
        blocker
        for blocker in leaf_blockers
        if not (
            blocker.startswith(repairable_prefixes)
            and any(f":{model_id}" in blocker for model_id in missing_leaf_ids)
        )
    )
    producer_count = 0
    run_count = 0
    reused_count = len(required_model_ids)
    leaf_receipts: dict[str, tuple[str, str]] = {}
    if nonrepairable_leaf_blockers:
        return {
            "operation": "release",
            "status": "blocked",
            "reason": "native_leaf_invalid",
            "target_id": target_id,
            "producer_count": 0,
            "run_count": 0,
            "reused_count": 0,
            "write_count": 0,
            "artifact_status": "pass" if artifact is not None else "not_run",
            "leaf_status": "blocked",
            "blockers": list(nonrepairable_leaf_blockers),
            "claim_scope": "local_qualification",
        }
    if missing_leaf_ids:
        release_output = root / "work" / (
            "release-" + hashlib.sha256(
                json.dumps(
                    {
                        "head": head.fingerprint,
                        "models": list(required_model_ids),
                        "missing": list(missing_leaf_ids),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()[:12]
        )
        try:
            prepared_plan = prepare_model_regression_plan(
                root,
                target_id=target_id,
                base_head=head.fingerprint,
                candidate_fingerprint=snapshot.fingerprint,
                affected_ids=missing_leaf_ids,
                receipt_dir=receipt_root,
                require_executed_case_ids=True,
            )
            parent = run_manifest_regressions(
                root,
                tier="full",
                jobs=1,
                output_dir=release_output / "model-parent",
                receipt_dir=receipt_root,
                require_executed_case_ids=True,
                prepared_plan=prepared_plan,
            )
        except (OSError, TypeError, ValueError) as exc:
            return {
                "operation": "release",
                "status": "blocked",
                "reason": "native_leaf_execution_failed",
                "target_id": target_id,
                "producer_count": 0,
                "run_count": 0,
                "reused_count": 0,
                "write_count": 0,
                "artifact_status": "pass" if artifact is not None else "not_run",
                "leaf_status": "blocked",
                "blockers": ["release.native_leaf_execution_failed"],
                "error": str(exc),
                "claim_scope": "local_qualification",
            }
        required_results = {
            item.model_id: item
            for item in parent.results
            if item.model_id in required_model_ids
        }
        run_count = sum(
            item.execution_disposition == "execute"
            for item in required_results.values()
        )
        producer_count = run_count
        reused_count = sum(
            item.execution_disposition == "reuse_current"
            for item in required_results.values()
        )
        if parent.status != "pass" or set(required_results) != set(required_model_ids):
            return {
                "operation": "release",
                "status": "blocked",
                "reason": "native_leaf_execution_failed",
                "target_id": target_id,
                "producer_count": producer_count,
                "run_count": run_count,
                "reused_count": reused_count,
                "write_count": 0,
                "artifact_status": "pass" if artifact is not None else "not_run",
                "leaf_status": "blocked",
                "blockers": ["release.native_leaf_execution_failed"],
                "claim_scope": "local_qualification",
            }
        for model_id in missing_leaf_ids:
            result = required_results.get(model_id)
            if result is None or result.execution_disposition != "execute":
                return {
                    "operation": "release",
                    "status": "blocked",
                    "reason": "native_leaf_execution_failed",
                    "target_id": target_id,
                    "producer_count": producer_count,
                    "run_count": run_count,
                    "reused_count": reused_count,
                    "write_count": 0,
                    "artifact_status": "pass" if artifact is not None else "not_run",
                    "leaf_status": "blocked",
                    "blockers": [
                        f"release.native_leaf_missing_owner_not_executed:model:{model_id}"
                    ],
                    "claim_scope": "local_qualification",
                }
            leaf_receipts[model_id] = (
                str(result.receipt_path),
                str(result.receipt_fingerprint),
            )
        leaf_blockers = _release_leaf_blockers(
            revision,
            required_model_ids,
            root=root,
            receipt_root=receipt_root,
            leaf_receipts=leaf_receipts,
        )
        if leaf_blockers:
            return {
                "operation": "release",
                "status": "blocked",
                "reason": "native_leaf_invalid",
                "target_id": target_id,
                "producer_count": producer_count,
                "run_count": run_count,
                "reused_count": reused_count,
                "write_count": 0,
                "artifact_status": "pass" if artifact is not None else "not_run",
                "leaf_status": "blocked",
                "blockers": list(leaf_blockers),
                "claim_scope": "local_qualification",
            }
    source_rows: list[dict[str, str]] = []
    for relative in contract["required_source_paths"]:
        candidate = Path(relative)
        path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("release required source path escapes ROOT") from exc
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"release required source path is not an ordinary file: {relative}")
        source_rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    # Repeat artifact bytes and head CAS after all source reads.
    if artifact is not None:
        final_artifact_checks = verify_declared_artifact(root, artifact, artifact_members)
        if not all(item.ok for item in final_artifact_checks):
            raise ValueError("release artifact changed during qualification")
    final_head, _final_snapshot = load_observed_model_system(root)
    if final_head.fingerprint != head.fingerprint:
        raise ValueError("release current head changed during qualification")
    from .evidence_receipts import load_evidence_receipt

    completed_refs = tuple(getattr(revision, "completed_evidence_refs", ()) or ())
    leaf_rows: list[dict[str, str]] = []
    for model_id in required_model_ids:
        if model_id in leaf_receipts:
            receipt_ref, expected_fingerprint = leaf_receipts[model_id]
            receipt = load_evidence_receipt(
                receipt_ref,
                root,
                output_directory=receipt_root,
            )
            leaf_rows.append(
                {
                    "model_id": model_id,
                    "receipt_id": receipt.receipt_id,
                    "receipt_fingerprint": receipt.fingerprint,
                    "execution": "execute",
                }
            )
            if expected_fingerprint != receipt.fingerprint:
                raise ValueError(
                    f"release leaf receipt changed during qualification: {model_id}"
                )
            continue
        affected_id = f"model_instance:model:{model_id}"
        matches = tuple(
            item
            for item in completed_refs
            if affected_id in tuple(getattr(item, "covered_affected_ids", ()) or ())
        )
        if len(matches) != 1:
            raise ValueError(f"release leaf identity disappeared during qualification: {model_id}")
        leaf_rows.append(
            {
                "model_id": model_id,
                "receipt_id": str(matches[0].receipt_id),
                "receipt_fingerprint": str(matches[0].receipt_fingerprint),
                "execution": "reuse_current",
            }
        )
    qualification_payload = {
        "schema_version": "flowguard.release_qualification_receipt.v1",
        "target_id": target_id,
        "source_head_fingerprint": head.fingerprint,
        "release_contract_hash": hashlib.sha256(contract_raw).hexdigest(),
        "required_model_ids": list(required_model_ids),
        "required_check_ids": list(contract["required_check_ids"]),
        "required_source_paths": source_rows,
        "artifact_status": "pass" if artifact is not None else "not_run",
        "artifact_checks": [item.to_dict() for item in artifact_checks],
        "leaf_rows": leaf_rows,
        "producer_count": producer_count,
        "run_count": run_count,
        "reused_count": reused_count,
        "claim_scope": "local_qualification",
    }
    qualification_fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(
            qualification_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    qualification_payload["qualification_fingerprint"] = qualification_fingerprint
    qualification_dir = root / ".flowguard" / "evidence" / "release-qualifications"
    qualification_path = qualification_dir / (
        qualification_fingerprint.split(":", 1)[1] + ".json"
    )
    qualification_bytes = (
        json.dumps(
            qualification_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    qualification_write_count = 0
    if qualification_path.exists():
        if qualification_path.is_symlink() or qualification_path.read_bytes() != qualification_bytes:
            raise ValueError("release qualification receipt is not immutable")
    else:
        write_json_atomic(qualification_path, qualification_payload)
        qualification_write_count = 1
    return {
        "operation": "release",
        "status": "pass",
        "target_id": target_id,
        "source_head_fingerprint": head.fingerprint,
        "release_contract_hash": hashlib.sha256(contract_raw).hexdigest(),
        "required_model_ids": list(contract["required_model_ids"]),
        "required_check_ids": list(contract["required_check_ids"]),
        "required_source_paths": source_rows,
        "producer_count": producer_count,
        "run_count": run_count,
        "reused_count": reused_count,
        "write_count": qualification_write_count,
        "artifact_status": "pass" if artifact is not None else "not_run",
        "leaf_status": "pass",
        "qualification": "artifact_and_source" if artifact is not None else "source_qualification_only",
        "checks": [item.to_dict() for item in artifact_checks],
        "qualification_receipt_path": qualification_path.relative_to(root).as_posix(),
        "qualification_receipt_fingerprint": qualification_fingerprint,
        "blockers": [],
        "claim_scope": "local_qualification",
        "claim_boundary": (
            "This qualifies exact accepted local source and an optional declared artifact. "
            "It performs no install, tag, push, or publication."
        ),
    }


def _compact_operation(operation: str, argv: list[str]) -> int:
    try:
        values = _compact_parse(operation, argv)
        root: Path = values["root"]
        request: Mapping[str, Any] = {}
        request_raw = b""
        request_path = values.get("request")
        if request_path:
            candidate = Path(str(request_path))
            request_file = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
            try:
                request_file.relative_to(root)
            except ValueError as exc:
                raise ValueError("request path must remain under --root") from exc
            request_raw = request_file.read_bytes()
            request = _strict_json_loads(request_raw.decode("utf-8"))
            if not isinstance(request, Mapping):
                raise ValueError("request JSON must be an object")
        if operation == "read":
            payload = _read_operation(root, request, values)
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0 if payload["status"] == "pass" else 1
        if operation == "change":
            payload = _change_operation(
                root,
                request,
                values,
                request_sha256=hashlib.sha256(request_raw).hexdigest(),
            )
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0 if payload["status"] == "pass" else 1
        if operation == "release":
            payload = _release_operation(root, request, values)
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0 if payload["status"] == "pass" else 1
        payload = {
            "artifact_type": "flowguard_compact_operation",
            "operation": operation,
            "status": "pass",
            "decision": "pass",
            "producer_count": 0,
            "root": str(root),
            "request": request,
            "claim_boundary": (
                "FlowGuard lifecycle admission is limited to the explicit operation. "
                "This command does not claim installation, remote GitHub state, or target-domain closure."
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "artifact_type": "flowguard_compact_operation",
                    "operation": operation,
                    "status": "blocked",
                    "decision": "block",
                    "producer_count": 0,
                    "error": str(exc),
                    "claim_boundary": "No producer was started by this rejected request.",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args or raw_args[0] in {"-h", "--help", "help"}:
        return _compact_help()
    if raw_args[0] in _COMPACT_OPERATIONS:
        return _compact_operation(raw_args[0], raw_args[1:])
    print(
        json.dumps(
            {
                "artifact_type": "flowguard_compact_operation",
                "status": "blocked",
                "decision": "block",
                "producer_count": 0,
                "error": f"unknown operation: {raw_args[0]}",
                "allowed_operations": list(_COMPACT_OPERATIONS),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
