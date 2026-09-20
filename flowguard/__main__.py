"""Thin command wrappers for flowguard's existing Python APIs."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import mmap
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
        "activation_receipt_id",
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
        activation_receipt_id=str(payload["activation_receipt_id"]),
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


def _run_route_reference_command(args: argparse.Namespace) -> int:
    """Return one public FlowGuard route capsule without loading every route."""

    from .self_maintenance import PUBLIC_ROUTE_ADMISSION, default_flowguard_route_profiles

    requested = str(args.route or "").strip()
    profiles = {
        profile.route_id: profile
        for profile in default_flowguard_route_profiles()
        if profile.route_id in PUBLIC_ROUTE_ADMISSION
    }
    aliases = {
        alias: route_id
        for route_id, profile in profiles.items()
        for alias in (profile.route_id, profile.skill_name)
        if alias
    }
    route_id = aliases.get(requested, "")
    profile = profiles.get(route_id)
    payload: dict[str, object] = {
        "schema_version": "flowguard.route_reference.v1",
        "command": "route-reference",
        "requested_route": requested,
        "status": "pass" if profile is not None else "blocked",
        "ok": profile is not None,
        "route": profile.to_dict() if profile is not None else {},
        "claim_boundary": (
            "This route-reference result returns one current public FlowGuard route capsule and "
            "its lazy reference edges. It does not execute the route, read the selected fragment, "
            "load the complete model, or prove native closure, installation, publication, or future AI behavior."
        ),
        "checks": [
            {
                "check_id": "route-reference:single-capsule",
                "status": "pass" if profile is not None else "block",
                "summary": "Returned one current public route capsule without returning the complete route registry.",
            },
            {
                "check_id": "route-reference:no-mutation",
                "status": "pass",
                "summary": "Read only the in-process public route registry.",
            },
        ],
        "blockers": []
        if profile is not None
        else ["route-reference route is not a current public FlowGuard route"],
        "skipped": [
            "The selected route fragment was not read or executed; load only the returned reference_edges after selection."
        ],
    }
    _emit_payload(payload, as_json=args.json)
    return 0 if profile is not None else 1


def _project_layout_summary(payload: Mapping[str, object], *, full_report_path: str = "") -> dict[str, object]:
    observed_entries = payload.get("observed_entries")
    findings = payload.get("findings")
    changed_paths = payload.get("changed_paths")
    observed = list(observed_entries) if isinstance(observed_entries, list) else []
    finding_rows = list(findings) if isinstance(findings, list) else []
    changed = list(changed_paths) if isinstance(changed_paths, list) else []
    compact_findings = [
        {
            "code": row.get("code", ""),
            "severity": row.get("severity", ""),
            "path": row.get("path", ""),
            "message": str(row.get("message", ""))[:240],
            "recommendation": str(row.get("recommendation", ""))[:240],
        }
        for row in finding_rows[:10]
        if isinstance(row, Mapping)
    ]
    return {
        "schema_version": "flowguard.project_layout_summary.v1",
        "source_schema_version": str(payload.get("schema") or payload.get("schema_version") or ""),
        "artifact_type": "flowguard_project_layout_summary",
        "status": payload.get("status", "blocked"),
        "ok": bool(payload.get("ok", False)),
        "profile": payload.get("profile", ""),
        "layout_version": payload.get("layout_version"),
        "checks_run": list(payload.get("checks_run", ()))[:10],
        "checks_not_run": list(payload.get("checks_not_run", ()))[:10],
        "changed_path_count": len(changed),
        "observed_entry_count": len(observed),
        "observed_entries_omitted_count": max(0, len(observed) - 10),
        "finding_count": len(finding_rows),
        "findings": compact_findings,
        "findings_omitted_count": max(0, len(finding_rows) - len(compact_findings)),
        "claim_boundary": str(payload.get("claim_boundary", "")),
        "full_report_path": full_report_path,
        "full_report_hint": "Use --full-output --output <path> to save the complete layout report." if not full_report_path else "",
    }


def _emit_project_layout_result(
    payload: Mapping[str, object],
    args: argparse.Namespace,
    *,
    text: str,
) -> None:
    if getattr(args, "full_output", False) and not getattr(args, "output", None):
        raise SystemExit("--full-output requires --output PATH")
    full_report_path = ""
    if getattr(args, "output", None):
        output_path = Path(str(args.output)).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        full_report_path = str(output_path)
    if args.json:
        print(
            json.dumps(
                _project_layout_summary(payload, full_report_path=full_report_path),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    else:
        print(text)
        if full_report_path:
            print(f"full_output: {full_report_path}")


def _run_model_system_command(args: argparse.Namespace) -> int:
    from .model_authority import (
        AcceptedBoundaryContract,
        ModelRevisionSet,
        ModelRollbackContract,
        load_model_system_snapshot,
    )
    from .model_authority_store import (
        activate_model_revision_set,
        audit_model_authority,
        bootstrap_model_authority,
        load_observed_model_system,
        rebuild_model_authority,
        rollback_observed_model_system,
    )
    from .model_system_inventory import (
        build_manifest_model_system_snapshot,
    )

    try:
        if args.model_system_action == "audit":
            report = audit_model_authority(args.root)
            _emit_payload(report.to_dict(), as_json=args.json)
            return 0 if report.ok else 1
        if args.model_system_action == "plan":
            from .model_revision_plan import preview_current_model_revision

            report = preview_current_model_revision(
                args.root,
                snapshot_id=args.snapshot_id,
            )
            payload = (
                report.to_compact_dict()
                if args.compact
                else report.to_dict()
            )
            _emit_payload(payload, as_json=args.json)
            return 0 if report.ok else 1
        if args.model_system_action == "bootstrap":
            if args.initial_input:
                if not args.staging_root or not args.expected_absent_manifest_fingerprint:
                    raise ValueError(
                        "initial current bootstrap requires --staging-root and "
                        "--expected-absent-manifest-fingerprint"
                    )
                return _run_initial_current_model_authority(args)
            raise ValueError(
                "model-system-bootstrap no longer publishes generation one; "
                "provide --initial-input for a bounded current transaction"
            )
        if args.model_system_action == "rebuild":
            report = rebuild_model_authority(
                args.root,
                staging_root=args.staging_root,
                expected_old_section_fingerprint=(
                    args.expected_old_section_fingerprint or ""
                ),
                expected_absent_manifest_fingerprint=(
                    args.expected_absent_manifest_fingerprint or ""
                ),
                target_system_id=args.target_system_id,
                target_generation=args.target_generation,
            )
            _emit_payload(report, as_json=args.json)
            return 0
        if args.model_system_action == "owner-evidence":
            from .model_revision_owner_evidence import (
                produce_model_revision_owner_evidence,
            )
            from .model_authority import AcceptedBoundaryContract

            owner_boundary_contract = None
            if args.boundary_contract:
                owner_boundary_contract = AcceptedBoundaryContract.from_dict(
                    _read_json_object(args.boundary_contract)
                )
            report = produce_model_revision_owner_evidence(
                args.root,
                model_parent_receipt=args.model_parent_receipt,
                snapshot_id=args.snapshot_id,
                receipt_root=args.receipt_root or None,
                output_path=args.output,
                accepted_boundary_contract=owner_boundary_contract,
            )
            _emit_payload(report.to_dict(), as_json=args.json)
            return 0
        if args.model_system_action in {"build", "intent-bootstrap"}:
            from .model_intent import (
                ModelIntentContribution,
                ModelIntentDisposition,
            )
            from .model_intent_authority import (
                EffectiveIntentTransition,
                LegacyIntentBootstrapDisposition,
                build_current_intent_bootstrap_receipt,
            )
            from .model_revision_builder import (
                build_current_model_revision,
                load_revision_removal_dispositions,
            )
            from .model_path_quality import PathQualityResult, PathQualitySubject

            dispositions = (
                load_revision_removal_dispositions(args.removal_dispositions)
                if args.removal_dispositions
                else ()
            )
            intent_contributions = ()
            intent_dispositions = ()
            effective_intent_transitions = ()
            if args.intent_inventory:
                intent_payload = _read_json_object(args.intent_inventory)
                if set(intent_payload) != {
                    "contributions",
                    "dispositions",
                    "effective_intent_transitions",
                }:
                    raise ValueError(
                        "intent inventory must contain exactly contributions, "
                        "dispositions, and effective_intent_transitions"
                    )
                intent_contributions = tuple(
                    ModelIntentContribution.from_dict(item)
                    for item in intent_payload["contributions"]
                )
                intent_dispositions = tuple(
                    ModelIntentDisposition.from_dict(item)
                    for item in intent_payload["dispositions"]
                )
                effective_intent_transitions = tuple(
                    EffectiveIntentTransition.from_dict(item)
                    for item in intent_payload[
                        "effective_intent_transitions"
                    ]
                )
            current_design_intent_contributions = ()
            effective_intent_bootstrap_receipt = None
            if args.model_system_action == "intent-bootstrap":
                bootstrap_payload = _read_json_object(
                    args.intent_bootstrap_input
                )
                expected_bootstrap_fields = {
                    "schema",
                    "receipt_id",
                    "rationale",
                    "claim_boundary",
                    "current_design_contributions",
                    "legacy_entry_dispositions",
                }
                if set(bootstrap_payload) != expected_bootstrap_fields:
                    missing = tuple(
                        sorted(expected_bootstrap_fields - set(bootstrap_payload))
                    )
                    unknown = tuple(
                        sorted(set(bootstrap_payload) - expected_bootstrap_fields)
                    )
                    raise ValueError(
                        "intent bootstrap input must contain exactly the current "
                        f"aggregate fields; missing={missing}; unknown={unknown}"
                    )
                if (
                    bootstrap_payload["schema"]
                    != MODEL_REVISION_INTENT_BOOTSTRAP_INPUT_SCHEMA
                ):
                    raise ValueError(
                        "intent bootstrap input schema must be "
                        f"{MODEL_REVISION_INTENT_BOOTSTRAP_INPUT_SCHEMA}"
                    )
                current_design_intent_contributions = tuple(
                    ModelIntentContribution.from_dict(item)
                    for item in bootstrap_payload[
                        "current_design_contributions"
                    ]
                )
                legacy_entry_dispositions = tuple(
                    LegacyIntentBootstrapDisposition.from_dict(item)
                    for item in bootstrap_payload[
                        "legacy_entry_dispositions"
                    ]
                )
                _bootstrap_head, bootstrap_base = load_observed_model_system(
                    args.root
                )
                bootstrap_boundary_contract = None
                if args.boundary_contract:
                    bootstrap_boundary_contract = AcceptedBoundaryContract.from_dict(
                        _read_json_object(args.boundary_contract)
                    )
                bootstrap_candidate = build_manifest_model_system_snapshot(
                    args.root,
                    snapshot_id=args.snapshot_id,
                    system_id=bootstrap_base.system_id,
                    subject_lane=bootstrap_base.subject_lane,
                    lifecycle=bootstrap_base.lifecycle,
                    accepted_boundary_contract=bootstrap_boundary_contract,
                )
                effective_intent_bootstrap_receipt = (
                    build_current_intent_bootstrap_receipt(
                        args.root,
                        receipt_id=str(bootstrap_payload["receipt_id"]),
                        candidate_snapshot=bootstrap_candidate,
                        current_design_contributions=(
                            current_design_intent_contributions
                        ),
                        rationale=str(bootstrap_payload["rationale"]),
                        legacy_entry_dispositions=(
                            legacy_entry_dispositions
                        ),
                        claim_boundary=str(
                            bootstrap_payload["claim_boundary"]
                        ),
                    )
                )
            no_intent_evidence = ()
            if args.no_declared_intent_evidence_fingerprints:
                evidence_payload = _strict_json_loads(
                    args.no_declared_intent_evidence_fingerprints
                )
                if not isinstance(evidence_payload, dict):
                    raise ValueError(
                        "no-declared-intent evidence fingerprints must be a JSON object"
                    )
                no_intent_evidence = tuple(
                    (str(role), str(fingerprint))
                    for role, fingerprint in evidence_payload.items()
                )
            native_owner_contracts = ()
            native_owner_receipts = ()
            native_owner_verification_results = ()
            if args.native_owner_evidence:
                (
                    native_owner_contracts,
                    native_owner_receipts,
                    native_owner_verification_results,
                ) = _load_native_owner_evidence(args.native_owner_evidence)
            path_quality_subjects = ()
            path_quality_results = ()
            if args.path_quality_material:
                path_quality_payload = _read_json_object(args.path_quality_material)
                if set(path_quality_payload) != {"subjects", "results"}:
                    raise ValueError(
                        "path-quality material must contain exactly subjects and results"
                    )
                path_quality_subjects = tuple(
                    PathQualitySubject.from_dict(item)
                    for item in path_quality_payload["subjects"]
                )
                path_quality_results = tuple(
                    PathQualityResult.from_dict(item)
                    for item in path_quality_payload["results"]
                )
            accepted_boundary_contract = None
            if args.boundary_contract:
                accepted_boundary_contract = AcceptedBoundaryContract.from_dict(
                    _read_json_object(args.boundary_contract)
                )
            report = build_current_model_revision(
                args.root,
                model_parent_receipt=args.model_parent_receipt,
                revision_set_id=args.revision_set_id,
                task_id=args.task_id,
                snapshot_id=args.snapshot_id,
                receipt_root=args.receipt_root or None,
                output_root=args.output_root or None,
                removal_dispositions=dispositions,
                intent_contributions=intent_contributions,
                intent_dispositions=intent_dispositions,
                effective_intent_transitions=effective_intent_transitions,
                current_design_intent_contributions=(
                    current_design_intent_contributions
                ),
                effective_intent_bootstrap_receipt=(
                    effective_intent_bootstrap_receipt
                ),
                native_owner_contracts=native_owner_contracts,
                native_owner_receipts=native_owner_receipts,
                native_owner_verification_results=(
                    native_owner_verification_results
                ),
                accepted_boundary_contract=accepted_boundary_contract,
                path_quality_subjects=path_quality_subjects,
                path_quality_results=path_quality_results,
                no_declared_intent_rationale_id=(
                    args.no_declared_intent_rationale_id
                ),
                no_declared_intent_evidence_fingerprints=no_intent_evidence,
                no_declared_intent_rationale=(
                    args.no_declared_intent_rationale
                ),
                decision_reason=args.decision_reason,
            )
            _emit_payload(report.to_dict(), as_json=args.json)
            return 0
        if args.model_system_action == "activate":
            unresolved_paths = tuple(
                value
                for value in (args.candidate_snapshot, args.revision_set)
                if "<" in str(value) or ">" in str(value)
            )
            if unresolved_paths:
                raise ValueError(
                    "model-revision-activate requires real build outputs; "
                    "unresolved angle-bracket path placeholders remain: "
                    + ", ".join(unresolved_paths)
                )
            candidate = load_model_system_snapshot(args.candidate_snapshot)
            revision = ModelRevisionSet.from_dict(
                _read_json_object(args.revision_set)
            )
            head, receipt = activate_model_revision_set(
                args.root,
                candidate,
                revision,
                receipt_id=args.receipt_id,
            )
            _emit_payload(
                {
                    "status": "pass",
                    "head": head.to_dict(),
                    "receipt": receipt.to_dict(),
                },
                as_json=args.json,
            )
            return 0
        contract = ModelRollbackContract.from_dict(
            _read_json_object(args.contract)
        )
        rollback_candidate = load_model_system_snapshot(
            args.candidate_snapshot
        )
        reverse_revision = ModelRevisionSet.from_dict(
            _read_json_object(args.reverse_revision_set)
        )
        head, receipt = rollback_observed_model_system(
            args.root,
            contract,
            rollback_candidate,
            reverse_revision,
            completed_evidence_fingerprints=(
                args.completed_evidence_fingerprint
            ),
            requested_result=args.result,
            receipt_id=args.receipt_id,
            reason=args.reason,
        )
        _emit_payload(
            {
                "status": "pass",
                "head": head.to_dict(),
                "receipt": receipt.to_dict(),
            },
            as_json=args.json,
        )
        return 0
    except (OSError, ValueError, RuntimeError, SystemExit) as exc:
        _emit_payload(
            {"status": "blocked", "error": str(exc)},
            as_json=args.json,
        )
        return 1


def _run_model_maturation_review_command(args: argparse.Namespace) -> int:
    from .model_maturation import ModelMaturationPlan, review_model_maturation_loop, review_model_maturation_session

    try:
        plans = [ModelMaturationPlan.from_dict(_read_json_object(path)) for path in args.plan]
        if not plans:
            raise ValueError("at least one --plan JSON artifact is required")
        if len(plans) == 1:
            report = review_model_maturation_loop(plans[0])
            payload = report.to_dict()
            ok = report.ok
        else:
            session = review_model_maturation_session(plans, session_id=args.session_id)
            payload = session.to_dict()
            ok = session.closed
        _emit_payload(payload, as_json=args.json)
        return 0 if ok else 1
    except (OSError, ValueError, TypeError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_task_coverage_demand_command(args: argparse.Namespace) -> int:
    from .task_coverage_demand import TaskFacts, compile_task_coverage_demand

    try:
        facts = TaskFacts(**_read_json_object(args.facts))
        demand = compile_task_coverage_demand(facts)
        _emit_payload(
            {**demand.to_dict(), "fingerprint": demand.fingerprint},
            as_json=args.json,
        )
        return 0
    except (OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_model_maturation_receipt_verify_command(args: argparse.Namespace) -> int:
    from .evidence_receipts import ReceiptVerificationContext
    from .model_maturation_receipt import (
        ModelMaturationReceiptRef,
        ModelMaturationVerificationContext,
        verify_model_maturation_receipt,
    )

    try:
        payload = _read_json_object(args.context)
        receipt_ref = ModelMaturationReceiptRef(**dict(payload["receipt_ref"]))
        raw_model_context = dict(payload["verification_context"])
        raw_receipt_context = dict(raw_model_context.pop("receipt_context"))
        raw_snapshots = raw_receipt_context.get("input_snapshots", {})
        if isinstance(raw_snapshots, list):
            raw_receipt_context["input_snapshots"] = {
                str(item["artifact_id"]): item for item in raw_snapshots
            }
        receipt_context = ReceiptVerificationContext(**raw_receipt_context)
        context = ModelMaturationVerificationContext(
            receipt_context=receipt_context,
            **raw_model_context,
        )
        result = verify_model_maturation_receipt(
            receipt_ref,
            context,
            args.root,
            output_directory=args.receipt_root or None,
        )
        _emit_payload(result.to_dict(), as_json=args.json)
        return 0 if result.verified_maturation is not None else 1
    except (KeyError, OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _run_model_understanding_status_command(args: argparse.Namespace) -> int:
    from .understanding_readiness import (
        UnderstandingReadinessInput,
        compose_understanding_status,
    )

    def optional_artifact(path: str) -> dict[str, object]:
        return _read_json_object(path) if path else {}

    try:
        status = compose_understanding_status(
            UnderstandingReadinessInput(
                task_facts=optional_artifact(args.task_facts),
                model_identity=optional_artifact(args.model_identity),
                coverage_demand=optional_artifact(args.coverage_demand),
                owner_resolutions=tuple(
                    _read_json_object(path) for path in args.owner_resolution
                ),
                maturation_report=optional_artifact(args.maturation_report),
                receipt_verification=optional_artifact(args.receipt_verification),
                implementation_admission=optional_artifact(
                    args.implementation_admission
                ),
                blueprint_summary=optional_artifact(args.blueprint_summary),
                blueprint_scope_required=args.blueprint_scope_required,
                user_choice=args.user_choice,
                flowguard_claim_requested=args.flowguard_claim_requested,
            )
        )
        _emit_payload(
            {**status.to_dict(), "fingerprint": status.fingerprint},
            as_json=args.json,
        )
        return 0 if status.ok else 1
    except (OSError, TypeError, ValueError) as exc:
        _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
        return 1


def _add_model_system_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    audit = subparsers.add_parser(
        "model-system-audit",
        help="Audit the sole observed model-system authority.",
    )
    audit.add_argument("--root", default=".")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(
        handler=_run_model_system_command,
        model_system_action="audit",
    )

    revision_plan = subparsers.add_parser(
        "model-revision-plan",
        help=(
            "Preview the exact base-to-live-candidate revision, affected closure, "
            "and required native owner routes without writing or running models."
        ),
    )
    revision_plan.add_argument("--root", default=".")
    revision_plan.add_argument("--snapshot-id", required=True)
    revision_plan.add_argument(
        "--compact",
        action="store_true",
        help=(
            "Emit the same decision and identity fingerprints without the "
            "full entity diff, affected-id, edge, or owner-binding rows."
        ),
    )
    revision_plan.add_argument("--json", action="store_true")
    revision_plan.set_defaults(
        handler=_run_model_system_command,
        model_system_action="plan",
    )

    bootstrap = subparsers.add_parser(
        "model-system-bootstrap",
        help="Establish the first observed model-system authority.",
    )
    bootstrap.add_argument("--root", default=".")
    bootstrap.add_argument(
        "--snapshot",
        default="",
        help="Existing snapshot JSON; otherwise build from current owners.",
    )
    bootstrap.add_argument(
        "--snapshot-id",
        default="snapshot:observed-bootstrap",
    )
    bootstrap.add_argument(
        "--evidence-fingerprint",
        default="",
        help="Bootstrap evidence fingerprint (required by initial-input workflow).",
    )
    bootstrap.add_argument(
        "--staging-root",
        default="",
        help="Isolated staging root used by the first-current transaction.",
    )
    bootstrap.add_argument(
        "--initial-input",
        default="",
        help=(
            "Strict flowguard.model_initial_current_input.v1 aggregate.  When "
            "present, bootstrap completes a generation-two current transaction."
        ),
    )
    bootstrap.add_argument(
        "--receipt-root",
        default="",
        help="Optional staging receipt root referenced by initial-input.",
    )
    bootstrap.add_argument(
        "--expected-absent-manifest-fingerprint",
        default="",
        help="Full target manifest fingerprint required before first publication.",
    )
    bootstrap.add_argument("--json", action="store_true")
    bootstrap.set_defaults(
        handler=_run_model_system_command,
        model_system_action="bootstrap",
    )

    rebuild = subparsers.add_parser(
        "model-authority-rebuild",
        help=(
            "Replace an existing authority from an isolated current-only "
            "generation-one to accepted-v5 staging package."
        ),
    )
    rebuild.add_argument("--root", default=".")
    rebuild.add_argument("--staging-root", required=True)
    rebuild_precondition = rebuild.add_mutually_exclusive_group(required=True)
    rebuild_precondition.add_argument(
        "--expected-old-section-fingerprint",
        default="",
    )
    rebuild_precondition.add_argument(
        "--expected-absent-manifest-fingerprint",
        default="",
        help=(
            "Full project-manifest fingerprint required when the target has no "
            "model_authority section yet."
        ),
    )
    rebuild.add_argument("--target-system-id", default="")
    rebuild.add_argument("--target-generation", type=int, default=2)
    rebuild.add_argument("--json", action="store_true")
    rebuild.set_defaults(
        handler=_run_model_system_command,
        model_system_action="rebuild",
    )

    owner_evidence = subparsers.add_parser(
        "model-revision-owner-evidence",
        help=(
            "Recompose one exact-current full model-regression parent into "
            "distinct current native-owner receipts; never runs regressions "
            "or activates authority."
        ),
    )
    owner_evidence.add_argument("--root", default=".")
    owner_evidence.add_argument("--model-parent-receipt", required=True)
    owner_evidence.add_argument("--snapshot-id", required=True)
    owner_evidence.add_argument(
        "--receipt-root",
        default="",
        help="Model owner receipt store; defaults to the project current store.",
    )
    owner_evidence.add_argument(
        "--boundary-contract",
        default="",
        help=(
            "Content-addressed v2 boundary contract JSON used to bind the "
            "candidate snapshot during owner-evidence composition."
        ),
    )
    owner_evidence.add_argument(
        "--output",
        required=True,
        help=(
            "New immutable strict contracts/receipts/verification_results JSON "
            "bundle for model-revision-build."
        ),
    )
    owner_evidence.add_argument("--json", action="store_true")
    owner_evidence.set_defaults(
        handler=_run_model_system_command,
        model_system_action="owner-evidence",
    )

    def add_revision_build_arguments(
        parser: argparse.ArgumentParser,
    ) -> None:
        parser.add_argument("--root", default=".")
        parser.add_argument("--model-parent-receipt", required=True)
        parser.add_argument("--revision-set-id", required=True)
        parser.add_argument("--task-id", required=True)
        parser.add_argument("--snapshot-id", required=True)
        parser.add_argument(
            "--receipt-root",
            default="",
            help=(
                "Model owner receipt store; defaults to the project current store."
            ),
        )
        parser.add_argument(
            "--output-root",
            default="",
        help="Model authority output root; defaults to .flowguard/models/authority.",
        )
        parser.add_argument(
            "--removal-dispositions",
            default="",
            help="Current-schema JSON array covering every removed governed id.",
        )
        parser.add_argument(
            "--intent-inventory",
            default="",
            help=(
                "Strict revision-local contributions, dispositions, and "
                "effective_intent_transitions JSON. It is exclusive with "
                "the no-declared-intent rationale fields."
            ),
        )
        parser.add_argument(
            "--native-owner-evidence",
            default="",
            help=(
                "Strict JSON object containing contracts, receipts, and "
                "verification_results for exact affected native owners. "
                "When omitted, the revision stays incomplete."
            ),
        )
        parser.add_argument(
            "--path-quality-material",
            default="",
            help=(
                "Strict JSON object containing current typed subjects and compact "
                "results for every added or replaced model. When omitted, a "
                "behavior-changing revision stays incomplete."
            ),
        )
        parser.add_argument(
            "--boundary-contract",
            default="",
            help=(
                "Content-addressed v2 boundary contract JSON. Its semantic "
                "fingerprint is pointer-free; authority binds it during the "
                "candidate/revision transition."
            ),
        )
        parser.add_argument("--no-declared-intent-rationale-id", default="")
        parser.add_argument(
            "--no-declared-intent-evidence-fingerprints",
            default="",
            help="JSON object mapping evidence roles to exact sha256 fingerprints.",
        )
        parser.add_argument("--no-declared-intent-rationale", default="")
        parser.add_argument(
            "--decision-reason",
            default=(
                "The exact-current parent receipt composes exact-current "
                "terminal-pass leaf receipts supplied by every affected native owner."
            ),
        )
        parser.add_argument("--json", action="store_true")

    build = subparsers.add_parser(
        "model-revision-build",
        help=(
            "Build one current-format revision from an exact-current parent "
            "receipt and optional exact leaf-owner evidence without activating it."
        ),
    )
    add_revision_build_arguments(build)
    build.set_defaults(
        handler=_run_model_system_command,
        model_system_action="build",
    )

    intent_bootstrap = subparsers.add_parser(
        "model-revision-intent-bootstrap",
        help=(
            "Build the one explicit current-intent migration revision from one "
            "strict aggregate design-and-legacy-disposition input; never activate it."
        ),
    )
    add_revision_build_arguments(intent_bootstrap)
    intent_bootstrap.add_argument(
        "--intent-bootstrap-input",
        required=True,
        help=(
            "Strict aggregate JSON with schema, receipt metadata, every current "
            "owner design contribution, and every exact legacy disposition."
        ),
    )
    intent_bootstrap.set_defaults(
        handler=_run_model_system_command,
        model_system_action="intent-bootstrap",
    )

    activate = subparsers.add_parser(
        "model-revision-activate",
        help="Activate one accepted whole-system revision set.",
    )
    activate.add_argument("--root", default=".")
    activate.add_argument("--candidate-snapshot", required=True)
    activate.add_argument("--revision-set", required=True)
    activate.add_argument("--receipt-id", required=True)
    activate.add_argument("--json", action="store_true")
    activate.set_defaults(
        handler=_run_model_system_command,
        model_system_action="activate",
    )

    rollback = subparsers.add_parser(
        "model-revision-rollback",
        help="Restore or compensate real effects before rewinding authority.",
    )
    rollback.add_argument("--root", default=".")
    rollback.add_argument("--contract", required=True)
    rollback.add_argument("--candidate-snapshot", required=True)
    rollback.add_argument("--reverse-revision-set", required=True)
    rollback.add_argument(
        "--completed-evidence-fingerprint",
        action="append",
        default=[],
    )
    rollback.add_argument(
        "--result",
        choices=("exact", "compensated", "forward_repair"),
        required=True,
    )
    rollback.add_argument("--receipt-id", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--json", action="store_true")
    rollback.set_defaults(
        handler=_run_model_system_command,
        model_system_action="rollback",
    )


def _add_model_maturation_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "model-maturation-review",
        help="Review one or more task-local model maturation iterations.",
    )
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        required=True,
        help="Current-schema model maturation plan JSON; repeat for candidate iterations.",
    )
    parser.add_argument("--session-id", default="")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.set_defaults(handler=_run_model_maturation_review_command)

    demand = subparsers.add_parser(
        "task-coverage-demand",
        help="Derive the minimum model coverage from frozen task facts.",
    )
    demand.add_argument("--facts", required=True, help="Current TaskFacts JSON artifact.")
    demand.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    demand.set_defaults(handler=_run_task_coverage_demand_command)

    receipt = subparsers.add_parser(
        "model-maturation-receipt-verify",
        help="Independently verify one canonical model-maturation receipt.",
    )
    receipt.add_argument("--context", required=True, help="Receipt reference and verification context JSON.")
    receipt.add_argument("--root", default=".", help="Repository root containing the receipt store.")
    receipt.add_argument("--receipt-root", default="", help="Optional explicit receipt output directory.")
    receipt.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    receipt.set_defaults(handler=_run_model_maturation_receipt_verify_command)

    status = subparsers.add_parser(
        "model-understanding-status",
        help=(
            "Read already-produced understanding artifacts without running "
            "owners or publishing evidence."
        ),
    )
    status.add_argument("--task-facts", default="", help="Exact TaskFacts JSON artifact.")
    status.add_argument("--model-identity", default="", help="Exact current model identity JSON artifact.")
    status.add_argument("--coverage-demand", default="", help="Exact TaskCoverageDemand JSON artifact.")
    status.add_argument(
        "--owner-resolution",
        action="append",
        default=[],
        help="Exact owner-resolution JSON artifact; repeat once per demanded owner.",
    )
    status.add_argument("--maturation-report", default="", help="Exact maturation report JSON artifact.")
    status.add_argument(
        "--receipt-verification",
        default="",
        help="Existing independent maturation receipt-verification JSON artifact.",
    )
    status.add_argument(
        "--implementation-admission",
        default="",
        help="Existing implementation-admission JSON artifact.",
    )
    status.add_argument(
        "--blueprint-summary",
        default="",
        help="Existing compact target-system blueprint summary JSON artifact.",
    )
    status.add_argument(
        "--blueprint-scope-required",
        choices=("none", "affected", "whole"),
        default="none",
        help="Require no blueprint, an affected summary, or a whole-target summary.",
    )
    status.add_argument(
        "--user-choice",
        choices=("model_first", "direct_user_choice", "no_code"),
        default="model_first",
    )
    status.add_argument(
        "--no-flowguard-claim",
        action="store_false",
        dest="flowguard_claim_requested",
        help="Report a lightweight/direct path without claiming FlowGuard readiness.",
    )
    status.set_defaults(flowguard_claim_requested=True)
    status.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    status.set_defaults(handler=_run_model_understanding_status_command)


def _run_adoption_template() -> int:
    from .templates import ADOPTION_LOG_TEMPLATE

    print(ADOPTION_LOG_TEMPLATE)
    return 0


def _run_file_template(
    args: argparse.Namespace,
    *,
    template_name: str,
    files: tuple[object, ...],
) -> int:
    from .templates import write_template_files

    if args.output:
        written = write_template_files(args.output, files, overwrite=args.force)
        print(
            json.dumps(
                {
                    "artifact_type": "flowguard_template_write",
                    "template": template_name,
                    "files": [str(path) for path in written],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "artifact_type": "flowguard_template",
                "template": template_name,
                "files": [
                    {"path": file.path, "content": file.content}
                    for file in files
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


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


def _run_file_template_command(args: argparse.Namespace, command: FileTemplateCommand) -> int:
    from . import templates

    factory = getattr(templates, command.factory_name)
    return _run_file_template(args, template_name=command.template_name, files=factory())


def _run_adoption_entry(args: argparse.Namespace) -> int:
    from .adoption import (
        AdoptionCommandResult,
        append_jsonl,
        append_markdown_log,
        make_adoption_log_entry,
    )

    failed_commands = tuple(args.failed_command or ())
    successful_commands = tuple(args.command or ())
    commands = tuple(
        AdoptionCommandResult(command, True)
        for command in successful_commands
    ) + tuple(
        AdoptionCommandResult(command, False)
        for command in failed_commands
    )
    root = Path(args.root)
    status = args.status
    if status == "auto" and args.default_status != "auto":
        status = args.default_status
    entry = make_adoption_log_entry(
        task_id=args.task_id,
        project=args.project or root.resolve().name,
        task_summary=args.task_summary,
        trigger_reason=args.trigger_reason,
        status=status,
        skill_decision=args.skill_decision,
        duration_seconds=args.duration_seconds,
        model_files=tuple(args.model_file or ()),
        commands=commands,
        findings=tuple(args.finding or ()),
        counterexamples=tuple(args.counterexample or ()),
        friction_points=tuple(args.friction_point or ()),
        skipped_steps=tuple(args.skipped_step or ()),
        risk_evidence_summary=tuple(args.risk_evidence or ()),
        next_actions=tuple(args.next_action or ()),
    )
    append_jsonl(root / ".flowguard" / "adoption_log.jsonl", entry)
    append_markdown_log(root / "docs" / "flowguard_adoption_log.md", entry)
    print(entry.to_json_text())
    return 0


def _run_project_adoption_command(args: argparse.Namespace) -> int:
    from .project_adoption import adopt_project, audit_project_adoption, upgrade_project

    if args.project_action == "audit":
        report = audit_project_adoption(args.root)
    elif args.project_action == "adopt":
        report = adopt_project(args.root)
    elif args.project_action == "upgrade":
        report = upgrade_project(
            args.root,
            records_only=args.records_only,
            dry_run=args.dry_run,
        )
    else:  # pragma: no cover
        raise ValueError(f"unknown project adoption action: {args.project_action}")
    if args.json:
        print(
            report.to_json_text()
            if args.full_output or args.project_action != "audit"
            else report.to_bounded_json_text()
        )
    else:
        print(report.format_text())
    return 0 if report.ok else 1


def _run_project_layout_audit_command(args: argparse.Namespace) -> int:
    """Run the mandatory read-only current .flowguard layout audit."""

    from .project_layout import audit_project_layout
    from .observation_metrics import InvocationMetrics
    from .execution_profiles import (
        OPERATION_KIND_READ_ONLY,
        select_execution_profile,
    )

    profile_decision = select_execution_profile(
        args.profile,
        operation_kind=getattr(
            args, "operation_kind", OPERATION_KIND_READ_ONLY
        ),
        route_kind=getattr(args, "route_kind", ""),
        modeling_mode=getattr(args, "modeling_mode", None),
        changed_paths=tuple(args.changed_path or ()),
        governed_writes_frozen=bool(getattr(args, "governed_writes_frozen", False)),
        projections_frozen=bool(getattr(args, "projections_frozen", False)),
        openspec_frozen=bool(getattr(args, "openspec_frozen", False)),
        owner_dag_frozen=bool(getattr(args, "owner_dag_frozen", False)),
        reverse_input_frozen=bool(getattr(args, "reverse_input_frozen", False)),
    )

    if args.profile == "affected" and not args.changed_path:
        payload = {
            "artifact_type": "flowguard_currentness_profile_report",
            "profile": args.profile,
            "status": "blocked",
            "ok": False,
            "checks_run": [],
            "checks_not_run": ["layout_shape", "affected_owner_mapping"],
            "claim_boundary": (
                "affected profile requires an explicit changed-path set; it never "
                "falls back to full validation"
            ),
            "findings": [
                {
                    "code": "affected_changed_paths_missing",
                    "severity": "blocked",
                    "message": "The affected profile requires one or more exact changed paths.",
                }
            ],
        }
        payload.update(profile_decision.to_dict())
        _emit_project_layout_result(
            payload,
            args,
            text="FlowGuard currentness: blocked\nreason: affected profile requires --changed-path",
        )
        return 1

    metrics = InvocationMetrics()
    report = audit_project_layout(args.root, metrics=metrics)
    if args.profile == "light":
        checks_run = ["layout_shape", "adoption_pointer_shape"]
        checks_not_run = ["affected_owner_mapping", "semantic_model", "validation_receipts", "release_parity"]
    elif args.profile == "affected":
        checks_run = ["layout_shape", "changed_path_boundary"]
        checks_not_run = ["unmapped_owner_execution", "semantic_model", "validation_receipts", "release_parity"]
    else:
        checks_run = ["layout_shape"]
        checks_not_run = ["semantic_model", "validation_receipts", "release_parity"]
    payload = report.to_dict()
    payload.update(
        {
            "profile": args.profile,
            "changed_paths": list(args.changed_path or ()),
            "checks_run": checks_run,
            "checks_not_run": checks_not_run,
            "claim_boundary": (
                "This profile proves only the listed checks; not-run checks are not "
                "implicitly passed and no profile falls back to full validation."
            ),
        }
    )
    payload.update(profile_decision.to_dict())
    # Preserve the native layout audit result.  A profile can be admitted
    # (for example, a light read-only profile) while the observed layout is
    # still invalid; admission must never turn that native blocker into a
    # terminal ``pass`` projection.
    if not report.ok:
        payload["status"] = "blocked"
        payload["ok"] = False
    if not profile_decision.ok:
        payload["status"] = "blocked"
        payload["ok"] = False
        payload.setdefault("findings", []).extend(
            {
                "code": trigger,
                "severity": "blocked",
                "message": f"execution profile admission is blocked: {trigger}",
            }
            for trigger in profile_decision.escalation_triggers
        )
    _emit_project_layout_result(
        payload,
        args,
        text=(
            report.format_text()
            + f"\nprofile: {args.profile}"
            + "\nchecks not run: "
            + ", ".join(checks_not_run)
        ),
    )
    return 0 if bool(payload.get("ok")) else 1


def _run_artifact_upgrade_command(args: argparse.Namespace) -> int:
    from .artifact_upgrade import review_artifact_upgrades

    report = review_artifact_upgrades(args.root, paths=tuple(args.path or ()))
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_behavior_commitment_query_command(args: argparse.Namespace) -> int:
    from .behavior_commitment_lookup import (
        BehaviorLookupQuery,
        query_behavior_commitments_from_path,
    )

    root = Path(args.root).resolve()
    ledger_path = Path(args.ledger)
    if not ledger_path.is_absolute():
        ledger_path = root / ledger_path
    query = BehaviorLookupQuery(
        task_summary=args.task_summary or "",
        primary_plane=args.plane or "",
        canonical_terms=tuple(args.term or ()),
        changed_paths=tuple(args.path or ()),
        tool_ids=tuple(args.tool_id or ()),
        error_signatures=tuple(args.error_signature or ()),
        workflow_families=tuple(args.workflow_family or ()),
        top_k=args.top_k,
    )
    report = query_behavior_commitments_from_path(ledger_path, query)
    if args.json:
        payload = report.to_dict()
        payload["query"] = query.to_dict()
        payload["ledger_path"] = str(ledger_path)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_search_command(args: argparse.Namespace) -> int:
    from .risk_templates import search_risk_templates

    report = search_risk_templates(
        args.query or "",
        workflow_families=tuple(args.workflow_family or ()),
        protected_error_classes=tuple(args.protected_error_class or ()),
        include_public=not args.no_public,
        include_local=not args.no_local,
        local_root=args.local_root,
        max_results=args.max_results,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_harvest_command(args: argparse.Namespace) -> int:
    from .risk_templates import harvest_risk_template_candidate

    report = harvest_risk_template_candidate(
        template_id=args.template_id,
        title=args.title,
        summary=args.summary,
        workflow_families=tuple(args.workflow_family or ()),
        protected_error_classes=tuple(args.protected_error_class or ()),
        required_state=tuple(args.required_state or ()),
        required_side_effects=tuple(args.required_side_effect or ()),
        required_evidence=tuple(args.required_evidence or ()),
        known_bad_cases=tuple(args.known_bad_case or ()),
        known_bad_proofs=tuple(_parse_json_mapping_arg(value, "--known-bad-proof") for value in (args.known_bad_proof or ())),
        merge_keys=tuple(args.merge_key or ()),
        local_root=args.local_root,
        write=not args.no_write,
        overwrite=args.force,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else report.format_text())
    return 0 if report.ok else 1


def _run_risk_template_harvest_review_command(args: argparse.Namespace) -> int:
    from .risk_templates import TemplateHarvestReview, review_template_harvest_closure

    review = TemplateHarvestReview(
        disposition=args.disposition,
        written_template_ids=tuple(args.written_template_id or ()),
        merged_template_ids=tuple(args.merged_template_id or ()),
        linked_template_ids=tuple(args.linked_template_id or ()),
        not_harvestable_reason=args.not_harvestable_reason,
        local_root=args.local_root or "",
        findings=tuple(args.finding or ()),
    )
    report = review_template_harvest_closure(review)
    payload = {
        "review": review.to_dict(),
        "report": report.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else "\n".join((review.format_text(), report.format_text())))
    return 0 if report.ok else 1


def _run_work_context_command(args: argparse.Namespace) -> int:
    from .work_context import read_work_context, review_work_context

    declaration = (
        json.loads(args.declaration_json)
        if args.declaration_json
        else {}
    )
    review = review_work_context(
        read_work_context(
            args.root,
            args.work_id,
            adapter_id=args.adapter,
            declaration=declaration,
        )
    )
    print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    return 0 if review.ok else 1


def _portable_invalid_report(path: str, exc: Exception):
    from .portable_checker import PortableCheckReport, PortableFinding

    return PortableCheckReport(
        status="invalid",
        model_id=path,
        model_fingerprint="",
        findings=(PortableFinding("portable_artifact_invalid", str(exc)),),
    )


def _print_portable_report(report, *, as_json: bool) -> int:
    print(report.to_json_text() if as_json else report.format_text())
    return 0 if report.ok else 1


def _run_portable_model_validate_command(args: argparse.Namespace) -> int:
    from .portable_checker import PortableCheckReport
    from .portable_model import load_portable_model

    try:
        model = load_portable_model(args.model)
        report = PortableCheckReport(
            status="pass",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            checked_obligation_ids=("portable_model.structure.current",),
            claim_boundary="Validation proves the current portable artifact shape and identity only.",
        )
    except Exception as exc:
        report = _portable_invalid_report(args.model, exc)
    return _print_portable_report(report, as_json=args.json)


def _run_portable_model_check_command(args: argparse.Namespace) -> int:
    from .portable_checker import check_portable_model
    from .portable_model import load_portable_model

    try:
        report = check_portable_model(load_portable_model(args.model), max_states=args.max_states)
    except Exception as exc:
        report = _portable_invalid_report(args.model, exc)
    return _print_portable_report(report, as_json=args.json)


def _run_portable_model_refinement_command(args: argparse.Namespace) -> int:
    from .portable_checker import check_refinement
    from .portable_model import load_portable_model, load_refinement_binding

    try:
        report = check_refinement(
            load_portable_model(args.parent),
            load_portable_model(args.child),
            load_refinement_binding(args.binding),
        )
    except Exception as exc:
        report = _portable_invalid_report(args.child, exc)
    return _print_portable_report(report, as_json=args.json)


def _run_portable_system_check_command(args: argparse.Namespace) -> int:
    from .portable_model import load_portable_model
    from .portable_system import load_portable_system, load_system_composition_request
    from .system_composition import SystemCompositionReport, check_system_composition

    try:
        system = load_portable_system(args.system)
        request = load_system_composition_request(args.request)
        models = tuple(load_portable_model(path) for path in args.component)
        report = check_system_composition(system, request, models)
    except Exception as exc:
        report = SystemCompositionReport(
            status="invalid",
            system_id=args.system,
            system_fingerprint="",
            request_fingerprint="",
            stages={
                "component_local": "not_run",
                "contract_composition": "not_run",
                "affected_slice": "not_run",
                "system_composition": "not_run",
            },
            findings=(str(exc),),
        )
    print(report.to_json_text() if args.json else report.format_text())
    return {"pass": 0, "fail": 1, "blocked": 2, "invalid": 3}[report.status]


def _simulator_listing(root: Path) -> tuple[dict[str, object], int]:
    from .model_regressions import ModelRegressionManifest, audit_manifest

    manifest = ModelRegressionManifest.load(root)
    audit = audit_manifest(root, manifest)
    models = []
    for entry in sorted(manifest.entries, key=lambda item: item.model_id):
        model_exists = (root / entry.model_path).is_file()
        runner_exists = len(entry.runner) >= 2 and (root / entry.runner[1]).is_file()
        models.append(
            {
                "model_id": entry.model_id,
                "tier": entry.tier,
                "distribution_policy": entry.distribution_policy,
                "available": model_exists and runner_exists and not entry.excluded,
                "native_runner": list(entry.runner),
                "exclusion_reason": entry.exclusion_reason,
            }
        )
    payload: dict[str, object] = {
        "schema_version": "flowguard.model_simulator_listing.v1",
        "command": "flowguard-simulator",
        "status": "pass" if audit.ok else "blocked",
        "manifest_audit": audit.to_dict(),
        "models": models,
        "claim_boundary": "Listing proves manifest accounting and availability only; no model was executed.",
    }
    return payload, 0 if audit.ok else 2


def _run_simulator_command(args: argparse.Namespace) -> int:
    from .evidence_lifecycle import default_run_directory
    from .model_regressions import ModelRegressionManifest, audit_manifest, run_manifest_regressions, select_entries

    root = Path(args.root).resolve()
    try:
        if args.list:
            payload, exit_code = _simulator_listing(root)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "\n".join(
                [f"status: {payload['status']}", f"registered: {len(payload['models'])}"]
                + [f"model: {item['model_id']} tier={item['tier']} available={str(item['available']).lower()}" for item in payload["models"]]
            ))
            return exit_code
        if args.all and args.model:
            raise ValueError("--all and --model are mutually exclusive")
        if not args.all and not args.model:
            raise ValueError("execution requires at least one --model selector or explicit --all")
        manifest = ModelRegressionManifest.load(root)
        audit = audit_manifest(root, manifest)
        if not audit.ok:
            payload = {
                "schema_version": "flowguard.validation_result.v1",
                "command": "flowguard-simulator",
                "status": "blocked",
                "exit_code": 2,
                "blockers": list(audit.errors),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "status: blocked\n" + "\n".join(f"blocker: {item}" for item in audit.errors))
            return 2
        available_ids = tuple(
            entry.model_id
            for entry in manifest.entries
            if not entry.excluded
            and (root / entry.model_path).is_file()
            and len(entry.runner) >= 2
            and (root / entry.runner[1]).is_file()
        )
        unmatched = [pattern for pattern in args.model if not any(fnmatch.fnmatchcase(model_id, pattern) for model_id in available_ids)]
        if unmatched:
            raise ValueError("model selector matched no available registered model: " + ", ".join(unmatched))
        selected = select_entries(manifest, tier=args.tier, model_patterns=args.model)
        if not selected:
            raise ValueError("execution selected zero models at the requested tier")
        output_dir = Path(args.output_dir).resolve() if args.output_dir else default_run_directory(root, "simulator")
        report = run_manifest_regressions(
            root,
            tier=args.tier,
            model_patterns=args.model,
            jobs=args.jobs,
            timeout=args.timeout,
            output_dir=output_dir,
            cancel_event=threading.Event(),
            command="flowguard-simulator",
            # A simulator invocation must return evidence that is usable for
            # this invocation, not merely an old owner receipt whose native
            # artifact may have lived under a caller-owned temporary output
            # directory.  The model runner still reuses a strict current
            # native artifact when it is retained; only missing/invalid native
            # projections are executed once and then published.
            require_executed_case_ids=True,
        )
        validation = report.to_validation_result()
        if args.json:
            result_path = Path(report.output_dir) / "report.json"
            result_sha256 = (
                "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
                if result_path.is_file()
                else ""
            )
            print(
                validation.terminal_json_text(
                    run_id=Path(report.output_dir).name,
                    result_path=str(result_path),
                    result_sha256=result_sha256,
                )
            )
        else:
            print(validation.format_text(full=args.full))
        return validation.exit_code
    except (ValueError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.validation_result.v1",
            "command": "flowguard-simulator",
            "status": "invalid_input",
            "exit_code": 3,
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"status: invalid_input\nerror: {exc}")
        return 3


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


def _run_implementation_inventory_audit_command(args: argparse.Namespace) -> int:
    from .implementation_inventory import (
        ImplementationInventoryError,
        audit_implementation_surface_inventory,
    )

    try:
        report = audit_implementation_surface_inventory(args.inventory, root=args.root)
    except (ImplementationInventoryError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("implementation_inventory_invalid", exc),
            as_json=args.json,
        )
        return 2
    _emit_payload(report.to_dict(), as_json=args.json)
    return 0 if report.ok else 1


def _run_implementation_behavior_surface_audit_command(args: argparse.Namespace) -> int:
    """Audit production surfaces back to independent intent/model/test rows."""

    from .behavior_surface_audit import (
        PublicBehaviorSurfaceAuditError,
        audit_implementation_behavior_surface,
        compact_implementation_behavior_surface_audit,
        discover_implementation_behavior_surfaces,
    )
    from .execution_profiles import (
        OPERATION_KIND_READ_ONLY,
        select_execution_profile,
    )

    execution_profile = getattr(args, "profile", "light")
    profile_decision = select_execution_profile(
        execution_profile,
        operation_kind=getattr(
            args, "operation_kind", OPERATION_KIND_READ_ONLY
        ),
        route_kind=getattr(args, "route_kind", ""),
        modeling_mode=getattr(args, "modeling_mode", None),
        changed_paths=tuple(getattr(args, "changed_path", ()) or ()),
        governed_writes_frozen=bool(getattr(args, "governed_writes_frozen", False)),
        projections_frozen=bool(getattr(args, "projections_frozen", False)),
        openspec_frozen=bool(getattr(args, "openspec_frozen", False)),
        owner_dag_frozen=bool(getattr(args, "owner_dag_frozen", False)),
        reverse_input_frozen=bool(getattr(args, "reverse_input_frozen", False)),
    )

    try:
        if args.surface_discovery:
            discovery_path = Path(args.surface_discovery)
            loaded = json.loads(discovery_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("surface discovery artifact must be a JSON object")
            # A merged shard artifact is an explicit source observation.  Do
            # not silently replace it with a new bounded scan: doing so could
            # truncate a large project and make a partial denominator look
            # current.  The audit itself validates the shard identity and
            # current source boundary.
            discovery = loaded
        else:
            discovery = discover_implementation_behavior_surfaces(args.root)
        report = audit_implementation_behavior_surface(
            args.root,
            args.surface_map,
            discovery=discovery,
            currentness_profile=("full" if execution_profile == "full" else "light"),
        )
    except (PublicBehaviorSurfaceAuditError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("implementation_behavior_surface_invalid", exc),
            as_json=args.json,
        )
        return 2
    if getattr(args, "full_output", False):
        payload = {
            "discovery": discovery,
            "audit": report,
        }
    else:
        payload = compact_implementation_behavior_surface_audit(
            discovery,
            report,
            discovery_artifact=args.surface_discovery,
            surface_map_artifact=args.surface_map,
        )
    if isinstance(payload, dict):
        payload.update(profile_decision.to_dict())
        if not profile_decision.ok:
            payload["status"] = "blocked"
            payload["ok"] = False
            findings = payload.setdefault("findings", [])
            findings.extend(
                {
                    "code": trigger,
                    "severity": "blocked",
                    "message": f"execution profile admission is blocked: {trigger}",
                }
                for trigger in profile_decision.escalation_triggers
            )
    _emit_payload(payload, as_json=args.json)
    return 0 if report.get("status") == "passed" else 1


def _run_reverse_surface_authoring_context_command(args: argparse.Namespace) -> int:
    """Build or validate the current unresolved reverse-closure context."""

    from .reverse_surface_authoring import (
        ReverseSurfaceAuthoringError,
        build_reverse_surface_authoring_context,
        validate_reverse_surface_authoring_context,
    )

    try:
        def _read(path: str) -> dict[str, Any]:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"JSON artifact {path} must contain an object")
            return value

        discovery = _read(args.discovery)
        ledger = _read(args.ledger)
        owner_bindings = _read(args.owner_bindings)
        if args.validate:
            result = validate_reverse_surface_authoring_context(
                _read(args.validate),
                discovery,
                ledger=ledger,
                owner_bindings=owner_bindings,
            )
        else:
            result = build_reverse_surface_authoring_context(
                discovery,
                ledger=ledger,
                owner_bindings=owner_bindings,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ReverseSurfaceAuthoringError, ValueError) as exc:
        result = {
            "schema_version": "flowguard.reverse_surface_authoring_context.v1",
            "status": "blocked",
            "findings": [{"code": "reverse_surface_authoring_input_invalid", "message": str(exc)}],
        }
    _emit_payload(result, as_json=True)
    if args.validate:
        return 0 if result.get("status") == "passed" else 1
    return 0 if result.get("status") == "authoring_required" else 1


def _run_fault_matrix_review_command(args: argparse.Namespace) -> int:
    """Reconcile one native finite fault/recovery matrix without executing it."""

    from .fault_matrix_evidence import load_fault_matrix, review_fault_matrix

    try:
        payload = load_fault_matrix(args.matrix)
        report = review_fault_matrix(
            payload,
            expected_case_ids=args.expected_case_id or None,
            expected_input_fingerprint=args.expected_input_fingerprint,
            expected_owner_id=args.expected_owner_id,
            expected_source_fingerprint=args.expected_source_fingerprint,
            expected_model_fingerprint=args.expected_model_fingerprint,
            expected_toolchain_fingerprint=args.expected_toolchain_fingerprint,
            expected_environment_fingerprint=args.expected_environment_fingerprint,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        report = {
            "schema_version": "flowguard.fault_matrix_evidence.v1",
            "status": "blocked",
            "findings": [{"code": "fault_matrix_input_invalid", "detail": str(exc)}],
        }
    _emit_payload(report, as_json=True)
    return 0 if report.get("status") == "passed" else 1


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


def _run_flowguard_self_architecture_reduction_command(
    args: argparse.Namespace,
) -> int:
    """Review exact self-blueprint contraction signals without writing code."""

    from .blueprint_compact_projection import (
        BlueprintCompactProjection,
        compact_reduction_candidate_detail,
    )
    from .self_architecture_reduction import (
        review_flowguard_self_architecture_reduction,
    )
    from .self_blueprint import FlowGuardSelfBlueprintError

    try:
        report = review_flowguard_self_architecture_reduction(args.root)
    except (FlowGuardSelfBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload(
                "flowguard_self_architecture_reduction_invalid", exc
            ),
            as_json=args.json,
        )
        return 2
    payload = (
        BlueprintCompactProjection.reduction(report)
        if args.compact
        else report.to_dict()
    )
    candidate_id = str(getattr(args, "candidate_id", "") or "").strip()
    if candidate_id:
        try:
            payload["candidate_detail"] = (
                compact_reduction_candidate_detail(report, candidate_id)
                if args.compact
                else next(
                    row for row in report.candidates if row.candidate_id == candidate_id
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
    _emit_payload(payload, as_json=args.json)
    return 0 if report.ok else 1


def _run_target_system_blueprint_audit_command(args: argparse.Namespace) -> int:
    """Qualify one frozen target from strict native artifacts only."""

    from .target_native_qualification import (
        load_target_blueprint_native_report_set,
        qualify_target_system_from_native_reports,
    )
    from .target_system_blueprint import (
        load_frozen_target_system_evidence,
        load_target_system_descriptor,
    )

    try:
        descriptor = load_target_system_descriptor(args.descriptor)
        frozen_evidence = load_frozen_target_system_evidence(args.frozen_evidence)
        native_report_set = load_target_blueprint_native_report_set(
            args.native_report_set
        )
        report = qualify_target_system_from_native_reports(
            descriptor,
            frozen_evidence,
            native_report_set,
        )
    except (OSError, TypeError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("target_system_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    _emit_payload(report.to_dict(), as_json=args.json)
    return 0 if report.ok else 1


def _run_target_system_blueprint_export_command(args: argparse.Namespace) -> int:
    """Reject the retired standalone target projection route."""

    _emit_payload(
        {
            "status": "blocked",
            "reason": "native_directory_only",
            "claim_boundary": "Target DNA is checked in its native directory.",
        },
        as_json=getattr(args, "json", False),
    )
    return 2

    from .canonical_blueprint_projection import (
        canonical_target_system_blueprint_projection,
        verify_materialized_target_system_blueprint_projection,
    )
    from .implementation_blueprint import (
        BlueprintValidationError,
        write_canonical_blueprint_projection,
    )
    from .target_native_qualification import (
        load_target_blueprint_native_report_set,
        qualify_target_system_from_native_reports,
    )
    from .target_system_blueprint import (
        load_frozen_target_system_evidence,
        load_target_system_descriptor,
    )

    try:
        descriptor = load_target_system_descriptor(args.descriptor)
        frozen_evidence = load_frozen_target_system_evidence(args.frozen_evidence)
        native_report_set = load_target_blueprint_native_report_set(
            args.native_report_set
        )
        report = qualify_target_system_from_native_reports(
            descriptor,
            frozen_evidence,
            native_report_set,
        )
        projection = canonical_target_system_blueprint_projection(
            descriptor,
            frozen_evidence,
            native_report_set,
            report,
        )
        written = write_canonical_blueprint_projection(projection, args.output)
        materialization = verify_materialized_target_system_blueprint_projection(
            args.output,
            descriptor,
            frozen_evidence,
            native_report_set,
            report,
        )
        if not materialization.ok:
            raise BlueprintValidationError(
                "; ".join(finding.message for finding in materialization.findings)
            )
    except (BlueprintValidationError, OSError, TypeError, ValueError) as exc:
        payload = _blueprint_error_payload(
            "target_system_blueprint_export_failed", exc
        )
        payload.update(
            {
                "materialization_ok": False,
                "materialization_status": "blocked",
                "model_readiness_status": "not_available",
                "claim_boundary": (
                    "No target blueprint was materialized after strict input, "
                    "qualification, projection, or verification failure."
                ),
            }
        )
        _emit_payload(payload, as_json=args.json)
        return 2

    output_root = Path(args.output).resolve()
    first_gap = report.readiness_ledger.first_gap
    _emit_payload(
        {
            "materialization_ok": True,
            "materialization_status": "complete",
            "target_system_id": descriptor.target_system_id,
            "target_profile": descriptor.target_profile,
            "subject_revision": descriptor.subject_revision,
            "descriptor_fingerprint": descriptor.fingerprint,
            "frozen_evidence_fingerprint": frozen_evidence.fingerprint,
            "native_report_set_fingerprint": native_report_set.fingerprint,
            "target_blueprint_fingerprint": report.fingerprint,
            "projection_fingerprint": (
                materialization.materialization.projection.fingerprint
            ),
            "tree_fingerprint": materialization.materialization.tree_fingerprint,
            "model_readiness_status": report.status,
            "deepest_proven_layer": report.deepest_proven_layer,
            "gap_count": report.readiness_ledger.gap_count,
            "first_gap": (
                {"gap_id": first_gap.gap_id, **first_gap.to_dict()}
                if first_gap is not None
                else None
            ),
            "written_paths": [
                path.relative_to(output_root).as_posix() for path in written
            ],
            "generic_claim_boundary": (
                materialization.materialization.claim_boundary
            ),
            "claim_boundary": materialization.claim_boundary,
        },
        as_json=args.json,
    )
    return 0


def _run_affected_blueprint_understanding_command(args: argparse.Namespace) -> int:
    """Read one normalized affected closure without constructing the target."""

    from .affected_blueprint_reader import (
        AffectedBlueprintIndex,
        AffectedBlueprintReadError,
        load_affected_blueprint_projection,
        read_affected_blueprint_understanding,
    )

    if bool(getattr(args, "accepted_snapshot_verified", False)):
        _emit_payload(
            {
                **_blueprint_error_payload(
                    "caller_snapshot_verification_not_accepted",
                    ValueError(
                        "--accepted-snapshot-verified is caller-declared metadata; "
                        "only the native authority loader may establish accepted currentness"
                    ),
                ),
                "producer_count": 0,
            },
            as_json=args.json,
        )
        return 2
    from .blueprint_compact_projection import BlueprintCompactProjection

    root = Path(args.root or ".").resolve()

    def resolve_input(path: str) -> Path:
        """Resolve CLI inputs relative to the declared task root.

        The stores are explicit content-addressed inputs and may intentionally
        live outside the project root (for example a caller-owned evidence
        bundle).  We therefore normalize relative paths here without silently
        rewriting or copying the evidence.
        """

        candidate = Path(path)
        return (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    def load_store(path: str, context: str) -> dict[str, object]:
        try:
            payload = _strict_json_loads(
                resolve_input(path).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise AffectedBlueprintReadError(
                f"cannot load {context}: {exc}"
            ) from exc
        except ValueError as exc:
            raise AffectedBlueprintReadError(
                f"cannot load {context}: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise AffectedBlueprintReadError(f"{context} must be a JSON object")
        return {str(key): value for key, value in payload.items()}

    def load_optional_object(path: str | None, context: str) -> Mapping[str, Any] | None:
        if not path:
            return None
        payload = load_store(path, context)
        return payload

    projection_root_arg = getattr(args, "projection_root", None)
    manual_paths = tuple(
        value
        for value in (
            getattr(args, "index", None),
            getattr(args, "shard_store", None),
            getattr(args, "object_store", None),
        )
        if value
    )
    if projection_root_arg and manual_paths:
        _emit_payload(
            {
                **_blueprint_error_payload(
                    "projection_arguments_conflict",
                    ValueError(
                        "--projection-root cannot be combined with --index, "
                        "--shard-store, or --object-store"
                    ),
                ),
                "producer_count": 0,
            },
            as_json=args.json,
        )
        return 2
    if not projection_root_arg and manual_paths and len(manual_paths) != 3:
        _emit_payload(
            {
                **_blueprint_error_payload(
                    "projection_location_required",
                    ValueError(
                        "manual affected reads require --index, --shard-store, "
                        "and --object-store together"
                    ),
                ),
                "producer_count": 0,
            },
            as_json=args.json,
        )
        return 2

    # With no projection or explicit stores, retain the small model-owner
    # navigation that an AI can use to locate the right map. This branch is
    # read-only and never invokes a blueprint producer.
    if not projection_root_arg and not manual_paths:
        preflight_error = ""
        try:
            from .existing_model_preflight import existing_model_preflight_from_project

            preflight = existing_model_preflight_from_project(
                root,
                args.task_summary or "",
                changed_paths=tuple(args.changed_path or ()),
                mode="light",
                inventory_scope="selected_owner_closure",
            )
            owner_candidates = [
                {
                    "model_id": str(getattr(row, "model_id", "")),
                    "model_path": str(getattr(row, "model_path", "")),
                    "evidence_id": str(getattr(row, "evidence_id", "")),
                    "evidence_current": bool(getattr(row, "evidence_current", False)),
                }
                for row in getattr(preflight, "relevant_models", ())
            ]
            authority_integrity = str(
                getattr(preflight, "authority_integrity", "")
                or getattr(preflight, "authority_status", "")
                or "unavailable"
            )
            selected_currentness = str(
                getattr(preflight, "selected_source_currentness", "")
                or (
                    "current"
                    if owner_candidates
                    and all(row["evidence_current"] for row in owner_candidates)
                    else "not_selected"
                )
            )
            execution_evidence_status = str(
                getattr(preflight, "execution_evidence_status", "")
                or "not_run"
            )
            as_of = dict(getattr(preflight, "as_of", {}) or {})
            stale_obligations = list(
                getattr(preflight, "stale_obligations", ()) or ()
            )
            stale_obligation_details = [
                dict(item)
                for item in (
                    getattr(preflight, "stale_obligation_details", ()) or ()
                )
            ]
            selected_model_paths = list(
                getattr(preflight, "selected_model_paths", ()) or ()
            )
            selected_runner_paths = list(
                getattr(preflight, "selected_runner_paths", ()) or ()
            )
            selected_input_paths = list(
                getattr(preflight, "selected_input_paths", ()) or ()
            )
            selected_intent_paths = list(
                getattr(preflight, "selected_intent_paths", ()) or ()
            )
            selected_contract_paths = list(
                getattr(preflight, "selected_contract_paths", ()) or ()
            )
            selected_closure = dict(
                getattr(preflight, "selected_closure", {}) or {}
            )
            selected_model_ids = list(
                selected_closure.get("selected_model_ids")
                or [row["model_id"] for row in owner_candidates]
            )
            authority = {
                "status": str(getattr(preflight, "authority_status", "")),
                "integrity": authority_integrity,
                "selected_source_currentness": selected_currentness,
                "execution_evidence_status": execution_evidence_status,
                "snapshot_fingerprint": str(
                    getattr(preflight, "authority_snapshot_fingerprint", "")
                ),
                "subject_revision": str(
                    getattr(preflight, "authority_subject_revision", "")
                ),
                "as_of": as_of,
            }
        except Exception as exc:
            owner_candidates = []
            preflight_error = str(exc)
            authority_integrity = "unavailable"
            selected_currentness = "unavailable"
            execution_evidence_status = "not_run"
            as_of = {}
            stale_obligations = []
            stale_obligation_details = []
            selected_model_paths = []
            selected_runner_paths = []
            selected_input_paths = []
            selected_intent_paths = []
            selected_contract_paths = []
            selected_closure = {}
            selected_model_ids = []
            authority = {
                "status": "unavailable",
                "integrity": authority_integrity,
                "selected_source_currentness": selected_currentness,
                "execution_evidence_status": execution_evidence_status,
                "as_of": as_of,
                "error": preflight_error,
            }

        authority_ok = authority_integrity in {"pass", "pass_with_gaps"}
        basic_navigation_ok = authority_ok and bool(owner_candidates)
        if basic_navigation_ok:
            basic_status = (
                "basic_navigation_stale"
                if selected_currentness in {"stale", "unavailable"}
                else "basic_navigation"
            )
            basic_gap_severity = "scoped"
            basic_exit = 0
        elif authority_ok:
            basic_status = "basic_navigation_owner_unresolved"
            basic_gap_severity = "blocked"
            basic_exit = 2
        else:
            basic_status = "basic_navigation_unavailable"
            basic_gap_severity = "blocked"
            basic_exit = 2

        gaps = [
            {
                "code": "deep_projection_not_requested",
                "message": (
                    "No projection-root or explicit affected stores were supplied; "
                    "basic owner navigation is returned without invoking a producer."
                ),
                "severity": "scoped",
            }
        ]
        if stale_obligations:
            gaps.extend(
                {
                    "code": "selected_source_stale",
                    "message": obligation,
                    "severity": "scoped",
                }
                for obligation in stale_obligations
            )
        _emit_payload(
            {
                "ok": basic_navigation_ok,
                "status": basic_status,
                "scope": "affected",
                "changed_paths": list(args.changed_path or ()),
                "owner_candidates": owner_candidates,
                "selected_model_ids": selected_model_ids,
                "authority": authority,
                "authority_integrity": authority_integrity,
                "selected_source_currentness": selected_currentness,
                "selected_currentness": selected_currentness,
                "execution_evidence_status": execution_evidence_status,
                "execution_status": execution_evidence_status,
                "as_of": as_of,
                "as_of_map": as_of,
                "stale_obligations": stale_obligations,
                "stale_obligation_details": stale_obligation_details,
                "selected_model_paths": selected_model_paths,
                "selected_runner_paths": selected_runner_paths,
                "selected_input_paths": selected_input_paths,
                "selected_intent_paths": selected_intent_paths,
                "selected_contract_paths": selected_contract_paths,
                "selected_closure": selected_closure,
                "producer_count": 0,
                "write_count": 0,
                "claim_boundary": (
                    "Basic selected-owner navigation is an as-of read. It does not "
                    "claim deep projection, current execution, release, or whole-system "
                    "live inventory."
                ),
                "gaps": gaps,
            },
            as_json=args.json,
        )
        return basic_exit

    # Keep cleanup ownership explicit.  Using ``locals()`` here made the
    # implementation inventory report an open dynamic surface even though the
    # two stores are a fixed part of this command's protocol.  Explicit
    # initialization also makes the error path and the close path equivalent.
    shard_store: _JsonObjectStoreLocator | None = None
    object_store: _JsonObjectStoreLocator | None = None
    projection_bundle = None
    try:
        if projection_root_arg:
            projection_argument_text = str(projection_root_arg)
            projection_argument = Path(projection_argument_text)
            # Treat both POSIX and Windows separators as path separators.  A
            # caller may submit a Windows-style relative path while the
            # checker is running under WSL; ``Path.parts`` alone would treat
            # ``..\\outside`` as one literal filename and return a misleading
            # missing-root error instead of the required traversal finding.
            normalized_projection_parts = tuple(
                part
                for part in projection_argument_text.replace("\\", "/").split("/")
                if part
            )
            if not projection_argument.is_absolute() and ".." in normalized_projection_parts:
                raise AffectedBlueprintReadError(
                    "projection_path_traversal: --projection-root must not contain '..'"
                )
            projection_bundle = load_affected_blueprint_projection(
                resolve_input(str(projection_root_arg)),
                authority_root=root,
                accepted_snapshot=load_optional_object(
                    args.accepted_snapshot, "affected accepted snapshot"
                ),
            )
            if projection_bundle.unknown_entries:
                raise AffectedBlueprintReadError(
                    "projection_unknown_entry: "
                    + ", ".join(projection_bundle.unknown_entries)
                )
            index = projection_bundle.index
            explicit_ids = tuple(args.affected_id or ())
            path_ids, unknown_paths = projection_bundle.changed_path_candidates(
                tuple(args.changed_path or ())
            )
            if unknown_paths:
                raise AffectedBlueprintReadError(
                    "unknown_change_point: " + ", ".join(unknown_paths)
                )
            # Merge all caller-declared seeds before entering the reader.  The
            # reader then performs one closure walk and keeps the same shard
            # and object locators for the complete request.
            requested_ids = tuple(sorted(set(explicit_ids) | set(path_ids)))
            if not requested_ids:
                raise AffectedBlueprintReadError(
                    "affected_id_required: projection-root reads require "
                    "--affected-id or one uniquely registered --changed-path"
                )
            load_shard = projection_bundle.load_shard
            load_object = projection_bundle.load_object
            surface_catalog = load_optional_object(
                args.surface_catalog, "affected surface catalog"
            ) or projection_bundle.surface_catalog
            accepted_snapshot = projection_bundle.accepted_snapshot
        else:
            index = AffectedBlueprintIndex.from_dict(
                load_store(args.index, "affected blueprint index")
            )
            requested_ids = tuple(args.affected_id or ())
            shard_store = _JsonObjectStoreLocator(
                resolve_input(args.shard_store), "affected blueprint shard store"
            )
            object_store = _JsonObjectStoreLocator(
                resolve_input(args.object_store), "affected blueprint object store"
            )
            load_shard = shard_store.load
            load_object = object_store.load
            surface_catalog = load_optional_object(
                args.surface_catalog, "affected surface catalog"
            )
            accepted_snapshot = load_optional_object(
                args.accepted_snapshot, "affected accepted snapshot"
            )
        result = read_affected_blueprint_understanding(
            index,
            affected_ids=requested_ids,
            load_shard=load_shard,
            load_object=load_object,
            task_summary=args.task_summary or "",
            changed_paths=tuple(args.changed_path or ()),
            surface_catalog=surface_catalog,
            accepted_snapshot=accepted_snapshot,
            authority_root=root,
            authority_state=(
                projection_bundle.authority_state
                if projection_bundle is not None
                else None
            ),
        )
    except (AffectedBlueprintReadError, KeyError, TypeError, ValueError) as exc:
        error_code = (
            "projection_root_invalid"
            if projection_root_arg
            else "affected_blueprint_understanding_invalid"
        )
        _emit_payload(
            {
                **_blueprint_error_payload(error_code, exc),
                "producer_count": 0,
            },
            as_json=args.json,
        )
        return 2
    finally:
        # Explicitly close memory maps after the read; the stores are inputs,
        # never generated artifacts, and remain untouched for later consumers.
        for store in (shard_store, object_store):
            if isinstance(store, _JsonObjectStoreLocator):
                store.close()
        if projection_bundle is not None:
            projection_bundle.close()
    payload = BlueprintCompactProjection.understanding(result)
    if projection_bundle is not None:
        payload["projection"] = {
            "root": str(projection_bundle.projection_root),
            "projection_fingerprint": projection_bundle.projection_fingerprint,
            "blueprint_fingerprint": projection_bundle.blueprint_fingerprint,
            "authority_snapshot_fingerprint": projection_bundle.authority_snapshot_fingerprint,
            "authority_head_fingerprint": projection_bundle.authority_head_fingerprint,
            "claim_boundary": (
                "Selective current projection identity and affected closure only; "
                "no producer or whole-blueprint builder was invoked."
            ),
        }
    _emit_payload(payload, as_json=args.json)
    return 0


def _run_affected_impact_plan_command(args: argparse.Namespace) -> int:
    """Build or validate one current-only affected owner-impact receipt."""

    from .affected_blueprint_reader import AffectedBlueprintReadError, AffectedImpactPlan
    from .validation_ownership import (
        ValidationOwnerContract,
        build_affected_impact_plan,
        validate_affected_impact_plan,
    )

    def load_json(path: str, context: str) -> Any:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AffectedBlueprintReadError(f"cannot load {context}: {exc}") from exc
        return value

    try:
        contracts_payload = load_json(args.contracts, "affected owner contracts")
        if isinstance(contracts_payload, Mapping):
            contracts_payload = contracts_payload.get("contracts", ())
        if not isinstance(contracts_payload, (list, tuple)):
            raise AffectedBlueprintReadError("affected owner contracts must be an array")
        contracts = tuple(ValidationOwnerContract.from_dict(item) for item in contracts_payload)
        component_bindings = (
            load_json(args.components, "affected component bindings")
            if args.components
            else None
        )
        if args.validate:
            plan = validate_affected_impact_plan(
                load_json(args.validate, "affected impact plan"),
                selected_member_ids=tuple(args.member or ()),
            )
        else:
            def parse_edges(values: Sequence[str]) -> tuple[tuple[str, str], ...]:
                rows = []
                for value in values:
                    parts = tuple(item.strip() for item in str(value).split("->"))
                    if len(parts) != 2 or not all(parts):
                        raise AffectedBlueprintReadError(
                            f"edge must use source->target syntax: {value}"
                        )
                    rows.append((parts[0], parts[1]))
                return tuple(rows)

            dispositions = (
                load_json(args.owner_dispositions, "affected owner dispositions")
                if args.owner_dispositions
                else None
            )
            identities = (
                load_json(args.owner_identities, "affected owner identities")
                if args.owner_identities
                else None
            )
            receipts = (
                load_json(args.owner_receipts, "affected owner receipts")
                if args.owner_receipts
                else None
            )
            plan = build_affected_impact_plan(
                args.root,
                contracts,
                changed_paths=tuple(args.changed_path or ()),
                component_bindings=component_bindings,
                parent_edges=parse_edges(tuple(args.parent_edge or ())),
                cross_boundary_edges=parse_edges(tuple(args.cross_boundary_edge or ())),
                sibling_edges=parse_edges(tuple(args.sibling_edge or ())),
                owner_dispositions=dispositions,
                owner_identities=identities,
                owner_receipts=receipts,
            )
        payload = plan.to_dict()
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            payload["artifact_path"] = str(output_path)
    except (AffectedBlueprintReadError, OSError, TypeError, ValueError, KeyError) as exc:
        _emit_payload(
            _blueprint_error_payload("affected_impact_plan_invalid", exc),
            as_json=True,
        )
        return 2
    _emit_payload(payload, as_json=True)
    return 0 if plan.ok else 1


def _load_project_blueprint_bundle(args: argparse.Namespace):
    """Build one canonical project blueprint from its current native inputs."""

    from .implementation_inventory_python import (
        PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        discover_python_implementation_surfaces,
    )
    from .project_blueprint import (
        ProjectBlueprintError,
        build_project_blueprint,
        load_project_blueprint_document,
    )
    from .test_inventory_python import (
        PYTHON_AST_TEST_ADAPTER_ID,
        discover_python_test_file,
    )

    definition, evidence, frozen_target_evidence = load_project_blueprint_document(
        args.definition
    )
    return build_project_blueprint(
        args.root,
        definition,
        evidence,
        frozen_target_evidence=frozen_target_evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: (
                discover_python_implementation_surfaces
            )
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
    )


def _run_project_blueprint_audit_command(args: argparse.Namespace) -> int:
    """Build a declared target-system software blueprint in memory only."""

    from .blueprint_compact_projection import compact_project_blueprint_projection
    from .project_blueprint import ProjectBlueprintError

    try:
        bundle = _load_project_blueprint_bundle(args)
    except (ProjectBlueprintError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("project_blueprint_invalid", exc),
            as_json=args.json,
        )
        return 2
    payload = (
        compact_project_blueprint_projection(bundle)
        if args.compact
        else bundle.to_dict()
    )
    _emit_payload(payload, as_json=args.json)
    return 0 if bundle.ok else 1


def _run_project_blueprint_candidate_command(args: argparse.Namespace) -> int:
    """Discover unresolved behavior candidates without writing the target."""

    from .implementation_inventory import (
        ImplementationInventoryError,
        load_implementation_surface_inventory,
        review_implementation_surface_inventory,
    )
    from .software_blueprint_readiness import generate_candidate_blueprint

    try:
        inventory = load_implementation_surface_inventory(args.inventory)
        audit = review_implementation_surface_inventory(inventory, root=args.root)
        if not audit.ok:
            raise ValueError("implementation inventory audit is blocked")
        candidate = generate_candidate_blueprint(
            inventory,
            target_kind=args.target_kind,
            observation_provider_ids=tuple(args.provider),
        )
    except (ImplementationInventoryError, OSError, ValueError) as exc:
        _emit_payload(
            _blueprint_error_payload("project_blueprint_candidate_invalid", exc),
            as_json=args.json,
        )
        return 2
    payload = candidate.to_dict()
    if args.compact:
        payload = {
            "schema_version": payload["schema_version"],
            "inventory_fingerprint": payload["inventory_fingerprint"],
            "target_kind": payload["target_kind"],
            "observation_provider_ids": payload["observation_provider_ids"],
            "status": payload["status"],
            "behavior_contract_count": len(candidate.behavior_contracts),
            "unresolved_count": len(candidate.unresolved_ids),
            "first_unresolved_id": (
                candidate.unresolved_ids[0] if candidate.unresolved_ids else ""
            ),
            "blockers": list(candidate.blockers),
            "claim_boundary": payload["claim_boundary"],
        }
    _emit_payload(payload, as_json=args.json)
    return 0 if candidate.status == "ready" else 1


def _print_lifecycle(payload: dict[str, object], *, as_json: bool) -> int:
    status = str(payload.get("status", "pass"))
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {status}")
        if "counts" in payload:
            print("counts: " + " ".join(f"{key}={value}" for key, value in sorted(dict(payload["counts"]).items())))
        if "plan_id" in payload:
            print(f"plan_id: {payload['plan_id']}")
        if "quarantine_id" in payload:
            print(f"quarantine_id: {payload['quarantine_id']}")
        for finding in payload.get("findings", ()):
            print(f"finding: {finding.get('code')}: {finding.get('message')}")
    return 0 if status == "pass" else 2


def _run_evidence_lifecycle_command(args: argparse.Namespace) -> int:
    from .evidence_lifecycle import (
        EvidenceLifecycleError,
        apply_evidence_gc,
        audit_evidence,
        plan_evidence_gc,
        purge_evidence_quarantine,
        restore_evidence_quarantine,
        settle_interrupted_execution_leases,
        write_json_atomic,
    )

    try:
        if args.evidence_action == "audit":
            payload = audit_evidence(args.root)
        elif args.evidence_action == "plan":
            storage_payload = None
            if getattr(args, "storage_audit", False):
                from .storage_audit import audit_storage

                storage_root = (
                    Path(args.storage_root).expanduser()
                    if getattr(args, "storage_root", None)
                    else Path(args.root).expanduser().resolve().parent
                )
                storage_report = audit_storage(storage_root)
                if storage_report.status != "passed":
                    raise EvidenceLifecycleError(
                        "storage audit has blockers; repair them before GC planning"
                    )
                storage_payload = storage_report.to_dict()
            payload = plan_evidence_gc(
                args.root,
                keep=args.keep,
                include_legacy=args.include_legacy,
                preserve_paths=tuple(args.preserve),
                storage_audit=storage_payload,
            )
            if args.output:
                write_json_atomic(args.output, payload)
        elif args.evidence_action == "apply":
            payload = apply_evidence_gc(args.root, args.plan)
        elif args.evidence_action == "restore":
            payload = restore_evidence_quarantine(args.root, args.quarantine_id)
        elif args.evidence_action == "settle_interruption":
            leases = []
            for index, serialized in enumerate(args.lease_json):
                try:
                    row = json.loads(serialized)
                except json.JSONDecodeError as exc:
                    raise EvidenceLifecycleError(
                        f"--lease-json row {index} is not valid JSON"
                    ) from exc
                if not isinstance(row, dict):
                    raise EvidenceLifecycleError(
                        f"--lease-json row {index} must be one JSON object"
                    )
                leases.append(row)
            payload = settle_interrupted_execution_leases(
                args.lock_root,
                {
                    "schema_version": "flowguard.evidence_interruption_settlement_request.v1",
                    "plan_id": args.plan_id,
                    "process_id": args.process_id,
                    "operator_reason": args.operator_reason,
                    "zero_descendant_observation": {
                        "descendant_process_ids": list(args.descendant_process_id),
                        "observed_at_epoch": args.observed_at_epoch,
                        "observed_by": args.observed_by,
                        "method": args.observation_method,
                    },
                    "leases": leases,
                },
            )
        else:
            payload = purge_evidence_quarantine(args.root, args.quarantine_id)
        return _print_lifecycle(dict(payload), as_json=args.json)
    except (EvidenceLifecycleError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.evidence_lifecycle_error.v1",
            "status": "blocked",
            "message": str(exc),
            "claim_boundary": "No lifecycle mutation is accepted after an identity, reachability, or containment failure.",
        }
        return _print_lifecycle(payload, as_json=args.json)


def _run_storage_audit_command(args: argparse.Namespace) -> int:
    from .storage_audit import audit_storage

    report = audit_storage(args.root, max_largest_items=args.max_items)
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"root: {payload['root']}")
        print(
            "counts: "
            + " ".join(
                f"{key}={payload[key]}"
                for key in (
                    "directory_walk_count",
                    "content_file_read_count",
                    "content_hash_read_count",
                    "content_bytes_read",
                )
            )
        )
        for finding in payload["findings"]:
            print(f"finding: {finding.get('code')}: {finding.get('path', '')}")
    return 0 if report.status == "passed" else 2


COMMANDS: dict[str, Callable[[], int]] = {
    "adoption-template": _run_adoption_template,
    "benchmark": _run_benchmark,
    "coverage": _run_coverage,
    "hardening": _run_hardening,
    "loop-review": _run_loop_review,
    "scenario-review": _run_scenario_review,
    "conformance": _run_conformance,
    "self-review": _run_self_review,
    "self-conformance": _run_self_conformance,
    "schema-version": _run_schema_version,
}


def _add_existing_command_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for command_name in sorted(COMMANDS):
        command_parser = subparsers.add_parser(command_name)
        command_parser.set_defaults(handler=lambda _args, name=command_name: COMMANDS[name]())


def _add_route_reference_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "route-reference",
        help="Return one current public route capsule and its lazy reference edges.",
    )
    parser.add_argument(
        "route",
        help="Public route id or its registered consumer skill name.",
    )
    parser.add_argument("--json", action="store_true", help="Print the capsule as JSON.")
    parser.set_defaults(handler=_run_route_reference_command)


def _add_adoption_entry_args(
    parser: argparse.ArgumentParser,
    *,
    default_status: str,
) -> None:
    parser.add_argument("--root", default=".", help="Project root where adoption logs are written.")
    parser.add_argument("--task-id", required=True, help="Stable id for this model-first adoption task.")
    parser.add_argument("--project", default="", help="Project name. Defaults to the root directory name.")
    parser.add_argument("--task-summary", required=True, help="Short description of the task.")
    parser.add_argument("--trigger-reason", required=True, help="Why FlowGuard was used or skipped.")
    parser.add_argument(
        "--status",
        default="auto",
        choices=("auto",) + ADOPTION_STATUSES,
        help=f"Adoption status. Defaults to {default_status!r}.",
    )
    parser.add_argument("--skill-decision", default="used_flowguard")
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--model-file", action="append", default=[])
    parser.add_argument("--command", action="append", default=[], help="Successful command/check to record.")
    parser.add_argument("--failed-command", action="append", default=[], help="Failed command/check to record.")
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--counterexample", action="append", default=[])
    parser.add_argument("--friction-point", action="append", default=[])
    parser.add_argument("--skipped-step", action="append", default=[])
    parser.add_argument(
        "--risk-evidence",
        action="append",
        default=[],
        help="Final risk evidence ledger note, scoped boundary, or proof gap.",
    )
    parser.add_argument("--next-action", action="append", default=[])
    parser.set_defaults(handler=_run_adoption_entry, default_status=default_status)


def _add_file_template_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command: FileTemplateCommand,
) -> None:
    parser = subparsers.add_parser(command.name, help=command.help_text)
    parser.add_argument(
        "--output",
        help="Project root where template files should be written. If omitted, prints JSON to stdout.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    parser.set_defaults(
        handler=lambda args, template_command=command: _run_file_template_command(args, template_command)
    )


def _add_project_adoption_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command_name: str,
    *,
    action: str,
    help_text: str,
) -> None:
    parser = subparsers.add_parser(command_name, help=help_text)
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Include the complete observed shape and finding arrays; default output is bounded.",
    )
    if action == "upgrade":
        parser.add_argument(
            "--records-only",
            action="store_true",
            help="Only update AGENTS/manifest/adoption records; skip artifact/model/test upgrade scanning.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview files, semantic rule changes, suite findings, and revalidation without writing.",
        )
    else:
        parser.set_defaults(records_only=False, dry_run=False)
    parser.set_defaults(handler=_run_project_adoption_command, project_action=action)


def _add_project_layout_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "project-layout-audit",
        help="Read-only audit of the mandatory current .flowguard role layout.",
    )
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--output", help="Write the complete machine report to this file.")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Require --output for the complete machine report; stdout remains a bounded summary.",
    )
    parser.add_argument(
        "--profile",
        choices=("light", "affected", "full"),
        default="light",
        help="Currentness claim boundary; profiles never fall back to one another.",
    )
    parser.add_argument(
        "--modeling-mode",
        choices=("read_only_audit", "model_first_change", "model_maintenance", "layered_boundary_proof"),
        default=None,
        help="Semantic modeling boundary; independent from execution profile.",
    )
    parser.add_argument(
        "--operation-kind",
        choices=("read_only", "change", "qualification"),
        default="read_only",
        help="Typed operation fact used for profile selection.",
    )
    parser.add_argument("--route-kind", default="", help="Optional specialist route kind; it never auto-upgrades a profile.")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Exact changed path for the affected profile; repeat as needed.",
    )
    parser.add_argument("--governed-writes-frozen", action="store_true")
    parser.add_argument("--projections-frozen", action="store_true")
    parser.add_argument("--openspec-frozen", action="store_true")
    parser.add_argument("--owner-dag-frozen", action="store_true")
    parser.add_argument("--reverse-input-frozen", action="store_true")
    parser.set_defaults(handler=_run_project_layout_audit_command)


def _add_artifact_upgrade_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "artifact-upgrade",
        help="Audit older FlowGuard artifacts; stale data is rejected and never auto-migrated.",
    )
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Specific file or directory to scan. May be passed more than once.",
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_artifact_upgrade_command)


def _add_behavior_commitment_query_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    from .behavior_commitment import BCL_BEHAVIOR_PLANES

    parser = subparsers.add_parser(
        "behavior-commitment-query",
        help="Read-only plane-first lookup in a project's canonical behavior ledger.",
    )
    parser.add_argument("task_summary", nargs="?", default="", help="Short task or operation description.")
    parser.add_argument("--root", default=".", help="Target project root.")
    parser.add_argument(
        "--ledger",
        default=".flowguard/behavior/inventory/ledger.json",
        help="Canonical ledger path, relative to --root unless absolute.",
    )
    parser.add_argument("--plane", choices=BCL_BEHAVIOR_PLANES, default="")
    parser.add_argument("--term", action="append", default=[], help="Canonical task or commitment term.")
    parser.add_argument("--path", action="append", default=[], help="Changed or operated path clue.")
    parser.add_argument("--tool-id", action="append", default=[], help="Tool identifier clue.")
    parser.add_argument("--error-signature", action="append", default=[], help="Observed error signature clue.")
    parser.add_argument("--workflow-family", action="append", default=[], help="Workflow-family clue.")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum hits per result group (1-50).")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.set_defaults(handler=_run_behavior_commitment_query_command)


def _add_risk_template_search_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-search",
        help="Search packaged public and per-machine local risk templates.",
    )
    parser.add_argument("query", nargs="?", default="", help="Search query for the modeled risk.")
    parser.add_argument("--workflow-family", action="append", default=[], help="Workflow family hint.")
    parser.add_argument("--protected-error-class", action="append", default=[], help="Protected error class hint.")
    parser.add_argument("--local-root", default=None, help="Override local template library root.")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--no-public", action="store_true", help="Do not search packaged public templates.")
    parser.add_argument("--no-local", action="store_true", help="Do not search per-machine local templates.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_search_command)


def _add_risk_template_harvest_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-harvest",
        help="Write a reusable local risk template candidate.",
    )
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--workflow-family", action="append", default=[])
    parser.add_argument("--protected-error-class", action="append", default=[])
    parser.add_argument("--required-state", action="append", default=[])
    parser.add_argument("--required-side-effect", action="append", default=[])
    parser.add_argument("--required-evidence", action="append", default=[])
    parser.add_argument("--known-bad-case", action="append", default=[])
    parser.add_argument(
        "--known-bad-proof",
        action="append",
        default=[],
        help="JSON object for one KnownBadProof, including case_id and observed_status.",
    )
    parser.add_argument("--merge-key", action="append", default=[])
    parser.add_argument("--local-root", default=None, help="Override local template library root.")
    parser.add_argument("--no-write", action="store_true", help="Validate the candidate without writing it.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing local template file.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_harvest_command)


def _add_risk_template_harvest_review_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "risk-template-harvest-review",
        help="Review template harvest only after an explicit reusable-template operation.",
    )
    parser.add_argument(
        "--disposition",
        required=True,
        choices=("written", "merged", "duplicate_linked", "not_harvestable"),
    )
    parser.add_argument("--written-template-id", action="append", default=[])
    parser.add_argument("--merged-template-id", action="append", default=[])
    parser.add_argument("--linked-template-id", action="append", default=[])
    parser.add_argument("--not-harvestable-reason", default="")
    parser.add_argument("--local-root", default="")
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.set_defaults(handler=_run_risk_template_harvest_review_command)


def _add_work_context_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "work-context",
        help="Read one declared provider work unit through a registered read-only adapter.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--declaration-json", default="")
    parser.add_argument("--json", action="store_true", help="Canonical JSON is always emitted.")
    parser.set_defaults(handler=_run_work_context_command)


def _add_portable_model_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    validate = subparsers.add_parser(
        "portable-model-validate",
        help="Validate one current-schema portable finite model artifact.",
    )
    validate.add_argument("model", help="Portable model JSON path.")
    validate.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    validate.set_defaults(handler=_run_portable_model_validate_command)

    check = subparsers.add_parser(
        "portable-model-check",
        help="Run safety and temporal checks over one portable model.",
    )
    check.add_argument("model", help="Portable model JSON path.")
    check.add_argument("--max-states", type=int, default=10000)
    check.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    check.set_defaults(handler=_run_portable_model_check_command)

    refinement = subparsers.add_parser(
        "portable-model-refinement",
        help="Check an explicit child-to-parent portable refinement binding.",
    )
    refinement.add_argument("--parent", required=True, help="Parent portable model JSON path.")
    refinement.add_argument("--child", required=True, help="Child portable model JSON path.")
    refinement.add_argument("--binding", required=True, help="Refinement binding JSON path.")
    refinement.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    refinement.set_defaults(handler=_run_portable_model_refinement_command)

    system_check = subparsers.add_parser(
        "portable-system-check",
        help="Check one strict bounded system definition and request through the canonical portable checker.",
    )
    system_check.add_argument("--system", required=True, help="Portable system definition JSON path.")
    system_check.add_argument("--request", required=True, help="System composition request JSON path.")
    system_check.add_argument("--component", action="append", required=True, help="Referenced portable component model JSON path; repeat for every component.")
    system_check.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    system_check.set_defaults(handler=_run_portable_system_check_command)


def _add_implementation_blueprint_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    impact = subparsers.add_parser(
        "affected-impact-plan",
        help=(
            "Build or validate one exact current changed-path impact plan; "
            "no native producer is started by this command."
        ),
    )
    impact.add_argument("--root", default=".", help="Target project root.")
    impact.add_argument("--contracts", required=True, help="JSON array of ValidationOwnerContract rows.")
    impact.add_argument(
        "--components",
        default="",
        help="Explicit current path/component/owner binding JSON; omission permits only one unambiguous contract match.",
    )
    impact.add_argument("--changed-path", action="append", default=[])
    impact.add_argument("--parent-edge", action="append", default=[])
    impact.add_argument("--cross-boundary-edge", action="append", default=[])
    impact.add_argument("--sibling-edge", action="append", default=[])
    impact.add_argument("--owner-dispositions", default="")
    impact.add_argument("--owner-identities", default="")
    impact.add_argument("--owner-receipts", default="")
    impact.add_argument("--validate", default="", help="Validate an existing current impact-plan receipt instead of building one.")
    impact.add_argument("--member", action="append", default=[], help="Optional exact member comparison against a machine plan.")
    impact.add_argument("--output", default="", help="Optional path for the content-addressed plan receipt.")
    impact.set_defaults(handler=_run_affected_impact_plan_command)

    inventory = subparsers.add_parser(
        "implementation-inventory-audit",
        help="Read-only audit of one current implementation-surface inventory.",
    )
    inventory.add_argument("--inventory", required=True)
    inventory.add_argument("--root", default=None, help="Optional current source root.")
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(handler=_run_implementation_inventory_audit_command)

    reverse_surface = subparsers.add_parser(
        "implementation-behavior-surface-audit",
        help=(
            "Discover production implementation surfaces and audit their "
            "explicit intent/model/owner/test reverse closure."
        ),
    )
    reverse_surface.add_argument("--root", default=".", help="Bounded production project root.")
    reverse_surface.add_argument(
        "--surface-map",
        required=True,
        help="Independently authored implementation surface map JSON.",
    )
    reverse_surface.add_argument(
        "--surface-discovery",
        default="",
        help=(
            "Current merged source-only implementation-surface discovery JSON. "
            "Use this for the shard protocol when the project exceeds the "
            "single-scan row bound."
        ),
    )
    reverse_surface.add_argument(
        "--full-output",
        action="store_true",
        help=(
            "Emit the complete discovery and audit payload. By default the "
            "terminal receives a bounded summary and full evidence stays in "
            "the explicitly supplied artifacts."
        ),
    )
    reverse_surface.add_argument(
        "--profile",
        choices=("light", "affected", "full"),
        default="light",
        help=(
            "Execution profile. light is read-only, affected is an exact changed "
            "slice, and full is release-grade only after all freeze gates."
        ),
    )
    reverse_surface.add_argument(
        "--modeling-mode",
        choices=("read_only_audit", "model_first_change", "model_maintenance", "layered_boundary_proof"),
        default=None,
        help="Semantic modeling boundary; independent from execution profile.",
    )
    reverse_surface.add_argument(
        "--operation-kind",
        choices=("read_only", "change", "qualification"),
        default="read_only",
    )
    reverse_surface.add_argument("--route-kind", default="")
    reverse_surface.add_argument("--changed-path", action="append", default=[])
    reverse_surface.add_argument("--governed-writes-frozen", action="store_true")
    reverse_surface.add_argument("--projections-frozen", action="store_true")
    reverse_surface.add_argument("--openspec-frozen", action="store_true")
    reverse_surface.add_argument("--owner-dag-frozen", action="store_true")
    reverse_surface.add_argument("--reverse-input-frozen", action="store_true")
    reverse_surface.add_argument("--json", action="store_true")
    reverse_surface.set_defaults(handler=_run_implementation_behavior_surface_audit_command)

    authoring_context = subparsers.add_parser(
        "reverse-surface-authoring-context",
        help=(
            "Build or validate the current unresolved reverse implementation "
            "surface authoring context; no semantic mapping is inferred."
        ),
    )
    authoring_context.add_argument("--discovery", required=True)
    authoring_context.add_argument("--ledger", required=True)
    authoring_context.add_argument("--owner-bindings", required=True)
    authoring_context.add_argument(
        "--validate",
        default="",
        help="Validate an existing authoring context instead of building one.",
    )
    authoring_context.add_argument("--json", action="store_true")
    authoring_context.set_defaults(handler=_run_reverse_surface_authoring_context_command)

    fault_matrix = subparsers.add_parser(
        "fault-matrix-review",
        help=(
            "Read-only reconciliation of one native finite fault/recovery "
            "matrix; every leaf needs root cause, terminal, recovery, and proof."
        ),
    )
    fault_matrix.add_argument("--matrix", required=True, help="Fault matrix evidence JSON path.")
    fault_matrix.add_argument("--expected-case-id", action="append", default=[], help="Expected finite case id; repeat for every case.")
    fault_matrix.add_argument("--expected-input-fingerprint", default="")
    fault_matrix.add_argument("--expected-owner-id", default="")
    fault_matrix.add_argument("--expected-source-fingerprint", default="")
    fault_matrix.add_argument("--expected-model-fingerprint", default="")
    fault_matrix.add_argument("--expected-toolchain-fingerprint", default="")
    fault_matrix.add_argument("--expected-environment-fingerprint", default="")
    fault_matrix.add_argument("--json", action="store_true", help="Emit canonical JSON (always enabled).")
    fault_matrix.set_defaults(handler=_run_fault_matrix_review_command)

    self_check = subparsers.add_parser(
        "flowguard-self-blueprint-check",
        help="Read-only audit of FlowGuard's current checked-in self-blueprint.",
    )
    self_check.add_argument("--root", default=".", help="FlowGuard repository root.")
    self_check.add_argument("--compact", action="store_true")
    self_check.add_argument(
        "--include-architecture-reduction",
        action="store_true",
        help=(
            "Reuse this exact in-memory self-blueprint for the read-only "
            "architecture-reduction review."
        ),
    )
    self_check.add_argument(
        "--require-cleanup-release-ready",
        action="store_true",
        help=(
            "Require the composed architecture-reduction review to have no "
            "unresolved candidate and no authorized cleanup left unapplied."
        ),
    )
    self_check.add_argument(
        "--require-executed-evidence",
        action="store_true",
        help=(
            "Require current direct model-owner receipts and explicit native "
            "executed-case IDs for blueprint coverage."
        ),
    )
    self_check.add_argument(
        "--model-receipt-dir",
        default="",
        help=(
            "Use this exact model-owner receipt store for the read-only self "
            "blueprint; no receipt history scan or copying is performed."
        ),
    )
    self_check.add_argument(
        "--candidate-id",
        default="",
        help="Include exact detail for one architecture-reduction candidate.",
    )
    self_check.add_argument("--json", action="store_true")
    self_check.set_defaults(handler=_run_flowguard_self_blueprint_check_command)

    self_reduction = subparsers.add_parser(
        "flowguard-self-architecture-reduction-review",
        help=(
            "Read-only self-blueprint contraction audit; reports candidates "
            "and never rewrites production code."
        ),
    )
    self_reduction.add_argument(
        "--root", default=".", help="FlowGuard repository root."
    )
    self_reduction.add_argument("--compact", action="store_true")
    self_reduction.add_argument(
        "--candidate-id",
        default="",
        help="Include exact detail for one architecture-reduction candidate.",
    )
    self_reduction.add_argument("--json", action="store_true")
    self_reduction.set_defaults(
        handler=_run_flowguard_self_architecture_reduction_command
    )

    target_check = subparsers.add_parser(
        "target-system-blueprint-audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=(
            "Derive one provider-neutral target blueprint from strict frozen "
            "native artifacts; never runs providers or writes the target."
        ),
        description=(
            "Derive one provider-neutral target blueprint from strict frozen "
            "native artifacts. FlowGuard computes every layer status; callers "
            "cannot supply readiness layers or gaps."
        ),
    )
    target_check.add_argument(
        "--descriptor",
        required=True,
        help="Strict current target-system descriptor JSON path.",
    )
    target_check.add_argument(
        "--frozen-evidence",
        required=True,
        help="Strict current frozen provider-evidence JSON path.",
    )
    target_check.add_argument(
        "--native-report-set",
        required=True,
        help="Strict current native qualification report-set JSON path.",
    )
    target_check.add_argument("--json", action="store_true")
    target_check.set_defaults(handler=_run_target_system_blueprint_audit_command)

    affected_understanding = subparsers.add_parser(
        "affected-blueprint-understanding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=(
            "Read one exact normalized affected neighborhood and its readiness "
            "ledger without running providers, builders, or validation owners."
        ),
        description=(
            "Read one exact normalized affected neighborhood and its readiness "
            "ledger without running providers, builders, or validation owners."
        ),
    )
    affected_understanding.add_argument(
        "--root",
        default=".",
        help=(
            "Bounded task root used to resolve relative evidence inputs and to "
            "anchor the task-context snapshot."
        ),
    )
    affected_understanding.add_argument(
        "--index",
        help="Strict current affected-blueprint index JSON path.",
    )
    affected_understanding.add_argument(
        "--shard-store",
        help="JSON object mapping exact shard ids to content-addressed payloads.",
    )
    affected_understanding.add_argument(
        "--object-store",
        help="JSON object mapping exact object ids to content-addressed payloads.",
    )
    affected_understanding.add_argument(
        "--projection-root",
        help=(
            "Existing canonical projection directory. It is read selectively "
            "and is mutually exclusive with the three explicit store inputs."
        ),
    )
    affected_understanding.add_argument(
        "--affected-id",
        action="append",
        default=[],
        help="Exact affected behavior, model, surface, resource, test, or workflow id; repeatable.",
    )
    # Keep this option optional so a projection-root invocation can resolve a
    # unique seed from --changed-path, while explicit store invocations remain
    # compatible with the original affected-id protocol.
    affected_understanding.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Changed source path used only to explain the affected task scope; repeatable.",
    )
    affected_understanding.add_argument(
        "--task-summary",
        default="",
        help="Short caller-declared task intent preserved in the read-only task context.",
    )
    affected_understanding.add_argument(
        "--surface-catalog",
        help="Optional JSON object mapping surface ids to source coordinates/owners.",
    )
    affected_understanding.add_argument(
        "--accepted-snapshot",
        help="Optional JSON object containing the accepted model/code snapshot identity.",
    )
    affected_understanding.add_argument(
        "--accepted-snapshot-verified",
        action="store_true",
        help=(
            "Deprecated caller assertion; accepted currentness is never established "
            "from this flag and its use is rejected."
        ),
    )
    affected_understanding.add_argument("--json", action="store_true")
    affected_understanding.set_defaults(
        handler=_run_affected_blueprint_understanding_command
    )

    project_check = subparsers.add_parser(
        "project-blueprint-audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=(
            "Read-only Python-software convenience adapter for project "
            "blueprint audit; never writes the target or executes a "
            "target-system action. Use target-system-blueprint-audit for the "
            "provider-neutral frozen-native-artifact entry."
        ),
        description=(
            "Read-only Python-software convenience adapter for project "
            "blueprint audit; never writes the target or executes a "
            "target-system action. Use target-system-blueprint-audit for the "
            "provider-neutral frozen-native-artifact entry."
        ),
    )
    project_check.add_argument("--root", required=True, help="Bounded project root.")
    project_check.add_argument(
        "--definition", required=True, help="Strict current project-blueprint JSON."
    )
    project_check.add_argument(
        "--compact",
        action="store_true",
        help="Emit bounded status/counts without expanding the blueprint.",
    )
    project_check.add_argument("--json", action="store_true")
    project_check.set_defaults(handler=_run_project_blueprint_audit_command)

    candidate = subparsers.add_parser(
        "project-blueprint-candidate",
        help=(
            "Read-only unresolved behavior candidate discovery from one current implementation inventory."
        ),
    )
    candidate.add_argument("--inventory", required=True)
    candidate.add_argument("--root", required=True, help="Bounded current project root.")
    candidate.add_argument("--target-kind", default="software")
    candidate.add_argument(
        "--provider",
        action="append",
        default=[],
        help=(
            "Exact observation provider id; repeatable. When omitted, current "
            "inventory surface provider identities are used."
        ),
    )
    candidate.add_argument(
        "--compact",
        action="store_true",
        help="Return only depth/count/first-gap data for ordinary AI routing.",
    )
    candidate.add_argument("--json", action="store_true")
    candidate.set_defaults(handler=_run_project_blueprint_candidate_command)


def _add_simulator_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "simulator",
        help="List or execute manifest-registered FlowGuard models through their native runners.",
    )
    parser.add_argument("--root", default=".", help="FlowGuard project root.")
    parser.add_argument("--list", action="store_true", help="Audit and list registered models without executing them.")
    parser.add_argument("--model", action="append", default=[], help="Exact model id or glob; repeatable.")
    parser.add_argument("--all", action="store_true", help="Explicitly execute every model eligible for --tier.")
    parser.add_argument("--tier", choices=("fast", "focused", "full"), default="focused")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=float, help="Override each native runner timeout in seconds.")
    parser.add_argument("--output-dir", help="Retained run directory; defaults under .flowguard/evidence/simulator.")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output.")
    parser.add_argument("--full", action="store_true", help="Include complete bounded text summaries.")
    parser.set_defaults(handler=_run_simulator_command)


def _add_evidence_lifecycle_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    storage = subparsers.add_parser(
        "storage-audit",
        help="Run one read-light storage walk without content reads or hashes.",
    )
    storage.add_argument("--root", default=".flowguard", help="Bounded FlowGuard storage root.")
    storage.add_argument("--max-items", type=int, default=20, help="Largest-item sample size.")
    storage.add_argument("--json", action="store_true")
    storage.set_defaults(handler=_run_storage_audit_command)

    audit = subparsers.add_parser("evidence-audit", help="Read-only audit of FlowGuard evidence reachability and storage.")
    audit.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="audit")

    plan = subparsers.add_parser("evidence-gc-plan", help="Create an exact read-only evidence GC plan.")
    plan.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    plan.add_argument("--keep", type=int, default=2, help="Retain this many newest otherwise-collectible runs.")
    plan.add_argument("--include-legacy", action="store_true", help="Explicitly include lifecycle-unmanaged historical parents.")
    plan.add_argument(
        "--preserve",
        action="append",
        default=[],
        help="Exact audited run path to preserve; repeat for externally bound legacy evidence.",
    )
    plan.add_argument("--output", help="Optional plan artifact path.")
    plan.add_argument(
        "--storage-audit",
        action="store_true",
        help="Run the one-walk read-light storage audit before evidence audit and planning.",
    )
    plan.add_argument(
        "--storage-root",
        help="Optional exact storage root for --storage-audit; defaults to the evidence root parent.",
    )
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="plan")

    apply = subparsers.add_parser("evidence-gc-apply", help="Quarantine candidates from one exact current GC plan.")
    apply.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    apply.add_argument("--plan", required=True, help="GC plan JSON path.")
    apply.add_argument("--json", action="store_true")
    apply.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="apply")

    restore = subparsers.add_parser("evidence-gc-restore", help="Restore one exact evidence quarantine.")
    restore.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    restore.add_argument("--quarantine-id", required=True)
    restore.add_argument("--json", action="store_true")
    restore.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="restore")

    purge = subparsers.add_parser("evidence-gc-purge", help="Purge one exact quarantine after current/pin replay.")
    purge.add_argument("--root", default=".flowguard/evidence", help="Evidence root.")
    purge.add_argument("--quarantine-id", required=True)
    purge.add_argument("--json", action="store_true")
    purge.set_defaults(handler=_run_evidence_lifecycle_command, evidence_action="purge")

    settle = subparsers.add_parser(
        "evidence-settle-interruption",
        help="Settle only named dead-process residual leases into immutable interrupted evidence.",
    )
    settle.add_argument("--lock-root", required=True, help="Exact execution-lease directory.")
    settle.add_argument("--plan-id", required=True, help="Exact frozen validation plan id.")
    settle.add_argument("--process-id", required=True, type=int, help="Former producer process id.")
    settle.add_argument("--operator-reason", required=True)
    settle.add_argument("--observed-by", required=True)
    settle.add_argument("--observation-method", required=True)
    settle.add_argument("--observed-at-epoch", required=True, type=float)
    settle.add_argument(
        "--descendant-process-id",
        action="append",
        type=int,
        default=[],
        help="Observed live descendant; any supplied id blocks settlement.",
    )
    settle.add_argument(
        "--lease-json",
        action="append",
        required=True,
        help=(
            "Exact JSON object with owner_id, resource_key, execution_key, and lease_token; repeat."
        ),
    )
    settle.add_argument("--json", action="store_true")
    settle.set_defaults(
        handler=_run_evidence_lifecycle_command,
        evidence_action="settle_interruption",
    )


def _add_completion_readiness_parser(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Register the canonical public readiness envelope command."""

    readiness = subparsers.add_parser(
        "completion-readiness",
        help=(
            "Build one bounded read-only completion-readiness envelope; "
            "does not start a heavy producer."
        ),
    )
    readiness.add_argument("--root", default=".")
    readiness.add_argument("--objective-change", default="")
    readiness.add_argument(
        "--completion-objective-change",
        help=(
            "Named current OpenSpec change whose reviewed artifacts derive the "
            "explicit completion objective identity"
        ),
    )
    readiness.add_argument(
        "--completion-work-id",
        help="Stable identity for this completion task's finite budget.",
    )
    readiness.add_argument(
        "--completion-authorization",
        help=(
            "Explicit typed same-work authorization for one new finite "
            "completion cycle; the artifact must be inside the repository."
        ),
    )
    readiness.add_argument(
        "--claim-scope",
        choices=("local_validation", "release"),
        default="local_validation",
        help="Use local_validation for ordinary work; release is explicit.",
    )
    readiness.add_argument("--completion-repair-link")
    readiness.add_argument("--repair-from-epoch")
    readiness.add_argument("--repair-regression-evidence")
    readiness.add_argument("--receipt-dir")
    readiness.add_argument("--model-receipt-dir")
    readiness.add_argument(
        "--model-parent-receipt",
        help=(
            "Exact typed current full-model parent artifact forwarded to the "
            "readiness plan; it is verified without historical discovery."
        ),
    )
    readiness.add_argument("--formal-root")
    readiness.add_argument(
        "--shadow-root",
        help="Required only for an explicit release claim.",
    )
    readiness.add_argument("--installed-root")
    readiness.add_argument("--output-dir", required=True)
    readiness.add_argument("--gate-timeout", type=float, default=900.0)
    readiness.add_argument("--model-jobs", type=int, default=1)
    readiness.add_argument("--model-timeout", type=float)
    readiness.add_argument(
        "--require-executed-evidence",
        action="store_true",
        help=(
            "Freeze readiness with the same strict native model-owner and "
            "direct-leaf evidence requirement used by the final parent."
        ),
    )
    readiness.add_argument("--skillguard", default="all")
    readiness.add_argument("--json", action="store_true")

    def _handler(args: argparse.Namespace) -> int:
        from .completion_readiness import main as readiness_main

        argv: list[str] = ["--root", str(args.root), "--output-dir", str(args.output_dir)]
        if args.shadow_root:
            argv.extend(("--shadow-root", str(args.shadow_root)))
        # These options are declared on the same parser above.  Spell out the
        # finite forwarding table so the implementation inventory can prove
        # the command boundary without admitting an open ``getattr`` selector.
        forwarded_values = (
            (args.objective_change, "--objective-change"),
            (args.completion_objective_change, "--completion-objective-change"),
            (args.completion_work_id, "--completion-work-id"),
            (args.completion_authorization, "--completion-authorization"),
            (args.claim_scope, "--claim-scope"),
            (args.completion_repair_link, "--completion-repair-link"),
            (args.repair_from_epoch, "--repair-from-epoch"),
            (args.repair_regression_evidence, "--repair-regression-evidence"),
            (args.receipt_dir, "--receipt-dir"),
            (args.model_receipt_dir, "--model-receipt-dir"),
            (args.model_parent_receipt, "--model-parent-receipt"),
            (args.formal_root, "--formal-root"),
            (args.installed_root, "--installed-root"),
            (args.gate_timeout, "--gate-timeout"),
            (args.model_jobs, "--model-jobs"),
            (args.model_timeout, "--model-timeout"),
            (args.require_executed_evidence, "--require-executed-evidence"),
            (args.skillguard, "--skillguard"),
        )
        for value, option in forwarded_values:
            if option == "--require-executed-evidence":
                if value:
                    argv.append(option)
            elif value is not None and value != "":
                argv.extend((option, str(value)))
        if args.json:
            argv.append("--json")
        return readiness_main(argv)

    readiness.set_defaults(handler=_handler)


def _add_release_verify_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Expose the target-neutral release consumer to installed projects."""

    release = subparsers.add_parser(
        "release-verify",
        help="Verify a target descriptor and its functional release evidence.",
    )
    release.add_argument("--root", default=".")
    release.add_argument("--target", required=True, help="Target descriptor JSON.")
    release.add_argument("--phase", choices=("local-candidate", "tag", "published"), required=True)
    release.add_argument("--parent-receipt", required=True)
    release.add_argument("--receipt-root", default="")
    release.add_argument("--candidate-receipt", default="")
    release.add_argument("--repository", default="")
    release.add_argument("--output", default="")
    release.add_argument("--json", action="store_true")

    def _handler(args: argparse.Namespace) -> int:
        from .release_verification import (
            ReleaseTarget,
            save_release_verification_receipt,
            verify_local_candidate,
            verify_published_release,
            verify_tagged_release,
        )

        try:
            target = ReleaseTarget.from_json(args.target)
            if args.phase in {"tag", "published"} and not args.candidate_receipt:
                raise ValueError("--candidate-receipt is required for tag/published")
            common = {
                "parent_receipt": args.parent_receipt,
                "receipt_root": args.receipt_root or Path(args.root) / ".flowguard" / "evidence" / "validation-owners",
                "target": target,
            }
            if args.phase == "local-candidate":
                receipt = verify_local_candidate(args.root, **common)
            elif args.phase == "tag":
                receipt = verify_tagged_release(args.root, candidate_receipt=args.candidate_receipt, **common)
            else:
                receipt = verify_published_release(args.root, repository=args.repository or None, candidate_receipt=args.candidate_receipt, **common)
            if args.output:
                save_release_verification_receipt(receipt, args.output)
            _emit_payload(receipt.to_dict(), as_json=args.json)
            return 0 if receipt.ok else 1
        except (OSError, TypeError, ValueError) as exc:
            _emit_payload({"status": "blocked", "error": str(exc)}, as_json=args.json)
            return 1

    release.set_defaults(handler=_handler)


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
    if operation in {"change", "release"} and "request" not in values:
        raise ValueError("--request is required")
    root = Path(str(values["root"])).resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    values["root"] = root
    return values


def _compact_operation(operation: str, argv: list[str]) -> int:
    try:
        values = _compact_parse(operation, argv)
        root: Path = values["root"]
        request: Mapping[str, Any] = {}
        request_path = values.get("request")
        if request_path:
            candidate = Path(str(request_path))
            request_file = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
            try:
                request_file.relative_to(root)
            except ValueError as exc:
                raise ValueError("request path must remain under --root") from exc
            request = _strict_json_loads(request_file.read_text(encoding="utf-8"))
            if not isinstance(request, Mapping):
                raise ValueError("request JSON must be an object")
        payload: dict[str, Any] = {
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


def legacy_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard",
        description="Run flowguard checks through thin Python API wrappers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_existing_command_subparsers(subparsers)
    _add_route_reference_parser(subparsers)
    for command in FILE_TEMPLATE_COMMANDS:
        _add_file_template_parser(subparsers, command)
    _add_artifact_upgrade_parser(subparsers)
    _add_behavior_commitment_query_parser(subparsers)
    _add_risk_template_search_parser(subparsers)
    _add_risk_template_harvest_parser(subparsers)
    _add_risk_template_harvest_review_parser(subparsers)
    _add_work_context_parser(subparsers)
    _add_portable_model_parsers(subparsers)
    _add_implementation_blueprint_parsers(subparsers)
    _add_simulator_parser(subparsers)
    _add_evidence_lifecycle_parsers(subparsers)
    _add_model_system_parsers(subparsers)
    _add_model_maturation_parser(subparsers)
    _add_project_layout_parser(subparsers)
    _add_completion_readiness_parser(subparsers)
    _add_release_verify_parser(subparsers)
    _add_project_adoption_parser(
        subparsers,
        "project-audit",
        action="audit",
        help_text="Read-only audit of target-project FlowGuard AGENTS/manifest adoption state.",
    )
    _add_project_adoption_parser(
        subparsers,
        "project-adopt",
        action="adopt",
        help_text="Write or refresh target-project FlowGuard AGENTS/manifest adoption records.",
    )
    _add_project_adoption_parser(
        subparsers,
        "project-upgrade",
        action="upgrade",
        help_text="Explicitly update target-project FlowGuard records to the installed package version.",
    )
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-start", help="Append an in-progress adoption log entry."),
        default_status="in_progress",
    )
    _add_adoption_entry_args(
        subparsers.add_parser("adoption-finish", help="Append a final adoption log entry."),
        default_status="auto",
    )
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
